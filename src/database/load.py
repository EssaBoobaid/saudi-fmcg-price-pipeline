"""=============================================================================
Module: Database Loader & Warehouse Synchronizer
Layer: Gold Layer (ETL Load Stage)
Description:
    نقل وحقن البيانات المعالجة داخل جداول PostgreSQL المنشأة في schema.sql.

Key Functions:
    1. إدارة الاتصال بقاعدة البيانات عبر SQLAlchemy Engine و psycopg2.
    2. إدخال وتحديث بيانات المنتجات والمتاجر بنظام الدمج (UPSERT / ON CONFLICT).
    3. تسجيل الأسعار اليومية في جدول الحقائق (Fact_Daily_Prices) بدون تكرار لنفس اليوم.
    4. تسجيل بيانات الأسعار الحكومية المرجعية في (Fact_Official_Benchmarks).
============================================================================="""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


load_dotenv(Path(__file__).resolve().parents[2] / '.env')

DB_CONFIG = {
    'dbname': os.getenv('POSTGRES_DB', 'fmcg'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', 'postgres'),
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': os.getenv('POSTGRES_PORT', '5432'),
}


def get_engine():
    db_url = (
        f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}@"
        f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}"
    )
    return create_engine(db_url)


def init_db():
    schema_path = Path(__file__).resolve().parent / 'schema.sql'
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_sql = f.read()

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(schema_sql))

    print('Database schema initialized successfully.')


if __name__ == '__main__':
    init_db()
