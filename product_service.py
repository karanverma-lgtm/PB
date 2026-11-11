"""Product Scraping & Price Extraction Service for Indian & Global E-Commerce.

Supports 6 major platforms:
1. Amazon (amazon.in, amazon.com, amzn.to, amzn.in)
2. Flipkart (flipkart.com, dl.flipkart.com)
3. JioMart (jiomart.com)
4. Reliance Digital (reliancedigital.in)
5. Croma (croma.com)
6. Samsung India (samsung.com/in)

Uses curl_cffi for realistic browser TLS fingerprinting, location cookies,
and robust selector cascading to reliably extract live prices, titles, images, and item IDs.
"""

import json
import re
import time
import logging
import threading
import urllib.request
from typing import Optional, Dict, Any, List
from curl_cffi import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Camoufox stealth browser integration (C++ engine level anti-bot bypass)
try:
    from camoufox.sync_api import Camoufox
    CAMOUFOX_AVAILABLE = True
except Exception:
    CAMOUFOX_AVAILABLE = False

# Global lock to ensure only 1 Camoufox headless browser instance runs at a time (prevents OOM on 512MB RAM)
_CAMOUFOX_LOCK = threading.Lock()


def fetch_page_with_camoufox(url: str, timeout_ms: int = 25000) -> Optional[str]:
    """Render full dynamic JavaScript page using Camoufox stealth browser with single-instance memory protection."""
    if not CAMOUFOX_AVAILABLE:
        return None

    # Acquire lock without blocking indefinitely to prevent process hangs
    if not _CAMOUFOX_LOCK.acquire(timeout=30.0):
        logger.warning(f"Camoufox lock busy, skipping browser fetch for {url[:50]}")
        return None

    try:
        logger.info(f"🦊 Invoking Camoufox stealth browser for {url[:60]}...")
        with Camoufox(headless=True, humanize=True) as browser:
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(2000)
            rendered = page.content()
            if rendered and len(rendered) > 500:
                return rendered
    except Exception as e:
        logger.debug(f"Camoufox stealth fetch failed for {url[:60]}: {e}")
    finally:
        _CAMOUFOX_LOCK.release()
    return None

# Default realistic browser headers with metro pincode cookies for Indian e-commerce
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
    "Cookie": "pincode=400001; delivery_pincode=400001; pin=400001; _pincode=400001; city=Mumbai",
}

# Dedicated clean browser headers for Amazon (no Indian pincode cookies that trigger bot WAF)
AMAZON_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8,hi;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
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

def resolve_amazon_short_url(target: str) -> str:
    """Resolve Amazon short URLs (amzn.in, amzn.to, /d/ links) without triggering full page blocks."""
    clean = clean_url_from_text(target)
    if not any(k in clean.lower() for k in ["amzn.to", "amzn.in", "bit.ly", "tinyurl.com"]):
        return clean

    # Method 1: Fast HTTP redirect check with curl_cffi (allow_redirects=False)
    try:
        r = requests.get(
            clean,
            impersonate="chrome120",
            headers={"User-Agent": AMAZON_HEADERS["User-Agent"]},
            allow_redirects=False,
            timeout=8,
        )
        loc = r.headers.get("Location") or r.headers.get("location")
        if loc:
            return loc
    except Exception as e:
        logger.debug(f"curl_cffi short url check failed: {e}")

    # Method 2: Standard urllib redirect handler (avoids page download / anti-bot gates)
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    try:
        opener = urllib.request.build_opener(_NoRedirect)
        req = urllib.request.Request(
            clean,
            headers={"User-Agent": AMAZON_HEADERS["User-Agent"]},
        )
        resp = opener.open(req, timeout=8)
        loc = resp.headers.get("Location")
        if loc:
            return loc
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location")
        if loc:
            return loc
    except Exception as e:
        logger.debug(f"urllib short url check failed: {e}")

    # Method 3: Fallback with allow_redirects=True
    try:
        r = requests.get(
            clean,
            impersonate="chrome120",
            headers=AMAZON_HEADERS,
            allow_redirects=True,
            timeout=12,
        )
        if r.url and r.url != clean:
            return r.url
    except Exception as e:
        logger.debug(f"curl_cffi full redirect failed: {e}")

    return clean


def extract_amazon_asin(text: str) -> Optional[str]:
    """Extract 10-character Amazon Standard Identification Number (ASIN)."""
    clean = clean_url_from_text(text)
    if re.match(r"^[A-Z0-9]{10}$", clean, re.IGNORECASE):
        return clean.upper()

    # Try resolving short links if present
    if any(k in clean.lower() for k in ["amzn.to", "amzn.in"]):
        clean = resolve_amazon_short_url(clean)

    patterns = [
        r"/dp/([A-Z0-9]{10})",
        r"/gp/product/([A-Z0-9]{10})",
        r"/product/([A-Z0-9]{10})",
        r"/gp/aw/d/([A-Z0-9]{10})",
        r"/d/([A-Z0-9]{10})",
        r"[?&]asin=([A-Z0-9]{10})",
        r"[?&]pd_rd_i=([A-Z0-9]{10})",
        r"/([A-Z0-9]{10})(?:[/?&]|$)",
    ]
    for p in patterns:
        m = re.search(p, clean, re.IGNORECASE)
        if m:
            candidate = m.group(1).upper()
            if candidate not in ["PRODUCT", "BUYING"]:
                return candidate
    return None


def parse_amazon_soup(soup: BeautifulSoup, asin: str, canonical_url: str) -> Optional[Dict[str, Any]]:
    """Parse product title, price, currency, and image from Amazon HTML BeautifulSoup."""
    title = None
    for t_sel in ["span#productTitle", "h1#title", "span#title", "h1.a-size-large"]:
        elem = soup.select_one(t_sel)
        if elem and elem.get_text(strip=True):
            title = elem.get_text(strip=True)
            break

    if not title:
        og_title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "title"})
        if og_title and og_title.get("content"):
            title = og_title.get("content").replace("Amazon.in:", "").replace("Amazon.com:", "").strip()

    if not title and soup.title:
        raw_t = soup.title.get_text(strip=True)
        if raw_t and "Robot Check" not in raw_t and "Page Not Found" not in raw_t:
            title = raw_t.replace("Amazon.in:", "").replace("Amazon.com:", "").strip()

    if not title:
        return None

    # Price Extraction
    price = None
    currency = "₹" if "amazon.in" in canonical_url else "$"

    # Whole + Fraction
    price_whole = soup.find("span", class_="a-price-whole")
    price_fraction = soup.find("span", class_="a-price-fraction")
    if price_whole:
        p_str = price_whole.get_text(strip=True).replace(",", "").replace(".", "").strip()
        if p_str.isdigit():
            frac = price_fraction.get_text(strip=True) if price_fraction else "00"
            frac = frac if frac.isdigit() else "00"
            price = float(f"{p_str}.{frac}")

    # Selectors fallback
    if price is None:
        for selector in [
            "span.priceToPay span.a-offscreen",
            "span.apexPriceToPay span.a-offscreen",
            "div#corePrice_desktop span.a-price-whole",
            "div#corePrice_mobile_feature_div span.a-price-whole",
            "div#corePriceDisplay_desktop_feature_div span.a-price-whole",
            "span.a-price.a-text-price span.a-offscreen",
            "span#priceblock_ourprice",
            "span#priceblock_dealprice",
            "span#priceblock_saleprice",
            "span.a-price span.a-offscreen",
            "span.a-color-price",
        ]:
            elem = soup.select_one(selector)
            if elem:
                txt = elem.get_text(strip=True)
                match = re.search(r"[\d,]+(?:\.\d+)?", txt)
                if match:
                    val = float(match.group(0).replace(",", ""))
                    if val > 0:
                        price = val
                        break

    # Hidden inputs / data attributes fallback
    if price is None:
        for input_name in ["displayedPrice", "items[0][price]", "twister-plus-price-data"]:
            inp = soup.find("input", attrs={"name": input_name})
            if inp and inp.get("value"):
                m = re.search(r"[\d,]+(?:\.\d+)?", inp.get("value"))
                if m:
                    val = float(m.group(0).replace(",", ""))
                    if val > 0:
                        price = val
                        break

    # Buybox regex search fallback
    if price is None:
        price_div = soup.find("div", id=re.compile(r"corePrice|apex_desktop|desktop_unifiedPrice|buybox|mobile_unifiedPrice"))
        if price_div:
            matches = re.findall(r"[₹\$]\s*([\d,]+(?:\.\d+)?)", price_div.get_text())
            if matches:
                val = float(matches[0].replace(",", ""))
                if val > 0:
                    price = val

    if price is None:
        return None

    # Currency symbol
    sym_elem = soup.find("span", class_="a-price-symbol")
    if sym_elem and sym_elem.get_text(strip=True):
        currency = sym_elem.get_text(strip=True)

    # Image extraction
    img_elem = soup.find("img", id="landingImage") or soup.find("img", id="imgBlkFront") or soup.find("img", id="main-image")
    img_url = img_elem.get("src") if img_elem else None
    if not img_url:
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            img_url = og_img.get("content")

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


def fetch_amazon_product(url_or_asin: str) -> Optional[Dict[str, Any]]:
    """Fetch live product details from Amazon with buy-box verification and Camoufox stealth escalation."""
    clean_target = clean_url_from_text(url_or_asin)
    try:
        # Resolve short link (amzn.in or amzn.to)
        if any(k in clean_target.lower() for k in ["amzn.to", "amzn.in"]):
            clean_target = resolve_amazon_short_url(clean_target)

        asin = extract_amazon_asin(clean_target)
        if not asin:
            logger.error(f"Could not extract ASIN from {clean_target}")
            return None

        domain = "amazon.com" if "amazon.com" in clean_target.lower() else "amazon.in"
        canonical_url = f"https://www.{domain}/dp/{asin}"
        mobile_url = f"https://www.{domain}/gp/aw/d/{asin}"

        res = None
        # 1. Primary: Try desktop and mobile endpoints with fast TLS browser impersonations
        fetch_attempts = [
            (canonical_url, "chrome124", AMAZON_HEADERS),
            (mobile_url, "chrome120", AMAZON_HEADERS),
            (canonical_url, "safari17_0", None),
            (mobile_url, "safari15_5", None),
        ]

        for target_url, imp, hdrs in fetch_attempts:
            try:
                r = requests.get(target_url, impersonate=imp, headers=hdrs, timeout=15)
                if r.status_code == 200:
                    if "api-services-support@amazon.com" in r.text or "validateCaptcha" in r.text:
                        logger.warning(f"Amazon CAPTCHA on {target_url} ({imp}), trying next profile...")
                        continue
                    res = r
                    break
                elif r.status_code in [429, 503]:
                    time.sleep(1.0)
            except Exception as req_err:
                logger.debug(f"Attempt failed for {target_url} ({imp}): {req_err}")
                time.sleep(0.5)

        # Parse with BeautifulSoup if curl_cffi succeeded
        if res and res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            parsed = parse_amazon_soup(soup, asin, canonical_url)
            if parsed:
                return parsed

        # 2. Automated Secondary Fallback: Camoufox stealth browser (bypasses WAF & solves challenges)
        if CAMOUFOX_AVAILABLE:
            logger.info(f"curl_cffi blocked or incomplete for Amazon ({asin}). Escalating to Camoufox stealth browser...")
            for cam_target in [canonical_url, mobile_url]:
                cam_html = fetch_page_with_camoufox(cam_target)
                if cam_html:
                    soup = BeautifulSoup(cam_html, "html.parser")
                    parsed = parse_amazon_soup(soup, asin, canonical_url)
                    if parsed:
                        logger.info(f"✅ Camoufox successfully resolved Amazon product #{asin}!")
                        return parsed

        logger.error(f"Could not extract Amazon details for ASIN {asin} across all engines")
        return None
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


def parse_flipkart_soup(soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
    """Parse product title, price, currency, image, and item ID from Flipkart HTML."""
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

    if not title and soup.title:
        title = soup.title.get_text(strip=True).replace("Online at Best Price in India - Flipkart", "").strip()

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
            if any(w in p_text.lower() for w in ["protect", "fee", "emi", "buy at", "pay", "off"]):
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
    img_matches = re.findall(r"https://rukminim\d*\.flixcart\.com/image/[^\"\'\s]+", str(soup))
    if img_matches:
        img_url = img_matches[0]

    item_id = extract_flipkart_id(url)

    return {
        "platform": "Flipkart",
        "platform_badge": "🛍️ Flipkart",
        "item_id": item_id,
        "title": title,
        "price": round(price, 2),
        "currency": "₹",
        "url": url,
        "image_url": img_url,
    }


def fetch_flipkart_product(url: str) -> Optional[Dict[str, Any]]:
    """Fetch live product details from Flipkart with Camoufox stealth escalation."""
    clean_target = clean_url_from_text(url)
    try:
        # 1. Primary: Fast TLS curl_cffi fetch
        res = requests.get(clean_target, impersonate="chrome120", headers=HEADERS, allow_redirects=True, timeout=20)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            parsed = parse_flipkart_soup(soup, res.url)
            if parsed:
                return parsed

        # 2. Automated Secondary Fallback: Camoufox stealth browser
        if CAMOUFOX_AVAILABLE:
            logger.info(f"curl_cffi failed on Flipkart. Escalating to Camoufox stealth browser...")
            cam_html = fetch_page_with_camoufox(clean_target)
            if cam_html:
                soup = BeautifulSoup(cam_html, "html.parser")
                parsed = parse_flipkart_soup(soup, clean_target)
                if parsed:
                    logger.info(f"✅ Camoufox successfully resolved Flipkart product!")
                    return parsed

        logger.error(f"Could not extract Flipkart details for {clean_target}")
        return None
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
    """Fetch live product details from Samsung India with variant resolution."""
    clean_target = clean_url_from_text(url)
    try:
        res = requests.get(clean_target, impersonate="chrome120", headers=HEADERS, allow_redirects=True, timeout=20)
        if res.status_code != 200:
            logger.error(f"Samsung HTTP {res.status_code} for {clean_target}")
            return None

        soup = BeautifulSoup(res.text, "html.parser")
        title, price, img_url, item_id = None, None, None, None

        # Check for requested variant SKU in URL (e.g. ?SM-S928... or sm-s928...)
        url_sku_match = re.search(r"sm-[a-z0-9]+", clean_target, re.IGNORECASE)
        target_sku = url_sku_match.group(0).upper() if url_sku_match else None

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
                            # Try to match the exact SKU from the URL if specified
                            chosen_variant = variants[0]
                            if target_sku:
                                for v in variants:
                                    if v.get("sku") and target_sku in v.get("sku").upper():
                                        chosen_variant = v
                                        break
                            if not img_url:
                                img = chosen_variant.get("image")
                                if img and img.startswith("//"):
                                    img = "https:" + img
                                img_url = img
                            if not item_id:
                                item_id = chosen_variant.get("sku")
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
            if target_sku:
                item_id = target_sku
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
