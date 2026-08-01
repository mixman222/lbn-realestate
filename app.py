"""
عقار لبنان — اتجاهات أسعار السوق
داشبورد: ملخص السوق، اتجاهات الأقضية، بحث وفلترة بالصور والتواصل، اشتراك.
"""
import os, sys, sqlite3, base64, json
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize import load_listings, normalize

st.set_page_config(page_title="عقار لبنان — اتجاهات الأسعار", layout="wide", page_icon="🏠")

st.markdown("""
<style>
    .stApp { direction: rtl; }
    .block-container { padding-top: 1.2rem; max-width: 1200px; }
    h1, h2, h3 { font-family: 'Segoe UI', Tahoma, sans-serif; }
    .kpi-card { background: linear-gradient(135deg, #1f6f8b 0%, #2a9d8f 100%);
                border-radius: 16px; padding: 18px 20px; color: white; margin-bottom: 8px; }
    .kpi-card .lbl { font-size: 0.85rem; opacity: 0.85; }
    .kpi-card .val { font-size: 1.7rem; font-weight: 700; }
    .list-card { background: white; border: 1px solid #e5e7eb; border-radius: 14px;
                 padding: 12px; margin-bottom: 10px; }
    .price-big { color: #1f6f8b; font-weight: 800; font-size: 1.15rem; }
    .tag { background: #eef4f6; color: #1f6f8b; border-radius: 8px; padding: 2px 10px;
           font-size: 0.78rem; display: inline-block; margin-left: 4px; }
    .muted { color: #6b7280; font-size: 0.8rem; }
    .phone-chip { background: #e8f5e9; color: #2e7d32; border-radius: 8px; padding: 2px 10px;
                  font-size: 0.85rem; direction: ltr; display: inline-block; }
    .cta-btn { background: #1f6f8b; color: white; border-radius: 10px; padding: 6px 14px;
               text-decoration: none; font-size: 0.85rem; }
    .hero { background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
            color: white; border-radius: 18px; padding: 26px 30px; margin-bottom: 18px; }
    .hero h1 { color: white; margin: 0 0 6px 0; }
    .hero p { color: #cfe3ea; margin: 0; font-size: 0.95rem; }
    div[data-testid="stImage"] img { border-radius: 10px; }
    .assistant-avatar { width: 74px; height: 74px; border-radius: 50%;
        background: linear-gradient(135deg, #ffd166 0%, #f4a261 100%);
        display: flex; align-items: center; justify-content: center;
        font-size: 2.4rem; box-shadow: 0 4px 12px rgba(0,0,0,.15);
        animation: floaty 3s ease-in-out infinite; }
    @keyframes floaty { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-6px); } }
    .assistant-bubble { background: #fff8e6; border: 1.5px solid #f4a261;
        border-radius: 14px; padding: 12px 14px; color: #5d4037; font-size: .95rem; }
    .assistant-name { color: #b7791f; font-weight: 700; font-size: .82rem; margin-bottom: 3px; }
</style>
""", unsafe_allow_html=True)

# الأسعار تُعرض بالليرة اللبنانية كما يعلنها البائع مباشرة — بدون تحويلات
@st.cache_data(ttl=3600)
def load_data():
    return normalize(load_listings())

df = load_data()

if df.empty:
    st.warning("لا توجد بيانات بعد — شغّل الزاحف أولاً: python scraper_opensooq.py")
    st.stop()

# ---------- ليال 🦸‍♀️: المساعدة الصوتية ثلاثية الأبعاد ----------
STEP_MSG = {
    1: "أهلين! أنا ليال، مساعدتك الشخصية — بضلّك معك خطوة خطوة. أول شي: نوع العقار، القضاء، المنطقة والمساحة. أي خانة عم تلمسها، بوضّحلك شو عم تحط 👇",
    2: "ممتاز! هلق السعر والتفاصيل. خلّي السعر عالعقل — الناس عم بتفلتر عالسعر أول شي. والسعر بليرة لبنانية 💵",
    3: "آخر خطوة! صورة ووصف ورقم التواصل. الصورة أقوى شي للبيع 📸 — ورقمك صح عشان يوصلوك",
}
ASSISTANT_HELP = {
    "pt": "الشقة أكتر طلباً — اختر النوع الأدق لتوصل أسرع للمشترين 🏢",
    "gov": "القضاء هو محافظتك — بيظهر بمخطط الأسعار بالموقع 📍",
    "loc": "أدق منطقة بتوصل أسرع: حمانا، فردان، الجميزة... 🗺️",
    "area": "المساحة الكلية بالمتر² — من أهم خانات البحث 📐",
    "price": "السعر بليرة لبنانية — مثال: 5 مليار بتكتبها 5,000,000,000 💵",
    "rooms": "كم غرفة نوم؟ 🛏️",
    "floor": "الطابق: 3، أرضي، آخر طابق... 🏗️",
    "furnished": "هل العقار مفروش بالأثاث؟ 🛋️",
    "parking": "في موقف سيارة؟ 🚗",
    "image": "الصور بترفع نسبة التواصل كتير — JPG أو PNG 📸",
    "desc": "الوصف بيفرّق: إطلالة، قرب جامعات، خدمات... ✍️",
    "name": "اسمك بيظهر للمشترين — ثقة أكتر 👤",
    "phone": "رقمك بيظهر مباشرة للمشترين — تحقق قبل النشر 📞",
}

def _assistant_say(msg):
    """يحدّث رسالة ليال (تظهر في فقاعتها وتننقال صوتياً)"""
    st.session_state.assistant = msg

def _assistant_field(key):
    st.session_state.assistant = ASSISTANT_HELP.get(key, "")

def _lyal_render():
    """يرسم ليال عائمة على يسار الشاشة ويبثّ رسالتها (استدعاء دائم بمكان ثابت)"""
    enabled = st.session_state.get("lyal_on", True)
    msg = st.session_state.get("assistant", STEP_MSG[1])
    if enabled:
        # معاينة مسبقة للنموذج حتى يظهر ليال فورًا (10MB عبر الشبكة)
        st.iframe(
            '<script>fetch("https://cdn.jsdelivr.net/gh/mixman222/lbn-realestate@master/models/low_poly_girl.glb").catch(function(){})</script>',
            width=1, height=1)
        char_html = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "lyal.html"),
                         encoding="utf-8").read()
        st.iframe(char_html.replace("__MSG__", msg), width=268, height=400)
        payload = json.dumps({"msg": msg}, ensure_ascii=False)
        st.iframe(f"<script>try{{new BroadcastChannel('lyal').postMessage({payload});}}catch(e){{}}</script>",
                  width=1, height=1)
    else:
        st.iframe("<div></div>", width=40, height=40)
        st.iframe("<div></div>", width=40, height=40)
        st.iframe("<div></div>", width=40, height=40)

# ---------- الهيرو ----------
st.markdown("""
<div class="hero">
  <h1>🏠 عقار لبنان — اتجاهات أسعار السوق</h1>
  <p>متابعة يومية لإعلانات السوق المفتوح: متوسطات الأسعار، سعر المتر²، وأحدث العروض —
     بالليرة اللبنانية كما يعلنها البائع. مجاني وبلا تسجيل.</p>
</div>
""", unsafe_allow_html=True)

tc1, tc2 = st.columns([4, 1])
with tc1:
    pass
with tc2:
    st.toggle("🎙️ ليال عم تحكي معك", value=True, key="lyal_on")
st.caption("ليال 🦸‍♀️ مساعدتك الثلاثية الأبعاد — عائمة على يسار الشاشة، بتتكلّم باللبناني وبتوضّحلك كل خانة. تحتاج أصوات عربية مفعّلة بجهازك لسماعها.")

# ---------- ليال: ترسم (تعويم يسار الشاشة) ----------
_lyal_render()

# ---------- البطاقات ----------
def fmt_lbp(v):
    """تنسيق الليرة اللبنانية: مليار/مليون/ألف"""
    if v >= 1e9:
        return f"{v/1e9:.2f} مليار ل.ل"
    if v >= 1e6:
        return f"{v/1e6:.1f} مليون ل.ل"
    if v >= 1e3:
        return f"{v/1e3:.0f} ألف ل.ل"
    return f"{v:,.0f} ل.ل"

c1, c2, c3, c4 = st.columns(4)
cards = [
    ("📊 إعلانات مراقبة", f"{len(df):,}"),
    ("🏘️ أقضية مغطاة", f"{df['governorate'].nunique()}"),
    ("💵 متوسط سعر المتر²", fmt_lbp(df['lbp_per_m2'].median())),
    ("🏠 متوسط سعر العقار", fmt_lbp(df['price_lbp'].median())),
]
for col, (lbl, val) in zip([c1, c2, c3, c4], cards):
    with col:
        st.markdown(f'<div class="kpi-card"><div class="lbl">{lbl}</div>'
                    f'<div class="val">{val}</div></div>', unsafe_allow_html=True)

st.markdown("---")

# ---------- إضافة إعلان (معالج بخطوات) ----------
with st.expander("➕ أضف إعلانك للبيع — بثلاث خطوات بسيطة", expanded=False):
    if "ad_step" not in st.session_state:
        st.session_state.ad_step = 1
        st.session_state.ad_data = {}
        _assistant_say(STEP_MSG[1])

    # شريط تقدم
    st.progress(st.session_state.ad_step / 3)
    st.caption(f"الخطوة {st.session_state.ad_step} من 3")

    if st.session_state.ad_step == 1:
        st.subheader("1️⃣ أساسيات العقار")
        pt = st.selectbox("نوع العقار", ["شقة", "منزل", "فيلا", "أرض", "تجاري", "مكتب", "محل", "مزرعة"],
                          help=ASSISTANT_HELP["pt"], on_change=_assistant_field, args=("pt",))
        gov = st.selectbox("القضاء", ["بيروت", "المتن", "بعبدا", "عاليه", "كسروان", "جبيل", "الشوف",
                                      "طرابلس", "صيدا", "صور", "النبطية", "عكار", "البترون", "زحلة", "غير ذلك"],
                           help=ASSISTANT_HELP["gov"], on_change=_assistant_field, args=("gov",))
        loc = st.text_input("المنطقة / الحي (مثال: حمانا، فردان...)",
                            help=ASSISTANT_HELP["loc"], on_change=_assistant_field, args=("loc",))
        area = st.number_input("المساحة (م²)", min_value=0, value=0, step=10,
                               help=ASSISTANT_HELP["area"], on_change=_assistant_field, args=("area",))
        if st.button("التالي ←"):
            if not loc.strip() or area <= 0:
                st.warning("اكتب المنطقة وأدخل المساحة.")
            else:
                st.session_state.ad_data.update({'prop_type': pt, 'governorate': gov, 'location': loc.strip(), 'area': area})
                _assistant_say(STEP_MSG[2])
                st.session_state.ad_step = 2
                st.rerun()

    elif st.session_state.ad_step == 2:
        st.subheader("2️⃣ السعر والتفاصيل")
        price = st.number_input("السعر المطلوب (ليرة لبنانية)", min_value=0, value=0, step=100_000_000,
                                help=ASSISTANT_HELP["price"], on_change=_assistant_field, args=("price",))
        rooms = st.selectbox("عدد الغرف", [0, 1, 2, 3, 4, 5, 6],
                             help=ASSISTANT_HELP["rooms"], on_change=_assistant_field, args=("rooms",))
        floor = st.text_input("الطابق", placeholder="مثال: 3، أرضي، آخر طابق",
                              help=ASSISTANT_HELP["floor"], on_change=_assistant_field, args=("floor",))
        furnished = st.radio("التأثيث", ["غير مفروش", "مفروش", "نصف مفروش"], horizontal=True,
                             help=ASSISTANT_HELP["furnished"], on_change=_assistant_field, args=("furnished",))
        parking = st.radio("موقف سيارة", ["لا", "نعم"], horizontal=True,
                           help=ASSISTANT_HELP["parking"], on_change=_assistant_field, args=("parking",))
        c1b, c2b = st.columns(2)
        with c1b:
            if st.button("→ رجوع"):
                _assistant_say(STEP_MSG[1])
                st.session_state.ad_step = 1
                st.rerun()
        with c2b:
            if st.button("التالي ←"):
                if price <= 0:
                    st.warning("أدخل السعر.")
                else:
                    st.session_state.ad_data.update({'price_lbp': price, 'rooms': rooms,
                                                     'floor': floor.strip() or 'غير محدد',
                                                     'furnished': furnished, 'parking': parking})
                    _assistant_say(STEP_MSG[3])
                    st.session_state.ad_step = 3
                    st.rerun()

    else:
        st.subheader("3️⃣ صورك ومعلومات التواصل")
        img = st.file_uploader("صورة العقار (اختياري)", type=["jpg", "jpeg", "png", "webp"],
                               help=ASSISTANT_HELP["image"], on_change=_assistant_field, args=("image",))
        desc = st.text_area("وصف مختصر (اختياري)", placeholder="مثال: شقة مطلة، إطلالة بحرية، قرب الجامعة...",
                            help=ASSISTANT_HELP["desc"], on_change=_assistant_field, args=("desc",))
        name = st.text_input("اسمك", help=ASSISTANT_HELP["name"], on_change=_assistant_field, args=("name",))
        phone = st.text_input("رقم الهاتف (ليراه المشترون)", placeholder="70 123 456",
                              help=ASSISTANT_HELP["phone"], on_change=_assistant_field, args=("phone",))
        c1b, c2b = st.columns(2)
        with c1b:
            if st.button("→ رجوع"):
                _assistant_say(STEP_MSG[2])
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
                    st.success(f"🎉 تم نشر إعلانك (#{ad_id})! يظهر الآن أسفل الصفحة في قسم إعلانات المستخدمين.")
                    _assistant_say("مبروك! 🎉 إعلانك اننشر — شوفو هلق أسفل الصفحة في قسم «إعلانات المستخدمين». أول إعلان ليك! 👏")
                    st.session_state.ad_step = 1
                    st.session_state.ad_data = {}

st.markdown("---")

# ---------- اتجاهات السعر ----------
st.subheader("📈 متوسط سعر المتر² حسب القضاء (ل.ل)")
g = (df.groupby('governorate')
       .agg(متوسط=('lbp_per_m2', 'median'), عدد=('id', 'count'))
       .reset_index().sort_values('متوسط'))
fig = go.Figure(go.Bar(
    x=g['متوسط'], y=g['governorate'], orientation='h',
    text=[fmt_lbp(v) for v in g['متوسط']], textposition='outside',
    marker=dict(color=g['متوسط'], colorscale='Tealgrn'),
))
fig.update_layout(height=480, margin=dict(l=10, r=60, t=10, b=10),
                  xaxis_title="ليرة/م²", yaxis_title="", showlegend=False,
                  font=dict(size=13))
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ---------- إعلانات المستخدمين ----------
try:
    import user_ads
    uads = user_ads.load_ads()
    if not uads.empty:
        st.subheader(f"🟢 إعلانات المستخدمين ({len(uads)})")
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
                        st.markdown('<div style="height:120px;background:#eef4f6;border-radius:10px;'
                                    'display:flex;align-items:center;justify-content:center;'
                                    'color:#9aa7ad;">لا صورة</div>', unsafe_allow_html=True)
                with ct:
                    st.markdown(f"**{r['prop_type']} — {r['location']}، {r['governorate']}**")
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
                    st.markdown(f'<div class="price-big">{fmt_lbp(r["price_lbp"])}</div>', unsafe_allow_html=True)
        st.markdown("---")
except Exception:
    pass

# ---------- الإعلانات ----------
st.subheader("🔍 الإعلانات")
f1, f2, f3, f4, f5 = st.columns(5)
with f1:
    govs = ["الكل"] + sorted(df['governorate'].dropna().unique().tolist())
    sel_gov = st.selectbox("القضاء", govs)
with f2:
    types = ["الكل"] + sorted(df['prop_type'].dropna().unique().tolist())
    sel_type = st.selectbox("نوع العقار", types)
with f3:
    rooms_opts = ["الكل", "1+", "2+", "3+"]
    sel_rooms = st.selectbox("الغرف", rooms_opts)
with f4:
    max_price = st.number_input("الحد الأقصى (ل.ل)", min_value=0, value=0, step=100_000_000)
with f5:
    sort_by = st.selectbox("ترتيب", ["الأحدث", "السعر من الأقل", "السعر من الأعلى", "أقل سعر للمتر"])

f = df.copy()
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
    f = f.sort_values('price_lbp')
elif sort_by == "السعر من الأعلى":
    f = f.sort_values('price_lbp', ascending=False)
else:
    f = f.sort_values('lbp_per_m2')

st.caption(f"عرض {min(len(f), 30)} من {len(f):,} إعلان")

for _, r in f.head(30).iterrows():
    loc = f"{r['location']}، {r['city_ar']}" if pd.notna(r['location']) and str(r['location']).strip() else r['city_ar']
    tags = [r['prop_type'] or '', f"{r['area']:.0f} م²" if pd.notna(r['area']) else '']
    if pd.notna(r['rooms']):
        tags.append(f"{r['rooms']:.0f} غرف")
    tags = [t for t in tags if t]
    tags_html = "".join(f'<span class="tag">{t}</span>' for t in tags)
    desc = (str(r['description'])[:160] + "…") if pd.notna(r['description']) and len(str(r['description'])) > 160 else (str(r['description']) if pd.notna(r['description']) else "")
    seller = r['seller'] if pd.notna(r['seller']) and str(r['seller']).strip() else ""
    phone = r['phone'] if pd.notna(r['phone']) else ""
    img = r['image'] if pd.notna(r['image']) else None

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
            st.markdown(f"📍 {loc} &nbsp;·&nbsp; {tags_html}", unsafe_allow_html=True)
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
            st.markdown(f'<a class="cta-btn" href="https://lb.opensooq.com{r["url"]}" target="_blank">عرض الإعلان كاملاً — كشف رقم الهاتف</a>',
                        unsafe_allow_html=True)
        with col_price:
            st.markdown(f'<div class="price-big">{fmt_lbp(r["price_lbp"])}</div>', unsafe_allow_html=True)
            if pd.notna(r['area']) and r['area'] > 0:
                st.markdown(f'<div class="muted">{fmt_lbp(r["lbp_per_m2"])}/م²</div>', unsafe_allow_html=True)

st.markdown("---")

# ---------- الاشتراك ----------
st.subheader("📧 تقرير أسبوعي مجاني")
st.caption("سلمك تقريراً أسبوعياً: متوسطات الأسعار، الاتجاهات، وأبرز العروض — بدون رسائل مزعجة.")

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
                st.success("🎉 تم تسجيل اشتراكك! سيصلك التقرير الأسبوعي قريباً.")
            else:
                # احتياط محلي إذا فشل السحابي
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

st.markdown("---")
st.caption("⚠️ الأسعار بالليرة اللبنانية كما يعلنها البائع على السوق المفتوح — للتوجيه فقط، وليست تقييماً مهنياً. "
           "الأرقام الهاتفية مقنّعة؛ الرقم الكامل من صفحة الإعلان الرسمية.")
