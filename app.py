
# app.py
import streamlit as st
import datetime as dt
import json
from pathlib import Path
from io import BytesIO
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import fitz  # PyMuPDF

# -------------------------------
# CONFIG & STYLES
# -------------------------------
st.set_page_config(page_title="MedTimer", page_icon="⏰", layout="wide")

# Theme toggles
THEMES = {
    "Light": {
        "bg": "#F8FCFF",
        "text": "#0D1B2A",
        "card": "#FFFFFF",
        "accent_green": "#2e7d32",
        "accent_yellow": "#f9a825",
        "accent_red": "#c62828",
        "accent_blue": "#1976d2",
    },
    "Dark": {
        "bg": "#0D1B2A",
        "text": "#E5E7EB",
        "card": "#162A3A",
        "accent_green": "#81c784",
        "accent_yellow": "#ffd54f",
        "accent_red": "#e57373",
        "accent_blue": "#64b5f6",
    },
    "High-Contrast": {
        "bg": "#000000",
        "text": "#FFFFFF",
        "card": "#000000",
        "accent_green": "#00FF00",
        "accent_yellow": "#FFFF00",
        "accent_red": "#FF0000",
        "accent_blue": "#00BFFF",
    },
}

if "theme_name" not in st.session_state:
    st.session_state.theme_name = "Light"
theme = THEMES[st.session_state.theme_name]

def inject_css():
    st.markdown(
        f"""
        <style>
            html, body, .appview-container {{
                background: {theme['bg']} !important;
                color: {theme['text']} !important;
            }}
            .big-title {{
                font-size: 2.0rem;
                font-weight: 700;
                color: {theme['accent_blue']};
            }}
            .card {{
                background: {theme['card']};
                border: 1px solid rgba(0,0,0,0.1);
                border-radius: 12px;
                padding: 12px 14px;
                margin: 8px 0;
            }}
            .status-pill {{
                font-weight: 600;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )

inject_css()

# -------------------------------
# DATA MODELS & STORAGE
# -------------------------------
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
LOG_PATH = DATA_DIR / "adherence_log.json"
MEDS_PATH = DATA_DIR / "meds.json"

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

@dataclass
class Med:
    name: str
    time: str            # "HH:MM" 24h
    days: List[str]      # e.g., ["Mon","Tue","Wed",...]
    active: bool = True
    reminder_min: int = 10  # minutes before

def load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return default

def save_json(path: Path, obj):
    try:
        path.write_text(json.dumps(obj, indent=2))
    except Exception:
        # Graceful: ignore write errors on hosted environments
        pass

def init_state():
    if "meds" not in st.session_state:
        # Load from disk or seed examples
        raw_meds = load_json(MEDS_PATH, default=None)
        if raw_meds is None:
            st.session_state.meds: List[Dict] = [
                asdict(Med("Metformin", "08:00", WEEKDAYS, True, 15)),
                asdict(Med("Vitamin D", "21:00", WEEKDAYS, True, 10)),
            ]
        else:
            st.session_state.meds = raw_meds

    if "taken_today" not in st.session_state:
        st.session_state.taken_today = set()  # e.g., "YYYY-MM-DD|name|HH:MM"

    if "tips_idx" not in st.session_state:
        st.session_state.tips_idx = 0

    if "adherence_log" not in st.session_state:
        st.session_state.adherence_log = load_json(LOG_PATH, default={})  # {date: {"taken":[], "scheduled":int}}

init_state()

TIPS = [
    "Small wins count—stay hydrated and take meds on time.",
    "Set a routine: same place, same time, every day.",
    "Celebrate adherence streaks—you’re doing great!",
    "Consistency beats intensity—keep a steady rhythm.",
]

# -------------------------------
# HELPERS
# -------------------------------
def parse_time(tstr: str) -> Optional[dt.time]:
    try:
        hh, mm = map(int, tstr.strip().split(":"))
        return dt.time(hh, mm)
    except Exception:
        return None

def now_local() -> dt.datetime:
    return dt.datetime.now()

def today_weekday(now=None) -> str:
    now = now or now_local()
    return WEEKDAYS[now.weekday()]

def is_for_today(days: List[str], now=None) -> bool:
    return today_weekday(now) in days

def sched_dt_for_today(t: dt.time, now=None) -> dt.datetime:
    now = now or now_local()
    return dt.datetime.combine(now.date(), t)

def schedule_key(date: dt.date, name: str, time_str: str) -> str:
    return f"{date.isoformat()}|{name}|{time_str}"

def build_today_schedule(meds: List[Dict], now=None, grace_min=60):
    now = now or now_local()
    items = []
    for m in meds:
        if not m.get("active", True):
            continue
        if not is_for_today(m.get("days", WEEKDAYS), now):
            continue
        t = parse_time(m.get("time", ""))
        if not t:
            continue
        sdt = sched_dt_for_today(t, now)
        key = schedule_key(now.date(), m["name"], m["time"])

        if key in st.session_state.taken_today:
            status = "taken"
        else:
            grace = dt.timedelta(minutes=grace_min)
            if now < sdt:
                status = "upcoming"
            elif now > sdt + grace:
                status = "missed"
            else:
                status = "upcoming"
        items.append({
            "name": m["name"],
            "time": t,
            "time_str": m["time"],
            "status": status,
            "key": key,
            "reminder_min": int(m.get("reminder_min", 10)),
            "scheduled_dt": sdt,
        })
    items.sort(key=lambda x: x["time"])
    return items

def record_daily_log(now=None):
    """Persist scheduled count and taken keys for today."""
    now = now or now_local()
    date_key = now.date().isoformat()
    sched = build_today_schedule(st.session_state.meds, now)
    taken = [s["key"] for s in sched if s["key"] in st.session_state.taken_today]
    st.session_state.adherence_log[date_key] = {
        "taken": taken,
        "scheduled": len(sched),
    }
    save_json(LOG_PATH, st.session_state.adherence_log)

def adherence_for_date(date: dt.date) -> int:
    """Return adherence % for given date from log."""
    dk = date.isoformat()
    entry = st.session_state.adherence_log.get(dk)
    if not entry:
        # compute ad-hoc from today's meds schedule (approx)
        # Note: historical meds may have changed—this is a best-effort.
        now = dt.datetime.combine(date, dt.datetime.min.time())
        sched = build_today_schedule(st.session_state.meds, now)
        taken = 0
        scheduled = len(sched)
    else:
        taken = len(entry["taken"])
        scheduled = entry.get("scheduled", 0)
    return int((taken / scheduled) * 100) if scheduled else 100

def adherence_past_7_days(now=None) -> int:
    now = now or now_local()
    totals_taken = 0
    totals_sched = 0
    for i in range(7):
        d = (now.date() - dt.timedelta(days=i))
        dk = d.isoformat()
        entry = st.session_state.adherence_log.get(dk)
        if entry:
            totals_taken += len(entry.get("taken", []))
            totals_sched += entry.get("scheduled", 0)
        else:
            # approximate current meds for that day
            # Build schedule for d's weekday
            dn = dt.datetime.combine(d, dt.datetime.now().time())
            sched = build_today_schedule(st.session_state.meds, dn)
            totals_sched += len(sched)
            # no taken data for earlier days unless logged
    return int((totals_taken / totals_sched) * 100) if totals_sched else 100

def current_streak(now=None, threshold=80) -> int:
    """Consecutive past days with adherence >= threshold."""
    now = now or now_local()
    streak = 0
    for i in range(0, 30):  # cap at last 30 days
        d = (now.date() - dt.timedelta(days=i))
        if adherence_for_date(d) >= threshold:
            streak += 1
        else:
            break
    return streak

# -------------------------------
# ENCOURAGEMENT GRAPHIC (Turtle-style with safe fallback)
# -------------------------------
def make_encouragement_image(score: int) -> BytesIO:
    """
    Generate a turtle-style encouragement graphic.
    We try to mimic Turtle drawing with Pillow for Streamlit compatibility.
    """
    img = Image.new("RGB", (420, 260), (240, 255, 240))
    d = ImageDraw.Draw(img)

    # Title
    d.rectangle((0,0,420,40), fill=(220,240,220))
    d.text((12,10), f"Adherence: {score}%", fill=(0,100,0))

    # Trophy / Smiley based on score
    if score >= 90:
        # Trophy
        d.ellipse((160,60,260,140), fill=(255,215,0), outline=(184,134,11), width=3)
        d.rectangle((205,140,215,180), fill=(218,165,32))
        d.rectangle((170,180,250,195), fill=(184,134,11))
        d.text((120,210), "Excellent! 🏆", fill=(0,128,0))
    elif score >= 80:
        # Smiley
        d.ellipse((160,60,260,160), outline=(0,128,0), width=4)
        d.ellipse((185,95,200,110), fill=(0,128,0))
        d.ellipse((220,95,235,110), fill=(0,128,0))
        d.arc((185,115,235,155), start=180, end=360, fill=(0,128,0), width=3)
        d.text((140,210), "Great job 😊", fill=(0,128,0))
    elif score >= 70:
        d.text((120,120), "Keep going 💪", fill=(0,128,0))
    else:
        d.text((85,120), "You’ve got this!\nTry setting reminders.", fill=(139,0,0))

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# -------------------------------
# AUDIO ALERT (WAV beep)
# -------------------------------
def make_beep(duration_sec=0.5, freq_hz=880, sr=44100, volume=0.4) -> BytesIO:
    t = np.linspace(0, duration_sec, int(sr * duration_sec), False)
    wave = (np.sin(2 * np.pi * freq_hz * t) * volume).astype(np.float32)

    # Write simple WAV (PCM 16-bit)
    buf = BytesIO()
    import wave, struct
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sr)
        for s in wave:
            wf.writeframes(struct.pack('<h', int(max(-1.0, min(1.0, s)) * 32767)))
    buf.seek(0)
    return buf

# -------------------------------
# WEEKLY REPORT (CSV + PDF)
# -------------------------------
def weekly_dataframe(now=None):
    import pandas as pd
    now = now or now_local()
    rows = []
    for i in range(6, -1, -1):
        d = now.date() - dt.timedelta(days=i)
        rows.append({
            "Date": d.isoformat(),
            "Scheduled": st.session_state.adherence_log.get(d.isoformat(), {}).get("scheduled", 0),
            "Taken": len(st.session_state.adherence_log.get(d.isoformat(), {}).get("taken", [])),
            "Adherence%": adherence_for_date(d),
        })
    return pd.DataFrame(rows)

def weekly_report_pdf(now=None) -> BytesIO:
    now = now or now_local()
    df = weekly_dataframe(now)
    doc = fitz.open()
    page = doc.new_page()
    title = f"MedTimer Weekly Report ({(now.date() - dt.timedelta(days=6)).isoformat()} to {now.date().isoformat()})"
    page.insert_text((50, 50), title, fontsize=16, fontname="helv", fill=(0,0,0))
    y = 90
    for _, r in df.iterrows():
        line = f"{r['Date']}  |  Scheduled: {r['Scheduled']}  |  Taken: {r['Taken']}  |  Adherence: {r['Adherence%']}%"
        page.insert_text((50, y), line, fontsize=12, fontname="helv", fill=(0,0,0))
        y += 22
    page.insert_text((50, y+20), "Generated by MedTimer", fontsize=10)
    pdf_bytes = doc.tobytes()
    doc.close()
    return BytesIO(pdf_bytes)

# -------------------------------
# UI COMPONENTS
# -------------------------------
st.markdown('<div class="big-title">⏰ MedTimer – Daily Medicine Companion</div>', unsafe_allow_html=True)

# Accessibility toggles
with st.sidebar:
    st.header("Accessibility")
    st.session_state.theme_name = st.radio("Theme", list(THEMES.keys()), index=list(THEMES.keys()).index(st.session_state.theme_name))
    inject_css()
    st.caption("Choose light / dark / high-contrast for better readability.")

# Main layout
col_left, col_right = st.columns([2, 1])

# ---------- LEFT: Checklist & Actions ----------
with col_left:
    st.subheader("Today's Checklist")
    now = now_local()
    schedule = build_today_schedule(st.session_state.meds, now)

    # Reminder alerts + beep for doses within reminder window
    due_alerts = []
    for s in schedule:
        diff_min = (s["scheduled_dt"] - now).total_seconds() / 60
        if 0 <= diff_min <= s["reminder_min"] and s["key"] not in st.session_state.taken_today:
            due_alerts.append((s["name"], int(diff_min)))
    if due_alerts:
        st.warning("Upcoming doses soon:")
        for name, mins in due_alerts:
            st.write(f"• **{name}** in **{mins} min**")
        # Play beep
        if st.button("🔔 Play alert beep"):
            st.audio(make_beep(), format="audio/wav")

    for s in schedule:
        color = {
            "taken": theme["accent_green"],
            "upcoming": theme["accent_yellow"],
            "missed": theme["accent_red"],
        }[s["status"]]

        st.markdown(
            f"""
            <div class="card" style="border-left: 8px solid {color}">
              <div style="font-size: 1.05rem; font-weight: 600;">
                {s['name']} — {s['time'].strftime('%H:%M')}
                <span class="status-pill" style="float:right; color:{color};">{s['status'].title()}</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        btn_cols = st.columns([1, 1, 2])
        with btn_cols[0]:
            if s["status"] != "taken":
                if st.button(f"Mark taken", key=s["key"]):
                    st.session_state.taken_today.add(s["key"])
                    record_daily_log(now)
                    st.experimental_rerun()
        with btn_cols[1]:
            st.caption(f"Reminder: {s['reminder_min']} min before")

# ---------- RIGHT: Score, Graphic, Tips, Streak, Reports ----------
with col_right:
    st.subheader("Weekly Adherence")
    record_daily_log(now)
    weekly_score = adherence_past_7_days(now)
    st.progress(weekly_score / 100.0)
    st.write(f"**Score:** {weekly_score}%")
    st.image(make_encouragement_image(weekly_score), caption="Encouragement", use_column_width=True)

    st.subheader("Streak")
    streak = current_streak(now, threshold=80)
    st.info(f"Current streak: **{streak}** day(s) with ≥80% adherence")

    st.subheader("Tip of the day")
    st.info(TIPS[st.session_state.tips_idx])
    if st.button("Next tip"):
        st.session_state.tips_idx = (st.session_state.tips_idx + 1) % len(TIPS)

    st.subheader("Weekly Report")
    # CSV
    df = weekly_dataframe(now)
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", data=csv_bytes, file_name="medtimer_weekly_report.csv", mime="text/csv")
    # PDF
    st.download_button("⬇️ Download PDF", data=weekly_report_pdf(now), file_name="medtimer_weekly_report.pdf", mime="application/pdf")

st.divider()
st.header("Manage Medicines")

# Add form
with st.form("add_med"):
    name = st.text_input("Medicine name", placeholder="e.g., Metformin")
    time_str = st.text_input("Time (24h HH:MM)", placeholder="08:00")
    days = st.multiselect("Days", WEEKDAYS, default=WEEKDAYS)
    reminder_min = st.number_input("Reminder (minutes before time)", min_value=0, max_value=180, value=10, step=5)
    submitted = st.form_submit_button("Add medicine")
    if submitted:
        if not name or not parse_time(time_str):
            st.error("Please enter a valid name and time (HH:MM).")
        else:
            st.session_state.meds.append(asdict(Med(name, time_str, days, True, int(reminder_min))))
            save_json(MEDS_PATH, st.session_state.meds)
            st.success(f"Added {name} at {time_str} on {', '.join(days)}")

# Editor/remover
for i, m in enumerate(st.session_state.meds):
    with st.expander(f"{m['name']} @ {m['time']}  ({','.join(m['days'])})"):
        colA, colB, colC, colD = st.columns([1, 1, 1, 1])
        with colA:
            st.session_state.meds[i]["active"] = st.checkbox("Active", value=m["active"], key=f"active_{i}")
        with colB:
            new_time = st.text_input("Time", value=m["time"], key=f"time_{i}")
            if parse_time(new_time):
                st.session_state.meds[i]["time"] = new_time
        with colC:
            new_days = st.multiselect("Days", WEEKDAYS, default=m["days"], key=f"days_{i}")
            st.session_state.meds[i]["days"] = new_days
        with colD:
            rem = st.number_input("Reminder (min)", min_value=0, max_value=180, value=int(m.get("reminder_min", 10)), key=f"rem_{i}")
            st.session_state.meds[i]["reminder_min"] = int(rem)

        cX, cY = st.columns([1,1])
        with cX:
            if st.button(f"Save changes", key=f"save_{i}"):
                save_json(MEDS_PATH, st.session_state.meds)
                st.success("Saved.")
        with cY:
            if st.button(f"Delete {m['name']}", key=f"del_{i}"):
                st.session_state.meds.pop(i)
                save_json(MEDS_PATH, st.session_state.meds)
                st.experimental_rerun()
