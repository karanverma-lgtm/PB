"""Stock data fetching and charting service using Yahoo Finance and Matplotlib.

Supports global equities, Indian markets (NSE/BSE), commodities, currencies, and major indices.
"""

import io
import re
import logging
from typing import Optional, Dict, Any
import yfinance as yf
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
    "BTC": "BTC-USD",
    "BITCOIN": "BTC-USD",
    "ETH": "ETH-USD",
    "ETHEREUM": "ETH-USD",
    "SOL": "SOL-USD",
    "SOLANA": "SOL-USD",
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
}


def resolve_symbol(raw: str) -> str:
    """Normalize input and resolve aliases (e.g. 'NIFTY 50' -> '^NSEI')."""
    cleaned = re.sub(r"\s+", " ", raw.strip()).upper()
    return SYMBOL_ALIASES.get(cleaned, cleaned)


def _fetch_quote_for_ticker(ticker_symbol: str) -> Optional[Dict[str, Any]]:
    """Helper to fetch quote for a single resolved ticker symbol."""
    try:
        ticker = yf.Ticker(ticker_symbol)
        fi = ticker.fast_info

        # Handle both camelCase and snake_case attributes
        price = fi.get("lastPrice") or fi.get("last_price")
        prev_close = (
            fi.get("previousClose")
            or fi.get("regularMarketPreviousClose")
            or fi.get("previous_close")
        )
        day_high = fi.get("dayHigh") or fi.get("day_high")
        day_low = fi.get("dayLow") or fi.get("day_low")
        currency = fi.get("currency", "USD")

        # Fallback to history if fast_info returned no price
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

        # Determine name
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
    """
    Fetch real-time stock quote from Yahoo Finance.
    Handles aliases and auto-falls back to Indian NSE (.NS) if standard US ticker is not found.
    """
    resolved = resolve_symbol(symbol)
    quote = _fetch_quote_for_ticker(resolved)
    if quote:
        return quote

    # If not found and symbol has no exchange suffix, try Indian NSE (.NS)
    if not any(char in resolved for char in [".", "^", "=", "-"]):
        nse_symbol = f"{resolved}.NS"
        nse_quote = _fetch_quote_for_ticker(nse_symbol)
        if nse_quote:
            return nse_quote

        # Also try BSE (.BO)
        bse_symbol = f"{resolved}.BO"
        bse_quote = _fetch_quote_for_ticker(bse_symbol)
        if bse_quote:
            return bse_quote

    return None


def generate_stock_chart(symbol: str, period: str = "1mo") -> Optional[io.BytesIO]:
    """
    Generate a price trend chart for the given symbol and return as a BytesIO stream.
    """
    resolved = resolve_symbol(symbol)
    try:
        ticker = yf.Ticker(resolved)
        hist = ticker.history(period=period)

        # Fallback to .NS if needed
        if (hist.empty or len(hist) < 2) and not any(char in resolved for char in [".", "^", "=", "-"]):
            resolved = f"{resolved}.NS"
            ticker = yf.Ticker(resolved)
            hist = ticker.history(period=period)

        if hist.empty or len(hist) < 2:
            return None

        # Clean style setup
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
