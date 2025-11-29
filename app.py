
# app.py
import streamlit as st
import datetime as dt
import json
import csv
import math
import wave
import struct
from pathlib import Path

# ---------------------------------
# CONFIG
# ---------------------------------
st.set_page_config(page_title="MedTimer", page_icon="⏰", layout="wide")

# ---------------------------------
# FILE PERSISTENCE
# ---------------------------------
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
MEDS_PATH = DATA_DIR / "meds.json"
LOG_PATH  = DATA_DIR / "adherence_log.json"  # { "YYYY-MM-DD": {"taken":[keys], "scheduled": int} }

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

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
        # On some hosted environments, writes may be ephemeral—ignore errors
        pass

# ---------------------------------
# STATE INIT
# ---------------------------------
# Load medicines
if "meds" not in st.session_state:
    st.session_state.meds = load_json(MEDS_PATH, default=[])

# Load adherence log
if "adherence_log" not in st.session_state:
    st.session_state.adherence_log = load_json(LOG_PATH, default={})

def today_str(now=None):
    now = now or dt.datetime.now()
    return now.date().isoformat()

# Track current date to auto-reset daily
if "current_date" not in st.session_state:
    st.session_state.current_date = today_str()

# Initialize taken_today from today's log (or empty)
if "taken_today" not in st.session_state:
    today_key = today_str()
    taken_list = st.session_state.adherence_log.get(today_key, {}).get("taken", [])
    st.session_state.taken_today = set(taken_list)

if "tips_idx" not in st.session_state:
    st.session_state.tips_idx = 0

# Global reminder window (minutes) for audio alerts
if "reminder_window_min" not in st.session_state:
    st.session_state.reminder_window_min = 10

TIPS = [
    "Stay hydrated and take meds on time.",
    "Consistency is key—same time every day.",
    "Celebrate small wins—you’re doing great!",
]

# ---------------------------------
# HELPERS
# ---------------------------------
def parse_time(tstr: str):
    """Return datetime.time from 'HH:MM' or None if invalid."""
    try:
        hh, mm = map(int, tstr.strip().split(":"))
        return dt.time(hh, mm)
    except Exception:
        return None

def weekday_name(date_obj: dt.date):
    return WEEKDAYS[date_obj.weekday()]

def schedule_key(date_obj: dt.date, name: str, time_str: str):
    return f"{date_obj.isoformat()}|{name}|{time_str}"

def scheduled_keys_for_date(date_obj: dt.date):
    """Return all scheduled dose keys for a given date based on current meds list."""
    wname = weekday_name(date_obj)
    keys = []
    for m in st.session_state.meds:
        days = m.get("days", WEEKDAYS)
        if wname not in days:
            continue
        t = parse_time(m.get("time",""))
        if not t:
            continue
        keys.append(schedule_key(date_obj, m["name"], m["time"]))
    return keys

def build_today_schedule(grace_minutes: int = 60):
    """
    Build today's schedule with live statuses:
      - upcoming: now < scheduled_dt (or within grace window)
      - taken: key in taken_today
      - missed: now > scheduled_dt + grace and not taken
    """
    now = dt.datetime.now()
    date_obj = now.date()
    items = []
    for m in st.session_state.meds:
        if weekday_name(date_obj) not in m.get("days", WEEKDAYS):
            continue
        t = parse_time(m.get("time",""))
        if not t:
            continue

        sched_dt = dt.datetime.combine(date_obj, t)
        key = schedule_key(date_obj, m["name"], m["time"])

        if key in st.session_state.taken_today:
            status = "taken"
        else:
            grace = dt.timedelta(minutes=grace_minutes)
            if now < sched_dt:
                status = "upcoming"
            elif now > sched_dt + grace:
                status = "missed"
            else:
                status = "upcoming"

        items.append({"name": m["name"], "time": t, "status": status, "key": key, "scheduled_dt": sched_dt})
    return sorted(items, key=lambda x: x["time"])

def record_today_log():
    """
    Persist today's scheduled count and taken list into adherence_log.json
    This lets us compute a true 7-day adherence from actual daily logs.
    """
    now = dt.datetime.now()
    date_key = now.date().isoformat()
    sched = build_today_schedule()
    taken = list(st.session_state.taken_today)
    st.session_state.adherence_log[date_key] = {
        "taken": taken,
        "scheduled": len(sched)
    }
    save_json(LOG_PATH, st.session_state.adherence_log)

def adherence_for_date(date_obj: dt.date):
    """
    True adherence for a given date: taken / scheduled * 100
    If the date hasn't been logged, infer 'scheduled' from meds, 'taken' = 0.
    """
    dk = date_obj.isoformat()
    entry = st.session_state.adherence_log.get(dk)
    if entry:
        taken = len(entry.get("taken", []))
        scheduled = entry.get("scheduled", 0)
    else:
        scheduled = len(scheduled_keys_for_date(date_obj))
        taken = 0
    return int((taken / scheduled) * 100) if scheduled else 100

def adherence_past_7_days():
    """
    Aggregate adherence over the last 7 days using the daily log.
    If some days are missing, infer scheduled from meds and taken=0.
    """
    now = dt.datetime.now()
    total_taken = 0
    total_sched = 0
    for i in range(7):
        d = (now.date() - dt.timedelta(days=i))
        dk = d.isoformat()
        entry = st.session_state.adherence_log.get(dk)
        if entry:
            total_taken += len(entry.get("taken", []))
            total_sched += entry.get("scheduled", 0)
        else:
            total_sched += len(scheduled_keys_for_date(d))
    return int((total_taken / total_sched) * 100) if total_sched else 100

def current_streak(threshold: int = 80, lookback_days: int = 30):
    """
    Count consecutive past days with adherence >= threshold.
    """
    now = dt.datetime.now()
    streak = 0
    for i in range(lookback_days):
        d = now.date() - dt.timedelta(days=i)
        if adherence_for_date(d) >= threshold:
            streak += 1
        else:
            break
    return streak

def weekly_csv_bytes():
    """
    Build a CSV (in-memory) for last 7 days: Date, Scheduled, Taken, Adherence%
    """
    now = dt.datetime.now()
    from io import StringIO
    sio = StringIO()
    writer = csv.writer(sio)
    writer.writerow(["Date", "Scheduled", "Taken", "Adherence%"])
    for i in range(6, -1, -1):
        d = now.date() - dt.timedelta(days=i)
        dk = d.isoformat()
        entry = st.session_state.adherence_log.get(dk, {})
        scheduled = entry.get("scheduled", len(scheduled_keys_for_date(d)))  # infer if missing
        taken = len(entry.get("taken", []))
        adh = int((taken / scheduled) * 100) if scheduled else 100
        writer.writerow([dk, scheduled, taken, adh])
    return sio.getvalue().encode("utf-8")

# ---------------------------------
# AUDIO REMINDER (stdlib WAV)
# ---------------------------------
def make_beep(duration_sec=0.6, freq_hz=880, sr=44100, volume=0.4):
    """
    Create a simple WAV beep (in-memory) using standard library only.
    """
    n_samples = int(sr * duration_sec)
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

# ---------------------------------
# DAILY AUTO-RESET
# ---------------------------------
def daily_auto_reset():
    today = today_str()
    if st.session_state.current_date != today:
        # Date changed: clear taken_today and start fresh
        st.session_state.current_date = today
        st.session_state.taken_today = set()
        record_today_log()  # initialize today's log entry

# Run auto-reset check
daily_auto_reset()

# Record today's log (keeps scheduled count updated)
record_today_log()

# ---------------------------------
# UI
# ---------------------------------
st.title("⏰ MedTimer – Daily Medicine Companion")

# Sidebar controls
with st.sidebar:
    st.header("Reminders & Legend")
    st.session_state.reminder_window_min = st.number_input(
        "Reminder window (minutes before time)",
        min_value=0, max_value=180, value=st.session_state.reminder_window_min, step=5
    )
    st.markdown("**Color Legend**")
    st.markdown("🟢 **Green** = Taken  \n🟡 **Yellow** = Upcoming  \n🔴 **Red** = Missed")

# Layout columns
col1, col2 = st.columns([2, 1])

# ---------- LEFT: Checklist ----------
with col1:
    st.subheader("Today's Checklist")

    if not st.session_state.meds:
        st.info("No medicines added yet. Use **Manage Medicines** below to add your first medicine (name, time, days).")
    schedule = build_today_schedule()

    # Audio reminder: show upcoming within global window; offer 'Play Reminder'
    now = dt.datetime.now()
    upcoming_due = []
    for s in schedule:
        minutes_to = int((s["scheduled_dt"] - now).total_seconds() // 60)
        if 0 <= minutes_to <= st.session_state.reminder_window_min and s["status"] != "taken":
            upcoming_due.append((s["name"], minutes_to))

    if upcoming_due:
        st.warning("Upcoming doses soon:")
        for name, mins in upcoming_due:
            st.write(f"• **{name}** in **{mins} min**")
        if st.button("🔔 Play Reminder"):
            st.audio(make_beep(), format="audio/wav")

    for s in schedule:
        color = {"taken": "#2e7d32", "upcoming": "#f9a825", "missed": "#c62828"}[s["status"]]
        st.markdown(
            f"""
            <div style="border-left:8px solid {color}; padding:10px; margin:8px 0;
                        border-radius:6px; background:#f7fbff">
              <strong>{s['name']}</strong> — {s['time'].strftime('%H:%M')}
              <span style="float:right; color:{color};"><em>{s['status'].title()}</em></span>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Missed dose warning
        if s["status"] == "missed":
            st.warning("You missed this dose!")

        # Mark taken button
        if s["status"] != "taken":
            if st.button(f"Mark taken: {s['name']} @ {s['time'].strftime('%H:%M')}", key=s["key"]):
                st.session_state.taken_today.add(s["key"])
                record_today_log()
                st.rerun()

# ---------- RIGHT: Weekly adherence + tips + CSV + streak ----------
with col2:
    st.subheader("Weekly Adherence")
    weekly_score = adherence_past_7_days()
    st.progress(weekly_score / 100.0)
    st.write(f"**Score (last 7 days):** {weekly_score}%")

    st.subheader("Adherence Streak")
    streak = current_streak(threshold=80, lookback_days=30)
    st.info(f"Current streak: **{streak} day(s)** (≥ 80%)")

    st.subheader("Tip of the day")
    st.info(TIPS[st.session_state.tips_idx])
    if st.button("Next tip"):
        st.session_state.tips_idx = (st.session_state.tips_idx + 1) % len(TIPS)

    st.subheader("Weekly Report")
    st.download_button(
        "⬇️ Download CSV",
        data=weekly_csv_bytes(),
        file_name="medtimer_weekly_report.csv",
        mime="text/csv"
    )

st.divider()
st.header("Manage Medicines")

with st.form("add_med"):
    name = st.text_input("Medicine name", placeholder="e.g., Metformin")
    time_str = st.text_input("Time (24h HH:MM)", placeholder="08:00")
    days = st.multiselect("Days", WEEKDAYS, default=WEEKDAYS)
    submitted = st.form_submit_button("Add medicine")
    if submitted:
        t = parse_time(time_str)
        if not name or not t:
            st.error("Please enter a valid name and time (HH:MM).")
        else:
            st.session_state.meds.append({"name": name.strip(), "time": time_str.strip(), "days": days})
            save_json(MEDS_PATH, st.session_state.meds)
            st.success(f"Added {name} at {time_str}")

# Edit/Delete with confirmation & editable name
for i, m in enumerate(st.session_state.meds):
    with st.expander(f"{m['name']} @ {m['time']}"):
        # Editable name
        new_name = st.text_input("Medicine name", value=m["name"], key=f"name_{i}")
        st.session_state.meds[i]["name"] = new_name.strip()

        # Update time (validate)
        new_time = st.text_input("Time (24h HH:MM)", value=m["time"], key=f"time_{i}")
        if parse_time(new_time):
            st.session_state.meds[i]["time"] = new_time.strip()
        else:
            st.warning("Invalid time format. Keep HH:MM (24h).")

        # Update days
        new_days = st.multiselect("Days", WEEKDAYS, default=m["days"], key=f"days_{i}")
        st.session_state.meds[i]["days"] = new_days

        # Save changes
        if st.button("Save changes", key=f"save_{i}"):
            save_json(MEDS_PATH, st.session_state.meds)
            st.success("Saved changes.")

        # Delete with confirmation
        confirm = st.checkbox("Confirm delete", key=f"confirm_{i}")
        if st.button(f"Delete {m['name']}", key=f"del_{i}"):
            if confirm:
                st.session_state.meds.pop(i)
                save_json(MEDS_PATH, st.session_state.meds)
                st.rerun()
            else:
                st.warning("Please tick 'Confirm delete' before deleting.")
