
# app.py
import streamlit as st
import datetime as dt
import json
import csv
import math
import wave
import struct
import os
from pathlib import Path

# Optional (local only for drawing): standard-library turtle
# In Streamlit Cloud, this may not open; we guard usage.
try:
    import turtle
    TURTLE_AVAILABLE = True
except Exception:
    TURTLE_AVAILABLE = False

# -------------------------------
# BASIC CONFIG & THEMES (Accessibility)
# -------------------------------
st.set_page_config(page_title="MedTimer", page_icon="⏰", layout="wide")

THEMES = {
    "Light": {
        "bg": "#F8FCFF", "text": "#0D1B2A", "card": "#FFFFFF",
        "green": "#2e7d32", "yellow": "#f9a825", "red": "#c62828", "blue": "#1976d2"
    },
    "Dark": {
        "bg": "#0D1B2A", "text": "#E5E7EB", "card": "#162A3A",
        "green": "#81c784", "yellow": "#ffd54f", "red": "#e57373", "blue": "#64b5f6"
    },
    "High-Contrast": {
        "bg": "#000000", "text": "#FFFFFF", "card": "#000000",
        "green": "#00FF00", "yellow": "#FFFF00", "red": "#FF0000", "blue": "#00BFFF"
    },
}
if "theme" not in st.session_state:
    st.session_state.theme = "Light"
theme = THEMES[st.session_state.theme]

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
                color: {theme['blue']};
            }}
            .card {{
                background: {theme['card']};
                border: 1px solid rgba(0,0,0,0.1);
                border-radius: 12px;
                padding: 12px 14px;
                margin: 8px 0;
            }}
            .pill {{
                font-weight: 600;
            }}
        </style>
        """,
        unsafe_allow_html=True
    )

inject_css()

# -------------------------------
# PERSISTENCE (JSON in ./data/)
# -------------------------------
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
MEDS_PATH = DATA_DIR / "meds.json"
LOG_PATH = DATA_DIR / "adherence_log.json"

WEEKDAYS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

def load_json(path, default):
    try:
        if Path(path).exists():
            return json.loads(Path(path).read_text())
    except Exception:
        pass
    return default

def save_json(path, obj):
    try:
        Path(path).write_text(json.dumps(obj, indent=2))
    except Exception:
        # On some hosted envs, writes may be ephemeral—ignore errors.
        pass

# -------------------------------
# INIT STATE
# -------------------------------
def init_state():
    if "meds" not in st.session_state:
        meds = load_json(MEDS_PATH, default=None)
        if meds is None:
            st.session_state.meds = [
                {"name": "Metformin", "time": "08:00", "days": WEEKDAYS, "active": True, "reminder_min": 10},
                {"name": "Vitamin D", "time": "21:00", "days": WEEKDAYS, "active": True, "reminder_min": 10},
            ]
        else:
            st.session_state.meds = meds
    if "taken_today" not in st.session_state:
        st.session_state.taken_today = set()  # "YYYY-MM-DD|name|HH:MM"
    if "tips_idx" not in st.session_state:
        st.session_state.tips_idx = 0
    if "adherence_log" not in st.session_state:
        st.session_state.adherence_log = load_json(LOG_PATH, default={})

init_state()

TIPS = [
    "Small wins count—stay hydrated and take meds on time.",
    "Set a routine: same place, same time, every day.",
    "Celebrate adherence streaks—you’re doing great!",
    "Consistency beats intensity—keep a steady rhythm.",
]

# -------------------------------
# UTILITIES
# -------------------------------
def parse_time(tstr):
    try:
        hh, mm = map(int, tstr.strip().split(":"))
        return dt.time(hh, mm)
    except Exception:
        return None

def now_local():
    return dt.datetime.now()

def today_weekday(now=None):
    now = now or now_local()
    return WEEKDAYS[now.weekday()]

def is_for_today(days, now=None):
    return today_weekday(now) in days

def combine_today(t: dt.time, now=None):
    now = now or now_local()
    return dt.datetime.combine(now.date(), t)

def schedule_key(date: dt.date, name: str, time_str: str):
    return f"{date.isoformat()}|{name}|{time_str}"

def build_today_schedule(meds, now=None, grace_min=60):
    """
    Returns list of dicts:
      {name, time (dt.time), time_str, status, key, reminder_min, scheduled_dt}
    Status rules:
      taken: key in taken_today
      upcoming: now < scheduled_dt (or within grace window after time)
      missed: now > scheduled_dt + grace
    """
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
        sdt = combine_today(t, now)
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
            "name": m["name"], "time": t, "time_str": m["time"], "status": status,
            "key": key, "reminder_min": int(m.get("reminder_min", 10)), "scheduled_dt": sdt
        })
    items.sort(key=lambda x: x["time"])
    return items

def record_daily_log(now=None):
    """Persist scheduled count and taken keys for today."""
    now = now or now_local()
    date_key = now.date().isoformat()
    sched = build_today_schedule(st.session_state.meds, now)
    taken = [s["key"] for s in sched if s["key"] in st.session_state.taken_today]
    st.session_state.adherence_log[date_key] = {"taken": taken, "scheduled": len(sched)}
    save_json(LOG_PATH, st.session_state.adherence_log)

def adherence_for_date(date: dt.date):
    entry = st.session_state.adherence_log.get(date.isoformat())
    if not entry:
        # Best-effort approximation if no log
        dn = dt.datetime.combine(date, dt.datetime.min.time())
        sched = build_today_schedule(st.session_state.meds, dn)
        scheduled = len(sched)
        return 100 if scheduled == 0 else 0
    taken = len(entry.get("taken", []))
    scheduled = entry.get("scheduled", 0)
    return int((taken / scheduled) * 100) if scheduled else 100

def adherence_past_7_days(now=None):
    now = now or now_local()
    total_taken, total_sched = 0, 0
    for i in range(7):
        d = now.date() - dt.timedelta(days=i)
        entry = st.session_state.adherence_log.get(d.isoformat())
        if entry:
            total_taken += len(entry.get("taken", []))
            total_sched += entry.get("scheduled", 0)
        else:
            # If not logged, we assume scheduled exists but none taken
            dn = dt.datetime.combine(d, dt.datetime.min.time())
            total_sched += len(build_today_schedule(st.session_state.meds, dn))
    return int((total_taken / total_sched) * 100) if total_sched else 100

def current_streak(now=None, threshold=80):
    now = now or now_local()
    streak = 0
    for i in range(30):  # look back up to 30 days
        d = now.date() - dt.timedelta(days=i)
        if adherence_for_date(d) >= threshold:
            streak += 1
        else:
            break
    return streak

# -------------------------------
# AUDIO BEEP (basic WAV from stdlib)
# -------------------------------
def make_beep(duration_sec=0.5, freq_hz=880, sr=44100, volume=0.4):
    """
    Creates a WAV beep in-memory using math+wave+struct (stdlib only).
    """
    n_samples = int(sr * duration_sec)
    buf = st.session_state.get("_beep_buf")
    # Always regenerate to avoid caching artifacts
    buf = None
    from io import BytesIO
    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit PCM
        wf.setframerate(sr)
        for i in range(n_samples):
            t = i / sr
            sample = int(32767 * volume * math.sin(2 * math.pi * freq_hz * t))
            wf.writeframes(struct.pack('<h', sample))
    buf.seek(0)
    return buf

# -------------------------------
# TURTLE REWARD (local only)
# -------------------------------
def draw_turtle_reward(score):
    """
    Opens a turtle window and draws a smiley/trophy depending on score.
    Works locally; likely won't render on Streamlit Cloud.
    """
    if not TURTLE_AVAILABLE:
        st.warning("Turtle module not available in this environment.")
        return
    wn = turtle.Screen()
    wn.title(f"MedTimer Reward — Adherence {score}%")
    t = turtle.Turtle()
    t.speed(0)

    if score >= 90:
        # Simple trophy: base + cup
        t.color("gold"); t.pensize(5)
        t.penup(); t.goto(-50, -100); t.pendown()
        for _ in range(2):
            t.forward(100); t.left(90); t.forward(20); t.left(90)
        t.penup(); t.goto(0, -80); t.pendown()
        t.left(90); t.forward(80); t.right(90)
        t.circle(50)  # cup
    elif score >= 80:
        # Smiley
        t.color("green"); t.pensize(4)
        t.penup(); t.goto(0, -50); t.pendown()
        t.circle(80)
        # eyes
        for x in (-30, 30):
            t.penup(); t.goto(x, 40); t.pendown()
            t.circle(10)
        # smile
        t.penup(); t.goto(-40, 10); t.setheading(-60); t.pendown()
        for _ in range(60):  # arc
            t.forward(2); t.left(2)
    else:
        # Encouragement text
        t.color("red"); t.penup(); t.goto(-100, 0); t.pendown()
        t.write("You’ve got this!\nTry setting reminders.", font=("Arial", 16, "normal"))

    # Keep window open until user closes it
    turtle.done()

# -------------------------------
# WEEKLY REPORT (CSV via stdlib)
# -------------------------------
def weekly_csv_bytes(now=None):
    """
    Build a CSV (in-memory) of last 7 days: Date, Scheduled, Taken, Adherence%.
    """
    now = now or now_local()
    from io import StringIO
    s = StringIO()
    writer = csv.writer(s)
    writer.writerow(["Date", "Scheduled", "Taken", "Adherence%"])
    for i in range(6, -1, -1):
        d = now.date() - dt.timedelta(days=i)
        entry = st.session_state.adherence_log.get(d.isoformat(), {})
        scheduled = entry.get("scheduled", 0)
        taken = len(entry.get("taken", []))
        adh = adherence_for_date(d)
        writer.writerow([d.isoformat(), scheduled, taken, adh])
    return s.getvalue().encode("utf-8")

# -------------------------------
# UI
# -------------------------------
st.markdown('<div class="big-title">⏰ MedTimer – Daily Medicine Companion</div>', unsafe_allow_html=True)

# Sidebar: Accessibility / Theme
with st.sidebar:
    st.header("Accessibility")
    st.session_state.theme = st.radio("Theme", list(THEMES.keys()), index=list(THEMES.keys()).index(st.session_state.theme))
    inject_css()
    st.caption("Toggle light / dark / high-contrast for readability.")

# Layout
left, right = st.columns([2,1])

# ---------- LEFT: Checklist ----------
with left:
    st.subheader("Today's Checklist")
    now = now_local()
    schedule = build_today_schedule(st.session_state.meds, now)

    # Reminder alerts within per-medicine window
    upcoming = []
    for s in schedule:
        minutes_to = int((s["scheduled_dt"] - now).total_seconds() // 60)
        if 0 <= minutes_to <= s["reminder_min"] and s["status"] != "taken":
            upcoming.append((s["name"], minutes_to))
    if upcoming:
        st.warning("Upcoming doses soon:")
        for name, mins in upcoming:
            st.write(f"• **{name}** in **{mins} min**")
        if st.button("🔔 Play alert beep"):
            st.audio(make_beep(), format="audio/wav")

    for s in schedule:
        color = {"taken": theme["green"], "upcoming": theme["yellow"], "missed": theme["red"]}[s["status"]]
        st.markdown(
            f"""
            <div class="card" style="border-left:8px solid {color}">
              <div style="font-size: 1.05rem; font-weight: 600;">
                {s['name']} — {s['time'].strftime('%H:%M')}
                <span class="pill" style="float:right; color:{color};">{s['status'].title()}</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        c1, c2 = st.columns([1,2])
        with c1:
            if s["status"] != "taken":
                if st.button("Mark taken", key=s["key"]):
                    st.session_state.taken_today.add(s["key"])
                    record_daily_log(now)
                    st.experimental_rerun()
        with c2:
            st.caption(f"Reminder: {s['reminder_min']} min before")

# ---------- RIGHT: Score, Reward, Tips, Streak, Report ----------
with right:
    st.subheader("Weekly Adherence")
    record_daily_log(now)
    score7 = adherence_past_7_days(now)
    st.progress(score7 / 100.0)
    st.write(f"**Score:** {score7}%")

    # Reward (emoji fallback) + Turtle (local)
    if score7 >= 90:
        st.success("🏆 Excellent adherence! (Turtle trophy available locally)")
    elif score7 >= 80:
        st.info("😊 Great job! (Turtle smiley available locally)")
    elif score7 >= 70:
        st.info("💪 Keep going!")
    else:
        st.warning("You’ve got this! Try setting reminders.")

    if TURTLE_AVAILABLE:
        if st.button("🧩 Show Turtle Reward (local only)"):
            draw_turtle_reward(score7)
    else:
        st.caption("Turtle graphics not available in this environment.")

    st.subheader("Streak")
    st.info(f"Current streak: **{current_streak(now, threshold=80)}** day(s) with ≥80% adherence")

    st.subheader("Tip of the day")
    st.info(TIPS[st.session_state.tips_idx])
    if st.button("Next tip"):
        st.session_state.tips_idx = (st.session_state.tips_idx + 1) % len(TIPS)

    st.subheader("Weekly Report")
    st.download_button("⬇️ Download CSV", data=weekly_csv_bytes(now), file_name="medtimer_weekly_report.csv", mime="text/csv")

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
            st.session_state.meds.append({
                "name": name, "time": time_str, "days": days, "active": True, "reminder_min": int(reminder_min)
            })
            save_json(MEDS_PATH, st.session_state.meds)
            st.success(f"Added {name} at {time_str} on {', '.join(days)}")

# Edit/Delete
for i, m in enumerate(st.session_state.meds):
    with st.expander(f"{m['name']} @ {m['time']}  ({','.join(m['days'])})"):
        cA, cB, cC, cD = st.columns([1, 1, 1, 1])
        with cA:
            st.session_state.meds[i]["active"] = st.checkbox("Active", value=m["active"], key=f"active_{i}")
        with cB:
            new_time = st.text_input("Time", value=m["time"], key=f"time_{i}")
            if parse_time(new_time):
                st.session_state.meds[i]["time"] = new_time
        with cC:
            new_days = st.multiselect("Days", WEEKDAYS, default=m["days"], key=f"days_{i}")
            st.session_state.meds[i]["days"] = new_days
        with cD:
            rem = st.number_input("Reminder (min)", min_value=0, max_value=180, value=int(m.get("reminder_min", 10)), key=f"rem_{i}")
            st.session_state.meds[i]["reminder_min"] = int(rem)

        b1, b2 = st.columns([1,1])
        with b1:
            if st.button("Save changes", key=f"save_{i}"):
                save_json(MEDS_PATH, st.session_state.meds)
                st.success("Saved.")
        with b2:
            if st.button(f"Delete {m['name']}", key=f"del_{i}"):
                st.session_state.meds.pop(i)
                save_json(MEDS_PATH, st.session_state.meds)
                st.experimental_rerun()
