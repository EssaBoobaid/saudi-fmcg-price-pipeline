import json

data = json.load(open('data/processed/stores/danube/danube_clean_latest.json'))
records = data['records']

target = [
    r for r in records
    if 'موزاريلا طبيعية' in (r.get('product_name_ar') or '')
]

print('عدد المطابقات:', len(target))
for r in target:
    print(r.get('product_name_ar'))
    print('  price:', r.get('price'))
    print('  regular_price:', r.get('regular_price'))
    print('  discount:', r.get('discount'))
    print()

print('=== كل منتجات بريزيدن عليها discount > 0 ===')
president_deals = [
    r for r in records
    if r.get('brand') == 'President' and (r.get('discount') or 0) > 0
]
print('عدد منتجات بريزيدن عليها خصم:', len(president_deals))
for r in president_deals[:10]:
    print(r.get('product_name_ar'), '| price:', r.get('price'), '| regular:', r.get('regular_price'), '| discount:', r.get('discount'))

print()
print('=== إجمالي عدد المنتجات (بكل الملف) اللي عليها discount > 0 ===')
all_deals = [r for r in records if (r.get('discount') or 0) > 0]
print('العدد:', len(all_deals), 'من أصل', len(records))