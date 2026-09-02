# Saudi FMCG Price Pipeline

مشروع ETL لفهرسة وأسعار السلع الاستهلاكية في السوق السعودي، مع جمع البيانات من متاجر مختلفة مثل Tamimi وBanda وDanube، وتنظيفها، ومطابقتها بالباركود، ثم تحميلها إلى قاعدة بيانات PostgreSQL.

## هدف المشروع

هدف هذا المشروع هو بناء نظام قابل للفهم والتطوير، بحيث يشتغل كل عضو في الفريق على متجر محدد، ويخرج بيانات قابلة للتحليل دون خلط بين البيانات الخام والمعالجة والملفات التجريبية.

## هيكل المشروع

- .github/workflows: مسارات الأتمتة باستخدام GitHub Actions
- data/raw: بيانات خام من كل متجر وبيانات مرجعية مفتوحة
- data/processed: بيانات منقّحة ومجموعة جاهزة للتحليل
- src/ingestion: سكربتات استخراج البيانات من مصادر مختلفة
- src/crawlers: زواحف الكتالوج الكامل لكل متجر
- src/transformation: تنظيف وتحويل وتوحيد البيانات
- src/database: مخطط قاعدة البيانات وملف التحميل
- src/utils: أدوات مساعدة مثل توليد العينات

## طبقات البيانات

### 1. Raw
البيانات الخام التي جُمعت من المتاجر بدون تعديل.

- كل متجر له مجلد خاص داخل data/raw/stores
- لا يلمس هذا الملف إلا المالك أو المسؤول عن هذا المتجر

### 2. Sample
عينة صغيرة للاختبار والتحقق، عادة 5 منتجات لكل فئة.

- تستخدم للـ QA ومرحلة فهم البيانات
- لا تُستخدم كملف نهائي

### 3. Processed
البيانات المنقّحة والمجمّعة للتجهيز والتحليل.

- central_product_catalog.json
- gastat_food_prices_clean.csv

### 4. Central catalog
هو الملف النهائي الذي يجمع كل المتاجر في تنسيق موحّد.

## نموذج عمل الفريق

### كل عضو يحمل متجرًا محددًا

- Banda Team
- Tamimi Team
- Danube Team

### كل متجر يجب أن يحتوي على:

- ملف raw كامل
- ملف sample صغير
- سجل واضح للبيانات
- التزام بنفس أسماء الأعمدة

## مسؤوليات كل متجر

### Banda
- استخراج البيانات الخام من Banda
- حفظها في data/raw/stores/banda
- إنشاء sample_5_per_category.json
- تأكيد جودة الحقول

### Tamimi
- استخراج البيانات الخام من Tamimi
- حفظها في data/raw/stores/tamimi
- إنشاء sample_5_per_category.json
- التحقق من السعر، العلامة، والفئة

### Danube
- استخراج البيانات الخام من Danube
- حفظها في data/raw/stores/danube
- إنشاء sample_5_per_category.json
- التحقق من تطابق الباركود والاسم

## قواعد مهمة

- Raw يبقى كما هو، لا تعدّل فيه
- Sample فقط للاختبار
- Processed فقط للبيانات النهائية
- Central catalog هو مصدر التحليل النهائي
- لا تخلط بين البيانات الخام والمعالجة

## التشغيل السريع

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 src/utils/generate_store_samples.py
```

## الملفات الأساسية

- [data/raw/stores](data/raw/stores)
- [data/processed](data/processed)
- [src/crawlers](src/crawlers)
- [src/ETL/build_central_catalog.py](src/ETL/build_central_catalog.py)
- [src/transformation/clean_gastat_food.py](src/transformation/clean_gastat_food.py)

## المكونات الرئيسية

### 1. Ingestion
مجموعة سكربتات لجمع البيانات من مختلف المصارف/المتاجر، مثل:
- tamimi.py
- extract_banda.py
- nana.py

كل سكربت مسؤول عن:
- طلب البيانات أو قراءة ملف JSON
- تحويل البنية الخام إلى تنسيق موحد
- حفظ البيانات في data/raw

### 2. Full Catalog Crawlers
لجمع الكتالوج الكامل عبر التصنيفات والترقيم، اضبط نقاط API الرسمية أو المصرح بها
في ملف `.env` ثم شغّل:

```bash
python -m src.crawlers.run_all_crawlers
```

وتحفظ النتائج في:
- `data/raw/stores/tamimi_full_catalog.json`
- `data/raw/stores/danube_full_catalog.json`
- `data/raw/stores/banda_full_catalog.json`

### 3. Transformation
تتولى هذه المرحلة:
- تنظيف الحقول
- إزالة القيم المكررة
- توحيد أسماء المنتجات
- تطبيع أسماء العلامات/السلالات
- مطابقة المنتج على أساس الباركود أو اسم المنتج
- إنشاء بيانات جاهزة للتحميل

### 4. Database
يحتوي على:
- schema.sql: تعريف الجداول والقيود
- load.py: تحميل البيانات إلى PostgreSQL

### 5. Utils
دوال مساعدة مثل:
- إعداد الاتصال بقاعدة البيانات
- إنشاء رؤوس HTTP/Headers للطلبات
- وظائف تنظيف النصوص
- وظائف لتسجيل الأحداث

## المتطلبات

- Python 3.11+
- PostgreSQL 15+
- Docker Desktop (اختياري للتشغيل المحلي)
- GitHub Actions

## التثبيت

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

## تشغيل PostgreSQL محلياً

```bash
docker-compose up -d
```

## مثال متغيرات البيئة

```bash
cp .env.example .env
```

ثم عدّل القيم في الملف .env حسب إعداداتك المحلية.

> ملاحظة: تم رفع ملف `.env` مؤقتًا لأن المشروع خاص بمعسكر تدريبي ومغلق على أعضاء الفريق فقط. في المشاريع العامة أو البيئات الإنتاجية، يجب نقل هذه الإعدادات إلى GitHub Secrets أو مدير أسرار ثم إضافتها إلى `.gitignore` لتجنب حفظها في المستودع.

## هيكل البيانات المقترح

### جدول products
- id
- barcode
- product_name
- brand
- category
- sku
- source
- created_at

### جدول prices
- id
- product_id
- store_name
- price
- currency
- price_date
- source_url
- created_at

## ملاحظات

- يتم حفظ البيانات الخام في data/raw كنسخة أصلية غير محدثة.
- يتم الاحتفاظ ببيانات معالجة أو محسّنة داخل data/processed.
- يفضل أن يكون كل مصدر بيانات له سكربت مستقل.
- في مرحلة لاحقة يمكن إضافة: جدول للخصومات، جدول للتنبيهات، أو مشغل ETL مجدول.

## خطة التطوير

1. إعداد اتصال قاعدة البيانات وملف المخطط SQL
2. بناء السكربتات الأولى لسحب البيانات من المتاجر
3. بناء طبقة التنظيف والتطبيع
4. اختبار تطابق المنتجات بالباركود
5. تشغيل التحميل إلى PostgreSQL
6. إضافة CI/CD مع GitHub Actions
