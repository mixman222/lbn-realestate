"""
التقرير الأسبوعي لعقار لبنان — يولّد ملخص السوق ويرسله لكل المشتركين عبر Brevo.
الاستخدام: BREVO_API_KEY + BREVO_SMTP_KEY في البيئة، ثم python send_report.py
"""
import os, sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

import brevo
from normalize import load_listings, normalize

def fmt_lbp(v):
    if v >= 1e9:
        return f"{v/1e9:.2f} مليار ل.ل"
    if v >= 1e6:
        return f"{v/1e6:.1f} مليون ل.ل"
    if v >= 1e3:
        return f"{v/1e3:.0f} ألف ل.ل"
    return f"{v:,.0f} ل.ل"

def build_report():
    df = normalize(load_listings())
    if df.empty:
        return None, None
    week_ago = datetime.now() - timedelta(days=7)
    new_ads = df[df['first_seen'] >= week_ago.strftime('%Y-%m-%d')]
    gov = (df.groupby('governorate')
             .agg(متوسط=('lbp_per_m2', 'median'), عدد=('id', 'count'))
             .sort_values('متوسط', ascending=False))
    top = gov.head(5)
    cheap = df.nsmallest(5, 'lbp_per_m2')
    latest = df.sort_values('first_seen', ascending=False).head(5)

    rows_gov = "".join(
        f"<tr><td>{idx}</td><td>{fmt_lbp(v['متوسط'])}</td><td>{v['عدد']}</td></tr>"
        for idx, v in top.iterrows())
    rows_new = "".join(
        f"<tr><td>{r['title'][:60]}</td><td>{r['city_ar']}</td><td>{fmt_lbp(r['price_lbp'])}</td></tr>"
        for _, r in latest.iterrows() if not r['title'] == "")
    rows_cheap = "".join(
        f"<tr><td>{r['title'][:60]}</td><td>{r['city_ar']}</td><td>{fmt_lbp(r['lbp_per_m2'])}</td></tr>"
        for _, r in cheap.iterrows())

    html = f"""
    <div dir="rtl" style="font-family:Segoe UI,Tahoma,sans-serif;max-width:640px;margin:auto;">
      <div style="background:linear-gradient(135deg,#1f6f8b,#2a9d8f);color:#fff;border-radius:14px;padding:22px 26px;">
        <h2 style="margin:0;">🏠 عقار لبنان — التقرير الأسبوعي</h2>
        <p style="margin:6px 0 0;opacity:.9;">{datetime.now().strftime('%d/%m/%Y')} • {len(df)} إعلان نشط • {df['governorate'].nunique()} قضاء</p>
      </div>
      <h3>📊 أغلى 5 أقضية (سعر المتر²)</h3>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <tr style="background:#eef4f6;"><th style="padding:8px;text-align:right;">القضاء</th><th>المتوسط</th><th>إعلانات</th></tr>
        {rows_gov}
      </table>
      <h3>🆕 أحدث الإعلانات</h3>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <tr style="background:#eef4f6;"><th style="padding:8px;text-align:right;">العنوان</th><th>القضاء</th><th>السعر</th></tr>
        {rows_new}
      </table>
      <h3>💎 أفضل 5 صفقات (سعر المتر²)</h3>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <tr style="background:#eef4f6;"><th style="padding:8px;text-align:right;">العنوان</th><th>القضاء</th><th>ل.ل/م²</th></tr>
        {rows_cheap}
      </table>
      <p style="color:#6b7280;font-size:12px;margin-top:18px;">
        شاهد الموقع كاملاً: <a href="https://byout-lb.streamlit.app">byout-lb.streamlit.app</a><br>
        الأسعار كما يعلنها البائعون على السوق المفتوح — للتوجيه فقط.
      </p>
    </div>
    """
    subject = f"عقار لبنان — تقرير {datetime.now().strftime('%d/%m/%Y')}"
    return subject, html

if __name__ == "__main__":
    subject, html = build_report()
    if not subject:
        print("لا توجد بيانات — لم يرسل شيء")
        sys.exit(1)
    subs = brevo.get_subscribers()
    print(f"المشتركون: {len(subs)}")
    if not subs:
        print("لا مشتركين بعد — لم يرسل شيء")
        sys.exit(0)
    ok, msg = brevo.send_email(subs, subject, html)
    print("نتيجة:", msg)
    sys.exit(0 if ok else 1)
