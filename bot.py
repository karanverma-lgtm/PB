"""Telegram Stock Alert Bot (@Stockmightybot).

Provides live stock prices, price charts, and automated target price notifications.
"""

import os
import re
import logging
from typing import Dict, Any
from dotenv import load_dotenv

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

import database
import stock_service

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Setup Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("StockMightyBot")


# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------

def parse_symbol_and_target(args: list[str]) -> tuple[str, float]:
    """
    Parse symbol and target price from argument list.
    Supports multi-word symbols like 'NIFTY 50 25044' or 'BANK NIFTY 60000'.
    """
    if len(args) < 2:
        raise ValueError("Need at least symbol and target price")

    target_str = args[-1].replace("$", "").replace("₹", "").replace(",", "")
    target_price = float(target_str)
    if target_price <= 0:
        raise ValueError("Target price must be positive")

    raw_symbol = " ".join(args[:-1]).strip()
    return raw_symbol, target_price


# ---------------------------------------------------------
# Command Handlers
# ---------------------------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message and guide the user on how to use the bot."""
    user = update.effective_user
    name = user.first_name if user else "Trader"

    text = (
        f"👋 *Welcome to StockMightyBot, {name}!*\n\n"
        "I am your personal stock market assistant. I track real-time stock prices "
        "and automatically notify you the moment a stock hits your target price!\n\n"
        "⚡ *Quick Commands:*\n"
        "• `/price <SYMBOL>` - Get real-time stock quote\n"
        "• `/alert <SYMBOL> <TARGET>` - Set a price alert\n"
        "• `/alerts` - View all your active alerts\n"
        "• `/chart <SYMBOL>` - View price trend chart\n"
        "• `/help` - View complete guide and examples\n\n"
        "🔥 *Examples:*\n"
        "  `/alert NIFTY 50 25044`\n"
        "  `/alert BANK NIFTY 60000`\n"
        "  `/alert RELIANCE 1350`\n"
        "  `/alert AAPL 250`\n"
        "  `/price NIFTY 50`\n"
        "  `/chart TSLA`"
    )

    keyboard = [
        [
            InlineKeyboardButton("🇮🇳 Nifty 50 Price", callback_data="price_^NSEI"),
            InlineKeyboardButton("🇺🇸 Apple Price", callback_data="price_AAPL"),
        ],
        [
            InlineKeyboardButton("📋 My Active Alerts", callback_data="list_alerts"),
            InlineKeyboardButton("❓ Help & Guide", callback_data="help_menu"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send detailed help and usage guide."""
    text = (
        "📚 *StockMightyBot User Guide*\n\n"
        "🔔 *Setting Up Target Price Alerts:*\n"
        "`/alert <SYMBOL> <TARGET_PRICE>`\n\n"
        "The bot automatically calculates whether your target is *Above* or *Below* the current market price.\n"
        "• `/alert NIFTY 50 25044`\n"
        "• `/alert BANK NIFTY 60000`\n"
        "• `/alert AAPL 250` (Alert when Apple hits $250)\n"
        "• `/alert TSLA 200` (Alert if Tesla drops to $200)\n\n"
        "📈 *Checking Stock Quotes:*\n"
        "`/price NIFTY 50` or `/price RELIANCE` or `/price AAPL`\n\n"
        "📊 *Generating Technical Charts:*\n"
        "`/chart NIFTY 50` or `/chart NVDA 3mo`\n"
        "_(Periods: 1d, 5d, 1mo, 3mo, 1y)_\n\n"
        "📋 *Managing Your Alerts:*\n"
        "• `/alerts` - List active alerts with 1-click delete buttons\n"
        "• `/delalert <ID>` - Delete a specific alert ID\n"
        "• `/clearalerts` - Delete all your active alerts\n\n"
        "🌐 *Supported Symbols:*\n"
        "• Indian Indices: `NIFTY 50`, `BANK NIFTY`, `FINNIFTY`, `SENSEX`, `INDIA VIX`\n"
        "• Indian Equities: `RELIANCE`, `TCS`, `INFY`, `HDFCBANK`, `TATAMOTORS`\n"
        "• US Stocks: `AAPL`, `MSFT`, `TSLA`, `GOOGL`, `AMZN`, `NVDA`\n"
        "• Crypto: `BTC`, `ETH`, `SOL`\n"
        "• Commodities: `GOLD`, `SILVER`, `CRUDE`"
    )
    if update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetch and display real-time quote for a stock or index."""
    if not context.args:
        await update.message.reply_text(
            "⚠️ Please specify a symbol.\nExample: `/price NIFTY 50` or `/price AAPL`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    symbol = " ".join(context.args).strip()
    await send_stock_quote(update.message.chat_id, symbol, context)


async def send_stock_quote(chat_id: int, symbol: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetch and send formatted stock quote."""
    loading_msg = await context.bot.send_message(
        chat_id=chat_id,
        text=f"🔍 Fetching live quote for *{symbol}*...",
        parse_mode=ParseMode.MARKDOWN,
    )

    quote = stock_service.get_stock_quote(symbol)
    if not quote:
        await loading_msg.edit_text(
            f"❌ Could not find market data for *{symbol}*. Please check the symbol or index name.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    sign = "+" if quote["change"] >= 0 else ""
    trend_emoji = "🟢 📈" if quote["change"] >= 0 else "🔴 📉"

    text = (
        f"🏷️ *{quote['name']}* (`{quote['symbol']}`)\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💰 *Current Price:* `{quote['price']} {quote['currency']}`\n"
        f"{trend_emoji} *24h Change:* `{sign}{quote['change']} ({sign}{quote['change_pct']}%)`\n"
        f"🔺 *Day High:* `{quote['day_high']} {quote['currency']}`\n"
        f"🔻 *Day Low:* `{quote['day_low']} {quote['currency']}`\n"
        f"⏮️ *Prev Close:* `{quote['prev_close']} {quote['currency']}`\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"_Use `/alert {quote['symbol']} <price>` to set a target price alert!_"
    )

    keyboard = [
        [
            InlineKeyboardButton("📊 View Chart", callback_data=f"chart_{quote['symbol']}"),
            InlineKeyboardButton("🔄 Refresh", callback_data=f"price_{quote['symbol']}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await loading_msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)


async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set a target price alert for a stock or index."""
    user = update.effective_user
    chat_id = update.effective_chat.id

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ *Invalid format!* Please provide both symbol and target price.\n\n"
            "Usage: `/alert <SYMBOL> <TARGET_PRICE>`\n"
            "Examples:\n"
            "• `/alert NIFTY 50 25044`\n"
            "• `/alert BANK NIFTY 60000`\n"
            "• `/alert AAPL 250`\n"
            "• `/alert RELIANCE 1350`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
        raw_symbol, target_price = parse_symbol_and_target(context.args)
    except ValueError as e:
        await update.message.reply_text(f"❌ Error: {e}. Please enter a valid number for the target price.")
        return

    # Fetch live price to determine condition (ABOVE vs BELOW)
    quote = stock_service.get_stock_quote(raw_symbol)
    if not quote:
        await update.message.reply_text(
            f"❌ Unable to find symbol or index *{raw_symbol}*. Please check the ticker name.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    resolved_symbol = quote["symbol"]
    current_price = quote["price"]
    currency = quote["currency"]

    if abs(target_price - current_price) < 0.001:
        await update.message.reply_text(
            f"⚠️ Target price ({target_price}) is equal to current price ({current_price}). "
            "Please pick a higher or lower target."
        )
        return

    condition = "ABOVE" if target_price > current_price else "BELOW"
    condition_desc = "rises to or above" if condition == "ABOVE" else "drops to or below"
    emoji = "📈" if condition == "ABOVE" else "📉"

    alert_id = database.add_alert(
        user_id=user.id,
        chat_id=chat_id,
        symbol=resolved_symbol,
        target_price=target_price,
        condition=condition,
        initial_price=current_price,
        currency=currency,
    )

    confirm_text = (
        f"✅ *Target Alert Created!* (ID: `#{alert_id}`)\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏷️ *Asset:* `{resolved_symbol}` ({quote['name']})\n"
        f"💰 *Current Price:* `{current_price} {currency}`\n"
        f"🎯 *Target Price:* `{target_price} {currency}`\n"
        f"{emoji} *Condition:* Alert when price *{condition_desc}* `{target_price} {currency}`\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔔 I will notify you automatically the moment this target is reached!"
    )

    keyboard = [
        [
            InlineKeyboardButton("📋 View All Alerts", callback_data="list_alerts"),
            InlineKeyboardButton("❌ Cancel Alert", callback_data=f"del_{alert_id}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(confirm_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)


async def list_alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display all active alerts for the calling user."""
    user = update.effective_user
    alerts = database.get_user_alerts(user.id)

    if not alerts:
        text = (
            "📭 *You have no active price alerts.*\n\n"
            "Set one right now using:\n"
            "`/alert <SYMBOL> <TARGET_PRICE>`\n"
            "Example: `/alert NIFTY 50 25044`"
        )
        if update.message:
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        elif update.callback_query:
            await update.callback_query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        return

    text = f"📋 *Your Active Price Alerts ({len(alerts)}):*\n━━━━━━━━━━━━━━━━━━━\n"
    keyboard = []

    for a in alerts:
        cond_icon = "📈 ≥" if a["condition"] == "ABOVE" else "📉 ≤"
        text += (
            f"• *ID `#{a['id']}`:* `{a['symbol']}` target {cond_icon} `{a['target_price']} {a['currency']}` "
            f"_(set at {a['initial_price']})_\n"
        )
        keyboard.append([
            InlineKeyboardButton(f"❌ Delete #{a['id']} ({a['symbol']})", callback_data=f"del_{a['id']}"),
            InlineKeyboardButton(f"🔍 Price {a['symbol']}", callback_data=f"price_{a['symbol']}"),
        ])

    keyboard.append([InlineKeyboardButton("🗑️ Clear All Alerts", callback_data="clear_all")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)


async def delalert_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a specific alert by ID."""
    user = update.effective_user
    if not context.args:
        await update.message.reply_text(
            "⚠️ Usage: `/delalert <ID>`\nCheck your alert IDs with `/alerts`.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    try:
        alert_id = int(context.args[0].replace("#", ""))
    except ValueError:
        await update.message.reply_text("❌ Alert ID must be a number.")
        return

    success = database.delete_alert(alert_id, user_id=user.id)
    if success:
        await update.message.reply_text(f"✅ Alert `#{alert_id}` has been deleted.", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(f"❌ Alert `#{alert_id}` not found or already deleted.", parse_mode=ParseMode.MARKDOWN)


async def clearalerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear all active alerts for user."""
    user = update.effective_user
    count = database.clear_user_alerts(user.id)
    await update.message.reply_text(f"🗑️ Cleared {count} active alert(s).")


async def chart_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate and send a technical chart for a stock or index."""
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text(
            "⚠️ Usage: `/chart <SYMBOL> [PERIOD]`\nExample: `/chart NIFTY 50` or `/chart AAPL 3mo`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    valid_periods = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "ytd", "max"]
    if len(context.args) > 1 and context.args[-1].lower() in valid_periods:
        period = context.args[-1].lower()
        symbol = " ".join(context.args[:-1]).strip()
    else:
        period = "1mo"
        symbol = " ".join(context.args).strip()

    await send_stock_chart(chat_id, symbol, period, context)


async def send_stock_chart(chat_id: int, symbol: str, period: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Render and send stock chart image."""
    status_msg = await context.bot.send_message(
        chat_id=chat_id,
        text=f"📊 Generating *{period.upper()}* chart for *{symbol}*...",
        parse_mode=ParseMode.MARKDOWN,
    )

    img_buf = stock_service.generate_stock_chart(symbol, period=period)
    if not img_buf:
        await status_msg.edit_text(
            f"❌ Could not generate chart for *{symbol}*. Please check the symbol or period.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    await status_msg.delete()
    await context.bot.send_photo(
        chat_id=chat_id,
        photo=img_buf,
        caption=f"📈 Chart for *{symbol}* ({period.upper()})",
        parse_mode=ParseMode.MARKDOWN,
    )


# ---------------------------------------------------------
# Callback Query Handler (Inline Buttons)
# ---------------------------------------------------------

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle interactive button clicks."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("price_"):
        symbol = data[len("price_"):]
        await send_stock_quote(query.message.chat_id, symbol, context)
    elif data.startswith("chart_"):
        symbol = data[len("chart_"):]
        await send_stock_chart(query.message.chat_id, symbol, "1mo", context)
    elif data.startswith("del_"):
        alert_id = int(data.split("_")[1])
        success = database.delete_alert(alert_id, user_id=query.from_user.id)
        if success:
            await query.edit_message_text(f"✅ Alert `#{alert_id}` has been cancelled.", parse_mode=ParseMode.MARKDOWN)
        else:
            await query.edit_message_text(f"❌ Alert `#{alert_id}` was already removed.", parse_mode=ParseMode.MARKDOWN)
    elif data == "list_alerts":
        await list_alerts_command(update, context)
    elif data == "help_menu":
        await help_command(update, context)
    elif data == "clear_all":
        count = database.clear_user_alerts(query.from_user.id)
        await query.edit_message_text(f"🗑️ Cleared all {count} alerts.")


# ---------------------------------------------------------
# Background Job: Target Price Monitor
# ---------------------------------------------------------

async def check_price_alerts_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Background job that polls active alerts against live market prices.
    Dispatches notifications when targets are triggered.
    """
    alerts = database.get_all_active_alerts()
    if not alerts:
        return

    # Collect distinct symbols to minimize API requests
    distinct_symbols = list({a["symbol"] for a in alerts})
    quotes: Dict[str, Any] = {}

    for sym in distinct_symbols:
        q = stock_service.get_stock_quote(sym)
        if q:
            quotes[sym] = q

    for alert in alerts:
        sym = alert["symbol"]
        if sym not in quotes:
            continue

        q = quotes[sym]
        current_price = q["price"]
        target_price = alert["target_price"]
        condition = alert["condition"]
        chat_id = alert["chat_id"]
        currency = alert["currency"] or q["currency"]

        triggered = False
        if condition == "ABOVE" and current_price >= target_price:
            triggered = True
        elif condition == "BELOW" and current_price <= target_price:
            triggered = True

        if triggered:
            database.mark_alert_triggered(alert["id"], current_price)
            logger.info(f"Target triggered: Alert #{alert['id']} for {sym} at {current_price} (Target: {target_price})")

            emoji = "🚀 📈" if condition == "ABOVE" else "📉 ⚠️"
            condition_text = "hit or exceeded" if condition == "ABOVE" else "dropped to or below"

            alert_msg = (
                f"{emoji} *PRICE TARGET TRIGGERED!* {emoji}\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"🏷️ *Asset:* `{sym}` ({q['name']})\n"
                f"🎯 *Target Price:* `{target_price} {currency}`\n"
                f"💰 *Current Price:* `{current_price} {currency}`\n"
                f"📊 *Triggered Condition:* Price {condition_text} your target!\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"_Alert ID: #{alert['id']}_"
            )

            keyboard = [
                [
                    InlineKeyboardButton(f"📈 Quote {sym}", callback_data=f"price_{sym}"),
                    InlineKeyboardButton("📊 View Chart", callback_data=f"chart_{sym}"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=alert_msg,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup,
                )
            except Exception as e:
                logger.error(f"Failed to send notification to chat {chat_id}: {e}")


# ---------------------------------------------------------
# Main Application Launcher
# ---------------------------------------------------------

def main() -> None:
    """Initialize and run the Telegram bot."""
    if not BOT_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN is not set in .env file!")
        return

    # Initialize SQLite database
    database.init_db()
    logger.info("Database initialized successfully.")

    # Build Application
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Register Command Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("quote", price_command))
    app.add_handler(CommandHandler("alert", alert_command))
    app.add_handler(CommandHandler("alerts", list_alerts_command))
    app.add_handler(CommandHandler("myalerts", list_alerts_command))
    app.add_handler(CommandHandler("delalert", delalert_command))
    app.add_handler(CommandHandler("clearalerts", clearalerts_command))
    app.add_handler(CommandHandler("chart", chart_command))

    # Interactive button handler
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Setup Background Alert Checker Job (runs every 60 seconds)
    if app.job_queue:
        app.job_queue.run_repeating(check_price_alerts_job, interval=60, first=10)
        logger.info("Target price alert background job registered (60s interval).")

    print("\n" + "=" * 50)
    print("🤖 StockMightyBot (@Stockmightybot) is running!")
    print("=" * 50)
    print("Listening for messages and monitoring target price alerts...\n")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
