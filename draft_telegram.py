import os
import json
import re
import io
import threading
import schedule
import time
import requests
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
LANGFLOW_URL = os.getenv("LANGFLOW_URL")
LANGFLOW_API_KEY = os.getenv("LANGFLOW_API_KEY")
LANGFLOW_CHART_URL = os.getenv("LANGFLOW_CHART_URL")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

last_suggestion_map = {}
call_langflow_count = 0

# === TELEGRAM ===
def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, json=payload)

def send_multiple_telegram_messages(chat_id, messages):
    for msg in messages:
        send_telegram_message(chat_id, msg)
        if "Bạn có muốn biết thêm:" in msg:
            try:
                suggestion = msg.split("Bạn có muốn biết thêm:")[-1].strip().strip('"“”')
                if suggestion:
                    last_suggestion_map[chat_id] = suggestion
            except: pass

def send_telegram_chart_url(chat_id, chart_url, caption=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    payload = {"chat_id": chat_id, "photo": chart_url}
    if caption:
        payload["caption"] = caption
    requests.post(url, data=payload)

def send_telegram_chart_as_file(chat_id, chart_url, caption=None):
    response = requests.get(chart_url)
    if response.status_code == 200:
        buf = io.BytesIO(response.content)
        buf.name = "chart.png"
        files = {"photo": buf}
        data = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", data=data, files=files)
    else:
        send_telegram_message(chat_id, "❌ Không thể tải ảnh biểu đồ.")

# === LANGFLOW ===
def extract_all_text_outputs(outputs):
    seen = set()
    results = []
    for output_block in outputs:
        for sub in output_block.get("outputs", []):
            message = sub.get("results", {}).get("message", {}).get("text", "").strip()
            if message and message not in seen:
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
            "TextInput-xpmxA": {"input_value": user_input},
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
    call_langflow_count += 1
    response = requests.post(LANGFLOW_URL, headers=headers, data=json.dumps(body))
    if response.status_code == 200:
        data = response.json()
        return extract_all_text_outputs(data.get("outputs", []))
    else:
        return [f"❌ Lỗi API ({response.status_code})"]

def call_langflow_chart_flow(prompt):
    headers = {
        "Content-Type": "application/json",
        "x-api-key": LANGFLOW_API_KEY
    }
    body = {
        "output_type": "chat",
        "input_type": "text",
        "tweaks": {
            "TextInput-ZWXXv": {"input_value": prompt},
            "CustomComponent-20mve": {"input_value": ""},
            "ChatOutput-BxE3i": {
                "clean_data": True,
                "data_template": "{text}",
                "sender": "Machine",
                "sender_name": "AI",
                "should_store_message": True
            }
        }
    }
    response = requests.post(LANGFLOW_CHART_URL, headers=headers, data=json.dumps(body))
    if response.status_code == 200:
        data = response.json()
        return extract_all_text_outputs(data.get("outputs", []))
    else:
        return [f"❌ Lỗi API biểu đồ ({response.status_code})"]

# === FLASK ===
@app.route(f"/webhook/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data and "text" in data["message"]:
        user_text = data["message"]["text"]
        chat_id = data["message"]["chat"]["id"]
        clean_text = user_text.strip().lower()

        if clean_text == "/ok":
            suggestion = last_suggestion_map.get(chat_id)
            if suggestion:
                send_telegram_message(chat_id, "⏳ Đang xử lý gợi ý trước đó...")
                messages = call_langflow(suggestion)
                send_multiple_telegram_messages(chat_id, messages)
            else:
                send_telegram_message(chat_id, "⚠️ Không có gợi ý nào để xử lý. Hãy gửi câu hỏi trước.")
            return "ok", 200

        elif clean_text.startswith("/ques"):
            parts = user_text.strip().split()
            if len(parts) == 2 and parts[1].isdigit():
                input_text = f"Hãy đặt {int(parts[1])} câu hỏi hợp lệ đi"
                send_telegram_message(chat_id, "⏳ Đang xử lý...")
                messages = call_langflow(input_text)
                send_multiple_telegram_messages(chat_id, messages)
            else:
                send_telegram_message(chat_id, "❌ Sai cú pháp! Dùng đúng định dạng: /ques {số}")
            return "ok", 200

        elif clean_text.startswith("/ai"):
            actual_text = user_text[3:].strip()
            if "reply_to_message" in data["message"]:
                replied_text = data["message"]["reply_to_message"].get("text", "").strip()
                combined_prompt = f"{actual_text}\n(Phản hồi từ người dùng: {actual_text})\n(Tin nhắn được reply: {replied_text})"
            else:
                combined_prompt = actual_text
            send_telegram_message(chat_id, "⏳ Đang xử lý...")
            messages = call_langflow(combined_prompt)
            send_multiple_telegram_messages(chat_id, messages)
            return "ok", 200

        elif clean_text.startswith("/rep"):
            actual_text = user_text[4:].strip()
            if "reply_to_message" in data["message"]:
                replied_text = data["message"]["reply_to_message"].get("text", "").strip()
                replied_text = re.sub(r"^/\w+\s*", "", replied_text)
                combined_prompt = f"{actual_text} [phản hồi từ] {replied_text}"
            else:
                send_telegram_message(chat_id, "⚠️ Bạn cần reply một tin nhắn để dùng /rep.")
                return "ok", 200
            send_telegram_message(chat_id, "⏳ Đang xử lý phản hồi...")
            messages = call_langflow(combined_prompt)
            send_multiple_telegram_messages(chat_id, messages)
            return "ok", 200

        elif clean_text == "/chart":
            if "reply_to_message" in data["message"]:
                replied_text = data["message"]["reply_to_message"].get("text", "").strip()
                send_telegram_message(chat_id, "📊 Đang phân tích và vẽ biểu đồ...")
                chart_results = call_langflow_chart_flow(replied_text)
                if chart_results and chart_results[0].startswith("https://quickchart.io/chart"):
                    send_telegram_chart_as_file(chat_id, chart_results[0], caption="📈 Biểu đồ được tạo tự động")
                else:
                    send_multiple_telegram_messages(chat_id, chart_results)
            else:
                send_telegram_message(chat_id, "⚠️ Bạn cần reply một tin nhắn có dữ liệu.")
            return "ok", 200

        elif clean_text == "/schedule":
            send_telegram_message(chat_id, "⚙️ Đang kích hoạt gửi câu hỏi như lúc 8:00 sáng...")
            notify_msg = "🤖 AI đang tự động khám phá 5 câu hỏi từ dữ liệu của bạn..."
            input_text = "Hãy đặt 5 câu hỏi hợp lệ"
            send_telegram_message(chat_id, notify_msg)
            messages = call_langflow(input_text)
            send_multiple_telegram_messages(chat_id, messages)
            return "ok", 200

    return "ok", 200

# === TIỆN ÍCH ===
@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is running!", 200

@app.route("/count", methods=["GET"])
def get_count():
    return f"Tổng số lần gửi input tới Langflow: {call_langflow_count}", 200

@app.route("/schedule", methods=["GET"])
def manual_schedule_trigger():
    job_daily_morning()
    return "✅ Đã kích hoạt gửi câu hỏi thủ công", 200

def job_daily_morning():
    if TELEGRAM_CHAT_ID:
        notify_msg = "🤖 AI đang tự động khám phá 5 câu hỏi từ dữ liệu của bạn..."
        input_text = "Hãy đặt 5 câu hỏi hợp lệ"
        send_telegram_message(TELEGRAM_CHAT_ID, notify_msg)
        messages = call_langflow(input_text)
        send_multiple_telegram_messages(TELEGRAM_CHAT_ID, messages)

def run_schedule():
    schedule.every().day.at("01:00").do(job_daily_morning)  # 8:00 sáng VN = 01:00 UTC
    while True:
        schedule.run_pending()
        time.sleep(5)

threading.Thread(target=run_schedule, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
