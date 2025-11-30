# app.py
import streamlit as st
import datetime as dt
import random
import math
import struct

# Optional: Turtle graphics (local desktop only)
try:
    import turtle
    TURTLE_AVAILABLE = True
except Exception:
    TURTLE_AVAILABLE = False


# ------------------------------
# App config & styling
# ------------------------------
st.set_page_config(page_title="MedTimer Companion", page_icon="💊", layout="wide")

st.markdown("""
<style>
    html, body, [class*="css"] {
        font-size: 18px;
        background-color: #F0F8FF; /* soft blue */
        color: #004d40; /* teal-green */
    }
    h1, h2, h3 {
        color: #00695C; /* deep green */
    }
    .stButton>button {
        background-color: #4CAF50; /* green */
        color: white;
        font-size: 16px;
        border-radius: 8px;
        padding: 0.45rem 0.9rem;
        border: none;
    }
    .pill {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 999px;
        font-weight: 600;
        color: white;
        margin-left: 8px;
    }
    .pill-green { background: #2E7D32; }
    .pill-yellow { background: #FBC02D; color: #1a1a1a; }
    .pill-red { background: #D32F2F; }
    .card {
        background: #ffffff;
        border: 1px solid #cfe8ff;
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)


# ------------------------------
# Reference lists
# ------------------------------
COMMON_MEDICINES = sorted([
    "Aspirin", "Amoxicillin", "Azithromycin", "Atorvastatin", "Acetaminophen", "Albuterol",
    "Ibuprofen", "Insulin", "Indomethacin", "Ivermectin", "Iron Supplement",
    "Levothyroxine", "Lisinopril", "Losartan", "Metformin", "Montelukast",
    "Omeprazole", "Ondansetron", "Paracetamol", "Pantoprazole", "Prednisone",
    "Sertraline", "Simvastatin", "Tramadol", "Tamsulosin", "Vitamin D", "Warfarin"
])

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

QUOTES = [
    "Every dose taken is a step toward wellness.",
    "Consistency builds strength.",
    "You're doing great—keep it up!",
    "Health is the real wealth.",
    "Small steps lead to big changes.",
    "Your effort today shapes your tomorrow.",
    "Peace of mind starts with care.",
    "One dose at a time, you're healing.",
    "Celebrate every dose taken!",
]


# ------------------------------
# Session state
# ------------------------------
if "schedules" not in st.session_state:
    # Each schedule: {name, days_of_week: [str], times: [time], start_date: date}
    st.session_state.schedules = []
if "taken_events" not in st.session_state:
    # Set of keys "YYYY-MM-DD|Name|HH:MM"
    st.session_state.taken_events = set()
if "reminder_minutes" not in st.session_state:
    st.session_state.reminder_minutes = 15
if "trigger_rerun" not in st.session_state:
    st.session_state.trigger_rerun = False


# ------------------------------
# Turtle graphics
# ------------------------------
def draw_trophy():
    if not TURTLE_AVAILABLE:
        return
    screen = turtle.Screen()
    screen.title("MedTimer: Weekly Trophy!")
    t = turtle.Turtle()
    t.speed(3)
    t.pensize(3)
    # Cup
    t.color("orange")
    t.begin_fill()
    t.circle(40)
    t.end_fill()
    # Base
    t.penup()
    t.goto(-20, -60)
    t.pendown()
    t.begin_fill()
    for _ in range(2):
        t.forward(40)
        t.right(90)
        t.forward(20)
        t.right(90)
    t.end_fill()
    # Text
    t.penup()
    t.goto(0, -100)
    t.write("🏆 Great Adherence!", align="center", font=("Arial", 14, "bold"))
    t.hideturtle()


# ------------------------------
# Audio beep (PCM WAV)
# ------------------------------
def generate_beep(duration_sec=0.3, freq_hz=880, sample_rate=44100, volume=0.4) -> bytes:
    n_samples = int(duration_sec * sample_rate)
    data = bytearray()

    def _le32(x): return struct.pack("<I", x)
    def _le16(x): return struct.pack("<H", x)

    byte_rate = sample_rate * 2  # mono 16-bit
    block_align = 2
    data_chunk_size = n_samples * 2

    header = b"RIFF" + _le32(36 + data_chunk_size) + b"WAVE"
    fmt = b"fmt " + _le32(16) + _le16(1) + _le16(1) + _le32(sample_rate) + _le32(byte_rate) + _le16(block_align) + _le16(16)
    data_hdr = b"data" + _le32(data_chunk_size)

    for i in range(n_samples):
        t = i / sample_rate
        sample = int(32767 * volume * math.sin(2 * math.pi * freq_hz * t))
        data += struct.pack("<h", sample)

    return header + fmt + data_hdr + data


def auto_beep():
    """Play an audio beep immediately (used for reminder window events)."""
    st.audio(generate_beep(), format="audio/wav")


# ------------------------------
# Helpers: events & adherence
# ------------------------------
def weekday_name(date_obj: dt.date) -> str:
    return DAY_ORDER[date_obj.weekday()]


def event_key(date_obj: dt.date, name: str, time_obj: dt.time) -> str:
    return f"{date_obj.isoformat()}|{name}|{time_obj.strftime('%H:%M')}"


def mark_taken(date_obj: dt.date, name: str, time_obj: dt.time):
    st.session_state.taken_events.add(event_key(date_obj, name, time_obj))


def occurrences_for_date(date_obj: dt.date):
    """Build list of scheduled events for a given date."""
    wname = weekday_name(date_obj)
    occ = []
    for sch in st.session_state.schedules:
        if date_obj >= sch["start_date"] and wname in sch["days_of_week"]:
            for t in sch["times"]:
                occ.append({"date": date_obj, "name": sch["name"], "time": t})
    return sorted(occ, key=lambda x: x["time"])


def weekly_occurrences(week_start: dt.date):
    """Map ISO date -> list of occurrences for a full week."""
    week = {}
    for i in range(7):
        d = week_start + dt.timedelta(days=i)
        week[d.isoformat()] = occurrences_for_date(d)
    return week


def adherence_this_week(today: dt.date) -> int:
    start = today - dt.timedelta(days=today.weekday())
    total = 0
    taken = 0
    for i in range(7):
        d = start + dt.timedelta(days=i)
        for ev in occurrences_for_date(d):
            total += 1
            if event_key(ev["date"], ev["name"], ev["time"]) in st.session_state.taken_events:
                taken += 1
    return int((taken / total) * 100) if total else 0


# ------------------------------
# Sidebar: settings
# ------------------------------
with st.sidebar:
    st.header("Reminders & settings")
    st.session_state.reminder_minutes = st.slider("Reminder window (minutes before dose)", 1, 60, st.session_state.reminder_minutes)


# ------------------------------
# Layout
# ------------------------------
st.title("💊 MedTimer — Daily Medicine Companion")
st.write("Add recurring schedules or one-off doses for today, see color-coded checklist, weekly calendar, and adherence. Automatic audio reminders included.")

col_input, col_main, col_side = st.columns([1.3, 1.7, 1.2])


# ------------------------------
# Input: add schedules (hybrid input) and one-off dose for today
# ------------------------------
with col_input:
    st.subheader("Add recurring schedule")

    choice = st.selectbox("Select medicine or choose 'Custom'", options=["Custom"] + COMMON_MEDICINES)
    med_name = st.text_input("Enter medicine name (used if 'Custom')", value="" if choice == "Custom" else choice)

    today = dt.date.today()
    today_wname = weekday_name(today)
    days_selected = st.multiselect("Days of week", DAY_ORDER, default=[today_wname])

    dose_count = st.number_input("Doses per selected day", min_value=1, max_value=6, value=1, step=1)
    dose_times = [st.time_input(f"Dose time #{i+1}", value=dt.time(9 + i*3, 0), key=f"rec_time_{i}") for i in range(dose_count)]

    start_date = st.date_input("Start date", value=today)

    if st.button("Add schedule"):
        final_name = med_name.strip()
        if not final_name or not days_selected:
            st.warning("Please provide a valid medicine name and select at least one day.")
        else:
            st.session_state.schedules.append({
                "name": final_name,
                "days_of_week": days_selected,
                "times": dose_times,
                "start_date": start_date
            })
            st.success(f"Added schedule for {final_name}")
            # Trigger safe rerun so today's checklist updates immediately
            st.session_state.trigger_rerun = True

    st.markdown("---")
    st.subheader("Quick add dose for today")
    quick_name = st.text_input("Medicine name for today", key="quick_name")
    quick_time = st.time_input("Dose time for today", value=dt.time(10, 0), key="quick_time")
    if st.button("Add dose to today's checklist"):
        name_ok = (quick_name or "").strip()
        if not name_ok:
            st.warning("Please enter a valid medicine name.")
        else:
            # Append as a one-off schedule strictly for today
            st.session_state.schedules.append({
                "name": name_ok,
                "days_of_week": [today_wname],
                "times": [quick_time],
                "start_date": today
            })
            st.success(f"Added {name_ok} at {quick_time.strftime('%H:%M')} to today")
            st.session_state.trigger_rerun = True

    st.markdown("---")
    st.subheader("Your schedules")
    if not st.session_state.schedules:
        st.info("No schedules yet. Add one above.")
    else:
        for idx, sch in enumerate(st.session_state.schedules):
            st.markdown(f"- **{sch['name']}** — {', '.join(sch['days_of_week'])} | times: {', '.join([t.strftime('%H:%M') for t in sch['times']])} | start: {sch['start_date'].isoformat()}")
            c1, c2, c3 = st.columns([1, 1, 1])
            with c1:
                if st.button(f"Edit {idx}", key=f"edit_btn_{idx}"):
                    new_name = st.text_input(f"Name {idx}", value=sch["name"], key=f"name_{idx}")
                    new_days = st.multiselect(f"Days {idx}", DAY_ORDER, default=sch["days_of_week"], key=f"days_{idx}")
                    new_count = st.number_input(f"Doses/day {idx}", min_value=1, max_value=6, value=len(sch["times"]), key=f"cnt_{idx}")
                    new_times = []
                    for j in range(new_count):
                        existing = sch["times"][j] if j < len(sch["times"]) else dt.time(9, 0)
                        new_times.append(st.time_input(f"Time {idx}-{j+1}", value=existing, key=f"time_{idx}_{j}"))
                    new_start = st.date_input(f"Start {idx}", value=sch["start_date"], key=f"start_{idx}")
                    if st.button(f"Save {idx}", key=f"save_{idx}"):
                        sch["name"] = new_name.strip() or sch["name"]
                        sch["days_of_week"] = new_days
                        sch["times"] = new_times
                        sch["start_date"] = new_start
                        st.success("Schedule updated.")
                        st.session_state.trigger_rerun = True
            with c2:
                if st.button(f"Delete {idx}", key=f"del_{idx}"):
                    st.session_state.schedules.pop(idx)
                    st.warning("Schedule deleted.")
                    st.session_state.trigger_rerun = True
            with c3:
                if st.button(f"Duplicate {idx}", key=f"dup_{idx}"):
                    st.session_state.schedules.append({
                        "name": sch["name"],
                        "days_of_week": sch["days_of_week"][:],
                        "times": sch["times"][:],
                        "start_date": sch["start_date"]
                    })
                    st.success("Schedule duplicated.")
                    st.session_state.trigger_rerun = True


# ------------------------------
# Main: today’s checklist (auto-beep in reminder window)
# ------------------------------
with col_main:
    st.subheader("Today's checklist")

    today = dt.date.today()
    now_time = dt.datetime.now().time()
    todays_events = occurrences_for_date(today)

    if not todays_events:
        st.info("No doses scheduled for today.")
    else:
        for i, ev in enumerate(todays_events):
            key = event_key(ev["date"], ev["name"], ev["time"])
            # Determine status
            if key in st.session_state.taken_events:
                status = "taken"
            elif now_time < ev["time"]:
                status = "upcoming"
            else:
                status = "missed"

            # Reminder window check (auto-beep)
            upcoming_window = False
            if status == "upcoming":
                delta_min = (dt.datetime.combine(today, ev["time"]) - dt.datetime.combine(today, now_time)).total_seconds() / 60.0
                upcoming_window = 0 <= delta_min <= st.session_state.reminder_minutes
                if upcoming_window:
                    auto_beep()

            pill_class = {"taken": "pill-green", "upcoming": "pill-yellow", "missed": "pill-red"}[status]
            st.markdown(f"""
            <div class="card">
              <div><b>{ev['name']}</b> at {ev['time'].strftime('%H:%M')}
                <span class="pill {pill_class}">{status.upper()}</span>
                {"<span style='margin-left:8px;color:#1565C0'>Reminder: due soon</span>" if upcoming_window else ""}
              </div>
            </div>
            """, unsafe_allow_html=True)

            cA, cB, cC = st.columns([1, 1, 1])
            with cA:
                if status != "taken":
                    if st.button("Mark taken", key=f"taken_btn_{i}"):
                        mark_taken(ev["date"], ev["name"], ev["time"])
                        st.success(f"Marked {ev['name']} ({ev['time'].strftime('%H:%M')}) as taken.")
                        st.session_state.trigger_rerun = True
            with cB:
                # Optional reset if accidentally marked taken
                if status == "taken":
                    if st.button("Unmark", key=f"unmark_btn_{i}"):
                        if key in st.session_state.taken_events:
                            st.session_state.taken_events.remove(key)
                        st.info("Dose unmarked.")
                        st.session_state.trigger_rerun = True
            with cC:
                pass

    # Weekly calendar
    st.markdown("---")
    st.subheader("Weekly calendar")
    start = today - dt.timedelta(days=today.weekday())
    week_map = weekly_occurrences(start)

    cal_rows = []
    for d_i in range(7):
        d = start + dt.timedelta(days=d_i)
        label = f"{DAY_ORDER[d_i]} ({d.strftime('%d %b')})"
        items = week_map[d.isoformat()]
        entries = "—" if not items else "; ".join([f"{ev['time'].strftime('%H:%M')} {ev['name']}" for ev in items])
        cal_rows.append({"Day": label, "Scheduled doses": entries})
    st.table(cal_rows)


# ------------------------------
# Side: adherence & motivation
# ------------------------------
with col_side:
    st.subheader("Weekly adherence")
    score = adherence_this_week(dt.date.today())
    st.metric("Adherence", f"{score}%")

    if score >= 80:
        st.success("🎉 Excellent adherence this week!")
        draw_trophy()
    elif score >= 50:
        st.info("👍 Good job! Keep going.")
    else:
        st.warning("⚠️ Let's aim for better consistency.")

    st.markdown("---")
    st.subheader("Motivational tip")
    st.info(random.choice(QUOTES))

    st.markdown("---")
    st.caption("Audio reminders play automatically when a dose is near. Turtle drawings open in a separate local window.")


# ------------------------------
# Safe rerun (deferred) to refresh UI after changes
# ------------------------------
if st.session_state.get("trigger_rerun"):
    st.session_state.trigger_rerun = False
    st.experimental_rerun()
