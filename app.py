import streamlit as st
import datetime as dt
from datetime import datetime
from io import BytesIO
import math, wave, struct
import turtle   # ✅ REQUIRED TURTLE IMPORT

# PAGE CONFIGURATION
st.set_page_config("MedTimer", "💊", layout="wide")

# AUTO REFRESH (updates upcoming → missed)
st.autorefresh(interval=60000, key="auto_refresh")

# SESSION STATE
if "meds" not in st.session_state or not isinstance(st.session_state.meds, dict):
    st.session_state.meds = {}

if "history" not in st.session_state:
    st.session_state.history = []

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ---------------- HELPER FUNCTIONS ----------------

def today():
    return dt.date.today()

def now():
    return dt.datetime.now()

def parse_time_str(s: str) -> dt.time:
    try:
        h, m = map(int, s.split(":"))
        return dt.time(h, m)
    except:
        return dt.datetime.now().time().replace(second=0, microsecond=0)

def get_history_entry(name, dose_time, date):
    for h in st.session_state.history:
        if h["date"] == date and h["name"] == name and h["dose_time"] == dose_time:
            return h
    return None

def ensure_history_entry(name, dose_time, date):
    if get_history_entry(name, dose_time, date) is None:
        st.session_state.history.append({
            "date": date,
            "name": name,
            "dose_time": dose_time,
            "taken": False
        })

def set_taken(name, dose_time, date, val):
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
    h = get_history_entry(name, dose_time, date)
    return h["taken"] if h else False

def status_for_dose(dose_time_str, taken, now_dt):
    if taken:
        return "taken"
    med_time = parse_time_str(dose_time_str)
    med_dt = dt.datetime.combine(now_dt.date(), med_time)
    return "upcoming" if med_dt > now_dt else "missed"

def adherence_score(history, days=7):
    cutoff = today() - dt.timedelta(days=days - 1)
    recent = [h for h in history if h["date"] >= cutoff]
    if not recent:
        return 0.0
    taken = sum(1 for h in recent if h["taken"])
    return round(100 * taken / len(recent), 1)

# ---------------- TURTLE REWARD ----------------

def draw_turtle_reward():
    screen = turtle.Screen()
    screen.setup(400, 400)
    screen.title("Great Job! 🐢")

    t = turtle.Turtle()
    t.hideturtle()
    t.speed(0)
    t.pensize(3)
    t.color("green")

    # Face
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

# ---------------- UI ----------------

st.title("MedTimer")

score = adherence_score(st.session_state.history)
st.metric("7-Day Adherence", f"{score}%")

if score >= 75:
    st.success("🏆 Excellent adherence!")
    if st.button("Show Reward 🐢"):
        draw_turtle_reward()

st.header("Today's Checklist")

today_date = today()
now_dt = now()
weekday = WEEKDAYS[today_date.weekday()]

if st.session_state.meds:
    for name, info in st.session_state.meds.items():
        if weekday not in info.get("days", WEEKDAYS):
            continue

        st.subheader(name)
        for dose in sorted(info.get("doses", [])):
            ensure_history_entry(name, dose, today_date)
            taken = get_taken(name, dose, today_date)
            status = status_for_dose(dose, taken, now_dt)

            c1, c2, c3 = st.columns(3)

            c1.write(f"⏰ {dose}")

            if status == "taken":
                c2.success("Taken")
            elif status == "upcoming":
                c2.warning("Upcoming")
            else:
                c2.error("Missed")

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

if st.button("Reset all data"):
    st.session_state.meds = {}
    st.session_state.history = []
    st.success("Data cleared")
    st.rerun()
