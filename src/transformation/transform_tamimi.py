from __future__ import annotations

import json
import re
import time
from collections import Counter
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

LATEST_OUTPUT_FILE = OUTPUT_DIR / "tamimi_clean_latest.json"


# ============================================================
# BASIC HELPERS
# ============================================================

def clean_text(value):
    if value is None:
        return None

    value = " ".join(str(value).split()).strip()
    return value or None


def safe_float(value):
    if value is None or isinstance(value, bool):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_unit(unit):
    if not unit:
        return None

    unit = str(unit).lower().strip()

    mapping = {
        "kilogram": "kg",
        "kilograms": "kg",
        "kilo": "kg",
        "gm": "g",
        "gr": "g",
        "gram": "g",
        "grams": "g",
        "milligram": "mg",
        "milligrams": "mg",
        "milliliter": "ml",
        "milliliters": "ml",
        "millilitre": "ml",
        "millilitres": "ml",
        "ltr": "l",
        "liter": "l",
        "litre": "l",
        "liters": "l",
        "litres": "l",
    }

    return mapping.get(unit, unit)


# ============================================================
# DISPLAY NAME CLEANING
# ============================================================

def tidy_name(text):
    if not text:
        return None

    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*-\s*$", "", text)
    text = re.sub(r"^\s*-\s*", "", text)
    text = re.sub(r"\(\s*\)", "", text)

    return text.strip() or None


def remove_brand_from_name(name, brand):
    """
    Remove the brand only when it appears at the beginning of the name.
    """
    if not name or not brand:
        return name

    pattern = rf"^\s*{re.escape(brand)}(?=\s|[-–—,:;/]|$)\s*"

    return tidy_name(
        re.sub(
            pattern,
            "",
            name,
            flags=re.IGNORECASE,
        )
    )


def remove_size_and_quantity(name):
    """
    Remove measurements and numeric pack formats only.

    Examples:
        Nido Fortified Grow With Fiber Tin-400G
        -> Nido Fortified Grow With Fiber Tin

        Juice 24*125ml
        -> Juice

        Juice 3x6x125ml
        -> Juice
    """
    if not name:
        return name

    number = r"\d+(?:\.\d+)?"

    unit = (
        r"(?:kg|kilogram(?:s)?|kilo|"
        r"g|gm|gr|gram(?:s)?|"
        r"mg|milligram(?:s)?|"
        r"ml|milliliter(?:s)?|millilitre(?:s)?|"
        r"cl|"
        r"l|ltr|liter(?:s)?|litre(?:s)?|"
        r"oz|ounce(?:s)?)"
    )

    multipack_pattern = (
        rf"\b{number}\s*[x×*]\s*"
        rf"(?:{number}\s*[x×*]\s*)*"
        rf"{number}\s*{unit}\b"
    )

    size_pattern = rf"\b{number}\s*{unit}\b"

    packaging_pattern = (
        rf"\b{number}\s*"
        r"(?:pack(?:s)?|bottle(?:s)?|can(?:s)?|jar(?:s)?|"
        r"piece(?:s)?|pcs?|pc|box(?:es)?|bag(?:s)?)\b"
    )

    name = re.sub(
        multipack_pattern,
        " ",
        name,
        flags=re.IGNORECASE,
    )

    name = re.sub(
        size_pattern,
        " ",
        name,
        flags=re.IGNORECASE,
    )

    name = re.sub(
        packaging_pattern,
        " ",
        name,
        flags=re.IGNORECASE,
    )

    return tidy_name(name)


def clean_display_name(name, brand):
    """
    Keep a readable fallback if cleaning accidentally removes all text.
    """
    original = name

    name = remove_brand_from_name(name, brand)
    name = remove_size_and_quantity(name)

    return name or original


# ============================================================
# PRODUCT / VARIANT HELPERS
# ============================================================

def get_variants(product):
    variants = product.get("variants") or []

    if not isinstance(variants, list):
        return []

    return [
        variant
        for variant in variants
        if isinstance(variant, dict)
    ]


def get_product_name(product, variant):
    return (
        clean_text(variant.get("fullName"))
        or clean_text(variant.get("name"))
        or clean_text(product.get("name"))
        or clean_text(product.get("fullName"))
    )


def get_arabic_name(product, variant):
    for source in (variant, product):
        for key in (
            "fullNameAr",
            "fullNameAR",
            "nameAr",
            "nameAR",
            "arabicName",
            "full_name_ar",
            "name_ar",
        ):
            value = clean_text(source.get(key))

            if value:
                return value

    return None


def get_brand(product):
    brand = product.get("brand")

    if isinstance(brand, dict):
        return clean_text(brand.get("name"))

    return clean_text(brand)


# ============================================================
# PRICE HELPERS
# ============================================================

def is_available(record):
    if record.get("available") is False:
        return False

    if record.get("inStock") is False:
        return False

    if record.get("in_stock") is False:
        return False

    stock = safe_float(record.get("stock"))

    return stock is None or stock > 0


def is_sale(record):
    discount = safe_float(record.get("discount")) or 0.0

    if discount > 0:
        return True

    price = safe_float(record.get("price"))
    original_price = safe_float(record.get("original_price"))

    return (
        price is not None
        and original_price is not None
        and original_price > price
    )


def choose_store_record(variant):
    """
    Prefer available records, then offer records, then choose the most
    frequently repeated pricing combination.
    """
    store_data = variant.get("storeSpecificData") or []

    records = [
        record
        for record in store_data
        if isinstance(record, dict)
        and safe_float(record.get("mrp")) is not None
    ]

    if not records:
        return None

    available_records = [
        record
        for record in records
        if is_available(record)
    ]

    candidates = available_records or records

    sale_records = [
        record
        for record in candidates
        if is_sale(record)
    ]

    if sale_records:
        candidates = sale_records

    states = [
        (
            safe_float(record.get("mrp")),
            safe_float(record.get("discount")) or 0.0,
            safe_float(record.get("price")),
        )
        for record in candidates
    ]

    selected_state = Counter(states).most_common(1)[0][0]

    for record in candidates:
        state = (
            safe_float(record.get("mrp")),
            safe_float(record.get("discount")) or 0.0,
            safe_float(record.get("price")),
        )

        if state == selected_state:
            return record

    return candidates[0]


def get_price_data(store_record):
    """
    Tamimi discount is a fixed Saudi-riyal discount amount:
    price = mrp - discount.
    """
    if not store_record:
        return None, None, None

    mrp = safe_float(store_record.get("mrp"))

    if mrp is None or mrp <= 0:
        return None, None, None

    discount_amount = safe_float(
        store_record.get("discount")
    ) or 0.0

    price = safe_float(store_record.get("price"))

    if price is None:
        price = mrp - discount_amount

    price = max(round(price, 2), 0.0)
    regular_price = round(mrp, 2)

    discount_percent = (
        round((regular_price - price) / regular_price * 100, 2)
        if regular_price > price
        else 0.0
    )

    return price, regular_price, discount_percent


# ============================================================
# SIZE / QUANTITY HELPERS
# ============================================================

def extract_size_and_unit(variant):
    text = (
        clean_text(variant.get("fullName"))
        or clean_text(variant.get("name"))
    )

    if not text:
        return None, None

    matches = re.findall(
        r"(\d+(?:\.\d+)?)\s*"
        r"(kg|kilogram|kilograms|kilo|"
        r"g|gm|gr|gram|grams|"
        r"mg|milligram|milligrams|"
        r"ml|milliliter|milliliters|millilitre|millilitres|"
        r"cl|l|ltr|liter|litre|liters|litres)\b",
        text,
        flags=re.IGNORECASE,
    )

    if not matches:
        return None, None

    size, unit = matches[-1]

    return safe_float(size), normalize_unit(unit)


def extract_quantity(variant):
    text = (
        clean_text(variant.get("fullName"))
        or clean_text(variant.get("name"))
        or ""
    ).lower()

    match = re.search(
        r"(\d+)\s*[x×*]\s*(\d+)\s*[x×*]\s*"
        r"\d+(?:\.\d+)?\s*(?:kg|g|mg|l|ml|cl)\b",
        text,
    )

    if match:
        return int(match.group(1)) * int(match.group(2))

    match = re.search(
        r"(\d+)\s*[x×*]\s*"
        r"\d+(?:\.\d+)?\s*(?:kg|g|mg|l|ml|cl)\b",
        text,
    )

    if match:
        return int(match.group(1))

    match = re.search(
        r"\b(\d+)\s*(?:pack|packs|bottles?|cans?|jars?|pcs?|pieces?)\b",
        text,
    )

    if match:
        return int(match.group(1))

    return 1


# ============================================================
# URL / IMAGE
# ============================================================

def build_product_url(product):
    slug = clean_text(product.get("slug"))

    if not slug:
        return None

    return f"https://shop.tamimimarkets.com/ar/product/{slug}"


def get_image(product, variant):
    for source in (variant, product):
        images = source.get("images") or []

        if not isinstance(images, list):
            continue

        for image in images:
            image = clean_text(image)

            if image:
                return image

    return None


# ============================================================
# LOAD / TRANSFORM
# ============================================================

def load_raw_data():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"RAW file not found:\n{INPUT_FILE}"
        )

    with INPUT_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def remove_duplicates(records):
    unique_records = []
    seen = set()

    for record in records:
        key = (
            record.get("product_name_en"),
            record.get("category"),
            record.get("size"),
            record.get("unit"),
            record.get("quantity"),
        )

        if key not in seen:
            seen.add(key)
            unique_records.append(record)

    return unique_records


def transform(raw_data):
    products = raw_data.get("hits") or []

    if not isinstance(products, list):
        products = []

    records = []

    for product in products:
        if not isinstance(product, dict):
            continue

        for variant in get_variants(product):
            original_name_en = get_product_name(
                product,
                variant,
            )

            if not original_name_en:
                continue

            brand = get_brand(product)

            product_name_en = clean_display_name(
                original_name_en,
                brand,
            )

            product_name_ar = get_arabic_name(
                product,
                variant,
            )

            store_record = choose_store_record(
                variant
            )

            price, regular_price, discount = get_price_data(
                store_record
            )

            if price is None:
                continue

            size, unit = extract_size_and_unit(
                variant
            )

            quantity = extract_quantity(
                variant
            )

            records.append(
                {
                    "product_name_ar": product_name_ar,
                    "product_name_en": product_name_en,
                    "store": "Tamimi Markets",
                    "category": clean_text(
                        product.get("_category_key")
                    ),
                    "price": price,
                    "regular_price": regular_price,
                    "discount": discount,
                    "brand": brand,
                    "size": size,
                    "unit": unit or "unit",
                    "quantity": quantity,
                    "total_size": (
                        round(size * quantity, 3)
                        if size is not None
                        else None
                    ),
                    "url": build_product_url(product),
                    "image": get_image(product, variant),
                }
            )

    return remove_duplicates(records)


# ============================================================
# SAVE
# ============================================================

def save_clean_file(records):
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = time.strftime(
        "%Y%m%d_%H%M%S",
        time.gmtime(),
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
        "generated_at": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(),
        ),
        "categories": categories,
        "records_count": len(records),
        "records": records,
    }

    timestamped_file = (
        OUTPUT_DIR
        / f"tamimi_clean_{timestamp}.json"
    )

    serialized = json.dumps(
        clean_data,
        ensure_ascii=False,
        indent=2,
    )

    for output_file in (
        timestamped_file,
        LATEST_OUTPUT_FILE,
    ):
        output_file.write_text(
            serialized,
            encoding="utf-8",
        )

    return timestamped_file


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("TAMIMI DATA TRANSFORMATION")
    print("=" * 60)

    raw_data = load_raw_data()
    records = transform(raw_data)
    output_file = save_clean_file(records)

    raw_hits = raw_data.get("hits") or []

    brands_found = sum(
        record.get("brand") is not None
        for record in records
    )

    sizes_found = sum(
        record.get("size") is not None
        for record in records
    )

    deals_found = sum(
        (record.get("discount") or 0) > 0
        for record in records
    )

    print(f"Raw products: {len(raw_hits)}")
    print(f"Clean records: {len(records)}")
    print(f"Brands found: {brands_found}/{len(records)}")
    print(f"Sizes found: {sizes_found}/{len(records)}")
    print(f"Products on discount: {deals_found}/{len(records)}")
    print(f"Timestamped: {output_file}")
    print(f"Latest: {LATEST_OUTPUT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()