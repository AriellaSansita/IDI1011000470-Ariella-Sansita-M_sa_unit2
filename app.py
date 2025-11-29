
# app.py
import streamlit as st
import datetime as dt

# -------------------------------
# CONFIG
# -------------------------------
st.set_page_config(page_title="MedTimer", page_icon="⏰", layout="wide")

# -------------------------------
# INITIAL STATE
# -------------------------------
if "meds" not in st.session_state:
    st.session_state.meds = []  # list of dicts: {"name": str, "time": "HH:MM"}
if "taken_today" not in st.session_state:
    st.session_state.taken_today = set()
if "tips_idx" not in st.session_state:
    st.session_state.tips_idx = 0

TIPS = [
    "Stay hydrated and take meds on time.",
    "Consistency is key—same time every day.",
    "Celebrate small wins—you’re doing great!"
]

WEEKDAYS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

# -------------------------------
# HELPERS
# -------------------------------
def parse_time(tstr):
    try:
        hh, mm = map(int, tstr.split(":"))
        return dt.time(hh, mm)
    except:
        return None

def now_local():
    return dt.datetime.now()

def build_today_schedule():
    now = now_local()
    today = WEEKDAYS[now.weekday()]
    items = []
    for m in st.session_state.meds:
        if today not in m.get("days", WEEKDAYS):
            continue
        t = parse_time(m["time"])
        if not t:
            continue
        sched_dt = dt.datetime.combine(now.date(), t)
        key = f"{now.date()}|{m['name']}|{m['time']}"
        if key in st.session_state.taken_today:
            status = "taken"
        else:
            if now < sched_dt:
                status = "upcoming"
            elif now > sched_dt + dt.timedelta(minutes=60):
                status = "missed"
            else:
                status = "upcoming"
        items.append({"name": m["name"], "time": t, "status": status, "key": key})
    return sorted(items, key=lambda x: x["time"])

def adherence_score():
    sched = build_today_schedule()
    total = len(sched)
    taken = sum(1 for s in sched if s["status"] == "taken")
    return int((taken / total) * 100) if total else 100

# -------------------------------
# UI
# -------------------------------
st.title("⏰ MedTimer – Daily Medicine Companion")

# LEFT: Checklist
col1, col2 = st.columns([2,1])
with col1:
    st.subheader("Today's Checklist")
    schedule = build_today_schedule()
    for s in schedule:
        color = {"taken":"#2e7d32","upcoming":"#f9a825","missed":"#c62828"}[s["status"]]
        st.markdown(
            f"""
            <div style="border-left:8px solid {color}; padding:10px; margin:8px 0; border-radius:6px; background:#f7fbff">
              <strong>{s['name']}</strong> — {s['time'].strftime('%H:%M')}
              <span style="float:right; color:{color};"><em>{s['status'].title()}</em></span>
            </div>
            """,
            unsafe_allow_html=True
        )
        if s["status"] != "taken":
            if st.button(f"Mark taken: {s['name']}", key=s["key"]):
                st.session_state.taken_today.add(s["key"])
                st.experimental_rerun()

# RIGHT: Score + Tips
with col2:
    st.subheader("Weekly Adherence")
    score = adherence_score()
    st.progress(score/100)
    st.write(f"**Score:** {score}%")
    if score >= 80:
        st.success("🎉 Great job! (Turtle reward locally)")
    else:
        st.info("Keep going—you’ve got this!")
    st.subheader("Tip of the day")
    st.info(TIPS[st.session_state.tips_idx])
    if st.button("Next tip"):
        st.session_state.tips_idx = (st.session_state.tips_idx + 1) % len(TIPS)

st.divider()
st.header("Manage Medicines")
with st.form("add_med"):
    name = st.text_input("Medicine name", placeholder="e.g., Metformin")
    time_str = st.text_input("Time (HH:MM)", placeholder="08:00")
    days = st.multiselect("Days", WEEKDAYS, default=WEEKDAYS)
    submitted = st.form_submit_button("Add medicine")
    if submitted:
        if not name or not parse_time(time_str):
            st.error("Please enter a valid name and time.")
        else:
            st.session_state.meds.append({"name": name, "time": time_str, "days": days})
            st.success(f"Added {name} at {time_str}")

# Edit/Delete
for i, m in enumerate(st.session_state.meds):
    with st.expander(f"{m['name']} @ {m['time']}"):
        active_days = st.multiselect("Days", WEEKDAYS, default=m["days"], key=f"days_{i}")
        st.session_state.meds[i]["days"] = active_days
        if st.button(f"Delete {m['name']}", key=f"del_{i}"):
            st.session_state.meds.pop(i)
            st.experimental_rerun()
