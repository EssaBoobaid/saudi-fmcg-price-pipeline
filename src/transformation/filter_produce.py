# src/transformation/filter_produce.py

import re

def get_produce_keywords():
    """استخراج جميع أسماء الفواكه والخضار من القاموس"""
    from .produce_matcher import PRODUCE_MAPPING
    return list(PRODUCE_MAPPING.keys())

def is_produce(product_name):
    """التحقق إذا كان المنتج فاكهة أو خضار"""
    keywords = get_produce_keywords()
    product_name = product_name.lower()
    
    for keyword in keywords:
        if keyword in product_name:
            return True
    return False

def filter_produce(df):
    """تصفية البيانات لتبقى الفواكه والخضار فقط"""
    return df[df['product_name'].apply(is_produce)]