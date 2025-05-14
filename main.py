from flask import Flask, request
import requests
import os
import json
import traceback

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
LANGFLOW_API_KEY = os.getenv("LANGFLOW_API_KEY")
LANGFLOW_URL = "https://langflow.4h30.space/api/v1/run/210e3265-ac54-41da-82ae-aa95eebf0118?stream=false"

MAX_LENGTH = 4096

# ✅ Hàm chia nhỏ text theo dòng, không vượt quá 4096 ký tự
def split_long_message(text, max_length=MAX_LENGTH):
    lines = text.split('\n')
    chunks = []
    current_chunk = ""

    for line in lines:
        if len(current_chunk) + len(line) + 1 <= max_length:
            current_chunk += line + "\n"
        else:
            chunks.append(current_chunk.strip())
            current_chunk = line + "\n"

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks

# ✅ Hàm gửi tin nhắn qua Telegram, chia nhỏ nếu cần
def send_telegram_message(chat_id, text):
    if not isinstance(text, str):
        text = str(text)

    for chunk in split_long_message(text):
        payload = {"chat_id": chat_id, "text": chunk}
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json=payload
        )
        print(f"[Telegram] {response.status_code} → {response.text}")

# ✅ Hàm gọi Langflow API
def call_langflow(user_input):
    headers = {
        "Content-Type": "application/json",
        "x-api-key": LANGFLOW_API_KEY
    }

    body = {
        "input_type": "chat",
        "output_type": "chat",
        "tweaks": {
            "TextInput-3JR1W": {
                "input_value": user_input
            },
            "Agent-Xxy8r": {
                "add_current_date_tool": True,
                "agent_llm": "OpenAI",
                "api_key": "OPENAI_API_KEY",
                "handle_parsing_errors": True,
                "model_name": "gpt-4o-mini",
                "temperature": 0.1,
                "verbose": True
            }
        }
    }

    print("\n--- [DEBUG] Gửi tới Langflow ---")
    print(json.dumps(body, indent=2))

    try:
        response = requests.post(LANGFLOW_URL, headers=headers, data=json.dumps(body))
        data = response.json()

        print("\n--- [DEBUG] Trả về từ Langflow ---")
        print(json.dumps(data, indent=2))

        outputs = data.get("outputs", [])
        messages = []

        for block in outputs:
            for out in block.get("outputs", []):
                if isinstance(out, dict):
                    msg = out.get("message", {}).get("text")
                    if msg:
                        messages.append(msg)
                    elif "text" in out:
                        messages.append(out["text"])
                    else:
                        messages.append(json.dumps(out))
                elif isinstance(out, str):
                    messages.append(out)
                else:
                    messages.append(str(out))

        return messages if messages else ["⚠️ Không có nội dung output nào được tìm thấy."]
    except Exception as e:
        traceback.print_exc()
        return [f"❌ Lỗi khi gọi Langflow: {str(e)}"]

# ✅ Webhook nhận tin nhắn từ Telegram
@app.route(f"/webhook/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    print("\n--- [DEBUG] Telegram Webhook ---")
    print(json.dumps(data, indent=2))

    if "message" in data and "text" in data["message"]:
        chat_id = data["message"]["chat"]["id"]
        user_text = data["message"]["text"]

        send_telegram_message(chat_id, "⏳ Đang xử lý...")

        outputs = call_langflow(user_text)
        for message in outputs:
            send_telegram_message(chat_id, message)

    return "ok", 200

# ✅ Endpoint kiểm tra bot sống
@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is running!"

# ✅ Chạy local
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Running on port {port}...")
    app.run(host="0.0.0.0", port=port)
