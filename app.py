import streamlit as st
import datetime as dt
import json
import csv
from pathlib import Path
from uuid import uuid4

st.set_page_config(page_title="MedTimer", page_icon="⏰", layout="wide")

# ---------------- FILE STORAGE ----------------
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

MEDS_FILE = DATA_DIR / "meds.json"
LOG_FILE = DATA_DIR / "log.json"
TAKEN_FILE = DATA_DIR / "taken.json"

WEEKDAYS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

# ---------------- HELPERS ----------------
def load(path, default):
    if path.exists():
        return json.loads(path.read_text())
    return default

def save(path, data):
    path.write_text(json.dumps(data, indent=2))

def parse_time(t):
    try:
        return dt.datetime.strptime(t, "%H:%M").time()
    except:
        return None

def now():
    return dt.datetime.now()

def weekday(now):
    return WEEKDAYS[now.weekday()]

# ---------------- INITIAL DATA ----------------
if "meds" not in st.session_state:
    st.session_state.meds = load(MEDS_FILE, [])

if "taken_log" not in st.session_state:
    st.session_state.taken_log = load(TAKEN_FILE, {})

if "daily_log" not in st.session_state:
    st.session_state.daily_log = load(LOG_FILE, {})

TODAY = dt.date.today().isoformat()
taken_today = set(st.session_state.taken_log.get(TODAY, []))

# ---------------- BUILD TODAY SCHEDULE ----------------
def today_schedule():
    result = []
    now_time = now()
    for m in st.session_state.meds:
        if weekday(now_time) not in m["days"]:
            continue

        med_time = parse_time(m["time"])
        scheduled = dt.datetime.combine(now_time.date(), med_time)
        key = f"{TODAY}-{m['id']}"

        if key in taken_today:
            status = "taken"
        elif now_time < scheduled:
            status = "upcoming"
        else:
            status = "missed"

        result.append({
            "id": m["id"], "name": m["name"], "time": m["time"],
            "status": status, "key": key
        })
    return sorted(result, key=lambda x: x["time"])

# ---------------- ADHERENCE ----------------
def record_day():
    sched = today_schedule()
    st.session_state.daily_log[TODAY] = {
        "taken": list(taken_today),
        "scheduled": len(sched)
    }
    save(LOG_FILE, st.session_state.daily_log)

def weekly_adherence():
    total_taken = 0
    total_sched = 0
    for i in range(7):
        d = (dt.date.today() - dt.timedelta(days=i)).isoformat()
        if d in st.session_state.daily_log:
            entry = st.session_state.daily_log[d]
            total_taken += len(entry["taken"])
            total_sched += entry["scheduled"]
    if total_sched == 0:
        return 100
    return int((total_taken / total_sched) * 100)

# ---------------- UI HEADER ----------------
st.title("⏰ MedTimer – Daily Medicine Companion")
st.caption("Track your daily medicines easily and safely.")

# ---------------- CHECKLIST ----------------
st.subheader("Today's Medicines")

schedule = today_schedule()

for med in schedule:
    color = {"taken":"🟢", "upcoming":"🟡", "missed":"🔴"}[med["status"]]
    st.write(f"{color} **{med['name']}** at {med['time']} → {med['status'].upper()}")

    if med["status"] != "taken":
        if st.button(f"Mark {med['name']} taken", key=med["key"]):
            taken_today.add(med["key"])
            st.session_state.taken_log[TODAY] = list(taken_today)
            save(TAKEN_FILE, st.session_state.taken_log)
            record_day()
            st.rerun()

# ---------------- ADHERENCE PANEL ----------------
st.divider()
st.subheader("📊 Weekly Adherence")
score = weekly_adherence()
st.progress(score / 100)
st.write(f"**Adherence: {score}%**")

if score >= 80:
    st.success("Great job staying consistent!")
else:
    st.warning("Try to stay on track tomorrow!")

# ---------------- TIP ----------------
TIPS = [
    "Stay hydrated.",
    "Set alarms for medicine time.",
    "Keep medicines in a visible place.",
    "Never skip doses."
]
st.info(TIPS[dt.date.today().weekday() % 4])

# ---------------- CSV REPORT ----------------
def csv_bytes():
    output = []
    output.append(["Date","Scheduled","Taken"])
    for d, v in st.session_state.daily_log.items():
        output.append([d, v["scheduled"], len(v["taken"])])

    text = "\n".join([",".join(map(str,row)) for row in output])
    return text.encode("utf-8")

st.download_button("⬇ Download Weekly Report", csv_bytes(), file_name="medtimer_report.csv")

# ---------------- ADD MEDICINE FORM ----------------
st.divider()
st.subheader("Add New Medicine")

with st.form("add_med"):
    name = st.text_input("Medicine Name")
    time_str = st.text_input("Time (HH:MM)")
    days = st.multiselect("Days", WEEKDAYS, default=WEEKDAYS)
    submit = st.form_submit_button("Add")

    if submit:
        if not name or not parse_time(time_str):
            st.error("Invalid name or time.")
        else:
            st.session_state.meds.append({
                "id": str(uuid4()),
                "name": name,
                "time": time_str,
                "days": days
            })
            save(MEDS_FILE, st.session_state.meds)
            st.success("Medicine added!")
            st.rerun()

# ---------------- EDIT / DELETE ----------------
st.divider()
st.subheader("Manage Medicines")

for med in list(st.session_state.meds):
    with st.expander(f"{med['name']} at {med['time']}"):
        new_time = st.text_input("Edit Time", med["time"], key=med["id"])
        new_days = st.multiselect("Edit Days", WEEKDAYS, med["days"], key=med["id"]+"d")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Save", key=med["id"]+"s"):
                med["time"] = new_time
                med["days"] = new_days
                save(MEDS_FILE, st.session_state.meds)
                st.success("Updated!")
                st.rerun()

        with col2:
            if st.button("Delete", key=med["id"]+"x"):
                st.session_state.meds.remove(med)
                save(MEDS_FILE, st.session_state.meds)
                st.warning("Deleted.")
                st.rerun()
