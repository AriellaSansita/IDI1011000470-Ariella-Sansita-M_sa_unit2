import streamlit as st
import datetime as dt
from io import BytesIO

# ------------------ PAGE CONFIG ------------------
st.set_page_config("MedTimer", "💊", layout="wide")

# ------------------ SESSION STATE ------------------
if "meds" not in st.session_state or not isinstance(st.session_state.meds, dict):
    st.session_state.meds = {}

if "history" not in st.session_state:
    st.session_state.history = []

# ------------------ CONSTANTS ------------------
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ------------------ TIME HELPERS ------------------
def now_local():
    return dt.datetime.now().replace(second=0, microsecond=0)

def today():
    return now_local().date()

def parse_time_str(s: str) -> dt.time:
    try:
        return dt.datetime.strptime(s, "%H:%M").time()
    except:
        return now_local().time()

def parse_hhmm(time_str: str) -> dt.datetime:
    t = dt.datetime.strptime(time_str, "%H:%M").time()
    return dt.datetime.combine(today(), t)

# ------------------ HISTORY HELPERS ------------------
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
        h["taken"] = val

def get_taken(name, dose_time, date):
    h = get_history_entry(name, dose_time, date)
    return h["taken"] if h else False

# ------------------ LOGIC ------------------
def status_for_dose(dose_time, taken):
    if taken:
        return "taken"
    return "upcoming" if now_local() < parse_hhmm(dose_time) else "missed"

def adherence_score(history, days=7):
    cutoff = today() - dt.timedelta(days=days - 1)
    recent = [h for h in history if h["date"] >= cutoff]
    if not recent:
        return 0
    taken = sum(1 for h in recent if h["taken"])
    return round((taken / len(recent)) * 100, 1)

def update_streak(history):
    streak = 0
    day = today()
    while True:
        entries = [h for h in history if h["date"] == day]
        if not entries or not all(h["taken"] for h in entries):
            break
        streak += 1
        day -= dt.timedelta(days=1)
    return streak

# ------------------ PDF REPORT ------------------
def build_report_pdf_bytes(history, meds_today):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        w, h = A4
        y = h - 60

        c.setFont("Helvetica-Bold", 16)
        c.drawString(60, y, "MedTimer – Weekly Adherence Report")
        y -= 30

        c.setFont("Helvetica", 10)
        c.drawString(60, y, f"Generated: {now_local().strftime('%Y-%m-%d %H:%M')}")
        y -= 20

        score = adherence_score(history)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(60, y, f"7-Day Adherence: {score}%")
        y -= 25

        for m in meds_today:
            c.setFont("Helvetica", 10)
            c.drawString(60, y, f"- {m['name']} @ {m['dose_time']} | Taken: {m['taken']}")
            y -= 15

        c.save()
        buf.seek(0)
        return buf.getvalue()
    except:
        return b""

# ------------------ UI ------------------
st.title("MedTimer")
st.caption(f"📅 {now_local().strftime('%A, %d %B %Y • %H:%M')}")

col1, col2, col3 = st.columns(3)
col1.markdown("### Today")
col2.metric("7-Day Adherence", f"{adherence_score(st.session_state.history)}%")
col3.metric("Perfect Streak", f"{update_streak(st.session_state.history)} days")

st.header("Today's Checklist")

weekday = WEEKDAYS[today().weekday()]

if st.session_state.meds:
    for name, info in st.session_state.meds.items():
        if weekday not in info.get("days", WEEKDAYS):
            continue

        st.write(f"**{name}** — {info.get('note', 'No note')}")

        for dose in sorted(info["doses"], key=parse_time_str):
            ensure_history_entry(name, dose, today())
            taken = get_taken(name, dose, today())
            status = status_for_dose(dose, taken)

            c1, c2, c3 = st.columns([2, 1, 1])
            c1.write(f"⏰ {dose}")

            if status == "taken":
                c2.success("Taken")
            elif status == "upcoming":
                c2.warning("Upcoming")
            else:
                c2.error("Missed")

            if taken:
                if c3.button("Undo", key=f"u_{name}_{dose}"):
                    set_taken(name, dose, today(), False)
                    st.rerun()
            else:
                if c3.button("Mark taken", key=f"t_{name}_{dose}"):
                    set_taken(name, dose, today(), True)
                    st.rerun()

        st.divider()
else:
    st.info("No medicines added yet.")

# ------------------ MOTIVATION ------------------
st.header("Your Daily Well-Being Check 😊")
score = adherence_score(st.session_state.history)

if score == 0:
    st.info("☹️ Let’s start today — one dose at a time.")
elif score <= 50:
    st.warning("😐 Progress matters. Keep going.")
elif score <= 75:
    st.success("🙂 Nice work! Stay consistent.")
else:
    st.success("🌟 Excellent! You’re doing great.")

# ------------------ RESET ------------------
if st.button("Reset all data"):
    st.session_state.meds = {}
    st.session_state.history = []
    st.success("All data cleared")
    st.rerun()

