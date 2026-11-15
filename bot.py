"""Multi-Platform Price Drop Tracker Telegram Bot (@Stockmightybot).

Monitors Amazon, Flipkart, JioMart, Reliance Digital, Croma, and Samsung product prices
and delivers automated alerts whenever a product's price drops to or below your desired target price.

Engineered for 24/7 high concurrency, non-blocking asyncio execution, HTML entity safety,
and persistent database caching across restarts.
"""

import os
import re
import html
import random
import asyncio
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.error import RetryAfter, TelegramError, Forbidden
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import database
import product_service

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Setup Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("PriceTrackerBot")

# Suppress repetitive HTTP polling requests from filling cloud logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


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


def safe_caption(text: str, max_len: int = 1000) -> str:
    """Ensure caption fits within Telegram's length limits."""
    if len(text) > max_len:
        return text[:max_len - 3] + "..."
    return text


# ---------------------------------------------------------
# Command Handlers
# ---------------------------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message and guide the user on how to track products."""
    user = update.effective_user
    name = html.escape(user.first_name) if user and user.first_name else "Shopper"
    user_pin = database.get_user_pincode(user.id) if user else "110001"

    text = (
        f"👋 <b>Welcome to Price Drop Alert Bot, {name}!</b>\n\n"
        "🛍️ Never miss a deal! Send me any product link from <b>11 major platforms</b>, set your desired target price, "
        "and I will notify you the moment the price drops or when out-of-stock items restock!\n\n"
        "⚡ <b>Supported Platforms:</b>\n"
        "• 📦 <b>Amazon India & Global</b> (<code>amazon.in</code>, <code>amzn.to</code>)\n"
        "• 🛍️ <b>Flipkart</b> (<code>flipkart.com</code>, <code>dl.flipkart.com</code>)\n"
        "• 🔴 <b>Myntra</b> (<code>myntra.com</code>)\n"
        "• 🌸 <b>Nykaa & Nykaa Fashion</b> (<code>nykaa.com</code>, <code>nykaafashion.com</code>)\n"
        "• ✨ <b>Tira Beauty</b> (<code>tirabeauty.com</code>)\n"
        "• 🛍️ <b>Meesho</b> (<code>meesho.com</code>)\n"
        "• 👗 <b>Savana</b> (<code>savana.com</code>, <code>sharein.savana.com</code>)\n"
        "• 🟢 <b>JioMart</b> (<code>jiomart.com</code>)\n"
        "• 🔴 <b>Reliance Digital</b> (<code>reliancedigital.in</code>)\n"
        "• ⚪ <b>Croma</b> (<code>croma.com</code>)\n"
        "• 🌌 <b>Samsung India</b> (<code>samsung.com/in</code>)\n\n"
        f"📍 <b>Active Delivery PIN:</b> <code>{user_pin}</code> (Change with <code>/pincode &lt;PIN&gt;</code>)\n\n"
        "⚡ <b>How to use:</b>\n"
        "1. Simply <b>paste or share any product link</b> into this chat.\n"
        "2. Choose a quick discount button (5%, 10%, 15% drop) or set your own target!\n\n"
        "📋 <b>Commands:</b>\n"
        "• <code>/track &lt;URL&gt; &lt;DESIRED_PRICE&gt;</code> — Track product with target price\n"
        "• <code>/pincode &lt;6-DIGIT-PIN&gt;</code> — Set delivery PIN for local price & stock\n"
        "• <code>/products</code> — View and manage all your tracked items\n"
        "• <code>/deltrack &lt;ID&gt;</code> — Stop tracking a product\n"
        "• <code>/cleartrack</code> — Clear all tracked products\n"
        "• <code>/help</code> — Detailed guide & examples"
    )

    keyboard = [
        [
            InlineKeyboardButton("📋 My Tracked Products", callback_data="list_products"),
            InlineKeyboardButton("📍 Set PIN Code", callback_data="pincode_menu"),
        ],
        [
            InlineKeyboardButton("❓ Help & Examples", callback_data="help_menu"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send detailed help and usage guide."""
    text = (
        "📚 <b>Price Drop Tracker Guide</b>\n\n"
        "🛒 <b>Tracking an Item:</b>\n"
        "<b>Method 1 (Fastest):</b>\n"
        "Just copy any product link from Amazon, Flipkart, Myntra, Nykaa, Tira, Meesho, JioMart, Reliance Digital, Croma, or Samsung and paste it into this chat! "
        "The bot will automatically fetch the item and let you pick your target price.\n\n"
        "<b>Method 2 (Command):</b>\n"
        "<code>/track &lt;PRODUCT_LINK&gt; &lt;DESIRED_PRICE&gt;</code>\n\n"
        "📍 <b>Delivery PIN Code (Localized Prices & Stock):</b>\n"
        "• <code>/pincode &lt;6_DIGIT_PIN&gt;</code> — Set your delivery PIN (e.g. <code>/pincode 110001</code>)\n"
        "• <code>/pincode</code> — View your active PIN & pick metro quick presets\n\n"
        "⚡ <b>Examples across platforms:</b>\n"
        "• <code>/track https://www.amazon.in/dp/B09G9BL5CP 75000</code>\n"
        "• <code>/track https://www.flipkart.com/... 55000</code>\n"
        "• <code>/track https://www.myntra.com/.../buy 1100</code>\n"
        "• <code>/track https://www.nykaa.com/.../p/821979 90</code>\n"
        "• <code>/track https://www.tirabeauty.com/product/... 90</code>\n"
        "• <code>/track https://www.meesho.com/.../p/... 450</code>\n"
        "• <code>/track https://www.croma.com/.../p/300652 56000</code>\n"
        "• <code>/track https://www.reliancedigital.in/.../p/493839309 56000</code>\n"
        "• <code>/track https://www.jiomart.com/... 56000</code>\n"
        "• <code>/track https://www.samsung.com/in/... 75000</code>\n\n"
        "📋 <b>Managing Your Products:</b>\n"
        "• <code>/products</code> or <code>/alerts</code> — See all your tracked items\n"
        "• <code>/deltrack &lt;ID&gt;</code> — Delete a tracked item\n"
        "• <code>/cleartrack</code> — Remove all your tracked items"
    )
    if update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode=ParseMode.HTML)


async def pincode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View or update user delivery pincode for accurate localized prices and stock."""
    user = update.effective_user
    if not user:
        return

    # If argument provided: validate and update user's pincode
    if context.args:
        candidate_pin = context.args[0].strip()
        if not re.match(r"^\d{6}$", candidate_pin):
            msg = (
                "❌ <b>Invalid PIN code format!</b>\n\n"
                "Please provide a valid 6-digit Indian PIN code (e.g. <code>/pincode 110001</code>)."
            )
            if update.message:
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            return

        database.set_user_pincode(user.id, candidate_pin)
        confirm_text = (
            f"📍 <b>Delivery PIN code updated to <code>{candidate_pin}</code>!</b>\n\n"
            f"All future price checks, stock verification, and alerts will check prices for PIN code <b>{candidate_pin}</b>."
        )
        if update.message:
            await update.message.reply_text(confirm_text, parse_mode=ParseMode.HTML)
        elif update.callback_query:
            await update.callback_query.message.reply_text(confirm_text, parse_mode=ParseMode.HTML)
        return

    # If no argument: display current pincode and quick selection menu
    current_pin = database.get_user_pincode(user.id)
    text = (
        f"📍 <b>Your Current Delivery PIN Code:</b> <code>{current_pin}</code>\n\n"
        "Stores like Reliance Digital, Croma, JioMart, and Flipkart display live stock and pricing based on your delivery PIN code.\n\n"
        "⚡ <b>How to update:</b>\n"
        "• Type: <code>/pincode &lt;YOUR_6_DIGIT_PIN&gt;</code>\n"
        "  <i>Example: <code>/pincode 110001</code></i>\n\n"
        "Or tap one of the quick metro presets below:"
    )

    keyboard = [
        [
            InlineKeyboardButton("🏛️ Delhi (110001)", callback_data="pin_110001"),
            InlineKeyboardButton("🌊 Mumbai (400001)", callback_data="pin_400001"),
        ],
        [
            InlineKeyboardButton("💻 Bangalore (560001)", callback_data="pin_560001"),
            InlineKeyboardButton("🌉 Kolkata (700001)", callback_data="pin_700001"),
        ],
        [
            InlineKeyboardButton("🏖️ Chennai (600001)", callback_data="pin_600001"),
            InlineKeyboardButton("🏰 Hyderabad (500001)", callback_data="pin_500001"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def track_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Track a product from any of the 6 platforms at a specified target price."""
    user = update.effective_user
    chat_id = update.effective_chat.id

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ <b>Invalid Format!</b>\n\n"
            "Usage: <code>/track &lt;PRODUCT_URL&gt; &lt;DESIRED_PRICE&gt;</code>\n"
            "Example: <code>/track https://www.flipkart.com/... 55000</code>\n"
            "Example: <code>/track https://www.amazon.in/... 75000</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    # Flexible parsing: identify URL and numeric price regardless of argument order
    url = None
    target_price = None

    for arg in context.args:
        arg_clean = arg.strip()
        if arg_clean.startswith("http://") or arg_clean.startswith("https://") or "amazon." in arg_clean or "amzn." in arg_clean or "flipkart." in arg_clean:
            url = arg_clean
        else:
            try:
                val = clean_price_input(arg_clean)
                target_price = val
            except Exception:
                pass

    if not url or target_price is None:
        await update.message.reply_text(
            "⚠️ <b>Could not recognize URL or target price!</b>\n\n"
            "Please provide both the product link and target price number.\n"
            "Example: <code>/track https://www.amazon.in/... 75000</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    user_pin = database.get_user_pincode(user.id)
    loading_msg = await update.message.reply_text(f"🔍 Fetching details for PIN <code>{user_pin}</code>... Please wait a moment.", parse_mode=ParseMode.HTML)

    # Run scraper in thread pool to prevent blocking asyncio event loop
    product = await asyncio.to_thread(product_service.fetch_product, url, user_pin)
    if not product:
        await loading_msg.edit_text(
            "❌ <b>Could not extract details from this link.</b>\n\n"
            "⚠️ <i>Common reasons:</i>\n"
            "• The item is currently <b>out of stock</b> or unavailable.\n"
            "• The link is a search results page rather than an individual product page.\n"
            "• Make sure you copy the link directly from the product page.",
            parse_mode=ParseMode.HTML,
        )
        return

    curr_price = product.get("price") or 0.0
    currency = product.get("currency", "₹")
    platform = product["platform"]
    in_stock = product.get("in_stock", True)

    if in_stock and curr_price > 0 and target_price >= curr_price:
        await loading_msg.edit_text(
            f"⚠️ Target price ({currency}{target_price:,.2f}) is already higher than or equal to the "
            f"current price ({currency}{curr_price:,.2f}).\n"
            "Please specify a lower target price to get alerted on a price drop!"
        )
        return

    savings = (curr_price - target_price) if (in_stock and curr_price > target_price) else 0.0
    savings_pct = (savings / curr_price * 100) if (curr_price > 0 and savings > 0) else 0.0

    # Save to database
    product_id = database.add_tracked_product(
        user_id=user.id,
        chat_id=chat_id,
        platform=platform,
        item_id=product["item_id"],
        title=product["title"],
        url=product["url"],
        image_url=product.get("image_url"),
        target_price=target_price,
        current_price=curr_price,
        currency=currency,
        pincode=user_pin,
        is_in_stock=in_stock,
    )

    title_escaped = html.escape(product["title"][:75])
    badge_escaped = html.escape(product.get("platform_badge", platform))

    if not in_stock:
        caption = (
            f"🔔 <b>Out-of-Stock Item Tracked!</b> (ID: <code>#{product_id}</code>)\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🏷️ <b>Platform:</b> <code>{badge_escaped}</code>\n"
            f"📦 <b>{title_escaped}...</b>\n\n"
            f"❌ <b>Stock Status:</b> <code>Currently Out of Stock</code>\n"
            f"🎯 <b>Target Price:</b> <code>{currency}{target_price:,.2f}</code>\n"
            f"📍 <b>Delivery PIN:</b> <code>{user_pin}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🔔 I am actively monitoring restocks and will alert you the moment this item is Back in Stock!"
        )
    else:
        caption = (
            f"✅ <b>Product Successfully Tracked!</b> (ID: <code>#{product_id}</code>)\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🏷️ <b>Platform:</b> <code>{badge_escaped}</code>\n"
            f"📦 <b>{title_escaped}...</b>\n\n"
            f"💰 <b>Current Price:</b> <code>{currency}{curr_price:,.2f}</code>\n"
            f"🎯 <b>Target Price:</b> <code>{currency}{target_price:,.2f}</code>\n"
            f"📉 <b>Target Savings:</b> <code>{currency}{savings:,.2f} ({savings_pct:.1f}% OFF)</code>\n"
            f"📍 <b>Delivery PIN:</b> <code>{user_pin}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🔔 I am actively monitoring this item and will alert you the moment the price drops!"
        )

    keyboard = [
        [
            InlineKeyboardButton(f"🛒 View on {platform}", url=product["url"]),
            InlineKeyboardButton("❌ Stop Tracking", callback_data=f"del_{product_id}"),
        ],
        [
            InlineKeyboardButton("📋 View All Products", callback_data="list_products"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await loading_msg.delete()
    except Exception:
        pass

    if product.get("image_url"):
        try:
            await update.message.reply_photo(
                photo=product["image_url"],
                caption=safe_caption(caption),
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
            return
        except Exception as e:
            logger.debug(f"Could not send photo, falling back to text: {e}")

    await update.message.reply_text(caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def list_products_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all tracked products for the user."""
    user = update.effective_user
    products = database.get_user_products(user.id)

    if not products:
        text = (
            "📭 <b>You are not tracking any products yet.</b>\n\n"
            "Paste any product link in this chat or use:\n"
            "<code>/track &lt;PRODUCT_URL&gt; &lt;TARGET_PRICE&gt;</code>"
        )
        if update.message:
            await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        elif update.callback_query:
            await update.callback_query.message.reply_text(text, parse_mode=ParseMode.HTML)
        return

    text = f"📋 <b>Your Tracked Products ({len(products)}):</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
    keyboard = []

    icons = {
        "Amazon": "📦",
        "Flipkart": "🛍️",
        "JioMart": "🟢",
        "RelianceDigital": "🔴",
        "Croma": "⚪",
        "Samsung": "🌌",
        "Myntra": "🔴",
        "Nykaa": "🌸",
        "Tira": "✨",
        "Meesho": "🛍️",
        "Savana": "👗",
    }

    chunks = []
    current_text = f"📋 <b>Your Tracked Products ({len(products)}):</b>\n━━━━━━━━━━━━━━━━━━━\n\n"
    current_keyboard = []

    for p in products:
        platform_icon = icons.get(p.get("platform"), "🏷️")
        p_title = html.escape(p["title"][:38])
        safe_url = html.escape(p["url"])
        p_pin = p.get("pincode") or "110001"
        is_stock = p.get("is_in_stock", 1)

        if not is_stock:
            stock_badge = "❌ <b>Out of Stock</b> (Monitoring Restock 🔔)"
            entry = (
                f"• <b>ID <code>#{p['id']}</code>:</b> {platform_icon} <a href=\"{safe_url}\">{p_title}...</a>\n"
                f"  {stock_badge} (📍 <code>{p_pin}</code>)\n\n"
            )
        else:
            savings = p["current_price"] - p["target_price"]
            curr_str = f"{p['currency']}{p['current_price']:,.2f}"
            target_str = f"{p['currency']}{p['target_price']:,.2f}"
            entry = (
                f"• <b>ID <code>#{p['id']}</code>:</b> {platform_icon} <a href=\"{safe_url}\">{p_title}...</a>\n"
                f"  💰 Current: <code>{curr_str}</code> ➔ Target: <code>{target_str}</code> (📍 <code>{p_pin}</code>)\n"
                f"  <i>Needs {p['currency']}{savings:,.2f} drop</i>\n\n"
            )
        buttons = [
            InlineKeyboardButton(f"🛒 #{p['id']} View", url=p["url"]),
            InlineKeyboardButton(f"❌ Stop #{p['id']}", callback_data=f"del_{p['id']}"),
        ]

        if len(current_text) + len(entry) > 3500 or len(current_keyboard) >= 20:
            chunks.append((current_text, current_keyboard))
            current_text = "📋 <b>Continued Tracked Products:</b>\n━━━━━━━━━━━━━━━━━━━\n\n" + entry
            current_keyboard = [buttons]
        else:
            current_text += entry
            current_keyboard.append(buttons)

    if current_text:
        current_keyboard.append([
            InlineKeyboardButton("📍 Delivery PIN Code", callback_data="pincode_menu"),
            InlineKeyboardButton("🗑️ Clear All Items", callback_data="clear_all"),
        ])
        chunks.append((current_text, current_keyboard))

    for idx, (chunk_text, chunk_kb) in enumerate(chunks):
        reply_markup = InlineKeyboardMarkup(chunk_kb)
        if update.message:
            await update.message.reply_text(chunk_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup, disable_web_page_preview=True)
        elif update.callback_query:
            await update.callback_query.message.reply_text(chunk_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup, disable_web_page_preview=True)


async def deltrack_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a tracked product by ID."""
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("⚠️ Usage: <code>/deltrack &lt;ID&gt;</code>\nCheck your product IDs with <code>/products</code>.", parse_mode=ParseMode.HTML)
        return

    try:
        product_id = int(context.args[0].replace("#", ""))
    except ValueError:
        await update.message.reply_text("❌ Product ID must be a number.")
        return

    success = database.delete_tracked_product(product_id, user_id=user.id)
    if success:
        await update.message.reply_text(f"✅ Product <code>#{product_id}</code> tracking stopped.", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(f"❌ Product <code>#{product_id}</code> not found or already removed.", parse_mode=ParseMode.HTML)


async def cleartrack_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear all active tracked products for user."""
    user = update.effective_user
    count = database.clear_user_products(user.id)
    await update.message.reply_text(f"🗑️ Cleared all {count} tracked product(s).")


# ---------------------------------------------------------
# Natural Message Handler: Direct Link Pasted
# ---------------------------------------------------------

async def handle_url_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detect when a user pastes a product link from any of the 6 supported platforms."""
    if not update.message or not update.message.text:
        return

    raw_text = update.message.text.strip()
    platform = product_service.detect_platform(raw_text)
    if platform == "Unknown":
        return

    user = update.effective_user
    user_pin = database.get_user_pincode(user.id) if user else "110001"
    loading = await update.message.reply_text(f"🔎 {platform} link detected! Checking live price for PIN <code>{user_pin}</code>...", parse_mode=ParseMode.HTML)

    # Run scraper in thread pool to prevent blocking asyncio event loop
    product = await asyncio.to_thread(product_service.fetch_product, raw_text, user_pin)
    if not product:
        await loading.edit_text(
            f"❌ <b>Could not extract details from this {platform} link.</b>\n\n"
            "⚠️ <i>Please check:</i>\n"
            "1. Is the product currently <b>in stock</b>?\n"
            "2. Did you share an individual product link (not a search or category list)?\n"
            "3. Try sending the link with <code>/track &lt;LINK&gt; &lt;TARGET_PRICE&gt;</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    # Persist pending product in SQLite database so button clicks survive bot restarts!
    database.save_pending_product(product)

    in_stock = product.get("in_stock", True)
    curr_price = product.get("price") or 0.0
    currency = product.get("currency", "₹")

    title_escaped = html.escape(product["title"][:75])
    badge_escaped = html.escape(product.get("platform_badge", platform))

    # Store in memory for instant access
    cache_key = f"prod_{product['item_id']}"
    context.user_data[cache_key] = product

    if not in_stock:
        caption = (
            f"{badge_escaped} <b>{title_escaped}...</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"❌ <b>Stock Status:</b> <code>Currently Out of Stock</code>\n"
            f"📍 <b>Delivery PIN:</b> <code>{user_pin}</code> (Change with <code>/pincode</code>)\n\n"
            f"🔔 This item is currently unavailable. Click below to get an instant <b>Back-in-Stock Restock Alert</b> the moment it's available, or track a target price with <code>/track {product['url']} &lt;price&gt;</code>."
        )
        keyboard = [
            [
                InlineKeyboardButton("🔔 Notify when Back in Stock", callback_data=f"restock_{product['item_id']}"),
            ],
            [
                InlineKeyboardButton(f"🛒 View on {product['platform']}", url=product["url"]),
            ]
        ]
    else:
        p5 = round(curr_price * 0.95, 2)
        p10 = round(curr_price * 0.90, 2)
        p15 = round(curr_price * 0.85, 2)

        caption = (
            f"{badge_escaped} <b>{title_escaped}...</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💰 <b>Current Price:</b> <code>{currency}{curr_price:,.2f}</code>\n"
            f"📍 <b>Delivery PIN:</b> <code>{user_pin}</code> (Change with <code>/pincode</code>)\n\n"
            f"🎯 <b>Select your desired price drop below:</b> or reply with <code>/track {product['url']} &lt;price&gt;</code>"
        )
        keyboard = [
            [
                InlineKeyboardButton(f"🔔 5% Drop ({currency}{p5:,.0f})", callback_data=f"set_{product['item_id']}_{p5}"),
                InlineKeyboardButton(f"🔔 10% Drop ({currency}{p10:,.0f})", callback_data=f"set_{product['item_id']}_{p10}"),
            ],
            [
                InlineKeyboardButton(f"🔥 15% Drop ({currency}{p15:,.0f})", callback_data=f"set_{product['item_id']}_{p15}"),
                InlineKeyboardButton(f"🛒 View on {product['platform']}", url=product["url"]),
            ]
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await loading.delete()
    except Exception:
        pass

    if product.get("image_url"):
        try:
            await update.message.reply_photo(
                photo=product["image_url"],
                caption=safe_caption(caption),
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
            return
        except Exception as e:
            logger.debug(f"Could not send photo, falling back to text: {e}")

    await update.message.reply_text(caption, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


# ---------------------------------------------------------
# Callback Query Handler (Interactive Buttons)
# ---------------------------------------------------------

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle interactive button clicks."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("restock_"):
        item_id = data.split("_")[1]
        product = context.user_data.get(f"prod_{item_id}") or database.get_pending_product(item_id)
        if not product:
            await query.message.reply_text("❌ Session expired. Please re-paste the product link.")
            return

        user_pin = database.get_user_pincode(query.from_user.id)
        # Add to tracked products with ceiling price and is_in_stock=False
        product_id = database.add_tracked_product(
            user_id=query.from_user.id,
            chat_id=query.message.chat_id,
            platform=product["platform"],
            item_id=product["item_id"],
            title=product["title"],
            url=product["url"],
            image_url=product.get("image_url"),
            target_price=999999999.0,
            current_price=product.get("price") or 0.0,
            currency=product.get("currency", "₹"),
            pincode=user_pin,
            is_in_stock=False,
        )

        title_escaped = html.escape(product["title"][:70])
        badge_escaped = html.escape(product.get("platform_badge", product["platform"]))

        confirm = (
            f"🔔 <b>Back-in-Stock Alert Activated!</b> (ID: <code>#{product_id}</code>)\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🏷️ <b>Platform:</b> <code>{badge_escaped}</code>\n"
            f"📦 <b>{title_escaped}...</b>\n\n"
            f"❌ <b>Current Status:</b> <code>Out of Stock</code>\n"
            f"📍 <b>Delivery PIN:</b> <code>{user_pin}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ I will immediately notify you the moment this product is Back in Stock!"
        )
        keyboard = [
            [
                InlineKeyboardButton(f"🛒 View on {product['platform']}", url=product["url"]),
                InlineKeyboardButton("❌ Stop Tracking", callback_data=f"del_{product_id}"),
            ],
            [
                InlineKeyboardButton("📋 View All Products", callback_data="list_products"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if query.message.photo:
            try:
                await query.edit_message_caption(safe_caption(confirm), parse_mode=ParseMode.HTML, reply_markup=reply_markup)
            except Exception:
                await query.message.reply_text(confirm, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        else:
            try:
                await query.edit_message_text(confirm, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
            except Exception:
                await query.message.reply_text(confirm, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

    elif data.startswith("set_"):
        parts = data.split("_")
        item_id = parts[1]
        target_price = float(parts[2])

        # Look in memory first, then fallback to database pending_products (survives restarts!)
        product = context.user_data.get(f"prod_{item_id}") or database.get_pending_product(item_id)
        if not product:
            await query.message.reply_text("❌ Session expired. Please re-paste the product link.")
            return

        user_pin = database.get_user_pincode(query.from_user.id)
        product_id = database.add_tracked_product(
            user_id=query.from_user.id,
            chat_id=query.message.chat_id,
            platform=product["platform"],
            item_id=product["item_id"],
            title=product["title"],
            url=product["url"],
            image_url=product.get("image_url"),
            target_price=target_price,
            current_price=product["price"],
            currency=product["currency"],
            pincode=user_pin,
            is_in_stock=product.get("in_stock", True),
        )

        title_escaped = html.escape(product["title"][:70])
        badge_escaped = html.escape(product.get("platform_badge", product["platform"]))

        confirm = (
            f"✅ <b>Tracking Alert Activated!</b> (ID: <code>#{product_id}</code>)\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🏷️ <b>Platform:</b> <code>{badge_escaped}</code>\n"
            f"📦 <b>{title_escaped}...</b>\n\n"
            f"💰 <b>Current Price:</b> <code>{product['currency']}{product['price']:,.2f}</code>\n"
            f"🎯 <b>Target Price:</b> <code>{product['currency']}{target_price:,.2f}</code>\n"
            f"📍 <b>Delivery PIN:</b> <code>{user_pin}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🔔 I will notify you the moment the price drops to or below your target!"
        )
        if query.message.photo:
            try:
                await query.edit_message_caption(safe_caption(confirm), parse_mode=ParseMode.HTML)
            except Exception:
                await query.message.reply_text(confirm, parse_mode=ParseMode.HTML)
        else:
            try:
                await query.edit_message_text(confirm, parse_mode=ParseMode.HTML)
            except Exception:
                await query.message.reply_text(confirm, parse_mode=ParseMode.HTML)

    elif data.startswith("del_"):
        product_id = int(data.split("_")[1])
        success = database.delete_tracked_product(product_id, user_id=query.from_user.id)
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        if success:
            await query.message.reply_text(f"🛑 Tracking stopped for product <code>#{product_id}</code>.", parse_mode=ParseMode.HTML)
        else:
            await query.message.reply_text(f"❌ Product <code>#{product_id}</code> was already removed.", parse_mode=ParseMode.HTML)

    elif data.startswith("pin_"):
        new_pin = data.split("_")[1]
        database.set_user_pincode(query.from_user.id, new_pin)
        await query.answer(f"📍 PIN code set to {new_pin}!", show_alert=True)
        confirm_pin = (
            f"✅ <b>Delivery PIN code updated to <code>{new_pin}</code>!</b>\n\n"
            f"All future price checks, stock verification, and alerts will check prices for PIN code <b>{new_pin}</b>."
        )
        try:
            await query.edit_message_text(confirm_pin, parse_mode=ParseMode.HTML)
        except Exception:
            await query.message.reply_text(confirm_pin, parse_mode=ParseMode.HTML)

    elif data == "pincode_menu":
        await pincode_command(update, context)

    elif data == "list_products":
        await list_products_command(update, context)

    elif data == "help_menu":
        await help_command(update, context)

    elif data == "clear_all":
        count = database.clear_user_products(query.from_user.id)
        await query.message.reply_text(f"🗑️ Cleared all {count} tracked product(s).")


# ---------------------------------------------------------
# Background Job: Multi-Platform Price Drop Monitor
# ---------------------------------------------------------

async def send_alert_safely(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    user_id: int,
    text: str,
    image_url: Optional[str],
    reply_markup: InlineKeyboardMarkup,
) -> bool:
    """Send alert message/photo to chat handling Telegram flood control and blocked bot events."""
    try:
        if image_url:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=image_url,
                caption=safe_caption(text),
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
        return True
    except RetryAfter as flood_err:
        logger.warning(f"Telegram FloodControl: Waiting {flood_err.retry_after}s...")
        await asyncio.sleep(flood_err.retry_after + 1.0)
        try:
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
            return True
        except Forbidden:
            logger.warning(f"Bot was blocked by chat {chat_id}. Deactivating alerts for user {user_id}.")
            database.clear_user_products(user_id)
            return False
        except Exception:
            return False
    except Forbidden:
        logger.warning(f"Bot was blocked by chat {chat_id}. Deactivating alerts for user {user_id}.")
        database.clear_user_products(user_id)
        return False
    except Exception as e:
        logger.debug(f"Photo dispatch failed ({e}), falling back to text: {e}")
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
            return True
        except Forbidden:
            logger.warning(f"Bot was blocked by chat {chat_id}. Deactivating alerts for user {user_id}.")
            database.clear_user_products(user_id)
            return False
        except Exception as text_e:
            logger.error(f"Failed to dispatch text update to chat {chat_id}: {text_e}")
            return False


async def check_prices_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Background worker that polls active tracked products for price drops and stock changes.
    Dispatches notifications when:
    1. An item transitions from In-Stock to Out-of-Stock
    2. An item transitions from Out-of-Stock to Back-in-Stock (Restock)
    3. current_price <= target_price (Price Drop)
    """
    products = database.get_all_active_products()
    if not products:
        return

    logger.info(f"Checking prices & stock for {len(products)} active tracked product(s)...")

    # Group by (platform, item_id, pincode) to eliminate redundant network calls while respecting user pincodes
    prod_map: Dict[tuple, list] = {}
    for p in products:
        pin = p.get("pincode") or database.get_user_pincode(p["user_id"])
        key = (p.get("platform", "Unknown"), p.get("item_id") or p["url"], pin)
        prod_map.setdefault(key, []).append((p, pin))

    for (platform_key, item_key, pin_key), items_with_pin in prod_map.items():
        fetch_url = items_with_pin[0][0]["url"]
        item_pin = pin_key
        try:
            # Run scraper in thread pool to prevent blocking asyncio event loop
            prod_data = await asyncio.to_thread(product_service.fetch_product, fetch_url, item_pin)
            if not prod_data:
                continue

            curr_stock = prod_data.get("in_stock", True)
            new_price = prod_data.get("price") or 0.0

            for item, pin in items_with_pin:
                product_id = item["id"]
                target_price = item["target_price"]
                chat_id = item["chat_id"]
                user_id = item["user_id"]
                currency = item["currency"]
                title = prod_data["title"]
                prod_url = prod_data["url"]
                image_url = prod_data.get("image_url")
                platform = prod_data["platform"]
                badge = prod_data.get("platform_badge", platform)
                prev_stock = item.get("is_in_stock", 1)

                title_escaped = html.escape(title[:75])
                badge_escaped = html.escape(badge)

                # ====================================================
                # Case 1: In-Stock -> Out-of-Stock (OOS) Transition
                # ====================================================
                if prev_stock == 1 and curr_stock is False:
                    database.update_product_stock_status(product_id, is_in_stock=False)
                    logger.info(f"Stock Alert: #{product_id} on {platform} went OUT OF STOCK")

                    oos_text = (
                        f"⚠️🚨 <b>{badge_escaped} OUT OF STOCK ALERT!</b> 🚨⚠️\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"📦 <b>{title_escaped}...</b>\n\n"
                        f"❌ This product has just gone <b>Out of Stock</b>!\n"
                        f"📍 <b>Delivery PIN:</b> <code>{pin}</code>\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"🔔 <i>We are actively monitoring restocks and will immediately notify you the moment it is Back in Stock!</i>"
                    )
                    keyboard = [
                        [InlineKeyboardButton(f"🛒 View on {platform}", url=prod_url)],
                        [InlineKeyboardButton("🛑 Stop Tracking", callback_data=f"del_{product_id}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    sent = await send_alert_safely(context, chat_id, user_id, oos_text, image_url, reply_markup)
                    if not sent:
                        break
                    await asyncio.sleep(0.5)
                    continue

                # ====================================================
                # Case 2: Out-of-Stock -> Back-in-Stock (Restock) Transition!
                # ====================================================
                elif prev_stock == 0 and curr_stock is True:
                    database.update_product_stock_status(product_id, is_in_stock=True, current_price=new_price)
                    logger.info(f"Restock Alert: #{product_id} on {platform} is BACK IN STOCK (Price: {new_price})")

                    restock_text = (
                        f"🟢🎉 <b>{badge_escaped} BACK IN STOCK ALERT!</b> 🎉🟢\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"📦 <b>{title_escaped}...</b>\n\n"
                        f"✅ <b>Hooray! This item is now available to order!</b>\n"
                        f"💰 <b>Live Price:</b> <code>{currency}{new_price:,.2f}</code>\n"
                        f"🎯 <b>Your Target Price:</b> <code>{currency}{target_price:,.2f}</code>\n"
                        f"📍 <b>Delivery PIN:</b> <code>{pin}</code>\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"⚡ Hurry! Grab it before it sells out again."
                    )
                    keyboard = [
                        [InlineKeyboardButton(f"🛒 Buy Now on {platform}", url=prod_url)],
                        [InlineKeyboardButton("🛑 Stop Tracking", callback_data=f"del_{product_id}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    sent = await send_alert_safely(context, chat_id, user_id, restock_text, image_url, reply_markup)
                    if not sent:
                        break

                    # If target reached as well, mark triggered
                    if new_price > 0 and target_price < 999999000 and new_price <= target_price:
                        database.mark_product_triggered(product_id, new_price)

                    await asyncio.sleep(0.5)
                    continue

                # ====================================================
                # Case 3: Still Out-of-Stock (prev_stock == 0 and curr_stock is False)
                # ====================================================
                elif curr_stock is False:
                    continue

                # ====================================================
                # Case 4: Item In Stock - Normal Price Check
                # ====================================================
                if new_price <= 0:
                    continue

                database.update_product_price(product_id, new_price)

                # Interactive buttons: Direct Link + One-Click Stop Tracking
                keyboard = [
                    [InlineKeyboardButton(f"🛒 {'Buy Now on' if new_price <= target_price else 'View on'} {platform}", url=prod_url)],
                    [InlineKeyboardButton("🛑 Stop Tracking", callback_data=f"del_{product_id}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # Accessory / Refurbished Dropdown Sanity Guard
                initial = item.get("initial_price", new_price)
                if initial > 1000 and new_price < initial * 0.15:
                    accessory_words = ["case", "cover", "cable", "adapter", "protector", "strap", "guard", "skin"]
                    if any(w in title.lower() for w in accessory_words) and not any(w in item.get("title", "").lower() for w in accessory_words):
                        logger.warning(f"Accessory mismatch detected for item #{product_id} ({title}). Skipping drop alert.")
                        continue

                if new_price <= target_price:
                    database.mark_product_triggered(product_id, new_price)
                    logger.info(f"Price Drop Triggered: #{product_id} on {platform} at {new_price} (Target: {target_price})")

                    savings = item["initial_price"] - new_price
                    savings_pct = (savings / item["initial_price"] * 100) if item["initial_price"] > 0 else 0

                    update_text = (
                        f"🎉🚨 <b>{badge_escaped} PRICE DROP TARGET REACHED!</b> 🚨🎉\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"📦 <b>{title_escaped}...</b>\n\n"
                        f"🔥 <b>Current Price:</b> <code>{currency}{new_price:,.2f}</code>\n"
                        f"🎯 <b>Your Target:</b> <code>{currency}{target_price:,.2f}</code>\n"
                        f"💰 <b>You Save:</b> <code>{currency}{savings:,.2f} ({savings_pct:.1f}% OFF)</code>\n"
                        f"📍 <b>Delivery PIN:</b> <code>{pin}</code>\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"⚡ Target price reached! Click below to buy or stop tracking."
                    )
                else:
                    diff = new_price - target_price
                    update_text = (
                        f"📊 <b>{badge_escaped} Price Check Update</b> (ID: <code>#{product_id}</code>)\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"📦 <b>{title_escaped}...</b>\n\n"
                        f"💰 <b>Current Price:</b> <code>{currency}{new_price:,.2f}</code>\n"
                        f"🎯 <b>Desired Set Price:</b> <code>{currency}{target_price:,.2f}</code>\n"
                        f"📈 <b>Difference:</b> <code>{currency}{diff:,.2f}</code> above your target\n"
                        f"📍 <b>Delivery PIN:</b> <code>{pin}</code>\n"
                        f"━━━━━━━━━━━━━━━━━━━\n"
                        f"🕒 <i>Next automated check in 4 hours.</i>"
                    )

                sent = await send_alert_safely(context, chat_id, user_id, update_text, image_url, reply_markup)
                if not sent:
                    break

                # Micro-pause between messages to the same chat to respect 1 msg/sec limit
                await asyncio.sleep(0.5)

            # Randomized human-like jitter delay between product URLs to prevent platform rate limits
            await asyncio.sleep(random.uniform(1.5, 3.5))
        except Exception as e:
            logger.error(f"Error checking price for {fetch_url}: {e}")
            await asyncio.sleep(random.uniform(1.0, 2.0))


# ---------------------------------------------------------
# Main Application Launcher
# ---------------------------------------------------------

def main() -> None:
    """Initialize and run the Price Drop Tracker Bot."""
    if not BOT_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN is not set in .env file!")
        return

    database.init_db()
    logger.info("Price Tracker Database initialized successfully with WAL mode.")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("track", track_command))
    app.add_handler(CommandHandler("alert", track_command))
    app.add_handler(CommandHandler("pincode", pincode_command))
    app.add_handler(CommandHandler("setpin", pincode_command))
    app.add_handler(CommandHandler("pin", pincode_command))
    app.add_handler(CommandHandler("products", list_products_command))
    app.add_handler(CommandHandler("alerts", list_products_command))
    app.add_handler(CommandHandler("tracked", list_products_command))
    app.add_handler(CommandHandler("deltrack", deltrack_command))
    app.add_handler(CommandHandler("cleartrack", cleartrack_command))

    # Interactive button handler
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Direct message handler (Auto-detects when a product link is pasted)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url_message))

    # Background Job: Configurable polling interval (default: 14400s / 4 hours)
    poll_interval = int(os.getenv("CHECK_INTERVAL", 14400))
    if app.job_queue:
        app.job_queue.run_repeating(check_prices_job, interval=poll_interval, first=15)
        logger.info(f"Price drop background job registered ({poll_interval}s interval - every {poll_interval // 3600} hours).")

    print("\n" + "=" * 65)
    print("🛍️ Multi-Platform Price Drop Bot (@Stockmightybot) Live!")
    print("=" * 65)
    print("Monitoring 11 Platforms: Amazon, Flipkart, Myntra, Nykaa, Tira, Meesho, Savana, JioMart, Reliance Digital, Croma & Samsung...\n")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
