from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import openai
import os
from dotenv import load_dotenv
import re

# .env 読み込み
load_dotenv()

app = Flask(__name__)

# 環境変数からAPIキーを取得
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
openai.api_key = OPENAI_API_KEY

# ✅ ホワイトリスト（発言者の user_id をここに登録）
WHITELIST_USER_IDS = {"U61787e7f07a6585c8c4c8f31b7edd734"}  # ← 大くんの user_id をここに！

# ✅ 言語判定（ひらがな or カタカナがあれば日本語と判断）
def is_japanese(text):
    return re.search(r'[ぁ-んァ-ン]', text) is not None

# ✅ GPTを使って日本語⇔ロシア語を翻訳
def translate_with_gpt(text, source_lang):
    if source_lang == 'ja':
        prompt = f"以下の日本語をロシア語に自然な文章で翻訳してください：\n{text}"
    else:
        prompt = f"以下のロシア語を日本語に自然な文章で翻訳してください：\n{text}"

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        temperature=0.7,  # 🎯 ← ここが大くん指定の温度設定！
        messages=[
            {"role": "system", "content": "あなたは日本語とロシア語に精通したプロの翻訳者です。"},
            {"role": "user", "content": prompt}
        ]
    )
    return response['choices'][0]['message']['content'].strip()

# ✅ LINE Webhook の受け口
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    print("📩 Webhook受信")
    print("📨 内容:", body)

    try:
        handler.handle(body, signature)
    except Exception as e:
        print("🚨 エラー:", e)
        abort(400)

    return 'OK'

# ✅ LINEメッセージ処理
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    group_id = getattr(event.source, 'group_id', None)
    text = event.message.text.strip()

    print(f"👤 user_id: {user_id}")
    print(f"💬 message: {text}")

    # ✅ グループ内でホワイトリスト外の発言は無視
    if group_id and user_id not in WHITELIST_USER_IDS:
        print("⛔ ホワイトリストに含まれていません。無視します。")
        return

    # ✅ 「@GPTちゃん」で呼びかけ → ChatGPT回答
    if text.startswith("@GPTちゃん"):
        question = text.replace("@GPTちゃん", "").strip()
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            temperature=0.7,
            messages=[
                {"role": "system", "content": "あなたは親切で楽しいAIアシスタントです。"},
                {"role": "user", "content": question}
            ]
        )
        answer = response['choices'][0]['message']['content'].strip()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=answer))
        return

    # ✅ 翻訳処理（日本語⇔ロシア語）
    if is_japanese(text):
        translated = translate_with_gpt(text, source_lang='ja')
    else:
        translated = translate_with_gpt(text, source_lang='ru')

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=translated))

# ✅ Flaskアプリ起動
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
