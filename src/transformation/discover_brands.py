"""Auto-discover brand candidates from Danube product names.

Reads the combined extraction output and analyzes English product names
to find recurring leading words/phrases — real brands appear across many
products, while generic words (Fresh, Full, Large...) don't cluster the
same way. Prints a ranked candidate list for quick manual review, then
writes it to a JSON file you can merge into KNOWN_BRANDS.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

# كلمات عامة نستبعدها لأنها صفات وصفية وليست براندات
GENERIC_WORDS = {
    "fresh", "full", "fat", "low", "free", "new", "premium", "organic",
    "natural", "pure", "extra", "large", "small", "medium", "big",
    "mini", "family", "value", "pack", "assorted", "mixed", "plain",
    "sweet", "salted", "unsalted", "whole", "skimmed", "semi", "light",
    "diet", "classic", "original", "regular", "imported", "local",
    "red", "green", "yellow", "white", "black", "flavored", "flavor",
    "frozen", "dried", "canned", "bottled", "sliced", "whole", "baby",
}

# بادئات شائعة بالعربي منقولة للإنجليزي، البراند الحقيقي يبدأ بعدها
AR_PREFIXES = {"al", "el", "the"}

MIN_OCCURRENCES = 4  # حد أدنى للتكرار عشان يُعتبر "براند مرشح"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def input_file() -> Path:
    return project_root() / "data" / "raw" / "stores" / "danube" / "danube_all_categories.json"


def output_file() -> Path:
    return project_root() / "data" / "raw" / "stores" / "danube" / "brand_candidates.json"


def get_candidate_phrases(name_en: str) -> list[str]:
    """يرجع مرشحين محتملين للبراند من اسم المنتج: كلمة أولى، وكلمتين لو فيه بادئة"""
    words = re.findall(r"[A-Za-z]+", name_en)
    if not words:
        return []

    candidates = []
    first = words[0]

    if first.lower() in AR_PREFIXES and len(words) >= 2:
        # بادئة مثل "Al" -> ناخذ كلمتين "Al Safi"
        candidates.append(f"{first} {words[1]}")
    else:
        candidates.append(first)

    return candidates


def discover_brands() -> list[dict]:
    data = json.loads(input_file().read_text(encoding="utf-8"))
    records = data.get("records", [])
    print(f"تحليل {len(records)} منتج...")

    phrase_counter: Counter[str] = Counter()
    phrase_examples: dict[str, list[str]] = {}

    for record in records:
        name_en = record.get("product_name_en") or ""
        for phrase in get_candidate_phrases(name_en):
            phrase_counter[phrase] += 1
            phrase_examples.setdefault(phrase, [])
            if len(phrase_examples[phrase]) < 3:
                phrase_examples[phrase].append(name_en)

    candidates = []
    for phrase, count in phrase_counter.most_common():
        first_word = phrase.split()[0].lower()
        if first_word in GENERIC_WORDS:
            continue
        if count < MIN_OCCURRENCES:
            continue
        candidates.append({
            "brand_candidate": phrase,
            "occurrences": count,
            "examples": phrase_examples[phrase],
        })

    return candidates


def save_and_print(candidates: list[dict]) -> None:
    output_file().write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n" + "=" * 70)
    print(f"تم اكتشاف {len(candidates)} براند مرشح (تكرار >= {MIN_OCCURRENCES} مرات)")
    print("=" * 70)
    print(f"{'البراند المرشح':<25} {'عدد المنتجات':<15} مثال")
    print("-" * 70)
    for c in candidates:
        example = c["examples"][0][:40] if c["examples"] else ""
        print(f"{c['brand_candidate']:<25} {c['occurrences']:<15} {example}")

    print("\n" + "=" * 70)
    print(f"الملف الكامل محفوظ في: {output_file()}")
    print("راجع القائمة واحذف أي عنصر ليس براندًا فعليًا، ثم أرسلها لي لتحديث KNOWN_BRANDS")


if __name__ == "__main__":
    candidates = discover_brands()
    save_and_print(candidates)
