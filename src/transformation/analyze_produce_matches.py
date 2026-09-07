# src/analysis/analyze_produce_matches.py

import json
from collections import Counter

def analyze_matches():
    with open('data/processed/matches/produce_matches.json', 'r', encoding='utf-8') as f:
        matches = json.load(f)
    
    stats = {
        'total': len(matches),
        'tamimi_matched': 0,
        'danube_matched': 0,
        'bindawood_matched': 0,
        'tamimi_high_confidence': 0,
        'danube_high_confidence': 0,
        'bindawood_high_confidence': 0
    }
    
    for match in matches:
        if match['tamimi'][1] > 0:
            stats['tamimi_matched'] += 1
            if match['tamimi'][1] >= 0.7:
                stats['tamimi_high_confidence'] += 1
        
        if match['danube'][1] > 0:
            stats['danube_matched'] += 1
            if match['danube'][1] >= 0.7:
                stats['danube_high_confidence'] += 1
        
        if match['bindawood'][1] > 0:
            stats['bindawood_matched'] += 1
            if match['bindawood'][1] >= 0.7:
                stats['bindawood_high_confidence'] += 1
    
    print(f"""
    ===== نتائج مطابقة الفواكه والخضار =====
    
    إجمالي المنتجات في GASTAT: {stats['total']}
    
    تميمي:
      - متطابق: {stats['tamimi_matched']} ({stats['tamimi_matched']/stats['total']*100:.1f}%)
      - دقة عالية: {stats['tamimi_high_confidence']} ({stats['tamimi_high_confidence']/stats['total']*100:.1f}%)
    
    دانوب:
      - متطابق: {stats['danube_matched']} ({stats['danube_matched']/stats['total']*100:.1f}%)
      - دقة عالية: {stats['danube_high_confidence']} ({stats['danube_high_confidence']/stats['total']*100:.1f}%)
    
    بن داود:
      - متطابق: {stats['bindawood_matched']} ({stats['bindawood_matched']/stats['total']*100:.1f}%)
      - دقة عالية: {stats['bindawood_high_confidence']} ({stats['bindawood_high_confidence']/stats['total']*100:.1f}%)
    """)
    
    return stats