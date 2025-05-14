from flask import Flask, request
import requests
import os
import json
import traceback

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
LANGFLOW_API_KEY = os.getenv("LANGFLOW_API_KEY")
LANGFLOW_URL = "https://langflow.4h30.space/api/v1/run/210e3265-ac54-41da-82ae-aa95eebf0118?stream=false"

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    response = requests.post(url, json=payload)
    print(f"[Telegram] Status {response.status_code}: {response.text}")

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

    print("\n--- [DEBUG] Request gửi đến Langflow ---")
    print(json.dumps(body, indent=2))

    try:
        response = requests.post(LANGFLOW_URL, headers=headers, data=json.dumps(body))
        print(f"\n--- [DEBUG] Langflow Status {response.status_code} ---")
        data = response.json()
        print(json.dumps(data, indent=2))

        outputs = data.get("outputs", [])
        messages = []

        for block in outputs:
            for out in block.get("outputs", []):
                if isinstance(out, dict):
                    # Ưu tiên lấy message["text"] nếu có
                    text = out.get("message", {}).get("text")
                    if text:
                        messages.append(text)
                    else:
                        messages.append(json.dumps(out))
                elif isinstance(out, str):
                    messages.append(out)
                else:
                    messages.append(str(out))

        return "\n\n---\n\n".join(messages) if messages else "⚠️ Không có nội dung output nào được tìm thấy."

    except Exception as e:
        traceback.print_exc()
        return f"❌ Lỗi khi gọi Langflow API: {str(e)}"

@app.route(f"/webhook/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    print("\n--- [DEBUG] Telegram Webhook ---")
    print(json.dumps(data, indent=2))

    if "message" in data and "text" in data["message"]:
        chat_id = data["message"]["chat"]["id"]
        user_text = data["message"]["text"]

        send_telegram_message(chat_id, "⏳ Đang xử lý...")
        output = call_langflow(user_text)
        send_telegram_message(chat_id, output)

    return "ok", 200

@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is running!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Running on port {port}...")
    app.run(host="0.0.0.0", port=port)
