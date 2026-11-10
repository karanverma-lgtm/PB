"""Product Scraping & Price Extraction Service for Amazon & Flipkart.

Uses curl_cffi for realistic browser TLS fingerprinting to reliably extract
product title, current price, image, and platform from Amazon and Flipkart.
"""

import re
import logging
from typing import Optional, Dict, Any, Tuple
from curl_cffi import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
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


def detect_platform(url_or_text: str) -> str:
    """Detect whether a link is from Amazon or Flipkart."""
    text = url_or_text.lower().strip()
    if "flipkart.com" in text or "dl.flipkart.com" in text:
        return "Flipkart"
    if "amazon." in text or "amzn." in text or re.match(r"^[A-Z0-9]{10}$", url_or_text.strip()):
        return "Amazon"
    return "Unknown"


# ---------------------------------------------------------
# Amazon Scraper
# ---------------------------------------------------------

def extract_amazon_asin(text: str) -> Optional[str]:
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


def fetch_amazon_product(url_or_asin: str) -> Optional[Dict[str, Any]]:
    """Fetch live product details from Amazon."""
    try:
        # Resolve short URL if needed
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
                logger.debug(f"Amazon short link redirect error: {e}")

        asin = extract_amazon_asin(url_or_asin)
        if not asin:
            return None

        domain = "amazon.com" if "amazon.com" in url_or_asin.lower() else "amazon.in"
        canonical_url = f"https://www.{domain}/dp/{asin}"

        res = requests.get(canonical_url, impersonate="chrome120", headers=HEADERS, timeout=20)
        if res.status_code != 200:
            return None

        soup = BeautifulSoup(res.text, "html.parser")

        # Title
        title_elem = soup.find("span", id="productTitle")
        if not title_elem:
            return None
        title = title_elem.get_text(strip=True)

        # Price
        price = None
        currency = "₹" if "amazon.in" in canonical_url else "$"

        price_whole = soup.find("span", class_="a-price-whole")
        price_fraction = soup.find("span", class_="a-price-fraction")

        if price_whole:
            p_str = price_whole.get_text(strip=True).replace(",", "").replace(".", "").strip()
            if p_str.isdigit():
                frac = price_fraction.get_text(strip=True) if price_fraction else "00"
                frac = frac if frac.isdigit() else "00"
                price = float(f"{p_str}.{frac}")

        if price is None:
            for selector in ["span.apexPriceToPay span.a-offscreen", "span#priceblock_ourprice", "span#priceblock_dealprice"]:
                elem = soup.select_one(selector)
                if elem:
                    txt = elem.get_text(strip=True)
                    match = re.search(r"[\d,]+(?:\.\d+)?", txt)
                    if match:
                        price = float(match.group(0).replace(",", ""))
                        break

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
            return None

        sym_elem = soup.find("span", class_="a-price-symbol")
        if sym_elem:
            currency = sym_elem.get_text(strip=True)

        img_elem = soup.find("img", id="landingImage") or soup.find("img", id="imgBlkFront")
        img_url = img_elem.get("src") if img_elem else None

        return {
            "platform": "Amazon",
            "platform_badge": "📦 Amazon",
            "item_id": asin,
            "title": title,
            "price": round(price, 2),
            "currency": currency,
            "url": canonical_url,
            "image_url": img_url,
        }
    except Exception as e:
        logger.error(f"Error scraping Amazon: {e}")
        return None


# ---------------------------------------------------------
# Flipkart Scraper
# ---------------------------------------------------------

def extract_flipkart_id(url: str) -> str:
    """Extract unique product identifier or clean URL for Flipkart."""
    pid_match = re.search(r"pid=([A-Z0-9]+)", url, re.IGNORECASE)
    if pid_match:
        return pid_match.group(1).upper()
    itm_match = re.search(r"/p/(itm[a-zA-Z0-9]+)", url)
    if itm_match:
        return itm_match.group(1)
    return "FLIPKART_ITEM"


def fetch_flipkart_product(url: str) -> Optional[Dict[str, Any]]:
    """Fetch live product details from Flipkart."""
    try:
        res = requests.get(url, impersonate="chrome120", headers=HEADERS, allow_redirects=True, timeout=20)
        if res.status_code != 200:
            return None

        soup = BeautifulSoup(res.text, "html.parser")

        # Title
        title = None
        for sel in ["span.VU-ZEz", "span.B_NuCI", "h1 span", "h1"]:
            elem = soup.select_one(sel)
            if elem and elem.get_text(strip=True):
                title = elem.get_text(strip=True)
                break
        if not title:
            og_title = soup.find("meta", property="og:title")
            if og_title:
                title = og_title.get("content", "").replace("Online at Best Price in India - Flipkart", "").strip()

        if not title:
            return None

        # Price
        price = None
        p_elem = soup.select_one("div.Nx9bqj") or soup.select_one("div._30jeq3")
        if p_elem:
            m = re.search(r"[\d,]+", p_elem.get_text())
            if m:
                price = float(m.group(0).replace(",", ""))

        if price is None:
            for text_node in soup.find_all(string=re.compile(r"₹\s*[\d,]+")):
                p_text = text_node.strip()
                if any(w in p_text.lower() for w in ["protect", "fee", "emi", "buy at", "pay"]):
                    continue
                m = re.search(r"₹\s*([\d,]+)", p_text)
                if m:
                    val = float(m.group(1).replace(",", ""))
                    if val > 10:
                        price = val
                        break

        if price is None:
            return None

        # Image
        img_url = None
        img_matches = re.findall(r"https://rukminim\d*\.flixcart\.com/image/[^\"\'\s]+", res.text)
        if img_matches:
            img_url = img_matches[0]

        item_id = extract_flipkart_id(res.url)

        return {
            "platform": "Flipkart",
            "platform_badge": "🛍️ Flipkart",
            "item_id": item_id,
            "title": title,
            "price": round(price, 2),
            "currency": "₹",
            "url": res.url,
            "image_url": img_url,
        }
    except Exception as e:
        logger.error(f"Error scraping Flipkart: {e}")
        return None


# ---------------------------------------------------------
# Unified Fetcher
# ---------------------------------------------------------

def fetch_product(url_or_text: str) -> Optional[Dict[str, Any]]:
    """Automatically detect platform and fetch product details."""
    platform = detect_platform(url_or_text)
    if platform == "Flipkart":
        return fetch_flipkart_product(url_or_text)
    elif platform == "Amazon":
        return fetch_amazon_product(url_or_text)
    else:
        # Try Amazon first, then Flipkart
        return fetch_amazon_product(url_or_text) or fetch_flipkart_product(url_or_text)
