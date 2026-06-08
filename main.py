import os
import sqlite3
import logging
from functools import wraps
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

# --- 1. 基础配置与日志 ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TG_TOKEN")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.isdigit()]

if not BOT_TOKEN:
    raise ValueError("❌ 未找到 TG_TOKEN 环境变量，请在 Render 设置中添加。")

# --- 2. 数据库初始化 (SQLite) ---
def init_db():
    """初始化数据库，创建监控代币表"""
    conn = sqlite3.connect('web3_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS monitored_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            token_address TEXT NOT NULL,
            logo_url TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("✅ 数据库初始化完成")

# --- 3. 权限校验装饰器 ---
def admin_required(func):
    """装饰器：限制只有管理员才能执行某些命令"""
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("🚫 权限不足：仅管理员可执行此操作。")
            return
        return await func(update, context)
    return wrapped

# --- 4. Telegram 机器人指令处理 ---
@admin_required
async def add_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """添加监控合约"""
    if not context.args:
        await update.message.reply_text("⚠️ 用法: /add <合约地址>\n例如: /add 0x1234...5678")
        return

    token_address = context.args[0]
    chat_id = update.effective_chat.id

    conn = sqlite3.connect('web3_bot.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO monitored_tokens (chat_id, token_address) VALUES (?, ?)", (chat_id, token_address))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ 合约 `{token_address}` 已成功加入监控！\n"
        f"💡 如需添加专属头像，请直接发送 Logo 图片（功能将在后续版本完善）。",
        parse_mode='Markdown'
    )

@admin_required
async def remove_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """删除监控合约"""
    if not context.args:
        await update.message.reply_text("⚠️ 用法: /remove <合约地址>")
        return

    token_address = context.args[0]
    chat_id = update.effective_chat.id

    conn = sqlite3.connect('web3_bot.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM monitored_tokens WHERE chat_id = ? AND token_address = ?", (chat_id, token_address))
    conn.commit()
    affected_rows = cursor.rowcount
    conn.close()

    if affected_rows > 0:
        await update.message.reply_text(f"🗑️ 合约 `{token_address}` 已从监控列表中移除。", parse_mode='Markdown')
    else:
        await update.message.reply_text("⚠️ 未找到该合约，请检查地址是否正确。")

@admin_required
async def list_tokens(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看当前群组监控的合约列表"""
    chat_id = update.effective_chat.id
    conn = sqlite3.connect('web3_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT token_address FROM monitored_tokens WHERE chat_id = ?", (chat_id,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("📭 当前群组暂无监控的合约。请使用 /add 添加。")
        return

    msg = "📊 **当前监控的合约列表:**\n\n"
    for i, row in enumerate(rows, 1):
        msg += f"{i}. `{row[0]}`\n"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

# --- 5. Flask 保活服务 ---
app = Flask(__name__)

@app.route('/ping')
def ping():
    return "Bot is alive!", 200

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

# --- 6. 启动入口 ---
if __name__ == '__main__':
    # 1. 初始化数据库
    init_db()

    # 2. 启动 Flask 保活线程
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("🌐 Flask 保活服务已启动")

    # 3. 启动 Telegram Bot
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # 注册指令处理器
    application.add_handler(CommandHandler("add", add_token))
    application.add_handler(CommandHandler("remove", remove_token))
    application.add_handler(CommandHandler("list", list_tokens))

    logger.info("🤖 Telegram 机器人正在启动...")
    application.run_polling(drop_pending_updates=True)
