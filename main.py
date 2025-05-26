from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import openai
import os
from dotenv import load_dotenv
import re

# .env読み込み
load_dotenv()

app = Flask(__name__)

# 環境変数の取得
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
openai.api_key = OPENAI_API_KEY

# ✅ ホワイトリスト（大くんのuser_idをここに入れてね！）
WHITELIST_USER_IDS = {
    "U61787e7f07a6585c8c4c8f31b7edd734"
}

# ✅ 日本語かどうかを判定（ひらがな or カタカナ含むか）
def is_japanese(text):
    return re.search(r'[ぁ-んァ-ン]', text) is not None

# ✅ 翻訳処理（日本語⇔ロシア語）
def translate_with_gpt(text, source_lang):
    if source_lang == 'ja':
        prompt = f"以下の日本語をロシア語に自然な文章で翻訳してください：\n{text}"
    else:
        prompt = f"以下のロシア語を日本語に自然な文章で翻訳してください：\n{text}"

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        temperature=0.7,
        messages=[
            {"role": "system", "content": "あなたは日本語とロシア語に精通したプロの翻訳者です。"},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

# ✅ Webhookエンドポイント
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)

    print("📩 Webhook受信")
    print("📨 body:", body)

    try:
        handler.handle(body, signature)
    except Exception as e:
        print("🚨 エラー:", e)
        abort(400)

    return "OK"

# ✅ メッセージ受信処理
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    source_type = event.source.type  # "user" or "group"
    group_id = getattr(event.source, "group_id", None)
    text = event.message.text.strip()

    print(f"👤 user_id: {user_id}")
    print(f"👥 source_type: {source_type}")
    print(f"💬 message: {text}")

    # ✅ ホワイトリストチェック（グループのみ）
    if source_type == "group":
        if user_id not in WHITELIST_USER_IDS:
            print(f"⛔ グループ発言者 {user_id} はホワイトリスト外。無視します。")
            return
        else:
            print(f"✅ グループ発言者 {user_id} はホワイトリストOK。処理を続行します。")
    else:
        print("✅ 個人チャットなのでホワイトリストチェックスキップ。")

    # ✅ @GPTちゃんでAI応答
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
        answer = response.choices[0].message.content.strip()
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
