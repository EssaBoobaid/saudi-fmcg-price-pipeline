import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IN_FILE = ROOT / "data" / "raw" / "open_data" / "gastat_historical_prices_clean.csv"
OUT_FILE = ROOT / "data" / "processed" / "gastat_food_prices_clean.csv"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def parse_float(value):
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return ""


def clean_row(row):
    if str(row.get("Level", "")).strip() != "6":
        return None

    item_name_ar = (row.get("item_name_ar") or "").strip()
    item_name_en = (row.get("item_name_en") or "").strip()
    if not item_name_ar and not item_name_en:
        return None

    cleaned = {
        "Level": "6",
        "Year": (row.get("Year") or "").strip(),
        "item_name_ar": item_name_ar,
        "item_name_en": item_name_en,
        "unit_ar": (row.get("unit_ar") or "").strip(),
        "unit_en": (row.get("unit_en") or "").strip(),
        "Annual average": parse_float(row.get("Annual average")),
    }

    for month in MONTHS:
        cleaned[month] = parse_float(row.get(month))

    return cleaned


def main():
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    with IN_FILE.open("r", encoding="utf-8", newline="") as infile:
        reader = csv.DictReader(infile)
        for raw_row in reader:
            cleaned = clean_row(raw_row)
            if cleaned is not None:
                rows.append(cleaned)

    fieldnames = ["Level", "Year", "item_name_ar", "item_name_en", "unit_ar", "unit_en", "Annual average", *MONTHS]
    with OUT_FILE.open("w", encoding="utf-8", newline="") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"food_rows={len(rows)}")
    print(f"output={OUT_FILE}")
    if rows:
        print(rows[0]["item_name_ar"], rows[0]["Year"], rows[0]["Annual average"])


if __name__ == "__main__":
    main()
