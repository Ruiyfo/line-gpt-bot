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

# ✅ ホワイトリスト（最初にBotを有効にできるuser_id）
WHITELIST_USER_IDS = {
    "U61787e7f07a6585c8c4c8f31b7edd734"  # 大くんのLINE user_id
}

# ✅ 許可済みグループの記憶（メモリ上／一時的）
ALLOWED_GROUP_IDS = set()

# ✅ 日本語判定（かな文字が含まれていれば日本語）
def is_japanese(text):
    return re.search(r'[ぁ-んァ-ン]', text) is not None

# ✅ 翻訳（日本語⇔ロシア語）
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

# ✅ メッセージイベント処理
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    source_type = event.source.type  # "user" または "group"
    group_id = getattr(event.source, "group_id", None)
    text = event.message.text.strip()

    print(f"👤 user_id: {user_id}")
    print(f"👥 source_type: {source_type}")
    print(f"💬 message: {text}")
    
    # ✅ 個人チャットなら即スルー
    if source_type == "user":
        print("⛔ 個人チャットなので無視します。")
        return

    # ✅ グループチャット：最初にホワイトリストユーザーが発言したら許可
    if source_type == "group":
        if group_id in ALLOWED_GROUP_IDS:
            print(f"✅ 許可済みグループ {group_id}。処理続行。")
        elif user_id in WHITELIST_USER_IDS:
            print(f"✅ ホワイトリストユーザー {user_id} の発言により、グループ {group_id} を許可！")
            ALLOWED_GROUP_IDS.add(group_id)
        else:
            print(f"⛔ グループ {group_id} の発言者 {user_id} は許可されていません。")
            return
    else:
        print("✅ 個人チャットなのでホワイトリストチェック不要。")

    # ✅ @GPTちゃん応答
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

    # ✅ 翻訳処理（日本語→ロシア語／ロシア語→日本語）
    if is_japanese(text):
        translated = translate_with_gpt(text, source_lang='ja')
    else:
        translated = translate_with_gpt(text, source_lang='ru')

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=translated))

# ✅ Flaskアプリ起動
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
