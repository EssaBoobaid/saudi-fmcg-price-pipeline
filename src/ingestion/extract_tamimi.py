"""
Tamimi Markets RAW product + category metadata extraction.

Collects:
- 100 products from each target category
- Category metadata from /api/layout/category
- Product metadata from /api/product
- Brand filters
- Price filters
- Tags
- Original API product objects

All data is stored together in:
data/raw/stores/tamimi/tamimi_raw_<timestamp>.json
data/raw/stores/tamimi/tamimi_raw_latest.json

No cleaning or transformation is applied.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests


# ============================================================
# CONFIG
# ============================================================

PRODUCT_API = "https://shop.tamimimarkets.com/api/product"
CATEGORY_API = "https://shop.tamimimarkets.com/api/layout/category"

API_LIMIT = 100
SAMPLE_LIMIT_PER_CATEGORY = 100

STORE_ID = 6
ORDER_TYPE = "PICKUP"

CATEGORIES = {
    "dairy": "dairy",
    "fruits-vegetables": "fruits vegetables",
    "water-beverages": "water beverages",
}


# ============================================================
# PATHS
# ============================================================

def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def raw_output_dir() -> Path:
    path = (
        project_root()
        / "data"
        / "raw"
        / "stores"
        / "tamimi"
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


# ============================================================
# HTTP
# ============================================================

def get_headers() -> dict[str, str]:
    return {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
    }


def get_json(
    url: str,
    params: dict[str, Any],
) -> dict[str, Any]:

    response = requests.get(
        url,
        params=params,
        headers=get_headers(),
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# CATEGORY METADATA
# ============================================================

def fetch_category_metadata(
    category_key: str,
    category_url: str,
) -> dict[str, Any]:

    print(
        f"\n[{category_key}] "
        f"Fetching category metadata..."
    )

    params = {
        "storeId": STORE_ID,
        "orderType": ORDER_TYPE,
        "url": category_url,
    }

    payload = get_json(
        CATEGORY_API,
        params,
    )

    data = payload.get("data") or {}

    print(
        f"[{category_key}] "
        f"Category metadata received."
    )

    return {
        "request": {
            "endpoint": CATEGORY_API,
            "params": params,
        },
        "response": payload,
        "summary": {
            "product_count": data.get("count"),
            "filter_count": len(
                data.get("filters") or {}
            ),
        },
    }


# ============================================================
# PRODUCT DATA
# ============================================================

def fetch_products(
    category_key: str,
    category_url: str,
) -> dict[str, Any]:

    print(
        f"\n[{category_key}] "
        f"Fetching RAW products..."
    )

    params = {
        "category": category_url,
        "facetSort": "A-Z",
        "layoutType": "GRID",
        "loadMoreType": "INFINITE",
        "sorting": "RELEVANCE",
        "page": 1,
        "storeId": STORE_ID,
        "orderType": ORDER_TYPE,
    }

    payload = get_json(
        PRODUCT_API,
        params,
    )

    data = payload.get("data") or {}

    products = data.get("product") or []

    if not isinstance(products, list):
        products = []

    print(
        f"[{category_key}] "
        f"API returned {len(products)} products."
    )

    products = products[:SAMPLE_LIMIT_PER_CATEGORY]

    # Keep original product objects.
    raw_products = []

    for product in products:

        if not isinstance(product, dict):
            continue

        raw_product = dict(product)

        # Metadata added only for traceability.
        # Original API fields remain untouched.
        raw_product["_category_key"] = category_key
        raw_product["_source_category"] = category_url

        raw_products.append(raw_product)

    print(
        f"[{category_key}] "
        f"RAW products collected: {len(raw_products)}"
    )

    return {
        "request": {
            "endpoint": PRODUCT_API,
            "params": params,
        },
        "response_metadata": {
            "code": payload.get("code"),
            "count": data.get("count"),
            "filter_count": len(
                data.get("filters") or {}
            ),
        },
        "filters": data.get("filters") or {},
        "products": raw_products,
    }


# ============================================================
# SAVE
# ============================================================

def save_raw_file(
    categories: dict[str, Any],
) -> None:

    timestamp = time.strftime(
        "%Y%m%d_%H%M%S",
        time.gmtime(),
    )

    generated_at = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ",
        time.gmtime(),
    )

    total_products = sum(
        len(
            category_data
            .get("products", [])
        )
        for category_data in categories.values()
    )

    result = {
        "store": "Tamimi Markets",

        "source": {
            "product_api": PRODUCT_API,
            "category_api": CATEGORY_API,
        },

        "fetched_at": generated_at,

        "configuration": {
            "store_id": STORE_ID,
            "order_type": ORDER_TYPE,
            "sample_limit_per_category": (
                SAMPLE_LIMIT_PER_CATEGORY
            ),
        },

        "categories": {},

        "summary": {
            "categories_count": len(categories),
            "products_count": total_products,
        },
    }

    # --------------------------------------------------------
    # Keep all category data together
    # --------------------------------------------------------

    for category_key, category_data in categories.items():

        result["categories"][category_key] = {
            "category_metadata": category_data[
                "category_metadata"
            ],

            "product_data": category_data[
                "product_data"
            ],
        }

    # --------------------------------------------------------
    # Timestamped RAW file
    # --------------------------------------------------------

    output_dir = raw_output_dir()

    timestamped_file = (
        output_dir
        / f"tamimi_raw_{timestamp}.json"
    )

    latest_file = (
        output_dir
        / "tamimi_raw_latest.json"
    )

    with timestamped_file.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            result,
            file,
            ensure_ascii=False,
            indent=2,
        )

    # --------------------------------------------------------
    # Latest RAW file
    # --------------------------------------------------------

    with latest_file.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            result,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print("\n========================================")
    print("Tamimi RAW extraction completed")
    print("========================================")

    print(
        f"Total categories: "
        f"{len(categories)}"
    )

    print(
        f"Total products: "
        f"{total_products}"
    )

    print(
        f"Saved: {timestamped_file}"
    )

    print(
        f"Latest: {latest_file}"
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    all_categories: dict[str, Any] = {}

    for category_key, category_url in CATEGORIES.items():

        print("\n----------------------------------------")
        print(f"Category: {category_key}")
        print("----------------------------------------")

        # 1. Category metadata
        category_metadata = fetch_category_metadata(
            category_key,
            category_url,
        )

        # 2. Product data + filters
        product_data = fetch_products(
            category_key,
            category_url,
        )

        all_categories[category_key] = {
            "category_metadata": category_metadata,
            "product_data": product_data,
        }

        # Small delay between categories
        time.sleep(1)

    save_raw_file(all_categories)


if __name__ == "__main__":
    main()