
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
    # Each item: {"name": str, "time": "HH:MM", "days": ["Mon", ...]}
    st.session_state.meds = []

if "taken_today" not in st.session_state:
    # Store taken keys: "YYYY-MM-DD|name|HH:MM"
    st.session_state.taken_today = set()

if "tips_idx" not in st.session_state:
    st.session_state.tips_idx = 0

TIPS = [
    "Stay hydrated and take meds on time.",
    "Consistency is key—same time every day.",
    "Celebrate small wins—you’re doing great!"
]
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# -------------------------------
# HELPERS
# -------------------------------
def parse_time(tstr: str):
    """Return datetime.time from 'HH:MM' or None if invalid."""
    try:
        hh, mm = map(int, tstr.strip().split(":"))
        return dt.time(hh, mm)
    except Exception:
        return None

def now_local() -> dt.datetime:
    return dt.datetime.now()

def build_today_schedule(grace_minutes: int = 60):
    """
    Build today's schedule with status:
    - upcoming: now < scheduled_dt (or within grace)
    - taken: key in taken_today
    - missed: now > scheduled_dt + grace and not taken
    """
    now = now_local()
    today_name = WEEKDAYS[now.weekday()]
    items = []
    for m in st.session_state.meds:
        days = m.get("days", WEEKDAYS)
        if today_name not in days:
            continue

        t = parse_time(m.get("time", ""))
        if not t:
            # Skip invalid time entries silently
            continue

        sched_dt = dt.datetime.combine(now.date(), t)
        key = f"{now.date()}|{m['name']}|{m['time']}"

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

    # Sort by time ascending
    return sorted(items, key=lambda x: x["time"])

def adherence_score():
    """
    Basic adherence score using today's schedule:
    taken / scheduled * 100 (if no scheduled, show 100%)
    """
    sched = build_today_schedule()
    total = len(sched)
    taken = sum(1 for s in sched if s["status"] == "taken")
    return int((taken / total) * 100) if total else 100

# -------------------------------
# UI
# -------------------------------
st.title("⏰ MedTimer – Daily Medicine Companion")

# Layout columns
col1, col2 = st.columns([2, 1])

# ---------- LEFT: Checklist ----------
with col1:
    st.subheader("Today's Checklist")
    schedule = build_today_schedule()

    for s in schedule:
        color = {
            "taken": "#2e7d32",   # green
            "upcoming": "#f9a825",# yellow
            "missed": "#c62828"   # red
        }[s["status"]]

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

        # Unique button key (already unique via s["key"])
        if s["status"] != "taken":
            if st.button(f"Mark taken: {s['name']} @ {s['time'].strftime('%H:%M')}", key=s["key"]):
                st.session_state.taken_today.add(s["key"])
                # Stable rerun API
                st.rerun()

# ---------- RIGHT: Score + Tips ----------
with col2:
    st.subheader("Weekly Adherence")
    score = adherence_score()
    st.progress(score/100)
    st.write(f"**Score:** {score}%")

    # Encouragement (emoji fallback; Turtle graphics are best run locally)
    if score >= 80:
        st.success("🎉 Great job!")
    else:
        st.info("Keep going—you’ve got this!")

    st.subheader("Tip of the day")
    st.info(TIPS[st.session_state.tips_idx])
    if st.button("Next tip"):
        st.session_state.tips_idx = (st.session_state.tips_idx + 1) % len(TIPS)

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

        # Delete
        if st.button(f"Delete {m['name']}", key=f"del_{i}"):
            st.session_state.meds.pop(i)
            st.rerun()
