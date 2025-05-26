from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import openai
import os
from dotenv import load_dotenv
import re

# 環境変数読み込み
load_dotenv()

app = Flask(__name__)

# LINEとOpenAIのAPIキー
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
openai.api_key = OPENAI_API_KEY

# ホワイトリスト（LINEユーザーID）
WHITELIST_USER_IDS = {"Uxxxxxxxxxxxxxxxxxxxx"}  # 大くんのUser IDをここに入れてね！

# 言語判別（かな文字があれば日本語）
def is_japanese(text):
    return bool(re.search(r'[ぁ-んァ-ン]', text))

# GPT翻訳（日本語⇔繁體中文）
def translate_with_gpt(text, source_lang):
    if source_lang == 'ja':
        prompt = f"以下の日本語を台湾華語（繁體字）に自然に翻訳してください：\n{text}"
    else:
        prompt = f"以下の台湾華語（繁體字）を日本語に自然に翻訳してください：\n{text}"

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "あなたは優秀な翻訳家です。"},
            {"role": "user", "content": prompt}
        ]
    )
    return response['choices'][0]['message']['content'].strip()

# Webhook受け取り
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    print("🔔 リクエスト受信！")
    print("📨 本文:", body)

    try:
        handler.handle(body, signature)
    except Exception as e:
        print("🚨 エラー発生:", e)
        abort(400)

    return 'OK'

# メッセージ処理
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    group_id = getattr(event.source, 'group_id', None)
    text = event.message.text.strip()

    print(f"👤 user_id: {user_id}")
    print(f"👥 group_id: {group_id}")
    print(f"💬 message: {text}")

    # グループで、ホワイトリストユーザーが含まれてなければ無視
    if group_id and user_id not in WHITELIST_USER_IDS:
        return

    # @GPTちゃん 呼び出し
    if text.startswith("@GPTちゃん"):
        question = text.replace("@GPTちゃん", "").strip()
        reply = translate_with_gpt(question, source_lang='ja')
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # 翻訳処理（日本語⇔台湾華語）
    if is_japanese(text):
        translated = translate_with_gpt(text, source_lang='ja')
    else:
        translated = translate_with_gpt(text, source_lang='zh')

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=translated))

# Flask起動
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
