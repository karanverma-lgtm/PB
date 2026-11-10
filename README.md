# Multi-Platform Price Drop Tracker Bot 🛍️📉

A full-featured Telegram bot that tracks product prices across **6 major e-commerce platforms** in real time and automatically delivers an instant Telegram notification whenever an item drops to or below your desired target price.

---

## 🌟 Key Features

1. **🛍️ 6 Supported Platforms**
   - **Amazon India & Global** (`amazon.in`, `amazon.com`, `amzn.in/d/...`, `amzn.to/...`)
   - **Flipkart** (`flipkart.com`, `dl.flipkart.com/s/...`)
   - **JioMart** (`jiomart.com`)
   - **Reliance Digital** (`reliancedigital.in`)
   - **Croma** (`croma.com`)
   - **Samsung India** (`samsung.com/in`)

2. **⚡ Seamless 1-Click Tracking**
   - **Method A:** Just paste or share any product link from any of the 6 platforms into the chat! The bot automatically detects the platform, fetches the product photo, title, and current price, and displays quick 1-click discount buttons (`5% Drop`, `10% Drop`, `15% Drop`).
   - **Method B:** Use `/track <PRODUCT_URL> <TARGET_PRICE>` to set an exact target price.

3. **⏰ 24/7 Background Price Monitoring**
   - Runs a background worker checking all active tracked items across all platforms every 5 minutes.
   - When the price drops to or below your target, you receive an instant alert with product photo, amount saved, and direct link to buy.

4. **📋 Tracked Items Dashboard**
   - Run `/products` or `/alerts` to see all items you are monitoring, categorized with platform badges (📦 Amazon, 🛍️ Flipkart, 🟢 JioMart, 🔴 Reliance Digital, ⚪ Croma, 🌌 Samsung), current vs target prices, and 1-click buttons to stop tracking.

5. **💾 SQLite Persistent Storage**
   - Products and alerts survive bot restarts and crashes via local SQLite (`alerts.db`).

---

## 📱 Bot Commands

| Command | Description | Example |
|---|---|---|
| `/start` | Launch menu & platform guide | `/start` |
| `/track <URL> <PRICE>` | Track item with target price | `/track https://www.croma.com/.../p/300652 56000`<br>`/track https://www.reliancedigital.in/.../p/493839309 56000`<br>`/track https://www.amazon.in/dp/B09G9BL5CP 75000` |
| `/products` | View and manage all your tracked items | `/products` |
| `/deltrack <ID>` | Stop tracking a specific item | `/deltrack 1` |
| `/cleartrack` | Stop tracking all items | `/cleartrack` |
| `/help` | Detailed instructions & examples | `/help` |

---

## 🚀 Deployment & Cloud Persistence

The bot includes deployment blueprints for 24/7 cloud hosting on **Railway**, **Render**, or any Docker host:
- `Procfile` & `render.yaml` — Configured for cloud workers
- `Dockerfile` — Ready for containerized deployment
- `requirements.txt` — Dependencies (`python-telegram-bot[job-queue]`, `curl_cffi`, `beautifulsoup4`, `lxml`, `python-dotenv`)

### 💾 Persistent Storage on Railway / Docker
By default, Docker containers have ephemeral storage. To ensure tracked products survive container redeploys:
1. In your **Railway Service Settings**, click **Add Volume** and mount it to `/data`.
2. Add an environment variable in Railway: `DATA_DIR=/data`.
3. The bot will automatically store `alerts.db` on the persistent volume with SQLite WAL (Write-Ahead Logging) mode enabled!

---

## 🛠 Project Structure

```
C:\Users\xMonks\TB\
├── .env                # Bot token & configuration (hidden/git-ignored)
├── .env.example        # Configuration template
├── .gitignore          # Git exclusion rules
├── bot.py              # Telegram bot runtime, handlers & price monitor
├── database.py         # SQLite database models for tracked products
├── product_service.py  # Multi-platform scraper with curl_cffi browser impersonation
├── Dockerfile          # Container configuration
├── Procfile            # Cloud process definition
├── render.yaml         # Blueprint for Render
├── requirements.txt    # Project dependencies
└── README.md           # Documentation
```
