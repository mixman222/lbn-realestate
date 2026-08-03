"""
زاحف عقارات لبنان من OLX / dubizzle Lebanon
يستخرج البيانات من __NEXT_DATA__ (نفس أسلوب السوق المفتوح):
- 11 تصنيفاً فرعياً (شقق/فلل، تجاري، أراضٍ، شاليهات، ابنية، غرف...)
- أسعار بالدولار + مساحة + موقع (محافظة/منطقة) + هاتف الوكيل مباشرة
- pagination (?page=N) — أحدث الإعلانات أولاً
"""
import sys, re, time, sqlite3, json, os
from datetime import datetime
import requests

sys.stdout.reconfigure(encoding='utf-8')

BASE = "https://www.olx.com.lb"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "realestate.db")
LBP_TO_USD = float(os.environ.get("LBP_TO_USD", "15000"))
MAX_PAGES_PER_SUBCAT = int(os.environ.get("OLX_MAX_PAGES", "8"))

# التصنيفات الفرعية (id، slug، الغرض) — من كاش قسم Properties
SUBCATS = [
    (95, "apartments-villas-for-sale", "sale"),
    (126, "apartments-villas-for-rent", "rent"),
    (99, "commercial-for-sale", "sale"),
    (124, "commercial-for-rent", "rent"),
    (336, "land-for-sale", "sale"),
    (352, "land-for-rent", "rent"),
    (337, "chalet-for-sale", "sale"),
    (353, "chalet-for-rent", "rent"),
    (338, "buildings-multiple-units-for-sale", "sale"),
    (127, "rooms-for-rent", "rent"),
    (420, "vacation-rentals-and-weekend-getaways", "rent"),
]

TYPE_AR = {
    "apartments": "شقة", "villas": "فيلا", "commercial": "تجاري", "land": "أرض",
    "chalet": "شاليه", "buildings": "مبنى", "rooms": "غرفة", "vacation": "إيجار سياحي",
    "apartment": "شقة", "villa": "فيلا",
}


def get_next_data(url):
    """يجلب __NEXT_DATA__ من صفحة (يدعم ?page=N)"""
    try:
        r = requests.get(BASE + url, headers=HEADERS, timeout=30)
        if r.status_code != 200:
            return None, None
        m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', r.text, re.S)
        if not m:
            return None, None
        return json.loads(m.group(1)), r.status_code
    except Exception:
        return None, None


def parse_items(data):
    """يستخرج الإعلانات (عادية + مميزة + نخبة) من NEXT_DATA"""
    try:
        st = data['props']['pageProps']['initialState']['search']
        hits = []
        for grp in ('ads', 'featuredAds', 'eliteAds'):
            for it in st.get(grp, {}).get('hits', []):
                if it.get('externalID') not in [h.get('externalID') for h in hits]:
                    hits.append(it)
        return hits, st
    except Exception:
        return [], {}


def _g(e, *keys):
    """أول مفتاح موجود"""
    for k in keys:
        if e and e.get(k):
            return e[k]
    return None


def extract_fields(hit, purpose):
    """يحوّل عنصر OLX إلى حقول قاعدة البيانات"""
    extra = hit.get('extraFields') or {}
    price_usd = None
    try:
        price_usd = float(extra.get('price') or hit.get('priceValue') or 0)
    except (TypeError, ValueError):
        price_usd = None
    if not price_usd:
        return None
    period = 'month'
    if extra.get('accommodation_type') is not None:
        period = 'night'
    else:
        rp = str(extra.get('rental_period') or '')
        if rp == '1':
            period = 'night'
        elif rp == '2':
            period = 'week'
        elif rp == '4':
            period = 'year'

    area = None
    try:
        area = float(extra.get('ft') or 0) or None
    except (TypeError, ValueError):
        area = None

    # قنينة الشواذ عند المصدر: سعر/م² فوق 30000$ يشير لخطأ في حقل السعر (مثال: شقة 114م² بـ153.9M$)
    if area and area > 0 and price_usd / area > 30000:
        return None

    rooms = None
    for k in ('bedrooms', 'beds', 'bedroom'):
        try:
            rv = int(float(extra.get(k, 0) or 0))
            if rv:
                rooms = rv
                break
        except (TypeError, ValueError):
            pass

    loc = hit.get('location') or []
    lv = {l['level']: l for l in loc}
    city = lv.get(1, {}).get('name')
    nhood = lv.get(2, {}).get('name') or lv.get(1, {}).get('name')

    agents = hit.get('agents') or []
    agency = hit.get('agency') or {}
    seller = (agency.get('name') or (agents[0].get('name') if agents else None)
              or hit.get('userExternalID'))
    phone = (agents[0].get('phoneNumber') if agents and agents[0].get('phoneNumber')
             else (agency.get('phoneNumber') or agency.get('shortNumber')))

    cat1 = hit.get('category.lvl1') or {}
    slug = (cat1.get('slug') or '').lower()
    ptype = None
    for en, ar in TYPE_AR.items():
        if en in slug:
            ptype = ar
            break
    if ptype is None:
        ptype = (cat1.get('name') or '')[:40]

    ts = hit.get('createdAt') or hit.get('timestamp')
    posted = None
    if ts:
        try:
            posted = datetime.fromtimestamp(int(ts)).strftime("%d-%m-%Y")
        except (TypeError, ValueError, OSError):
            posted = None

    photos = hit.get('photos') or []
    img = None
    for p in photos:
        if p.get('url'):
            img = p['url']
            break
        if p.get('id'):
            # OLX لم يعد يرسل url داخل الصور — الرابط يُبنى من معرّف الصورة
            img = f"https://images-prod.olx-dubizzle.com/thumbnails/{p['id']}-400x300.webp"
            break
    if img is None:
        cover = hit.get('coverPhoto') or {}
        if cover.get('url'):
            img = cover['url']
        elif cover.get('id'):
            img = f"https://images-prod.olx-dubizzle.com/thumbnails/{cover['id']}-400x300.webp"

    return {
        'ad_id': hit.get('externalID'),
        'url': f"{BASE}/item/{hit.get('externalID')}/",
        'title': (hit.get('title') or '')[:200],
        'price_lbp': price_usd * LBP_TO_USD,
        'price_usd': price_usd,
        'currency': 'USD',
        'area': area,
        'rooms': rooms,
        'location': nhood,
        'city': city,
        'prop_type': ptype,
        'date_posted': posted,
        'seller': seller,
        'seller_url': None,
        'phone': phone,
        'has_phone': bool(phone),
        'reveal_key': None,
        'description': (hit.get('description') or '')[:500],
        'highlights': None,
        'image': img,
        'image_count': hit.get('photoCount'),
        'price_period': period,
        'listing_type': 'rent' if purpose == 'rent' else 'sale',
        'source': 'olx',
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
            source TEXT DEFAULT 'opensooq',
            price_period TEXT DEFAULT 'month'
        )
    """)
    try:
        conn.execute("ALTER TABLE listings ADD COLUMN source TEXT DEFAULT 'opensooq'")
        conn.commit()
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE listings ADD COLUMN price_period TEXT DEFAULT 'month'")
        conn.commit()
    except Exception:
        pass
    conn.commit()
    return conn


def scrape_subcategory(subcat_id, slug, purpose, conn, max_pages=MAX_PAGES_PER_SUBCAT):
    """يزحف تصنيفاً فرعياً (أحدث الإعلانات أولاً)"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    added = 0
    for page in range(1, max_pages + 1):
        url = f"/properties/{slug}/" + (f"?page={page}" if page > 1 else "")
        data, _ = get_next_data(url)
        items, st = parse_items(data) if data else ([], {})
        if not items:
            break
        for it in items:
            f = extract_fields(it, purpose)
            if not f:
                continue
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO listings
                    (url, title, price_lbp, price_usd, area, rooms, location, city, prop_type,
                     date_posted, first_seen, last_seen, seller, seller_url, phone, description,
                     highlights, image, listing_type, source, price_period)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (f['url'], f['title'], f['price_lbp'], f['price_usd'], f['area'], f['rooms'],
                      f['location'], f['city'], f['prop_type'], f['date_posted'], now, now,
                      f['seller'], f['seller_url'], f['phone'], f['description'], f['highlights'],
                      f['image'], f['listing_type'], f['source'], f['price_period']))
                conn.execute("UPDATE listings SET last_seen=?, price_lbp=?, price_usd=?, area=?, rooms=?, title=?, seller=?, phone=?, description=?, image=?, price_period=? WHERE url=?",
                             (now, f['price_lbp'], f['price_usd'], f['area'], f['rooms'], f['title'], f['seller'], f['phone'], f['description'], f['image'], f['price_period'], f['url']))
                added += 1
            except Exception:
                pass
        time.sleep(0.5)
    conn.commit()
    return added


def main():
    conn = init_db()
    total = 0
    for sid, slug, purpose in SUBCATS:
        n = scrape_subcategory(sid, slug, purpose, conn)
        if n:
            total += n
            print(f"[OLX] {slug}: +{n}")
    count = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    by_src = dict(conn.execute("SELECT source, COUNT(*) FROM listings GROUP BY source").fetchall())
    by_type = dict(conn.execute("SELECT listing_type, COUNT(*) FROM listings GROUP BY listing_type").fetchall())
    print(f"TOTAL: {total} updates | rows: {count} | by source: {by_src} | by type: {by_type}")
    conn.close()


if __name__ == "__main__":
    main()
