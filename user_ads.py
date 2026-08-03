"""
إعلانات المستخدمين — تخزين سحابي (Supabase) مع احتياط محلي مؤقت
- add_ad: نشر إعلان (سحابي أولاً، محلي إذا فشل)
- load_ads: جلب الإعلانات (سحابي أولاً)
- الصورة تُخزن base64 داخل القاعدة (ينتقل لـ Storage لاحقاً)
"""
import os, sqlite3, base64, hashlib, hmac, secrets, time, re
from datetime import datetime
from functools import lru_cache
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

def _write_key():
    """مفتاح الكتابة: service key (سري، من st.secrets فقط) إن وُجد، وإلا anon"""
    return _secret("SUPABASE_SERVICE_KEY") or _secret("SUPABASE_ANON_KEY")

def _headers():
    return {"apikey": _cloud()[1], "Authorization": "Bearer " + _cloud()[1],
            "Content-Type": "application/json"}

def _write_headers():
    return {"apikey": _write_key(), "Authorization": "Bearer " + _write_key(),
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
            image_b64 TEXT, created_at TEXT, status TEXT DEFAULT 'new',
            deal_type TEXT DEFAULT 'للبيع'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL UNIQUE,
            salt TEXT NOT NULL,
            pw_hash TEXT NOT NULL,
            created_at INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS owners (
            ad_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            PRIMARY KEY (ad_id, source)
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
         furnished, parking, description, name, phone, image_b64, created_at, deal_type)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (data.get('prop_type'), data.get('governorate'), data.get('location'),
          data.get('floor'), data.get('rooms'), data.get('area'), data.get('price_lbp'),
          data.get('furnished'), data.get('parking'), data.get('description'),
          data.get('name'), data.get('phone'), image_b64,
          datetime.now().strftime('%Y-%m-%d %H:%M:%S'), data.get('deal_type', 'للبيع')))
    conn.commit()
    aid = cur.lastrowid
    conn.close()
    return aid

def _update_local(ad_id, user_id, fields):
    _init_local()
    conn = sqlite3.connect(DB_PATH)
    sets, vals = [], []
    for k in ('price_lbp', 'description'):
        if k in fields:
            sets.append(f"{k}=?")
            vals.append(fields[k])
    vals += [ad_id, ad_id, user_id]
    cur = conn.execute(
        f"UPDATE user_ads SET {', '.join(sets)} WHERE id=? "
        "AND EXISTS (SELECT 1 FROM owners WHERE ad_id=? AND source='local' AND user_id=?)",
        vals)
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok

def _delete_local(ad_id, user_id):
    _init_local()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "DELETE FROM user_ads WHERE id=? "
        "AND EXISTS (SELECT 1 FROM owners WHERE ad_id=? AND source='local' AND user_id=?)",
        (ad_id, ad_id, user_id))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok

def _link(ad_id, source, user_id):
    _init_local()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR REPLACE INTO owners (ad_id, source, user_id) VALUES (?,?,?)",
                 (str(ad_id), source, user_id))
    conn.commit()
    conn.close()

def _links_of(user_id):
    _init_local()
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT ad_id, source FROM owners WHERE user_id=?", (user_id,)).fetchall()
    conn.close()
    return rows

def _load_local():
    _init_local()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM user_ads ORDER BY id DESC", conn)
    conn.close()
    return df

# ---------- الحسابات ----------
@lru_cache(maxsize=8)
def _cloud_table_exists(table):
    """هل جدول معيّن موجود في Supabase؟ (نتيجة مخزّنة مؤقتاً)"""
    url, key = _cloud()
    if not url or not key:
        return False
    try:
        r = requests.get(f"{url}/rest/v1/{table}?select=id&limit=1",
                         headers=_headers(), timeout=15)
        return r.status_code == 200
    except Exception:
        return False

PBKDF2_ITER = 200_000

def _hash_pw(password, salt):
    """تجزئة PBKDF2-HMAC-SHA256 (مكتبة قياسية، مقاومة لكسر سريع) — تُخزَّن بالصيغة pbkdf2$n$salt$hash"""
    return f"pbkdf2${PBKDF2_ITER}${salt}${hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), PBKDF2_ITER).hex()}"

def _legacy_hash_pw(password, salt):
    """التجزئة القديمة SHA256(salt+password) — تُقبل فقط للترحيل عند الدخول"""
    return hashlib.sha256((salt + password).encode('utf-8')).hexdigest()

def _verify_pw(password, stored, salt=""):
    """تحقق من كلمة السر — يدعم الصيغة الجديدة (pbkdf2) والقديمة (sha256) للترحيل"""
    if stored.startswith('pbkdf2$'):
        try:
            _, n, s, h = stored.split('$', 3)
            calc = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), s.encode('utf-8'), int(n)).hex()
            return hmac.compare_digest(calc, h)
        except Exception:
            return False
    return hmac.compare_digest(_legacy_hash_pw(password, salt or ""), stored)

def _register_local(name, phone, salt, pw_hash):
    _init_local()
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute(
            "INSERT INTO users (name, phone, salt, pw_hash, created_at) VALUES (?,?,?,?,?)",
            (name, phone, salt, pw_hash, int(time.time())))
        conn.commit()
        uid = cur.lastrowid
        conn.close()
        return {'id': uid, 'name': name, 'phone': phone}
    except sqlite3.IntegrityError:
        conn.close()
        return None

def _register_cloud(name, phone, salt, pw_hash):
    url, key = _cloud()
    try:
        r = requests.post(f"{url}/rest/v1/users",
                          headers={**_write_headers(), "Prefer": "return=representation"},
                          json={'name': name, 'phone': phone, 'salt': salt,
                                'pw_hash': pw_hash}, timeout=20)
        if r.status_code in (200, 201):
            d = r.json()
            u = d[0] if isinstance(d, list) and d else {}
            if u:
                return {'id': u.get('id'), 'name': u.get('name'), 'phone': u.get('phone')}
        return 'taken' if r.status_code == 409 else None
    except Exception:
        return None

def register(name, phone, password):
    """إنشاء حساب جديد — يرجع (user, error)"""
    name, phone = (name or '').strip(), (phone or '').strip()
    if not name or not phone or len(phone) < 7:
        return None, 'أدخل اسمك ورقم هاتف صحيح'
    if not password or len(password) < 6:
        return None, 'كلمة السر ٦ أحرف على الأقل'
    salt = secrets.token_hex(8)
    pw_hash = _hash_pw(password, salt)
    if _cloud_table_exists('users'):
        res = _register_cloud(name, phone, salt, pw_hash)
        if res == 'taken':
            return None, 'رقم الهاتف مسجّل مسبقاً — سجّل الدخول'
        if res:
            return res, None
    u = _register_local(name, phone, salt, pw_hash)
    if u:
        return u, None
    return None, 'رقم الهاتف مسجّل مسبقاً — سجّل الدخول'

def _login_local(phone, password):
    _init_local()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT * FROM users WHERE phone=?", (phone,)).fetchone()
    if row and _verify_pw(password, row[4], row[3]):
        if not row[4].startswith('pbkdf2$'):
            # ترحيل: تجزئة قديمة → PBKDF2 على نجاح الدخول
            conn.execute("UPDATE users SET salt=?, pw_hash=? WHERE id=?",
                         (row[3], _hash_pw(password, row[3]), row[0]))
            conn.commit()
        conn.close()
        return {'id': row[0], 'name': row[1], 'phone': row[2]}
    conn.close()
    return None

def _login_cloud(phone, password):
    url, key = _cloud()
    try:
        r = requests.get(f"{url}/rest/v1/users",
                         params={'phone': f"eq.{phone}",
                                 'select': 'id,name,phone,salt,pw_hash'},
                         headers=_write_headers(), timeout=20)
        if r.status_code == 200:
            rows = r.json()
            if rows:
                u = rows[0]
                if _verify_pw(password, u.get('pw_hash', ''), u.get('salt', '')):
                    if not (u.get('pw_hash') or '').startswith('pbkdf2$'):
                        # ترحيل التجزئة القديمة في السحابة عبر PATCH
                        nsalt = secrets.token_hex(8)
                        try:
                            requests.patch(f"{url}/rest/v1/users",
                                           params={'id': f"eq.{u['id']}"},
                                           headers={**_write_headers(), "Prefer": "return=minimal"},
                                           json={'salt': nsalt, 'pw_hash': _hash_pw(password, nsalt)},
                                           timeout=20)
                        except Exception:
                            pass
                    return {'id': u['id'], 'name': u['name'], 'phone': u['phone']}
        return None
    except Exception:
        return None

# حماية الدخول: 5 محاولات فاشلة = قفل 10 دقائق (لكل رقم، في ذاكرة المثيل)
_LOGIN_FAILS = {}
_LOGIN_MAX = 5
_LOGIN_WINDOW = 600

def _login_blocked(phone):
    f = _LOGIN_FAILS.get(phone)
    if f and f[0] >= _LOGIN_MAX and time.time() - f[1] < _LOGIN_WINDOW:
        return True
    if f and f[0] >= _LOGIN_MAX:
        del _LOGIN_FAILS[phone]
    return False

def _login_fail(phone):
    f = _LOGIN_FAILS.get(phone)
    _LOGIN_FAILS[phone] = (1 if not f else f[0] + 1, time.time() if not f else f[1])

def _login_ok(phone):
    _LOGIN_FAILS.pop(phone, None)

def login(phone, password):
    """تسجيل الدخول — يرجع user أو None"""
    phone = (phone or '').strip()
    if not phone or not password:
        return None
    if _login_blocked(phone):
        return None
    if _cloud_table_exists('users'):
        u = _login_cloud(phone, password)
        if u:
            _login_ok(phone)
            return u
    u = _login_local(phone, password)
    if u:
        _login_ok(phone)
        return u
    _login_fail(phone)
    return None

# ---------- سحابي ----------
def _add_cloud(data, image_b64):
    url, key = _cloud()
    if not url or not key:
        return None
    row = {**data, 'image_b64': image_b64}
    r = requests.post(f"{url}/rest/v1/user_ads",
                      headers={**_write_headers(), "Prefer": "return=representation"},
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
                                   'created_at', 'status', 'deal_type'])
    return df

# ---------- الواجهة العامة ----------
def add_ad(data, image_bytes=None, image_ext=None, user_id=None):
    """يضيف إعلان — سحابي، ومحلي احتياط. يرجع id"""
    image_b64 = None
    if image_bytes:
        image_b64 = base64.b64encode(image_bytes).decode('ascii')
    cloud_id = _add_cloud(data, image_b64)
    if cloud_id is not None:
        if user_id is not None:
            _link(cloud_id, 'cloud', user_id)
        return cloud_id
    local_id = _add_local(data, image_b64)
    if local_id is not None and user_id is not None:
        _link(local_id, 'local', user_id)
    return local_id

def list_user_ads(user_id):
    """إعلانات مستخدم معيّن — سحابي ثم محلي (حسب الربط)"""
    links = _links_of(user_id)
    if not links:
        return pd.DataFrame()
    url, key = _cloud()
    cloud_rows, local_rows = [], []
    cloud_ids = [str(a) for a, s in links if s == 'cloud']
    local_ids = [a for a, s in links if s == 'local']
    if cloud_ids and url and key:
        try:
            r = requests.get(f"{url}/rest/v1/user_ads",
                             params={'id': f"in.({','.join(cloud_ids)})"},
                             headers=_headers(), timeout=20)
            if r.status_code == 200:
                cloud_rows = r.json()
        except Exception:
            pass
    if local_ids:
        _init_local()
        conn = sqlite3.connect(DB_PATH)
        q = f"SELECT * FROM user_ads WHERE id IN ({','.join('?' * len(local_ids))})"
        rows = conn.execute(q, local_ids).fetchall()
        cols = [c[1] for c in conn.execute("PRAGMA table_info(user_ads)").fetchall()]
        conn.close()
        local_rows = [dict(zip(cols, r)) for r in rows]
    rows = cloud_rows + local_rows
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df['_src'] = ['cloud'] * len(cloud_rows) + ['local'] * len(local_rows)
    df['id'] = df['id'].astype(str)
    return df.sort_values('id', ascending=False).reset_index(drop=True)

def update_ad(ad_id, user_id, fields):
    """تعديل إعلان مملوك للمستخدم — يرجع نجاح/فشل"""
    ad_id = str(ad_id)
    links = {str(a): s for a, s in _links_of(user_id)}
    url, key = _cloud()
    if ad_id in links:
        if links[ad_id] == 'cloud' and url and key:
            try:
                r = requests.patch(f"{url}/rest/v1/user_ads",
                                   params={'id': f"eq.{ad_id}"},
                                   headers={**_write_headers(), "Prefer": "return=minimal"},
                                   json={k: v for k, v in fields.items()
                                         if k in ('price_lbp', 'description')},
                                   timeout=20)
                if r.status_code in (200, 204):
                    return True
            except Exception:
                pass
            return False
        return _update_local(ad_id, user_id, fields)
    return False

def delete_ad(ad_id, user_id):
    """حذف إعلان مملوك للمستخدم — يرجع نجاح/فشل"""
    ad_id = str(ad_id)
    links = {str(a): s for a, s in _links_of(user_id)}
    url, key = _cloud()
    if ad_id in links:
        if links[ad_id] == 'cloud' and url and key:
            try:
                r = requests.delete(f"{url}/rest/v1/user_ads",
                                    params={'id': f"eq.{ad_id}"},
                                    headers=_write_headers(), timeout=20)
                if r.status_code in (200, 204):
                    return True
            except Exception:
                pass
            return False
        return _delete_local(ad_id, user_id)
    return False

def load_ads():
    """كل الإعلانات — سحابي أولاً"""
    df = _load_cloud()
    if df is not None and not df.empty:
        return df
    return _load_local()
