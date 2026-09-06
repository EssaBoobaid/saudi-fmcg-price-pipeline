from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from rapidfuzz.fuzz import token_set_ratio


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BINDAWOOD_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "stores"
    / "bindawood"
    / "bindawood_clean_latest.json"
)
DEFAULT_DANUBE_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "stores"
    / "danube"
    / "danube_clean_latest.json"
)
DEFAULT_TAMIMI_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "stores"
    / "tamimi"
    / "tamimi_clean_latest.json"
)
DEFAULT_OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "analysis"
    / "three_store_product_matches.json"
)


def normalize_name(value: Any) -> str:
    """Normalize Arabic/English names for reliable exact comparisons."""
    if value is None:
        return ""

    text = unicodedata.normalize("NFKC", str(value)).casefold()
    text = re.sub(r"[\u064B-\u065F\u0670\u06D6-\u06ED]", "", text)
    text = text.translate(str.maketrans("إأآى", "اااي"))
    text = text.replace("ـ", "")
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = " ".join(text.split())
    return re.sub(r"\s+م$", "", text).strip()


def load_records(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    records = data.get("records", [])
    if not isinstance(records, list):
        raise ValueError(f"Expected a 'records' list in {path}")
    return [record for record in records if isinstance(record, dict)]


def names(record: dict[str, Any]) -> tuple[str, str]:
    return (
        normalize_name(record.get("product_name_ar")),
        normalize_name(record.get("product_name_en")),
    )


def category(record: dict[str, Any]) -> str:
    return normalize_name(record.get("category"))


def valid_barcode(record: dict[str, Any]) -> str | None:
    barcode = str(record.get("barcode") or "")
    if not barcode.isdigit() or len(barcode) not in {12, 13, 14}:
        return None

    total = sum(
        int(digit) * (3 if position % 2 == 1 else 1)
        for position, digit in enumerate(reversed(barcode[:-1]), start=1)
    )
    check_digit = (10 - total % 10) % 10
    return barcode if check_digit == int(barcode[-1]) else None


def barcode_candidates(record: dict[str, Any]) -> list[str]:
    values = record.get("barcode_candidates") or [record.get("barcode")]
    candidates = []
    for value in values:
        barcode = str(value or "")
        if barcode.isdigit() and len(barcode) in {12, 13, 14} and barcode not in candidates:
            candidates.append(barcode)
    return candidates


def one_digit_barcode_match(
    source: dict[str, Any], target: dict[str, Any]
) -> bool:
    source_barcodes = barcode_candidates(source)
    target_barcodes = barcode_candidates(target)
    return any(
        len(source_barcode) == len(target_barcode)
        and sum(a != b for a, b in zip(source_barcode, target_barcode)) == 1
        for source_barcode in source_barcodes
        for target_barcode in target_barcodes
    )


def match_method(source: dict[str, Any], target: dict[str, Any]) -> str:
    source_barcode = valid_barcode(source)
    target_barcode = valid_barcode(target)

    if source_barcode and source_barcode == target_barcode:
        return "barcode"
    if one_digit_barcode_match(source, target):
        return "barcode_one_digit_difference"
    return "name"


def brand_key(record: dict[str, Any]) -> str:
    brand = normalize_name(record.get("brand"))
    if brand in {"ksa", "saudi", "saudi arabia"}:
        return ""
    return brand


def unit_key(record: dict[str, Any]) -> str:
    unit = normalize_name(record.get("unit"))
    return {
        "milliliter": "ml",
        "milliliters": "ml",
        "liter": "l",
        "liters": "l",
        "litre": "l",
        "litres": "l",
        "kilogram": "kg",
        "kilograms": "kg",
        "gram": "g",
        "grams": "g",
        "piece": "unit",
        "pieces": "unit",
        "pcs": "unit",
        "pc": "unit",
    }.get(unit, unit)


def metadata_compatible(source: dict[str, Any], target: dict[str, Any]) -> bool:
    source_brand = brand_key(source)
    target_brand = brand_key(target)
    if source_brand and target_brand and source_brand != target_brand:
        return False

    source_unit = unit_key(source)
    target_unit = unit_key(target)
    if source_unit and target_unit and source_unit != target_unit:
        return False

    source_size = source.get("size")
    target_size = target.get("size")
    if source_size is not None and target_size is not None:
        try:
            if abs(float(source_size) - float(target_size)) > 0.001:
                return False
        except (TypeError, ValueError):
            if str(source_size).strip() != str(target_size).strip():
                return False

    return True


def exact_match_count(
    bindawood: list[dict[str, Any]], danube: list[dict[str, Any]]
) -> int:
    """Count strict one-to-one matches by name and product metadata."""
    return len(best_matches(bindawood, danube))


def fuzzy_match_count(
    bindawood: list[dict[str, Any]],
    danube: list[dict[str, Any]],
    threshold: float,
) -> int:
    """Count fuzzy matches whose names and metadata are compatible."""
    return len(best_matches(bindawood, danube, threshold))


def percentage(matches: int, total: int) -> float:
    return round(matches / total * 100, 2) if total else 0.0


def price(record: dict[str, Any]) -> float | None:
    value = record.get("price")
    try:
        return round(float(value), 2) if value is not None else None
    except (TypeError, ValueError):
        return None


def best_matches(
    source_records: list[dict[str, Any]],
    target_records: list[dict[str, Any]],
    threshold: float | None = None,
) -> dict[int, tuple[int, float]]:
    """Return one-to-one matches, preferring valid shared barcodes."""
    target_by_category: dict[str, list[tuple[int, tuple[str, str]]]] = {}
    target_by_barcode: dict[tuple[str, str], list[int]] = {}
    for target_index, record in enumerate(target_records):
        target_by_category.setdefault(category(record), []).append(
            (target_index, names(record))
        )
        barcode = valid_barcode(record)
        if barcode:
            target_by_barcode.setdefault((category(record), barcode), []).append(
                target_index
            )

    matches: dict[int, tuple[int, float]] = {}
    used_targets: set[int] = set()
    for source_index, source_record in enumerate(source_records):
        source_names = [name for name in names(source_record) if name]
        source_barcode = valid_barcode(source_record)
        if source_barcode:
            barcode_indexes = target_by_barcode.get(
                (category(source_record), source_barcode), []
            )
            candidates = [
                (target_index, names(target_records[target_index]))
                for target_index in barcode_indexes
            ]
            if not candidates:
                candidates = target_by_category.get(category(source_record), [])
        else:
            candidates = target_by_category.get(category(source_record), [])
        best_target = None
        best_score = 0.0

        for target_index, target_names in candidates:
            if target_index in used_targets:
                continue
            target_barcode = valid_barcode(target_records[target_index])
            barcode_close = one_digit_barcode_match(
                source_record,
                target_records[target_index],
            )
            if source_barcode and target_barcode != source_barcode and not barcode_close:
                continue
            if not metadata_compatible(source_record, target_records[target_index]):
                continue
            target_name_set = set(target_names) - {""}
            source_name_set = set(source_names)
            exact = source_name_set & target_name_set
            score = 100.0 if exact else max(
                (token_set_ratio(source_name, target_name)
                 for source_name in source_names
                 for target_name in target_names
                 if source_name and target_name),
                default=0.0,
            )
            if threshold is None and not exact:
                continue
            if threshold is not None and score < threshold:
                continue
            if score > best_score:
                best_target = target_index
                best_score = score

        if best_target is not None:
            used_targets.add(best_target)
            matches[source_index] = (best_target, best_score)

    return matches


def build_three_store_matches(
    bindawood: list[dict[str, Any]],
    danube: list[dict[str, Any]],
    tamimi: list[dict[str, Any]],
    threshold: float,
    fuzzy: bool,
) -> list[dict[str, Any]]:
    match_threshold = threshold if fuzzy else None
    danube_matches = best_matches(bindawood, danube, match_threshold)
    tamimi_matches = best_matches(bindawood, tamimi, match_threshold)
    matched_products = []

    for bindawood_index, (danube_index, danube_score) in danube_matches.items():
        tamimi_match = tamimi_matches.get(bindawood_index)
        if tamimi_match is None:
            continue

        tamimi_index, tamimi_score = tamimi_match
        bindawood_record = bindawood[bindawood_index]
        danube_record = danube[danube_index]
        tamimi_record = tamimi[tamimi_index]
        prices = {
            "bindawood": price(bindawood_record),
            "danube": price(danube_record),
            "tamimi": price(tamimi_record),
        }
        available_prices = [value for value in prices.values() if value is not None]

        matched_products.append(
            {
                "product_name_ar": bindawood_record.get("product_name_ar"),
                "product_name_en": bindawood_record.get("product_name_en"),
                "category": bindawood_record.get("category"),
                "prices": prices,
                "average_price": round(sum(available_prices) / len(available_prices), 2)
                if available_prices
                else None,
                "match_scores": {
                    "bindawood_danube": round(danube_score, 2),
                    "bindawood_tamimi": round(tamimi_score, 2),
                },
                "match_method": {
                    "bindawood_danube": match_method(
                        bindawood_record,
                        danube_record,
                    ),
                    "bindawood_tamimi": match_method(
                        bindawood_record,
                        tamimi_record,
                    ),
                },
                "stores": {
                    "bindawood": bindawood_record,
                    "danube": danube_record,
                    "tamimi": tamimi_record,
                },
            }
        )

    return matched_products


def save_results(
    output_file: Path,
    exact_matches: list[dict[str, Any]],
    fuzzy_matches: list[dict[str, Any]],
    threshold: float,
) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "description": "Products matched across Bindawood, Danube, and Tamimi",
        "fuzzy_threshold": threshold,
        "exact_three_store_matches_count": len(exact_matches),
        "fuzzy_three_store_matches_count": len(fuzzy_matches),
        "exact_three_store_matches": exact_matches,
        "fuzzy_three_store_matches": fuzzy_matches,
    }
    with output_file.open("w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)


def print_comparison(
    first_name: str,
    first_records: list[dict[str, Any]],
    second_name: str,
    second_records: list[dict[str, Any]],
    threshold: float,
) -> None:
    exact_matches = exact_match_count(first_records, second_records)
    fuzzy_matches = fuzzy_match_count(first_records, second_records, threshold)
    comparison_base = min(len(first_records), len(second_records))

    print(f"\n{first_name} vs {second_name}")
    print(f"{first_name} products: {len(first_records)}")
    print(f"{second_name} products: {len(second_records)}")
    print(f"Exact matches: {exact_matches}")
    print(f"Exact similarity: {percentage(exact_matches, comparison_base)}%")
    print(f"Fuzzy matches (threshold {threshold:g}): {fuzzy_matches}")
    print(f"Fuzzy similarity: {percentage(fuzzy_matches, comparison_base)}%")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare product-name similarity between Saudi supermarket catalogs."
    )
    parser.add_argument("--bindawood", type=Path, default=DEFAULT_BINDAWOOD_FILE)
    parser.add_argument("--danube", type=Path, default=DEFAULT_DANUBE_FILE)
    parser.add_argument("--tamimi", type=Path, default=DEFAULT_TAMIMI_FILE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_FILE)
    parser.add_argument(
        "--threshold",
        type=float,
        default=90.0,
        help="Minimum fuzzy similarity score from 0 to 100 (default: 90).",
    )
    args = parser.parse_args()

    if not 0 <= args.threshold <= 100:
        parser.error("--threshold must be between 0 and 100")

    bindawood = load_records(args.bindawood)
    danube = load_records(args.danube)
    tamimi = load_records(args.tamimi)

    print_comparison("Bindawood", bindawood, "Danube", danube, args.threshold)
    print_comparison("Bindawood", bindawood, "Tamimi", tamimi, args.threshold)
    print_comparison("Danube", danube, "Tamimi", tamimi, args.threshold)

    exact_matches = build_three_store_matches(
        bindawood, danube, tamimi, args.threshold, fuzzy=False
    )
    fuzzy_matches = build_three_store_matches(
        bindawood, danube, tamimi, args.threshold, fuzzy=True
    )
    save_results(args.output, exact_matches, fuzzy_matches, args.threshold)
    print(f"\nSaved results to: {args.output}")
    print(f"Exact three-store products saved: {len(exact_matches)}")
    print(f"Fuzzy three-store products saved: {len(fuzzy_matches)}")


if __name__ == "__main__":
    main()