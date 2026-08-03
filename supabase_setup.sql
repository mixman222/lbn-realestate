-- ============================================================================
-- إعداد أمان Supabase لمنصة عقار لبنان
-- (نسخة آمنة قابلة لإعادة التشغيل أكثر من مرة دون أخطاء)
-- ============================================================================

-- 1) جدول المستخدمين (إن لم يكن موجوداً) — هواتف + تجزئات كلمات السر
CREATE TABLE IF NOT EXISTS public.users (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name        text NOT NULL,
  phone       text NOT NULL UNIQUE,
  salt        text NOT NULL,
  pw_hash     text NOT NULL,
  created_at  bigint
);

-- 2) أعمدة إعلانات المستخدمين التي يستخدمها التطبيق (تُضاف فقط إن كانت ناقصة)
ALTER TABLE public.user_ads ADD COLUMN IF NOT EXISTS prop_type     text;
ALTER TABLE public.user_ads ADD COLUMN IF NOT EXISTS governorate   text;
ALTER TABLE public.user_ads ADD COLUMN IF NOT EXISTS location      text;
ALTER TABLE public.user_ads ADD COLUMN IF NOT EXISTS floor         text;
ALTER TABLE public.user_ads ADD COLUMN IF NOT EXISTS rooms         integer;
ALTER TABLE public.user_ads ADD COLUMN IF NOT EXISTS area          numeric;
ALTER TABLE public.user_ads ADD COLUMN IF NOT EXISTS price_lbp     numeric;
ALTER TABLE public.user_ads ADD COLUMN IF NOT EXISTS furnished     text;
ALTER TABLE public.user_ads ADD COLUMN IF NOT EXISTS parking       text;
ALTER TABLE public.user_ads ADD COLUMN IF NOT EXISTS description   text;
ALTER TABLE public.user_ads ADD COLUMN IF NOT EXISTS name          text;
ALTER TABLE public.user_ads ADD COLUMN IF NOT EXISTS phone         text;
ALTER TABLE public.user_ads ADD COLUMN IF NOT EXISTS image_b64     text;
ALTER TABLE public.user_ads ADD COLUMN IF NOT EXISTS created_at    text;
ALTER TABLE public.user_ads ADD COLUMN IF NOT EXISTS status        text DEFAULT 'new';
ALTER TABLE public.user_ads ADD COLUMN IF NOT EXISTS deal_type     text DEFAULT 'للبيع';

-- 3) تفعيل حماية الصفوف (RLS) على الجدولين
ALTER TABLE public.user_ads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users   ENABLE ROW LEVEL SECURITY;

-- 4) الجمهور (مفتاح anon) يقرأ إعلانات المستخدمين فقط — لا تعديل ولا حذف
DROP POLICY IF EXISTS "public_read_user_ads" ON public.user_ads;
CREATE POLICY "public_read_user_ads" ON public.user_ads
  FOR SELECT TO anon, authenticated USING (true);

-- 5) النشر جديد (INSERT) مسموح للجمهور — هذه ميزة الموقع نفسه
DROP POLICY IF EXISTS "public_insert_user_ads" ON public.user_ads;
CREATE POLICY "public_insert_user_ads" ON public.user_ads
  FOR INSERT TO anon, authenticated WITH CHECK (true);

-- 6) التعديل والـحذف: فقط عبر مفتاح service (سري في التطبيق) — الجمهور ممنوع
DROP POLICY IF EXISTS "public_update_user_ads" ON public.user_ads;
CREATE POLICY "public_update_user_ads" ON public.user_ads
  FOR UPDATE TO anon, authenticated USING (false) WITH CHECK (false);
DROP POLICY IF EXISTS "public_delete_user_ads" ON public.user_ads;
CREATE POLICY "public_delete_user_ads" ON public.user_ads
  FOR DELETE TO anon, authenticated USING (false);

-- 7) جدول المستخدمين: لا قراءة عامة — كل عمليات الحسابات عبر مفتاح service
DROP POLICY IF EXISTS "no_public_users_read" ON public.users;
CREATE POLICY "no_public_users_read" ON public.users
  FOR SELECT TO anon, authenticated USING (false);

-- 8) عداد الزوار: جدول + سياسات (الجمهور: إدراج وقراءة فقط — لا تعديل ولا حذف)
CREATE TABLE IF NOT EXISTS public.site_visits (
  id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  session_id text NOT NULL,
  visit_date date NOT NULL DEFAULT CURRENT_DATE,
  created_at timestamptz DEFAULT now()
);
ALTER TABLE public.site_visits ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "public_site_visits_insert" ON public.site_visits;
CREATE POLICY "public_site_visits_insert" ON public.site_visits
  FOR INSERT TO anon, authenticated WITH CHECK (true);
DROP POLICY IF EXISTS "public_site_visits_select" ON public.site_visits;
CREATE POLICY "public_site_visits_select" ON public.site_visits
  FOR SELECT TO anon, authenticated USING (true);