"""
تطبيع بيانات العقارات اللبنانية:
- توحيد أسماء المدن (عربي/إنجليزي)
- حساب سعر المتر² (أهم مؤشر للتحليل)
- تصفية القيم الشاذة
"""
import sqlite3, os, sys
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "realestate.db")

# توحيد أسماء المدن -> الاسم العربي (المفاتيح كما يرسلها السوق المفتوح)
CITY_AR = {
    "beirut": "بيروت", "tripoli": "طرابلس", "sidon": "صيدا", "zahle": "زحلة",
    "tyre": "صور", "nabatieh": "النبطية", "jbeil": "جبيل", "byblos": "جبيل",
    "matn": "المتن", "baabda": "بعبدا", "aley": "عاليه", "kesrouane": "كسروان",
    "jounieh": "جونية", "chouf": "الشوف", "akkar": "عكار", "aakkar": "عكار",
    "hermel": "الهرمل", "baalbek": "بعلبك", "batroun": "البترون", "bcharre": "بشري",
    "bint jbeil": "بنت جبيل", "bint-jbeil": "بنت جبيل", "danniyeh": "الضنية",
    "jezzine": "جزين", "koura": "الكورة", "marjaayoun": "مرجعيون",
    "rachaiya": "راشيا", "zgharta": "زغرتا", "west bekaa": "البقاع الغربي",
    "south governorate": "الجنوب",
}

# الأحياء -> القضاء (لبنان: المحافظة)
LOCATION_MAP = {
    "achrafieh": "بيروت", "ras beirut": "بيروت", "hamra": "بيروت",
    "solidere": "بيروت", "verdun": "بيروت", "mar elias": "بيروت",
    "tabaris": "بيروت", "saifi": "بيروت", "gemmayze": "بيروت",
    "mar mikhael": "بيروت", "badaro": "بيروت", "sin el fil": "المتن",
    "hazmieh": "بعبدا", "antelias": "المتن", "jdeideh": "المتن",
    "bikfaya": "المتن", "dhour el choueir": "المتن", "mansourieh": "المتن",
    "rabieh": "المتن", "bourj hammoud": "المتن", "naqqache": "المتن",
    "ghazir": "كسروان", "ajaltoun": "كسروان", "bzommar": "كسروان",
    "adonis": "كسروان", "fidar": "جبيل", "amchit": "جبيل",
    "beiteddine": "الشوف", "deir el qamar": "الشوف",
    "soufar": "عاليه", "ain w zain": "عاليه",
    "halba": "عكار", "abou samra": "طرابلس",
    "broummana": "المتن", "bchamoun": "عاليه",
    "kfarhbab": "المتن", "zalka": "المتن",
    "jbeil city": "جبيل", "aley city": "عاليه",
}

def load_listings():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM listings", conn)
    conn.close()
    return df

def normalize(df, lbp_rate=15000.0):
    if df.empty:
        return df
    df = df.copy()
    # إعادة حساب USD بسعر قابل للتعديل
    df['price_usd'] = df['price_lbp'] / lbp_rate
    # سعر المتر²
    df['price_per_m2'] = df['price_usd'] / df['area']
    # توحيد أسماء المدن
    df['city_ar'] = df['city'].astype(str).str.strip().str.lower().map(CITY_AR)
    df['city_ar'] = df['city_ar'].fillna(df['city'].astype(str)).fillna("غير محدد")
    # القضاء من الموقع (الحي)
    df['governorate'] = df['location'].astype(str).str.strip().str.lower().map(LOCATION_MAP)
    df['governorate'] = df['governorate'].fillna(df['city_ar']).fillna("غير محدد")
    # تصفية القيم الشاذة: سعر المتر² خارج [50, 20000] يعتبر خطأ
    mask = (df['price_per_m2'] > 50) & (df['price_per_m2'] < 20000)
    df = df[mask]
    # التاريخ
    df['date_posted'] = pd.to_datetime(df['date_posted'], format='%d-%m-%Y', errors='coerce')
    df['first_seen'] = pd.to_datetime(df['first_seen'], errors='coerce')
    return df

def summary(df):
    """إحصاءات سريعة للوحة"""
    return {
        "total": len(df),
        "cities": df['governorate'].nunique(),
        "avg_price_m2": df['price_per_m2'].median(),
        "avg_price": df['price_usd'].median(),
        "avg_area": df['area'].median(),
    }

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    df = load_listings()
    df = normalize(df)
    print(f"Listings: {len(df)}")
    print(f"Governorates: {df['governorate'].nunique()}")
    print(f"Median $/m2: {df['price_per_m2'].median():,.0f}")
    g = df.groupby('governorate').agg(count=('id', 'count'), avg_m2=('price_per_m2', 'median')).sort_values('count', ascending=False)
    print(g.head(12).to_string())
