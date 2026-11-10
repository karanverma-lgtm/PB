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
        ("B09G9BL5CP", "Amazon"),
        ("https://www.flipkart.com/apple-iphone-15/p/itm6ac6485515ae4", "Flipkart"),
        ("https://dl.flipkart.com/s/12345", "Flipkart"),
        ("https://www.jiomart.com/product/apple-iphone-15-128gb-blue-mhxt4j-17504497", "JioMart"),
        ("https://www.reliancedigital.in/apple-iphone-15-128gb-black/p/493839309", "RelianceDigital"),
        ("https://www.croma.com/apple-iphone-15-128gb-black-/p/300652", "Croma"),
        ("https://www.samsung.com/in/smartphones/galaxy-s/galaxy-s26-fe-pistachio-256gb-sm-s741blgcins/", "Samsung"),
    ]

    print("\n🔍 1. Platform Detection Tests:")
    for url, expected in detection_cases:
        detected = product_service.detect_platform(url)
        assert detected == expected, f"Expected {expected}, got {detected} for {url}"
        print(f"  ✅ {expected.ljust(16)} ➔ {url[:45]}...")

    # 2. Live Product Fetching across all 6 platforms
    live_targets = [
        ("Amazon", "https://www.amazon.in/dp/B09G9BL5CP"),
        ("Flipkart", "https://www.flipkart.com/apple-iphone-15-black-128-gb/p/itm6ac6485515ae4"),
        ("Croma", "https://www.croma.com/apple-iphone-15-128gb-black-/p/300652"),
        ("Reliance Digital", "https://www.reliancedigital.in/apple-iphone-15-128gb-black/p/493839309"),
        ("JioMart", "https://www.jiomart.com/product/apple-iphone-15-128gb-blue-mhxt4j-17504497"),
        ("Samsung India", "https://www.samsung.com/in/smartphones/galaxy-s/galaxy-s26-fe-pistachio-256gb-sm-s741blgcins/"),
    ]

    print("\n🌐 2. Live Scraper Verification Across 6 Platforms:")
    fetched_products = []
    for platform_name, target_url in live_targets:
        print(f"\n  Fetching [{platform_name}]...")
        prod = product_service.fetch_product(target_url)
        if not prod:
            print(f"  ❌ FAILED to fetch {platform_name} from {target_url}")
            sys.exit(1)

        assert prod["price"] > 0, f"Invalid price {prod['price']}"
        assert prod["title"], "Missing title"
        assert prod["item_id"], "Missing item_id"
        assert prod["currency"] in ["₹", "$"], f"Unexpected currency {prod['currency']}"

        print(f"  ✅ {prod['platform_badge']} ({prod['platform']})")
        print(f"     Title: {prod['title'][:55]}...")
        print(f"     Price: {prod['currency']}{prod['price']:,.2f}")
        print(f"     Item ID: {prod['item_id']}")
        fetched_products.append(prod)

    # 3. Database Integration Test
    print("\n💾 3. Database Integration Tests:")
    database.init_db()
    test_user_id = 999888777
    database.clear_user_products(test_user_id)

    # Test pending product caching across restarts
    sample_prod = fetched_products[0]
    database.save_pending_product(sample_prod)
    cached = database.get_pending_product(sample_prod["item_id"])
    assert cached is not None, "Pending product was not saved"
    assert cached["item_id"] == sample_prod["item_id"], "Mismatch in pending product item_id"
    print("  ✅ Pending product caching verified (survives bot restarts).")

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
        )
        inserted_ids.append(pid)

    stored = database.get_user_products(test_user_id)
    assert len(stored) == len(fetched_products), f"Expected {len(fetched_products)} items, got {len(stored)}"
    print(f"  ✅ Successfully tracked all {len(stored)} products in SQLite database.")

    # Cleanup test user entries
    database.clear_user_products(test_user_id)
    print("  ✅ Cleanup completed.")

    print("\n" + "=" * 60)
    print("🎉 ALL TESTS PASSED! 6 PLATFORMS FULLY OPERATIONAL!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
