import streamlit as st
import datetime as dt
from datetime import datetime
from io import BytesIO
import math, wave, struct

# ================= PAGE CONFIG =================
st.set_page_config("MedTimer", "💊", layout="wide")

# ================= SESSION STATE =================
if "meds" not in st.session_state or not isinstance(st.session_state.meds, dict):
    st.session_state.meds = {}

if "history" not in st.session_state:
    st.session_state.history = []

if "streak" not in st.session_state:
    st.session_state.streak = 0

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ================= HELPERS =================
def today():
    return dt.date.today()

def now():
    return dt.datetime.now()

def parse_time_str(s: str) -> dt.time:
    try:
        hh, mm = map(int, s.split(":"))
        return dt.time(hh, mm)
    except:
        return now().time().replace(second=0, microsecond=0)

def get_history_entry(name, dose_time, date):
    for h in st.session_state.history:
        if h["date"] == date and h["name"] == name and h["dose_time"] == dose_time:
            return h
    return None

def ensure_history_entry(name, dose_time, date):
    if not get_history_entry(name, dose_time, date):
        st.session_state.history.append({
            "date": date,
            "name": name,
            "dose_time": dose_time,
            "taken": False
        })

def set_taken(name, dose_time, date, val):
    h = get_history_entry(name, dose_time, date)
    if h:
        h["taken"] = bool(val)
    else:
        st.session_state.history.append({
            "date": date,
            "name": name,
            "dose_time": dose_time,
            "taken": bool(val)
        })

def get_taken(name, dose_time, date):
    h = get_history_entry(name, dose_time, date)
    return bool(h["taken"]) if h else False

# ================= ✅ FIXED TIME LOGIC =================
def status_for_dose(dose_time_str, taken, now_dt):
    if taken:
        return "taken"

    med_time = parse_time_str(dose_time_str)
    current_time = now_dt.time().replace(second=0, microsecond=0)

    if med_time > current_time:
        return "upcoming"
    else:
        return "missed"

def adherence_score(history, days=7):
    if not history:
        return 0.0
    cutoff = today() - dt.timedelta(days=days - 1)
    recent = [h for h in history if h["date"] >= cutoff]
    if not recent:
        return 0.0
    taken = sum(1 for h in recent if h["taken"])
    return round(100 * taken / len(recent), 1)

def update_streak(history):
    streak = 0
    d = today()
    while True:
        day_entries = [h for h in history if h["date"] == d]
        if not day_entries:
            break
        if all(h["taken"] for h in day_entries):
            streak += 1
            d -= dt.timedelta(days=1)
        else:
            break
    return streak

# ================= UI =================
st.title("MedTimer")

col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    st.markdown("### Today")
with col2:
    st.metric("7-Day Adherence", f"{adherence_score(st.session_state.history)}%")
with col3:
    st.metric("Perfect Streak", f"{update_streak(st.session_state.history)} days")

# ================= TODAY'S CHECKLIST =================
st.header("Today's Checklist")

today_date = today()
now_dt = now()
weekday = WEEKDAYS[today_date.weekday()]

if st.session_state.meds:
    for name, info in st.session_state.meds.items():
        if weekday not in info.get("days", WEEKDAYS):
            continue

        st.write(f"**{name}** — {info.get('note') or 'No note'}")

        for dose in sorted(info.get("doses", []), key=parse_time_str):
            ensure_history_entry(name, dose, today_date)

            taken = get_taken(name, dose, today_date)
            status = status_for_dose(dose, taken, now_dt)

            c1, c2, c3 = st.columns([2.2, 1.2, 1.2])
            with c1:
                st.write(f"⏰ {dose}")
            with c2:
                if status == "taken":
                    st.success("Taken")
                elif status == "upcoming":
                    st.warning("Upcoming")
                else:
                    st.error("Missed")
            with c3:
                key = f"{name}_{dose}_{taken}"
                if taken:
                    if st.button("Undo", key=key):
                        set_taken(name, dose, today_date, False)
                        st.rerun()
                else:
                    if st.button("Mark taken", key=key):
                        set_taken(name, dose, today_date, True)
                        st.rerun()
        st.divider()
else:
    st.info("No medicines yet. Use Add section below.")

# ================= ADD MEDICINES =================
st.header("Add Medicine")

name = st.text_input("Medicine name")
note = st.text_input("Note")
freq = st.number_input("Times per day", 1, 10, 1)

times = []
for i in range(freq):
    tm = st.time_input(
        f"Dose {i+1}",
        value=datetime.strptime("08:00", "%H:%M").time(),
        key=f"time_{i}"
    )
    times.append(tm.strftime("%H:%M"))

days = []
cols = st.columns(7)
for i, d in enumerate(WEEKDAYS):
    if cols[i].checkbox(d, True, key=f"day_{d}"):
        days.append(d)

if st.button("Add"):
    if name.strip():
        st.session_state.meds[name] = {
            "doses": times,
            "note": note,
            "days": days or WEEKDAYS
        }
        st.success("Medicine added")
        st.rerun()
    else:
        st.warning("Enter a medicine name")

# ================= FOOTER =================
st.markdown("---")
st.info("💙 Small habits today build a healthier tomorrow.")
