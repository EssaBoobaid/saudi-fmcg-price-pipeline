/*******************************************************************************
 * Script: Data Warehouse DDL Schema Definition
 * Architecture: Star Schema (Kimball Methodology)
 * Layer: Gold Layer (Analytical Data Storage)
 * Database: PostgreSQL
 *
 * Description:
 *     يحتوي هذا الملف على تعريف بنية مستودع البيانات:
 *     - جداول الأبعاد (Dimensions):
 *         1. Dim_Products: الكتالوج الموحد للمنتجات والمواصفات المعيارية والباركود.
 *         2. Dim_Stores: بيانات المتاجر وسلاسل التجزئة ونوع المنصة.
 *         3. Dim_Location: المدن والمناطق لمطابقة المسوحات الجغرافية.
 *         4. Dim_Date: التقويم الزمني للتحليلات الزمنية والمواسم.
 *     - جداول الحقائق (Facts):
 *         1. Fact_Daily_Prices: تسجيل الأسعار اليومية للمتاجر ونسب التخفيض وتوفر المخزون.
 *         2. Fact_Official_Benchmarks: تسجيل متوسطات الأسعار الحكومية المرجعية.
 *     - الفهارس (Indexes): لتسريع عمليات الربط والتجميع التحليلي.
 ******************************************************************************/

CREATE TABLE IF NOT EXISTS Dim_Products (
    product_id SERIAL PRIMARY KEY,
    barcode VARCHAR(50),
    product_name_ar TEXT NOT NULL,
    brand VARCHAR(200),
    category VARCHAR(150),
    standard_unit VARCHAR(50),
    standard_size VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (barcode)
);

CREATE TABLE IF NOT EXISTS Dim_Stores (
    store_id SERIAL PRIMARY KEY,
    store_name VARCHAR(150) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Dim_Location (
    location_id SERIAL PRIMARY KEY,
    city_name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Dim_Date (
    date_id DATE PRIMARY KEY,
    year_num INT NOT NULL,
    month_num INT NOT NULL,
    day_num INT NOT NULL,
    quarter_num INT NOT NULL,
    day_name VARCHAR(20),
    is_weekend BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS Fact_Daily_Prices (
    fact_daily_price_id SERIAL PRIMARY KEY,
    product_id INT NOT NULL REFERENCES Dim_Products(product_id) ON DELETE CASCADE,
    store_id INT NOT NULL REFERENCES Dim_Stores(store_id) ON DELETE CASCADE,
    location_id INT REFERENCES Dim_Location(location_id) ON DELETE SET NULL,
    date_id DATE NOT NULL REFERENCES Dim_Date(date_id),
    regular_price NUMERIC(12, 3),
    sell_price NUMERIC(12, 3),
    discount_amount NUMERIC(12, 3),
    discount_percent NUMERIC(5, 2),
    is_promo BOOLEAN NOT NULL DEFAULT FALSE,
    stock_status VARCHAR(50),
    source_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Fact_Official_Benchmarks (
    benchmark_id SERIAL PRIMARY KEY,
    product_id INT NOT NULL REFERENCES Dim_Products(product_id) ON DELETE CASCADE,
    location_id INT NOT NULL REFERENCES Dim_Location(location_id) ON DELETE CASCADE,
    date_id DATE NOT NULL REFERENCES Dim_Date(date_id),
    official_avg_price NUMERIC(12, 3),
    official_min_price NUMERIC(12, 3),
    official_max_price NUMERIC(12, 3),
    source_name VARCHAR(150),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO Dim_Stores (store_name)
VALUES ('Tamimi Markets'), ('Amazon'), ('Danube')
ON CONFLICT (store_name) DO NOTHING;

INSERT INTO Dim_Location (city_name)
VALUES ('Dammam'), ('Riyadh'), ('Jeddah')
ON CONFLICT (city_name) DO NOTHING;

WITH RECURSIVE dates AS (
    SELECT DATE '2024-01-01' AS day_id
    UNION ALL
    SELECT (day_id + INTERVAL '1 day')::DATE
    FROM dates
    WHERE day_id < DATE '2026-12-31'
)
INSERT INTO Dim_Date (date_id, year_num, month_num, day_num, quarter_num, day_name, is_weekend)
SELECT
    day_id,
    EXTRACT(YEAR FROM day_id)::INT AS year_num,
    EXTRACT(MONTH FROM day_id)::INT AS month_num,
    EXTRACT(DAY FROM day_id)::INT AS day_num,
    ((EXTRACT(MONTH FROM day_id)::INT - 1) / 3) + 1 AS quarter_num,
    TO_CHAR(day_id, 'Day') AS day_name,
    CASE WHEN EXTRACT(ISODOW FROM day_id) IN (6,7) THEN TRUE ELSE FALSE END AS is_weekend
FROM dates
ON CONFLICT (date_id) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_dim_products_barcode ON Dim_Products(barcode);
CREATE INDEX IF NOT EXISTS idx_dim_products_brand ON Dim_Products(brand);
CREATE INDEX IF NOT EXISTS idx_fact_daily_prices_product_date ON Fact_Daily_Prices(product_id, date_id);
CREATE INDEX IF NOT EXISTS idx_fact_daily_prices_store_date ON Fact_Daily_Prices(store_id, date_id);
CREATE INDEX IF NOT EXISTS idx_fact_daily_prices_product_store ON Fact_Daily_Prices(product_id, store_id);
CREATE INDEX IF NOT EXISTS idx_fact_official_benchmarks_product_date ON Fact_Official_Benchmarks(product_id, date_id);
CREATE INDEX IF NOT EXISTS idx_fact_official_benchmarks_location_date ON Fact_Official_Benchmarks(location_id, date_id);
