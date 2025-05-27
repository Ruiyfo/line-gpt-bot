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

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
openai.api_key = OPENAI_API_KEY

WHITELIST_USER_IDS = {
    "U61787e7f07a6585c8c4c8f31b7edd734"  # 大くんのLINE user_id
}

# ✅ ファイルから許可済みグループIDを読み込み
ALLOWED_GROUP_IDS = set()
if os.path.exists("allowed_groups.txt"):
    with open("allowed_groups.txt", "r") as f:
        ALLOWED_GROUP_IDS = set(line.strip() for line in f if line.strip())

# ✅ 日本語判定
def is_japanese(text):
    return re.search(r'[ぁ-んァ-ン]', text) is not None

# ✅ 翻訳処理
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

    try:
        handler.handle(body, signature)
    except Exception:
        abort(400)

    return "OK"

# ✅ メッセージ処理
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    source_type = event.source.type
    group_id = getattr(event.source, "group_id", None)
    text = event.message.text.strip()

    # 個人チャットは無視
    if source_type == "user":
        return

    # グループ許可チェック
    if group_id not in ALLOWED_GROUP_IDS:
        if user_id in WHITELIST_USER_IDS:
            ALLOWED_GROUP_IDS.add(group_id)
            with open("allowed_groups.txt", "a") as f:
                f.write(f"{group_id}\n")
        else:
            return

    # @GPTちゃん → ChatGPT応答
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

    # 翻訳処理
    source_lang = 'ja' if is_japanese(text) else 'ru'
    translated = translate_with_gpt(text, source_lang)
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=translated))

# ✅ Flaskアプリ起動
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
