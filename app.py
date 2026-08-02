"""
عقار لبنان — منصة العقارات اللبنانية
مسارات واضحة: شراء / إيجار / استثمار / نشر عقارك
بيانات يومية من السوق المفتوح + إعلانات المستخدمين.
"""
import os, sys, sqlite3, base64
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize import load_listings, normalize

try:
    from streamlit_searchbox import st_searchbox
    HAS_SEARCHBOX = True
except Exception:
    HAS_SEARCHBOX = False

@st.cache_data(ttl=3600)
def known_locations():
    """أسماء الأحياء/المناطق الفريدة من قاعدة البيانات لدعم البحث الفوري في خانة المنطقة"""
    db = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'realestate.db')
    locs, seen = [], set()
    try:
        con = sqlite3.connect(db)
        rows = con.execute(
            "SELECT DISTINCT location FROM listings "
            "WHERE location IS NOT NULL AND location != ''").fetchall()
        con.close()
        for (loc,) in rows:
            loc = (loc or '').strip()
            if (not loc or len(loc) < 2 or any(c in loc for c in '-؟،')):
                continue
            if loc not in seen:
                seen.add(loc)
                locs.append(loc)
    except Exception:
        pass
    return sorted(locs) if locs else ["بيروت", "حمانا", "فردان", "الجميزة", "انطلياس"]

LOC_ALIASES = {
    'الأشرفية': 'Achrafieh', 'حمانا': 'Hammana', 'فردان': 'Verdun',
    'الجميزة': 'Gemmayze', 'البدارو': 'Badaro', 'فرن الشباك': 'Furn El Chebbak',
    'الحازمية': 'Hazmiyeh', 'رأس بيروت': 'Ras Beirut', 'المصيطبة': 'Msaytbeh',
    'الرملة البيضا': 'Ramleh Al-Bayda', 'طريق الجديدة': 'Tariq Al-Jadideh',
    'كفرشيما': 'Kfarshima', 'الشويفات': 'Chouaifet', 'الغبيري': 'Ghobeiry',
    'الشياح': 'Chiyah', 'حارة حريك': 'Haret Hreik', 'عين الرمانة': 'Ain El Remmaneh',
    'كاسليك': 'Kaslik', 'جونية': 'Jounieh', 'جبيل': 'Jbeil',
    'انطلياس': 'Antelias', 'جل الديب': 'Jal El Dib', 'البوشرية': 'Baouchrieh',
    'سن الفيل': 'Sin El Fil', 'فنار': 'Fanar', 'زركة': 'Zalka',
    'بعبدا': 'Baabda', 'برمانا': 'Broummana', 'بكفيا': 'Bikfaya',
    'بيت مري': 'Beit Meri', 'عاليه': 'Aley', 'بحمدون': 'Bhamdoun',
    'بشامون': 'Bchamoun', 'الرابية': 'Rabieh', 'عين سعادة': 'Ain Saadeh',
    'مار إلياس': 'Mar Elias', 'صيدا': 'Saida', 'زحلة': 'Zahle',
    'البترون': 'Batroun', 'المزرعة': 'Mazraa', 'حدت': 'Hadath',
    'خلدة': 'Khaldeh', 'الصوديكو': 'Sodeco', 'اليرزة': 'Yarze',
    'عيناب': 'Ainab', 'المنصورية': 'Mansourieh',
}

def loc_suggestions(q):
    """اقتراحات المنطقة: مطابقة إنجليزية مباشرة أو عبر الأسماء العربية"""
    ql = q.strip().lower()
    out, seen = [], set()

    def add(en, ar=None):
        if en.lower() == 'other' or en.lower() in seen:
            return
        seen.add(en.lower())
        out.append((en, ar))

    for l in known_locations():
        if l.lower().startswith(ql):
            add(l)
    for l in known_locations():
        if ql in l.lower() and not l.lower().startswith(ql):
            add(l)
    for ar, en in LOC_ALIASES.items():
        ar_n = ar.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
        ar_n = ar_n[2:] if ar_n.startswith('ال') else ar_n
        q_n = ql.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
        q_n = q_n[2:] if q_n.startswith('ال') else q_n
        q_root = q_n.lstrip('ا')
        if q_n and (q_n in ar_n or ar_n.startswith(q_n) or
                    (q_root and (q_root in ar_n or ar_n.startswith(q_root)))):
            add(en, ar)
    return out[:8]

st.set_page_config(page_title="عقار لبنان — منصة العقارات", layout="wide", page_icon="🏠")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
    .stApp { direction: rtl; font-family: 'Cairo', 'Segoe UI', Tahoma, sans-serif;
             background: #f1f3f6; }
    .block-container { padding-top: 1rem; max-width: 1180px; }
    h1, h2, h3 { font-family: 'Cairo', 'Segoe UI', Tahoma, sans-serif; }

    /* ---------- الهيدر ---------- */
    .topbar { display: flex; align-items: center; justify-content: space-between;
              border-bottom: 1px solid #e5e7eb; padding-bottom: 14px; margin-bottom: 18px;
              gap: 16px; flex-wrap: wrap; }
    .brand { font-size: 1.5rem; font-weight: 800; color: #0f2027; }
    .brand span { color: #2a9d8f; }
    .topbar .tagline { color: #6b7280; font-size: 0.9rem; margin-top: 4px; }
    .chips { display: flex; gap: 14px; flex-wrap: wrap; }
    .chip { background: #f0fdf9; border: 1px solid #bfe8df; color: #147d64;
            border-radius: 999px; padding: 9px 18px; font-size: 0.95rem; font-weight: 700;
            box-shadow: 0 2px 6px rgba(20,125,100,.08); white-space: nowrap; }

    /* ---------- أزرار الأدوار ---------- */
    div[role="radiogroup"] { gap: 10px; }
    div[role="radiogroup"] label { background: #f9fafb; border: 1.5px solid #e5e7eb;
        border-radius: 14px; padding: 14px 20px; flex: 1; text-align: center;
        font-weight: 700; font-size: 1.02rem; color: #374151; cursor: pointer;
        transition: all .15s ease; }
    div[role="radiogroup"] label:hover { border-color: #2a9d8f; background: #f0fdf9; }
    div[role="radiogroup"] label:has(input:checked) { border-color: #2a9d8f;
        background: linear-gradient(135deg, #1f6f8b 0%, #2a9d8f 100%); color: #fff;
        box-shadow: 0 6px 16px rgba(42,157,143,.25); }
    div[role="radiogroup"] label p { font-weight: 700; }

    /* ---------- البطاقات ---------- */
    .kpi-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 14px;
                padding: 14px 18px; box-shadow: 0 1px 3px rgba(0,0,0,.04); }
    .kpi-card .lbl { color: #6b7280; font-size: 0.8rem; font-weight: 600; }
    .kpi-card .val { color: #0f2027; font-size: 1.45rem; font-weight: 800; margin-top: 2px; }
    .kpi-card .sub { color: #9aa7ad; font-size: 0.75rem; }

    .list-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 14px;
                 padding: 14px; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,.04); }
    .price-big { color: #1f6f8b; font-weight: 800; font-size: 1.1rem; }
    .tag { background: #eef4f6; color: #1f6f8b; border-radius: 8px; padding: 2px 10px;
           font-size: 0.75rem; display: inline-block; margin-left: 4px; font-weight: 600; }
    .tag-sale { background: #eef4f6; color: #1f6f8b; }
    .tag-rent { background: #fef3e2; color: #b7791f; }
    .muted { color: #6b7280; font-size: 0.8rem; }
    .phone-chip { background: #e8f5e9; color: #2e7d32; border-radius: 8px; padding: 2px 10px;
                  font-size: 0.82rem; direction: ltr; display: inline-block; }
    .cta-btn { background: #1f6f8b; color: #fff; border-radius: 10px; padding: 6px 14px;
               text-decoration: none; font-size: 0.82rem; font-weight: 600;
               display: inline-block; }
    .cta-btn:hover { background: #17576f; color: #fff; }

    /* ---------- لوحة الاستثمار ---------- */
    .yield-card { background: linear-gradient(135deg, #0f2027 0%, #2c5364 100%);
                  color: #fff; border-radius: 14px; padding: 16px 18px; }
    .yield-card .yval { font-size: 1.6rem; font-weight: 800; color: #ffd166; }
    .yield-card .ylbl { color: #cfe3ea; font-size: 0.8rem; }

    /* ---------- أسطر صغيرة ---------- */
    .section-title { font-size: 1.15rem; font-weight: 800; color: #0f2027;
                     margin: 22px 0 10px 0; }
    .foot { color: #9aa7ad; font-size: 0.8rem; text-align: center; margin-top: 24px; }
    div[data-testid="stImage"] img { border-radius: 10px; }
    .hero-note { background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 12px;
                 padding: 10px 16px; color: #6b7280; font-size: 0.85rem; }

    /* ---------- خانات كبيرة وواضحة ---------- */
    div[data-testid="stWidgetLabel"] p { font-size: 1.02rem !important; font-weight: 700 !important; color: #1f2937 !important; }
    div[data-testid="stTextInput"] input, div[data-testid="stNumberInput"] input {
        font-size: 1.08rem !important; padding: 14px 16px !important; border-radius: 12px !important;
        border: 2px solid #cbd5e1 !important; background: #fff !important; min-height: 54px !important; }
    div[data-testid="stTextInput"] input:focus, div[data-testid="stNumberInput"] input:focus {
        border-color: #2a9d8f !important; box-shadow: 0 0 0 3px rgba(42,157,143,.15) !important; }
    div[data-testid="stTextArea"] textarea {
        font-size: 1.08rem !important; padding: 14px 16px !important; border-radius: 12px !important;
        border: 2px solid #cbd5e1 !important; min-height: 110px !important; }
    div[data-testid="stTextArea"] textarea:focus { border-color: #2a9d8f !important;
        box-shadow: 0 0 0 3px rgba(42,157,143,.15) !important; }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        min-height: 54px !important; border-radius: 12px !important;
        border: 2px solid #cbd5e1 !important; font-size: 1.05rem !important; }
    div[data-testid="stSelectbox"]:focus-within div[data-baseweb="select"] > div {
        border-color: #2a9d8f !important; box-shadow: 0 0 0 3px rgba(42,157,143,.15) !important; }
    div[data-testid="stRadio"] label { font-size: 1.02rem !important; font-weight: 600 !important; }
    div[data-testid="stRadio"] label:has(input:checked) { background: #f0fdf9 !important;
        border: 1.5px solid #2a9d8f !important; border-radius: 10px !important; }
    div[data-testid="stRadio"] input[type="radio"] { width: 24px !important; height: 24px !important;
        accent-color: #2a9d8f !important; cursor: pointer !important; }
    div[data-testid="stFileUploader"] section { border-radius: 12px !important; }
    div[data-testid="stFileUploader"] button { font-size: 1.02rem !important; }
    div[data-testid="stButton"] button { font-size: 1.05rem !important; font-weight: 700 !important;
        border-radius: 12px !important; padding: 10px 20px !important; }
    .stFormSubmitButton button { font-size: 1.05rem !important; font-weight: 700 !important;
        border-radius: 12px !important; padding: 10px 20px !important; }

    /* ---------- دليل المساعدة تحت الخانة ---------- */
    .field-hint { background: #f0f7ff; border-right: 4px solid #2a9d8f; color: #33576b;
        border-radius: 8px; padding: 8px 12px; margin: 4px 0 14px 0; font-size: 0.92rem;
        line-height: 1.6; }
    .field-hint b { color: #147d64; }
    .step-banner { background: linear-gradient(135deg, #1f6f8b 0%, #2a9d8f 100%); color: #fff;
        border-radius: 12px; padding: 10px 16px; margin: 10px 0; font-size: 1rem; font-weight: 700; }
    .step-banner span { opacity: .85; font-weight: 400; }
</style>
""", unsafe_allow_html=True)

# ---------- البيانات ----------
@st.cache_data(ttl=3600)
def load_data():
    return normalize(load_listings())

df = load_data()

def fmt_usd(v):
    if pd.isna(v) or v == 0:
        return "—"
    if v >= 1e6:
        return f"${v/1e6:.1f}M"
    if v >= 1e3:
        return f"${v/1e3:.0f}K"
    return f"${v:,.0f}"

# ---------- الهيدر ----------
n_total = len(df) if not df.empty else 0
n_gov = df['governorate'].nunique() if not df.empty else 0
st.markdown(f"""
<div class="topbar">
  <div>
    <div class="brand">عقار <span>لبنان</span></div>
    <div class="tagline">الوجهة الأولى لسوق العقارات اللبناني — بيانات يومية، شفافية كاملة، بلا وسطاء.</div>
  </div>
  <div class="chips">
    <span class="chip">📊 {n_total:,} إعلان مُراقَب</span>
    <span class="chip">📍 {n_gov} قضاء</span>
    <span class="chip">🔄 تحديث يومي</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ---------- اختيار الدور ----------
ROLES = {
    "🏠 شراء": "buy",
    "🔑 إيجار": "rent",
    "📈 استثمار": "invest",
    "📤 انشر عقارك": "post",
}
role = st.radio("", list(ROLES.keys()), horizontal=True, label_visibility="collapsed", key="role")

sale = df[df['listing_type'] == 'sale'] if not df.empty else df
rent = df[df['listing_type'] == 'rent'] if not df.empty else df


def market_panel(dd, is_rent):
    """لوحة السوق: بطاقات + اتجاهات + فلترة + إعلانات"""
    suffix = " شهرياً" if is_rent else ""
    c1, c2, c3, c4 = st.columns(4)
    med_m2 = dd['price_per_m2'].median() if not dd.empty else None
    med_px = dd['price_usd'].median() if not dd.empty else None
    med_ar = dd['area'].median() if not dd.empty else None
    cards = [
        ("إعلانات متاحة", f"{len(dd):,}"),
        ("متوسط سعر المتر²", fmt_usd(med_m2) + (f"/م²{suffix}" if med_m2 else "")),
        ("متوسط سعر العقار", fmt_usd(med_px) + (suffix if med_px else "")),
        ("متوسط المساحة", (f"{med_ar:,.0f} م²" if pd.notna(med_ar) else "—")),
    ]
    for col, (lbl, val) in zip([c1, c2, c3, c4], cards):
        with col:
            st.markdown(f'<div class="kpi-card"><div class="lbl">{lbl}</div>'
                        f'<div class="val">{val}</div></div>', unsafe_allow_html=True)

    if dd.empty:
        st.info("لا توجد إعلانات لهذا النوع بعد — الزاحف يمر يومياً، عد لاحقاً.")
        return

    # ---------- اتجاهات ----------
    st.markdown('<div class="section-title">📈 متوسط سعر المتر² حسب القضاء</div>', unsafe_allow_html=True)
    g = (dd.groupby('governorate')
           .agg(متوسط=('price_per_m2', 'median'), عدد=('id', 'count'))
           .reset_index().sort_values('متوسط'))
    fig = go.Figure(go.Bar(
        x=g['متوسط'], y=g['governorate'], orientation='h',
        text=[fmt_usd(v) for v in g['متوسط']], textposition='outside',
        marker=dict(color=g['متوسط'], colorscale='Tealgrn'),
    ))
    fig.update_layout(height=460, margin=dict(l=10, r=70, t=10, b=10),
                      xaxis_title="$/م²" + suffix, yaxis_title="", showlegend=False,
                      font=dict(size=13))
    st.plotly_chart(fig, use_container_width=True)

    # ---------- فلترة وإعلانات ----------
    st.markdown('<div class="section-title">🔍 تصفح الإعلانات</div>', unsafe_allow_html=True)
    f1, f2, f3, f4, f5 = st.columns(5)
    with f1:
        govs = ["الكل"] + sorted(dd['governorate'].dropna().unique().tolist())
        sel_gov = st.selectbox("القضاء", govs, key=f"gov_{is_rent}")
    with f2:
        types = ["الكل"] + sorted(dd['prop_type'].dropna().unique().tolist())
        sel_type = st.selectbox("نوع العقار", types, key=f"type_{is_rent}")
    with f3:
        sel_rooms = st.selectbox("الغرف", ["الكل", "1+", "2+", "3+"], key=f"rooms_{is_rent}")
    with f4:
        max_price = st.number_input("الحد الأقصى ($)", min_value=0, value=0, step=100_000,
                                    key=f"maxp_{is_rent}")
    with f5:
        sort_by = st.selectbox("ترتيب", ["الأحدث", "السعر من الأقل", "السعر من الأعلى",
                                         "أقل سعر للمتر"], key=f"sort_{is_rent}")

    f = dd.copy()
    if sel_gov != "الكل":
        f = f[f['governorate'] == sel_gov]
    if sel_type != "الكل":
        f = f[f['prop_type'] == sel_type]
    if sel_rooms != "الكل":
        need = int(sel_rooms[0])
        f = f[f['rooms'].notna() & (f['rooms'] >= need)]
    if max_price > 0:
        f = f[f['price_usd'] <= max_price]
    if sort_by == "الأحدث":
        f = f.sort_values('date_posted', ascending=False, na_position='last')
    elif sort_by == "السعر من الأقل":
        f = f.sort_values('price_usd')
    elif sort_by == "السعر من الأعلى":
        f = f.sort_values('price_usd', ascending=False)
    else:
        f = f.sort_values('price_per_m2')

    st.caption(f"عرض {min(len(f), 30)} من {len(f):,} إعلان"
               f"{' للإيجار شهرياً' if is_rent else ' للبيع'}")
    for _, r in f.head(30).iterrows():
        loc = (f"{r['location']}، {r['city_ar']}" if pd.notna(r['location'])
               and str(r['location']).strip() else r['city_ar'])
        tags = [r['prop_type'] or '', f"{r['area']:.0f} م²" if pd.notna(r['area']) else '']
        if pd.notna(r['rooms']):
            tags.append(f"{r['rooms']:.0f} غرف")
        tags = [t for t in tags if t]
        tags_html = "".join(f'<span class="tag">{t}</span>' for t in tags)
        desc = (str(r['description'])[:160] + "…") if pd.notna(r['description']) and len(str(r['description'])) > 160 else (str(r['description']) if pd.notna(r['description']) else "")
        seller = r['seller'] if pd.notna(r['seller']) and str(r['seller']).strip() else ""
        phone = r['phone'] if pd.notna(r['phone']) else ""
        img = r['image'] if pd.notna(r['image']) else None
        src = str(r['source']).strip() if pd.notna(r.get('source')) and str(r.get('source')).strip() else 'opensooq'
        src_label = "OLX لبنان" if src == 'olx' else "السوق المفتوح"
        url = str(r['url']) if pd.notna(r['url']) else ""
        if not url.startswith("http"):
            url = "https://lb.opensooq.com" + url

        with st.container(border=True):
            col_img, col_txt, col_price = st.columns([1, 2.4, 1])
            with col_img:
                if img and str(img).startswith("http"):
                    try:
                        st.image(str(img), use_container_width=True)
                    except Exception:
                        pass
            with col_txt:
                st.markdown(f"**{r['title']}**")
                st.markdown(f"📍 {loc} &nbsp;·&nbsp; {tags_html}"
                            f"<span class='tag' style='background:#eef2ff;color:#4338ca;'>{src_label}</span>",
                            unsafe_allow_html=True)
                if desc:
                    st.markdown(f'<div class="muted">{desc}</div>', unsafe_allow_html=True)
                info = []
                if seller:
                    info.append(f"👤 {seller}")
                if phone:
                    info.append(f'<span class="phone-chip">📞 {phone}</span>')
                if pd.notna(r['date_posted']):
                    info.append(f"🗓 {r['date_posted'].strftime('%d/%m/%Y')}")
                st.markdown(" &nbsp; ".join(info), unsafe_allow_html=True)
                st.markdown(f'<a class="cta-btn" href="{url}" target="_blank">عرض الإعلان كاملاً</a>',
                            unsafe_allow_html=True)
            with col_price:
                st.markdown(f'<div class="price-big">{fmt_usd(r["price_usd"])}{"/شهر" if is_rent else ""}</div>',
                            unsafe_allow_html=True)
                if pd.notna(r['area']) and r['area'] > 0:
                    st.markdown(f'<div class="muted">{fmt_usd(r["price_per_m2"])}/م²{"/شهر" if is_rent else ""}</div>',
                                unsafe_allow_html=True)


def invest_panel():
    """لوحة المستثمر: عوائد الإيجار، توزع الأسعار، أفضل الصفقات"""
    if sale.empty:
        st.info("البيانات تصل قريباً — الزاحف يجمع إعلانات البيع يومياً.")
        return

    # ---------- العائد السنوي على الإيجار ----------
    st.markdown('<div class="section-title">📊 تحليل المستثمر</div>', unsafe_allow_html=True)
    if not rent.empty:
        sm = (sale.groupby(['governorate', 'prop_type'])
                .agg(sale_m2=('price_per_m2', 'median')).reset_index())
        rm = (rent.groupby(['governorate', 'prop_type'])
                .agg(rent_m2=('price_per_m2', 'median')).reset_index())
        y = sm.merge(rm, on=['governorate', 'prop_type'])
        if not y.empty:
            # عائد سنوي تقديري: إيجار شهري للمتر² × 12 ÷ سعر بيع المتر²
            y['yield'] = y['rent_m2'] * 12 / y['sale_m2'] * 100
            y = y[y['yield'] > 0].sort_values('yield', ascending=False).head(6)
            if not y.empty:
                top = y.iloc[0]
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown(f"""
                    <div class="yield-card">
                      <div class="ylbl">أعلى عائد إيجاري سنوي</div>
                      <div class="yval">{top['yield']:.1f}%</div>
                      <div class="ylbl">{top['governorate']} — {top['prop_type']}</div>
                    </div>""", unsafe_allow_html=True)
                with c2:
                    st.markdown(f"""
                    <div class="yield-card">
                      <div class="ylbl">متوسط إيجار المتر²</div>
                      <div class="yval">{fmt_usd(rent['price_per_m2'].median())}</div>
                      <div class="ylbl">شهرياً</div>
                    </div>""", unsafe_allow_html=True)
                with c3:
                    st.markdown(f"""
                    <div class="yield-card">
                      <div class="ylbl">متوسط سعر بيع المتر²</div>
                      <div class="yval">{fmt_usd(sale['price_per_m2'].median())}</div>
                      <div class="ylbl">على كامل لبنان</div>
                    </div>""", unsafe_allow_html=True)

                fig = go.Figure(go.Bar(
                    x=y['yield'], y=[f"{a} — {b}" for a, b in zip(y['governorate'], y['prop_type'])],
                    orientation='h',
                    text=[f"{v:.1f}%" for v in y['yield']], textposition='outside',
                    marker=dict(color=y['yield'], colorscale='Tealgrn'),
                ))
                fig.update_layout(height=380, margin=dict(l=10, r=50, t=10, b=10),
                                  xaxis_title="عائد سنوي تقديري %", yaxis_title="", showlegend=False,
                                  font=dict(size=13))
                st.plotly_chart(fig, use_container_width=True)
                st.caption("العائد التقديري = متوسط إيجار المتر² شهرياً × 12 ÷ متوسط سعر بيع المتر² — لكل قضاء ونوع عقار تتوفر فيه بيانات البيع والإيجار.")
            else:
                st.caption("بيانات الإيجار لا تزال قليلة — العائد يظهر تلقائياً عند تراكمها.")
    else:
        st.caption("بيانات الإيجار تصل قريباً — تحليل العوائد يظهر تلقائياً.")

    # ---------- أسعار البيع ----------
    st.markdown('<div class="section-title">💰 توزع أسعار البيع (ألف دولار)</div>', unsafe_allow_html=True)
    hfig = go.Figure(go.Histogram(
        x=sale['price_usd'] / 1000, nbinsx=25,
        marker=dict(color='#2a9d8f'),
    ))
    hfig.update_layout(height=320, margin=dict(l=10, r=30, t=10, b=10),
                       xaxis_title="سعر العقار (ألف $)", yaxis_title="عدد الإعلانات",
                       showlegend=False, font=dict(size=13))
    st.plotly_chart(hfig, use_container_width=True)

    # ---------- أفضل الصفقات ----------
    st.markdown('<div class="section-title">💎 أفضل الصفقات (أدنى سعر للمتر²)</div>', unsafe_allow_html=True)
    cheap = sale.nsmallest(6, 'price_per_m2')
    rows = "".join(
        f"<tr><td>{r['title'][:55]}</td><td>{r['governorate']}</td>"
        f"<td>{fmt_usd(r['price_per_m2'])}/م²</td><td>{fmt_usd(r['price_usd'])}</td></tr>"
        for _, r in cheap.iterrows())
    st.markdown(f"""
    <div style="overflow-x:auto;">
      <table style="width:100%;border-collapse:collapse;font-size:0.85rem;background:#fff;border-radius:12px;">
        <tr style="background:#f3f4f6;color:#374151;">
          <th style="padding:8px 10px;text-align:right;">العقار</th>
          <th style="padding:8px;text-align:right;">القضاء</th>
          <th style="padding:8px;text-align:right;">سعر المتر²</th>
          <th style="padding:8px;text-align:right;">السعر الإجمالي</th>
        </tr>
        {rows}
      </table>
    </div>""", unsafe_allow_html=True)

    # ---------- أغلى الأقضية ----------
    st.markdown('<div class="section-title">🏙️ الأغلى ثمناً (متوسط سعر المتر²)</div>', unsafe_allow_html=True)
    top5 = (sale.groupby('governorate').agg(متوسط=('price_per_m2', 'median'))
                .reset_index().sort_values('متوسط', ascending=False).head(5))
    t5 = "".join(f"<tr><td>{r['governorate']}</td><td>{fmt_usd(r['متوسط'])}</td></tr>"
                 for _, r in top5.iterrows())
    st.markdown(f"""
    <div style="overflow-x:auto;">
      <table style="width:100%;border-collapse:collapse;font-size:0.85rem;background:#fff;border-radius:12px;">
        <tr style="background:#f3f4f6;color:#374151;">
          <th style="padding:8px 10px;text-align:right;">القضاء</th>
          <th style="padding:8px;text-align:right;">متوسط سعر المتر²</th>
        </tr>
        {t5}
      </table>
    </div>""", unsafe_allow_html=True)


def _search_locations(searchterm):
    """مصدر اقتراحات منطقة البحث: أسماء حقيقية من قاعدة البيانات (عربي/إنجليزي)"""
    term = (searchterm or '').strip()
    if len(term) < 2:
        return []
    return [(f"{ar} ({en})".strip() if ar else en, en)
            for en, ar in loc_suggestions(term)]

def post_panel():
    """لوحة البائع/المالك: اختيار نوع العرض + النشر بثلاث خطوات + إعلانات المستخدمين"""
    st.markdown('<div class="section-title">📤 انشر عقارك — يصل مباشرة لآلاف الزوار</div>',
                unsafe_allow_html=True)
    st.caption("ثلاث خطوات بسيطة: أساسيات العقار ← السعر والتفاصيل ← الصور وبيانات التواصل. "
               "إعلانك يظهر فوراً في هذه الصفحة.")
    deal_type = st.radio("نوع العرض", ["للبيع", "للإيجار"], horizontal=True, key="deal_type",
                         help="الإيجار شهري — السعر الذي تدخله هو الإيجار الشهري المطلوب.")

    if "ad_step" not in st.session_state:
        st.session_state.ad_step = 1
        st.session_state.ad_data = {}

    st.progress(st.session_state.ad_step / 3)
    st.markdown(f'<div class="step-banner">الخطوة {st.session_state.ad_step} من 3'
                f'<span> — {["أساسيات العقار", "السعر والتفاصيل", "الصور والتواصل"][st.session_state.ad_step - 1]}</span></div>',
                unsafe_allow_html=True)

    if st.session_state.ad_step == 1:
        st.subheader("1️⃣ أساسيات العقار")
        pt = st.selectbox("نوع العقار", ["شقة", "منزل", "فيلا", "أرض", "تجاري", "مكتب", "محل", "مزرعة"])
        st.markdown('<div class="field-hint">💡 <b>الشقة</b> الأكثر طلباً — حدّد النوع بدقة ليصل إعلانك للمهتمين المناسبين.</div>',
                    unsafe_allow_html=True)
        gov = st.selectbox("القضاء", ["بيروت", "المتن", "بعبدا", "عاليه", "كسروان", "جبيل", "الشوف",
                                      "طرابلس", "صيدا", "صور", "النبطية", "عكار", "البترون", "زحلة", "غير ذلك"])
        st.markdown('<div class="field-hint">💡 القضاء يظهر في <b>مخططات الأسعار</b> بالموقع — اختاره بدقة.</div>',
                    unsafe_allow_html=True)
        if HAS_SEARCHBOX:
            loc = st_searchbox(
                _search_locations,
                label="المنطقة / الحي — اكتب أول حرفين وسنقترح عليك",
                placeholder="Achrafieh، الأشرفية، حمانا…",
                default="", default_use_searchterm=True,
                edit_after_submit="option", rerun_on_update=True,
                key="loc_searchbox",
                style_overrides={'searchbox': {
                    'control': {'minHeight': '54px', 'borderRadius': '12px',
                                'border': '2px solid #cbd5e1', 'backgroundColor': '#fff',
                                'boxShadow': 'none', 'fontSize': '1.05rem'},
                    'input': {'fontSize': '1.08rem', 'color': '#1f2937'},
                    'placeholder': {'fontSize': '1.02rem', 'color': '#9aa7ad'},
                    'menuList': {'fontSize': '1rem', 'color': '#1f2937'},
                }})
            loc_final = (loc or '').strip()
        else:
            loc_final = st.text_input("المنطقة / الحي", key="loc_input").strip()
        st.markdown('<div class="field-hint">💡 <b>اكتب أول حرفين</b> — التكملة تظهر تلقائياً داخل الخانة'
                    ' نفسها (Achrafieh، الأشرفية، Hammana، حمانا…)، اخترها من القائمة'
                    ' أو أكمل الكتابة بنفسك.</div>', unsafe_allow_html=True)
        area = st.number_input("المساحة (م²)", min_value=0, value=0, step=10)
        st.markdown('<div class="field-hint">💡 المساحة الكلية بالمتر² — أساس حساب <b>سعر المتر</b>'
                    ' الذي يقارنه الجميع.</div>', unsafe_allow_html=True)
        if st.button("التالي ←"):
            if not loc_final or area <= 0:
                st.warning("اختر المنطقة وأدخل المساحة.")
            else:
                st.session_state.ad_data.update({'prop_type': pt, 'governorate': gov,
                                                 'location': loc_final, 'area': area,
                                                 'deal_type': deal_type})
                st.session_state.ad_step = 2
                st.rerun()

    elif st.session_state.ad_step == 2:
        st.subheader("2️⃣ السعر والتفاصيل")
        price = st.number_input("السعر المطلوب ($)", min_value=0, value=0, step=10_000)
        st.markdown('<div class="field-hint">💡 <b>سعر واقعي</b> يجذب الاهتمام — المقارنة تبدأ من سعر المتر²:'
                    ' شقق بيروت بين 2,000$ و 4,000$/م² تقريباً.</div>', unsafe_allow_html=True)
        rooms = st.selectbox("عدد الغرف", [0, 1, 2, 3, 4, 5, 6])
        st.markdown('<div class="field-hint">💡 اختر <b>0</b> للأراضي والمكاتب — الغرف تحدد نوع المشتري.</div>',
                    unsafe_allow_html=True)
        floor = st.text_input("الطابق", placeholder="مثال: 3، أرضي، آخر طابق")
        st.markdown('<div class="field-hint">💡 مهم جداً: الأراضي اكتب <b>—</b>، والطوابق العليا أغلى بالإطلالات.</div>',
                    unsafe_allow_html=True)
        furnished = st.radio("التأثيث", ["غير مفروش", "مفروش", "نصف مفروش"], horizontal=True)
        parking = st.radio("موقف سيارة", ["لا", "نعم"], horizontal=True)
        c1b, c2b = st.columns(2)
        with c1b:
            if st.button("→ رجوع"):
                st.session_state.ad_step = 1
                st.rerun()
        with c2b:
            if st.button("التالي ←"):
                if price <= 0:
                    st.warning("أدخل السعر.")
                else:
                    st.session_state.ad_data.update({'price_lbp': price * 15000, 'rooms': rooms,
                                                     'floor': floor.strip() or 'غير محدد',
                                                     'furnished': furnished, 'parking': parking})
                    st.session_state.ad_step = 3
                    st.rerun()

    else:
        st.subheader("3️⃣ صورك ومعلومات التواصل")
        img = st.file_uploader("صورة العقار (اختياري)", type=["jpg", "jpeg", "png", "webp"])
        st.markdown('<div class="field-hint">💡 الصورة <b>أول ما يُرى</b> — ارفع صورة واضحة ومضيئة، والإعلانات'
                    ' المصورة تحصل على تواصل أكثر بمرتين.</div>', unsafe_allow_html=True)
        desc = st.text_area("وصف مختصر (اختياري)", placeholder="مثال: شقة مطلة، إطلالة بحرية، قرب الجامعة...")
        st.markdown('<div class="field-hint">💡 التفاصيل تفرق: <b>الإطلالة، القرب من الجامعات، الخدمات، السن، المصعد…</b></div>',
                    unsafe_allow_html=True)
        name = st.text_input("اسمك")
        st.markdown('<div class="field-hint">💡 الاسم يبني <b>الثقة</b> — المهتمون يتواصلون بثقة أكبر مع صاحب إعلان معرّف.</div>',
                    unsafe_allow_html=True)
        phone = st.text_input("رقم الهاتف (ليراه المهتمون)", placeholder="70 123 456")
        st.markdown('<div class="field-hint">💡 تحقق من الرقم — الهاتف هو <b>أسرع طريق</b> لإغلاق الصفقة.</div>',
                    unsafe_allow_html=True)
        c1b, c2b = st.columns(2)
        with c1b:
            if st.button("→ رجوع"):
                st.session_state.ad_step = 2
                st.rerun()
        with c2b:
            if st.button("🚀 نشر الإعلان"):
                if not name.strip() or not phone.strip():
                    st.warning("أدخل اسمك ورقم هاتفك.")
                else:
                    import user_ads
                    ad = {**st.session_state.ad_data,
                          'description': desc.strip(), 'name': name.strip(), 'phone': phone.strip()}
                    ad_id = user_ads.add_ad(ad,
                                            img.getvalue() if img else None,
                                            img.name.split('.')[-1] if img else None)
                    st.success(f"تم نشر إعلانك (#{ad_id}) — يظهر الآن في قسم إعلانات المستخدمين.")
                    st.session_state.ad_step = 1
                    st.session_state.ad_data = {}
                    st.rerun()

    st.markdown("---")

    # ---------- إعلانات المستخدمين ----------
    try:
        import user_ads
        uads = user_ads.load_ads()
        if not uads.empty:
            if 'deal_type' not in uads.columns:
                uads['deal_type'] = "للبيع"
            uads['deal_type'] = uads['deal_type'].fillna("للبيع")
            want = "للإيجار" if deal_type == "للإيجار" else "للبيع"
            uads = uads[uads['deal_type'].astype(str).str.strip() == want]
        if uads.empty:
            st.info("لا توجد إعلانات مستخدمين بهذا النوع بعد — كن أول من ينشر!")
        else:
            st.markdown(f'<div class="section-title">🟢 إعلانات المستخدمين — {want} ({len(uads)})</div>',
                        unsafe_allow_html=True)
            for _, r in uads.iterrows():
                with st.container(border=True):
                    ci, ct, cp = st.columns([1, 2.4, 1])
                    with ci:
                        img_src = None
                        if pd.notna(r.get('image_b64')) and str(r['image_b64']).strip():
                            try:
                                img_src = base64.b64decode(r['image_b64'])
                            except Exception:
                                pass
                        elif pd.notna(r.get('image_path')) and os.path.exists(str(r['image_path'])):
                            img_src = r['image_path']
                        if img_src is not None:
                            try:
                                st.image(img_src, use_container_width=True)
                            except Exception:
                                pass
                        else:
                            st.markdown('<div style="height:120px;background:#f3f4f6;border-radius:10px;'
                                        'display:flex;align-items:center;justify-content:center;'
                                        'color:#9aa7ad;">لا صورة</div>', unsafe_allow_html=True)
                    with ct:
                        is_rent_ad = str(r['deal_type']).strip() == "للإيجار"
                        tag_cls = "tag tag-rent" if is_rent_ad else "tag tag-sale"
                        price_extra = " شهرياً" if is_rent_ad else ""
                        st.markdown(f"**{r['prop_type']} — {r['location']}، {r['governorate']}** "
                                    f"<span class='{tag_cls}'>🔑 للإيجار</span>" if is_rent_ad
                                    else f"**{r['prop_type']} — {r['location']}، {r['governorate']}** "
                                    f"<span class='{tag_cls}'>🏷️ للبيع</span>", unsafe_allow_html=True)
                        details = [f"{r['area']:.0f} م²" if pd.notna(r['area']) and r['area'] > 0 else ""]
                        if pd.notna(r['rooms']) and r['rooms'] > 0:
                            details.append(f"{r['rooms']:.0f} غرف")
                        details += [r['furnished'] or "", r['floor'] or ""]
                        st.markdown(" · ".join(d for d in details if d))
                        if pd.notna(r['description']) and str(r['description']).strip():
                            st.markdown(f'<div class="muted">{r["description"]}</div>', unsafe_allow_html=True)
                        st.markdown(f"👤 {r['name']} &nbsp;·&nbsp; <span class='phone-chip'>📞 {r['phone']}</span>",
                                    unsafe_allow_html=True)
                    with cp:
                        st.markdown(f'<div class="price-big">{fmt_usd(r["price_lbp"] / 15000)}{price_extra}</div>',
                                    unsafe_allow_html=True)
    except Exception:
        st.info("خدمة الإعلانات غير متاحة حالياً — حاول لاحقاً.")


# ---------- تشغيل اللوحة حسب الدور ----------
if role == "🏠 شراء":
    market_panel(sale, is_rent=False)
elif role == "🔑 إيجار":
    market_panel(rent, is_rent=True)
elif role == "📈 استثمار":
    invest_panel()
else:
    post_panel()

# ---------- التذييل: الاشتراك + تنويه ----------
st.markdown("---")
with st.expander("📧 التقرير الأسبوعي المجاني — متوسطات الأسعار وأبرز العروض كل جمعة"):
    st.caption("بدون رسائل مزعجة — تقرير واحد أسبوعياً، تنسحب وقت ما بدك.")
    with st.form("subscribe_form", clear_on_submit=True):
        sub_email = st.text_input("البريد الإلكتروني", placeholder="you@example.com")
        sub_role = st.selectbox("أنا...", ["مستثمر/مهتم بالشراء", "وسيط عقاري", "باحث/محلل", "غير ذلك"])
        submitted = st.form_submit_button("اشترك مجاناً", use_container_width=True)

    if submitted:
        if "@" in sub_email and "." in sub_email:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            try:
                import brevo
                for k, v in (st.secrets.get("brevo", {}) if hasattr(st, "secrets") else {}).items():
                    os.environ.setdefault(k, v)
                ok, msg = brevo.add_subscriber(sub_email, sub_role)
                if ok:
                    st.success("🎉 تم تسجيل اشتراكك! سيصلك التقرير الأسبوعي.")
                else:
                    DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "subscribers.db")
                    conn = sqlite3.connect(DB)
                    conn.execute("CREATE TABLE IF NOT EXISTS subscribers (email TEXT PRIMARY KEY, role TEXT, created_at TEXT)")
                    conn.execute("INSERT OR IGNORE INTO subscribers (email, role, created_at) VALUES (?, ?, ?)",
                                 (sub_email.strip().lower(), sub_role, pd.Timestamp.now().isoformat()))
                    conn.commit()
                    conn.close()
                    st.success("🎉 تم تسجيل اشتراكك محلياً!")
            except Exception:
                st.info("النظام يخزن الاشتراكات — حاول لاحقاً.")
        else:
            st.error("يرجى إدخال بريد إلكتروني صحيح.")

st.markdown('<div class="foot">⚠️ الأسعار بالدولار الأمريكي (محوّلة بسعر 15000 ل.ل/$) كما يعلنها البائعون على السوق المفتوح — للتوجيه فقط وليست تقييماً مهنياً. '
            'الأرقام الهاتفية مقنّعة؛ الرقم الكامل من صفحة الإعلان الرسمية. '
            '<br>عقار لبنان — منصة مستقلة لمتابعة سوق العقارات اللبناني. 🇱🇧</div>', unsafe_allow_html=True)
