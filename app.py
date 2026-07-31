"""
موقع اتجاهات أسعار العقارات في لبنان
- صفحة رئيسية: ملخص السوق + اتجاهات
- صفحة الشقق: بحث وفلترة
- صفحة التحليلات: تفصيل بالأقضية
- صفحة الاشتراك: نموذج جمع مشتركين
"""
import os, sys, sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize import load_listings, normalize

st.set_page_config(page_title="عقار لبنان — اتجاهات الأسعار", layout="wide", page_icon="🏠")

# اتجاه RTL
st.markdown("""
<style>
    .stApp { direction: rtl; }
    .block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)

# سعر الصرف قابل للتعديل من الشريط الجانبي
lbp_rate = st.sidebar.number_input("سعر صرف الليرة للدولار", min_value=10000.0, max_value=150000.0,
                                   value=15000.0, step=1000.0, help="السوق المفتوح يعرض بالليرة — نحولها للدولار")

@st.cache_data(ttl=3600)
def load_data():
    df = load_listings()
    return normalize(df)

df = load_data()

st.title("🏠 عقار لبنان — اتجاهات أسعار السوق")
st.caption(f"بيانات حية من إعلانات السوق المفتوح — {len(df)} إعلان • آخر تحديث: {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}")

if df.empty:
    st.warning("لا توجد بيانات بعد — شغّل الزاحف أولاً: python scraper_opensooq.py")
    st.stop()

# ---------- KPIs ----------
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("📊 إعلانات مراقبة", f"{len(df)}")
with c2:
    st.metric("🏘️ أقضية مغطاة", f"{df['governorate'].nunique()}")
with c3:
    st.metric("💵 متوسط سعر المتر²", f"{df['price_per_m2'].median():,.0f}$")
with c4:
    st.metric("🏠 متوسط سعر العقار", f"{df['price_usd'].median():,.0f}$")

st.markdown("---")

# ---------- متوسط سعر المتر² حسب القضاء ----------
st.subheader("📈 متوسط سعر المتر² حسب القضاء")
g = (df.groupby('governorate')
       .agg(متوسط_سعر_المتر=('price_per_m2', 'median'),
            عدد_الإعلانات=('id', 'count'))
       .reset_index()
       .sort_values('متوسط_سعر_المتر', ascending=True))
fig = px.bar(g, x='متوسط_سعر_المتر', y='governorate', orientation='h',
             text_auto='.0f', color='متوسط_سعر_المتر', color_continuous_scale='viridis')
fig.update_layout(height=500, xaxis_title="دولار/م²", yaxis_title="", showlegend=False,
                  margin=dict(l=10, r=10, t=30, b=10))
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# ---------- الشقق: بحث وفلترة ----------
st.subheader("🔍 أحدث الشقق المعروضة")
col_f1, col_f2, col_f3, col_f4 = st.columns(4)
with col_f1:
    govs = ["الكل"] + sorted(df['governorate'].unique().tolist())
    sel_gov = st.selectbox("القضاء", govs)
with col_f2:
    types = ["الكل"] + sorted(df['prop_type'].dropna().unique().tolist())
    sel_type = st.selectbox("نوع العقار", types)
with col_f3:
    max_price = st.number_input("الحد الأقصى للسعر ($)", min_value=0, value=0, step=50000)
with col_f4:
    sort_by = st.selectbox("ترتيب", ["الأحدث", "السعر من الأقل", "السعر من الأعلى", "أقل سعر للمتر"])

f = df.copy()
if sel_gov != "الكل":
    f = f[f['governorate'] == sel_gov]
if sel_type != "الكل":
    f = f[f['prop_type'] == sel_type]
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

for _, r in f.head(20).iterrows():
    loc = f"{r['location']}، {r['city_ar']}" if pd.notna(r['location']) else r['city_ar']
    t = f"{r['title']}"
    if pd.notna(r['area']): t += f" • {r['area']:.0f} م²"
    if pd.notna(r['rooms']): t += f" • {r['rooms']:.0f} غرف"
    with st.container(border=True):
        cL, cR = st.columns([3, 1])
        with cL:
            st.markdown(f"**{t}**")
            st.caption(f"📍 {loc} • {r['prop_type'] or ''} • {r['date_posted'].strftime('%d/%m/%Y') if pd.notna(r['date_posted']) else ''}")
        with cR:
            st.markdown(f"### {r['price_usd']:,.0f}$")
            if pd.notna(r['area']) and r['area'] > 0:
                st.caption(f"{r['price_per_m2']:,.0f}$/م²")

st.markdown("---")
st.caption("⚠️ الأسعار تقريبية مبنية على إعلانات السوق المفتوح — للتوجيه فقط، وليست تقييماً مهنياً.")

# ---------- الاشتراك ----------
st.markdown("---")
st.subheader("📧 ابقَ على اطلاع — تقرير أسبوعي مجاني")
st.caption("سلمك تقريراً أسبوعياً: متوسطات الأسعار، الاتجاهات، وأبرز العروض — بدون رسائل مزعجة.")

with st.form("subscribe_form", clear_on_submit=True):
    sub_email = st.text_input("البريد الإلكتروني", placeholder="you@example.com")
    sub_role = st.selectbox("أنا...", ["مستثمر/مهتم بالشراء", "وسيط عقاري", "باحث/محلل", "غير ذلك"])
    submitted = st.form_submit_button("اشترك مجاناً", use_container_width=True)

if submitted:
    if "@" in sub_email and "." in sub_email:
        DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "subscribers.db")
        conn = sqlite3.connect(DB)
        conn.execute("CREATE TABLE IF NOT EXISTS subscribers (email TEXT PRIMARY KEY, role TEXT, created_at TEXT)")
        try:
            conn.execute("INSERT INTO subscribers (email, role, created_at) VALUES (?, ?, ?)",
                         (sub_email.strip().lower(), sub_role, pd.Timestamp.now().isoformat()))
            conn.commit()
            st.success("🎉 تم تسجيل اشتراكك! ستصلك رسالة التفعيل قريباً.")
        except sqlite3.IntegrityError:
            st.info("أنت مسجّل سابقاً — شكراً لثقتك!")
        conn.close()
    else:
        st.error("يرجى إدخال بريد إلكتروني صحيح.")
