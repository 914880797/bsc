import os
import logging
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from web3 import Web3

# --- 1. 基础配置与日志 ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 从环境变量获取敏感信息 (Render 后台填写的)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
RPC_PRIMARY = os.environ.get("RPC_URL_PRIMARY")
RPC_BACKUP = os.environ.get("RPC_URL_BACKUP")

if not BOT_TOKEN:
    raise ValueError("未找到 BOT_TOKEN 环境变量，请在 Render 设置中添加。")

# --- 2. Web3 区块链连接逻辑 (含容灾) ---
def get_web3_instance():
    """尝试连接主节点，失败则连接备用节点"""
    # 尝试主节点
    try:
        w3 = Web3(Web3.HTTPProvider(RPC_PRIMARY))
        if w3.is_connected():
            logger.info(f"✅ 成功连接到主节点: {RPC_PRIMARY[:20]}...")
            return w3
    except Exception as e:
        logger.warning(f"⚠️ 主节点连接失败: {e}")

    # 尝试备用节点
    try:
        w3 = Web3(Web3.HTTPProvider(RPC_BACKUP))
        if w3.is_connected():
            logger.info(f"✅ 成功连接到备用节点: {RPC_BACKUP[:20]}...")
            return w3
    except Exception as e:
        logger.error(f"❌ 备用节点也连接失败: {e}")

    return None

w3 = get_web3_instance()

# --- 3. Telegram 机器人功能 ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 欢迎！我是 BSC 链上助手。\n输入 /block 查看最新区块高度。")

async def check_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not w3 or not w3.is_connected():
        await update.message.reply_text("❌ 无法连接到区块链网络，请稍后再试。")
        return

    try:
        block_num = w3.eth.block_number
        gas_price = w3.eth.gas_price
        msg = (f"📊 **BSC 网络状态**\n"
               f"当前区块: `{block_num}`\n"
               f"Gas Price: `{Web3.from_wei(gas_price, 'gwei'):.2f} Gwei`")
        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"查询出错: {str(e)}")

# --- 4. Flask 保活服务 (防止 Render 休眠) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running! 🚀"

def run_flask():
    # Render 会自动分配 PORT 环境变量
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- 5. 启动入口 ---
if __name__ == '__main__':
    # 在后台线程启动 Flask
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

    # 启动 Telegram Bot
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("block", check_block))

    logger.info("🤖 机器人正在启动...")
    application.run_polling()