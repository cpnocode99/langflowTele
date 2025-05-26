import os
import json
import re
import io
import requests
import discord
from discord.ext import commands

# === ENV ===
LANGFLOW_URL = os.getenv("LANGFLOW_URL")
LANGFLOW_CHART_URL = os.getenv("LANGFLOW_CHART_URL")
LANGFLOW_API_KEY = os.getenv("LANGFLOW_API_KEY")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# === STATE ===
last_suggestion_map = {}
call_langflow_count = 0

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
    call_langflow_count += 1
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

def send_chart_image_from_url(chart_url):
    response = requests.get(chart_url)
    if response.status_code == 200:
        return discord.File(io.BytesIO(response.content), filename="chart.png")
    return None

# === DISCORD COMMANDS ===
@bot.event
async def on_ready():
    print(f"✅ Bot đã sẵn sàng: {bot.user}")

@bot.command()
async def ai(ctx, *, prompt):
    if ctx.message.reference:
        replied = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        prompt = f"{prompt}\n(Phản hồi từ người dùng: {prompt})\n(Tin nhắn được reply: {replied.content.strip()})"
    await ctx.send("⏳ Đang xử lý...")
    result = call_langflow(prompt)
    for r in result:
        await ctx.send(r)
        if "Bạn có muốn biết thêm:" in r:
            try:
                suggestion = r.split("Bạn có muốn biết thêm:")[-1].strip().strip('"“”')
                if suggestion:
                    last_suggestion_map[ctx.channel.id] = suggestion
            except: pass

@bot.command()
async def rep(ctx, *, text):
    if ctx.message.reference:
        replied = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        reply_clean = re.sub(r"^/\w+\s*", "", replied.content.strip())
        prompt = f"{text} [phản hồi từ] {reply_clean}"
        await ctx.send("⏳ Đang xử lý phản hồi...")
        result = call_langflow(prompt)
        for r in result:
            await ctx.send(r)
    else:
        await ctx.send("⚠️ Bạn cần reply một tin nhắn để dùng /rep.")

@bot.command()
async def chart(ctx):
    if ctx.message.reference:
        replied = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        await ctx.send("📊 Đang phân tích và vẽ biểu đồ...")
        chart_result = call_langflow_chart_flow(replied.content.strip())
        if chart_result and chart_result[0].startswith("https://quickchart.io/chart"):
            chart_file = send_chart_image_from_url(chart_result[0])
            if chart_file:
                await ctx.send(file=chart_file, content="📈 Biểu đồ được tạo tự động")
            else:
                await ctx.send("❌ Không thể tải ảnh biểu đồ.")
        else:
            for msg in chart_result:
                await ctx.send(msg)
    else:
        await ctx.send("⚠️ Bạn cần reply một tin nhắn có dữ liệu.")

@bot.command()
async def ok(ctx):
    suggestion = last_suggestion_map.get(ctx.channel.id)
    if suggestion:
        await ctx.send("⏳ Đang xử lý gợi ý trước đó...")
        result = call_langflow(suggestion)
        for r in result:
            await ctx.send(r)
    else:
        await ctx.send("⚠️ Không có gợi ý nào để xử lý.")

@bot.command()
async def ques(ctx, count: int):
    if count <= 0:
        await ctx.send("❌ Số câu hỏi phải lớn hơn 0.")
        return
    await ctx.send(f"⏳ Đang tạo {count} câu hỏi...")
    prompt = f"Hãy đặt {count} câu hỏi hợp lệ đi"
    result = call_langflow(prompt)
    for r in result:
        await ctx.send(r)

@bot.command()
async def schedule(ctx):
    await ctx.send("⚙️ Đang kích hoạt gửi câu hỏi như lúc 8:00 sáng...")
    notify_msg = "🤖 AI đang tự động khám phá 5 câu hỏi từ dữ liệu của bạn..."
    input_text = "Hãy đặt 5 câu hỏi hợp lệ"
    await ctx.send(notify_msg)
    result = call_langflow(input_text)
    for msg in result:
        await ctx.send(msg)

@bot.command()
async def count(ctx):
    await ctx.send(f"Tổng số lần gửi input tới Langflow: {call_langflow_count}")

bot.run(DISCORD_BOT_TOKEN)
