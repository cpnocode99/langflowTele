from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

# Load environment variables
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
        print("\n--- [DEBUG] Gửi tới Langflow ---")
        print(json.dumps(body, indent=2, ensure_ascii=False))

        response = requests.post(LANGFLOW_URL, headers=headers, data=json.dumps(body))
        print(f"--- [DEBUG] HTTP Status: {response.status_code} ---")
        raw_text = response.text
        print("[DEBUG] Raw Text:\n", raw_text[:2000], "..." if len(raw_text) > 2000 else "")

        data = response.json()
        outputs = data.get("outputs", [])
        all_messages = set()

        for block in outputs:
            for out in block.get("outputs", []):
                candidates = []

                for key_path in [
                    ("results", "message", "text"),
                    ("outputs", "message", "message"),
                    ("message", "text"),
                    ("text",),
                ]:
                    ref = out
                    for key in key_path:
                        ref = ref.get(key, {})
                    if isinstance(ref, str):
                        candidates.append(ref)

                for m in out.get("messages", []):
                    msg = m.get("message")
                    if msg and isinstance(msg, str):
                        candidates.append(msg)

                for msg in candidates:
                    cleaned = msg.strip()
                    if cleaned:
                        all_messages.add(cleaned)

        print("\n--- [DEBUG] Trả về từ Langflow ---")
        for i, msg in enumerate(all_messages, 1):
            print(f"[{i}] {msg}")
        print("--- [END DEBUG] ---\n")

        return split_long_message("\n\n---\n\n".join(all_messages)) if all_messages else ["⚠️ Không có output."]
    except Exception as e:
        print("❌ Lỗi xử lý Langflow:", e)
        return [f"❌ Lỗi: {str(e)}"]

@app.route(f"/webhook/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    print("\n--- [DEBUG] Telegram Webhook ---")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    if "message" in data and "text" in data["message"]:
        chat_id = data["message"]["chat"]["id"]
        user_text = data["message"]["text"]

        if user_text.lower().strip().startswith("/ai "):
            user_query = user_text[4:].strip()
            send_telegram_message(chat_id, "⏳ Đang xử lý...")
            responses = call_langflow(user_query)
            for msg in responses:
                send_telegram_message(chat_id, msg)

    return "ok", 200

@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is running!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
