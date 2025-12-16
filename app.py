import streamlit as st
import datetime as dt
from datetime import datetime
from io import BytesIO
import math, wave, struct
import turtle   # Turtle graphics used for motivational rewards

# ---------------- PAGE CONFIGURATION ----------------
# Wide layout and emoji icon for accessibility and clarity
st.set_page_config("MedTimer", "💊", layout="wide")

# Auto-refresh every 60 seconds so upcoming doses
# automatically become missed if time passes
st.autorefresh(interval=60000, key="auto_refresh")

# ---------------- SESSION STATE ----------------
# meds stores all medicines added by the user
# Structure:
# {
#   "Medicine Name": {
#       "doses": ["08:00", "20:00"],
#       "days": ["Mon", "Tue", "Wed"]
#   }
# }
if "meds" not in st.session_state or not isinstance(st.session_state.meds, dict):
    st.session_state.meds = {}

# history stores daily dose records to track adherence
# Each entry records date, medicine name, dose time, and taken status
if "history" not in st.session_state:
    st.session_state.history = []

# Weekday labels used for scheduling medicines
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ---------------- HELPER FUNCTIONS ----------------

def today():
    """Returns today's date."""
    return dt.date.today()

def now():
    """Returns current date and time."""
    return dt.datetime.now()

def parse_time_str(s: str) -> dt.time:
    """
    Converts a HH:MM string into a time object.
    If parsing fails, returns the current time safely.
    """
    try:
        h, m = map(int, s.split(":"))
        return dt.time(h, m)
    except:
        return dt.datetime.now().time().replace(second=0, microsecond=0)

def get_history_entry(name, dose_time, date):
    """
    Retrieves a specific history record for a medicine dose on a given date.
    """
    for h in st.session_state.history:
        if h["date"] == date and h["name"] == name and h["dose_time"] == dose_time:
            return h
    return None

def ensure_history_entry(name, dose_time, date):
    """
    Ensures a history record exists for today's dose.
    This allows missed doses to be detected automatically.
    """
    if get_history_entry(name, dose_time, date) is None:
        st.session_state.history.append({
            "date": date,
            "name": name,
            "dose_time": dose_time,
            "taken": False
        })

def set_taken(name, dose_time, date, val):
    """
    Marks a specific dose as taken or not taken.
    """
    h = get_history_entry(name, dose_time, date)
    if h:
        h["taken"] = val
    else:
        st.session_state.history.append({
            "date": date,
            "name": name,
            "dose_time": dose_time,
            "taken": val
        })

def get_taken(name, dose_time, date):
    """
    Returns True if the dose has been taken, otherwise False.
    """
    h = get_history_entry(name, dose_time, date)
    return h["taken"] if h else False

def status_for_dose(dose_time_str, taken, now_dt):
    """
    Determines the current status of a dose:
    - taken: already marked as taken
    - upcoming: scheduled for later today
    - missed: scheduled time has passed and not taken
    """
    if taken:
        return "taken"

    med_time = parse_time_str(dose_time_str)
    med_dt = dt.datetime.combine(now_dt.date(), med_time)

    return "upcoming" if med_dt > now_dt else "missed"

def adherence_score(history, days=7):
    """
    Calculates adherence percentage over the last 7 days.
    Adherence = (taken doses / scheduled doses) * 100
    """
    cutoff = today() - dt.timedelta(days=days - 1)
    recent = [h for h in history if h["date"] >= cutoff]

    if not recent:
        return 0.0

    taken = sum(1 for h in recent if h["taken"])
    return round(100 * taken / len(recent), 1)

# ---------------- TURTLE REWARD ----------------
# Turtle graphics are used as positive reinforcement.
# When adherence is high, a friendly turtle face is drawn
# to encourage consistency and reduce anxiety.

def draw_turtle_reward():
    screen = turtle.Screen()
    screen.setup(400, 400)
    screen.title("Great Job! 🐢")

    t = turtle.Turtle()
    t.hideturtle()
    t.speed(0)
    t.pensize(3)
    t.color("green")

    # Turtle face
    t.penup()
    t.goto(0, -20)
    t.pendown()
    t.circle(80)

    # Eyes
    for x in [-30, 30]:
        t.penup()
        t.goto(x, 40)
        t.pendown()
        t.dot(10)

    # Smile
    t.penup()
    t.goto(-35, 10)
    t.setheading(-60)
    t.pendown()
    t.circle(40, 120)

    screen.exitonclick()

# ---------------- BEEP SOUND ----------------
# Generates a short audio beep to confirm a dose is marked as taken

def generate_beep_wav(seconds=0.4, freq=880):
    framerate = 44100
    nframes = int(seconds * framerate)
    buf = BytesIO()

    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(framerate)

        for i in range(nframes):
            val = int(32767 * math.sin(2 * math.pi * freq * (i / framerate)))
            w.writeframes(struct.pack('<h', val))

    buf.seek(0)
    return buf

# ---------------- USER INTERFACE ----------------

st.title("MedTimer")

# Display weekly adherence score
score = adherence_score(st.session_state.history)
st.metric("7-Day Adherence", f"{score}%")

# Show reward if adherence is high
if score >= 75:
    st.success("🏆 Excellent adherence!")
    if st.button("Show Reward 🐢"):
        draw_turtle_reward()

st.header("Today's Checklist")

today_date = today()
now_dt = now()
weekday = WEEKDAYS[today_date.weekday()]

# Display medicines scheduled for today
if st.session_state.meds:
    for name, info in st.session_state.meds.items():
        if weekday not in info.get("days", WEEKDAYS):
            continue

        st.subheader(name)

        for dose in sorted(info.get("doses", [])):
            ensure_history_entry(name, dose, today_date)
            taken = get_taken(name, dose, today_date)
            status = status_for_dose(dose, taken, now_dt)

            # Three-column layout: time, status, action
            c1, c2, c3 = st.columns(3)
            c1.write(f"⏰ {dose}")

            if status == "taken":
                c2.success("Taken")
            elif status == "upcoming":
                c2.warning("Upcoming")
            else:
                c2.error("Missed")

            # Mark dose as taken
            if not taken:
                if c3.button("Mark taken", key=f"{name}_{dose}"):
                    set_taken(name, dose, today_date, True)
                    st.audio(generate_beep_wav(), format="audio/wav")
                    st.rerun()
            else:
                c3.write("✔")
else:
    st.info("No medicines added.")

# ---------------- ADD MEDICINE ----------------

st.header("Add Medicine")

name = st.text_input("Medicine name")
times = st.number_input("Times per day", 1, 5, 1)

dose_times = []
for i in range(times):
    t = st.time_input(f"Dose {i+1}", datetime.strptime("08:00", "%H:%M").time())
    dose_times.append(t.strftime("%H:%M"))

days = st.multiselect("Days", WEEKDAYS, default=WEEKDAYS)

if st.button("Add Medicine"):
    if name.strip():
        st.session_state.meds[name] = {
            "doses": dose_times,
            "days": days or WEEKDAYS
        }
        st.success("Medicine added")
        st.rerun()
    else:
        st.warning("Enter medicine name")

# ---------------- FOOTER ----------------

st.markdown("---")
st.info("💙 Consistency today builds a healthier tomorrow.")

# Reset all stored data
if st.button("Reset all data"):
    st.session_state.meds = {}
    st.session_state.history = []
    st.success("Data cleared")
    st.rerun()
