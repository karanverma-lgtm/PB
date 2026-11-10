"""Amazon Product Scraping and Price Extraction Service.

Uses curl_cffi for realistic browser TLS fingerprinting to reliably extract
product title, current price, image, and availability from Amazon India and global Amazon.
"""

import re
import logging
from typing import Optional, Dict, Any
from curl_cffi import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
    "Cache-Control": "max-age=0",
    "Sec-Ch-Ua": '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
}


def extract_asin(text: str) -> Optional[str]:
    """Extract 10-character Amazon Standard Identification Number (ASIN)."""
    text = text.strip()
    if re.match(r"^[A-Z0-9]{10}$", text, re.IGNORECASE):
        return text.upper()

    patterns = [
        r"/dp/([A-Z0-9]{10})",
        r"/gp/product/([A-Z0-9]{10})",
        r"/d/([A-Z0-9]{10})",
        r"/product/([A-Z0-9]{10})",
        r"/gp/aw/d/([A-Z0-9]{10})",
        r"/([A-Z0-9]{10})(?:[/?]|$)",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).upper()
    return None


def get_canonical_url(url_or_asin: str) -> tuple[str, str]:
    """Return (canonical_url, asin). Defaults to amazon.in if not specified."""
    asin = extract_asin(url_or_asin)
    if not asin:
        raise ValueError("Could not extract a valid Amazon ASIN or product link")

    domain = "amazon.com" if "amazon.com" in url_or_asin.lower() else "amazon.in"
    return f"https://www.{domain}/dp/{asin}", asin


def fetch_amazon_product(url_or_asin: str) -> Optional[Dict[str, Any]]:
    """
    Fetch live Amazon product details: Title, Current Price, Image, and Availability.
    """
    try:
        # If it's a short URL (amzn.in or amzn.to), resolve redirect first
        if "amzn.to" in url_or_asin or "amzn.in" in url_or_asin:
            try:
                head_res = requests.get(
                    url_or_asin,
                    impersonate="chrome120",
                    headers=HEADERS,
                    allow_redirects=True,
                    timeout=15,
                )
                url_or_asin = head_res.url
            except Exception as e:
                logger.debug(f"Short link resolution error: {e}")

        canonical_url, asin = get_canonical_url(url_or_asin)

        res = requests.get(
            canonical_url,
            impersonate="chrome120",
            headers=HEADERS,
            timeout=20,
        )

        if res.status_code != 200:
            logger.error(f"Amazon responded with HTTP {res.status_code} for {canonical_url}")
            return None

        soup = BeautifulSoup(res.text, "html.parser")

        # 1. Title Extraction
        title_elem = soup.find("span", id="productTitle")
        if not title_elem:
            logger.error("Could not find productTitle element")
            return None
        title = title_elem.get_text(strip=True)

        # 2. Price Extraction
        price = None
        currency = "₹" if "amazon.in" in canonical_url else "$"

        # Try .a-price-whole first (most common on Amazon)
        price_whole = soup.find("span", class_="a-price-whole")
        price_fraction = soup.find("span", class_="a-price-fraction")

        if price_whole:
            p_str = price_whole.get_text(strip=True).replace(",", "").replace(".", "").strip()
            if p_str.isdigit():
                frac = price_fraction.get_text(strip=True) if price_fraction else "00"
                frac = frac if frac.isdigit() else "00"
                price = float(f"{p_str}.{frac}")

        # Fallback 1: .apexPriceToPay or #priceblock_ourprice
        if price is None:
            for selector in ["span.apexPriceToPay span.a-offscreen", "span#priceblock_ourprice", "span#priceblock_dealprice"]:
                elem = soup.select_one(selector)
                if elem:
                    txt = elem.get_text(strip=True)
                    match = re.search(r"[\d,]+(?:\.\d+)?", txt)
                    if match:
                        price = float(match.group(0).replace(",", ""))
                        break

        # Fallback 2: Any .a-offscreen under price block
        if price is None:
            price_div = soup.find("div", id=re.compile(r"corePrice|apex_desktop|desktop_unifiedPrice"))
            if price_div:
                offscreen = price_div.find("span", class_="a-offscreen")
                if offscreen:
                    txt = offscreen.get_text(strip=True)
                    match = re.search(r"[\d,]+(?:\.\d+)?", txt)
                    if match:
                        price = float(match.group(0).replace(",", ""))

        if price is None:
            logger.warning(f"Product found ({title[:40]}) but price is currently unavailable / out of stock.")
            return None

        # Currency Symbol
        sym_elem = soup.find("span", class_="a-price-symbol")
        if sym_elem:
            currency = sym_elem.get_text(strip=True)

        # 3. Image URL Extraction
        img_elem = soup.find("img", id="landingImage") or soup.find("img", id="imgBlkFront")
        img_url = img_elem.get("src") if img_elem else None

        # 4. In Stock Check
        avail_elem = soup.find("div", id="availability")
        in_stock = True
        if avail_elem and "unavailable" in avail_elem.get_text().lower():
            in_stock = False

        return {
            "asin": asin,
            "title": title,
            "price": round(price, 2),
            "currency": currency,
            "url": canonical_url,
            "image_url": img_url,
            "in_stock": in_stock,
        }

    except Exception as e:
        logger.error(f"Error scraping Amazon product for {url_or_asin}: {e}")
        return None
