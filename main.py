from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import openai
import os
from dotenv import load_dotenv
import re

# .envから環境変数読み込み
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

openai.api_key = OPENAI_API_KEY
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

app = Flask(__name__)

# ✅ 大くんのLINEユーザーIDをここに入れる！
WHITELIST_USER_IDS = {"U61787e7f07a6585c8c4c8f31b7edd734"}  # ←ここを実際のIDに変更してね！
authorized_groups = set()

# 日本語判定（ひらがな or カタカナ）
def is_japanese(text):
    return bool(re.search(r'[ぁ-んァ-ン]', text))

# GPT翻訳処理
def translate_with_gpt(text, target_lang):
    prompt = f"次の文章を{target_lang}に自然な口調で翻訳してください：\n{text}"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        temperature=0.7,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except Exception as e:
        print(f"エラー: {e}")
        abort(400)

    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    group_id = getattr(event.source, 'group_id', None)
    text = event.message.text.strip()

    print(f"発言者のID: {user_id}")
    print(f"受信メッセージ: {text}")

    if not group_id:
        return

    # ✅ ホワイトリスト制限：許可された人がグループにいれば有効
    if group_id not in authorized_groups:
        if user_id in WHITELIST_USER_IDS:
            authorized_groups.add(group_id)
            print(f"グループ {group_id} を許可しました")
        else:
            print("ホワイトリスト外ユーザーからの発言。無視します。")
            return

    # GPTちゃん呼び出し処理
    if text.startswith("@GPTちゃん"):
        question = text.replace("@GPTちゃん", "").strip()
        if not question:
            return
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            temperature=0.7,
            messages=[
                {"role": "system", "content": "親切でおちゃめなアシスタントです。"},
                {"role": "user", "content": question}
            ]
        )
        reply = response.choices[0].message.content.strip()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # 翻訳処理（日本語↔ロシア語）
    if is_japanese(text):
        translated = translate_with_gpt(text, "ロシア語")
    else:
        translated = translate_with_gpt(text, "日本語")

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=translated))

# ✅ ポート明示（Render向け）
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)