"""Danube Online RAW extraction via public Algolia API endpoint.

Pulls ALL products (full pagination, no limit) across the 3 target
categories EXACTLY as returned by the API, with NO cleaning, NO brand
parsing, NO size parsing. This is the immutable raw snapshot.

The only field dropped is "inventory_modifiers": it is an internal
operational blob (~17KB per record, ~80% of total record size) with
zero analytical value for pricing/brand work, so keeping it would
bloat the raw snapshot ~5x for no benefit.

Output: data/raw/stores/danube/danube_raw_<timestamp>.json

Run transform_danube.py afterwards to produce the cleaned dataset.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

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

# حقول ضخمة عديمة الفائدة التحليلية نستثنيها من اللقطة الخام لتوفير المساحة
DROP_FIELDS = ["inventory_modifiers"]


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def raw_output_dir() -> Path:
    path = project_root() / "data" / "raw" / "stores" / "danube"
    path.mkdir(parents=True, exist_ok=True)
    return path


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


def fetch_category_raw(category_key: str, taxon_value: str) -> list[dict]:
    print(f"\n[{category_key}] Fetching raw hits from Algolia...")

    all_hits: list[dict] = []
    page = 0
    nb_pages = 1

    while page < nb_pages and page < MAX_PAGES_SAFETY:
        hits, nb_pages = fetch_page(taxon_value, page)
        if not hits:
            break
        for hit in hits:
            hit["_category_key"] = category_key
            for field in DROP_FIELDS:
                hit.pop(field, None)
        all_hits.extend(hits)
        print(f"  page {page + 1}/{nb_pages}: {len(hits)} hits (total: {len(all_hits)})")
        page += 1
        time.sleep(0.5)

    print(f"[{category_key}] Raw hits collected: {len(all_hits)}")
    return all_hits


def save_raw_file(all_hits: list[dict]) -> Path:
    timestamp = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    result = {
        "store": "Danube Online",
        "source": "algolia_api",
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hits_count": len(all_hits),
        "hits": all_hits,
    }
    path = raw_output_dir() / f"danube_raw_{timestamp}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    latest_path = raw_output_dir() / "danube_raw_latest.json"
    latest_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return path


def extract_danube_raw() -> list[dict]:
    print("=" * 60)
    print("STARTING DANUBE RAW EXTRACTION (NO CLEANING)")
    print("=" * 60)

    all_hits: list[dict] = []
    for category_key, taxon_value in CATEGORIES.items():
        try:
            hits = fetch_category_raw(category_key, taxon_value)
        except requests.RequestException as exc:
            print(f"[{category_key}] ERROR: API request failed: {exc}")
            hits = []
        except Exception as exc:
            print(f"[{category_key}] ERROR: {type(exc).__name__}: {exc}")
            hits = []
        all_hits.extend(hits)

    path = save_raw_file(all_hits)

    print("\n" + "=" * 60)
    print("DANUBE RAW EXTRACTION FINISHED")
    print("=" * 60)
    print(f"  Total raw hits: {len(all_hits)}")
    print(f"  Saved to: {path}")
    print(f"  Also saved to: danube_raw_latest.json (used by transform_danube.py)")

    return all_hits


if __name__ == "__main__":
    extract_danube_raw()