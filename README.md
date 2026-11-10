# Amazon & Flipkart Price Drop Tracker Bot 🛍️📉

A full-featured Telegram bot that tracks product prices across **Amazon** and **Flipkart** in real time and automatically delivers an instant Telegram notification whenever an item drops to or below your desired target price.

---

## 🌟 Key Features

1. **🛍️ Multi-Platform Support**
   - **Amazon:** Amazon India (`amazon.in`), Amazon US/Global (`amazon.com`), and mobile short links (`amzn.in/d/...`, `amzn.to/...`).
   - **Flipkart:** `flipkart.com` and Flipkart mobile app short links (`dl.flipkart.com/s/...`).

2. **⚡ Seamless 1-Click Tracking**
   - **Method A:** Just paste or share any Amazon or Flipkart product link into the chat! The bot automatically detects the platform, fetches product image, title, and current price, and displays quick 1-click discount buttons (`5% Drop`, `10% Drop`, `15% Drop`).
   - **Method B:** Use `/track <PRODUCT_URL> <TARGET_PRICE>` to set an exact target price.

3. **⏰ 24/7 Background Price Monitoring**
   - Runs a background worker checking all active tracked items every 5 minutes.
   - When the price drops to or below your target, you receive an instant alert with product photo, amount saved, and direct link to buy.

4. **📋 Tracked Items Dashboard**
   - Run `/products` or `/alerts` to see all items you are monitoring, current vs target prices, and 1-click buttons to stop tracking.

5. **💾 SQLite Persistent Storage**
   - Products and alerts survive bot restarts and crashes via local SQLite (`alerts.db`).

---

## 📱 Bot Commands

| Command | Description | Example |
|---|---|---|
| `/start` | Launch menu & instructions | `/start` |
| `/track <URL> <PRICE>` | Track item with target price | `/track https://www.flipkart.com/... 55000`<br>`/track https://www.amazon.in/... 75000` |
| `/products` | View and manage all your tracked items | `/products` |
| `/deltrack <ID>` | Stop tracking a specific item | `/deltrack 1` |
| `/cleartrack` | Stop tracking all items | `/cleartrack` |
| `/help` | Detailed instructions & examples | `/help` |

---

## 🚀 Deployment

The bot includes deployment blueprints for 24/7 cloud hosting on **Railway**, **Render**, or any Docker host:
- `Procfile` & `render.yaml` — Configured for cloud workers
- `Dockerfile` — Ready for containerized deployment
- `requirements.txt` — Dependencies (`python-telegram-bot[job-queue]`, `curl_cffi`, `beautifulsoup4`, `lxml`, `python-dotenv`)

---

## 🛠 Project Structure

```
C:\Users\xMonks\TB\
├── .env                # Bot token & configuration (hidden/git-ignored)
├── .env.example        # Configuration template
├── .gitignore          # Git exclusion rules
├── bot.py              # Telegram bot runtime, handlers & price monitor
├── database.py         # SQLite database models for tracked products
├── product_service.py  # Amazon & Flipkart scraper with curl_cffi browser impersonation
├── Dockerfile          # Container configuration
├── Procfile            # Cloud process definition
├── render.yaml         # Blueprint for Render
├── requirements.txt    # Project dependencies
└── README.md           # Documentation
```
