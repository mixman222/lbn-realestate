"""
إعلانات المستخدمين — تخزين سحابي (Supabase) مع احتياط محلي مؤقت
- add_ad: نشر إعلان (سحابي أولاً، محلي إذا فشل)
- load_ads: جلب الإعلانات (سحابي أولاً)
- الصورة تُخزن base64 داخل القاعدة (ينتقل لـ Storage لاحقاً)
"""
import os, sqlite3, base64
from datetime import datetime
import requests
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_ads.db")
IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_ads_images")

def _secret(name):
    """مفتاح من البيئة أو st.secrets (أساسي أو داخل قسم brevo)"""
    v = os.environ.get(name)
    if v:
        return v
    try:
        import streamlit as st
        if name in st.secrets:
            return st.secrets[name]
        brevo = st.secrets.get("brevo", {})
        if name in brevo:
            return brevo[name]
    except Exception:
        pass
    return ""

def _cloud():
    return _secret("SUPABASE_URL"), _secret("SUPABASE_ANON_KEY")

def _headers():
    return {"apikey": _cloud()[1], "Authorization": "Bearer " + _cloud()[1],
            "Content-Type": "application/json"}

# ---------- محلي (احتياط) ----------
def _init_local():
    os.makedirs(IMG_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prop_type TEXT, governorate TEXT, location TEXT,
            floor TEXT, rooms INTEGER, area REAL,
            price_lbp REAL, furnished TEXT, parking TEXT,
            description TEXT, name TEXT, phone TEXT,
            image_b64 TEXT, created_at TEXT, status TEXT DEFAULT 'new'
        )
    """)
    conn.commit()
    conn.close()

def _add_local(data, image_b64):
    _init_local()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("""
        INSERT INTO user_ads
        (prop_type, governorate, location, floor, rooms, area, price_lbp,
         furnished, parking, description, name, phone, image_b64, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (data.get('prop_type'), data.get('governorate'), data.get('location'),
          data.get('floor'), data.get('rooms'), data.get('area'), data.get('price_lbp'),
          data.get('furnished'), data.get('parking'), data.get('description'),
          data.get('name'), data.get('phone'), image_b64,
          datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    aid = cur.lastrowid
    conn.close()
    return aid

def _load_local():
    _init_local()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM user_ads ORDER BY id DESC", conn)
    conn.close()
    return df

# ---------- سحابي ----------
def _add_cloud(data, image_b64):
    url, key = _cloud()
    if not url or not key:
        return None
    row = {**data, 'image_b64': image_b64}
    r = requests.post(f"{url}/rest/v1/user_ads",
                      headers={**_headers(), "Prefer": "return=representation"},
                      json=row, timeout=20)
    if r.status_code in (200, 201):
        d = r.json()
        return d[0]['id'] if isinstance(d, list) and d else None
    return None

def _load_cloud():
    url, key = _cloud()
    if not url or not key:
        return None
    r = requests.get(f"{url}/rest/v1/user_ads?select=*&order=id.desc",
                     headers=_headers(), timeout=20)
    if r.status_code != 200:
        return None
    df = pd.DataFrame(r.json())
    if df.empty:
        df = pd.DataFrame(columns=['id', 'prop_type', 'governorate', 'location', 'floor',
                                   'rooms', 'area', 'price_lbp', 'furnished', 'parking',
                                   'description', 'name', 'phone', 'image_b64',
                                   'created_at', 'status'])
    return df

# ---------- الواجهة العامة ----------
def add_ad(data, image_bytes=None, image_ext=None):
    """يضيف إعلان — سحابي، ومحلي احتياط. يرجع id"""
    image_b64 = None
    if image_bytes:
        image_b64 = base64.b64encode(image_bytes).decode('ascii')
    cloud_id = _add_cloud(data, image_b64)
    if cloud_id is not None:
        return cloud_id
    return _add_local(data, image_b64)

def load_ads():
    """كل الإعلانات — سحابي أولاً"""
    df = _load_cloud()
    if df is not None and not df.empty:
        return df
    return _load_local()
