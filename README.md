# Amazon Price Drop Tracker Bot 🛍️📉

A full-featured Telegram bot that tracks Amazon product prices in real time and automatically sends you an instant Telegram notification whenever an item drops to or below your desired target price.

---

## 🌟 Key Features

1. **🔗 Universal Amazon Link Support**
   - Works with **Amazon India (`amazon.in`)** and **Amazon US / Global (`amazon.com`)**.
   - Supports regular product URLs (`/dp/...`, `/gp/product/...`) and mobile short links (`amzn.in/d/...`, `amzn.to/...`).

2. **⚡ Seamless 1-Click Tracking**
   - **Method A:** Just paste or share any Amazon product link into the chat! The bot automatically fetches the product image, title, and current price, and displays quick 1-click discount buttons (`5% Drop`, `10% Drop`, `15% Drop`).
   - **Method B:** Use `/track <AMAZON_URL> <TARGET_PRICE>` to set an exact target price.

3. **⏰ Background Price Monitoring**
   - Runs a 24/7 background scheduler checking all active tracked items.
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
| `/track <URL> <PRICE>` | Track an Amazon item at target price | `/track https://www.amazon.in/dp/B09G9BL5CP 75000` |
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
├── amazon_service.py   # Amazon product scraper with curl_cffi browser impersonation
├── Dockerfile          # Container configuration
├── Procfile            # Cloud process definition
├── render.yaml         # Blueprint for Render
├── requirements.txt    # Project dependencies
└── README.md           # Documentation
```
