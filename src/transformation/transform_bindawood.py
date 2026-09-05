from __future__ import annotations

import json
import os
import re
from datetime import datetime


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

INPUT_FILE = os.path.join(
    PROJECT_ROOT,
    "data",
    "raw",
    "stores",
    "bindawood",
    "bindawood_raw_latest.json",
)

OUTPUT_DIR = os.path.join(
    PROJECT_ROOT,
    "data",
    "processed",
    "stores",
    "bindawood",
)

OUTPUT_FILE = os.path.join(
    OUTPUT_DIR,
    "bindawood_clean.json",
)


# ============================================================
# CATEGORY MAPPING
# ============================================================

CATEGORY_MAP = {
    "fruits_vegetables": "fruits_vegetables",
    "dairy": "dairy",
    "beverages": "beverages",
}


# ============================================================
# TEXT HELPERS
# ============================================================

def clean_text(value):
    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    return value


def normalize_text(value):
    value = clean_text(value)

    if not value:
        return ""

    value = value.lower()

    value = value.replace("_", " ")
    value = value.replace("-", " ")
    value = value.replace("/", " ")

    value = re.sub(r"\s+", " ", value)

    return value.strip()


# ============================================================
# NUMBER HELPERS
# ============================================================

def to_float(value):
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ============================================================
# BRAND EXTRACTION
# ============================================================

def extract_brand(product):
    # 1. Direct API fields
    brand_en = clean_text(product.get("brand_en"))
    brand_ar = clean_text(product.get("brand_ar"))

    if brand_en:
        return brand_en

    if brand_ar:
        return brand_ar

    # 2. Other possible API fields
    for key in [
        "brand",
        "brand_name",
        "manufacturer",
        "manufacturer_name",
    ]:
        value = clean_text(product.get(key))

        if value:
            return value

    return None


# ============================================================
# UNIT NORMALIZATION
# ============================================================

def normalize_unit(unit):
    if not unit:
        return None

    unit = normalize_text(unit)

    unit_map = {
        "kg": "kg",
        "kilo": "kg",
        "kilos": "kg",
        "kilogram": "kg",
        "kilograms": "kg",
        "kgram": "kg",

        "g": "g",
        "gram": "g",
        "grams": "g",
        "gm": "g",

        "mg": "mg",
        "milligram": "mg",
        "milligrams": "mg",

        "l": "l",
        "liter": "l",
        "litre": "l",
        "liters": "l",
        "litres": "l",

        "ml": "ml",
        "milliliter": "ml",
        "millilitre": "ml",
        "milliliters": "ml",
        "millilitres": "ml",

        "pc": "piece",
        "pcs": "piece",
        "piece": "piece",
        "pieces": "piece",

        "pack": "pack",
        "packs": "pack",

        "tray": "tray",
        "trays": "tray",

        "box": "box",
        "boxes": "box",

        "bottle": "bottle",
        "bottles": "bottle",

        "can": "can",
        "cans": "can",

        "jar": "jar",
        "jars": "jar",

        "bag": "bag",
        "bags": "bag",
    }

    return unit_map.get(unit)


# ============================================================
# SIZE EXTRACTION FROM TEXT
# ============================================================

def extract_size_from_text(text):
    """
    Extract size from product name / URL.

    Examples:
        250g       -> 250, g
        250-g      -> 250, g
        1kg        -> 1, kg
        1-kg       -> 1, kg
        500ml      -> 500, ml
        500-ml     -> 500, ml
        1L         -> 1, l
        1-l        -> 1, l
    """

    if not text:
        return None, None

    text = str(text).lower()

    # Normalize separators only for matching
    normalized = text.replace("_", "-")
    normalized = re.sub(r"\s+", "-", normalized)

    # More specific units first
    patterns = [
        (r"(\d+(?:\.\d+)?)\s*(?:kg|kilo|kgram)\b", "kg"),
        (r"(\d+(?:\.\d+)?)\s*(?:g|gram|grams|gm)\b", "g"),
        (r"(\d+(?:\.\d+)?)\s*(?:mg|milligram|milligrams)\b", "mg"),
        (r"(\d+(?:\.\d+)?)\s*(?:ml|milliliter|millilitre)\b", "ml"),
        (r"(\d+(?:\.\d+)?)\s*(?:l|liter|litre)\b", "l"),
    ]

    for pattern, unit in patterns:
        match = re.search(pattern, text)

        if match:
            return float(match.group(1)), unit

    # Handle forms where hyphen is between number and unit
    patterns_hyphen = [
        (r"(\d+(?:\.\d+)?)-?(?:kg|kilo|kgram)\b", "kg"),
        (r"(\d+(?:\.\d+)?)-?(?:g|gram|grams|gm)\b", "g"),
        (r"(\d+(?:\.\d+)?)-?(?:mg|milligram|milligrams)\b", "mg"),
        (r"(\d+(?:\.\d+)?)-?(?:ml|milliliter|millilitre)\b", "ml"),
        (r"(\d+(?:\.\d+)?)-?(?:l|liter|litre)\b", "l"),
    ]

    for pattern, unit in patterns_hyphen:
        match = re.search(pattern, normalized)

        if match:
            return float(match.group(1)), unit

    return None, None


# ============================================================
# UNIT FROM PACKAGING WORD
# ============================================================

def extract_packaging_unit(text):
    if not text:
        return None

    text = normalize_text(text)

    packaging_patterns = [
        (r"\bpieces?\b", "piece"),
        (r"\bpcs?\b", "piece"),
        (r"\bpacks?\b", "pack"),
        (r"\btrays?\b", "tray"),
        (r"\bbox(?:es)?\b", "box"),
        (r"\bbags?\b", "bag"),
        (r"\bbottles?\b", "bottle"),
        (r"\bcans?\b", "can"),
        (r"\bjars?\b", "jar"),
    ]

    for pattern, unit in packaging_patterns:
        if re.search(pattern, text):
            return unit

    return None


# ============================================================
# QUANTITY EXTRACTION
# ============================================================

def extract_quantity(text, size=None, unit=None):
    """
    Extract quantity for products such as:

        48 x 200 ml
        48-star-200-ml
        6 pack
        12 bottles
        1 pc
    """

    if not text:
        return 1

    text = str(text).lower()

    # --------------------------------------------------------
    # Case: 48 x 200 ml
    # Case: 48-star-200-ml
    # --------------------------------------------------------

    multi_patterns = [
        r"\b(\d+)\s*[x×]\s*\d+(?:\.\d+)?\s*(?:kg|g|mg|l|ml)\b",
        r"\b(\d+)[-\s]*(?:star|pack|packs)[-\s]*\d+(?:\.\d+)?[-\s]*(?:kg|g|mg|l|ml)\b",
    ]

    for pattern in multi_patterns:
        match = re.search(pattern, text)

        if match:
            quantity = int(match.group(1))

            if quantity > 0:
                return quantity

    # --------------------------------------------------------
    # Case: 6 pack / 6 packs
    # --------------------------------------------------------

    pack_match = re.search(
        r"\b(\d+)\s*(?:pack|packs)\b",
        text,
    )

    if pack_match:
        quantity = int(pack_match.group(1))

        if quantity > 0:
            return quantity

    # --------------------------------------------------------
    # Case: 12 bottles / 24 cans
    # --------------------------------------------------------

    container_match = re.search(
        r"\b(\d+)\s*(?:bottles?|cans?|jars?|pieces?|pcs?|pc)\b",
        text,
    )

    if container_match:
        quantity = int(container_match.group(1))

        if quantity > 0:
            return quantity

    # --------------------------------------------------------
    # Case: 1 pc
    # --------------------------------------------------------

    if unit == "piece":
        pc_match = re.search(
            r"\b(\d+)\s*(?:pc|pcs|piece|pieces)\b",
            text,
        )

        if pc_match:
            quantity = int(pc_match.group(1))

            if quantity > 0:
                return quantity

    return 1


# ============================================================
# WEIGHT FROM API
# ============================================================

def extract_api_weight(product):
    """
    Try to use Bindawood's own weight-related fields first.
    """

    possible_fields = [
        "weight",
        "weight_increment",
        "size",
        "total_size",
    ]

    for field in possible_fields:
        value = product.get(field)

        if value is None:
            continue

        # Numeric direct value
        numeric_value = to_float(value)

        if numeric_value is not None and numeric_value > 0:
            return numeric_value

        # String value such as "250g"
        parsed_size, parsed_unit = extract_size_from_text(str(value))

        if parsed_size is not None:
            return parsed_size, parsed_unit

    return None


# ============================================================
# SIZE + UNIT EXTRACTION
# ============================================================

def extract_size_and_unit(product):
    name_en = clean_text(product.get("name_en"))
    name_ar = clean_text(product.get("name_ar"))
    url_en = clean_text(product.get("url_en"))
    url_ar = clean_text(product.get("url_ar"))

    # --------------------------------------------------------
    # 1. Try API weight field
    # --------------------------------------------------------

    api_weight = extract_api_weight(product)

    if isinstance(api_weight, tuple):
        return api_weight

    if api_weight is not None:
        # If API gives a numeric weight, we still need unit.
        # Use product text to identify it.
        combined_text = " ".join(
            value
            for value in [
                name_en,
                name_ar,
                url_en,
                url_ar,
            ]
            if value
        )

        _, detected_unit = extract_size_from_text(combined_text)

        if detected_unit:
            return api_weight, detected_unit

    # --------------------------------------------------------
    # 2. Product name
    # --------------------------------------------------------

    for text in [
        name_en,
        name_ar,
    ]:
        size, unit = extract_size_from_text(text)

        if size is not None:
            return size, unit

    # --------------------------------------------------------
    # 3. URL
    # --------------------------------------------------------

    for text in [
        url_en,
        url_ar,
    ]:
        size, unit = extract_size_from_text(text)

        if size is not None:
            return size, unit

    # --------------------------------------------------------
    # 4. No measurable size found
    # --------------------------------------------------------

    return None, None


# ============================================================
# UNIT EXTRACTION
# ============================================================

def extract_unit(product, size, detected_unit):
    if detected_unit:
        return detected_unit

    # Check raw unit fields
    for key in [
        "unit",
        "unit_name",
        "measurement_unit",
    ]:
        value = normalize_unit(product.get(key))

        if value:
            return value

    # Check names and URLs for packaging
    texts = [
        product.get("name_en"),
        product.get("name_ar"),
        product.get("url_en"),
        product.get("url_ar"),
    ]

    for text in texts:
        unit = extract_packaging_unit(text)

        if unit:
            return unit

    # If no size exists, many fresh products are sold as pieces
    # but only use this as a fallback.
    if size is None:
        return "unit"

    return None


# ============================================================
# PRICE / DISCOUNT
# ============================================================

def calculate_discount(price, regular_price):
    if price is None or regular_price is None:
        return 0.0

    if regular_price <= 0:
        return 0.0

    if regular_price <= price:
        return 0.0

    discount = ((regular_price - price) / regular_price) * 100

    return round(discount, 2)


def extract_prices(product):
    price = to_float(product.get("price"))

    original_price = to_float(
        product.get("original_price")
    )

    # Some APIs may have sale_price instead
    sale_price = to_float(
        product.get("sale_price")
    )

    if price is None and sale_price is not None:
        price = sale_price

    if original_price is None:
        original_price = price

    discount = calculate_discount(
        price,
        original_price,
    )

    return (
        price,
        original_price,
        discount,
    )


# ============================================================
# URL
# ============================================================

def build_url(product):
    url_en = clean_text(product.get("url_en"))
    url_ar = clean_text(product.get("url_ar"))

    url = url_en or url_ar

    if not url:
        return None

    if url.startswith("http://") or url.startswith("https://"):
        return url

    if url.startswith("/"):
        return "https://www.bindawood.sa" + url

    return "https://www.bindawood.sa/" + url


# ============================================================
# IMAGE
# ============================================================

def extract_image(product):
    possible_fields = [
        "image",
        "image_url",
        "image_urls",
        "images",
        "images_url",
    ]

    for field in possible_fields:
        value = product.get(field)

        if isinstance(value, str):
            value = value.strip()

            if value:
                return value

        if isinstance(value, list) and value:
            first = value[0]

            if isinstance(first, str):
                return first

            if isinstance(first, dict):
                for key in [
                    "url",
                    "src",
                    "image_url",
                ]:
                    image_url = first.get(key)

                    if image_url:
                        return image_url

    return None


# ============================================================
# PRODUCT TRANSFORMATION
# ============================================================

def transform_product(product):
    product_name_ar = clean_text(
        product.get("name_ar")
    )

    product_name_en = clean_text(
        product.get("name_en")
    )

    category_raw = clean_text(
        product.get("_category_key")
    )

    category = CATEGORY_MAP.get(
        category_raw,
        category_raw,
    )

    # --------------------------------------------------------
    # Brand
    # --------------------------------------------------------

    brand = extract_brand(product)

    # --------------------------------------------------------
    # Price
    # --------------------------------------------------------

    price, regular_price, discount = extract_prices(
        product
    )

    # --------------------------------------------------------
    # Size / Unit
    # --------------------------------------------------------

    size, detected_unit = extract_size_and_unit(
        product
    )

    unit = extract_unit(
        product,
        size,
        detected_unit,
    )

    # --------------------------------------------------------
    # Quantity
    # --------------------------------------------------------

    combined_text = " ".join(
        value
        for value in [
            product_name_en,
            product_name_ar,
            product.get("url_en"),
            product.get("url_ar"),
        ]
        if value
    )

    quantity = extract_quantity(
        combined_text,
        size=size,
        unit=unit,
    )

    # --------------------------------------------------------
    # Total Size
    # --------------------------------------------------------

    total_size = None

    if size is not None:
        if quantity is not None and quantity > 0:
            total_size = round(
                size * quantity,
                3,
            )
        else:
            total_size = size

    # --------------------------------------------------------
    # URL / Image
    # --------------------------------------------------------

    url = build_url(product)

    image = extract_image(product)

    # --------------------------------------------------------
    # Standardized output
    # --------------------------------------------------------

    return {
        "product_name_ar": product_name_ar,
        "product_name_en": product_name_en,
        "store": "BinDawood Online",
        "category": category,
        "price": price,
        "regular_price": regular_price,
        "discount": discount,
        "brand": brand,
        "size": size,
        "unit": unit,
        "quantity": quantity,
        "total_size": total_size,
        "url": url,
        "image": image,
    }


# ============================================================
# VALIDATION
# ============================================================

def is_valid_product(product):
    name_ar = product.get("product_name_ar")
    name_en = product.get("product_name_en")
    price = product.get("price")

    if not name_ar and not name_en:
        return False

    if price is None:
        return False

    return True


# ============================================================
# STATISTICS
# ============================================================

def print_statistics(products):
    total = len(products)

    if total == 0:
        return

    print()
    print("=" * 70)
    print("BINDAWOOD TRANSFORM STATISTICS")
    print("=" * 70)

    categories = {}

    for product in products:
        category = product.get("category")

        if category:
            categories[category] = (
                categories.get(category, 0) + 1
            )

    print()
    print("Category counts:")

    for category, count in categories.items():
        print(f"  {category}: {count}")

    # --------------------------------------------------------
    # Brand
    # --------------------------------------------------------

    brand_count = sum(
        1
        for product in products
        if product.get("brand")
    )

    print()
    print(
        f"Brands extracted: {brand_count}/{total} "
        f"({brand_count / total * 100:.1f}%)"
    )

    # --------------------------------------------------------
    # Size
    # --------------------------------------------------------

    size_count = sum(
        1
        for product in products
        if product.get("size") is not None
    )

    print(
        f"Sizes extracted: {size_count}/{total} "
        f"({size_count / total * 100:.1f}%)"
    )

    # --------------------------------------------------------
    # Unit
    # --------------------------------------------------------

    unit_count = sum(
        1
        for product in products
        if product.get("unit")
    )

    print(
        f"Units extracted: {unit_count}/{total} "
        f"({unit_count / total * 100:.1f}%)"
    )

    # --------------------------------------------------------
    # Quantity
    # --------------------------------------------------------

    quantity_count = sum(
        1
        for product in products
        if product.get("quantity") is not None
    )

    print(
        f"Quantities extracted: {quantity_count}/{total} "
        f"({quantity_count / total * 100:.1f}%)"
    )

    # --------------------------------------------------------
    # Total size
    # --------------------------------------------------------

    total_size_count = sum(
        1
        for product in products
        if product.get("total_size") is not None
    )

    print(
        f"Total sizes calculated: {total_size_count}/{total} "
        f"({total_size_count / total * 100:.1f}%)"
    )

    # --------------------------------------------------------
    # Discounts
    # --------------------------------------------------------

    discount_count = sum(
        1
        for product in products
        if product.get("discount", 0) > 0
    )

    print(
        f"Products on discount: {discount_count}/{total} "
        f"({discount_count / total * 100:.1f}%)"
    )

    print("=" * 70)


# ============================================================
# SAVE
# ============================================================

def save_processed_data(products):
    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    timestamped_file = os.path.join(
        OUTPUT_DIR,
        f"bindawood_clean_{timestamp}.json",
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            products,
            file,
            ensure_ascii=False,
            indent=2,
        )

    with open(
        timestamped_file,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            products,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print("=" * 70)
    print("BINDAWOOD TRANSFORM FINISHED")
    print("=" * 70)
    print(f"Clean products: {len(products)}")
    print(f"Latest file: {OUTPUT_FILE}")
    print(f"Timestamped file: {timestamped_file}")


# ============================================================
# MAIN
# ============================================================

def main():
    print()
    print("=" * 70)
    print("STARTING BINDAWOOD TRANSFORM")
    print("=" * 70)

    if not os.path.exists(INPUT_FILE):
        print()
        print("ERROR: Raw Bindawood file not found:")
        print(INPUT_FILE)
        return

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        raw_data = json.load(file)

    raw_products = raw_data.get("hits", [])

    print(
        f"Loaded {len(raw_products)} raw products"
    )

    processed_products = []

    for raw_product in raw_products:
        try:
            clean_product = transform_product(
                raw_product
            )

            if is_valid_product(clean_product):
                processed_products.append(
                    clean_product
                )

        except Exception as error:
            print(
                "WARNING: Failed to transform product:",
                error,
            )

    print_statistics(
        processed_products
    )

    save_processed_data(
        processed_products
    )


if __name__ == "__main__":
    main()