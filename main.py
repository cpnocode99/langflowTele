from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
LANGFLOW_API_KEY = os.getenv("LANGFLOW_API_KEY")
LANGFLOW_URL = "https://langflow.4h30.space/api/v1/run/210e3265-ac54-41da-82ae-aa95eebf0118?stream=false"

MAX_LENGTH = 4096

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

def send_telegram_message(chat_id, text):
    if not isinstance(text, str):
        text = str(text)

    for chunk in split_long_message(text):
        payload = {"chat_id": chat_id, "text": chunk}
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json=payload
        )

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

    try:
        response = requests.post(LANGFLOW_URL, headers=headers, data=json.dumps(body))
        data = response.json()

        outputs = data.get("outputs", [])
        messages = []

        for block in outputs:
            for out in block.get("outputs", []):
                msg = (
                    out.get("results", {}).get("message", {}).get("text") or
                    out.get("outputs", {}).get("message", {}).get("message") or
                    (
                        out.get("messages", [{}])[0].get("message")
                        if isinstance(out.get("messages", None), list) and out["messages"]
                        else None
                    ) or
                    out.get("message", {}).get("text") or
                    out.get("text") or
                    json.dumps(out)
                )
                messages.extend(split_long_message(str(msg)))

        return messages if messages else ["⚠️ Không có output."]
    except Exception:
        return ["❌ Lỗi khi gọi Langflow hoặc xử lý dữ liệu."]

@app.route(f"/webhook/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()

    if "message" in data and "text" in data["message"]:
        chat_id = data["message"]["chat"]["id"]
        user_text = data["message"]["text"]

        send_telegram_message(chat_id, "⏳ Đang xử lý...")

        outputs = call_langflow(user_text)
        for message in outputs:
            send_telegram_message(chat_id, message)

    return "ok", 200

@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is running!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
