"""Danube data TRANSFORM step.

Reads:
    data/raw/stores/danube/danube_raw_latest.json

Writes:
    data/processed/stores/danube/danube_clean_<timestamp>.json
    data/processed/stores/danube/danube_clean_latest.json

No network calls are made here.

Pricing:
- Uses `real_price` / `real_original_price` when they are present.
- Falls back to the top-level price fields for older raw snapshots.

Display names:
- `brand`, `size`, `unit`, and `quantity` stay in separate columns.
- The displayed Arabic/English product names have the extracted brand and
  explicit size / multipack expression removed where possible.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import pandas as pd


# ============================================================
# CONFIG
# ============================================================


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


# Explicit Arabic aliases only. Add a brand here only when you are sure of
# its official Arabic spelling. This avoids translating or guessing names.
ARABIC_BRAND_ALIASES = {
    "Almarai": ["المراعي"],
    "Nadec": ["نادك"],
    "Nada": ["ندى"],
    "Saudia": ["السعودية"],
    "KDD": ["كي دي دي", "كي دي دي"],
    "Al Safi": ["الصافي"],
    "Al Rabie": ["الربيع"],
    "Lurpak": ["لورباك"],
    "Puck": ["بوك"],
    "Kiri": ["كيري"],
    "Arla": ["أرلا"],
    "Pepsi": ["بيبسي"],
    "Coca Cola": ["كوكا كولا"],
    "Fanta": ["فانتا"],
    "Sprite": ["سبرايت"],
    "Schweppes": ["شويبس"],
    "Lipton": ["ليبتون"],
    "Nescafe": ["نسكافيه"],
    "Nestlé": ["نستله", "نستلي"],
    "Red Bull": ["ريد بول"],
    "Monster": ["مونستر"],
    "Tropicana": ["تروبيكانا"],
    "Tang": ["تانج"],
    "Vimto": ["فيمتو"],
    "Rani": ["راني"],
    "Barbican": ["باربيكان"],
    "Berain": ["بيرين"],
    "Aquafina": ["أكوافينا"],
    "Evian": ["إيفيان"],
    "Volvic": ["فولفيك"],
    "Voss": ["فوس"],
    "Perrier": ["بيرييه"],
    "Al Ain": ["العين"],
    "Alaska": ["ألاسكا"],
    "Anchor": ["أنكور"],
    "Cadbury": ["كادبوري"],
    "Galaxy": ["جالكسي"],
    "Kraft": ["كرافت"],
    "Philadelphia": ["فيلادلفيا"],
    "President": ["بريزيدن"],
    "Danette": ["دانونيت"],
    "Activia": ["أكتيفيا"],
    "Actimel": ["أكتيميل"],
    "Babybel": ["بيبي بيل"],
}


UNIT_PATTERN = (
    r"(ml|milliliter|milliliters|millilitre|millilitres|"
    r"ltr|l|liter|litre|liters|litres|"
    r"kg|kilogram|kilograms|kilo|"
    r"g|gm|gr|gram|grams|"
    r"mg|milligram|milligrams|"
    r"pcs|pc|piece|pieces|pack|packs|oz|ounce|ounces)"
)

PATTERN_QTY_FIRST = re.compile(
    rf"(\d+)\s*[x×*]\s*(\d+(?:\.\d+)?)\s*{UNIT_PATTERN}\b",
    re.IGNORECASE,
)

PATTERN_SIZE_FIRST = re.compile(
    rf"(\d+(?:\.\d+)?)\s*{UNIT_PATTERN}\s*[x×*]\s*(\d+)\b",
    re.IGNORECASE,
)

SINGLE_SIZE_PATTERN = re.compile(
    rf"(\d+(?:\.\d+)?)\s*{UNIT_PATTERN}\b",
    re.IGNORECASE,
)


# ============================================================
# PATHS
# ============================================================


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def raw_input_path() -> Path:
    return (
        project_root()
        / "data"
        / "raw"
        / "stores"
        / "danube"
        / "danube_raw_latest.json"
    )


def processed_output_dir() -> Path:
    path = (
        project_root()
        / "data"
        / "processed"
        / "stores"
        / "danube"
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


# ============================================================
# BASIC HELPERS
# ============================================================


def clean_text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, float) and pd.isna(value):
        return ""

    return " ".join(str(value).split()).strip()


def safe_float(value: Any) -> float | None:
    if value in (None, "", "null"):
        return None

    if isinstance(value, float) and pd.isna(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_unit(unit: str | None) -> str | None:
    if not unit:
        return None

    mapping = {
        "milliliter": "ml",
        "milliliters": "ml",
        "millilitre": "ml",
        "millilitres": "ml",
        "ltr": "l",
        "liter": "l",
        "litre": "l",
        "liters": "l",
        "litres": "l",
        "kilogram": "kg",
        "kilograms": "kg",
        "kilo": "kg",
        "gm": "g",
        "gr": "g",
        "gram": "g",
        "grams": "g",
        "milligram": "mg",
        "milligrams": "mg",
        "pc": "pcs",
        "piece": "pcs",
        "pieces": "pcs",
        "packs": "pack",
        "ounce": "oz",
        "ounces": "oz",
    }

    return mapping.get(unit.lower(), unit.lower())


# ============================================================
# BRAND / DISPLAY-NAME CLEANING
# ============================================================


def extract_brand(name_en: str) -> str | None:
    """Return a known brand only when it begins the English product name."""
    if not name_en:
        return None

    name_casefold = name_en.casefold()

    for brand in KNOWN_BRANDS_SORTED:
        if name_casefold.startswith(brand.casefold()):
            return brand

    return None


def tidy_name(text: str) -> str:
    """Remove spacing and separators left behind after token deletion."""
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"^\s*[-–—,;:/|*×x]+\s*", "", text)
    text = re.sub(r"\s*[-–—,;:/|*×x]+\s*$", "", text)
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\[\s*\]", "", text)

    return text.strip()


def remove_brand_from_name_en(name_en: str, brand: str | None) -> str:
    """Remove only an initial English brand label."""
    if not name_en or not brand:
        return name_en

    pattern = rf"^\s*{re.escape(brand)}(?=\s|[-–—,:;/]|$)\s*"

    return tidy_name(
        re.sub(
            pattern,
            "",
            name_en,
            flags=re.IGNORECASE,
        )
    )


def remove_brand_from_name_ar(name_ar: str, brand: str | None) -> str:
    """Remove an Arabic brand only if a declared alias starts the name."""
    if not name_ar or not brand:
        return name_ar

    aliases = ARABIC_BRAND_ALIASES.get(brand, [])

    for alias in aliases:
        pattern = rf"^\s*{re.escape(alias)}(?=\s|[-–—,:;/]|$)\s*"

        cleaned = re.sub(
            pattern,
            "",
            name_ar,
            flags=re.IGNORECASE,
        )

        if cleaned != name_ar:
            return tidy_name(cleaned)

    return name_ar


def remove_size_and_quantity(name: str) -> str:
    """Remove explicit size and numeric multipack fragments from a name.

    It deliberately does not remove packaging words without a number:
    `(Tray)` stays, while `6 pack` or `24*125ml` is removed.
    """
    if not name:
        return name

    # Supports Latin and Arabic/Hindi digits.
    number = r"[0-9٠-٩]+(?:[.,][0-9٠-٩]+)?"

    english_unit = (
        r"(?:ml|milliliter(?:s)?|millilitre(?:s)?|"
        r"l|ltr|liter(?:s)?|litre(?:s)?|"
        r"kg|kilogram(?:s)?|kilo(?:s)?|"
        r"g|gm|gr|gram(?:s)?|"
        r"mg|milligram(?:s)?|"
        r"oz|ounce(?:s)?)"
    )

    arabic_unit = (
        r"(?:مل|ملي(?:لتر)?|لتر|لترات|"
        r"كجم|كغ|كغم|كيلو(?:غرام)?|"
        r"غرام|جرام|غ|ملغ|مجم)"
    )

    unit = rf"(?:{english_unit}|{arabic_unit})"

    # Examples: 24*125ml, 3x6x125 ml, ٣×٦×١٢٥مل.
    multipack_pattern = (
        rf"{number}\s*[x×*]\s*"
        rf"(?:{number}\s*[x×*]\s*)*"
        rf"{number}\s*{unit}"
    )

    # Examples: 700g, 150 g, ١٥٠غرام, 1.5 kg.
    size_pattern = rf"{number}\s*{unit}"

    # Examples: 6 pack, 24 bottles, ٦ عبوات, ١٢ حبة.
    counted_packaging_pattern = (
        rf"{number}\s*"
        r"(?:pack(?:s)?|bottle(?:s)?|can(?:s)?|jar(?:s)?|"
        r"piece(?:s)?|pcs?|pc|box(?:es)?|bag(?:s)?|"
        r"عبوات?|زجاجات?|علب(?:ة)?|حبات?|قطع(?:ة)?)"
    )

    cleaned = re.sub(
        multipack_pattern,
        " ",
        name,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        size_pattern,
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        counted_packaging_pattern,
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )

    return tidy_name(cleaned)


def clean_display_names(
    name_ar: str,
    name_en: str,
    brand: str | None,
) -> tuple[str, str]:
    """Return display names without extracted brand, size, or pack count."""
    original_ar = name_ar
    original_en = name_en

    name_en = remove_brand_from_name_en(name_en, brand)
    name_en = remove_size_and_quantity(name_en)

    name_ar = remove_brand_from_name_ar(name_ar, brand)
    name_ar = remove_size_and_quantity(name_ar)

    # Never create an empty display label.
    return (
        name_ar or original_ar,
        name_en or original_en,
    )


# ============================================================
# PACK SIZE / QUANTITY
# ============================================================


def extract_pack_size(name_en: str) -> tuple[float | None, str | None, int]:
    """Extract size, normalized unit, and pack quantity from English name."""
    if not name_en:
        return None, None, 1

    match = PATTERN_QTY_FIRST.search(name_en)

    if match:
        quantity, size_str, unit = match.groups()
        return float(size_str), normalize_unit(unit), int(quantity)

    match = PATTERN_SIZE_FIRST.search(name_en)

    if match:
        size_str, unit, quantity = match.groups()
        return float(size_str), normalize_unit(unit), int(quantity)

    # Supports chains such as 3*6*125ml -> size=125, quantity=18.
    match = re.search(
        rf"\b(\d+)\s*[x×*]\s*(\d+)\s*[x×*]\s*"
        rf"(\d+(?:\.\d+)?)\s*{UNIT_PATTERN}\b",
        name_en,
        flags=re.IGNORECASE,
    )

    if match:
        first_quantity, second_quantity, size_str, unit = match.groups()

        return (
            float(size_str),
            normalize_unit(unit),
            int(first_quantity) * int(second_quantity),
        )

    matches = SINGLE_SIZE_PATTERN.findall(name_en)

    if matches:
        size_str, unit = matches[-1]
        return float(size_str), normalize_unit(unit), 1

    return None, None, 1


# ============================================================
# PRICE / URL
# ============================================================


def calculate_discount(
    price: float | None,
    regular_price: float | None,
) -> float | None:
    if price is None or regular_price is None:
        return None

    if regular_price <= 0 or regular_price <= price:
        return 0.0

    return round(
        (regular_price - price) / regular_price * 100,
        2,
    )


def build_product_url(row: pd.Series) -> str | None:
    url_en = row.get("url_en")
    url_ar = row.get("url_ar")

    if isinstance(url_en, str) and url_en.startswith("/"):
        return f"https://www.danube.sa{url_en}"

    if isinstance(url_en, str) and url_en:
        return url_en

    if isinstance(url_ar, str) and url_ar.startswith("/"):
        return f"https://www.danube.sa{url_ar}"

    return url_ar if isinstance(url_ar, str) else None


# ============================================================
# LOAD / TRANSFORM
# ============================================================


def load_raw_hits() -> pd.DataFrame:
    raw_path = raw_input_path()

    if not raw_path.exists():
        raise FileNotFoundError(
            f"Raw file not found: {raw_path}\n"
            "Run extract_danube_raw.py first."
        )

    data = json.loads(
        raw_path.read_text(
            encoding="utf-8",
        )
    )

    hits = data.get("hits") or []

    print(
        f"Loaded {len(hits)} raw hits from "
        f"{raw_path.name}"
    )

    return pd.DataFrame(hits)


def transform(df: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []

    for _, row in df.iterrows():
        product = row.to_dict()

        source_name_ar = (
            clean_text(product.get("full_name_ar"))
            or clean_text(product.get("name_ar"))
        )

        source_name_en = (
            clean_text(product.get("full_name_en"))
            or clean_text(product.get("name_en"))
        )

        if not source_name_ar and not source_name_en:
            continue

        brand = extract_brand(source_name_en)

        # Extract structured attributes from original source names first.
        size, unit, quantity = extract_pack_size(source_name_en)

        # Then create a concise display name with duplicate information gone.
        product_name_ar, product_name_en = clean_display_names(
            source_name_ar,
            source_name_en,
            brand,
        )

        if "real_price" in df.columns:
            real_price = safe_float(product.get("real_price"))
            top_level_price = safe_float(product.get("price"))
            price = (
                real_price
                if real_price is not None
                else top_level_price
            )
        else:
            price = safe_float(product.get("price"))

        if "real_original_price" in df.columns:
            real_original_price = safe_float(
                product.get("real_original_price")
            )
            top_level_original_price = safe_float(
                product.get("original_price")
            )
            original_price = (
                real_original_price
                if real_original_price is not None
                else top_level_original_price
            )
        else:
            original_price = safe_float(
                product.get("original_price")
            )

        if price is None:
            continue

        regular_price = (
            original_price
            if original_price is not None
            and original_price > price
            else price
        )

        records.append(
            {
                "product_name_ar": product_name_ar,
                "product_name_en": product_name_en,
                "store": "Danube Online",
                "category": clean_text(
                    product.get("_category_key")
                ),
                "price": price,
                "regular_price": regular_price,
                "discount": calculate_discount(
                    price,
                    regular_price,
                ),
                "brand": brand,
                "size": size,
                "unit": unit or "unit",
                "quantity": quantity,
                "total_size": (
                    round(size * quantity, 3)
                    if size is not None
                    else None
                ),
                "url": build_product_url(row),
                "image": clean_text(
                    product.get("image")
                ) or None,
            }
        )

    columns = [
        "product_name_ar",
        "product_name_en",
        "store",
        "category",
        "price",
        "regular_price",
        "discount",
        "brand",
        "size",
        "unit",
        "quantity",
        "total_size",
        "url",
        "image",
    ]

    return pd.DataFrame(records, columns=columns)


# ============================================================
# SAVE / MAIN
# ============================================================


def save_clean_file(df: pd.DataFrame) -> Path:
    timestamp = time.strftime(
        "%Y%m%d_%H%M%S",
        time.gmtime(),
    )

    result = {
        "store": "Danube Online",
        "generated_at": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime(),
        ),
        "categories": (
            df["category"].value_counts().to_dict()
            if not df.empty
            else {}
        ),
        "records_count": len(df),
        "records": json.loads(
            df.to_json(
                orient="records",
                force_ascii=False,
            )
        ),
    }

    output_dir = processed_output_dir()

    timestamped_path = (
        output_dir
        / f"danube_clean_{timestamp}.json"
    )

    latest_path = (
        output_dir
        / "danube_clean_latest.json"
    )

    serialized = json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
    )

    timestamped_path.write_text(
        serialized,
        encoding="utf-8",
    )

    latest_path.write_text(
        serialized,
        encoding="utf-8",
    )

    return timestamped_path


def transform_danube() -> pd.DataFrame:
    print("=" * 60)
    print("STARTING DANUBE TRANSFORM (pandas, no network calls)")
    print("=" * 60)

    raw_df = load_raw_hits()
    clean_df = transform(raw_df)
    output_path = save_clean_file(clean_df)

    print("\n" + "=" * 60)
    print("DANUBE TRANSFORM FINISHED")
    print("=" * 60)

    if clean_df.empty:
        print("No valid products were generated.")
        return clean_df

    print(clean_df["category"].value_counts().to_string())
    print(f"  Total: {len(clean_df)} products")

    brands_found = clean_df["brand"].notna().sum()
    sizes_found = clean_df["size"].notna().sum()
    deals_found = (clean_df["discount"] > 0).sum()

    print(
        f"  Brands extracted: {brands_found}/{len(clean_df)} "
        f"({brands_found / len(clean_df) * 100:.1f}%)"
    )
    print(
        f"  Sizes extracted: {sizes_found}/{len(clean_df)} "
        f"({sizes_found / len(clean_df) * 100:.1f}%)"
    )
    print(
        f"  Products on discount: {deals_found}/{len(clean_df)} "
        f"({deals_found / len(clean_df) * 100:.1f}%)"
    )
    print(f"  File: {output_path}")

    return clean_df


if __name__ == "__main__":
    transform_danube()