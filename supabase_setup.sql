-- إعداد أمان Supabase لمنصة عقار لبنان
-- التنفيذ: Supabase Dashboard ← SQL Editor ← شغّل هذا الملف مرة واحدة

-- 1) تفعيل حماية الصفوف (RLS) على الجدولين
ALTER TABLE public.user_ads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users   ENABLE ROW LEVEL SECURITY;

-- 2) الجمهور (مفتاح anon) يقرأ إعلانات المستخدمين فقط — لا تعديل ولا حذف
--    كل عمليات الإضافة/التعديل/الحذف تتم عبر مفتاح service (من التطبيق، سرّي)
CREATE POLICY "public_read_user_ads" ON public.user_ads
  FOR SELECT USING (true);

-- 3) جدول المستخدمين (هواتف + تجزئات كلمات السر): لا قراءة عامة إطلاقاً
--    التسجيل والدخول يتمان بمفتاح service من داخل التطبيق
CREATE POLICY "no_public_users_read" ON public.users
  FOR SELECT USING (false);

-- ملاحظة: بدون هذه السياسات كان أي زائر يملك رابط REST الخاص بالمشروع
-- قادراً على قراءة/تعديل/حذف أي إعلان وأي حساب بمجرد معرفة رقمه التسلسلي.
