# src/transformation/match_produce.py

import re
from .produce_matcher import PRODUCE_MAPPING

class ProduceMatcher:
    def __init__(self):
        self.mapping = PRODUCE_MAPPING
        self.all_names = self._build_name_index()
    
    def _build_name_index(self):
        """بناء فهرس لجميع الأسماء"""
        index = {}
        for main_name, synonyms in self.mapping.items():
            index[main_name] = main_name  # الاسم الرئيسي
            for synonym in synonyms:
                index[synonym] = main_name  # المرادفات تشير إلى الرئيسي
        return index
    
    def match(self, gastat_name, store_products):
        """
        تطابق منتج من GASTAT مع منتجات المتجر
        Returns: (matched_product_name, confidence_score)
        """
        gastat_name = gastat_name.strip()
        
        # 1. تطابق تام
        if gastat_name in store_products:
            return gastat_name, 1.0
        
        # 2. تطابق بالقاموس
        if gastat_name in self.all_names:
            main_name = self.all_names[gastat_name]
            # ابحث عن أي مرادف في المتجر
            for product in store_products:
                if product in self.mapping.get(main_name, []):
                    return product, 0.9
                if product == main_name:
                    return product, 0.9
        
        # 3. تطابق بالكلمات المفتاحية
        for product in store_products:
            # تحقق إذا كان اسم GASTAT جزء من اسم المنتج
            if gastat_name in product or product in gastat_name:
                return product, 0.7
        
        # 4. تطابق جزئي (أقل دقة)
        gastat_words = set(gastat_name.split())
        for product in store_products:
            product_words = set(product.split())
            intersection = gastat_words & product_words
            if len(intersection) >= 1:
                return product, 0.5
        
        return None, 0.0