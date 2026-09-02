from pathlib import Path
import json

from playwright.sync_api import sync_playwright


categories = {
    "Juices": {
        "category_id": 386,
        "parent_category_id": 2888,
        "pages": 13
    },
    "Dairy & Eggs": {
        "category_id": 356,
        "parent_category_id": 311,
        "pages": 10
    },
    "Fruits & Vegetables": {
        "category_id": 352,
        "parent_category_id": 311,
        "pages": 6
    }
}


def project_root():
    return Path(__file__).resolve().parents[2]


def output_path():
    path = (
        project_root()
        / "data"
        / "raw"
        / "stores"
        / "panda"
        / "panda_data.json"
    )

    path.parent.mkdir(parents=True, exist_ok=True)

    return path


def extract_panda_prices():

    all_products = []

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for category, info in categories.items():

            print("\n==============================")
            print(f"--- {category} ---")
            print(f"Pages: {info['pages']}")
            print("==============================")

            category_products = []

            for page_number in range(1, info["pages"] + 1):

                print(
                    f"Processing page "
                    f"{page_number}/{info['pages']}..."
                )

                url = (
                    f"https://www.panda.sa/en/plp?"
                    f"category_id={info['category_id']}"
                    f"&parent_category_id={info['parent_category_id']}"
                )

                if page_number > 1:
                    url += f"&page={page_number}"

                page.goto(
                    url,
                    wait_until="domcontentloaded"
                )

                page.wait_for_load_state("networkidle")

                # كل النص الموجود في الصفحة
                lines = [
                    line.strip()
                    for line in page.locator("body")
                    .inner_text()
                    .splitlines()
                    if line.strip()
                ]

                # تحديد بداية كل منتج
                product_indexes = []

                for i in range(len(lines) - 1):

                    if lines[i + 1] == category:
                        product_indexes.append(i)

                products = []

                for position, start_index in enumerate(product_indexes):

                    # تحديد نهاية بيانات المنتج الحالي
                    if position + 1 < len(product_indexes):
                        end_index = product_indexes[position + 1]
                    else:
                        end_index = len(lines)

                    product_block = lines[start_index:end_index]

                    if not product_block:
                        continue

                    product_name = product_block[0]

                    # الوحدة
                    unit = None

                    if len(product_block) > 2:

                        possible_unit = product_block[-1]

                        for value in product_block:

                            value_lower = value.lower()

                            if any(
                                x in value_lower
                                for x in [
                                    "ml",
                                    " l",
                                    "gm",
                                    "kg",
                                    "piece",
                                    " g",
                                    " ml"
                                ]
                            ):
                                unit = value
                                break

                    # استخراج جميع الأرقام الموجودة في بيانات المنتج
                    numeric_values = []

                    for value in product_block:

                        try:
                            number = float(value)

                            if number >= 0:
                                numeric_values.append(number)

                        except ValueError:
                            continue

                    # السعر الأساسي المتاح
                    price = None

                    if numeric_values:
                        price = numeric_values[-1]

                    # نحفظ كل البيانات الخام الخاصة بالمنتج
                    raw_data = product_block

                    product = {
                        "store": "Panda",
                        "product_name": product_name,
                        "category": category,
                        "unit": unit,
                        "price": price,
                        "raw_data": raw_data
                    }

                    products.append(product)

                # إزالة التكرار داخل الفئة
                for product in products:

                    if product not in category_products:
                        category_products.append(product)

                print(
                    f"   Products found on page: "
                    f"{len(products)}"
                )

            all_products.extend(category_products)

            print(
                f"\nTotal unique products in "
                f"{category}: "
                f"{len(category_products)}"
            )

        # حفظ البيانات
        path = output_path()

        path.write_text(
            json.dumps(
                all_products,
                ensure_ascii=False,
                indent=4
            ),
            encoding="utf-8"
        )

        print("\n==============================")
        print("PANDA EXTRACTION COMPLETE")
        print("==============================")
        print(
            f"Total products: "
            f"{len(all_products)}"
        )
        print(f"Saved to: {path}")
        print("==============================")

        browser.close()

    return all_products


if __name__ == "__main__":
    extract_panda_prices()