from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


# ============================================================
# PATHS
# ============================================================

PROCESSED_STORES_DIR = Path("data/processed/stores")
OUTPUT_DIR = Path("data/processed/matches")

STORE_FILES = {
    "danube": PROCESSED_STORES_DIR / "danube" / "danube_clean_latest.json",
    "bindawood": PROCESSED_STORES_DIR / "bindawood" / "bindawood_clean_latest.json",
    "tamimi": PROCESSED_STORES_DIR / "tamimi" / "tamimi_clean_latest.json",
}

OUTPUT_FILE = OUTPUT_DIR / "unified_products_latest.json"


# ============================================================
# HELPERS
# ============================================================

def safe_text(value: Any) -> str:
    """يرجع نصًا آمنًا، أو نصًا فارغًا للقيم null."""
    if value is None:
        return ""

    return str(value).strip()


def safe_number(value: Any) -> float | None:
    """يرجع رقمًا إن أمكن، أو None."""
    if value is None or value == "":
        return None

    try:
        return float(value)
    except (ValueError, TypeError):
        return None


# ============================================================
# GTIN / BARCODE NORMALIZATION
# ============================================================

def calculate_gtin_check_digit(body: str) -> str:
    """
    يحسب آخر رقم تحقق في GTIN / EAN.

    مثال:
    body = 628110050551
    check digit = 8
    full barcode = 6281100505518
    """
    total = 0

    for index, digit in enumerate(reversed(body)):
        multiplier = 3 if index % 2 == 0 else 1
        total += int(digit) * multiplier

    return str((10 - (total % 10)) % 10)


def is_valid_gtin(barcode: str) -> bool:
    """يتحقق من أن رقم GTIN صحيح رياضيًا."""
    if not barcode.isdigit():
        return False

    if len(barcode) not in {8, 12, 13, 14}:
        return False

    return barcode[-1] == calculate_gtin_check_digit(barcode[:-1])


def normalize_barcode(value: Any) -> str:
    """
    يوحد الباركود للاستخدام كمفتاح ربط.

    حالات المشروع:
    - Danube/BinDawood: قد يرجع الرقم من اسم الصورة بـ12 خانة.
      نضيف check digit ليصبح GTIN-13.
    - Tamimi: يرجع غالبًا GTIN-13 كاملًا.
    """
    barcode = re.sub(r"\D", "", safe_text(value))

    if not barcode:
        return ""

    # EAN-13 / GTIN-13 مكتمل وصحيح.
    if len(barcode) == 13 and is_valid_gtin(barcode):
        return barcode

    # GTIN-14 كامل وصحيح.
    if len(barcode) == 14 and is_valid_gtin(barcode):
        return barcode

    # رقم 12 خانة من Danube أو BinDawood:
    # نعالجه كجسم EAN-13 ونضيف رقم التحقق.
    if len(barcode) == 12:
        return barcode + calculate_gtin_check_digit(barcode)

    # GTIN-8 صحيح: نضيف أصفارًا ليصبح بطول 13.
    if len(barcode) == 8 and is_valid_gtin(barcode):
        return "00000" + barcode

    # رقم لا نستطيع الوثوق به.
    return ""


# ============================================================
# LOAD CLEAN FILES
# ============================================================

def load_clean_file(path: Path) -> tuple[dict, list[dict]]:
    """
    يقرأ ملف clean_latest.json بالشكل:

    {
      "store": "Danube Online",
      "generated_at": "2026-09-06T12:42:18Z",
      "categories": {...},
      "records_count": 2380,
      "records": [ ... ]
    }
    """
    if not path.exists():
        raise FileNotFoundError(f"لم أجد الملف:\n{path}")

    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    if not isinstance(payload, dict):
        raise ValueError(
            f"الملف يجب أن يكون JSON object وليس list:\n{path}"
        )

    records = payload.get("records")

    if not isinstance(records, list):
        raise ValueError(
            f"لم أجد قائمة records داخل الملف:\n{path}"
        )

    return payload, records


# ============================================================
# INDEX STORE PRODUCTS BY BARCODE
# ============================================================

def get_price(record: dict) -> float | None:
    """
    نستخدم السعر الحالي price.
    المنتج لا يدخل ملف الحقن إذا لم يكن له سعر واضح.
    """
    price = safe_number(record.get("price"))

    if price is None or price <= 0:
        return None

    return round(price, 2)


def build_barcode_index(
    records: list[dict],
    store_key: str,
) -> tuple[dict[str, dict], dict[str, int]]:
    """
    يبني قاموس:

    {
      "6281100505518": product_record,
      ...
    }

    إذا تكرر نفس الباركود في متجر واحد:
    نحتفظ بالمنتج صاحب أقل سعر صالح.
    """
    index: dict[str, dict] = {}

    stats = {
        "total_records": len(records),
        "valid_barcode": 0,
        "valid_price": 0,
        "indexed": 0,
        "duplicate_barcode": 0,
    }

    for record in records:
        barcode = normalize_barcode(record.get("barcode"))

        if not barcode:
            continue

        stats["valid_barcode"] += 1

        price = get_price(record)

        if price is None:
            continue

        stats["valid_price"] += 1

        record_copy = dict(record)
        record_copy["_normalized_barcode"] = barcode
        record_copy["_store_key"] = store_key
        record_copy["_price"] = price

        existing = index.get(barcode)

        if existing is None:
            index[barcode] = record_copy
            stats["indexed"] += 1
            continue

        stats["duplicate_barcode"] += 1

        # عند وجود نفس الباركود أكثر من مرة في نفس المتجر،
        # نحتفظ بالسجل صاحب السعر الأقل.
        if record_copy["_price"] < existing["_price"]:
            index[barcode] = record_copy

    return index, stats


# ============================================================
# CREATE THE UNIFIED PRODUCT RECORD
# ============================================================

def store_price_payload(record: dict) -> dict:
    current_price = safe_number(record.get("price"))
    regular_price = safe_number(record.get("regular_price"))
    discount_percent = safe_number(record.get("discount"))

    if current_price is not None:
        current_price = round(current_price, 2)

    if regular_price is None:
        regular_price = current_price
    else:
        regular_price = round(regular_price, 2)

    if (
        regular_price is not None
        and current_price is not None
        and regular_price > current_price
    ):
        calculated_discount = round(
            ((regular_price - current_price) / regular_price) * 100,
            2,
        )
    else:
        calculated_discount = 0.0

    if discount_percent is None or discount_percent <= 0:
        discount_percent = calculated_discount
    else:
        discount_percent = round(discount_percent, 2)

    return {
        "store": safe_text(record.get("store")),
        "current_price": current_price,
        "regular_price": regular_price,
        "discount_percent": discount_percent,
        "on_discount": discount_percent > 0,
        "url": safe_text(record.get("url")),
    }


def make_unified_record(match: dict) -> dict:
    danube_prices = store_price_payload(match["danube_record"])
    bindawood_prices = store_price_payload(match["bindawood_record"])
    tamimi_prices = store_price_payload(match["tamimi_record"])

    current_prices = [
        danube_prices["current_price"],
        bindawood_prices["current_price"],
        tamimi_prices["current_price"],
    ]

    regular_prices = [
        danube_prices["regular_price"],
        bindawood_prices["regular_price"],
        tamimi_prices["regular_price"],
    ]

    valid_current_prices = [
        price for price in current_prices
        if price is not None
    ]

    valid_regular_prices = [
        price for price in regular_prices
        if price is not None
    ]

    price_by_store = {
        "danube": danube_prices["current_price"],
        "bindawood": bindawood_prices["current_price"],
        "tamimi": tamimi_prices["current_price"],
    }

    lowest_current_price = min(valid_current_prices)
    highest_current_price = max(valid_current_prices)

    return {
        "barcode": match["danube_barcode"],
        "product_name_ar": match["danube_product_name_ar"] or None,
        "product_name_en": match["danube_product_name_en"] or None,
        "category": match["category"],
        "brand": match["brand"],
        "size": None if pd.isna(match["size_value"]) else match["size_value"],
        "unit": match["unit"],
        "quantity": match["quantity"],
        "total_size": (
            None
            if pd.isna(match["total_size_standard"])
            else match["total_size_standard"]
        ),
        "image_url": match["danube_image_url"],
        "prices": {
            "danube": danube_prices,
            "bindawood": bindawood_prices,
            "tamimi": tamimi_prices,
        },
        "average_current_price": round(
            sum(valid_current_prices) / len(valid_current_prices),
            2,
        ),
        "average_regular_price": round(
            sum(valid_regular_prices) / len(valid_regular_prices),
            2,
        ),
        "lowest_current_price": round(lowest_current_price, 2),
        "highest_current_price": round(highest_current_price, 2),
        "price_spread": round(
            highest_current_price - lowest_current_price,
            2,
        ),
        "cheapest_store": min(
            price_by_store,
            key=lambda store: price_by_store[store],
        ),
        "match_method": "barcode",
        "captured_at": match["generated_at_utc"],
    }


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    print("\nLoading clean product files...")

    danube_metadata, danube_records = load_clean_file(
        STORE_FILES["danube"]
    )

    bindawood_metadata, bindawood_records = load_clean_file(
        STORE_FILES["bindawood"]
    )

    tamimi_metadata, tamimi_records = load_clean_file(
        STORE_FILES["tamimi"]
    )

    print(f"Danube raw clean records:    {len(danube_records):,}")
    print(f"BinDawood raw clean records: {len(bindawood_records):,}")
    print(f"Tamimi raw clean records:    {len(tamimi_records):,}")

    print("\nBuilding barcode indexes...")

    danube_index, danube_stats = build_barcode_index(
        danube_records,
        "danube",
    )

    bindawood_index, bindawood_stats = build_barcode_index(
        bindawood_records,
        "bindawood",
    )

    tamimi_index, tamimi_stats = build_barcode_index(
        tamimi_records,
        "tamimi",
    )

    print(f"Danube indexed barcodes:    {len(danube_index):,}")
    print(f"BinDawood indexed barcodes: {len(bindawood_index):,}")
    print(f"Tamimi indexed barcodes:    {len(tamimi_index):,}")

    # فقط الباركودات المشتركة بين الثلاثة.
    shared_barcodes = (
        set(danube_index)
        & set(bindawood_index)
        & set(tamimi_index)
    )

    print(f"\nShared barcodes in all 3 stores: {len(shared_barcodes):,}")

    unified_records = []

    for barcode in sorted(shared_barcodes):
        danube_record = danube_index[barcode]
        bindawood_record = bindawood_index[barcode]
        tamimi_record = tamimi_index[barcode]

        match = {
            "danube_barcode": barcode,
            "danube_product_name_ar": danube_record.get(
                "product_name_ar"
            ),
            "danube_product_name_en": danube_record.get(
                "product_name_en"
            ),
            "category": danube_record.get("category"),
            "brand": danube_record.get("brand"),
            "size_value": danube_record.get("size"),
            "unit": danube_record.get("unit"),
            "quantity": danube_record.get("quantity"),
            "total_size_standard": danube_record.get("total_size"),
            "danube_image_url": (
                danube_record.get("image_url")
                or danube_record.get("image")
            ),
            "danube_record": danube_record,
            "bindawood_record": bindawood_record,
            "tamimi_record": tamimi_record,
            "generated_at_utc": generated_at,
        }

        unified_record = make_unified_record(
            match
        )

        unified_records.append(unified_record)

    # ترتيب الملف: كاتقوري ثم براند ثم الاسم الإنجليزي.
    unified_records.sort(
        key=lambda record: (
            safe_text(record.get("category")).lower(),
            safe_text(record.get("brand")).lower(),
            safe_text(record.get("product_name_en")).lower(),
        )
    )

    output_payload = {
        "generated_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "records_count": len(unified_records),
        "records": unified_records,
    }

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%d_%H%M%S"
    )
    timestamped_output = (
        OUTPUT_DIR / f"unified_products_{timestamp}.json"
    )

    serialized_payload = json.dumps(
        output_payload,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    )

    for output_file in (timestamped_output, OUTPUT_FILE):
        output_file.write_text(
            serialized_payload,
            encoding="utf-8",
        )

    print("\n" + "=" * 70)
    print("Saudi PriceLens — Unified three-store products")
    print("=" * 70)
    print(f"Danube valid indexed products:    {len(danube_index):,}")
    print(f"BinDawood valid indexed products: {len(bindawood_index):,}")
    print(f"Tamimi valid indexed products:    {len(tamimi_index):,}")
    print(f"Unified records for DB injection: {len(unified_records):,}")
    print("\nOutput files:")
    print(timestamped_output)
    print(OUTPUT_FILE)
    print("=" * 70)


if __name__ == "__main__":
    main()