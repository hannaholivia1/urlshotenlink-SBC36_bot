# ============ HIDE TOKEN FROM LOGS (MUST BE FIRST) ============
import logging
logging.getLogger("httpx").setLevel(logging.WARNING)

# ============ IMPORTS ============
import os
import re
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)

# ============ LOGGING ============
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============ CONFIG ============
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
BOT_NAME       = os.getenv('BOT_NAME', 'SBC36 URL Shortener')
OWNER_ID       = os.getenv('OWNER_ID', '')

if not TELEGRAM_TOKEN:
    raise ValueError("❌ No TELEGRAM_BOT_TOKEN set!")

# In-memory history per user
HISTORY = {}      # user_id -> [list of {short, original}]
STATS = {"total": 0}  # global counter


# ============ HELPERS ============

URL_REGEX = re.compile(
    r'^(https?://)'                                  # must start with http:// or https://
    r'([\w\-]+\.)+[\w\-]+'                           # domain
    r'(:\d+)?'                                       # optional port
    r'(/[\w\-./?%&=+~:@!$&\'()*]*)?$',               # path/query
    re.IGNORECASE
)


def is_valid_url(text: str) -> bool:
    """Basic URL validation."""
    text = text.strip()
    if not text.startswith(("http://", "https://")):
        return False
    if len(text) > 2000:
        return False
    # Must contain a dot after the protocol
    after_proto = text.split("://", 1)[1]
    if "." not in after_proto.split("/")[0]:
        return False
    return True


def shorten_url(long_url: str) -> str:
    """Shorten using TinyURL (free, no API key)."""
    try:
        api = f"https://tinyurl.com/api-create.php?url={requests.utils.quote(long_url, safe='')}"
        r = requests.get(api, timeout=15)
        if r.status_code == 200 and r.text.startswith("http"):
            return r.text.strip()
        return None
    except Exception as e:
        logger.error(f"Shorten error: {e}")
        return None


# ============ KEYBOARDS ============

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 My History", callback_data="history")],
        [InlineKeyboardButton("ℹ️ About", callback_data="about"),
         InlineKeyboardButton("🆘 Help", callback_data="help")],
    ])


def back_button():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu")]
    ])


# ============ COMMANDS ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"🔗 <b>Hello {user.first_name}!</b>\n\n"
        f"I'm <b>{BOT_NAME}</b>.\n\n"
        "Send me any URL and I'll shorten it instantly!\n\n"
        "<b>Example:</b>\n"
        "<code>https://www.example.com/very/long/url</code>\n\n"
        "<b>Commands:</b>\n"
        "/start – Show this message\n"
        "/help – How to use\n"
        "/history – Your shortened URLs\n"
        "/about – About this bot\n\n"
        "🚀 Just paste a link to begin!"
    )
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=main_menu())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "<b>🆘 How to use this bot</b>\n\n"
        "<b>1.</b> Copy any URL (must start with http:// or https://)\n"
        "<b>2.</b> Send it to me\n"
        "<b>3.</b> Get a short, clean link back in seconds\n\n"
        "<b>Examples:</b>\n"
        "<code>https://www.youtube.com/watch?v=abc123</code>\n"
        "<code>https://example.com/blog/post-1</code>\n\n"
        "<b>Commands:</b>\n"
        "/start – Main menu\n"
        "/help – This message\n"
        "/history – See your past shortened links\n"
        "/about – About this bot\n\n"
        "<b>Tips:</b>\n"
        "• Only http:// and https:// links work\n"
        "• Your history is kept while the bot runs\n"
        "• 100% free, no signup required"
    )
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=back_button())


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"<b>ℹ️ About {BOT_NAME}</b>\n\n"
        "A simple, fast URL shortener for Telegram.\n\n"
        "<b>Features:</b>\n"
        "• ⚡ Instant shortening\n"
        "• 📋 Personal history\n"
        "• 🔒 No signup, no tracking\n"
        "• 💯 100% free\n\n"
        "<b>How it works:</b>\n"
        "Send a URL → get a short link via TinyURL.\n\n"
        "Made with ❤️ for the Telegram community."
    )
    await update.message.reply_text(text, parse_mode='HTML', reply_markup=back_button())


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_history(update, context)


# ============ SCREEN BUILDERS ============

async def send_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    items = HISTORY.get(user_id, [])

    if not items:
        text = (
            "📋 <b>Your Shortened URLs</b>\n\n"
            "You haven't shortened any URLs yet.\n\n"
            "Send a link to get started!"
        )
    else:
        text = f"📋 <b>Your Shortened URLs</b> ({len(items)} total)\n\n"
        for i, item in enumerate(items[-10:], 1):  # last 10
            short = item['short']
            original = item['original']
            if len(original) > 60:
                original = original[:57] + "..."
            text += f"<b>{i}.</b> {short}\n   → <i>{original}</i>\n\n"
        if len(items) > 10:
            text += f"\n<i>Showing last 10 of {len(items)}.</i>"

    kb = back_button()
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode='HTML', reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode='HTML', reply_markup=kb)


# ============ MAIN MESSAGE HANDLER ============

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if not is_valid_url(text):
        await update.message.reply_text(
            "❌ <b>That's not a valid URL.</b>\n\n"
            "Make sure it starts with <code>http://</code> or <code>https://</code>\n\n"
            "Example:\n"
            "<code>https://www.example.com/page</code>",
            parse_mode='HTML',
            reply_markup=back_button()
        )
        return

    thinking = await update.message.reply_text("⏳ <i>Shortening...</i>", parse_mode='HTML')

    short = shorten_url(text)

    if not short:
        await thinking.edit_text(
            "⚠️ <b>Could not shorten that URL right now.</b>\n\n"
            "Please try again in a few seconds.",
            parse_mode='HTML',
            reply_markup=back_button()
        )
        return

    # Save to history
    user_id = update.effective_user.id
    HISTORY.setdefault(user_id, []).append({'short': short, 'original': text})
    STATS['total'] += 1

    response = (
        "✅ <b>URL Shortened!</b>\n\n"
        f"🔗 <b>Original:</b>\n<code>{text}</code>\n\n"
        f"📎 <b>Short URL:</b>\n<code>{short}</code>\n\n"
        f"📊 Total shortened: {len(HISTORY[user_id])}"
    )
    await thinking.edit_text(
        response,
        parse_mode='HTML',
        reply_markup=main_menu()
    )


# ============ BUTTON ROUTER ============

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu":
        user = update.effective_user
        text = (
            f"🔗 <b>Hello {user.first_name}!</b>\n\n"
            "Send me any URL and I'll shorten it instantly!\n\n"
            "<b>Example:</b>\n"
            "<code>https://www.example.com/very/long/url</code>"
        )
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=main_menu())
    elif data == "history":
        await send_history(update, context)
    elif data == "about":
        await about_command(update, context)
    elif data == "help":
        await help_command(update, context)


# ============ FALLBACK FOR NON-TEXT ============

async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Send me a URL to shorten!\n\n"
        "Example: <code>https://example.com</code>",
        parse_mode='HTML',
        reply_markup=main_menu()
    )


# ============ OWNER STATS ============

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if OWNER_ID and str(update.effective_user.id) != str(OWNER_ID):
        await update.message.reply_text("⛔ Not authorized.")
        return
    await update.message.reply_text(
        f"📊 <b>Bot Statistics</b>\n\n"
        f"🔗 Total URLs shortened: <b>{STATS['total']}</b>\n"
        f"👥 Active users: <b>{len(HISTORY)}</b>\n"
        f"🤖 Status: Running",
        parse_mode='HTML'
    )


# ============ ERROR HANDLER ============

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ An error occurred. Please try again."
            )
    except Exception:
        pass


# ============ MAIN ============

def main():
    print(f"🚀 Starting {BOT_NAME}...")

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("stats", stats))

    # Buttons
    application.add_handler(CallbackQueryHandler(on_button))

    # Text messages (URLs)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Non-text fallback
    application.add_handler(MessageHandler(~filters.TEXT & ~filters.COMMAND, fallback))

    # Errors
    application.add_error_handler(error_handler)

    print(f"🤖 {BOT_NAME} is running!")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )


if __name__ == '__main__':
    main()
