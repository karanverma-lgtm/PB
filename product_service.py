"""Product Scraping & Price Extraction Service for Indian & Global E-Commerce.

Supports 6 major platforms:
1. Amazon (amazon.in, amazon.com, amzn.to, amzn.in)
2. Flipkart (flipkart.com, dl.flipkart.com)
3. JioMart (jiomart.com)
4. Reliance Digital (reliancedigital.in)
5. Croma (croma.com)
6. Samsung India (samsung.com/in)

Uses curl_cffi for browser TLS fingerprinting to reliably extract product title,
current price, image, item ID, and platform without getting blocked.
"""

import json
import re
import logging
from typing import Optional, Dict, Any
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
    """Detect whether a link is from Amazon, Flipkart, JioMart, Reliance Digital, Croma, or Samsung."""
    text = url_or_text.lower().strip()
    if "reliancedigital.in" in text:
        return "RelianceDigital"
    if "croma.com" in text:
        return "Croma"
    if "jiomart.com" in text:
        return "JioMart"
    if "samsung.com" in text:
        return "Samsung"
    if "flipkart.com" in text or "dl.flipkart.com" in text:
        return "Flipkart"
    if "amazon." in text or "amzn." in text or re.match(r"^[A-Z0-9]{10}$", url_or_text.strip()):
        return "Amazon"
    return "Unknown"


# =====================================================================
# 1. Amazon Scraper
# =====================================================================

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

        # 3. Regex search for currency on page if still None
        if price is None:
            price_div = soup.find("div", id=re.compile(r"corePrice|apex_desktop|desktop_unifiedPrice|buybox"))
            if price_div:
                matches = re.findall(r"[₹\$]\s*([\d,]+(?:\.\d+)?)", price_div.get_text())
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


# =====================================================================
# 2. Flipkart Scraper
# =====================================================================

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


# =====================================================================
# 3. JioMart Scraper
# =====================================================================

def fetch_jiomart_product(url: str) -> Optional[Dict[str, Any]]:
    """Fetch live product details from JioMart."""
    clean_target = clean_url_from_text(url)
    try:
        res = requests.get(clean_target, impersonate="chrome120", headers=HEADERS, allow_redirects=True, timeout=20)
        if res.status_code != 200:
            logger.error(f"JioMart HTTP {res.status_code} for {clean_target}")
            return None

        soup = BeautifulSoup(res.text, "html.parser")
        title, price, img_url, item_id = None, None, None, None

        # 1. Check JSON-LD Product schema
        for s in soup.find_all("script", type="application/ld+json"):
            try:
                d = json.loads(s.string)
                if isinstance(d, dict) and d.get("@type") == "Product":
                    if not title and d.get("name"):
                        title = d.get("name")
                    if not img_url and d.get("image"):
                        img = d.get("image")
                        img_url = img[0] if isinstance(img, list) else img
            except Exception:
                pass

        # 2. Check window.APP_DATA Redux state
        idx = res.text.find("window.APP_DATA")
        if idx != -1:
            brace_start = res.text.find("{", idx)
            depth = 0
            json_str = None
            for i in range(brace_start, len(res.text)):
                if res.text[i] == "{":
                    depth += 1
                elif res.text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        json_str = res.text[brace_start:i+1]
                        break
            if json_str:
                cleaned = re.sub(r':\s*undefined\b', ':null', json_str)
                try:
                    data = json.loads(cleaned)
                    pd = data.get("reduxData", {}).get("catalog", {}).get("product_details", {})
                    if not title and pd.get("name"):
                        title = pd.get("name")
                    if not item_id and pd.get("item_code"):
                        item_id = str(pd.get("item_code"))
                    if not img_url and pd.get("medias"):
                        img_url = pd["medias"][0].get("url")
                except Exception:
                    pass

        # 3. Extract Price: look for price-rrp (selling price) or price-mrp
        rrp_match = re.search(r'"price-rrp"\s*:\s*"(\d+(?:\.\d+)?)"', res.text)
        if rrp_match:
            price = float(rrp_match.group(1))
        else:
            mrp_match = re.search(r'"price-mrp"\s*:\s*"(\d+(?:\.\d+)?)"', res.text)
            if mrp_match:
                price = float(mrp_match.group(1))

        # Fallback Title from HTML
        if not title:
            if soup.title and soup.title.string:
                title = soup.title.string.replace("Online at Best Prices in India - JioMart", "").replace("Buy ", "").strip()
            og_t = soup.find("meta", property="og:title")
            if og_t:
                title = og_t.get("content", "").strip()

        # Fallback item ID from URL
        if not item_id:
            m = re.search(r"-(\d+)(?:[/?]|$)", clean_target) or re.search(r"/(\d+)(?:[/?]|$)", clean_target)
            item_id = m.group(1) if m else "JIOMART_ITEM"

        if not title or price is None:
            logger.warning(f"Could not extract JioMart title or price for {clean_target}")
            return None

        return {
            "platform": "JioMart",
            "platform_badge": "🟢 JioMart",
            "item_id": item_id,
            "title": title,
            "price": round(price, 2),
            "currency": "₹",
            "url": res.url,
            "image_url": img_url,
        }
    except Exception as e:
        logger.error(f"Error scraping JioMart: {e}")
        return None


# =====================================================================
# 4. Reliance Digital Scraper
# =====================================================================

def fetch_reliancedigital_product(url: str) -> Optional[Dict[str, Any]]:
    """Fetch live product details from Reliance Digital."""
    clean_target = clean_url_from_text(url)
    try:
        res = requests.get(clean_target, impersonate="chrome120", headers=HEADERS, allow_redirects=True, timeout=20)
        if res.status_code != 200:
            logger.error(f"Reliance Digital HTTP {res.status_code} for {clean_target}")
            return None

        title, price, img_url, item_id = None, None, None, None

        idx = res.text.find("window.__INITIAL_STATE__")
        if idx != -1:
            brace_start = res.text.find("{", idx)
            depth = 0
            state_str = None
            for j in range(brace_start, len(res.text)):
                if res.text[j] == "{":
                    depth += 1
                elif res.text[j] == "}":
                    depth -= 1
                    if depth == 0:
                        state_str = res.text[brace_start:j+1]
                        break
            if state_str:
                cleaned = re.sub(r':\s*undefined\b', ':null', state_str)
                state = json.loads(cleaned)
                pdp = state.get("productDetailsPage", {})
                prod = pdp.get("product", {})
                title = prod.get("name")
                item_id = str(prod.get("item_code", ""))
                if prod.get("medias"):
                    img_url = prod["medias"][0].get("url")

                meta_price = pdp.get("product_meta", {}).get("price", {})
                if meta_price:
                    eff = meta_price.get("effective", {}) or meta_price.get("selling", {}) or meta_price.get("marked", {})
                    if eff and "min" in eff:
                        price = float(eff["min"])

        # Fallbacks
        if not item_id:
            m = re.search(r"/p/(\d+)", clean_target)
            item_id = m.group(1) if m else "RD_ITEM"

        if not title:
            soup = BeautifulSoup(res.text, "html.parser")
            if soup.title and "Reliance Digital" in soup.title.string:
                title = soup.title.string.split("-")[0].strip()

        if not title or price is None:
            logger.warning(f"Could not extract Reliance Digital details for {clean_target}")
            return None

        return {
            "platform": "RelianceDigital",
            "platform_badge": "🔴 Reliance Digital",
            "item_id": item_id,
            "title": title,
            "price": round(price, 2),
            "currency": "₹",
            "url": res.url,
            "image_url": img_url,
        }
    except Exception as e:
        logger.error(f"Error scraping Reliance Digital: {e}")
        return None


# =====================================================================
# 5. Croma Scraper
# =====================================================================

def fetch_croma_product(url: str) -> Optional[Dict[str, Any]]:
    """Fetch live product details from Croma."""
    clean_target = clean_url_from_text(url)
    try:
        res = requests.get(clean_target, impersonate="chrome120", headers=HEADERS, allow_redirects=True, timeout=20)
        if res.status_code != 200:
            logger.error(f"Croma HTTP {res.status_code} for {clean_target}")
            return None

        title, price, img_url, item_id = None, None, None, None

        idx = res.text.find("window.__INITIAL_DATA__=")
        if idx != -1:
            brace_start = res.text.find("{", idx)
            depth = 0
            json_str = None
            for i in range(brace_start, len(res.text)):
                if res.text[i] == "{":
                    depth += 1
                elif res.text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        json_str = res.text[brace_start:i+1]
                        break
            if json_str:
                cleaned = re.sub(r':\s*undefined\b', ':null', json_str)
                d = json.loads(cleaned)
                pdp = d.get("pdpReducer", {}).get("pdpData", {})
                title = pdp.get("name")
                item_id = str(pdp.get("code", ""))
                images = pdp.get("imageInfo", [])
                if images:
                    img_url = images[0].get("url")

                price_data = d.get("pdpPriceReducer", {}).get("pdpPriceData", {})
                sp = price_data.get("sellingPrice", {}).get("value") or price_data.get("mrp", {}).get("value")
                if sp:
                    price = float(sp)

        if not item_id:
            m = re.search(r"/p/(\d+)", clean_target)
            item_id = m.group(1) if m else "CROMA_ITEM"

        if not title or price is None:
            logger.warning(f"Could not extract Croma details for {clean_target}")
            return None

        return {
            "platform": "Croma",
            "platform_badge": "⚪ Croma",
            "item_id": item_id,
            "title": title,
            "price": round(price, 2),
            "currency": "₹",
            "url": res.url,
            "image_url": img_url,
        }
    except Exception as e:
        logger.error(f"Error scraping Croma: {e}")
        return None


# =====================================================================
# 6. Samsung India Scraper
# =====================================================================

def fetch_samsung_product(url: str) -> Optional[Dict[str, Any]]:
    """Fetch live product details from Samsung India."""
    clean_target = clean_url_from_text(url)
    try:
        res = requests.get(clean_target, impersonate="chrome120", headers=HEADERS, allow_redirects=True, timeout=20)
        if res.status_code != 200:
            logger.error(f"Samsung HTTP {res.status_code} for {clean_target}")
            return None

        soup = BeautifulSoup(res.text, "html.parser")
        title, price, img_url, item_id = None, None, None, None

        # Check JSON-LD
        for s in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(s.string)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    t = item.get("@type")
                    if t == "Product":
                        if not title:
                            title = item.get("name")
                        if not img_url:
                            img = item.get("image")
                            img_url = img[0] if isinstance(img, list) else img
                        if not price and "offers" in item:
                            offers = item.get("offers", {})
                            p_val = offers.get("price")
                            if p_val:
                                price = float(str(p_val).replace(",", ""))
                    elif t == "ProductGroup":
                        if not title:
                            title = item.get("name")
                        variants = item.get("hasVariant", [])
                        if variants:
                            v0 = variants[0]
                            if not img_url:
                                img = v0.get("image")
                                if img and img.startswith("//"):
                                    img = "https:" + img
                                img_url = img
                            if not item_id:
                                item_id = v0.get("sku")
            except Exception:
                pass

        # Fallback price from regex if not in JSON-LD
        if price is None:
            m = re.findall(r"₹\s*([\d,]+)", res.text)
            if m:
                for cand in m:
                    val = float(cand.replace(",", ""))
                    if val > 500:
                        price = val
                        break

        # Fallback item_id from URL
        if not item_id:
            m = re.search(r"sm-[a-z0-9]+", clean_target, re.IGNORECASE)
            if m:
                item_id = m.group(0).upper()
            else:
                parts = [p for p in clean_target.rstrip("/").split("/") if p]
                item_id = parts[-1] if parts else "SAMSUNG_ITEM"

        # Fallback title
        if not title:
            if soup.title and soup.title.string:
                title = soup.title.string.split("|")[0].replace("Buy", "").strip()

        if not title or price is None:
            logger.warning(f"Could not extract Samsung details for {clean_target}")
            return None

        return {
            "platform": "Samsung",
            "platform_badge": "🌌 Samsung",
            "item_id": item_id,
            "title": title,
            "price": round(price, 2),
            "currency": "₹",
            "url": res.url,
            "image_url": img_url,
        }
    except Exception as e:
        logger.error(f"Error scraping Samsung: {e}")
        return None


# =====================================================================
# Unified Fetcher
# =====================================================================

def fetch_product(url_or_text: str) -> Optional[Dict[str, Any]]:
    """Automatically detect platform and fetch live product details."""
    clean_target = clean_url_from_text(url_or_text)
    platform = detect_platform(clean_target)

    if platform == "RelianceDigital":
        return fetch_reliancedigital_product(clean_target)
    elif platform == "Croma":
        return fetch_croma_product(clean_target)
    elif platform == "JioMart":
        return fetch_jiomart_product(clean_target)
    elif platform == "Samsung":
        return fetch_samsung_product(clean_target)
    elif platform == "Flipkart":
        return fetch_flipkart_product(clean_target)
    elif platform == "Amazon":
        return fetch_amazon_product(clean_target)
    else:
        # Fallback cascade across supported platforms
        for fetcher in [
            fetch_amazon_product,
            fetch_flipkart_product,
            fetch_jiomart_product,
            fetch_reliancedigital_product,
            fetch_croma_product,
            fetch_samsung_product,
        ]:
            res = fetcher(clean_target)
            if res:
                return res
        return None
