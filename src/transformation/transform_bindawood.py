from __future__ import annotations

import json
import os
import re
from collections import Counter
from datetime import datetime


# ============================================================
# CONFIG / PATHS
# ============================================================

ROOT = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

INPUT_FILE = os.path.join(
    ROOT,
    "data",
    "raw",
    "stores",
    "bindawood",
    "bindawood_raw_latest.json",
)

OUTPUT_DIR = os.path.join(
    ROOT,
    "data",
    "processed",
    "stores",
    "bindawood",
)

LATEST_OUTPUT_FILE = os.path.join(
    OUTPUT_DIR,
    "bindawood_clean_latest.json",
)

CATEGORY_MAP = {
    "fruits_vegetables": "fruits-vegetables",
    "fruits-vegetables": "fruits-vegetables",
    "dairy": "dairy",
    "beverages": "beverages",
    "water-beverages": "beverages",
}

KNOWN_BRANDS = [
    "Florida's Natural", "The Ginger People", "Al Qasim Produce",
    "Philippine Brand", "La Vache Qui Rit", "Solan de Cabras",
    "The Three Cows", "Orient Gardens", "Cathedral City", "Philadelphia",
    "Mountain Dew", "S.Pellegrino", "Vitamin Well", "Power Horse",
    "Rude Health", "Driscoll's", "Martinelli", "Natureland", "Capri-Sun",
    "Dr.Pepper", "Coca Cola", "Starbucks", "President", "Schweppes",
    "Sun Blast", "Barbican", "Sunbulah", "Vitamizu", "Cofrutos",
    "Heineken", "Code Red", "Cacaolat", "Victoria", "Al Rabie",
    "Valbreso", "Rubicon", "Landana", "Actimel", "Belvoir", "Halwani",
    "Danette", "Forsana", "Perrier", "Mirinda", "Activia", "Babybel",
    "Beltion", "Mishkat", "Violife", "Almarai", "Al Safi", "Juhayna",
    "Caesar", "Suntop", "Balade", "Puvana", "Saudia", "Twisst", "Berain",
    "Lurpak", "Sprite", "Rockit", "Moussy", "Klasse", "Scotti", "Lipton",
    "Rauch", "Nerve", "Sante", "Vimto", "Milaf", "Nadec", "Ultra",
    "Pepsi", "Kraft", "Pinar", "Kinza", "Frico", "Yopro", "Safio",
    "Fanta", "Koita", "Akoya", "Vinut", "Twist", "Hotly", "Orasi",
    "Bonny", "Queen", "Monin", "Oatly", "Prime", "Pride", "Alpro",
    "Spada", "Evian", "Regal", "Danao", "Luna", "Nova", "Dari", "RARE",
    "Arwa", "Oska", "Rita", "Safa", "Kiri", "Puck", "Fifa", "Alsi",
    "Goro", "Noug", "Arla", "Nada", "7 Up", "Rani", "Zoi", "OKF", "May",
    "KDD", "Danube", "Original", "Rockstar", "Juicy", "Danya", "Shani",
    "Legero", "Senac", "Disfruta", "Canada", "Anchor",
    "A&W", "Acqua Panna", "ADY Elixirs", "Al Ain", "Al Bayan",
    "Al Madinah", "Al Sawsan", "Al Tashilat", "Al-Amri", "Alaska",
    "Algharbia Farms", "Aqua Verde", "Aquafina", "Ava", "B Cola",
    "Bambini", "Barebells", "Baskin Robbins", "Beypazari", "Blonde 22K",
    "Bowl & Basket", "Britvic", "Cadbury", "Calzetti", "Carl Jung",
    "Carlsberg", "Cheestrings", "Chris Family", "Christis", "Chupa Chups",
    "Cocomax", "Coconaut", "Cofique", "Cojo Cojo", "Corona", "Crush",
    "Daisy", "Damas", "Danablu", "Dava", "Desperados", "Domty",
    "Don Simon", "Dunkin'", "Ease", "El Capitán", "Elecio", "Elle & Vire",
    "Ensure", "Entaj", "Espadafor", "Fakieh", "Farm Harvest", "Fever Tree",
    "Fiji", "Fizzy Wizzy", "Flora", "FoodSaf", "Foody's",
    "Foster Clark's", "Freshly", "Galaxy", "Gatorade", "Glebe Farm",
    "Golden Chair", "Goya", "Graham's Family Dairy", "Granarolo",
    "Granini", "Grante", "Hajdu", "Hamdard", "Hass To Be Hass",
    "Hata Kosen", "Henri Willig", "Holsten", "Hotos",
    "Isigny Sainte-Mère", "It's Water", "Ival", "Jam-E-Shirin",
    "Jumi Jumi", "Jwod", "Kafy", "Kasih", "Kerrygold", "Kwality",
    "La Tansa", "Lavi", "Leemo-1", "Life WTR", "Limolife", "Linda",
    "Lite", "Mahou", "Maison Perrier", "Maxim's", "Mixa", "Mojan Farms",
    "Moma", "Mondariz", "Monster", "Muller", "Naqa'a", "Naqwat Alnanaa",
    "Nescafe", "Nestlé", "Nyssa", "Ocean Spray", "Originz",
    "Perfectly Pressed", "Port Salut", "Pristine", "Rachel's", "Rahima",
    "Rain", "Rainbow", "Raw Pressery", "Red Bull", "Robinsons", "Rudolfs",
    "Saha", "Salik", "Sanpellegrino", "Sant Aniol", "Shahela",
    "Slush Puppie", "Sobia Musbah khudary", "Souroti", "Star Soda",
    "Sting", "Stream", "Suncola", "Tang", "Tango", "Tania", "Tessa",
    "The Premium Harvest", "Tim Hortons", "Tono", "Towt", "Tropicana",
    "UP2U", "Ursu", "VaiWai", "Vendôme", "Vinola", "Volvic", "Voss",
    "Wadan", "Waw", "Wholesome Pantry", "Zamzam",
]

KNOWN_BRANDS_SORTED = sorted(
    set(KNOWN_BRANDS),
    key=len,
    reverse=True,
)


# ============================================================
# BASIC HELPERS
# ============================================================

def clean_text(value):
    if value is None:
        return None

    value = " ".join(str(value).split()).strip()
    return value or None


def to_float(value):
    if value is None or isinstance(value, bool):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_spaces(text):
    if not text:
        return None

    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?)])", r"\1", text)
    text = re.sub(r"([(])\s+", r"\1", text)
    return text or None


# ============================================================
# BRAND / NAME CLEANING
# ============================================================

def extract_brand(product, name_en):
    for key in (
        "brand_en",
        "brand_ar",
        "brand",
        "brand_name",
        "manufacturer",
        "manufacturer_name",
    ):
        value = clean_text(product.get(key))
        if value:
            return value

    if not name_en:
        return None

    name_lower = name_en.casefold()

    for brand in KNOWN_BRANDS_SORTED:
        if name_lower.startswith(brand.casefold()):
            return brand

    return None


def remove_brand_from_name_en(name_en, brand):
    if not name_en or not brand:
        return name_en

    pattern = rf"^\s*{re.escape(brand)}(?=\s|[-–—,:;/]|$)\s*"
    return normalize_spaces(re.sub(pattern, "", name_en, flags=re.IGNORECASE))


def remove_brand_from_name_ar(name_ar, brand):
    """
    لا نحذف العلامة من العربي إلا إذا كانت العلامة نفسها مكتوبة
    بالحروف العربية داخل الاسم. لا نترجم أو نخمن اسم العلامة.
    """
    if not name_ar or not brand:
        return name_ar

    pattern = rf"^\s*{re.escape(brand)}(?=\s|[-–—,:;/]|$)\s*"
    return normalize_spaces(re.sub(pattern, "", name_ar, flags=re.IGNORECASE))


def remove_size_and_quantity(name):
    """
    Remove only explicit size/measurement and multipack expressions.
    Does not remove descriptive wording such as '(Tray)' when it has
    no numeric quantity.
    """
    if not name:
        return name

    number = r"[0-9٠-٩]+(?:[.,][0-9٠-٩]+)?"
    unit = (
        r"(?:ml|milliliter(?:s)?|millilitre(?:s)?|"
        r"l|ltr|liter(?:s)?|litre(?:s)?|"
        r"kg|kilogram(?:s)?|kilo(?:s)?|"
        r"g|gm|gr|gram(?:s)?|mg|milligram(?:s)?|"
        r"oz|ounce(?:s)?|"
        r"مل|ملي(?:لتر)?|لتر|لترات|كجم|كغ|كغم|كيلو(?:غرام)?|"
        r"غرام|جرام|غ|ملغ|مجم)"
    )

    # Examples: 3*6*125ml, 24 x 125 ml, 6×330ml.
    multipack = (
        rf"\b{number}\s*[x×*]\s*"
        rf"(?:{number}\s*[x×*]\s*)*"
        rf"{number}\s*{unit}\b"
    )

    # Examples: 700g, 150 g, ١٥٠غرام, 1.5 kg.
    single_size = rf"\b{number}\s*{unit}\b"

    # Examples: 6 pack, 12 bottles, 24 cans, ٦ عبوات, ١٢ حبة.
    counted_packaging = (
        rf"\b{number}\s*"
        r"(?:pack(?:s)?|bottle(?:s)?|can(?:s)?|jar(?:s)?|"
        r"piece(?:s)?|pcs?|pc|box(?:es)?|bag(?:s)?|"
        r"عبوات?|زجاجات?|علب(?:ة)?|حبات?|قطع(?:ة)?)\b"
    )

    text = name
    text = re.sub(multipack, " ", text, flags=re.IGNORECASE)
    text = re.sub(single_size, " ", text, flags=re.IGNORECASE)
    text = re.sub(counted_packaging, " ", text, flags=re.IGNORECASE)

    # Remove separators left after measurement deletion only.
    text = re.sub(r"\s*[-–—*/×x]\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*[-–—*/×x]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()

    return normalize_spaces(text)


def clean_display_names(name_ar, name_en, brand):
    original_ar = name_ar
    original_en = name_en

    name_en = remove_brand_from_name_en(name_en, brand)
    name_en = remove_size_and_quantity(name_en)

    name_ar = remove_brand_from_name_ar(name_ar, brand)
    name_ar = remove_size_and_quantity(name_ar)

    # Never create an empty display name.
    return (
        name_ar or original_ar,
        name_en or original_en,
    )


# ============================================================
# SIZE / QUANTITY
# ============================================================

def normalize_unit(unit):
    if not unit:
        return None

    unit = unit.casefold()

    mapping = {
        "milliliter": "ml", "milliliters": "ml",
        "millilitre": "ml", "millilitres": "ml",
        "ltr": "l", "liter": "l", "litre": "l",
        "liters": "l", "litres": "l",
        "kilogram": "kg", "kilograms": "kg",
        "kilo": "kg", "kilos": "kg",
        "gm": "g", "gr": "g", "gram": "g", "grams": "g",
        "milligram": "mg", "milligrams": "mg",
    }

    return mapping.get(unit, unit)


def extract_size_and_unit(name_en, name_ar, product):
    texts = [
        name_en,
        name_ar,
        clean_text(product.get("full_name_en")),
        clean_text(product.get("full_name_ar")),
        clean_text(product.get("name_en")),
        clean_text(product.get("name_ar")),
        clean_text(product.get("url_en")),
        clean_text(product.get("url_ar")),
    ]

    unit_pattern = (
        r"(ml|milliliter|milliliters|millilitre|millilitres|"
        r"ltr|liter|litre|liters|litres|"
        r"kg|kilogram|kilograms|kilo|"
        r"g|gm|gr|gram|grams|"
        r"mg|milligram|milligrams|"
        r"oz|ounce|ounces)"
    )

    for text in texts:
        if not text:
            continue

        matches = re.findall(
            rf"(\d+(?:\.\d+)?)\s*{unit_pattern}\b",
            text,
            flags=re.IGNORECASE,
        )

        if matches:
            size, unit = matches[-1]
            return float(size), normalize_unit(unit)

    return None, None


def extract_quantity(text):
    if not text:
        return 1

    text = text.lower()

    match = re.search(
        r"\b(\d+)\s*[x×*]\s*(\d+)\s*[x×*]\s*"
        r"\d+(?:\.\d+)?\s*(?:kg|g|mg|l|ml)\b",
        text,
    )
    if match:
        return int(match.group(1)) * int(match.group(2))

    match = re.search(
        r"\b(\d+)\s*[x×*]\s*"
        r"\d+(?:\.\d+)?\s*(?:kg|g|mg|l|ml)\b",
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
# PRICE / DISCOUNT
# ============================================================

def calculate_discount(price, regular_price):
    if price is None or regular_price is None or regular_price <= 0:
        return None

    if regular_price <= price:
        return 0.0

    return round((regular_price - price) / regular_price * 100, 2)


def is_sale_modifier(modifier):
    price = to_float(modifier.get("price"))
    original_price = to_float(modifier.get("original_price"))

    return (
        modifier.get("on_sale") is True
        or (
            price is not None
            and original_price is not None
            and original_price > price
        )
    )


def representative_price_from_modifiers(product):
    modifiers = product.get("inventory_modifiers")

    if not isinstance(modifiers, dict):
        return None, None

    records = [
        item
        for item in modifiers.values()
        if isinstance(item, dict)
        and to_float(item.get("price")) is not None
        and item.get("available") is not False
        and item.get("in_stock") is not False
    ]

    if not records:
        return None, None

    sale_records = [
        item
        for item in records
        if is_sale_modifier(item)
    ]

    # Promotions are preferred: non-sale Makkah branches are ignored.
    candidates = sale_records or records

    states = [
        (
            to_float(item.get("price")),
            to_float(item.get("original_price")),
        )
        for item in candidates
    ]

    price, original_price = Counter(states).most_common(1)[0][0]

    return price, original_price


def extract_prices(product):
    # Prefer branch-level sale data from the raw snapshot.
    price, original_price = representative_price_from_modifiers(product)

    if price is None:
        price = to_float(product.get("real_price"))
        original_price = to_float(product.get("real_original_price"))

    if price is None:
        price = to_float(product.get("price"))
        original_price = to_float(product.get("original_price"))

    regular_price = (
        original_price
        if original_price is not None and original_price > price
        else price
    )

    return (
        price,
        regular_price,
        calculate_discount(price, regular_price),
    )


# ============================================================
# URL / IMAGE
# ============================================================

def build_url(product):
    url = clean_text(product.get("url_en")) or clean_text(product.get("url_ar"))

    if not url:
        return None

    if url.startswith(("https://", "http://")):
        return url

    return f"https://www.bindawood.sa{url if url.startswith('/') else '/' + url}"


def extract_image(product):
    image = product.get("image")

    if isinstance(image, str) and image.strip():
        return image.strip()

    for key in ("image_url", "image_urls", "images", "images_url"):
        value = product.get(key)

        if isinstance(value, list) and value:
            value = value[0]

        if isinstance(value, str) and value.strip():
            return value.strip()

        if isinstance(value, dict):
            for image_key in ("url", "src", "image_url"):
                image = clean_text(value.get(image_key))
                if image:
                    return image

    return None


# ============================================================
# TRANSFORM
# ============================================================

def transform_product(product):
    original_name_ar = (
        clean_text(product.get("full_name_ar"))
        or clean_text(product.get("name_ar"))
    )

    original_name_en = (
        clean_text(product.get("full_name_en"))
        or clean_text(product.get("name_en"))
    )

    if not original_name_ar and not original_name_en:
        return None

    brand = extract_brand(product, original_name_en)

    size, detected_unit = extract_size_and_unit(
        original_name_en,
        original_name_ar,
        product,
    )

    combined_text = " ".join(
        text
        for text in (
            original_name_en,
            original_name_ar,
            clean_text(product.get("url_en")),
            clean_text(product.get("url_ar")),
        )
        if text
    )

    quantity = extract_quantity(combined_text)

    product_name_ar, product_name_en = clean_display_names(
        original_name_ar,
        original_name_en,
        brand,
    )

    price, regular_price, discount = extract_prices(product)

    if price is None:
        return None

    return {
        "product_name_ar": product_name_ar,
        "product_name_en": product_name_en,
        "store": "Bindawood Online",
        "category": CATEGORY_MAP.get(
            clean_text(product.get("_category_key")),
            clean_text(product.get("_category_key")),
        ),
        "price": price,
        "regular_price": regular_price,
        "discount": discount,
        "brand": brand,
        "size": size,
        "unit": detected_unit or "unit",
        "quantity": quantity,
        "total_size": round(size * quantity, 3) if size is not None else None,
        "url": build_url(product),
        "image": extract_image(product),
    }


def load_raw_products():
    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(f"Raw file not found:\n{INPUT_FILE}")

    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        raw_data = json.load(file)

    hits = raw_data.get("hits") or []

    if not isinstance(hits, list):
        raise ValueError("Expected a list under `hits` in the raw JSON file.")

    return hits


def save_processed_data(products):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    result = {
        "store": "Bindawood Online",
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "categories": {
            category: sum(
                product.get("category") == category
                for product in products
            )
            for category in ("fruits-vegetables", "dairy", "beverages")
        },
        "records_count": len(products),
        "records": products,
    }

    timestamped_file = os.path.join(
        OUTPUT_DIR,
        f"bindawood_clean_{timestamp}.json",
    )

    for output_file in (LATEST_OUTPUT_FILE, timestamped_file):
        with open(output_file, "w", encoding="utf-8") as file:
            json.dump(result, file, ensure_ascii=False, indent=2)

    return timestamped_file


def main():
    print("=" * 60)
    print("STARTING BINDAWOOD TRANSFORM")
    print("=" * 60)

    raw_products = load_raw_products()
    processed_products = []

    for product in raw_products:
        if not isinstance(product, dict):
            continue

        try:
            record = transform_product(product)

            if record:
                processed_products.append(record)

        except Exception as error:
            print(f"WARNING: Failed to transform product: {error}")

    output_file = save_processed_data(processed_products)

    brands_found = sum(
        product.get("brand") is not None
        for product in processed_products
    )
    sizes_found = sum(
        product.get("size") is not None
        for product in processed_products
    )
    deals_found = sum(
        (product.get("discount") or 0) > 0
        for product in processed_products
    )

    print(f"Raw products: {len(raw_products)}")
    print(f"Clean products: {len(processed_products)}")
    print(f"Brands found: {brands_found}/{len(processed_products)}")
    print(f"Sizes found: {sizes_found}/{len(processed_products)}")
    print(f"Products on sale: {deals_found}/{len(processed_products)}")
    print(f"Latest: {LATEST_OUTPUT_FILE}")
    print(f"Timestamped: {output_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()