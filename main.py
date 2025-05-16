from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

# ENV
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
LANGFLOW_API_KEY = os.getenv("LANGFLOW_API_KEY")
LANGFLOW_URL = os.getenv("LANGFLOW_URL")

if not LANGFLOW_URL:
    raise RuntimeError("❌ LANGFLOW_URL is not set.")

MAX_LENGTH = 4096

def split_long_message(text, max_length=MAX_LENGTH):
    lines = text.split('\n')
    chunks, chunk = [], ""
    for line in lines:
        if len(chunk) + len(line) + 1 <= max_length:
            chunk += line + "\n"
        else:
            chunks.append(chunk.strip())
            chunk = line + "\n"
    if chunk:
        chunks.append(chunk.strip())
    return chunks

def send_telegram_message(chat_id, text):
    if not isinstance(text, str):
        text = str(text)
    for chunk in split_long_message(text):
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": chunk}
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
        data = response.json()

        outputs = data.get("outputs", [])
        messages = []

        for block in outputs:
            for out in block.get("outputs", []):
                candidates = []

                # All possible message formats
                if out.get("results", {}).get("message", {}).get("text"):
                    candidates.append(out["results"]["message"]["text"])
                if out.get("outputs", {}).get("message", {}).get("message"):
                    candidates.append(out["outputs"]["message"]["message"])
                if out.get("message", {}).get("text"):
                    candidates.append(out["message"]["text"])
                if out.get("text"):
                    candidates.append(out["text"])
                if out.get("messages"):
                    for m in out["messages"]:
                        if m.get("message"):
                            candidates.append(m["message"])

                if not candidates:
                    candidates.append(json.dumps(out))

                for msg in candidates:
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

        if user_text.lower().strip().startswith("/ai "):
            user_query = user_text[4:].strip()
            send_telegram_message(chat_id, "⏳ Đang xử lý...")
            results = call_langflow(user_query)
            for msg in results:
                send_telegram_message(chat_id, msg)

    return "ok", 200

@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is running!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
