"""Tamimi Markets RAW extraction via public product API.

Pulls available products for the target categories using offset-based
pagination. API product objects are stored exactly as returned:
no cleaning, no brand parsing, no size parsing, and no price selection.

The endpoint behaves like a search API, so every returned product is
verified against its `primaryCategory` hierarchy before being placed into
one of the three target categories.

Output:
    data/raw/stores/tamimi/tamimi_raw_<timestamp>.json
    data/raw/stores/tamimi/tamimi_raw_latest.json

Run transform_tamimi.py afterwards to produce the cleaned dataset.
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

# This is requested from the API. Some deployments may cap their returned
# page size below this value, so pagination advances by the actual number
# returned rather than blindly by API_LIMIT.
API_LIMIT = 100

# Protection against an API repeatedly returning data forever.
MAX_PAGES_SAFETY = 500

# Stop after this many successive pages add no new products. It protects
# against repeated pages while allowing one page of search overlap.
MAX_CONSECUTIVE_NO_NEW_PAGES = 2

REQUEST_DELAY_SECONDS = 0.5

# Queries retrieve a broad candidate set. category_id and slug are the
# authoritative filters applied locally afterward.
CATEGORIES = {
    "fruits-vegetables": {
        "query": "fruits vegetables",
        "slug": "fruits--vegetables",
        "category_id": 3,
    },
    "dairy": {
        "query": "dairy",
        "slug": "dairy",
        "category_id": 36,
    },
    "beverages": {
        "query": "water beverages",
        "slug": "water--beverages",
        "category_id": 82,
    },
}


# ============================================================
# PATHS
# ============================================================


def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).resolve().parents[2]


def raw_output_dir() -> Path:
    """Create and return the Tamimi raw-data directory."""
    path = project_root() / "data" / "raw" / "stores" / "tamimi"
    path.mkdir(parents=True, exist_ok=True)
    return path


# ============================================================
# TEXT HELPERS
# ============================================================


def clean_text(value: Any) -> str:
    """Normalize a value only for local comparisons."""
    if value is None:
        return ""

    return " ".join(str(value).split()).strip()


# ============================================================
# CATEGORY FILTERING
# ============================================================


def get_category_nodes(product: dict[str, Any]) -> list[dict[str, Any]]:
    """Return primary category and every parent category of a product."""
    nodes: list[dict[str, Any]] = []

    current = product.get("primaryCategory")

    while isinstance(current, dict) and current:
        nodes.append(current)
        current = current.get("parentCategory")

    return nodes


def product_belongs_to_category(
    product: dict[str, Any],
    category_id: int,
    category_slug: str,
) -> bool:
    """Check category membership using the complete category hierarchy."""
    for node in get_category_nodes(product):
        if node.get("id") == category_id:
            return True

        if clean_text(node.get("slug")) == category_slug:
            return True

    return False


# ============================================================
# DEDUPLICATION
# ============================================================


def get_product_key(product: dict[str, Any]) -> str:
    """Build a stable key for a raw product without changing it."""
    product_id = product.get("id")
    variants = product.get("variants") or []

    variant_ids: list[str] = []

    if isinstance(variants, list):
        for variant in variants:
            if not isinstance(variant, dict):
                continue

            variant_id = variant.get("id")

            if variant_id is not None:
                variant_ids.append(str(variant_id))

    variants_part = ",".join(sorted(variant_ids))

    if product_id is not None:
        return f"product:{product_id}|variants:{variants_part}"

    slug = clean_text(product.get("slug"))
    name = clean_text(product.get("name"))

    return f"fallback:{slug}|{name}|variants:{variants_part}"


# ============================================================
# HTTP / API
# ============================================================


def get_headers() -> dict[str, str]:
    """Return browser-like headers required by the public endpoint."""
    return {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://shop.tamimimarkets.com",
        "Referer": "https://shop.tamimimarkets.com/",
    }


def fetch_page(
    query: str,
    offset: int,
) -> tuple[list[dict[str, Any]], int | None]:
    """Fetch one page of Tamimi product search results."""
    params = {
        "q": query,
        "limit": API_LIMIT,
        "offset": offset,
    }

    response = requests.get(
        PRODUCT_API,
        params=params,
        headers=get_headers(),
        timeout=30,
    )
    response.raise_for_status()

    payload = response.json()
    data = payload.get("data") or {}

    products = data.get("product") or []

    if not isinstance(products, list):
        products = []

    raw_total = data.get("count")

    try:
        total_count = (
            int(raw_total)
            if raw_total is not None
            else None
        )
    except (TypeError, ValueError):
        total_count = None

    return products, total_count


# ============================================================
# EXTRACTION
# ============================================================


def fetch_category_raw(
    category_key: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Fetch every available search-result page for one target category."""
    query = str(config["query"])
    category_slug = str(config["slug"])
    category_id = int(config["category_id"])

    print(f"\n[{category_key}] Fetching raw products from Tamimi API...")
    print(f"  Search query: {query!r}")
    print(
        f"  Local category filter: "
        f"id={category_id}, slug={category_slug!r}"
    )

    all_products: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    offset = 0
    page_number = 0
    total_reported: int | None = None
    consecutive_no_new_pages = 0

    while page_number < MAX_PAGES_SAFETY:
        products, page_total = fetch_page(
            query=query,
            offset=offset,
        )

        page_number += 1

        if total_reported is None:
            total_reported = page_total

        if not products:
            print("  No more products returned; stopping.")
            break

        raw_page_count = len(products)
        kept_this_page = 0
        duplicates_this_page = 0
        rejected_outside_category = 0

        for product in products:
            if not isinstance(product, dict):
                continue

            if not product_belongs_to_category(
                product=product,
                category_id=category_id,
                category_slug=category_slug,
            ):
                rejected_outside_category += 1
                continue

            product_key = get_product_key(product)

            if product_key in seen_keys:
                duplicates_this_page += 1
                continue

            seen_keys.add(product_key)

            # Raw API fields stay untouched. Only pipeline traceability
            # metadata is appended.
            product["_category_key"] = category_key
            product["_category_slug"] = category_slug
            product["_category_id"] = category_id
            product["_source_query"] = query
            product["_source_offset"] = offset

            all_products.append(product)
            kept_this_page += 1

        total_label = (
            str(total_reported)
            if total_reported is not None
            else "unknown"
        )

        print(
            f"  page {page_number} | offset {offset} | "
            f"API returned {raw_page_count} | "
            f"kept {kept_this_page} | "
            f"duplicates {duplicates_this_page} | "
            f"outside category {rejected_outside_category} | "
            f"category total {len(all_products)} | "
            f"search count {total_label}"
        )

        # A non-empty page that contains no unseen qualifying products can
        # be caused by overlapping/repeated search pages. Allow one repeat,
        # then stop safely.
        if kept_this_page == 0:
            consecutive_no_new_pages += 1
        else:
            consecutive_no_new_pages = 0

        if consecutive_no_new_pages >= MAX_CONSECUTIVE_NO_NEW_PAGES:
            print(
                "  Stopping because consecutive pages added no new "
                "products to this category."
            )
            break

        # IMPORTANT:
        # Increment by the number actually returned. If the endpoint ignores
        # limit=100 and returns 20, offsets will be 0, 20, 40, 60... rather
        # than jumping 0, 100, 200... and skipping data.
        offset += raw_page_count

        # A reported search total is useful only for logging. We do not stop
        # at that total because it describes the broad text search result,
        # not necessarily the locally filtered category result.
        time.sleep(REQUEST_DELAY_SECONDS)

    if page_number >= MAX_PAGES_SAFETY:
        print(
            f"  WARNING: stopped at MAX_PAGES_SAFETY="
            f"{MAX_PAGES_SAFETY}."
        )

    print(
        f"[{category_key}] Raw products collected: "
        f"{len(all_products)}"
    )

    return all_products


# ============================================================
# SAVE
# ============================================================


def save_raw_file(
    all_products: list[dict[str, Any]],
) -> Path:
    """Save timestamped and latest Tamimi raw snapshots."""
    timestamp = time.strftime(
        "%Y%m%d_%H%M%S",
        time.gmtime(),
    )

    fetched_at = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ",
        time.gmtime(),
    )

    category_counts = {
        category_key: sum(
            1
            for product in all_products
            if product.get("_category_key") == category_key
        )
        for category_key in CATEGORIES
    }

    result = {
        "store": "Tamimi Markets",
        "source": "tamimi_public_api",
        "endpoint": PRODUCT_API,
        "fetched_at": fetched_at,
        "configuration": {
            "requested_page_limit": API_LIMIT,
            "max_pages_safety": MAX_PAGES_SAFETY,
            "request_delay_seconds": REQUEST_DELAY_SECONDS,
        },
        "hits_count": len(all_products),
        "categories": category_counts,
        "hits": all_products,
    }

    output_dir = raw_output_dir()

    timestamped_path = (
        output_dir
        / f"tamimi_raw_{timestamp}.json"
    )

    latest_path = (
        output_dir
        / "tamimi_raw_latest.json"
    )

    timestamped_path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    latest_path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return timestamped_path


# ============================================================
# MAIN
# ============================================================


def extract_tamimi_raw() -> list[dict[str, Any]]:
    """Run the full Tamimi raw extraction for every target category."""
    print("=" * 60)
    print("STARTING TAMIMI RAW EXTRACTION (NO CLEANING)")
    print("=" * 60)

    all_products: list[dict[str, Any]] = []

    for category_key, config in CATEGORIES.items():
        try:
            products = fetch_category_raw(
                category_key=category_key,
                config=config,
            )
        except requests.RequestException as error:
            print(
                f"[{category_key}] API ERROR: {error}"
            )
            products = []
        except Exception as error:
            print(
                f"[{category_key}] UNEXPECTED ERROR: "
                f"{type(error).__name__}: {error}"
            )
            products = []

        all_products.extend(products)

    output_path = save_raw_file(all_products)

    category_counts = {
        category_key: sum(
            1
            for product in all_products
            if product.get("_category_key") == category_key
        )
        for category_key in CATEGORIES
    }

    print("\n" + "=" * 60)
    print("TAMIMI RAW EXTRACTION FINISHED")
    print("=" * 60)

    for category_key, count in category_counts.items():
        print(f"  {category_key}: {count} raw products")

    print(f"  Total raw products: {len(all_products)}")
    print(f"  Saved to: {output_path}")
    print(
        "  Also saved to: tamimi_raw_latest.json "
        "(used by transform_tamimi.py)"
    )

    return all_products


if __name__ == "__main__":
    extract_tamimi_raw()