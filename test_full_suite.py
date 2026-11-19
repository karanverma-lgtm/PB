"""Comprehensive Test Suite for 6-Platform Price Tracker Bot.

Tests:
1. Platform detection for Amazon, Flipkart, JioMart, Reliance Digital, Croma, Samsung.
2. Live fetching of product details across all 6 platforms.
3. Database insertion, tracking, and retrieval with platform icons.
"""

import sys
import os
import database
import product_service

def run_tests():
    print("=" * 60)
    print("🧪 RUNNING COMPREHENSIVE MULTI-PLATFORM TEST SUITE")
    print("=" * 60)

    # 1. Test Platform Detection
    detection_cases = [
        ("https://www.amazon.in/dp/B09G9BL5CP", "Amazon"),
        ("https://amzn.to/3xyz", "Amazon"),
        ("https://amzn.in/d/0gl6MyWv", "Amazon"),
        ("B09G9BL5CP", "Amazon"),
        ("https://www.flipkart.com/apple-iphone-15/p/itm6ac6485515ae4", "Flipkart"),
        ("https://dl.flipkart.com/s/12345", "Flipkart"),
        ("https://www.myntra.com/tshirts/roadster/roadster-men-black-pure-cotton-t-shirt/2127874/buy", "Myntra"),
        ("https://www.nykaa.com/blue-heaven-walkfree-kajal-roll-on/p/821979", "Nykaa"),
        ("https://www.nykaafashion.com/mabish-by-sonal-jain-blue-cotton-sleeveless-co-ord-set/p/25761772", "Nykaa"),
        ("https://www.tirabeauty.com/product/wishcare-niacinamide-oil-balance-fluid-sunscreen-snap-pack-sachet-10-pcs-16927317", "Tira"),
        ("https://www.meesho.com/chuchumama-baby-diaper-pants-l-9-14-kg-pack-of-1-50-pieces-anti-lock-gel-technology-upto-12-hours-protection/p/1izwjr", "Meesho"),
        ("https://sharein.savana.com/db/details/1955712", "Savana"),
        ("https://in.savana.com/details/1955712", "Savana"),
        ("https://www.jiomart.com/product/apple-iphone-15-128gb-blue-mhxt4j-17504497", "JioMart"),
        ("https://www.reliancedigital.in/apple-iphone-15-128gb-black/p/493839309", "RelianceDigital"),
        ("https://www.croma.com/apple-iphone-15-128gb-black-/p/300652", "Croma"),
        ("https://www.samsung.com/in/smartphones/galaxy-s/galaxy-s26-fe-pistachio-256gb-sm-s741blgcins/", "Samsung"),
    ]

    print("\n🔍 1. Platform Detection Tests (11 Platforms):")
    for url, expected in detection_cases:
        detected = product_service.detect_platform(url)
        assert detected == expected, f"Expected {expected}, got {detected} for {url}"
        print(f"  ✅ {expected.ljust(16)} ➔ {url[:45]}...")

    # 2. Live Product Fetching across all 11 platforms
    live_targets = [
        ("Amazon", "https://www.amazon.in/dp/B09G9BL5CP"),
        ("Flipkart", "https://www.flipkart.com/apple-iphone-15-black-128-gb/p/itm6ac6485515ae4"),
        ("Flipkart Short Link", "https://dl.flipkart.com/s/fNh4ycuuuN"),
        ("Myntra", "https://www.myntra.com/tshirts/roadster/roadster-men-black-pure-cotton-t-shirt/2127874/buy"),
        ("Nykaa", "https://www.nykaa.com/blue-heaven-walkfree-kajal-roll-on/p/821979"),
        ("Nykaa Fashion", "https://www.nykaafashion.com/mabish-by-sonal-jain-blue-cotton-sleeveless-co-ord-set/p/25761772"),
        ("Tira Beauty", "https://www.tirabeauty.com/product/wishcare-niacinamide-oil-balance-fluid-sunscreen-snap-pack-sachet-10-pcs-16927317"),
        ("Savana", "https://sharein.savana.com/db/details/1955712?ub_cl=in_en-IN&vid=16"),
        ("Meesho", "https://www.meesho.com/chuchumama-baby-diaper-pants-l-9-14-kg-pack-of-1-50-pieces-anti-lock-gel-technology-upto-12-hours-protection/p/1izwjr"),
        ("Croma", "https://www.croma.com/apple-iphone-15-128gb-black-/p/300652"),
        ("Reliance Digital", "https://www.reliancedigital.in/apple-iphone-15-128gb-black/p/493839309"),
        ("JioMart", "https://www.jiomart.com/product/apple-iphone-15-128gb-blue-mhxt4j-17504497"),
        ("Samsung India", "https://www.samsung.com/in/smartphones/galaxy-s/galaxy-s26-fe-pistachio-256gb-sm-s741blgcins/"),
    ]

    print("\n🌐 2. Live Scraper Verification Across 11 Platforms:")
    fetched_products = []
    for platform_name, target_url in live_targets:
        print(f"\n  Fetching [{platform_name}]...")
        prod = product_service.fetch_product(target_url)
        if not prod:
            print(f"  ❌ FAILED to fetch {platform_name} from {target_url}")
            sys.exit(1)

        assert prod["title"], "Missing title"
        assert prod["item_id"], "Missing item_id"
        assert prod["currency"] in ["₹", "$"], f"Unexpected currency {prod['currency']}"
        assert "in_stock" in prod and isinstance(prod["in_stock"], bool), "Missing or invalid in_stock status"
        assert "price" in prod and prod["price"] >= 0, f"Invalid price {prod['price']}"
        assert "offers" in prod and isinstance(prod["offers"], list), "Missing or invalid offers list"

        print(f"  ✅ {prod['platform_badge']} ({prod['platform']})")
        print(f"     Title: {prod['title'][:55]}...")
        print(f"     Price: {prod['currency']}{prod['price']:,.2f}")
        print(f"     Stock: {'🟢 In Stock' if prod['in_stock'] else '❌ Out of Stock'}")
        print(f"     Item ID: {prod['item_id']}")
        if prod["offers"]:
            print(f"     Offers ({len(prod['offers'])}): {prod['offers'][0][:75]}")
        fetched_products.append(prod)

    # 3. Stock Status & Availability Parsing Unit Tests
    print("\n📦 3. Stock Status Detection Tests (Synthetic & HTML):")
    from bs4 import BeautifulSoup

    # Amazon OOS Soup
    amz_oos_html = '<html><body><span id="productTitle">Sony WH-1000XM5</span><div id="availability"><span class="a-color-price">Currently unavailable.</span></div></body></html>'
    amz_parsed = product_service.parse_amazon_soup(BeautifulSoup(amz_oos_html, "html.parser"), "B09XS7JWHH", "https://amazon.in/dp/B09XS7JWHH")
    assert amz_parsed is not None, "Failed to parse Amazon OOS soup"
    assert amz_parsed["in_stock"] is False, f"Expected in_stock=False, got {amz_parsed['in_stock']}"
    print("  ✅ Amazon Out-of-Stock detected correctly from 'Currently unavailable'.")

    # Flipkart OOS Soup
    fk_oos_html = '<html><head><title>Pixel 8 Pro - Flipkart</title></head><body><span class="VU-ZEz">Google Pixel 8 Pro</span><div>CURRENTLY OUT OF STOCK</div><button>NOTIFY ME</button></body></html>'
    fk_parsed = product_service.parse_flipkart_soup(BeautifulSoup(fk_oos_html, "html.parser"), "https://flipkart.com/p/itm123")
    assert fk_parsed is not None, "Failed to parse Flipkart OOS soup"
    assert fk_parsed["in_stock"] is False, f"Expected in_stock=False, got {fk_parsed['in_stock']}"
    print("  ✅ Flipkart Out-of-Stock detected correctly from 'NOTIFY ME' / 'CURRENTLY OUT OF STOCK'.")

    # 3b. Bank / Credit Card / Coupon Offer Extraction Unit Tests
    print("\n💳 3b. Offer & Credit Card Discount Extraction Tests:")
    import bot

    amz_offer_html = """
    <html><body>
      <span id="productTitle">Apple iPhone 15</span>
      <span class="a-price-whole">59,900</span>
      <span id="couponBadgeRegularVpc">Apply ₹1,000 coupon Terms</span>
      <div id="itembox-InstantBankDiscount">
        <span class="offers-items-title">Bank Offer</span>
        <span class="offers-items-content">Upto ₹1,849.75 discount on Axis Bank Credit Cards 1 offer</span>
      </div>
      <div id="itembox-GCCashback">
        <span class="offers-items-title">Cashback</span>
        <span class="offers-items-content">Upto ₹2,219.00 cashback on Amazon Pay ICICI Credit Cards</span>
      </div>
    </body></html>
    """
    amz_offers = product_service.extract_amazon_offers(BeautifulSoup(amz_offer_html, "html.parser"))
    assert len(amz_offers) == 3, f"Expected 3 Amazon offers, got {amz_offers}"
    assert "Axis Bank Credit Cards" in amz_offers[1] and "1 offer" not in amz_offers[1], f"Unexpected Amazon bank offer: {amz_offers[1]}"
    print(f"  ✅ Amazon offer extraction verified ({len(amz_offers)} offers: coupon, bank, cashback).")

    fk_offer_html = (
        '<html><body><script>{"type":"NepOffers","offerTitle":"Flipkart Axis","offerSubTitleRC":{"value":{"contentList":[{"contentValue":"Credit Card"}]}},"discountedPriceText":"₹2,995 off"}'
        '{"type":"NepOffers","offerTitle":"Flipkart SBI","offerSubTitleRC":{"value":{"contentList":[{"contentValue":"Credit Card"}]}},"discountedPriceText":"₹2,995 off"}'
        '{"type":"NepOffers","offerTitle":"Zero Placeholder","discountedPriceText":"₹0 off"}</script></body></html>'
    )
    fk_offers = product_service.extract_flipkart_offers(BeautifulSoup(fk_offer_html, "html.parser"), fk_offer_html)
    assert len(fk_offers) == 2, f"Expected 2 Flipkart offers, got {fk_offers}"
    assert "Flipkart Axis (Credit Card): ₹2,995 off" == fk_offers[0], f"Unexpected Flipkart offer: {fk_offers[0]}"
    print(f"  ✅ Flipkart NepOffers extraction verified ({len(fk_offers)} bank/card offers).")

    croma_pdp = {
        "discount": "12%",
        "storeoffer": [
            {"toDate": "2024-04-27T11:59:00+0530", "storeOfferLabel": "Expired Offer"},
            {"toDate": "2029-12-31T23:59:09+0530", "storeOfferLabel": "Note:", "productLabel": "<html>Bulk purchase disclaimer</html>"},
            {"toDate": "2029-12-31T23:59:09+0530", "storeOfferLabel": "HDFC Credit Card Instant ₹3,000 Off"},
        ],
    }
    croma_offers = product_service.extract_croma_offers(croma_pdp)
    assert len(croma_offers) == 2 and "HDFC Credit Card Instant ₹3,000 Off" in croma_offers, f"Unexpected Croma offers: {croma_offers}"
    print(f"  ✅ Croma offer filtering verified (expired & disclaimer notes excluded).")

    formatted_block = bot.format_offers_block(amz_offers)
    assert "💳 <b>Available Offers:</b>" in formatted_block and "Axis Bank Credit Cards" in formatted_block
    msg_with, kb_with = bot.build_offers_message(
        {"platform": "Amazon", "platform_badge": "📦 Amazon", "title": "Apple iPhone 15", "price": 59900.0, "currency": "₹", "url": "https://www.amazon.in/dp/B0CHX2F5QT", "in_stock": True, "offers": amz_offers},
        "110001",
    )
    assert "Available Bank & Card Offers (3)" in msg_with and kb_with is not None
    msg_empty, _ = bot.build_offers_message(
        {"platform": "Savana", "platform_badge": "👗 Savana", "title": "Retro Sunglasses", "price": 390.0, "currency": "₹", "url": "https://in.savana.com/details/1955712", "in_stock": True, "offers": []},
        "110001",
    )
    assert "No bank, credit card, or coupon offers" in msg_empty
    print("  ✅ Telegram HTML offer block & /offers command formatting verified.")

    # 4. Database Integration Test
    print("\n💾 4. Database Integration & Stock Transition Tests:")
    database.init_db()
    test_user_id = 999888777
    database.clear_user_products(test_user_id)

    # Test Pincode functionality
    database.set_user_pincode(test_user_id, "560001")
    user_pin = database.get_user_pincode(test_user_id)
    assert user_pin == "560001", f"Expected pincode 560001, got {user_pin}"
    print("  ✅ User delivery PIN code storage & retrieval verified (560001).")

    # Test pending product caching across restarts with in_stock and offers
    sample_prod = dict(fetched_products[0])
    sample_prod["offers"] = ["Bank Offer: ₹1,500 off on HDFC Credit Card"]
    database.save_pending_product(sample_prod)
    cached = database.get_pending_product(sample_prod["item_id"])
    assert cached is not None, "Pending product was not saved"
    assert cached["item_id"] == sample_prod["item_id"], "Mismatch in pending product item_id"
    assert "in_stock" in cached and isinstance(cached["in_stock"], bool), "Missing in_stock in cached pending product"
    assert cached.get("offers") == sample_prod["offers"], f"Pending offers not persisted: {cached.get('offers')}"
    print("  ✅ Pending product caching with stock status & offers verified (survives bot restarts).")

    inserted_ids = []
    for prod in fetched_products:
        pid = database.add_tracked_product(
            user_id=test_user_id,
            chat_id=test_user_id,
            platform=prod["platform"],
            item_id=prod["item_id"],
            title=prod["title"],
            url=prod["url"],
            image_url=prod.get("image_url"),
            target_price=prod["price"] * 0.9,
            current_price=prod["price"],
            currency=prod["currency"],
            pincode=user_pin,
            is_in_stock=prod.get("in_stock", True),
        )
        inserted_ids.append(pid)

    stored = database.get_user_products(test_user_id)
    assert len(stored) == len(fetched_products), f"Expected {len(fetched_products)} items, got {len(stored)}"
    assert stored[0]["pincode"] == "560001", f"Expected stored item pincode 560001, got {stored[0].get('pincode')}"
    assert "is_in_stock" in stored[0], "Missing is_in_stock in stored product"
    print(f"  ✅ Successfully tracked all {len(stored)} products in SQLite database with custom delivery PIN and stock status.")

    # Test Stock Transitions in DB
    test_prod_id = inserted_ids[0]
    # Transition to OOS
    database.update_product_stock_status(test_prod_id, is_in_stock=False)
    updated_items = {item["id"]: item for item in database.get_user_products(test_user_id)}
    assert updated_items[test_prod_id]["is_in_stock"] == 0, "Failed to transition to Out-of-Stock (expected 0)"
    print("  ✅ Database Out-of-Stock transition verified (is_in_stock: 1 ➔ 0).")

    # Transition to Back-in-Stock (Restock) with new price
    database.update_product_stock_status(test_prod_id, is_in_stock=True, current_price=64999.0)
    updated_items = {item["id"]: item for item in database.get_user_products(test_user_id)}
    assert updated_items[test_prod_id]["is_in_stock"] == 1, "Failed to transition to Back-in-Stock (expected 1)"
    assert updated_items[test_prod_id]["current_price"] == 64999.0, "Failed to update price on restock"
    print("  ✅ Database Back-in-Stock transition verified (is_in_stock: 0 ➔ 1 with live price).")

    # Cleanup test user entries
    database.clear_user_products(test_user_id)
    print("  ✅ Cleanup completed.")

    print("\n" + "=" * 60)
    print("🎉 ALL TESTS PASSED! 11 PLATFORMS & STOCK NOTIFICATIONS FULLY OPERATIONAL!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
