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
    "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8,hi;q=0.7",
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


def clean_url_from_text(raw_text: str) -> str:
    """Extract clean URL if user shared a message with words and a link."""
    m = re.search(r"https?://[^\s]+", raw_text)
    if m:
        return m.group(0).strip(").,>\"'")
    return raw_text.strip()


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
    text = clean_url_from_text(text)
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
    clean_target = clean_url_from_text(url_or_asin)
    try:
        # Resolve short URL if needed (amzn.in or amzn.to)
        if "amzn.to" in clean_target or "amzn.in" in clean_target:
            try:
                head_res = requests.get(
                    clean_target,
                    impersonate="chrome120",
                    headers=HEADERS,
                    allow_redirects=True,
                    timeout=15,
                )
                if head_res.url and head_res.url != clean_target:
                    clean_target = head_res.url
            except Exception as e:
                logger.debug(f"Amazon short link redirect error: {e}")

        asin = extract_amazon_asin(clean_target)
        if not asin:
            logger.error(f"Could not extract ASIN from {clean_target}")
            return None

        domain = "amazon.com" if "amazon.com" in clean_target.lower() else "amazon.in"
        canonical_url = f"https://www.{domain}/dp/{asin}"

        res = requests.get(canonical_url, impersonate="chrome120", headers=HEADERS, timeout=20)
        if res.status_code != 200:
            logger.error(f"Amazon HTTP {res.status_code} for {canonical_url}")
            return None

        # Check for CAPTCHA block
        if "api-services-support@amazon.com" in res.text or "validateCaptcha" in res.text:
            logger.warning(f"Amazon CAPTCHA detected for {canonical_url}")
            return None

        soup = BeautifulSoup(res.text, "html.parser")

        # Title Extraction
        title = None
        title_elem = soup.find("span", id="productTitle")
        if title_elem and title_elem.get_text(strip=True):
            title = title_elem.get_text(strip=True)
        else:
            og_title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "title"})
            if og_title and og_title.get("content"):
                title = og_title.get("content").replace("Amazon.in:", "").replace("Amazon.com:", "").strip()

        if not title:
            logger.error("Could not find product title on Amazon")
            return None

        # Price Extraction
        price = None
        currency = "₹" if "amazon.in" in canonical_url else "$"

        # 1. Whole + Fraction
        price_whole = soup.find("span", class_="a-price-whole")
        price_fraction = soup.find("span", class_="a-price-fraction")

        if price_whole:
            p_str = price_whole.get_text(strip=True).replace(",", "").replace(".", "").strip()
            if p_str.isdigit():
                frac = price_fraction.get_text(strip=True) if price_fraction else "00"
                frac = frac if frac.isdigit() else "00"
                price = float(f"{p_str}.{frac}")

        # 2. Selectors fallback
        if price is None:
            for selector in [
                "span.priceToPay span.a-offscreen",
                "span.apexPriceToPay span.a-offscreen",
                "span.a-price.a-text-price span.a-offscreen",
                "span#priceblock_ourprice",
                "span#priceblock_dealprice",
                "span.a-price span.a-offscreen",
            ]:
                elem = soup.select_one(selector)
                if elem:
                    txt = elem.get_text(strip=True)
                    match = re.search(r"[\d,]+(?:\.\d+)?", txt)
                    if match:
                        price = float(match.group(0).replace(",", ""))
                        break

        # 3. Regex search for ₹ on page if still None
        if price is None:
            price_div = soup.find("div", id=re.compile(r"corePrice|apex_desktop|desktop_unifiedPrice|buybox"))
            if price_div:
                matches = re.findall(r"₹\s*([\d,]+(?:\.\d+)?)", price_div.get_text())
                if matches:
                    price = float(matches[0].replace(",", ""))

        if price is None:
            logger.warning(f"Product '{title[:40]}' found but price is unavailable / out of stock.")
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
    clean_target = clean_url_from_text(url)
    try:
        res = requests.get(clean_target, impersonate="chrome120", headers=HEADERS, allow_redirects=True, timeout=20)
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
    clean_target = clean_url_from_text(url_or_text)
    platform = detect_platform(clean_target)
    if platform == "Flipkart":
        return fetch_flipkart_product(clean_target)
    elif platform == "Amazon":
        return fetch_amazon_product(clean_target)
    else:
        return fetch_amazon_product(clean_target) or fetch_flipkart_product(clean_target)
