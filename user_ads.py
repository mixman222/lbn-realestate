"""
إعلانات المستخدمين — تخزين محلي مؤقت (ينتقل للسحابة لاحقاً)
"""
import os, sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_ads.db")
IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_ads_images")

def init():
    os.makedirs(IMG_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prop_type TEXT, governorate TEXT, location TEXT,
            floor TEXT, rooms INTEGER, area REAL,
            price_lbp REAL, furnished TEXT, parking TEXT,
            description TEXT, name TEXT, phone TEXT,
            image_path TEXT, created_at TEXT, status TEXT DEFAULT 'new'
        )
    """)
    conn.commit()
    conn.close()

def add_ad(data, image_bytes=None, image_ext=None):
    """يحفظ إعلان مستخدم + الصورة — يرجع id"""
    init()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("""
        INSERT INTO user_ads
        (prop_type, governorate, location, floor, rooms, area, price_lbp,
         furnished, parking, description, name, phone, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (data.get('prop_type'), data.get('governorate'), data.get('location'),
          data.get('floor'), data.get('rooms'), data.get('area'), data.get('price_lbp'),
          data.get('furnished'), data.get('parking'), data.get('description'),
          data.get('name'), data.get('phone'), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    ad_id = cur.lastrowid
    img_path = None
    if image_bytes and image_ext:
        ext = image_ext.lower().replace('jpeg', 'jpg')
        img_path = os.path.join(IMG_DIR, f"{ad_id}.{ext}")
        with open(img_path, 'wb') as f:
            f.write(image_bytes)
        conn.execute("UPDATE user_ads SET image_path=? WHERE id=?", (img_path, ad_id))
        conn.commit()
    conn.close()
    return ad_id

def load_ads():
    import pandas as pd
    init()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM user_ads ORDER BY id DESC", conn)
    conn.close()
    return df
