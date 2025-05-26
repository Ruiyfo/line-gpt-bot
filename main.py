from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import openai
import os
from dotenv import load_dotenv
import re

# .envの読み込み
load_dotenv()

app = Flask(__name__)

# 環境変数からキー取得
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
openai.api_key = OPENAI_API_KEY

# ✅ ホワイトリスト（発言者のユーザーID）
WHITELIST_USER_IDS = {"Uxxxxxxxxxxxxxxxxxxxxxxxxxx"}  # 大くんのLINEユーザーIDをここに！

# ✅ 言語判定：かな文字が入っていれば日本語
def is_japanese(text):
    return re.search(r'[ぁ-んァ-ン]', text) is not None

# ✅ GPTを使った翻訳（日本語⇔ロシア語）
def translate_with_gpt(text, source_lang):
    if source_lang == 'ja':
        prompt = f"以下の日本語をロシア語に自然に翻訳してください：\n{text}"
    else:
        prompt = f"以下のロシア語を日本語に自然に翻訳してください：\n{text}"

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "あなたは優秀な翻訳者です。"},
            {"role": "user", "content": prompt}
        ]
    )
    return response['choices'][0]['message']['content'].strip()

# ✅ Webhookの入口
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    print("📩 Webhook受信！")
    print("🔸 本文:", body)

    try:
        handler.handle(body, signature)
    except Exception as e:
        print("🚨 エラー:", e)
        abort(400)

    return 'OK'

# ✅ メッセージ受信処理
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    group_id = getattr(event.source, 'group_id', None)
    text = event.message.text.strip()

    print(f"👤 user_id: {user_id}")
    print(f"💬 text: {text}")

    # ✅ グループでホワイトリスト以外の人なら無視
    if group_id and user_id not in WHITELIST_USER_IDS:
        print("⛔ ホワイトリスト外ユーザー（無視）")
        return

    # ✅ GPTちゃんへの質問機能
    if text.startswith("@GPTちゃん"):
        question = text.replace("@GPTちゃん", "").strip()
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "あなたは親切で楽しいAIアシスタントです。"},
                {"role": "user", "content": question}
            ]
        )
        answer = response['choices'][0]['message']['content'].strip()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=answer))
        return

    # ✅ 翻訳実行
    if is_japanese(text):
        translated = translate_with_gpt(text, source_lang='ja')
    else:
        translated = translate_with_gpt(text, source_lang='ru')

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=translated))

# ✅ Flask起動
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
