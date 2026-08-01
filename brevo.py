"""
ربط Brevo (الإرسال وقائمة المشتركين):
- add_subscriber: يضيف المشترك لقائمة Weekly Report
- get_subscribers: يجلب قائمة المشتركين
- send_email: إرسال عبر SMTP Brevo
المفاتيح من متغيرات البيئة (لا تخزن في الكود)
"""
import os, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests

API_URL = "https://api.brevo.com/v3"
LIST_ID = int(os.environ.get("BREVO_LIST_ID", "3"))

def _headers():
    key = os.environ.get("BREVO_API_KEY", "")
    return {"api-key": key, "Content-Type": "application/json"}

def add_subscriber(email, role="غير ذلك"):
    """يضيف أو يحدّث مشتركاً في القائمة — يرجع (نجاح، رسالة)"""
    key = os.environ.get("BREVO_API_KEY", "")
    if not key:
        return False, "لا يوجد مفتاح Brevo"
    try:
        r = requests.put(f"{API_URL}/contacts/{email.lower()}",
                         headers=_headers(),
                         json={"email": email.lower(), "listIds": [LIST_ID],
                               "attributes": {"ROLE": role}},
                         timeout=15)
        if r.status_code in (200, 201, 204):
            return True, "ok"
        if r.status_code == 404:
            r2 = requests.post(f"{API_URL}/contacts",
                               headers=_headers(),
                               json={"email": email.lower(), "listIds": [LIST_ID],
                                     "attributes": {"ROLE": role}},
                               timeout=15)
            if r2.status_code in (200, 201):
                return True, "ok"
            return False, f"إنشاء فشل ({r2.status_code})"
        return False, f"فشل ({r.status_code})"
    except Exception as e:
        return False, str(e)

def get_subscribers():
    """كل إيميلات المشتركين في القائمة"""
    key = os.environ.get("BREVO_API_KEY", "")
    if not key:
        return []
    emails = []
    offset = 0
    while True:
        r = requests.get(f"{API_URL}/contacts/lists/{LIST_ID}/contacts",
                         headers=_headers(),
                         params={"limit": 500, "offset": offset}, timeout=15)
        if r.status_code != 200:
            break
        d = r.json()
        batch = [c.get("email") for c in d.get("contacts", [])]
        emails.extend(batch)
        if len(batch) < 500:
            break
        offset += 500
    return emails

def send_email(to_emails, subject, html_body):
    """يرسل عبر SMTP Brevo — bcc لكل المشتركين"""
    smtp_user = os.environ.get("BREVO_SMTP_USER", "b40b0e001@smtp-brevo.com")
    smtp_key = os.environ.get("BREVO_SMTP_KEY", "")
    sender = os.environ.get("BREVO_SENDER", "mixman222@gmail.com")
    if not smtp_key:
        return False, "لا يوجد مفتاح SMTP"
    msg = MIMEMultipart("alternative")
    msg["From"] = f"عقار لبنان <{sender}>"
    msg["To"] = sender
    msg["Subject"] = subject
    msg["Bcc"] = ", ".join(to_emails)
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    try:
        with smtplib.SMTP("smtp-relay.brevo.com", 587, timeout=30) as s:
            s.starttls()
            s.login(smtp_user, smtp_key)
            s.send_message(msg)
        return True, f"أُرسل إلى {len(to_emails)} مشترك"
    except Exception as e:
        return False, str(e)
