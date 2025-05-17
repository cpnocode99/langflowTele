from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
LANGFLOW_URL = os.getenv("LANGFLOW_URL")
LANGFLOW_API_KEY = os.getenv("LANGFLOW_API_KEY")

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("[ERROR] Gửi tin nhắn Telegram:", str(e))

def extract_all_text_outputs(outputs):
    seen = set()
    results = []

    for i, output_block in enumerate(outputs):
        for sub in output_block.get("outputs", []):
            message = (
                sub.get("results", {})
                   .get("message", {})
                   .get("text", "")
                   .strip()
            )
            if message and message not in seen:
                results.append(message)
                seen.add(message)

    return results if results else ["✅ Langflow không trả về nội dung phù hợp."]

def call_langflow(user_input):
    headers = {
        "Content-Type": "application/json",
        "x-api-key": LANGFLOW_API_KEY
    }

    body = {
        "output_type": "chat",
        "input_type": "text",
        "tweaks": {
            "TextInput-xpmxA": {
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

    try:
        response = requests.post(LANGFLOW_URL, headers=headers, data=json.dumps(body))
        if response.status_code == 200:
            data = response.json()
            return extract_all_text_outputs(data.get("outputs", []))
        else:
            return [f"❌ Lỗi API ({response.status_code})"]
    except Exception as e:
        return [f"❌ Lỗi khi gọi API: {str(e)}"]

def send_multiple_telegram_messages(chat_id, messages):
    for msg in messages:
        send_telegram_message(chat_id, msg)

@app.route(f"/webhook/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    print("--- [DEBUG] Telegram Webhook ---")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    if "message" in data and "text" in data["message"]:
        user_text = data["message"]["text"]
        chat_id = data["message"]["chat"]["id"]

        if user_text.lower().startswith("/ai"):
            actual_text = user_text[3:].strip()
            send_telegram_message(chat_id, "⏳ Đang xử lý...")
            messages = call_langflow(actual_text)
            send_multiple_telegram_messages(chat_id, messages)

    return "ok", 200

@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is running!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
