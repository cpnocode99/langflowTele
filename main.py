from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
LANGFLOW_API_KEY = os.getenv("LANGFLOW_API_KEY")
LANGFLOW_URL = "https://langflow.4h30.space/api/v1/run/210e3265-ac54-41da-82ae-aa95eebf0118?stream=false"

def send_telegram_message(chat_id, text):
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(telegram_url, json=payload)

def call_langflow(user_text):
    headers = {
        "Content-Type": "application/json",
        "x-api-key": LANGFLOW_API_KEY
    }

    body = {
        "output_type": "chat",
        "input_type": "text",
        "tweaks": {
            "TextInput-3JR1W": {"input_value": user_text},
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
            return response.json().get("result", {}).get("output", "✅ Gọi API thành công nhưng không có dữ liệu trả về.")
        else:
            return f"❌ Lỗi API: {response.status_code}"
    except Exception as e:
        return f"❌ Lỗi khi gọi API: {str(e)}"

@app.route(f"/webhook/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data and "text" in data["message"]:
        chat_id = data["message"]["chat"]["id"]
        user_text = data["message"]["text"]

        send_telegram_message(chat_id, "⏳ Đang xử lý...")

        output = call_langflow(user_text)
        send_telegram_message(chat_id, output)

    return "ok", 200

@app.route("/", methods=["GET"])
def index():
    return "Bot is running!"

