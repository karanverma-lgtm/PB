"""Backward-compatibility alias pointing to product_service."""
from product_service import (
    fetch_amazon_product,
    extract_amazon_asin as extract_asin,
    fetch_product,
)

# Alias for legacy compatibility
fetch_amazon_product = fetch_amazon_product
