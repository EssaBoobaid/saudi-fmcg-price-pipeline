from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


# ============================================================
# PATHS
# ============================================================

PROCESSED_STORES_DIR = Path("data/processed/stores")
OUTPUT_DIR = Path("data/processed/matches")

STORE_FILES = {
    "danube": PROCESSED_STORES_DIR / "danube" / "danube_clean_latest.json",
    "bindawood": PROCESSED_STORES_DIR / "bindawood" / "bindawood_clean_latest.json",
    "tamimi": PROCESSED_STORES_DIR / "tamimi" / "tamimi_clean_latest.json",
}

OUTPUT_FILE = OUTPUT_DIR / "unified_products_latest.json"
PRODUCE_OUTPUT_FILE = OUTPUT_DIR / "unified_produce_latest.json"


# ============================================================
# PRODUCE (FRUITS & VEGETABLES) MAPPING - موسع ومحسن
# ============================================================

PRODUCE_MAPPING = {
    # ===== الفواكه =====
    'موز': [
        'موز بلدي', 'موز مستورد', 'موز',
        'banana', 'bananas',
        'شربتلي', 'الفلبين', 'موز الشربتلي', 'موز الشربتلي الفلبين',
        'Philippine Banana', 'موز الفلبين', 'موز فلبيني',
        'موز كبير', 'موز صغير', 'موز هندي',
        'موز الصغير', 'موز الكبير', 'Banana pack', 'Banana berry mix'
    ],
    'تفاح': [
        'تفاح أحمر', 'تفاح أخضر', 'تفاح جولدن', 'تفاح محلي', 'تفاح مستورد',
        'تفاح', 'apple', 'apples', 'فوجي', 'تفاح فوجي', 'تفاح ريد',
        'تفاح جراني', 'تفاح مصري', 'تفاح سعودي', 'تفاح احمر', 'تفاح اخضر',
        'Red apple', 'Green apple', 'Golden apple'
    ],
    'عنب': [
        'عنب أحمر', 'عنب أخضر', 'عنب أسود', 'عنب محلي', 'عنب طائفي',
        'عنب', 'grape', 'grapes', 'عنب سكري', 'عنب مستورد',
        'عنب لبناني', 'عنب سعودي', 'عنب مصري', 'عنب احمر', 'عنب اخضر',
        'Red grape', 'Green grape', 'Black grape', 'Lebanese grape'
    ],
    'برتقال': [
        'برتقال أبو سرة', 'برتقال بلدي', 'برتقال مستورد', 'برتقال',
        'orange', 'oranges',
        'سرة', 'برتقال سرة', 'برتقال مصري',
        'برتقال سعودي', 'برتقال حلواني', 'برتقال ابو سرة',
        'برتقال أبو صرة مصري', 'Abu Sura orange',
        'برتقال كبير', 'برتقال صغير', 'برتقال أبو صرة'
    ],
    'فراولة': [
        'فراولة محلية', 'فراولة مستوردة', 'فراولة كبيرة', 'فراولة',
        'strawberry', 'strawberries', 'فراولة سعودية', 'فراولة مصرية',
        'فراوله', 'فريز', 'strawberry pack'
    ],
    'مانجو': [
        'مانجو هندي', 'مانجو مصري', 'مانجو محلي', 'مانجو',
        'mango', 'mangoes', 'مانجو عوافي', 'مانجو كيت', 'مانجو مستورد',
        'مانجو سعودي', 'مانجو هندي', 'مانجو كبير', 'مانجو صغير'
    ],
  'بطيخ': [
    'بطيخ أحمر', 'بطيخ أصفر', 'بطيخ مستورد', 'بطيخ',
    'watermelon', 'بطيخ سعودي', 'بطيخ مصري', 'بطيخ كبير',
    'بطيخ احمر', 'بطيخ اصفر', 'جبس', 'بطيخ مستدير',
    'حبحب', 'حبحب بطيخ', 'حباحب', 'حباحب بطيخ'
],

    'شمام': [
        'شمام بلدي', 'شمام مستورد', 'شمام',
        'cantaloupe', 'melon', 'شمام سعودي', 'شمام مصري',
        'شمام اصفر', 'شمام اخضر', 'شمام كبير'
    ],
    'رمان': [
        'رمان بلدي', 'رمان مستورد', 'رمان حلو', 'رمان',
        'pomegranate', 'رمان سعودي', 'رمان مصري', 'رمان وردي',
        'رمان احمر', 'رمان كبير', 'رمان صغير'
    ],
    'جوافة': [
        'جوافة محلية', 'جوافة مستوردة', 'جوافة',
        'guava', 'جوافة سعودية', 'جوافة مصرية',
        'جوافه', 'جوافة كبيرة', 'جوافة صغيرة'
    ],
    'ليمون': [
        'ليمون بلدي', 'ليمون مستورد', 'ليمون',
        'lemon', 'lemons',
        'ليمون سعودي', 'ليمون مصري', 'ليمون حامض',
        'ليمون اخضر', 'ليمون اصفر', 'ليمون كبير', 'ليمون صغير',
        'ليمون وسط أفريقي', 'African lemon',
        'ليمون بني', 'ليمون عضوي', 'ليمون طازج'
    ],
    'تمر': [
        'تمر بلدي', 'تمر مستورد', 'تمر',
        'dates', 'date',
        'تمر سكري', 'تمر صقعي', 'تمر خلاص', 'تمر برحي',
        'تمر مجدول', 'تمر عجوه', 'تمر سعودي', 'تمر المدينة',
        'رطب', 'تمر رطب', 'Sukkary', 'Rutab', 'Sukkary Rutab', 'Sukkary Rutab Dates',
        'تمر المدينة المنورة', 'تمر القصيم', 'تمر الأحساء',
        'تمر جاف', 'تمر طازج', 'تمر كبير', 'تمر صغير'
    ],
    'تين': [
        'تين بلدي', 'تين مستورد', 'تين',
        'fig', 'figs',
        'تين مجفف', 'تين طازج',
        'تين اسود', 'تين اخضر', 'تين كبير', 'تين صغير',
        'تين شوكي', 'تين بري', 'تين مجفف عضوي'
    ],
    'يوسفي': [
        'يوسفي بلدي', 'يوسفي مستورد', 'يوسفي',
        'tangerine', 'mandarin',
        'يوسفي سعودي', 'يوسفي مصري',
        'يوسفي كبير', 'يوسفي صغير',
        'يوسفي باكستاني', 'Pakistani tangerine',
        'يوسفي جاف', 'يوسفي طازج', 'يوسفي عضوي'
    ],
    'أناناس': [
        'أناناس مستورد', 'أناناس طازج', 'أناناس',
        'pineapple', 'أناناس فليبيني', 'أناناس كامل',
        'أناناس كبير', 'أناناس صغير'
    ],
    'كيوي': [
        'كيوي مستورد', 'كيوي طازج', 'كيوي',
        'kiwi', 'كيوي اخضر', 'كيوي ذهبي',
        'كيوي كبير', 'كيوي صغير'
    ],
    'خوخ': [
        'خوخ محلي', 'خوخ مستورد', 'خوخ',
        'peach', 'peaches', 'خوخ سعودي', 'خوخ مصري', 'خوخ كبير',
        'خوخ احمر', 'خوخ اصفر', 'خوخ طازج'
    ],
    'نكتارين': [
        'نكتارين محلي', 'نكتارين مستورد', 'نكتارين',
        'nectarine', 'نكتارين سعودي', 'نكتارين مصري',
        'نكتارين كبير', 'نكتارين صغير'
    ],
    'كمثرى': [
        'كمثرى محلي', 'كمثرى مستورد', 'كمثرى',
        'pear', 'pears', 'كمثرى سعودي', 'كمثرى مصري',
        'كمثري', 'اجاص', 'كمثرى كبير', 'كمثرى صغير'
    ],
    'أفوكادو': [
        'أفوكادو مستورد', 'أفوكادو كبير', 'أفوكادو',
        'avocado', 'أفوكادو هاس', 'أفوكادو مكسيكي',
        'افوكادو', 'أفوكادو طازج', 'أفوكادو عضوي'
    ],
    'توت': [
        'توت بري', 'توت أسود', 'توت أحمر', 'توت',
        'berry', 'berries', 'blueberry', 'raspberry', 'توت شوكي',
        'توت اسود', 'توت احمر', 'توت طازج', 'توت مجمد'
    ],
    'كرز': [
        'كرز محلي', 'كرز مستورد', 'كرز',
        'cherry', 'cherries', 'كرز حلبي', 'كرز كبير',
        'كرز احمر', 'كرز اسود', 'كرز طازج'
    ],
    'جريب فروت': [
        'جريب فروت بلدي', 'جريب فروت مستورد', 'جريب فروت',
        'grapefruit', 'جريب فروت وردي', 'جريب فروت احمر',
        'جريب فروت ابيض', 'جريب فروت كبير', 'جريب فروت صغير'
    ],
    'فاكهة التنين': [
        'فاكهة التنين حمراء', 'فاكهة التنين بيضاء', 'فاكهة التنين',
        'dragon fruit', 'دراجون فروت', 'فاكهة التنين الصفراء',
        'فاكهة التنين الاحمر', 'فاكهة التنين الابيض', 'فاكهة التنين الكبيرة'
    ],
    'كمكوات': [
        'كمكوات', 'kumquat', 'كمكوات مستورد',
        'كمكوات كبير', 'كمكوات صغير'
    ],
    'لوز': [
        'لوز', 'almond', 'almonds', 'لوز هندي',
        'لوز اخضر', 'لوز محمص', 'لوز كبير', 'لوز صغير'
    ],
    'جوز': [
        'جوز', 'walnut', 'walnuts', 'عين الجمل',
        'جوز كامل', 'جوز مقشر', 'جوز كبير'
    ],
    'فستق': [
        'فستق', 'pistachio', 'pistachios', 'فستق حلبي',
        'فستق اخضر', 'فستق محمص', 'فستق كبير'
    ],
    'كاجو': [
        'كاجو', 'cashew', 'cashews',
        'كاجو محمص', 'كاجو كامل', 'كاجو كبير'
    ],
    'بلح': [
        'بلح', 'بلح سعودي', 'بلح المدينة',
        'بلح طازج', 'بلح مجفف', 'بلح كبير'
    ],
    'عناب': [
        'عناب', 'عناب سعودي', 'عناب المدينة',
        'عناب مجفف', 'عناب طازج'
    ],
    'كرز': [
        'كرز', 'cherry', 'cherries', 'كرز طازج',
        'كرز مجمد', 'كرز كبير'
    ],
    'رمان': [
        'رمان', 'pomegranate', 'رمان طازج',
        'رمان كبير', 'رمان صغير'
    ],
    
    # ===== الخضار =====
    'طماطم': [
        'طماطم مستديرة', 'طماطم كرزية', 'طماطم محلية', 'طماطم مستوردة',
        'طماطم', 'tomato', 'tomatoes', 'طماطم شيري', 'طماطم كرزي',
        'طماطم سعودية', 'طماطم مصرية', 'طماطم كبيرة',
        'طماطم صغيرة', 'طماطم حمراء', 'طماطم كرز', 'طماطم مستديرة',
        'طماطم عضوية', 'طماطم طازجة'
    ],
    'خيار': [
        'خيار بلدي', 'خيار مستورد', 'خيار صغير', 'خيار كبير',
        'خيار', 'cucumber', 'خيار سعودي', 'خيار مصري', 'خيار خشن',
        'خيار احمر', 'خيار اخضر', 'خيار طازج', 'خيار عضوي'
    ],
    'بطاطس': [
        'بطاطس محلية', 'بطاطس مستوردة', 'بطاطس صغيرة', 'بطاطس كبيرة',
        'بطاطس', 'potato', 'potatoes', 'بطاطس سعودية', 'بطاطس مصرية',
        'بطاطس بيضاء', 'بطاطس حمراء', 'بطاطس طازجة', 'بطاطس عضوية'
    ],
    'بصل': [
        'بصل أحمر', 'بصل أبيض', 'بصل بلدي', 'بصل مستورد',
        'بصل', 'onion', 'onions', 'بصل سعودي', 'بصل مصري', 'بصل كبير',
        'بصل اخضر', 'بصل احمر', 'بصل ابيض', 'بصل طازج'
    ],
    'ثوم': [
        'ثوم بلدي', 'ثوم مستورد', 'ثوم صغير',
        'ثوم', 'garlic', 'ثوم سعودي', 'ثوم مصري', 'ثوم كبير',
        'ثوم كامل', 'ثوم مقشر', 'ثوم طازج'
    ],
    'جزر': [
        'جزر بلدي', 'جزر مستورد', 'جزر صغير',
        'جزر', 'carrot', 'carrots', 'جزر سعودي', 'جزر مصري',
        'جزر برتقالي', 'جزر كبير', 'جزر طازج', 'جزر عضوي'
    ],
    'فلفل': [
        'فلفل أحمر', 'فلفل أخضر', 'فلفل أصفر', 'فلفل حار', 'فلفل بارد',
        'فلفل', 'pepper', 'peppers', 'bell pepper', 'فلفل رومي',
        'فلفل سعودي', 'فلفل مصري', 'فلفل كبير',
        'فلفل احمر', 'فلفل اخضر', 'فلفل اصفر', 'فلفل حلو',
        'فلفل طازج', 'فلفل عضوي'
    ],
    'كوسا': [
        'كوسا بلدي', 'كوسا مستورد', 'كوسا صغير',
        'كوسا', 'zucchini', 'courgette', 'كوسا سعودية', 'كوسا مصرية',
        'كوسا اخضر', 'كوسا كبير', 'كوسا طازجة'
    ],
    'باذنجان': [
        'باذنجان بلدي', 'باذنجان مستورد', 'باذنجان أسود',
        'باذنجان', 'eggplant', 'aubergine', 'باذنجان سعودي', 'باذنجان مصري',
        'باذنجان اسود', 'باذنجان كبير', 'باذنجان طازج'
    ],
    'قرنبيط': [
        'قرنبيط بلدي', 'قرنبيط مستورد', 'قرنبيط',
        'cauliflower', 'قرنبيط سعودي', 'قرنبيط مصري',
        'قرنبيط ابيض', 'قرنبيط كبير', 'قرنبيط طازج'
    ],
    'بروكلي': [
        'بروكلي بلدي', 'بروكلي مستورد', 'بروكلي',
        'broccoli', 'بروكلي سعودي', 'بروكلي مصري',
        'بروكلي اخضر', 'بروكلي كبير', 'بروكلي طازج'
    ],
    'خس': [
        'خس بلدي', 'خس مستورد', 'خس روماني', 'خس آيسبرغ',
        'خس', 'lettuce', 'خس سعودي', 'خس مصري', 'خس كبير',
        'خس اخضر', 'خس روماني', 'خس طازج'
    ],
    'سبانخ': [
        'سبانخ بلدي', 'سبانخ مستورد', 'سبانخ ورقي',
        'سبانخ', 'spinach', 'سبانخ سعودية', 'سبانخ مصرية',
        'سبانخ طازج', 'سبانخ مجمد', 'سبانخ عضوي'
    ],
    'ملفوف': [
        'ملفوف أحمر', 'ملفوف أبيض', 'ملفوف بلدي',
        'ملفوف', 'cabbage', 'ملفوف سعودي', 'ملفوف مصري',
        'ملفوف احمر', 'ملفوف ابيض', 'ملفوف كبير', 'ملفوف طازج'
    ],
    'كرفس': [
        'كرفس بلدي', 'كرفس مستورد',
        'كرفس', 'celery', 'كرفس سعودي', 'كرفس مصري',
        'كرفس اخضر', 'كرفس طازج'
    ],
    'بقدونس': [
        'بقدونس بلدي', 'بقدونس مستورد', 'بقدونس أملس',
        'بقدونس', 'parsley', 'بقدونس سعودي', 'بقدونس مصري',
        'بقدونس ناعم', 'بقدونس خشن', 'بقدونس طازج'
    ],
    'كزبرة': [
        'كزبرة بلدي', 'كزبرة مستوردة',
        'كزبرة', 'coriander', 'cilantro', 'كزبرة سعودية', 'كزبرة مصرية',
        'كزبرة ناعمة', 'كزبرة خضراء', 'كزبرة طازجة'
    ],
    'نعناع': [
        'نعناع بلدي', 'نعناع مستورد',
        'نعناع', 'mint', 'نعناع سعودي', 'نعناع مصري',
        'نعناع اخضر', 'نعناع مجفف', 'نعناع طازج'
    ],
    'فجل': [
        'فجل أحمر', 'فجل أبيض', 'فجل بلدي',
        'فجل', 'radish', 'فجل سعودي', 'فجل مصري',
        'فجل احمر', 'فجل ابيض', 'فجل طازج'
    ],
    'شمندر': [
        'شمندر أحمر', 'شمندر بلدي',
        'شمندر', 'beetroot', 'beets', 'شمندر سعودي', 'شمندر مصري',
        'شمندر احمر', 'شمندر كبير', 'شمندر طازج'
    ],
    'ذرة': [
        'ذرة حلوة', 'ذرة بلدي', 'ذرة مستوردة',
        'ذرة', 'corn', 'sweet corn', 'ذرة سعودية', 'ذرة مصرية',
        'ذرة صفراء', 'ذرة بيضاء', 'ذرة طازجة', 'ذرة مجمدة'
    ],
    'بازلاء': [
        'بازلاء بلدي', 'بازلاء مستوردة', 'بازلاء خضراء',
        'بازلاء', 'peas', 'بازلاء سعودية', 'بازلاء مصرية',
        'بازلاء خضراء', 'بازلاء مجمدة', 'بازلاء طازجة'
    ],
    'فاصولياء': [
        'فاصولياء خضراء', 'فاصولياء بلدي', 'فاصولياء مستوردة',
        'فاصولياء', 'green beans', 'فاصولياء سعودية', 'فاصولياء مصرية',
        'فاصولياء خضراء', 'فاصوليا', 'فاصولياء طازجة'
    ],
    'كراث': [
        'كراث بلدي', 'كراث مستورد',
        'كراث', 'leek', 'كراث سعودي', 'كراث مصري',
        'كراث اخضر', 'كراث كبير', 'كراث طازج'
    ],
    'هليون': [
        'هليون مستورد', 'هليون أخضر',
        'هليون', 'asparagus', 'هليون سعودي',
        'هليون اخضر', 'هليون ابيض', 'هليون طازج'
    ],
    'زهرة': [
        'زهرة', 'cauliflower', 'زهرة سعودية',
        'زهرة بيضاء', 'زهرة كبيرة', 'زهرة طازجة'
    ],
    'بقلة': [
        'بقلة', 'بقلة سعودية', 'بقلة مصرية',
        'بقلة خضراء', 'بقلة طازجة'
    ],
    'جرجير': [
        'جرجير', 'rocket', 'arugula', 'جرجير سعودي',
        'جرجير اخضر', 'جرجير طازج'
    ],
    'فطر': [
        'فطر', 'mushroom', 'mushrooms', 'فطر سعودي',
        'فطر طازج', 'فطر ابيض', 'فطر بني', 'فطر كبير'
    ],
    'بامية': [
        'بامية', 'okra', 'بامية سعودية', 'بامية مصرية',
        'بامية خضراء', 'بامية طازجة', 'بامية مجمدة'
    ],
  
'ملوخية': [
    'ملوخية', 'molokhia', 'ملوخية سعودية', 'ملوخية مصرية',
    'ملوخية طازجة', 'ملوخية مجمدة',
    'ملوخية ة', 'ملوخيه', 'Molokhia leaves', 'Jew\'s mallow',
    'ملوخية خضراء', 'ملوخية ناعمة'
],
}

# جميع أسماء الفواكه والخضار كمفتاح للتصفية
PRODUCE_NAMES = set(PRODUCE_MAPPING.keys())


# ============================================================
# HELPERS
# ============================================================

def safe_text(value: Any) -> str:
    """يرجع نصًا آمنًا، أو نصًا فارغًا للقيم null."""
    if value is None:
        return ""
    return str(value).strip()


def safe_number(value: Any) -> float | None:
    """يرجع رقمًا إن أمكن، أو None."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def get_product_name(record: dict) -> str:
    """
    استخراج اسم المنتج من السجل.
    تميمي يستخدم product_name_en (لأن product_name_ar = None)
    دانوب وبن داود يستخدمون product_name_ar
    GASTAT يستخدم item_name_ar أو item_name_en
    """
    # 1. تميمي: نفحص product_name_en أولاً
    if record.get('product_name_en'):
        return str(record.get('product_name_en')).strip()
    
    # 2. GASTAT: نفحص item_name_ar و item_name_en
    if record.get('item_name_ar'):
        return str(record.get('item_name_ar')).strip()
    if record.get('item_name_en'):
        return str(record.get('item_name_en')).strip()
    
    # 3. باقي المتاجر: نفحص الأسماء العربية
    possible_keys = [
        'product_name_ar',
        'product_name',
        'name',
        'title',
        'product',
        'item_name',
        'description'
    ]
    
    for key in possible_keys:
        value = record.get(key)
        if value and isinstance(value, str) and value.strip():
            return str(value).strip()
    
    return ""


def is_produce(product_name: str) -> bool:
    """
    التحقق إذا كان المنتج فاكهة أو خضار
    """
    if not product_name:
        return False
    
    product_name = str(product_name).strip().lower()
    
    # تحقق من الكلمات المفتاحية بالعربي والإنجليزي
    for produce_name in PRODUCE_NAMES:
        if produce_name in product_name:
            return True
        
        # تحقق من المرادفات الإنجليزية
        for synonym in PRODUCE_MAPPING.get(produce_name, []):
            if synonym.lower() in product_name:
                return True
    
    return False


# ============================================================
# GTIN / BARCODE NORMALIZATION
# ============================================================

def calculate_gtin_check_digit(body: str) -> str:
    """
    يحسب آخر رقم تحقق في GTIN / EAN.
    """
    total = 0
    for index, digit in enumerate(reversed(body)):
        multiplier = 3 if index % 2 == 0 else 1
        total += int(digit) * multiplier
    return str((10 - (total % 10)) % 10)


def is_valid_gtin(barcode: str) -> bool:
    """يتحقق من أن رقم GTIN صحيح رياضيًا."""
    if not barcode.isdigit():
        return False
    if len(barcode) not in {8, 12, 13, 14}:
        return False
    return barcode[-1] == calculate_gtin_check_digit(barcode[:-1])


def normalize_barcode(value: Any) -> str:
    """
    يوحد الباركود للاستخدام كمفتاح ربط.
    """
    barcode = re.sub(r"\D", "", safe_text(value))
    if not barcode:
        return ""
    
    # EAN-13 / GTIN-13 مكتمل وصحيح.
    if len(barcode) == 13 and is_valid_gtin(barcode):
        return barcode
    
    # GTIN-14 كامل وصحيح.
    if len(barcode) == 14 and is_valid_gtin(barcode):
        return barcode
    
    # رقم 12 خانة من Danube أو BinDawood
    if len(barcode) == 12:
        return barcode + calculate_gtin_check_digit(barcode)
    
    # GTIN-8 صحيح
    if len(barcode) == 8 and is_valid_gtin(barcode):
        return "00000" + barcode
    
    return ""


# ============================================================
# LOAD CLEAN FILES
# ============================================================

def load_clean_file(path: Path) -> tuple[dict, list[dict]]:
    """يقرأ ملف clean_latest.json."""
    if not path.exists():
        raise FileNotFoundError(f"لم أجد الملف:\n{path}")
    
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    
    if not isinstance(payload, dict):
        raise ValueError(f"الملف يجب أن يكون JSON object وليس list:\n{path}")
    
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError(f"لم أجد قائمة records داخل الملف:\n{path}")
    
    return payload, records


# ============================================================
# PRODUCE MATCHER CLASS
# ============================================================

class ProduceMatcher:
    """
    مطابقة الفواكه والخضار باستخدام الأسماء
    """
    
    def __init__(self):
        self.mapping = PRODUCE_MAPPING
        self._build_index()
    
    def _build_index(self):
        """بناء فهرس لجميع الأسماء"""
        self.name_index = {}
        for main_name, synonyms in self.mapping.items():
            self.name_index[main_name] = main_name
            for synonym in synonyms:
                self.name_index[synonym.lower()] = main_name
    
    def match(self, gastat_name: str, store_products: list[str]) -> tuple[str | None, float]:
        """
        تطابق منتج من GASTAT مع منتجات المتجر
        Returns: (matched_product_name, confidence_score)
        """
        gastat_name = str(gastat_name).strip().lower()
        
        if not gastat_name:
            return None, 0.0
        
        # تحويل أسماء المتجر إلى lowercase للمقارنة
        store_products_lower = [str(p).strip().lower() for p in store_products if p]
        
        if not store_products_lower:
            return None, 0.0
        
        # 1. تطابق تام
        if gastat_name in store_products_lower:
            idx = store_products_lower.index(gastat_name)
            return store_products[idx], 1.0
        
        # 2. تطابق بالقاموس
        if gastat_name in self.name_index:
            main_name = self.name_index[gastat_name]
            # ابحث عن أي مرادف في المتجر
            for i, product in enumerate(store_products_lower):
                if product in [s.lower() for s in self.mapping.get(main_name, [])]:
                    return store_products[i], 0.9
                if product == main_name.lower():
                    return store_products[i], 0.9
        
        # 3. تطابق بالكلمات المفتاحية
        for i, product in enumerate(store_products_lower):
            if gastat_name in product:
                return store_products[i], 0.7
        
        # 4. تطابق جزئي
        gastat_words = set(gastat_name.split())
        for i, product in enumerate(store_products_lower):
            product_words = set(product.split())
            intersection = gastat_words & product_words
            if len(intersection) >= 1:
                return store_products[i], 0.5
        
        # 5. مطابقة متقدمة: استخراج الكلمات الرئيسية
        for produce_name in PRODUCE_NAMES:
            if produce_name in gastat_name:
                for i, product in enumerate(store_products_lower):
                    if produce_name in product:
                        return store_products[i], 0.6
        
        # 6. مطابقة المرادفات الموسعة
        gastat_parts = gastat_name.split()
        for part in gastat_parts:
            if part in self.name_index:
                main_name = self.name_index[part]
                for i, product in enumerate(store_products_lower):
                    if main_name in product:
                        return store_products[i], 0.5
                    for synonym in self.mapping.get(main_name, []):
                        if synonym.lower() in product:
                            return store_products[i], 0.5
        
        return None, 0.0
    
    def match_store_records(self, gastat_name: str, store_records: list[dict]) -> tuple[dict | None, float]:
        """
        تطابق منتج من GASTAT مع سجلات المتجر
        Returns: (matched_record, confidence_score)
        """
        if not store_records:
            return None, 0.0
        
        # جلب أسماء المنتجات من السجلات
        store_names = [get_product_name(r) for r in store_records]
        
        matched_name, confidence = self.match(gastat_name, store_names)
        
        if matched_name:
            for record in store_records:
                record_name = get_product_name(record)
                if record_name == matched_name:
                    return record, confidence
        
        return None, 0.0


# ============================================================
# BUILD STORE INDEXES
# ============================================================

def get_price(record: dict) -> float | None:
    """استخراج السعر من السجل."""
    price = safe_number(record.get("price"))
    if price is None or price <= 0:
        return None
    return round(price, 2)


def build_barcode_index(
    records: list[dict],
    store_key: str,
) -> tuple[dict[str, dict], dict[str, int]]:
    """
    يبني قاموس الباركود للمنتجات.
    """
    index: dict[str, dict] = {}
    stats = {
        "total_records": len(records),
        "valid_barcode": 0,
        "valid_price": 0,
        "indexed": 0,
        "duplicate_barcode": 0,
    }
    
    for record in records:
        barcode = normalize_barcode(record.get("barcode"))
        if not barcode:
            continue
        stats["valid_barcode"] += 1
        
        price = get_price(record)
        if price is None:
            continue
        stats["valid_price"] += 1
        
        record_copy = dict(record)
        record_copy["_normalized_barcode"] = barcode
        record_copy["_store_key"] = store_key
        record_copy["_price"] = price
        
        existing = index.get(barcode)
        if existing is None:
            index[barcode] = record_copy
            stats["indexed"] += 1
        else:
            stats["duplicate_barcode"] += 1
            if record_copy["_price"] < existing["_price"]:
                index[barcode] = record_copy
    
    return index, stats


# ============================================================
# CREATE UNIFIED RECORDS
# ============================================================

def store_price_payload(record: dict | None) -> dict | None:
    """إنشاء payload السعر لمتجر معين."""
    if record is None:
        return None
    
    current_price = safe_number(record.get("price"))
    regular_price = safe_number(record.get("regular_price"))
    discount_percent = safe_number(record.get("discount"))
    
    if current_price is not None:
        current_price = round(current_price, 2)
    
    if regular_price is None:
        regular_price = current_price
    else:
        regular_price = round(regular_price, 2)
    
    if (
        regular_price is not None
        and current_price is not None
        and regular_price > current_price
    ):
        calculated_discount = round(
            ((regular_price - current_price) / regular_price) * 100,
            2,
        )
    else:
        calculated_discount = 0.0
    
    if discount_percent is None or discount_percent <= 0:
        discount_percent = calculated_discount
    else:
        discount_percent = round(discount_percent, 2)
    
    return {
        "store": safe_text(record.get("store")),
        "current_price": current_price,
        "regular_price": regular_price,
        "discount_percent": discount_percent,
        "on_discount": discount_percent > 0,
        "url": safe_text(record.get("url")),
    }


def make_unified_record_from_barcode(match: dict) -> dict:
    """إنشاء سجل موحد من مطابقة الباركود."""
    danube_prices = store_price_payload(match["danube_record"])
    bindawood_prices = store_price_payload(match["bindawood_record"])
    tamimi_prices = store_price_payload(match["tamimi_record"])
    
    current_prices = [
        danube_prices["current_price"],
        bindawood_prices["current_price"],
        tamimi_prices["current_price"],
    ]
    
    regular_prices = [
        danube_prices["regular_price"],
        bindawood_prices["regular_price"],
        tamimi_prices["regular_price"],
    ]
    
    valid_current_prices = [
        price for price in current_prices
        if price is not None
    ]
    
    valid_regular_prices = [
        price for price in regular_prices
        if price is not None
    ]
    
    price_by_store = {
        "danube": danube_prices["current_price"],
        "bindawood": bindawood_prices["current_price"],
        "tamimi": tamimi_prices["current_price"],
    }
    
    lowest_current_price = min(valid_current_prices)
    highest_current_price = max(valid_current_prices)
    
    return {
        "barcode": match["danube_barcode"],
        "product_name_ar": match["danube_product_name_ar"] or None,
        "product_name_en": match["danube_product_name_en"] or None,
        "category": match["category"],
        "brand": match["brand"],
        "size": None if pd.isna(match["size_value"]) else match["size_value"],
        "unit": match["unit"],
        "quantity": match["quantity"],
        "total_size": (
            None
            if pd.isna(match["total_size_standard"])
            else match["total_size_standard"]
        ),
        "image_url": match["danube_image_url"],
        "prices": {
            "danube": danube_prices,
            "bindawood": bindawood_prices,
            "tamimi": tamimi_prices,
        },
        "average_current_price": round(
            sum(valid_current_prices) / len(valid_current_prices),
            2,
        ),
        "average_regular_price": round(
            sum(valid_regular_prices) / len(valid_regular_prices),
            2,
        ),
        "lowest_current_price": round(lowest_current_price, 2),
        "highest_current_price": round(highest_current_price, 2),
        "price_spread": round(
            highest_current_price - lowest_current_price,
            2,
        ),
        "cheapest_store": min(
            price_by_store,
            key=lambda store: price_by_store[store],
        ),
        "match_method": "barcode",
        "captured_at": match["generated_at_utc"],
        "is_produce": False,
    }


def make_unified_record_from_produce(
    gastat_name: str,
    gastat_price: float | None,
    danube_match: tuple[dict | None, float],
    bindawood_match: tuple[dict | None, float],
    tamimi_match: tuple[dict | None, float],
    generated_at: str,
) -> dict:
    """إنشاء سجل موحد من مطابقة الفواكه والخضار."""
    
    danube_record, danube_conf = danube_match
    bindawood_record, bindawood_conf = bindawood_match
    tamimi_record, tamimi_conf = tamimi_match
    
    danube_prices = store_price_payload(danube_record)
    bindawood_prices = store_price_payload(bindawood_record)
    tamimi_prices = store_price_payload(tamimi_record)
    
    prices = {
        "danube": danube_prices,
        "bindawood": bindawood_prices,
        "tamimi": tamimi_prices,
    }
    
    # حساب المتوسط
    valid_current_prices = [
        p["current_price"] for p in [danube_prices, bindawood_prices, tamimi_prices]
        if p is not None and p["current_price"] is not None
    ]
    
    if valid_current_prices:
        avg_price = round(sum(valid_current_prices) / len(valid_current_prices), 2)
        lowest_price = min(valid_current_prices)
        highest_price = max(valid_current_prices)
        
        price_by_store = {
            "danube": danube_prices["current_price"] if danube_prices else None,
            "bindawood": bindawood_prices["current_price"] if bindawood_prices else None,
            "tamimi": tamimi_prices["current_price"] if tamimi_prices else None,
        }
        
        valid_price_by_store = {k: v for k, v in price_by_store.items() if v is not None}
        cheapest_store = min(valid_price_by_store, key=valid_price_by_store.get) if valid_price_by_store else None
    else:
        avg_price = None
        lowest_price = None
        highest_price = None
        cheapest_store = None
    
    # اختيار أفضل اسم للمنتج
    product_name = gastat_name
    if tamimi_record:
        product_name = get_product_name(tamimi_record) or gastat_name
    elif danube_record:
        product_name = get_product_name(danube_record) or gastat_name
    elif bindawood_record:
        product_name = get_product_name(bindawood_record) or gastat_name
    
    return {
        "barcode": None,
        "product_name_ar": product_name,
        "product_name_en": None,
        "category": "فواكه وخضار",
        "brand": None,
        "size": None,
        "unit": None,
        "quantity": None,
        "total_size": None,
        "image_url": None,
        "prices": prices,
        "average_current_price": avg_price,
        "average_regular_price": avg_price,
        "lowest_current_price": lowest_price,
        "highest_current_price": highest_price,
        "price_spread": round(highest_price - lowest_price, 2) if (highest_price and lowest_price) else None,
        "cheapest_store": cheapest_store,
        "match_method": "produce_name",
        "captured_at": generated_at,
        "is_produce": True,
        "gastat_price": gastat_price,
        "confidence_scores": {
            "danube": danube_conf,
            "bindawood": bindawood_conf,
            "tamimi": tamimi_conf,
        },
        "gastat_name": gastat_name,
    }


# ============================================================
# LOAD GASTAT DATA - بدون دمج المكررات (كل السجلات)
# ============================================================

def load_gastat_data() -> list[dict]:
    """تحميل بيانات GASTAT - نحتفظ بجميع السجلات المكررة."""
    gastat_file = Path("data/processed/open_data/gastat_food_prices_clean.json")
    
    if not gastat_file.exists():
        print(f"⚠️  ملف GASTAT غير موجود: {gastat_file}")
        return []
    
    with gastat_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
    
    if isinstance(data, dict):
        records = data.get("records", [])
    elif isinstance(data, list):
        records = data
    else:
        records = []
    
    # نحتفظ بجميع السجلات بدون دمج (المكررات موجودة)
    produce_records = []
    for record in records:
        product_name = str(record.get("item_name_ar", "") or record.get("item_name_en", "") or "")
        
        if not product_name or not is_produce(product_name):
            continue
        
        # استخراج السعر من Annual average أو من الأشهر
        price = safe_number(record.get("Annual average"))
        if price is None:
            for month in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']:
                price = safe_number(record.get(month))
                if price is not None:
                    break
        
        if price is None:
            continue
        
        # نضيف كل سجل كما هو (مع الاحتفاظ بالتكرارات)
        produce_records.append({
            'name': product_name,
            'price': price,
            'level': record.get('Level', ''),
            'year': record.get('Year', ''),
            'month': record.get('month', ''),
        })
    
    print(f"   GASTAT produce records (with duplicates): {len(produce_records)}")
    return produce_records


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    print("\n" + "=" * 70)
    print("Saudi PriceLens — Unified Products (Barcode + Produce)")
    print("=" * 70)
    
    # ==========================================================
    # 1. تحميل بيانات المتاجر
    # ==========================================================
    
    print("\n📂 Loading clean product files...")
    
    danube_metadata, danube_records = load_clean_file(STORE_FILES["danube"])
    bindawood_metadata, bindawood_records = load_clean_file(STORE_FILES["bindawood"])
    tamimi_metadata, tamimi_records = load_clean_file(STORE_FILES["tamimi"])
    
    print(f"   Danube:    {len(danube_records):,} records")
    print(f"   BinDawood: {len(bindawood_records):,} records")
    print(f"   Tamimi:    {len(tamimi_records):,} records")
    
    # ==========================================================
    # 2. مطابقة الباركود (المنتجات العادية)
    # ==========================================================
    
    print("\n🔗 Building barcode indexes...")
    
    danube_index, danube_stats = build_barcode_index(danube_records, "danube")
    bindawood_index, bindawood_stats = build_barcode_index(bindawood_records, "bindawood")
    tamimi_index, tamimi_stats = build_barcode_index(tamimi_records, "tamimi")
    
    print(f"   Danube indexed:    {len(danube_index):,}")
    print(f"   BinDawood indexed: {len(bindawood_index):,}")
    print(f"   Tamimi indexed:    {len(tamimi_index):,}")
    
    # الباركودات المشتركة
    shared_barcodes = set(danube_index) & set(bindawood_index) & set(tamimi_index)
    print(f"\n✅ Shared barcodes (all 3 stores): {len(shared_barcodes):,}")
    
    # إنشاء السجلات الموحدة من الباركود
    unified_barcode_records = []
    
    for barcode in sorted(shared_barcodes):
        danube_record = danube_index[barcode]
        bindawood_record = bindawood_index[barcode]
        tamimi_record = tamimi_index[barcode]
        
        # التحقق إذا كان المنتج من الفواكه والخضار
        product_name = get_product_name(danube_record)
        is_produce_item = is_produce(product_name)
        
        match = {
            "danube_barcode": barcode,
            "danube_product_name_ar": danube_record.get("product_name_ar"),
            "danube_product_name_en": danube_record.get("product_name_en"),
            "category": danube_record.get("category"),
            "brand": danube_record.get("brand"),
            "size_value": danube_record.get("size"),
            "unit": danube_record.get("unit"),
            "quantity": danube_record.get("quantity"),
            "total_size_standard": danube_record.get("total_size"),
            "danube_image_url": danube_record.get("image_url") or danube_record.get("image"),
            "danube_record": danube_record,
            "bindawood_record": bindawood_record,
            "tamimi_record": tamimi_record,
            "generated_at_utc": generated_at,
            "is_produce": is_produce_item,
        }
        
        unified_record = make_unified_record_from_barcode(match)
        unified_barcode_records.append(unified_record)
    
    print(f"   Unified barcode records: {len(unified_barcode_records):,}")
    
    # ==========================================================
    # 3. مطابقة الفواكه والخضار (مع الاحتفاظ بالمكررات)
    # ==========================================================
    
    print("\n🍎 Matching produce (fruits & vegetables) by name...")
    
    gastat_records = load_gastat_data()
    
    # تصفية الفواكه والخضار من بيانات المتاجر
    danube_produce = [
        r for r in danube_records 
        if is_produce(get_product_name(r))
    ]
    bindawood_produce = [
        r for r in bindawood_records 
        if is_produce(get_product_name(r))
    ]
    tamimi_produce = [
        r for r in tamimi_records 
        if is_produce(get_product_name(r))
    ]
    
    print(f"   Danube produce:    {len(danube_produce)}")
    print(f"   BinDawood produce: {len(bindawood_produce)}")
    print(f"   Tamimi produce:    {len(tamimi_produce)}")
    
    # إنشاء مطابقة الفواكه والخضار
    matcher = ProduceMatcher()
    unified_produce_records = []
    
    matched_count = 0
    high_confidence_count = 0
    
    for gastat_item in gastat_records:
        gastat_name = gastat_item["name"]
        gastat_price = gastat_item["price"]
        
        danube_match = matcher.match_store_records(gastat_name, danube_produce)
        bindawood_match = matcher.match_store_records(gastat_name, bindawood_produce)
        tamimi_match = matcher.match_store_records(gastat_name, tamimi_produce)
        
        # التحقق من وجود أي تطابق
        if danube_match[0] or bindawood_match[0] or tamimi_match[0]:
            matched_count += 1
            if danube_match[1] >= 0.7 or bindawood_match[1] >= 0.7 or tamimi_match[1] >= 0.7:
                high_confidence_count += 1
        
        unified_record = make_unified_record_from_produce(
            gastat_name,
            gastat_price,
            danube_match,
            bindawood_match,
            tamimi_match,
            generated_at,
        )
        # إضافة معلومات التكرار
        unified_record['duplicate_info'] = {
            'level': gastat_item.get('level', ''),
            'year': gastat_item.get('year', ''),
            'month': gastat_item.get('month', ''),
        }
        unified_produce_records.append(unified_record)
    
    # عرض النتائج
    if len(gastat_records) > 0:
        print(f"\n   ✅ Matched produce:    {matched_count}/{len(gastat_records)} ({matched_count/len(gastat_records)*100:.1f}%)")
        print(f"   ✅ High confidence:    {high_confidence_count}/{len(gastat_records)} ({high_confidence_count/len(gastat_records)*100:.1f}%)")
    else:
        print(f"\n   ⚠️  No GASTAT produce records found! Skipping produce matching stats.")
    
    # ==========================================================
    # 4. دمج النتائج وحفظها
    # ==========================================================
    
    print("\n💾 Saving results...")
    
    # دمج جميع السجلات
    all_unified_records = unified_barcode_records + unified_produce_records
    
    # ترتيب الملف
    all_unified_records.sort(
        key=lambda record: (
            not record.get("is_produce", False),
            safe_text(record.get("category", "")).lower(),
            safe_text(record.get("product_name_ar", "")).lower(),
        )
    )
    
    # حفظ الملف الموحد الكامل
    output_payload = {
        "generated_at": generated_at,
        "records_count": len(all_unified_records),
        "records": all_unified_records,
        "stats": {
            "barcode_matches": len(unified_barcode_records),
            "produce_matches": len(unified_produce_records),
            "total": len(all_unified_records),
        }
    }
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    timestamped_output = OUTPUT_DIR / f"unified_products_{timestamp}.json"
    
    serialized_payload = json.dumps(
        output_payload,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    )
    
    for output_file in (timestamped_output, OUTPUT_FILE):
        output_file.write_text(serialized_payload, encoding="utf-8")
    
    # حفظ ملف الفواكه والخضار منفصل (مع المكررات)
    produce_payload = {
        "generated_at": generated_at,
        "records_count": len(unified_produce_records),
        "records": unified_produce_records,
    }
    
    produce_timestamped = OUTPUT_DIR / f"unified_produce_{timestamp}.json"
    produce_serialized = json.dumps(
        produce_payload,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    )
    
    for output_file in (produce_timestamped, PRODUCE_OUTPUT_FILE):
        output_file.write_text(produce_serialized, encoding="utf-8")
    
    # ==========================================================
    # 5. عرض النتائج
    # ==========================================================
    
    print("\n" + "=" * 70)
    print("📊 FINAL SUMMARY")
    print("=" * 70)
    print(f"   Barcode matches (all products):  {len(unified_barcode_records):,}")
    print(f"   Produce name matches:            {len(unified_produce_records):,}")
    print(f"   Total unified records:           {len(all_unified_records):,}")
    print("\n📁 Output files:")
    print(f"   • {timestamped_output}")
    print(f"   • {OUTPUT_FILE}")
    print(f"   • {produce_timestamped}")
    print(f"   • {PRODUCE_OUTPUT_FILE}")
    print("=" * 70)


if __name__ == "__main__":
    main()
