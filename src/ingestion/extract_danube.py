"""Extract public Danube category product results from the Algolia search endpoint.

هذا السكربت يقرأ إعدادات المشروع من ملف .env.danube في جذر المشروع،
ويتحقق من وجود المفاتيح المطلوبة قبل إرسال أي طلب، ثم يحفظ كل نتائج قسم
(بعد تجميع كل صفحاته) في ملف منتجات نظيف واحد فقط لكل قسم.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv


CATEGORIES = {
    "dairy_eggs": {
        "display_name": "Dairy & Eggs",
        "facet_filter": "taxons_ar.lvl1:الأقسام > منتجات الألبان والبيض",
    },
    "fresh_fruits_vegetables": {
        "display_name": "Fresh Fruits & Vegetables",
        "facet_filter": "taxons_ar.lvl1:الأقسام > فواكه و خضروات طازجة",
    },
    "water_beverages": {
        "display_name": "Water & Beverages",
        "facet_filter": "taxons_ar.lvl1:الأقسام > الماء و المشروبات",
    },
}

HITS_PER_PAGE = 1000


def load_config():
    project_root = Path(__file__).resolve().parents[2]
    env_path = project_root / ".env.danube"

    load_dotenv(dotenv_path=str(env_path), override=False)

    application_id = os.getenv("DANUBE_ALGOLIA_APPLICATION_ID", "").strip()
    api_key = os.getenv("DANUBE_ALGOLIA_SEARCH_API_KEY", "").strip()
    index_name = os.getenv("DANUBE_INDEX_NAME", "spree_products").strip() or "spree_products"
    tenant_id = os.getenv("DANUBE_TENANT_ID", "1").strip() or "1"
    request_delay_seconds = float(os.getenv("DANUBE_REQUEST_DELAY_SECONDS", "3").strip() or "3")

    if not application_id or not api_key:
        raise ValueError(
            "DANUBE_ALGOLIA_APPLICATION_ID and DANUBE_ALGOLIA_SEARCH_API_KEY are missing from "
            "the project-root .env.danube file. Add them before starting the Danube extractor."
        )

    return {
        "project_root": project_root,
        "application_id": application_id,
        "api_key": api_key,
        "index_name": index_name,
        "tenant_id": tenant_id,
        "request_delay_seconds": request_delay_seconds,
    }


def build_single_category_payload(index_name, tenant_id, facet_filter, page):
    search_params = {
        "query": "",
        "maxValuesPerFacet": 9999,
        "page": page,
        "hitsPerPage": HITS_PER_PAGE,
        "filters": f"tenant_id = {tenant_id}",
        "facets": json.dumps(
            ["price", "taxons_ar.lvl0", "taxons_ar.lvl1", "taxons_ar.lvl2", "taxons_ar.lvl3"],
            ensure_ascii=False,
        ),
        "tagFilters": "",
        "facetFilters": json.dumps([[facet_filter]], ensure_ascii=False),
        "attributesToRetrieve": json.dumps(["*"]),
        "attributesToHighlight": json.dumps([]),
        "attributesToSnippet": json.dumps([]),
        "analytics": "false",
        "clickAnalytics": "false",
    }

    params_string = urlencode(search_params)
    return {"requests": [{"indexName": index_name, "params": params_string}]}


def build_endpoint(application_id):
    return f"https://{application_id}-dsn.algolia.net/1/indexes/*/queries"


def fetch_algolia_response(endpoint, headers, payload):
    response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def ensure_output_directory(project_root):
    output_dir = project_root / "data" / "raw" / "stores" / "danube"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def save_json(output_path, data):
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def fetch_all_pages_for_category(endpoint, headers, index_name, tenant_id, category, request_delay_seconds):
    all_hits = []
    page = 0

    while True:
        payload = build_single_category_payload(
            index_name=index_name,
            tenant_id=tenant_id,
            facet_filter=category["facet_filter"],
            page=page,
        )

        response_data = fetch_algolia_response(endpoint, headers, payload)
        result = response_data["results"][0]

        hits = result.get("hits", [])
        nb_hits = result.get("nbHits", 0)
        nb_pages = result.get("nbPages", 0)

        all_hits.extend(hits)

        print(
            "[" + category["display_name"] + "] page " + str(page + 1) + "/" + str(nb_pages) +
            " | got=" + str(len(hits)) +
            " | total_reported=" + str(nb_hits) +
            " | collected_so_far=" + str(len(all_hits))
        )

        if not hits or page + 1 >= nb_pages:
            break

        page += 1
        time.sleep(request_delay_seconds)

    print("[" + category["display_name"] + "] DONE. Collected " + str(len(all_hits)) + " products.")
    return all_hits


def clean_text(value):
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def get_main_category_path(hit):
    taxons = hit.get("taxons_ar", {})
    if not isinstance(taxons, dict):
        return None

    for level in ("lvl3", "lvl2", "lvl1"):
        paths = taxons.get(level, [])
        if not isinstance(paths, list):
            continue

        valid_paths = [
            clean_text(p) for p in paths
            if clean_text(p).startswith("الأقسام >")
            and "العروض الأسبوعية" not in clean_text(p)
        ]
        if valid_paths:
            return max(valid_paths, key=lambda p: p.count(">"))

    return None


def parse_category(path):
    if not path:
        return {"department_ar": None, "category_ar": None, "subcategory_ar": None}

    parts = [clean_text(p) for p in path.split(">")]
    return {
        "department_ar": parts[1] if len(parts) > 1 else None,
        "category_ar": parts[2] if len(parts) > 2 else None,
        "subcategory_ar": parts[3] if len(parts) > 3 else None,
    }


def simplify_hit(hit):
    """
    يحول hit خام من Danube إلى منتج نظيف واحد فقط.

    بدل حفظ ملف أسعار فروع منفصل، نحسب هنا أرخص سعر متاح فعليًا
    بين كل الفروع (min_branch_price) ونضعه داخل نفس المنتج،
    فتحصل على سعرين مفيدين بدون تعقيد inventory_modifiers الخام:
    - base_price: السعر المعروض عمومًا للمنتج
    - min_branch_price: أرخص سعر فعلي موجود في أي فرع
    """
    category_path = get_main_category_path(hit)
    category_data = parse_category(category_path)

    inventory_modifiers = hit.get("inventory_modifiers", {})
    available_prices = []
    if isinstance(inventory_modifiers, dict):
        for modifier in inventory_modifiers.values():
            if isinstance(modifier, dict) and modifier.get("price") not in (None, ""):
                available_prices.append(float(modifier["price"]))

    min_price = min(available_prices) if available_prices else hit.get("price")

    product = {
        "master_id": hit.get("master_id"),
        "tenant_id": hit.get("tenant_id"),
        "name_ar": hit.get("full_name_ar") or hit.get("name_ar"),
        "name_en": hit.get("full_name_en") or hit.get("name_en"),
        "base_price": hit.get("price"),
        "min_branch_price": min_price,
        "on_sale": hit.get("on_sale"),
        "original_price": hit.get("original_price"),
        "url_ar": hit.get("url_ar"),
        "url_en": hit.get("url_en"),
        "image": hit.get("image"),
        "weighted": hit.get("weighted"),
        "department_ar": category_data["department_ar"],
        "category_ar": category_data["category_ar"],
        "subcategory_ar": category_data["subcategory_ar"],
        "category_path_ar": category_path,
    }

    return {"product": product}


def extract_danube_prices():
    print("STARTING SCRIPT NOW...")

    config = load_config()
    project_root = config["project_root"]

    output_dir = ensure_output_directory(project_root)
    endpoint = build_endpoint(str(config["application_id"]))

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Algolia-Application-Id": str(config["application_id"]),
        "X-Algolia-API-Key": str(config["api_key"]),
        "X-Algolia-Agent": "SaudiFMCGPricePipeline/0.1",
    }

    saved_paths = []

    for category_key, category in CATEGORIES.items():
        all_hits = fetch_all_pages_for_category(
            endpoint=endpoint,
            headers=headers,
            index_name=str(config["index_name"]),
            tenant_id=str(config["tenant_id"]),
            category=category,
            request_delay_seconds=float(config["request_delay_seconds"]),
        )

        products = []
        for hit in all_hits:
            simplified = simplify_hit(hit)
            products.append(simplified["product"])

        products_path = output_dir / (category_key + "_products.json")
        save_json(products_path, products)

        print(
            "[" + category["display_name"] + "] saved " + str(len(products)) + " products"
        )

        saved_paths.append(str(products_path))

    print("SCRIPT FINISHED")
    return saved_paths


if __name__ == "__main__":
    extract_danube_prices()