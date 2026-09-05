from __future__ import annotations

import json
import os
from datetime import datetime

import requests


ALGOLIA_APP_ID = "KBGHG5MR5E"
ALGOLIA_API_KEY = "8c6b85b7bdebb06d260ccde6b810884b"

ALGOLIA_URL = (
    f"https://{ALGOLIA_APP_ID.lower()}-dsn.algolia.net/1/indexes/*/queries"
)

INDEX_NAME = "spree_products"

HITS_PER_PAGE = 100
MAX_PAGES_SAFETY = 200


CATEGORIES = {
    "fruits_vegetables": "الأقسام > فواكه و خضروات طازجة",
    "dairy": "الأقسام > منتجات الألبان والبيض",
    "beverages": "الأقسام > الماء و المشروبات",
}


PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

OUTPUT_DIR = os.path.join(
    PROJECT_ROOT,
    "data",
    "raw",
    "stores",
    "bindawood",
)


HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0",
    "X-Algolia-Application-Id": ALGOLIA_APP_ID,
    "X-Algolia-API-Key": ALGOLIA_API_KEY,
    "X-Algolia-Agent": "Algolia for JavaScript",
}


def fetch_page(category_filter: str, page: int) -> dict:

    params = (
        "query="
        "&maxValuesPerFacet=9999"
        f"&page={page}"
        "&filters=tenant_id%20%3D%202"
        "&hitsPerPage=100"
        "&facets=%5B%22price%22%2C%22taxons_ar.lvl0%22%2C"
        "%22taxons_ar.lvl1%22%2C%22taxons_ar.lvl2%22%5D"
        "&facetFilters=%5B%5B%22"
        f"taxons_ar.lvl1%3A{requests.utils.quote(category_filter, safe='')}"
        "%22%5D%5D"
    )

    payload = {
        "requests": [
            {
                "indexName": INDEX_NAME,
                "params": params,
            }
        ]
    }

    response = requests.post(
        ALGOLIA_URL,
        headers=HEADERS,
        json=payload,
        timeout=60,
    )

    response.raise_for_status()

    data = response.json()

    return data["results"][0]


def fetch_category_raw(
    category_key: str,
    category_filter: str,
) -> list[dict]:

    print()
    print("=" * 70)
    print(f"Extracting category: {category_key}")
    print(f"Filter: {category_filter}")
    print("=" * 70)

    all_hits = []

    first_page = fetch_page(
        category_filter,
        0,
    )

    total_hits = first_page.get(
        "nbHits",
        0,
    )

    total_pages = first_page.get(
        "nbPages",
        0,
    )

    print(f"Total products: {total_hits}")
    print(f"Total pages: {total_pages}")

    first_hits = first_page.get(
        "hits",
        [],
    )

    for hit in first_hits:
        hit["_category_key"] = category_key

    all_hits.extend(first_hits)

    print(
        f"Page 1/{total_pages}: "
        f"{len(first_hits)} products"
    )

    for page in range(
        1,
        min(total_pages, MAX_PAGES_SAFETY),
    ):

        result = fetch_page(
            category_filter,
            page,
        )

        hits = result.get(
            "hits",
            [],
        )

        for hit in hits:
            hit["_category_key"] = category_key

        all_hits.extend(hits)

        print(
            f"Page {page + 1}/{total_pages}: "
            f"{len(hits)} products"
        )

    print(
        f"Finished {category_key}: "
        f"{len(all_hits)} products extracted"
    )

    return all_hits


def save_raw_file(all_hits: list[dict]) -> None:

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True,
    )

    fetched_at = datetime.now().isoformat(
        timespec="seconds"
    )

    output_data = {
        "store": "BinDawood Online",
        "source": "algolia_api",
        "fetched_at": fetched_at,
        "hits_count": len(all_hits),
        "hits": all_hits,
    }

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    timestamped_file = os.path.join(
        OUTPUT_DIR,
        f"bindawood_raw_{timestamp}.json",
    )

    latest_file = os.path.join(
        OUTPUT_DIR,
        "bindawood_raw_latest.json",
    )

    with open(
        timestamped_file,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            output_data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    with open(
        latest_file,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            output_data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print("=" * 70)
    print("RAW DATA SAVED")
    print("=" * 70)

    print(f"Total products: {len(all_hits)}")
    print(f"Latest file: {latest_file}")


def extract_bindawood_raw() -> None:

    print()
    print("=" * 70)
    print("BINDAWOOD RAW EXTRACTION")
    print("=" * 70)

    all_hits = []

    for category_key, category_filter in CATEGORIES.items():

        try:

            category_hits = fetch_category_raw(
                category_key,
                category_filter,
            )

            all_hits.extend(category_hits)

        except requests.RequestException as error:

            print()
            print(
                f"ERROR while extracting "
                f"{category_key}: {error}"
            )

    print()
    print("=" * 70)
    print("EXTRACTION SUMMARY")
    print("=" * 70)

    print(
        f"Total products extracted: {len(all_hits)}"
    )

    save_raw_file(all_hits)


if __name__ == "__main__":
    extract_bindawood_raw()