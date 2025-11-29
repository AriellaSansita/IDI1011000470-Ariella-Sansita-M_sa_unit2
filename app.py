
# app.py
import streamlit as st
import datetime as dt
import json
import csv
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
if "meds" not in st.session_state:
    # Load medicines from JSON (or start empty)
    st.session_state.meds = load_json(MEDS_PATH, default=[])

if "adherence_log" not in st.session_state:
    # Load daily taken history by date
    st.session_state.adherence_log = load_json(LOG_PATH, default={})

def today_str(now=None):
    now = now or dt.datetime.now()
    return now.date().isoformat()

# Keep "taken_today" in sync with today's log so it survives reruns
if "taken_today" not in st.session_state:
    today_key = today_str()
    taken_list = st.session_state.adherence_log.get(today_key, {}).get("taken", [])
    st.session_state.taken_today = set(taken_list)

if "tips_idx" not in st.session_state:
    st.session_state.tips_idx = 0

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

        items.append({"name": m["name"], "time": t, "status": status, "key": key})
    return sorted(items, key=lambda x: x["time"])

def record_today_log():
    """
    Persist today's scheduled count and taken list into adherence_log.json
    This lets us compute a true 7-day adherence from actual daily logs.
    """
    date_key = today_str()
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
    If the date hasn't been logged, we infer 'scheduled' from current meds, and 'taken' = 0.
    """
    dk = date_obj.isoformat()
    entry = st.session_state.adherence_log.get(dk)
    if entry:
        taken = len(entry.get("taken", []))
        scheduled = entry.get("scheduled", 0)
    else:
        # No log for that day: infer scheduled from meds for that weekday; taken=0
        scheduled = len(scheduled_keys_for_date(date_obj))
        taken = 0
    return int((taken / scheduled) * 100) if scheduled else 100

def adherence_past_7_days():
    """
    Aggregate adherence over the last 7 days using the daily log.
    If some days are missing from the log, we infer scheduled counts from meds and taken=0.
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
            # infer scheduled from meds for that weekday; taken=0
            total_sched += len(scheduled_keys_for_date(d))
    return int((total_taken / total_sched) * 100) if total_sched else 100

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
# UI
# ---------------------------------
st.title("⏰ MedTimer – Daily Medicine Companion")

# Record today’s log (scheduled count + taken list) so weekly stats are accurate
record_today_log()

col1, col2 = st.columns([2, 1])

# ---------- LEFT: Checklist ----------
with col1:
    st.subheader("Today's Checklist")
    schedule = build_today_schedule()

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
        if s["status"] != "taken":
            if st.button(f"Mark taken: {s['name']} @ {s['time'].strftime('%H:%M')}", key=s["key"]):
                st.session_state.taken_today.add(s["key"])
                record_today_log()  # persist change
                st.rerun()

# ---------- RIGHT: Weekly adherence + tips + CSV ----------
with col2:
    st.subheader("Weekly Adherence")
    weekly_score = adherence_past_7_days()
    st.progress(weekly_score / 100.0)
    st.write(f"**Score (last 7 days):** {weekly_score}%")

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

# ---------- Manage Medicines ----------
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
            save_json(MEDS_PATH, st.session_state.meds)  # persist
            st.success(f"Added {name} at {time_str}")

# Edit/Delete
for i, m in enumerate(st.session_state.meds):
    with st.expander(f"{m['name']} @ {m['time']}"):
        # Update days
        new_days = st.multiselect("Days", WEEKDAYS, default=m["days"], key=f"days_{i}")
        st.session_state.meds[i]["days"] = new_days

        # Update time (validate)
        new_time = st.text_input("Time (HH:MM)", value=m["time"], key=f"time_{i}")
        if parse_time(new_time):
            st.session_state.meds[i]["time"] = new_time

        # Save changes
        if st.button("Save changes", key=f"save_{i}"):
            save_json(MEDS_PATH, st.session_state.meds)
            st.success("Saved changes.")

        # Delete
        if st.button(f"Delete {m['name']}", key=f"del_{i}"):
            st.session_state.meds.pop(i)
            save_json(MEDS_PATH, st.session_state.meds)
            st.rerun()
