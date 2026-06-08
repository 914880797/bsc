import os
import logging
import threading
from flask import Flask, request, jsonify
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# --- 配置日志 ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- 环境变量读取 ---
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
FLASK_PORT = int(os.environ.get("PORT", 5000)) # Render 强制要求读取 PORT 变量

if not BOT_TOKEN:
    raise ValueError("未找到 TELEGRAM_BOT_TOKEN 环境变量，请在 Render 设置中添加")

# --- 初始化 Flask (用于保活和接收 Webhook) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Service is alive! 🤖"

@app.route('/health')
def health_check():
    # UptimeRobot 可以访问这个地址
    return jsonify({"status": "ok"}), 200

# --- Telegram Bot 逻辑 ---
async def start(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! I am running on Render.")

async def handle_message(update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    logger.info(f"收到消息: {text}")
    await update.message.reply_text(f"Echo: {text}")

def run_bot():
    """在后台线程中运行 Telegram Bot"""
    try:
        application = ApplicationBuilder().token(BOT_TOKEN).build()
        
        # 添加处理器
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        logger.info("Telegram Bot 正在启动...")
        # 使用 run_polling() 启动轮询模式
        # 注意：在 Web Service 中，如果同时有 Flask，建议不要设置 drop_pending_updates=True
        # 以免丢失启动期间的消息，或者根据需求调整
        application.run_polling() 
    except Exception as e:
        logger.error(f"Bot 运行出错: {e}")

# --- 主入口 ---
if __name__ == '__main__':
    # 1. 启动 Telegram Bot 到后台线程
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # 2. 在主线程启动 Flask (Render 只检查主线程的端口)
    logger.info(f"Flask 正在监听端口 {FLASK_PORT}...")
    app.run(host='0.0.0.0', port=FLASK_PORT)

