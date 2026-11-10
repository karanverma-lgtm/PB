# StockMightyBot (@Stockmightybot) 📈🤖

A full-featured Telegram stock market assistant that delivers real-time stock prices, technical trend charts, and automated target price alerts directly to your Telegram chat.

---

## 🌟 Key Features

1. **🔔 Target Price Alerts (Automatic Above/Below Detection)**
   - Set a target price for any stock: `/alert <SYMBOL> <TARGET_PRICE>`
   - Automatically determines whether your target is above (bullish target) or below (stop-loss/dip target) the current price.
   - The bot runs a 24/7 background monitor that checks live prices every 60 seconds and immediately sends you an alert notification when the price reaches your target!

2. **💰 Real-time Stock Quotes**
   - Query global stocks, Indian stocks (NSE/BSE), and crypto: `/price AAPL`, `/price RELIANCE.NS`, `/price BTC-USD`.
   - Displays current price, daily gain/loss ($ and %), day high, day low, and previous close.

3. **📊 Interactive Charts**
   - View candlestick / trend line charts rendered directly in Telegram: `/chart TSLA` or `/chart AAPL 3mo`.

4. **📋 Alert Management**
   - `/alerts` displays all active price targets with one-click interactive inline buttons to cancel or check current prices.
   - `/delalert <ID>` to remove a specific alert.
   - `/clearalerts` to wipe active alerts.

5. **💾 SQLite Persistent Storage**
   - Alerts survive bot restarts and crashes via a local SQLite database (`alerts.db`).

---

## 🚀 Quick Start

### 1. Requirements
Ensure Python 3.10+ is installed.

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Credentials
Create or edit `.env`:
```env
TELEGRAM_BOT_TOKEN=9241019062:AAHFY-X9PxhpefjdQjWjMhqAAwi85kJubIU
BOT_USERNAME=Stockmightybot
```

### 4. Run the Bot
```bash
python bot.py
```

---

## 📱 Bot Commands

| Command | Description | Example |
|---|---|---|
| `/start` | Welcome message and interactive quick-start menu | `/start` |
| `/help` | Detailed instructions and syntax guide | `/help` |
| `/price <SYMBOL>` | Real-time quote for any stock | `/price AAPL` or `/price RELIANCE.NS` |
| `/alert <SYMBOL> <TARGET>` | Set target price alert | `/alert TSLA 250` |
| `/alerts` | View your active alerts with 1-click delete | `/alerts` |
| `/delalert <ID>` | Delete an alert by ID | `/delalert 3` |
| `/clearalerts` | Delete all active alerts | `/clearalerts` |
| `/chart <SYMBOL> [PERIOD]` | Send price chart image (1d, 5d, 1mo, 3mo, 1y) | `/chart NVDA 1mo` |

---

## 🛠 Project Structure

```
C:\Users\xMonks\TB\
├── .env                # Bot token & configuration (hidden/git-ignored)
├── .env.example        # Configuration template
├── .gitignore          # Git exclusion rules
├── bot.py              # Main Telegram bot runtime, handlers & background scheduler
├── database.py         # SQLite database models & query operations
├── stock_service.py    # Yahoo Finance real-time quote & Matplotlib chart generator
├── requirements.txt    # Project dependencies
└── README.md           # Documentation
```

