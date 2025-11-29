# app.py (improved)
import streamlit as st
import datetime as dt
import json
import csv
import math
import wave
import struct
from pathlib import Path
from uuid import uuid4
from io import BytesIO, StringIO

# Turtle optional
try:
    import turtle
    TURTLE_AVAILABLE = True
except Exception:
    TURTLE_AVAILABLE = False

st.set_page_config(page_title="MedTimer", page_icon="⏰", layout="wide")

# -------------------------------
# THEMES
# -------------------------------
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
# PERSISTENCE
# -------------------------------
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
MEDS_PATH = DATA_DIR / "meds.json"
LOG_PATH = DATA_DIR / "adherence_log.json"
TAKEN_PATH = DATA_DIR / "taken.json"  # persist taken keys for dates

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
        # hosted env may block writes; fail silently but keep app usable
        pass

# -------------------------------
# INITIAL STATE
# -------------------------------
def init_state():
    # meds: list of dicts with stable 'id'
    meds = load_json(MEDS_PATH, default=None)
    if meds is None:
        st.session_state.meds = [
            {"id": str(uuid4()), "name": "Metformin", "time": "08:00", "days": WEEKDAYS, "active": True, "reminder_min": 10},
            {"id": str(uuid4()), "name": "Vitamin D", "time": "21:00", "days": WEEKDAYS, "active": True, "reminder_min": 10},
        ]
        save_json(MEDS_PATH, st.session_state.meds)
    else:
        st.session_state.meds = meds

    # taken_today persisted as list on disk keyed by date -> list(keys)
    raw_taken = load_json(TAKEN_PATH, default={})
    st.session_state.taken_by_date = raw_taken  # dict str(date) -> list of keys
    today = dt.date.today().isoformat()
    st.session_state.taken_today = set(st.session_state.taken_by_date.get(today, []))

    st.session_state.adherence_log = load_json(LOG_PATH, default={})
    st.session_state.tips_idx = st.session_state.get("tips_idx", 0)

init_state()

# -------------------------------
# TIPS
# -------------------------------
TIPS = [
    "Small wins count—stay hydrated and take meds on time.",
    "Set a routine: same place, same time, every day.",
    "Celebrate adherence streaks—you’re doing great!",
    "Consistency beats intensity—keep a steady rhythm.",
]

# -------------------------------
# TIME UTILITIES
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

def schedule_key(date: dt.date, med_id: str, time_str: str):
    # deterministic, safe key: date|med_id|time
    return f"{date.isoformat()}|{med_id}|{time_str}"

# -------------------------------
# SCHEDULE BUILDING & LOGGING
# -------------------------------
def build_today_schedule(meds, now=None, grace_min=60):
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
        key = schedule_key(now.date(), m["id"], m["time"])
        if key in st.session_state.taken_today:
            status = "taken"
        else:
            grace = dt.timedelta(minutes=grace_min)
            if now < sdt:
                status = "upcoming"
            elif now > sdt + grace:
                status = "missed"
            else:
                # within grace window -> upcoming (can still mark taken)
                status = "upcoming"
        items.append({
            "id": m["id"],
            "name": m["name"],
            "time": t,
            "time_str": m["time"],
            "status": status,
            "key": key,
            "reminder_min": int(m.get("reminder_min", 10)),
            "scheduled_dt": sdt
        })
    items.sort(key=lambda x: x["time"])
    return items

def record_daily_log(now=None):
    now = now or now_local()
    date_key = now.date().isoformat()
    sched = build_today_schedule(st.session_state.meds, now)
    scheduled_count = len(sched)
    taken_list = list(st.session_state.taken_today)
    # Persist both adherence log and taken_by_date
    st.session_state.adherence_log[date_key] = {"taken": taken_list, "scheduled": scheduled_count}
    save_json(LOG_PATH, st.session_state.adherence_log)
    # persist taken_by_date structure too
    st.session_state.taken_by_date[date_key] = taken_list
    save_json(TAKEN_PATH, st.session_state.taken_by_date)

def adherence_for_date(date: dt.date):
    entry = st.session_state.adherence_log.get(date.isoformat())
    if entry is not None:
        taken = len(entry.get("taken", []))
        scheduled = entry.get("scheduled", 0)
        return int((taken / scheduled) * 100) if scheduled else 100
    # best-effort compute scheduled (no log) and check taken_by_date
    date_key = date.isoformat()
    scheduled = len(build_today_schedule(st.session_state.meds, dt.datetime.combine(date, dt.datetime.min.time())))
    taken = len(st.session_state.taken_by_date.get(date_key, []))
    return int((taken / scheduled) * 100) if scheduled else 100

def adherence_past_7_days(now=None):
    now = now or now_local()
    total_taken, total_sched = 0, 0
    for i in range(7):
        d = now.date() - dt.timedelta(days=i)
        date_key = d.isoformat()
        entry = st.session_state.adherence_log.get(date_key)
        if entry:
            total_taken += len(entry.get("taken", []))
            total_sched += entry.get("scheduled", 0)
        else:
            # no logged entry - approximate using schedule + recorded taken_by_date
            scheduled = len(build_today_schedule(st.session_state.meds, dt.datetime.combine(d, dt.datetime.min.time())))
            total_sched += scheduled
            total_taken += len(st.session_state.taken_by_date.get(date_key, []))
    return int((total_taken / total_sched) * 100) if total_sched else 100

def current_streak(now=None, threshold=80):
    now = now or now_local()
    streak = 0
    for i in range(30):
        d = now.date() - dt.timedelta(days=i)
        if adherence_for_date(d) >= threshold:
            streak += 1
        else:
            break
    return streak

# -------------------------------
# AUDIO BEEP
# -------------------------------
def make_beep(duration_sec=0.5, freq_hz=880, sr=44100, volume=0.4):
    n_samples = int(sr * duration_sec)
    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        for i in range(n_samples):
            t = i / sr
            sample = int(32767 * volume * math.sin(2 * math.pi * freq_hz * t))
            wf.writeframes(struct.pack('<h', sample))
    buf.seek(0)
    return buf.read()

# -------------------------------
# TURTLE (unchanged)
# -------------------------------
def draw_turtle_reward(score):
    if not TURTLE_AVAILABLE:
        st.warning("Turtle module not available in this environment.")
        return
    wn = turtle.Screen()
    wn.title(f"MedTimer Reward — Adherence {score}%")
    t = turtle.Turtle()
    t.speed(0)
    if score >= 90:
        t.color("gold"); t.pensize(5)
        t.penup(); t.goto(-50, -100); t.pendown()
        for _ in range(2):
            t.forward(100); t.left(90); t.forward(20); t.left(90)
        t.penup(); t.goto(0, -80); t.pendown()
        t.left(90); t.forward(80); t.right(90)
        t.circle(50)
    elif score >= 80:
        t.color("green"); t.pensize(4)
        t.penup(); t.goto(0, -50); t.pendown()
        t.circle(80)
        for x in (-30, 30):
            t.penup(); t.goto(x, 40); t.pendown()
            t.circle(10)
        t.penup(); t.goto(-40, 10); t.setheading(-60); t.pendown()
        for _ in range(60):
            t.forward(2); t.left(2)
    else:
        t.color("red"); t.penup(); t.goto(-100, 0); t.pendown()
        t.write("You’ve got this!\nTry setting reminders.", font=("Arial", 16, "normal"))
    turtle.done()

# -------------------------------
# CSV REPORT
# -------------------------------
def weekly_csv_bytes(now=None):
    now = now or now_local()
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
# UTILITY: persist taken_today to disk
# -------------------------------
def save_taken_today():
    date_key = dt.date.today().isoformat()
    st.session_state.taken_by_date[date_key] = list(st.session_state.taken_today)
    save_json(TAKEN_PATH, st.session_state.taken_by_date)
    # also update adherence log for today
    record_daily_log()

# -------------------------------
# UI
# -------------------------------
st.markdown('<div class="big-title">⏰ MedTimer – Daily Medicine Companion</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("Accessibility")
    st.session_state.theme = st.radio("Theme", list(THEMES.keys()), index=list(THEMES.keys()).index(st.session_state.theme))
    inject_css()
    st.caption("Toggle light / dark / high-contrast for readability.")

left, right = st.columns([2,1])

with left:
    st.subheader("Today's Checklist")
    now = now_local()
    schedule = build_today_schedule(st.session_state.meds, now)

    # upcoming reminders
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
                # unique button key uses med id + date
                btn_key = f"mark_{s['key']}"
                if st.button("Mark taken", key=btn_key):
                    st.session_state.taken_today.add(s["key"])
                    save_taken_today()
                    st.experimental_rerun()
        with c2:
            st.caption(f"Reminder: {s['reminder_min']} min before")

with right:
    st.subheader("Weekly Adherence")
    record_daily_log(now)
    score7 = adherence_past_7_days(now)
    st.progress(score7 / 100.0)
    st.write(f"**Score:** {score7}%")
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
    st.info(f"Current streak: **{current_streak(now, threshold=80)}** day(s)")

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
            new_med = {"id": str(uuid4()), "name": name, "time": time_str, "days": days, "active": True, "reminder_min": int(reminder_min)}
            st.session_state.meds.append(new_med)
            save_json(MEDS_PATH, st.session_state.meds)
            st.success(f"Added {name} at {time_str} on {', '.join(days)}")
            st.experimental_rerun()

# Edit/Delete medicines
for i, m in enumerate(list(st.session_state.meds)):
    with st.expander(f"{m['name']} @ {m['time']}  ({','.join(m['days'])})"):
        cA, cB, cC, cD = st.columns([1, 1, 1, 1])
        with cA:
            active = st.checkbox("Active", value=m["active"], key=f"active_{m['id']}")
            st.session_state.meds[i]["active"] = active
        with cB:
            new_time = st.text_input("Time", value=m["time"], key=f"time_{m['id']}")
            if parse_time(new_time):
                st.session_state.meds[i]["time"] = new_time
        with cC:
            new_days = st.multiselect("Days", WEEKDAYS, default=m["days"], key=f"days_{m['id']}")
            st.session_state.meds[i]["days"] = new_days
        with cD:
            rem = st.number_input("Reminder (min)", min_value=0, max_value=180, value=int(m.get("reminder_min", 10)), key=f"rem_{m['id']}")
            st.session_state.meds[i]["reminder_min"] = int(rem)

        b1, b2 = st.columns([1,1])
        with b1:
            if st.button("Save changes", key=f"save_{m['id']}"):
                save_json(MEDS_PATH, st.session_state.meds)
                st.success("Saved.")
        with b2:
            if st.button(f"Delete {m['name']}", key=f"del_{m['id']}"):
                # remove all future/past taken keys for this med id
                med_id = m["id"]
                # filter meds
                st.session_state.meds = [x for x in st.session_state.meds if x["id"] != med_id]
                # remove keys from taken_by_date
                for date_key, lst in list(st.session_state.taken_by_date.items()):
                    new_list = [k for k in lst if f"|{med_id}|" not in k]
                    if new_list:
                        st.session_state.taken_by_date[date_key] = new_list
                    else:
                        st.session_state.taken_by_date.pop(date_key, None)
                save_json(MEDS_PATH, st.session_state.meds)
                save_json(TAKEN_PATH, st.session_state.taken_by_date)
                st.experimental_rerun()

