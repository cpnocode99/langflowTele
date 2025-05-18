from flask import Flask, request
import requests
import os
import json
import threading
import schedule
import time

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
LANGFLOW_URL = os.getenv("LANGFLOW_URL")
LANGFLOW_API_KEY = os.getenv("LANGFLOW_API_KEY")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

last_suggestion_map = {}  # Lưu gợi ý từng chat_id
call_langflow_count = 0   # Tổng số lần gửi input

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        print(f"[LOG] Gửi tin nhắn tới chat_id={chat_id}: {text}")
        response = requests.post(url, json=payload)
        print(f"[LOG] Telegram response status: {response.status_code}")
        if response.status_code != 200:
            print(f"[ERROR] Telegram API trả về lỗi: {response.text}")
    except Exception as e:
        print("[ERROR] Gửi tin nhắn Telegram:", str(e))

def send_multiple_telegram_messages(chat_id, messages):
    print(f"[LOG] Gửi {len(messages)} tin nhắn tới Telegram")
    for msg in messages:
        send_telegram_message(chat_id, msg)
        if "Bạn có muốn biết thêm:" in msg:
            try:
                suggestion = msg.split("Bạn có muốn biết thêm:")[-1].strip().strip('"“”')
                if suggestion:
                    last_suggestion_map[chat_id] = suggestion
                    print(f"[LOG] Lưu gợi ý cho chat_id={chat_id}: {suggestion}")
            except Exception as e:
                print("[ERROR] Khi phân tích gợi ý:", str(e))

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
                print(f"[DEBUG] Output {i}: {message}")
                results.append(message)
                seen.add(message)
    return results if results else ["✅ Langflow không trả về nội dung phù hợp."]

def call_langflow(user_input):
    global call_langflow_count
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

    print("[LOG] Gửi yêu cầu đến Langflow với input:", user_input)
    try:
        call_langflow_count += 1
        print(f"[LOG] Tổng số lần gửi input tới Langflow: {call_langflow_count}")
        response = requests.post(LANGFLOW_URL, headers=headers, data=json.dumps(body))
        print(f"[LOG] Langflow response status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            return extract_all_text_outputs(data.get("outputs", []))
        else:
            print("[ERROR] Langflow API lỗi:", response.text)
            return [f"❌ Lỗi API ({response.status_code})"]
    except Exception as e:
        print("[ERROR] Exception khi gọi Langflow:", str(e))
        return [f"❌ Lỗi khi gọi API: {str(e)}"]

@app.route(f"/webhook/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    print("--- [DEBUG] Nhận webhook từ Telegram ---")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    if "message" in data and "text" in data["message"]:
        user_text = data["message"]["text"]
        chat_id = data["message"]["chat"]["id"]
        print(f"[LOG] Nhận tin nhắn từ user: {user_text} (chat_id={chat_id})")

        clean_text = user_text.strip().lower()

        if clean_text == "/ok":
            suggestion = last_suggestion_map.get(chat_id)
            if suggestion:
                print(f"[LOG] Xử lý lệnh /ok với gợi ý: {suggestion}")
                send_telegram_message(chat_id, "⏳ Đang xử lý gợi ý trước đó...")
                messages = call_langflow(suggestion)
                send_multiple_telegram_messages(chat_id, messages)
            else:
                send_telegram_message(chat_id, "⚠️ Không có gợi ý nào để xử lý. Hãy gửi câu hỏi trước.")
            return "ok", 200

        elif clean_text.startswith("/ques"):
            parts = user_text.strip().split()
            if len(parts) == 2 and parts[1].isdigit():
                num = int(parts[1])
                input_text = f"Hãy đặt {num} câu hỏi hợp lệ đi"
                print(f"[LOG] Xử lý lệnh /ques với số lượng: {num}")
                send_telegram_message(chat_id, "⏳ Đang xử lý...")
                messages = call_langflow(input_text)
                send_multiple_telegram_messages(chat_id, messages)
            else:
                send_telegram_message(chat_id, "❌ Sai cú pháp! Dùng đúng định dạng: /ques {số}")
            return "ok", 200

        elif clean_text.startswith("/ai"):
            actual_text = user_text[3:].strip()
            print(f"[LOG] Xử lý lệnh /ai với nội dung: {actual_text}")
            send_telegram_message(chat_id, "⏳ Đang xử lý...")
            messages = call_langflow(actual_text)
            send_multiple_telegram_messages(chat_id, messages)
            return "ok", 200

    return "ok", 200

@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is running!", 200

@app.route("/count", methods=["GET"])
def get_count():
    return f"Tổng số lần gửi input tới Langflow: {call_langflow_count}", 200

def job_daily_morning():
    print("[LOG] 🔁 Đang chạy job định kỳ (test mỗi phút)")
    if TELEGRAM_CHAT_ID:
        input_text = "Hãy đặt 5 câu hỏi hợp lệ đi"
        print(f"[LOG] [AUTO] Gửi input tự động: {input_text}")
        messages = call_langflow(input_text)
        send_multiple_telegram_messages(TELEGRAM_CHAT_ID, messages)
    else:
        print("[WARNING] ❌ TELEGRAM_CHAT_ID không được thiết lập.")

def run_schedule():
    print("[LOG] ⚙️ Khởi động thread định kỳ gửi câu hỏi")
    schedule.every(1).minutes.do(job_daily_morning)  # test mỗi phút
    while True:
        schedule.run_pending()
        time.sleep(5)

threading.Thread(target=run_schedule, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"[LOG] Khởi động server Flask tại port {port}")
    app.run(host="0.0.0.0", port=port)
