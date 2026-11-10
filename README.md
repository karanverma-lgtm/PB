# StockMightyBot (@Stockmightybot) 📈🤖

A full-featured Telegram stock market assistant that delivers real-time stock prices, technical trend charts, automated target price alerts, technical indicators (RSI & SMA), market news, and personal watchlists directly to your Telegram chat.

---

## 🌟 Key Features

1. **🔔 Target Price Alerts (Automatic Above/Below Detection)**
   - Set a target price for any asset: `/alert <SYMBOL> <TARGET_PRICE>`
   - Automatically determines whether your target is above (bullish target) or below (stop-loss/dip target) the current price.
   - Runs a 24/7 background monitor that checks live prices every 60 seconds and immediately sends you an alert notification when the price reaches your target!

2. **💰 Real-time Quotes & Crypto Auto-Resolution**
   - Query global stocks, Indian stocks (NSE/BSE), commodities, and crypto.
   - Automatically maps crypto pairs: `btcusd`, `btcusdt`, `btc` ➔ `BTC-USD`.
   - Displays current price, daily gain/loss ($ and %), day high, day low, and previous close.

3. **📊 Technical Analysis (`/ta`)**
   - Calculates **RSI (14-day)** with overbought/oversold status.
   - Computes **50-day & 200-day Simple Moving Averages (SMA)**.
   - Provides overall technical sentiment (🟢 Bullish / 🟡 Neutral / 🔴 Bearish).

4. **📰 Market News (`/news`)**
   - Fetches the latest 4 market headlines with direct article links and publishers.

5. **⭐ Personal Watchlist (`/watchlist`)**
   - Save your favorite assets (`/addwatch <SYMBOL>`) and view them in a single dashboard with live prices and daily % changes.

6. **📈 Interactive Charts (`/chart`)**
   - High-resolution dark-themed trend charts rendered via Matplotlib (`1d`, `5d`, `1mo`, `3mo`, `1y`).

7. **💾 Persistent SQLite Database**
   - Alerts and watchlists survive bot restarts and crashes via a local SQLite database (`alerts.db`).

---

## 📱 Bot Commands

| Command | Description | Example |
|---|---|---|
| `/start` | Welcome message and interactive quick-start menu | `/start` |
| `/help` | Detailed instructions and syntax guide | `/help` |
| `/price <SYMBOL>` | Real-time quote for any stock or crypto | `/price NIFTY 50`<br>`/price btcusd`<br>`/price AAPL` |
| `/alert <SYMBOL> <TARGET>` | Set target price alert (auto-detects above/below) | `/alert btcusd 74320`<br>`/alert NIFTY 50 25044`<br>`/alert TSLA 250` |
| `/alerts` | View your active alerts with 1-click delete | `/alerts` |
| `/delalert <ID>` | Delete an alert by ID | `/delalert 2` |
| `/clearalerts` | Delete all active alerts | `/clearalerts` |
| `/chart <SYMBOL> [PERIOD]` | Send price chart image (1d, 5d, 1mo, 3mo, 1y) | `/chart NVDA 1mo`<br>`/chart btcusd 3mo` |
| `/ta <SYMBOL>` | Technical analysis (RSI, 50 & 200 SMA, Sentiment) | `/ta btcusd`<br>`/ta NIFTY 50` |
| `/news <SYMBOL>` | Latest market headlines with links | `/news RELIANCE`<br>`/news TSLA` |
| `/watchlist` | View your personal watchlist dashboard | `/watchlist` |
| `/addwatch <SYMBOL>` | Add asset to personal watchlist | `/addwatch btcusd`<br>`/addwatch TCS` |
| `/delwatch <SYMBOL>` | Remove asset from personal watchlist | `/delwatch TCS` |

---

## 🚀 Deployment

The bot includes deployment blueprints for 24/7 cloud hosting:
- `Procfile` & `render.yaml` — Ready for **Render** or **Railway**
- `Dockerfile` — Ready for **Fly.io**, **Railway**, **DigitalOcean**, or any VPS

---

## 🛠 Project Structure

```
C:\Users\xMonks\TB\
├── .env                # Bot token & configuration (hidden/git-ignored)
├── .env.example        # Configuration template
├── .gitignore          # Git exclusion rules
├── bot.py              # Main Telegram bot runtime, handlers & background scheduler
├── database.py         # SQLite database models for alerts and watchlists
├── stock_service.py    # Quotes, charts, technical indicators & news fetcher
├── Dockerfile          # Container configuration
├── Procfile            # Cloud process definition
├── render.yaml         # Blueprint for Render
├── requirements.txt    # Project dependencies
└── README.md           # Documentation
```
