"""
زاحف عقارات لبنان من السوق المفتوح (OpenSooq Lebanon) — الإصدار 2
يستخرج البيانات المرتبة من __NEXT_DATA__ (JSON مدمج بالصفحة) بدل تحليل HTML:
- أسعار نظيفة بالليرة + تحويل رسمي 15000
- اسم البائع + رقم الهاتف (مقنّع) + رابط الإعلان
- المساحة، الغرف، الحي، المدينة، الوصف، تاريخ النشر
- دعم pagination (?page=N) حسب meta.pages
"""
import sys, re, time, sqlite3, json, os
from datetime import datetime
import requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

BASE = "https://lb.opensooq.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
}
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "realestate.db")

# سعر الصرف الرسمي — السوق المفتوح يعرض الليرة بسعر 15000 (تأكدنا: الإعلان يقول USD 315,000 ↔ 4.7B LBP)
LBP_TO_USD = float(os.environ.get("LBP_TO_USD", "15000"))

LISTING_URLS = [
    "/en/property/property-for-sale",
    "/en/property/apartments-for-sale",
    "/en/property/houses-for-sale",
    "/en/property/lands-for-sale",
    "/en/property/commercial-for-sale",
    "/en/property/villas-for-sale",
    "/en/property/residential-for-sale",
    "/en/property/farm-for-sale",
    "/en/property/building-for-sale",
    "/en/property/warehouse-for-sale",
    "/en/property/shop-for-sale",
    "/en/property/office-for-sale",
    "/en/property/factory-for-sale",
]

CITY_URLS = [
    "/en/beirut/property/property-for-sale",
    "/en/tripoli/property/property-for-sale",
    "/en/sidon/property/property-for-sale",
    "/en/zahle/property/property-for-sale",
    "/en/tyre/property/property-for-sale",
    "/en/nabatieh/property/property-for-sale",
    "/en/jbeil/property/property-for-sale",
    "/en/matn/property/property-for-sale",
    "/en/baabda/property/property-for-sale",
    "/en/aley/property/property-for-sale",
    "/en/kesrouane/property/property-for-sale",
    "/en/jounieh/property/property-for-sale",
    "/en/chouf/property/property-for-sale",
    "/en/akkar/property/property-for-sale",
    "/en/baalbek/property/property-for-sale",
    "/en/batroun/property/property-for-sale",
    "/en/bcharre/property/property-for-sale",
    "/en/bint-jbeil/property/property-for-sale",
    "/en/danniyeh/property/property-for-sale",
    "/en/jezzine/property/property-for-sale",
    "/en/koura/property/property-for-sale",
    "/en/marjaayoun/property/property-for-sale",
    "/en/rachaiya/property/property-for-sale",
    "/en/zgharta/property/property-for-sale",
    "/en/hermel/property/property-for-sale",
    "/en/west-bekaa/property/property-for-sale",
    "/en/south-governorate/property/property-for-sale",
]

NEIGHBORHOOD_URLS = [
    "/en/beirut/achrafieh/property/property-for-sale",
    "/en/beirut/ras-beirut/property/property-for-sale",
    "/en/beirut/hamra/property/property-for-sale",
    "/en/beirut/solidere/property/property-for-sale",
    "/en/beirut/verdun/property/property-for-sale",
    "/en/beirut/mar-elias/property/property-for-sale",
    "/en/beirut/tabaris/property/property-for-sale",
    "/en/beirut/saifi/property/property-for-sale",
    "/en/beirut/gemmayze/property/property-for-sale",
    "/en/beirut/mar-mikhael/property/property-for-sale",
    "/en/beirut/sin-el-fil/property/property-for-sale",
    "/en/beirut/badaro/property/property-for-sale",
    "/en/beirut/hazmieh/property/property-for-sale",
    "/en/matn/antelias/property/property-for-sale",
    "/en/matn/jdeideh/property/property-for-sale",
    "/en/matn/bikfaya/property/property-for-sale",
    "/en/matn/dhour-el-choueir/property/property-for-sale",
    "/en/matn/mansourieh/property/property-for-sale",
    "/en/matn/rabieh/property/property-for-sale",
    "/en/matn/bourj-hammoud/property/property-for-sale",
    "/en/matn/naqqache/property/property-for-sale",
    "/en/kesrouane/ghazir/property/property-for-sale",
    "/en/kesrouane/ajaltoun/property/property-for-sale",
    "/en/kesrouane/bzommar/property/property-for-sale",
    "/en/kesrouane/adonis/property/property-for-sale",
    "/en/jbeil/fidar/property/property-for-sale",
    "/en/jbeil/amchit/property/property-for-sale",
    "/en/jbeil/jbeil-city/property/property-for-sale",
    "/en/chouf/beiteddine/property/property-for-sale",
    "/en/chouf/deir-el-qamar/property/property-for-sale",
    "/en/aley/aley-city/property/property-for-sale",
    "/en/aley/ain-w-zain/property/property-for-sale",
    "/en/aley/soufar/property/property-for-sale",
]

# الإيجار: نفس الأقسام بصيغة for-rent (الروابط غير الموجودة تُتخطى تلقائياً)
RENT_LISTING_URLS = [u.replace("-for-sale", "-for-rent") for u in LISTING_URLS]
RENT_CITY_URLS = [u.replace("-for-sale", "-for-rent") for u in CITY_URLS]
RENT_NEIGHBORHOOD_URLS = [u.replace("-for-sale", "-for-rent") for u in NEIGHBORHOOD_URLS]

TYPE_AR = {
    "apartments": "شقة", "houses": "منزل", "villas": "فيلا", "lands": "أرض",
    "commercial": "تجاري", "residential": "سكني", "farm": "مزرعة",
    "building": "مبنى", "warehouse": "مستودع", "shop": "محل", "office": "مكتب",
    "factory": "مصنع",
}

def get_next_data(url):
    """يجلب __NEXT_DATA__ من صفحة (يدعم ?page=N)"""
    try:
        r = requests.get(BASE + url, headers=HEADERS, timeout=25)
        if r.status_code != 200:
            return None, None
        m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', r.text, re.S)
        if not m:
            return None, None
        return json.loads(m.group(1)), r.status_code
    except Exception:
        return None, None

def parse_items(data):
    """يستخرج الإعلانات المرتبة + meta الترحيل"""
    try:
        serp = data['props']['pageProps']['serpApiResponse']
        items = serp['listings']['items']
        meta = serp['listings']['meta']
        return items, meta
    except Exception:
        return [], {}

def extract_fields(it, listing_type="sale"):
    """يحوّل عنصر JSON إلى حقول قاعدة البيانات"""
    price_lbp, price_usd, cur = None, None, None
    pa = (it.get('price_amount') or '').strip()
    m = re.match(r'^([\d,]+\.?\d*)\s*(LBP|USD|\$)$', pa)
    if m:
        val = float(m.group(1).replace(',', ''))
        cur = "USD" if m.group(2) in ("USD", "$") else "LBP"
        price_lbp = val if cur == "LBP" else val * LBP_TO_USD
        price_usd = val if cur == "USD" else val / LBP_TO_USD

    area = rooms = None
    cps = it.get('cps') or []
    for c in cps:
        cm = re.search(r'Area:\s*([\d,]+)\s*m2', c)
        if cm:
            area = float(cm.group(1).replace(',', ''))
            continue
        rm = re.search(r'(\d+)\s*Bedrooms?', c)
        if rm:
            rooms = int(rm.group(1))
    if area is None:
        hm = re.search(r'([\d,]+)\s*m2', it.get('highlights') or '')
        if hm:
            area = float(hm.group(1).replace(',', ''))
    if rooms is None:
        hm = re.search(r'(\d+)\s*Bedrooms?', it.get('highlights') or '')
        if hm:
            rooms = int(hm.group(1))

    posted = None
    # تصفية الإيجارات السنوية — سعرها سنوي ويفسد متوسطات الشهر
    if listing_type == "rent" and any("yearly" in (c or "").lower() for c in cps):
        return None
    pd_ = it.get('inserted_date')
    if pd_:
        posted = pd_
    else:
        pa2 = it.get('posted_at')
        mrel = re.search(r'(\d+)\s+(hour|day|week|month|minute)s?\s+ago', (pa2 or ''), re.I)
        if mrel:
            n = int(mrel.group(1)); u = mrel.group(2).lower()
            hours = {"minute": 1/60, "hour": 1, "day": 24, "week": 168, "month": 720}
            posted = (datetime.now().replace(microsecond=0) -
                      datetime.timedelta(hours=n * hours[u])).strftime("%d-%m-%Y")

    # النوع من cat2_uri أو cat2_label
    cat2 = it.get('cat2_uri') or it.get('cat2_label') or ''
    ptype = None
    for en, ar in TYPE_AR.items():
        if en in cat2.lower():
            ptype = ar
            break
    if ptype is None and it.get('cat1_label'):
        ptype = it['cat1_label']

    return {
        'ad_id': it.get('id'),
        'url': it.get('post_url') or f"/en/search/{it.get('id')}",
        'title': (it.get('title') or '')[:200],
        'price_lbp': price_lbp,
        'price_usd': price_usd,
        'currency': cur,
        'area': area,
        'rooms': rooms,
        'location': it.get('nhood_label'),
        'city': it.get('city_label'),
        'prop_type': ptype,
        'date_posted': posted,
        'seller': it.get('member_display_name'),
        'seller_url': f"/en/members/{it.get('member_user_name')}" if it.get('member_user_name') else None,
        'phone': it.get('phone_number'),
        'has_phone': it.get('has_phone'),
        'reveal_key': it.get('phone_reveal_key'),
        'description': (it.get('masked_description') or '')[:500],
        'highlights': it.get('highlights'),
        'image': (f"https://opensooq-imagesv2.os-cdn.com/previews/700x0/{it['image_uri']}.webp"
                  if it.get('image_uri') else None),
        'image_count': it.get('image_count'),
        'listing_type': listing_type,
        'source': 'opensooq',
    }

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY,
            url TEXT UNIQUE,
            title TEXT,
            price_lbp REAL,
            price_usd REAL,
            area REAL,
            rooms INTEGER,
            location TEXT,
            city TEXT,
            prop_type TEXT,
            date_posted TEXT,
            first_seen TEXT,
            last_seen TEXT,
            seller TEXT,
            seller_url TEXT,
            phone TEXT,
            description TEXT,
            highlights TEXT,
            image TEXT,
            listing_type TEXT DEFAULT 'sale',
            source TEXT DEFAULT 'opensooq'
        )
    """)
    try:
        conn.execute("ALTER TABLE listings ADD COLUMN source TEXT DEFAULT 'opensooq'")
        conn.commit()
    except Exception:
        pass
    conn.commit()
    return conn

def scrape_listing_page(url, conn, listing_type="sale"):
    """يزحف صفحة + كل صفحاتها (?page=N)"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    added = 0
    page = 1
    while True:
        data, _ = get_next_data(url + (f"?page={page}" if page > 1 else ""))
        items, meta = parse_items(data) if data else ([], {})
        if not items:
            break
        for it in items:
            f = extract_fields(it, listing_type)
            if not f or f['price_lbp'] is None:
                continue
            try:
                # منع تكرار العقار نفسه: نفس البائع + السعر + المساحة بإعلان جديد = نفس العقار
                if f['seller'] and f['area']:
                    dup = conn.execute(
                        "SELECT id FROM listings WHERE seller=? AND price_lbp=? AND area=? AND listing_type=? AND url!=? LIMIT 1",
                        (f['seller'], f['price_lbp'], f['area'], listing_type, f['url'])).fetchone()
                    if dup:
                        conn.execute("UPDATE listings SET last_seen=? WHERE id=?", (now, dup[0]))
                        continue
                conn.execute("""
                    INSERT OR IGNORE INTO listings
                    (url, title, price_lbp, price_usd, area, rooms, location, city, prop_type,
                     date_posted, first_seen, last_seen, seller, seller_url, phone, description,
                     highlights, image, listing_type, source)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (f['url'], f['title'], f['price_lbp'], f['price_usd'], f['area'], f['rooms'],
                      f['location'], f['city'], f['prop_type'], f['date_posted'], now, now,
                      f['seller'], f['seller_url'], f['phone'], f['description'], f['highlights'],
                      f['image'], listing_type, f.get('source', 'opensooq')))
                conn.execute("UPDATE listings SET last_seen=?, price_lbp=?, price_usd=?, area=?, rooms=?, title=?, seller=?, phone=?, description=?, image=? WHERE url=?",
                             (now, f['price_lbp'], f['price_usd'], f['area'], f['rooms'], f['title'], f['seller'], f['phone'], f['description'], f['image'], f['url']))
                added += 1
            except Exception:
                pass
        pages = int(meta.get('pages') or 1) if meta else 1
        if page >= pages:
            break
        page += 1
        time.sleep(0.4)
    conn.commit()
    return added

def main():
    conn = init_db()
    total = 0
    for u in LISTING_URLS + CITY_URLS + NEIGHBORHOOD_URLS:
        n = scrape_listing_page(u, conn, "sale")
        if n:
            total += n
            print(f"[بيع] {u}: +{n}")
        time.sleep(0.6)
    for u in RENT_LISTING_URLS + RENT_CITY_URLS + RENT_NEIGHBORHOOD_URLS:
        n = scrape_listing_page(u, conn, "rent")
        if n:
            total += n
            print(f"[إيجار] {u}: +{n}")
        time.sleep(0.6)
    count = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    distinct = conn.execute("SELECT COUNT(DISTINCT url) FROM listings").fetchone()[0]
    by_type = dict(conn.execute("SELECT listing_type, COUNT(*) FROM listings GROUP BY listing_type").fetchall())
    print(f"TOTAL: {total} updates / {distinct} unique / {count} rows / by type: {by_type}")
    conn.close()

if __name__ == "__main__":
    main()
