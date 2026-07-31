"""
زاحف عقارات لبنان من السوق المفتوح (OpenSooq Lebanon)
يجمع: السعر، المساحة، الغرف، المدينة، المنطقة، تاريخ النشر
ويخزن في SQLite — لبناء تحليل اتجاهات أسعار العقارات اللبنانية.
"""
import sys, re, time, sqlite3, json, os
from datetime import datetime
import requests
from bs4 import BeautifulSoup

BASE = "https://lb.opensooq.com"
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

# صفحات المدن اللبنانية — كل مدينة صفحتها الخاصة (إعلانات مختلفة)
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

# أحياء المدن الكبرى — كل حي له صفحة إعلانات مستقلة
NEIGHBORHOOD_URLS = [
    # بيروت
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
    # المتن
    "/en/matn/antelias/property/property-for-sale",
    "/en/matn/jdeideh/property/property-for-sale",
    "/en/matn/bikfaya/property/property-for-sale",
    "/en/matn/dhour-el-choueir/property/property-for-sale",
    "/en/matn/mansourieh/property/property-for-sale",
    "/en/matn/rabieh/property/property-for-sale",
    "/en/matn/bourj-hammoud/property/property-for-sale",
    "/en/matn/naqqache/property/property-for-sale",
    # كسروان
    "/en/kesrouane/ghazir/property/property-for-sale",
    "/en/kesrouane/ajaltoun/property/property-for-sale",
    "/en/kesrouane/bzommar/property/property-for-sale",
    "/en/kesrouane/adonis/property/property-for-sale",
    # جبيل
    "/en/jbeil/fidar/property/property-for-sale",
    "/en/jbeil/amchit/property/property-for-sale",
    "/en/jbeil/jbeil-city/property/property-for-sale",
    # الشوف
    "/en/chouf/beiteddine/property/property-for-sale",
    "/en/chouf/deir-el-qamar/property/property-for-sale",
    # عاليه
    "/en/aley/aley-city/property/property-for-sale",
    "/en/aley/ain-w-zain/property/property-for-sale",
    "/en/aley/soufar/property/property-for-sale",
]

def main():
    conn = init_db()
    total = 0
    for u in LISTING_URLS + CITY_URLS + NEIGHBORHOOD_URLS:
        n = scrape_listing_page(u, conn)
        if n:
            total += n
            print(f"{u}: +{n}")
        time.sleep(0.7)
    count = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    print(f"TOTAL: {total} new / {count} in DB")
    conn.close()
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
}
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "realestate.db")

# سعر الصرف: السوق المفتوح اللبناني يعرض الأسعار بالليرة بسعر الصرف الرسمي (15000)
# بدل السوق السوداء — تبعاً للإعلانات: شقة فيدار 170م² ببحر جبيل = 315K$ بحدود المعقول
LBP_TO_USD = float(os.environ.get("LBP_TO_USD", "15000"))
# قائمة المدن اللبنانية الشهيرة
KNOWN_CITIES = {
    "beirut", "tripoli", "sidon", "zahle", "tyre", "nabatieh", "jbeil", "byblos",
    "matn", "baabda", "aley", "kesrouane", "jounieh", "chouf", "akkar", "hermel",
    "baalbek", "batroun", "bcharre", "bint jbeil", "danniyeh", "jezzine", "koura",
    "marjaayoun", "rachaiya", "zgharta", "halba", "antelias", "jaz", "amchit",
    "jdeideh", "fidar", "ghazir", "bikfaya", "dhour", "mzaar", "feytroun",
}

def get_soup(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        if r.status_code != 200:
            return None
        return BeautifulSoup(r.text, "lxml")
    except Exception:
        return None

def parse_price(text):
    """يستخرج السعر من نص مثل '4,725,789,825 LBP' -> (قيمة، عملة)"""
    m = re.search(r"([\d,]+\.?\d*)\s*(LBP|USD|\$)", text)
    if not m:
        return None, None
    val = float(m.group(1).replace(",", ""))
    cur = "USD" if m.group(2) in ("USD", "$") else "LBP"
    return val, cur

def parse_area(text):
    m = re.search(r"Area:\s*([\d,]+)\s*m2", text)
    return float(m.group(1).replace(",", "")) if m else None

def parse_rooms(text):
    m = re.search(r"(\d+)\s*(?:Bedrooms|bedroom)", text, re.I)
    return int(m.group(1)) if m else None

def parse_location(text):
    """يستخرج المنطقة والمدينة مثل 'Fidar, Jbeil'"""
    m = re.search(r"\|\s*([A-Za-z\s]+),?\s*([A-Za-z\s]+?)\s*\|\s*(?:Apartments|Villas|Houses|Lands|Commercial|Residential|Farm|Building|Warehouse|Shop|Office|Factory)",
                  text)
    if m:
        loc = m.group(1).strip()
        city = m.group(2).strip() if m.group(2) else ""
        return loc, city
    return None, None

def parse_date(text):
    m = re.search(r"(\d{2}-\d{2}-\d{4})", text)
    if m:
        return m.group(1)
    m2 = re.search(r"(\d+)\s+(hour|hours|day|days|week|month)\s+ago", text, re.I)
    if m2:
        n = int(m2.group(1)); unit = m2.group(2).lower()
        hours = {"hour": 1, "hours": 1, "day": 24, "days": 24, "week": 168, "month": 720}
        return (datetime.now().replace(microsecond=0) -
                __import__("datetime").timedelta(hours=n * hours[unit])).strftime("%d-%m-%Y")
    return None

def parse_type(text):
    m = re.search(r"\|\s*([A-Za-z\s]+?)\s*(?:for\s*Sale)?\s*\|", text)
    if m:
        t = m.group(1).strip().lower()
        mapping = {"apartments": "شقة", "houses": "منزل", "villas": "فيلا",
                   "lands": "أرض", "commercial": "تجاري", "residential": "سكني",
                   "farm": "مزرعة", "building": "مبنى", "warehouse": "مستودع",
                   "shop": "محل", "office": "مكتب", "factory": "مصنع"}
        return mapping.get(t, t)
    return None

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
            last_seen TEXT
        )
    """)
    conn.commit()
    return conn

def scrape_listing_page(url, conn):
    soup = get_soup(BASE + url)
    if not soup:
        return 0
    cards = soup.find_all("a", href=re.compile(r"/en/search/\d+"))
    links = [a["href"] for a in cards]
    links = list(dict.fromkeys(links))  # فك التكرار
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    added = 0
    for link in links:
        card_links = [a for a in cards if a["href"] == link]
        if not card_links:
            continue
        card = card_links[0]
        # نص الإعلان من الرابط نفسه — في المدن كل إعلان رابط مباشر،
        # وفي الصفحات العامة نبحث عن الحاوية kMfbet إذا النص مش كامل
        text = card.get_text(" | ", strip=True)
        if text.count("Area:") == 0:
            anc = card
            for _ in range(8):
                if anc is None: break
                anc = anc.parent
                if anc is None: break
                cls = " ".join(anc.get("class")) if anc.get("class") else ""
                if "kMfbet" in cls and anc.get_text(" | ", strip=True).count("Area:") == 1:
                    text = anc.get_text(" | ", strip=True)
                    break
        price_lbp, cur = parse_price(text)
        if not price_lbp:
            continue
        # رقم الإعلان الفريد (من الرابط) — مفتاح التكرار
        ad_id = re.search(r"/en/search/(\d+)", link)
        ad_key = ad_id.group(1) if ad_id else link
        url_key = "/en/search/" + ad_key
        price_usd = price_lbp / LBP_TO_USD if cur == "LBP" else price_lbp
        area = parse_area(text)
        rooms = parse_rooms(text)
        loc, city = parse_location(text)
        dpost = parse_date(text)
        ptype = parse_type(text)
        title = text.split("|")[0].strip() if "|" in text else text[:100]
        try:
            conn.execute("""
                INSERT OR IGNORE INTO listings
                (url, title, price_lbp, price_usd, area, rooms, location, city, prop_type, date_posted, first_seen, last_seen)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (url_key, title[:200], price_lbp, round(price_usd, 1), area, rooms,
                  loc, city, ptype, dpost, now, now))
            conn.execute("UPDATE listings SET last_seen=? WHERE url=?", (now, url_key))
            added += 1
        except Exception:
            pass
    conn.commit()
    return added

def main():
    conn = init_db()
    total = 0
    for u in LISTING_URLS + CITY_URLS + NEIGHBORHOOD_URLS:
        n = scrape_listing_page(u, conn)
        if n:
            total += n
            print(f"{u}: +{n}")
        time.sleep(0.7)
    count = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    print(f"TOTAL: {total} new / {count} in DB")
    conn.close()

if __name__ == "__main__":
    main()
