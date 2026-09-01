"""Danube Online product extraction via public Algolia API endpoint.

Extracts ALL products (full pagination, no limit) across the 3 target
categories and saves them into a SINGLE combined JSON file:
    data/raw/stores/danube/danube_all_categories.json

Brand, pack quantity, size and unit are parsed out of the English
product name since Danube's Algolia index does not expose them as
separate fields. Handles multi-pack patterns like "2*500g" and "1L X12".
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import requests

ALGOLIA_APP_ID = "1D2IEWLQAD"
ALGOLIA_API_KEY = "87ca3b6b2ce56f0bb76fc194a8d170e2"
ALGOLIA_URL = f"https://{ALGOLIA_APP_ID.lower()}-dsn.algolia.net/1/indexes/*/queries"

INDEX_NAME = "spree_products"
HITS_PER_PAGE = 100
MAX_PAGES_SAFETY = 200

CATEGORIES = {
    "fruits-vegetables": "الأقسام > فواكه و خضروات طازجة",
    "dairy": "الأقسام > منتجات الألبان والبيض",
    "beverages": "الأقسام > الماء و المشروبات",
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
    "KDD", "Danube","Original", "Rockstar" , "Juicy", "Danya", "Shani" ,"Legero", "Senac",
    "Disfruta", "Canada" 
]

# الوحدات المدعومة (يشمل الصيغ الطويلة والقصيرة)
UNIT_PATTERN = r'(ml|milliliter|ltr|l|liter|litre|kg|kilogram|g|gm|gr|gram|pcs|pack|oz|ounce)'

# النمط 1: عدد أولاً (2*500g, 6x1L, 6×1L)
PATTERN_QTY_FIRST = re.compile(
    rf'(\d+)\s*[x×*]\s*(\d+(?:\.\d+)?)\s*{UNIT_PATTERN}\b', re.IGNORECASE,
)
# النمط 2: الحجم أولاً ثم العدد (1L X12, 1LTR X12, 500G*6)
PATTERN_SIZE_FIRST = re.compile(
    rf'(\d+(?:\.\d+)?)\s*{UNIT_PATTERN}\s*[x×*]\s*(\d+)\b', re.IGNORECASE,
)
# النمط 3: حجم مفرد بدون عدد عبوات
SINGLE_SIZE_PATTERN = re.compile(
    rf'(\d+(?:\.\d+)?)\s*{UNIT_PATTERN}\b', re.IGNORECASE,
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def output_dir() -> Path:
    path = project_root() / "data" / "raw" / "stores" / "danube"
    path.mkdir(parents=True, exist_ok=True)
    return path


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def safe_float(value: Any) -> float | None:
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_brand(name_en: str) -> str | None:
    if not name_en:
        return None
    name_lower = name_en.lower()
    for brand in sorted(KNOWN_BRANDS, key=len, reverse=True):
        if name_lower.startswith(brand.lower()):
            return brand
    return None


def extract_pack_size(name_en: str) -> tuple[float | None, str | None, int]:
    """يستخرج (حجم العبوة الواحدة، الوحدة، عدد العبوات) من اسم المنتج"""
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


def build_facet_filter(taxon_value: str) -> str:
    return f"taxons_ar.lvl1:{taxon_value}"


def fetch_page(taxon_value: str, page: int) -> tuple[list[dict], int]:
    facet_filter = build_facet_filter(taxon_value)

    payload = {
        "requests": [
            {
                "indexName": INDEX_NAME,
                "params": (
                    f"query=&maxValuesPerFacet=9999&page={page}"
                    "&filters=tenant_id%20%3D%201"
                    f"&hitsPerPage={HITS_PER_PAGE}"
                    "&facets=%5B%22price%22%5D"
                    f"&facetFilters=%5B%5B%22{facet_filter}%22%5D%5D"
                ),
            }
        ]
    }

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0",
        "Origin": "https://www.danube.sa",
        "Referer": "https://www.danube.sa/",
    }

    params = {
        "x-algolia-application-id": ALGOLIA_APP_ID,
        "x-algolia-api-key": ALGOLIA_API_KEY,
    }

    response = requests.post(
        ALGOLIA_URL, params=params, headers=headers,
        data=json.dumps(payload), timeout=30,
    )
    response.raise_for_status()

    body = response.json()
    results = body.get("results") or []
    if not results:
        return [], 0

    result = results[0]
    return result.get("hits") or [], result.get("nbPages", 0)


def fetch_category(category_key: str, taxon_value: str) -> list[dict]:
    print(f"\n[{category_key}] Searching Danube Algolia index...")
    print(f"Filter: {taxon_value}")

    all_hits: list[dict] = []
    page = 0
    nb_pages = 1

    while page < nb_pages and page < MAX_PAGES_SAFETY:
        hits, nb_pages = fetch_page(taxon_value, page)
        if not hits:
            break
        all_hits.extend(hits)
        print(f"  صفحة {page + 1}/{nb_pages}: {len(hits)} منتج (إجمالي: {len(all_hits)})")
        page += 1
        time.sleep(0.5)

    records = []
    for product in all_hits:
        simplified = simplify_product(product, category_key)
        if not simplified["product_name_ar"] and not simplified["product_name_en"]:
            continue
        if simplified["price"] is None:
            continue
        records.append(simplified)

    print(f"[{category_key}] Total extracted: {len(records)} products")
    return records


def calculate_discount(price: float | None, regular_price: float | None) -> float | None:
    if price is None or regular_price is None:
        return None
    if regular_price <= 0 or regular_price <= price:
        return 0.0
    return round((regular_price - price) / regular_price * 100, 2)


def simplify_product(product: dict, category_key: str) -> dict:
    name_ar = clean_text(product.get("full_name_ar") or product.get("name_ar"))
    name_en = clean_text(product.get("full_name_en") or product.get("name_en"))

    price = safe_float(product.get("price"))
    original_price = safe_float(product.get("original_price"))
    regular_price = original_price if original_price and original_price > (price or 0) else price
    discount = calculate_discount(price, regular_price)

    brand = extract_brand(name_en)
    size, unit, quantity = extract_pack_size(name_en)
    total_size = round(size * quantity, 3) if size is not None else None

    url_ar = product.get("url_ar")
    url_en = product.get("url_en")
    url = (
        f"https://www.danube.sa{url_en}" if url_en and url_en.startswith("/")
        else url_en or (f"https://www.danube.sa{url_ar}" if url_ar and url_ar.startswith("/") else url_ar)
    )

    return {
        "store": "Danube Online",
        "product_name_ar": name_ar,
        "product_name_en": name_en,
        "brand": brand,
        "category": category_key,
        "price": price,
        "regular_price": regular_price,
        "discount": discount,
        "quantity": quantity,
        "size": size,
        "unit": unit or "unit",
        "total_size": total_size,
        "url": url,
        "image": product.get("image"),
    }


def save_combined_file(all_records: list[dict]) -> Path:
    result = {
        "store": "Danube Online",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "categories": {
            category: sum(1 for r in all_records if r["category"] == category)
            for category in CATEGORIES
        },
        "records_count": len(all_records),
        "records": all_records,
    }
    path = output_dir() / "danube_all_categories.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def extract_danube_prices() -> list[dict]:
    print("=" * 60)
    print("STARTING DANUBE EXTRACTION (FULL, EN+AR, BRAND/PACK PARSED)")
    print("=" * 60)

    all_records: list[dict] = []
    for category_key, taxon_value in CATEGORIES.items():
        try:
            records = fetch_category(category_key, taxon_value)
        except requests.RequestException as exc:
            print(f"[{category_key}] ERROR: API request failed: {exc}")
            records = []
        except Exception as exc:
            print(f"[{category_key}] ERROR: {type(exc).__name__}: {exc}")
            records = []
        all_records.extend(records)

    path = save_combined_file(all_records)

    print("\n" + "=" * 60)
    print("DANUBE EXTRACTION FINISHED")
    print("=" * 60)
    for category_key in CATEGORIES:
        count = sum(1 for r in all_records if r["category"] == category_key)
        print(f"  {category_key}: {count} منتج")
    print(f"  الإجمالي: {len(all_records)} منتج")

    brands_found = sum(1 for r in all_records if r["brand"])
    sizes_found = sum(1 for r in all_records if r["size"])
    print(f"  منتجات تم استخراج براندها: {brands_found}/{len(all_records)}")
    print(f"  منتجات تم استخراج حجمها: {sizes_found}/{len(all_records)}")
    print(f"  الملف: {path}")

    return all_records


if __name__ == "__main__":
    extract_danube_prices()
