import json
import re
from datetime import datetime, timezone
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    ROOT
    / "data"
    / "raw"
    / "stores"
    / "tamimi"
    / "tamimi_raw_latest.json"
)

OUTPUT_DIR = (
    ROOT
    / "data"
    / "processed"
    / "stores"
    / "tamimi"
)

OUTPUT_FILE = OUTPUT_DIR / "tamimi_clean_latest.json"


# ============================================================
# HELPERS
# ============================================================

def safe_float(value):
    """
    Convert value to float safely.
    """
    if value is None:
        return None

    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def clean_text(value):
    """
    Clean text values.
    """
    if value is None:
        return None

    text = str(value).strip()

    return text if text else None


def get_first_variant(product):
    """
    Get the first product variant.
    """
    variants = product.get("variants") or []

    if not variants:
        return None

    return variants[0]


def get_store_data(variant):
    """
    Get the first store-specific record for the variant.
    """
    if not variant:
        return None

    store_data = variant.get("storeSpecificData") or []

    if not store_data:
        return None

    return store_data[0]


def extract_size_and_unit(variant):
    """
    Extract size and unit from the variant name.

    Examples:
        473Ml -> 473, ml
        1.8Kg -> 1.8, kg
        500G -> 500, g
        1L -> 1, l
    """

    if not variant:
        return None, None

    full_name = clean_text(variant.get("fullName"))
    variant_name = clean_text(variant.get("name"))

    text = full_name or variant_name

    if not text:
        return None, None

    # Search for number + unit
    pattern = re.search(
        r"(\d+(?:\.\d+)?)\s*(kg|g|mg|l|ml|cl|litre|liter|liters|litres)",
        text.lower()
    )

    if not pattern:
        return None, None

    size = safe_float(pattern.group(1))
    unit = pattern.group(2).lower()

    # Normalize units
    unit_mapping = {
        "kilogram": "kg",
        "kilograms": "kg",
        "kg": "kg",
        "g": "g",
        "mg": "mg",
        "l": "l",
        "litre": "l",
        "liter": "l",
        "liters": "l",
        "litres": "l",
        "ml": "ml",
        "cl": "cl",
    }

    unit = unit_mapping.get(unit, unit)

    return size, unit


def calculate_price(mrp, discount):
    """
    Tamimi discount is a fixed SAR amount.

    price = MRP - discount
    """

    if mrp is None:
        return None

    if discount is None:
        discount = 0.0

    price = mrp - discount

    # Avoid negative prices caused by bad data
    if price < 0:
        price = 0.0

    return round(price, 2)


def calculate_total_size(size, quantity):
    """
    Calculate total size when possible.
    """

    if size is None or quantity is None:
        return None

    return round(size * quantity, 3)


def build_product_url(product):
    """
    Build Tamimi product URL.

    Example:
    https://shop.tamimimarkets.com/product/<slug>
    """

    slug = clean_text(product.get("slug"))

    if not slug:
        return None

    return f"https://shop.tamimimarkets.com/product/{slug}"


def get_image(product, variant):
    """
    Get the first available product image.
    """

    # Try variant images first
    if variant:
        variant_images = variant.get("images") or []

        if variant_images:
            return variant_images[0]

    # Try product images
    product_images = product.get("images") or []

    if isinstance(product_images, list) and product_images:
        return product_images[0]

    return None


# ============================================================
# LOAD RAW DATA
# ============================================================

def load_raw_data():
    """
    Load Tamimi RAW JSON.
    """

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"RAW file not found:\n{INPUT_FILE}"
        )

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


# ============================================================
# TRANSFORM
# ============================================================

def transform(raw_data):
    """
    Transform Tamimi RAW data into the same schema
    used by Danube and BinDawood.
    """

    products = raw_data.get("hits") or []

    records = []

    for product in products:

        # ----------------------------------------------------
        # Basic product information
        # ----------------------------------------------------

        product_name_en = clean_text(product.get("name"))

        if not product_name_en:
            continue

        product_name_ar = clean_text(
            product.get("nameAr")
            or product.get("name_ar")
            or product.get("arabicName")
        )

        # If Arabic name is not available,
        # use English name as fallback.
        if not product_name_ar:
            product_name_ar = product_name_en

        # ----------------------------------------------------
        # Brand
        # ----------------------------------------------------

        brand_data = product.get("brand")

        if isinstance(brand_data, dict):
            brand = clean_text(brand_data.get("name"))
        else:
            brand = clean_text(brand_data)

        # ----------------------------------------------------
        # Category
        # ----------------------------------------------------

        category = clean_text(
            product.get("_category_key")
        )

        # ----------------------------------------------------
        # Variant
        # ----------------------------------------------------

        variant = get_first_variant(product)

        store_data = get_store_data(variant)

        if not store_data:
            continue

        # ----------------------------------------------------
        # Price
        # ----------------------------------------------------

        mrp = safe_float(
            store_data.get("mrp")
        )

        discount = safe_float(
            store_data.get("discount")
        )

        if discount is None:
            discount = 0.0

        price = calculate_price(
            mrp,
            discount
        )

        if price is None:
            continue

        # ----------------------------------------------------
        # Size & Unit
        # ----------------------------------------------------

        size, unit = extract_size_and_unit(
            variant
        )

        # ----------------------------------------------------
        # Quantity
        # ----------------------------------------------------

        quantity = safe_float(
            store_data.get("unit")
        )

        if quantity is None:
            quantity = 1

        # Convert whole numbers to int
        if quantity.is_integer():
            quantity = int(quantity)

        # ----------------------------------------------------
        # Total Size
        # ----------------------------------------------------

        total_size = calculate_total_size(
            size,
            quantity
        )

        # ----------------------------------------------------
        # URL
        # ----------------------------------------------------

        url = build_product_url(
            product
        )

        # ----------------------------------------------------
        # Image
        # ----------------------------------------------------

        image = get_image(
            product,
            variant
        )

        # ----------------------------------------------------
        # Final record
        # ----------------------------------------------------

        record = {
            "product_name_ar": product_name_ar,
            "product_name_en": product_name_en,
            "store": "Tamimi Markets",
            "category": category,
            "price": round(price, 2),
            "regular_price": round(mrp, 2) if mrp is not None else None,
            "discount": round(discount, 2),
            "brand": brand,
            "size": size,
            "unit": unit,
            "quantity": quantity,
            "total_size": total_size,
            "url": url,
            "image": image
        }

        records.append(record)

    # --------------------------------------------------------
    # Remove duplicate products
    # --------------------------------------------------------

    unique_records = []

    seen = set()

    for record in records:

        key = (
            record.get("product_name_en"),
            record.get("category")
        )

        if key in seen:
            continue

        seen.add(key)
        unique_records.append(record)

    return unique_records


# ============================================================
# SAVE CLEAN DATA
# ============================================================

def save_clean_file(records, raw_data):
    """
    Save only tamimi_clean_latest.json
    using the same wrapper structure as Danube/BinDawood.
    """

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    categories = {}

    for record in records:

        category = record.get("category")

        if category:
            categories[category] = (
                categories.get(category, 0) + 1
            )

    clean_data = {
        "store": "Tamimi Markets",
        "generated_at": raw_data.get(
            "fetched_at",
            datetime.now(timezone.utc).isoformat()
        ),
        "categories": categories,
        "records_count": len(records),
        "records": records
    }

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            clean_data,
            file,
            ensure_ascii=False,
            indent=2
        )

    return clean_data


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("TAMIMI DATA TRANSFORMATION")
    print("=" * 60)

    print(f"RAW input:")
    print(INPUT_FILE)

    print()

    raw_data = load_raw_data()

    records = transform(
        raw_data
    )

    clean_data = save_clean_file(
        records,
        raw_data
    )

    print()
    print("TRANSFORMATION COMPLETE")
    print("-" * 60)

    print(
        f"RAW products: {len(raw_data.get('hits') or [])}"
    )

    print(
        f"CLEAN records: {clean_data['records_count']}"
    )

    print()
    print("CATEGORIES:")

    for category, count in clean_data["categories"].items():
        print(
            f"  {category}: {count}"
        )

    print()
    print("OUTPUT:")
    print(OUTPUT_FILE)

    print("=" * 60)


if __name__ == "__main__":
    main()