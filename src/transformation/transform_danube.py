"""Danube data TRANSFORM step (cleaning, brand + pack size parsing).

Reads the raw snapshot produced by extract_danube_raw.py
(data/raw/stores/danube/danube_raw_latest.json) and produces a cleaned,
analysis-ready dataset using pandas.

Output: data/processed/stores/danube/danube_clean_<timestamp>.json
        data/processed/stores/danube/danube_clean_latest.json

Re-run this file any time the cleaning logic (brand list, unit patterns,
discount rules) changes -- NO network calls, NO re-scraping needed.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import pandas as pd

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
    "Beltion", "Mishkat", "Violife", "Almarai", "Al Safi", "juhayna",
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
    "Legero", "Senac", "Disfruta", "Canada",
]
KNOWN_BRANDS_SORTED = sorted(KNOWN_BRANDS, key=len, reverse=True)

UNIT_PATTERN = r'(ml|milliliter|ltr|l|liter|litre|kg|kilogram|g|gm|gr|gram|pcs|pack|oz|ounce)'

PATTERN_QTY_FIRST = re.compile(
    rf'(\d+)\s*[x×*]\s*(\d+(?:\.\d+)?)\s*{UNIT_PATTERN}\b', re.IGNORECASE,
)
PATTERN_SIZE_FIRST = re.compile(
    rf'(\d+(?:\.\d+)?)\s*{UNIT_PATTERN}\s*[x×*]\s*(\d+)\b', re.IGNORECASE,
)
SINGLE_SIZE_PATTERN = re.compile(
    rf'(\d+(?:\.\d+)?)\s*{UNIT_PATTERN}\b', re.IGNORECASE,
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def raw_input_path() -> Path:
    return project_root() / "data" / "raw" / "stores" / "danube" / "danube_raw_latest.json"


def processed_output_dir() -> Path:
    path = project_root() / "data" / "processed" / "stores" / "danube"
    path.mkdir(parents=True, exist_ok=True)
    return path


def clean_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return " ".join(str(value).split()).strip()


def safe_float(value: Any) -> float | None:
    if value in (None, "", "null") or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_brand(name_en: str) -> str | None:
    if not name_en:
        return None
    name_lower = name_en.lower()
    for brand in KNOWN_BRANDS_SORTED:
        if name_lower.startswith(brand.lower()):
            return brand
    return None


def extract_pack_size(name_en: str) -> tuple[float | None, str | None, int]:
    if not name_en:
        return None, None, 1

    m = PATTERN_QTY_FIRST.search(name_en)
    if m:
        qty, size_str, unit = m.groups()
        return float(size_str), unit.lower(), int(qty)

    m = PATTERN_SIZE_FIRST.search(name_en)
    if m:
        size_str, unit, qty = m.groups()
        return float(size_str), unit.lower(), int(qty)

    matches = SINGLE_SIZE_PATTERN.findall(name_en)
    if matches:
        size_str, unit = matches[-1]
        return float(size_str), unit.lower(), 1

    return None, None, 1


def calculate_discount(price: float | None, regular_price: float | None) -> float | None:
    if price is None or regular_price is None:
        return None
    if regular_price <= 0 or regular_price <= price:
        return 0.0
    return round((regular_price - price) / regular_price * 100, 2)


def build_product_url(row: pd.Series) -> str | None:
    url_ar = row.get("url_ar")
    url_en = row.get("url_en")
    if isinstance(url_en, str) and url_en.startswith("/"):
        return f"https://www.danube.sa{url_en}"
    if isinstance(url_en, str) and url_en:
        return url_en
    if isinstance(url_ar, str) and url_ar.startswith("/"):
        return f"https://www.danube.sa{url_ar}"
    return url_ar


def load_raw_hits() -> pd.DataFrame:
    raw_path = raw_input_path()
    if not raw_path.exists():
        raise FileNotFoundError(
            f"Raw file not found: {raw_path}\n"
            "Run extract_danube_raw.py first to produce it."
        )
    data = json.loads(raw_path.read_text(encoding="utf-8"))
    hits = data.get("hits", [])
    print(f"Loaded {len(hits)} raw hits from {raw_path.name}")
    return pd.DataFrame(hits)


def transform(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)

    out["product_name_ar"] = (df.get("full_name_ar", df.get("name_ar"))).apply(clean_text)
    out["product_name_en"] = (df.get("full_name_en", df.get("name_en"))).apply(clean_text)
    out["store"] = "Danube Online"
    out["category"] = df.get("_category_key")

    price = df.get("price").apply(safe_float)
    original_price = df.get("original_price").apply(safe_float)
    out["price"] = price
    out["regular_price"] = [
        op if op and op > (p or 0) else p
        for op, p in zip(original_price, price)
    ]
    out["discount"] = [
        calculate_discount(p, rp) for p, rp in zip(out["price"], out["regular_price"])
    ]

    brand_size = out["product_name_en"].apply(
        lambda n: (extract_brand(n), *extract_pack_size(n))
    )
    out["brand"] = brand_size.apply(lambda t: t[0])
    out["size"] = brand_size.apply(lambda t: t[1])
    out["unit"] = brand_size.apply(lambda t: t[2] or "unit")
    out["quantity"] = brand_size.apply(lambda t: t[3])
    out["total_size"] = [
        round(s * q, 3) if s is not None else None
        for s, q in zip(out["size"], out["quantity"])
    ]

    out["url"] = df.apply(build_product_url, axis=1)
    out["image"] = df.get("image")

    out = out[
        (out["product_name_ar"] != "") | (out["product_name_en"] != "")
    ]
    out = out[out["price"].notna()]

    return out.reset_index(drop=True)


def save_clean_file(df: pd.DataFrame) -> Path:
    timestamp = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    records = json.loads(df.to_json(orient="records", force_ascii=False))

    result = {
        "store": "Danube Online",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "categories": df["category"].value_counts().to_dict(),
        "records_count": len(records),
        "records": records,
    }

    out_dir = processed_output_dir()
    path = out_dir / f"danube_clean_{timestamp}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    latest_path = out_dir / "danube_clean_latest.json"
    latest_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return path


def transform_danube() -> pd.DataFrame:
    print("=" * 60)
    print("STARTING DANUBE TRANSFORM (pandas, no network calls)")
    print("=" * 60)

    raw_df = load_raw_hits()
    clean_df = transform(raw_df)
    path = save_clean_file(clean_df)

    print("\n" + "=" * 60)
    print("DANUBE TRANSFORM FINISHED")
    print("=" * 60)
    print(clean_df["category"].value_counts().to_string())
    print(f"  Total: {len(clean_df)} products")

    brands_found = clean_df["brand"].notna().sum()
    sizes_found = clean_df["size"].notna().sum()
    print(f"  Brands extracted: {brands_found}/{len(clean_df)} ({brands_found/len(clean_df)*100:.1f}%)")
    print(f"  Sizes extracted: {sizes_found}/{len(clean_df)} ({sizes_found/len(clean_df)*100:.1f}%)")
    print(f"  File: {path}")

    return clean_df


if __name__ == "__main__":
    transform_danube()