"""Amazon Price Drop Tracker Telegram Bot (@Stockmightybot).

Monitors Amazon product prices and delivers automated alerts whenever a product's
price drops to or below your desired target price.
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
    MessageHandler,
    ContextTypes,
    filters,
)

import database
import amazon_service

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Setup Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("AmazonTrackerBot")


# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------

def clean_price_input(price_str: str) -> float:
    """Parse user numeric price input."""
    cleaned = price_str.replace("₹", "").replace("$", "").replace(",", "").strip()
    val = float(cleaned)
    if val <= 0:
        raise ValueError("Price must be greater than zero")
    return val


# ---------------------------------------------------------
# Command Handlers
# ---------------------------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message and guide the user on how to track Amazon products."""
    user = update.effective_user
    name = user.first_name if user else "Shopper"

    text = (
        f"👋 *Welcome to Amazon Price Drop Alert Bot, {name}!*\n\n"
        "🛍️ Never overpay again! Send me any **Amazon product link**, set your desired target price, "
        "and I will notify you the moment the price drops!\n\n"
        "⚡ *How to use:*\n"
        "1. Simply **paste or share any Amazon link** into this chat.\n"
        "2. Choose a quick discount button (5%, 10%, 15% drop) or set your own target!\n\n"
        "📋 *Commands:*\n"
        "• `/track <URL> <DESIRED_PRICE>` — Track product with target price\n"
        "• `/products` — View and manage all your tracked items\n"
        "• `/deltrack <ID>` — Stop tracking a product\n"
        "• `/cleartrack` — Clear all tracked products\n"
        "• `/help` — Detailed guide & examples\n\n"
        "_Example:_\n"
        "`/track https://www.amazon.in/dp/B09G9BL5CP 75000`"
    )

    keyboard = [
        [
            InlineKeyboardButton("📋 My Tracked Products", callback_data="list_products"),
            InlineKeyboardButton("❓ Help & Examples", callback_data="help_menu"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send detailed help and usage guide."""
    text = (
        "📚 *Amazon Price Tracker Guide*\n\n"
        "🛒 *Tracking an Item:*\n"
        "**Method 1 (Fastest):**\n"
        "Just copy any product link from the Amazon App or browser and paste it here! "
        "The bot will fetch the item and let you pick your target price.\n\n"
        "**Method 2 (Command):**\n"
        "`/track <AMAZON_LINK> <DESIRED_PRICE>`\n"
        "• `/track https://www.amazon.in/dp/B09G9BL5CP 75000`\n"
        "• `/track https://amzn.to/example 1999`\n\n"
        "📋 *Managing Your Products:*\n"
        "• `/products` or `/alerts` — See all your tracked items with current vs target prices\n"
        "• `/deltrack <ID>` — Delete a tracked item\n"
        "• `/cleartrack` — Remove all your tracked items\n\n"
        "🌐 *Supported Amazon Domains:*\n"
        "• Amazon India (`amazon.in`, `amzn.in`)\n"
        "• Amazon US & Global (`amazon.com`, `amzn.to`)"
    )
    if update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def track_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Track an Amazon product at a specified target price."""
    user = update.effective_user
    chat_id = update.effective_chat.id

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ *Invalid Format!*\n\n"
            "Usage: `/track <AMAZON_URL> <DESIRED_PRICE>`\n"
            "Example: `/track https://www.amazon.in/dp/B09G9BL5CP 75000`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    url = context.args[0].strip()
    try:
        target_price = clean_price_input(context.args[1])
    except ValueError as e:
        await update.message.reply_text(f"❌ Invalid target price: {e}")
        return

    loading_msg = await update.message.reply_text("🔍 Fetching product details from Amazon... Please wait.")

    product = amazon_service.fetch_amazon_product(url)
    if not product:
        await loading_msg.edit_text(
            "❌ Could not extract product details. Please ensure the link is a valid Amazon product page."
        )
        return

    curr_price = product["price"]
    currency = product["currency"]

    if target_price >= curr_price:
        await loading_msg.edit_text(
            f"⚠️ Target price ({currency}{target_price:,.2f}) is already higher than or equal to the "
            f"current price ({currency}{curr_price:,.2f}).\n"
            "Please specify a lower target price to get alerted on a price drop!"
        )
        return

    savings = curr_price - target_price
    savings_pct = (savings / curr_price) * 100

    # Save to database
    product_id = database.add_tracked_product(
        user_id=user.id,
        chat_id=chat_id,
        asin=product["asin"],
        title=product["title"],
        url=product["url"],
        image_url=product.get("image_url"),
        target_price=target_price,
        current_price=curr_price,
        currency=currency,
    )

    caption = (
        f"✅ *Product Successfully Tracked!* (ID: `#{product_id}`)\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📦 *{product['title'][:70]}...*\n\n"
        f"💰 *Current Price:* `{currency}{curr_price:,.2f}`\n"
        f"🎯 *Target Price:* `{currency}{target_price:,.2f}`\n"
        f"📉 *Target Savings:* `{currency}{savings:,.2f} ({savings_pct:.1f}% OFF)`\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔔 I am actively monitoring this item and will alert you the moment the price drops!"
    )

    keyboard = [
        [
            InlineKeyboardButton("🛒 View on Amazon", url=product["url"]),
            InlineKeyboardButton("❌ Stop Tracking", callback_data=f"del_{product_id}"),
        ],
        [
            InlineKeyboardButton("📋 View All Products", callback_data="list_products"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await loading_msg.delete()

    if product.get("image_url"):
        try:
            await update.message.reply_photo(
                photo=product["image_url"],
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup,
            )
            return
        except Exception:
            pass

    await update.message.reply_text(caption, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)


async def list_products_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all tracked Amazon products for the user."""
    user = update.effective_user
    products = database.get_user_products(user.id)

    if not products:
        text = (
            "📭 *You are not tracking any Amazon products yet.*\n\n"
            "Paste any Amazon link in this chat or use:\n"
            "`/track <AMAZON_URL> <TARGET_PRICE>`"
        )
        if update.message:
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        elif update.callback_query:
            await update.callback_query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        return

    text = f"📋 *Your Tracked Amazon Products ({len(products)}):*\n━━━━━━━━━━━━━━━━━━━\n\n"
    keyboard = []

    for p in products:
        savings = p["current_price"] - p["target_price"]
        curr_str = f"{p['currency']}{p['current_price']:,.2f}"
        target_str = f"{p['currency']}{p['target_price']:,.2f}"

        text += (
            f"• *ID `#{p['id']}`:* [{p['title'][:40]}...]({p['url']})\n"
            f"  💰 Current: `{curr_str}` ➔ Target: `{target_str}` "
            f"_(Needs {p['currency']}{savings:,.2f} drop)_\n\n"
        )
        keyboard.append([
            InlineKeyboardButton(f"🛒 #{p['id']} Buy", url=p["url"]),
            InlineKeyboardButton(f"❌ Stop #{p['id']}", callback_data=f"del_{p['id']}"),
        ])

    keyboard.append([InlineKeyboardButton("🗑️ Clear All Tracked Items", callback_data="clear_all")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup, disable_web_page_preview=True)
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup, disable_web_page_preview=True)


async def deltrack_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a tracked product by ID."""
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/deltrack <ID>`\nCheck your product IDs with `/products`.", parse_mode=ParseMode.MARKDOWN)
        return

    try:
        product_id = int(context.args[0].replace("#", ""))
    except ValueError:
        await update.message.reply_text("❌ Product ID must be a number.")
        return

    success = database.delete_tracked_product(product_id, user_id=user.id)
    if success:
        await update.message.reply_text(f"✅ Product `#{product_id}` tracking stopped.", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(f"❌ Product `#{product_id}` not found or already removed.", parse_mode=ParseMode.MARKDOWN)


async def cleartrack_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear all active tracked products for user."""
    user = update.effective_user
    count = database.clear_user_products(user.id)
    await update.message.reply_text(f"🗑️ Cleared all {count} tracked product(s).")


# ---------------------------------------------------------
# Natural Message Handler: Direct Amazon URL Pasted
# ---------------------------------------------------------

async def handle_amazon_url_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detect when a user simply pastes an Amazon link without any command."""
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    asin = amazon_service.extract_asin(text)
    if not asin and "amazon." not in text and "amzn." not in text:
        return  # Not an Amazon link

    loading = await update.message.reply_text("🔎 Amazon link detected! Fetching current price and details...")
    product = amazon_service.fetch_amazon_product(text)
    if not product:
        await loading.edit_text("❌ Could not extract details from this Amazon link. Please check if the link is active.")
        return

    curr_price = product["price"]
    currency = product["currency"]

    # Calculate suggested target prices
    p5 = round(curr_price * 0.95, 2)
    p10 = round(curr_price * 0.90, 2)
    p15 = round(curr_price * 0.85, 2)

    caption = (
        f"📦 *{product['title'][:80]}...*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💰 *Current Price:* `{currency}{curr_price:,.2f}`\n\n"
        f"🎯 *Select your desired price drop below:* or reply with `/track {product['asin']} <price>`"
    )

    # Store product data in context user_data for quick buttons
    context.user_data[f"prod_{product['asin']}"] = product

    keyboard = [
        [
            InlineKeyboardButton(f"🔔 5% Drop ({currency}{p5:,.0f})", callback_data=f"set_{product['asin']}_{p5}"),
            InlineKeyboardButton(f"🔔 10% Drop ({currency}{p10:,.0f})", callback_data=f"set_{product['asin']}_{p10}"),
        ],
        [
            InlineKeyboardButton(f"🔥 15% Drop ({currency}{p15:,.0f})", callback_data=f"set_{product['asin']}_{p15}"),
            InlineKeyboardButton("🛒 View on Amazon", url=product["url"]),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await loading.delete()

    if product.get("image_url"):
        try:
            await update.message.reply_photo(
                photo=product["image_url"],
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup,
            )
            return
        except Exception:
            pass

    await update.message.reply_text(caption, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)


# ---------------------------------------------------------
# Callback Query Handler (Interactive Buttons)
# ---------------------------------------------------------

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle interactive button clicks."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("set_"):
        parts = data.split("_")
        asin = parts[1]
        target_price = float(parts[2])

        product = context.user_data.get(f"prod_{asin}")
        if not product:
            product = amazon_service.fetch_amazon_product(asin)

        if not product:
            await query.edit_message_caption("❌ Error: Product details expired. Please re-paste the Amazon link.")
            return

        product_id = database.add_tracked_product(
            user_id=query.from_user.id,
            chat_id=query.message.chat_id,
            asin=product["asin"],
            title=product["title"],
            url=product["url"],
            image_url=product.get("image_url"),
            target_price=target_price,
            current_price=product["price"],
            currency=product["currency"],
        )

        confirm = (
            f"✅ *Tracking Alert Activated!* (ID: `#{product_id}`)\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📦 *{product['title'][:70]}...*\n\n"
            f"💰 *Current Price:* `{product['currency']}{product['price']:,.2f}`\n"
            f"🎯 *Target Price:* `{product['currency']}{target_price:,.2f}`\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🔔 I will notify you the moment the price drops to or below your target!"
        )
        if query.message.photo:
            await query.edit_message_caption(confirm, parse_mode=ParseMode.MARKDOWN)
        else:
            await query.edit_message_text(confirm, parse_mode=ParseMode.MARKDOWN)

    elif data.startswith("del_"):
        product_id = int(data.split("_")[1])
        success = database.delete_tracked_product(product_id, user_id=query.from_user.id)
        if success:
            await query.message.reply_text(f"✅ Product `#{product_id}` tracking stopped.", parse_mode=ParseMode.MARKDOWN)
        else:
            await query.message.reply_text(f"❌ Product `#{product_id}` was already removed.", parse_mode=ParseMode.MARKDOWN)

    elif data == "list_products":
        await list_products_command(update, context)

    elif data == "help_menu":
        await help_command(update, context)

    elif data == "clear_all":
        count = database.clear_user_products(query.from_user.id)
        await query.message.reply_text(f"🗑️ Cleared all {count} tracked product(s).")


# ---------------------------------------------------------
# Background Job: Amazon Price Drop Monitor
# ---------------------------------------------------------

async def check_amazon_prices_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Background worker that polls active tracked products for price drops.
    Dispatches notifications when current_price <= target_price.
    """
    products = database.get_all_active_products()
    if not products:
        return

    logger.info(f"Checking prices for {len(products)} active tracked product(s)...")

    # Group by ASIN to avoid duplicate scraping requests
    asin_map: Dict[str, list] = {}
    for p in products:
        asin_map.setdefault(p["asin"], []).append(p)

    for asin, items in asin_map.items():
        sample = items[0]
        prod_data = amazon_service.fetch_amazon_product(sample["url"])
        if not prod_data or not prod_data.get("price"):
            continue

        new_price = prod_data["price"]

        for item in items:
            product_id = item["id"]
            target_price = item["target_price"]
            chat_id = item["chat_id"]
            currency = item["currency"]
            title = prod_data["title"]
            url = prod_data["url"]
            image_url = prod_data.get("image_url")

            # Update latest price in DB
            database.update_product_price(product_id, new_price)

            # Check if Price Drop Target Reached
            if new_price <= target_price:
                database.mark_product_triggered(product_id, new_price)
                logger.info(f"Price Drop Triggered: #{product_id} ({asin}) at {new_price} (Target: {target_price})")

                savings = item["initial_price"] - new_price
                savings_pct = (savings / item["initial_price"] * 100) if item["initial_price"] > 0 else 0

                alert_text = (
                    f"🎉🚨 *PRICE DROP ALERT!* 🚨🎉\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"📦 *{title[:75]}...*\n\n"
                    f"🔥 *New Price:* `{currency}{new_price:,.2f}`\n"
                    f"🎯 *Your Target:* `{currency}{target_price:,.2f}`\n"
                    f"💰 *You Save:* `{currency}{savings:,.2f} ({savings_pct:.1f}% OFF)`\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"⚡ Grab it before the deal ends!"
                )

                keyboard = [
                    [InlineKeyboardButton("🛒 Buy Now on Amazon", url=url)]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                try:
                    if image_url:
                        await context.bot.send_photo(
                            chat_id=chat_id,
                            photo=image_url,
                            caption=alert_text,
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=reply_markup,
                        )
                    else:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=alert_text,
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=reply_markup,
                        )
                except Exception as e:
                    logger.error(f"Failed to dispatch alert to chat {chat_id}: {e}")


# ---------------------------------------------------------
# Main Application Launcher
# ---------------------------------------------------------

def main() -> None:
    """Initialize and run the Amazon Price Drop Tracker Bot."""
    if not BOT_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN is not set in .env file!")
        return

    # Initialize SQLite database
    database.init_db()
    logger.info("Amazon Tracker Database initialized successfully.")

    # Build Application
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("track", track_command))
    app.add_handler(CommandHandler("alert", track_command))
    app.add_handler(CommandHandler("products", list_products_command))
    app.add_handler(CommandHandler("alerts", list_products_command))
    app.add_handler(CommandHandler("tracked", list_products_command))
    app.add_handler(CommandHandler("deltrack", deltrack_command))
    app.add_handler(CommandHandler("cleartrack", cleartrack_command))

    # Interactive button handler
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Direct message handler (Auto-detects when an Amazon link is pasted)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amazon_url_message))

    # Background Job: Polls Amazon prices (every 5 minutes = 300 seconds)
    if app.job_queue:
        app.job_queue.run_repeating(check_amazon_prices_job, interval=300, first=15)
        logger.info("Amazon price drop background job registered (300s interval).")

    print("\n" + "=" * 55)
    print("🛍️ Amazon Price Drop Tracker Bot (@Stockmightybot) Live!")
    print("=" * 55)
    print("Monitoring Amazon products and listening for link inputs...\n")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
