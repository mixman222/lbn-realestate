# عقار لبنان — اتجاهات أسعار السوق

موقع مجاني يتابع أسعار العقارات في لبنان عبر زحف إعلانات السوق المفتوح يومياً، ويعرض الاتجاهات بالدولار (سعر الصرف الرسمي 15,000).

## الملفات
| ملف | الوظيفة |
|---|---|
| `scraper_opensooq.py` | زاحف الإعلانات (73 صفحة: أنواع + مدن + أحياء) → SQLite |
| `normalize.py` | توحيد أسماء المدن، حساب $/م²، تصفية القيم الشاذة |
| `app.py` | موقع Streamlit: اتجاهات، بحث، نموذج اشتراك |
| `subscribers.db` | المشتركون (ينشأ تلقائياً) |

## التشغيل المحلي
```bash
pip install -r requirements.txt
python scraper_opensooq.py   # زحف جديد
python -m streamlit run app.py
```

## التحديث اليومي
GitHub Action (`.github/workflows/daily_scrape.yml`) يزحف يومياً الساعة 8 صباحاً ويرفع البيانات تلقائياً.

## النشر على Streamlit Cloud
1. ارفع هذا المجلد كريبو GitHub
2. Streamlit Cloud → New app → اختر الريبو (main, app.py)
