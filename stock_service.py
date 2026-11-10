"""Stock data fetching, charting, technical analysis, and news service."""

import io
import re
import logging
from typing import Optional, Dict, Any, List
import yfinance as yf
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

logger = logging.getLogger(__name__)

# Common Market Aliases mapped to Yahoo Finance Tickers
SYMBOL_ALIASES = {
    "NIFTY": "^NSEI",
    "NIFTY 50": "^NSEI",
    "NIFTY50": "^NSEI",
    "NIFTY-50": "^NSEI",
    "CNX NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "BANK NIFTY": "^NSEBANK",
    "NIFTY BANK": "^NSEBANK",
    "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
    "NIFTY FINANCIAL": "NIFTY_FIN_SERVICE.NS",
    "SENSEX": "^BSESN",
    "BSE SENSEX": "^BSESN",
    "MIDCAPNIFTY": "^NSEMDCP50",
    "NIFTY MIDCAP": "^NSEMDCP50",
    "NIFTY IT": "^CNXIT",
    "NIFTYIT": "^CNXIT",
    "INDIA VIX": "^INDIAVIX",
    "INDIAVIX": "^INDIAVIX",
    "VIX": "^INDIAVIX",
    "SP500": "^GSPC",
    "S&P 500": "^GSPC",
    "S&P500": "^GSPC",
    "SPX": "^GSPC",
    "NASDAQ": "^IXIC",
    "NDX": "^IXIC",
    "DOW": "^DJI",
    "DJIA": "^DJI",
    "DOW JONES": "^DJI",
    "RUSSELL 2000": "^RUT",
    "GOLD": "GC=F",
    "SILVER": "SI=F",
    "CRUDE": "CL=F",
    "CRUDE OIL": "CL=F",
    "OIL": "CL=F",
    "NATURAL GAS": "NG=F",
    "BITCOIN": "BTC-USD",
    "ETHEREUM": "ETH-USD",
    "SOLANA": "SOL-USD",
}

KNOWN_CRYPTOS = {
    "BTC", "ETH", "SOL", "DOGE", "XRP", "ADA", "BNB", "DOT",
    "AVAX", "LINK", "MATIC", "SHIB", "PEPE", "LTC", "NEAR",
    "SUI", "APT", "XMR", "TRX", "TON", "XLM", "BCH", "UNI"
}

FRIENDLY_NAMES = {
    "^NSEI": "NIFTY 50 Index",
    "^NSEBANK": "NIFTY Bank Index",
    "^BSESN": "BSE SENSEX Index",
    "^NSEMDCP50": "NIFTY Midcap 50",
    "^CNXIT": "NIFTY IT Index",
    "^INDIAVIX": "India VIX",
    "^GSPC": "S&P 500 Index",
    "^IXIC": "NASDAQ Composite",
    "^DJI": "Dow Jones Industrial Average",
    "GC=F": "Gold Futures",
    "SI=F": "Silver Futures",
    "CL=F": "Crude Oil Futures",
    "BTC-USD": "Bitcoin (USD)",
    "ETH-USD": "Ethereum (USD)",
    "SOL-USD": "Solana (USD)",
    "DOGE-USD": "Dogecoin (USD)",
}


def resolve_symbol(raw: str) -> str:
    """Normalize input and resolve aliases (e.g. 'btcusd' -> 'BTC-USD', 'NIFTY 50' -> '^NSEI')."""
    cleaned = re.sub(r"\s+", " ", raw.strip()).upper().replace("/", "").replace("_", "")

    # Check direct aliases
    if cleaned in SYMBOL_ALIASES:
        return SYMBOL_ALIASES[cleaned]

    # Handle Crypto formats: BTCUSDT -> BTC-USD, BTCUSD -> BTC-USD
    if cleaned.endswith("USDT") and len(cleaned) > 4:
        base = cleaned[:-4]
        return f"{base}-USD"

    if cleaned.endswith("USD") and "-" not in cleaned and len(cleaned) > 3:
        base = cleaned[:-3]
        if base in KNOWN_CRYPTOS or len(base) in [3, 4, 5]:
            return f"{base}-USD"

    # Handle bare crypto symbol: BTC -> BTC-USD
    if cleaned in KNOWN_CRYPTOS:
        return f"{cleaned}-USD"

    return cleaned


def _fetch_quote_for_ticker(ticker_symbol: str) -> Optional[Dict[str, Any]]:
    """Helper to fetch quote for a single resolved ticker symbol."""
    try:
        ticker = yf.Ticker(ticker_symbol)
        fi = ticker.fast_info

        price = fi.get("lastPrice") or fi.get("last_price")
        prev_close = (
            fi.get("previousClose")
            or fi.get("regularMarketPreviousClose")
            or fi.get("previous_close")
        )
        day_high = fi.get("dayHigh") or fi.get("day_high")
        day_low = fi.get("dayLow") or fi.get("day_low")
        currency = fi.get("currency", "USD")

        if price is None:
            hist = ticker.history(period="5d")
            if hist.empty:
                return None
            price = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else price
            day_high = float(hist["High"].iloc[-1])
            day_low = float(hist["Low"].iloc[-1])

        price = float(price)
        prev_close = float(prev_close) if prev_close else price
        day_high = float(day_high) if day_high else price
        day_low = float(day_low) if day_low else price

        change = price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0.0

        name = FRIENDLY_NAMES.get(ticker_symbol)
        if not name:
            try:
                name = (
                    ticker.info.get("shortName")
                    or ticker.info.get("longName")
                    or ticker_symbol
                )
            except Exception:
                name = ticker_symbol

        return {
            "symbol": ticker_symbol,
            "name": name,
            "price": round(price, 2),
            "currency": currency or "USD",
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "day_high": round(day_high, 2),
            "day_low": round(day_low, 2),
            "prev_close": round(prev_close, 2),
        }
    except Exception as e:
        logger.debug(f"Failed to fetch {ticker_symbol}: {e}")
        return None


def get_stock_quote(symbol: str) -> Optional[Dict[str, Any]]:
    """Fetch real-time stock quote from Yahoo Finance."""
    resolved = resolve_symbol(symbol)
    quote = _fetch_quote_for_ticker(resolved)
    if quote:
        return quote

    # If it's a crypto pair ending with -USD that failed, don't fallback to .NS
    if "-USD" in resolved:
        return None

    # Fallback to Indian markets if no suffix
    if not any(char in resolved for char in [".", "^", "=", "-"]):
        nse_quote = _fetch_quote_for_ticker(f"{resolved}.NS")
        if nse_quote:
            return nse_quote
        bse_quote = _fetch_quote_for_ticker(f"{resolved}.BO")
        if bse_quote:
            return bse_quote

    return None


def generate_stock_chart(symbol: str, period: str = "1mo") -> Optional[io.BytesIO]:
    """Generate a price trend chart for the given symbol."""
    resolved = resolve_symbol(symbol)
    try:
        ticker = yf.Ticker(resolved)
        hist = ticker.history(period=period)

        if (hist.empty or len(hist) < 2) and not any(char in resolved for char in [".", "^", "=", "-"]):
            resolved = f"{resolved}.NS"
            ticker = yf.Ticker(resolved)
            hist = ticker.history(period=period)

        if hist.empty or len(hist) < 2:
            return None

        plt.style.use("seaborn-v0_8-darkgrid" if "seaborn-v0_8-darkgrid" in plt.style.available else "default")
        fig, ax = plt.subplots(figsize=(9, 4.5), dpi=150)
        fig.patch.set_facecolor("#161b22")
        ax.set_facecolor("#0d1117")

        first_price = hist["Close"].iloc[0]
        last_price = hist["Close"].iloc[-1]
        line_color = "#3fb950" if last_price >= first_price else "#f85149"
        fill_color = "#238636" if last_price >= first_price else "#da3633"

        ax.plot(hist.index, hist["Close"], color=line_color, linewidth=2, label="Close")
        ax.fill_between(hist.index, hist["Close"], hist["Close"].min() * 0.99, color=fill_color, alpha=0.15)

        currency = ticker.fast_info.get("currency", "USD")
        change_val = last_price - first_price
        change_pct = (change_val / first_price) * 100

        sign = "+" if change_val >= 0 else ""
        display_name = FRIENDLY_NAMES.get(resolved, resolved)
        ax.set_title(
            f"{display_name} ({period.upper()}) | {last_price:.2f} {currency} ({sign}{change_pct:.2f}%)",
            color="#ffffff",
            fontsize=13,
            pad=12,
            fontweight="bold",
        )

        ax.tick_params(colors="#8b949e", labelsize=9)
        date_format = "%H:%M" if period == "1d" else "%b %d" if period in ["5d", "1mo", "3mo"] else "%b %Y"
        ax.xaxis.set_major_formatter(mdates.DateFormatter(date_format))
        fig.autofmt_xdate()

        for spine in ax.spines.values():
            spine.set_color("#30363d")

        ax.grid(True, linestyle="--", alpha=0.3, color="#30363d")

        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception as e:
        logger.error(f"Error generating chart for {resolved}: {e}")
        return None


def get_stock_news(symbol: str) -> List[Dict[str, str]]:
    """Fetch top recent news articles for a symbol."""
    resolved = resolve_symbol(symbol)
    try:
        ticker = yf.Ticker(resolved)
        articles = []
        for item in (ticker.news or [])[:4]:
            content = item.get("content", {})
            title = content.get("title") or item.get("title")
            canonical = content.get("canonicalUrl", {})
            url = canonical.get("url") or item.get("link")
            provider = content.get("provider", {}).get("displayName") or item.get("publisher") or "Market News"
            if title and url:
                articles.append({
                    "title": title,
                    "url": url,
                    "publisher": provider,
                })
        return articles
    except Exception as e:
        logger.error(f"Error fetching news for {resolved}: {e}")
        return []


def get_technical_analysis(symbol: str) -> Optional[Dict[str, Any]]:
    """Calculate key technical indicators (RSI 14, SMA 50, SMA 200, 52w range)."""
    resolved = resolve_symbol(symbol)
    try:
        ticker = yf.Ticker(resolved)
        hist = ticker.history(period="1y")

        if (hist.empty or len(hist) < 30) and not any(char in resolved for char in [".", "^", "=", "-"]):
            resolved = f"{resolved}.NS"
            ticker = yf.Ticker(resolved)
            hist = ticker.history(period="1y")

        if hist.empty or len(hist) < 20:
            return None

        close = hist["Close"]
        current_price = float(close.iloc[-1])
        currency = ticker.fast_info.get("currency", "USD")

        # 50 and 200 Moving Averages
        sma50 = float(close.rolling(window=50).mean().iloc[-1]) if len(close) >= 50 else None
        sma200 = float(close.rolling(window=200).mean().iloc[-1]) if len(close) >= 200 else None

        # RSI (14 period)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss.replace(0, 0.0001))
        rsi = float((100 - (100 / (1 + rs))).iloc[-1])

        high_52w = float(hist["High"].max())
        low_52w = float(hist["Low"].min())

        score = 0
        if sma50 and current_price > sma50:
            score += 1
        if sma200 and current_price > sma200:
            score += 1
        if sma50 and sma200 and sma50 > sma200:
            score += 1

        if rsi > 70:
            rsi_desc = "Overbought (> 70)"
        elif rsi < 30:
            rsi_desc = "Oversold (< 30)"
        else:
            rsi_desc = "Neutral (30-70)"

        if score >= 2 and rsi < 70:
            sentiment = "🟢 Bullish"
        elif score == 0 or rsi > 70:
            sentiment = "🔴 Bearish / Overheated"
        else:
            sentiment = "🟡 Neutral"

        return {
            "symbol": resolved,
            "name": FRIENDLY_NAMES.get(resolved, resolved),
            "price": round(current_price, 2),
            "currency": currency,
            "rsi": round(rsi, 1),
            "rsi_desc": rsi_desc,
            "sma50": round(sma50, 2) if sma50 else None,
            "sma200": round(sma200, 2) if sma200 else None,
            "high_52w": round(high_52w, 2),
            "low_52w": round(low_52w, 2),
            "sentiment": sentiment,
        }
    except Exception as e:
        logger.error(f"Error calculating TA for {resolved}: {e}")
        return None
