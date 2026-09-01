
"""Tamimi Markets product extraction via public API endpoint.

Extracts 5 products per category from Tamimi Markets API and saves:
data/raw/stores/tamimi/tamimi_sample_5_per_category.json
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests


BASE_URL = "https://shop.tamimimarkets.com/api/product"

SAMPLE_LIMIT_PER_CATEGORY = 100
API_LIMIT = 100

CATEGORIES = {
    "dairy": "dairy",
    "fruits-vegetables": "fruits vegetables",
    "water-beverages": "water beverages",
}


def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).resolve().parents[2]


def output_path() -> Path:
    """Return the output JSON path."""
    path = (
        project_root()
        / "data"
        / "raw"
        / "stores"
        / "tamimi"
        / "tamimi_sample_5_per_category.json"
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def clean_text(value: Any) -> str:
    """Normalize text."""
    if value is None:
        return ""

    return " ".join(str(value).split()).strip()


def safe_float(value: Any) -> float | None:
    """Convert a value to float safely."""
    if value in (None, "", "null"):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_category_path(product: dict) -> str:
    """Build category path from Tamimi category hierarchy."""

    primary = product.get("primaryCategory") or {}

    parent = primary.get("parentCategory") or {}
    grand_parent = parent.get("parentCategory") or {}

    names = []

    if grand_parent.get("name"):
        names.append(clean_text(grand_parent["name"]))

    if parent.get("name"):
        names.append(clean_text(parent["name"]))

    if primary.get("name"):
        names.append(clean_text(primary["name"]))

    return " > ".join(names)


def get_first_variant(product: dict) -> dict:
    """Return the first product variant containing useful data."""

    variants = product.get("variants") or []

    if not isinstance(variants, list):
        return {}

    for variant in variants:
        if isinstance(variant, dict):
            return variant

    return {}


def get_price_data(product: dict, variant: dict) -> tuple[float | None, float | None, bool, int | None]:
    """Extract price, regular price, sale status and stock."""

    store_data = variant.get("storeSpecificData") or []

    if not isinstance(store_data, list):
        store_data = []

    selected_store = None

    # Prefer a store record that actually contains price information.
    for item in store_data:
        if isinstance(item, dict):
            if item.get("mrp") not in (None, ""):
                selected_store = item
                break

    if selected_store is None and store_data:
        selected_store = store_data[0]

    selected_store = selected_store or {}

    mrp = safe_float(selected_store.get("mrp"))
    discount = safe_float(selected_store.get("discount"))

    # The API can expose discount as a numeric value.
    # If discount is > 0, calculate the selling price from MRP.
    price = mrp

    if discount is not None and discount > 0 and mrp is not None:
        price = round(mrp - discount, 2)

    stock = selected_store.get("stock")

    try:
        stock_int = int(stock) if stock is not None else None
    except (TypeError, ValueError):
        stock_int = None

    in_stock = stock_int is None or stock_int > 0

    return price, mrp, price != mrp, stock_int


def simplify_product(product: dict, category_key: str) -> dict:
    """Convert Tamimi API product into project-standard structure."""

    variant = get_first_variant(product)

    price, regular_price, on_sale, stock = get_price_data(
        product,
        variant,
    )

    barcodes = variant.get("barcodes") or product.get("barcodes") or []

    if isinstance(barcodes, str):
        barcodes = [barcodes]

    barcode = None

    if isinstance(barcodes, list):
        for code in barcodes:
            code = clean_text(code)
            if code:
                barcode = code
                break

    brand = product.get("brand") or {}

    if isinstance(brand, dict):
        brand_name = clean_text(brand.get("name"))
    else:
        brand_name = clean_text(brand)

    product_name = (
        clean_text(variant.get("fullName"))
        or clean_text(product.get("name"))
    )

    variant_name = clean_text(variant.get("name"))

    if variant_name and variant_name not in product_name:
        product_name = f"{product_name} - {variant_name}"

    return {
        "store": "Tamimi Markets",
        "barcode": barcode,
        "product_name": product_name,
        "brand": brand_name or None,
        "category": category_key,
        "price": price,
        "regular_price": regular_price,
        "unit": "unit",
        "size": 1.0,
        "currency": "SAR",
        "in_stock": bool(stock is None or stock > 0),
        "stock": stock,
        "product_id": product.get("id"),
        "variant_id": variant.get("id"),
        "category_path": get_category_path(product),
        "url": (
            "https://shop.tamimimarkets.com/product/"
            + clean_text(product.get("slug"))
            if product.get("slug")
            else None
        ),
        "image": (
            variant.get("images", [None])[0]
            if isinstance(variant.get("images"), list)
            and variant.get("images")
            else None
        ),
        "on_sale": on_sale,
    }


def fetch_category(
    category_key: str,
    query: str,
) -> list[dict]:
    """Fetch products for one category."""

    print(f"\n[{category_key}] Searching Tamimi API...")
    print(f"Query: {query}")

    params = {
        "q": query,
        "limit": API_LIMIT,
        "offset": 0,
    }

    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
    }

    response = requests.get(
        BASE_URL,
        params=params,
        headers=headers,
        timeout=30,
    )

    response.raise_for_status()

    payload = response.json()

    data = payload.get("data") or {}
    products = data.get("product") or []

    if not isinstance(products, list):
        products = []

    print(
        f"[{category_key}] API returned "
        f"{len(products)} products "
        f"(total reported: {data.get('count', 'unknown')})"
    )

    results = []

    for product in products:
        if not isinstance(product, dict):
            continue

        simplified = simplify_product(
            product,
            category_key,
        )

        # Ignore products where no useful name exists.
        if not simplified["product_name"]:
            continue

        # Ignore products without a price.
        if simplified["price"] is None:
            continue

        results.append(simplified)

        if len(results) >= SAMPLE_LIMIT_PER_CATEGORY:
            break

    print(
        f"[{category_key}] Selected "
        f"{len(results)} products."
    )

    time.sleep(1)

    return results


def extract_tamimi_prices() -> list[dict]:
    """Main Tamimi extraction function."""

    print("=" * 60)
    print("STARTING TAMIMI EXTRACTION")
    print("=" * 60)

    all_records = []

    for category_key, query in CATEGORIES.items():

        try:
            records = fetch_category(
                category_key=category_key,
                query=query,
            )

            all_records.extend(records)

        except requests.RequestException as exc:
            print(
                f"[{category_key}] ERROR: "
                f"API request failed: {exc}"
            )

        except Exception as exc:
            print(
                f"[{category_key}] ERROR: "
                f"{type(exc).__name__}: {exc}"
            )

    result = {
        "generated_at": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(),
        ),
        "sample_limit_per_category": SAMPLE_LIMIT_PER_CATEGORY,
        "categories": {
            category: sum(
                1
                for record in all_records
                if record["category"] == category
            )
            for category in CATEGORIES
        },
        "records_count": len(all_records),
        "records": all_records,
    }

    path = output_path()

    path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print("TAMIMI EXTRACTION FINISHED")
    print("=" * 60)

    print(f"Total records: {len(all_records)}")
    print(f"Output: {path}")

    return all_records


if __name__ == "__main__":
    extract_tamimi_prices()

