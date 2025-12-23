import streamlit as st
import datetime as dt
from io import BytesIO
import turtle

st.set_page_config("MedTimer", "💊", layout="wide")

if "meds" not in st.session_state or not isinstance(st.session_state.meds, dict):
    st.session_state.meds = {}    

if "history" not in st.session_state:
    st.session_state.history = []    

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

def today():
    return dt.date.today()

def now():
    return dt.datetime.now().replace(second=0, microsecond=0)

def time_to_str(t: dt.time) -> str:
    return t.strftime("%H:%M")

def parse_time_str(s: str) -> dt.time:
    try:
        hh, mm = map(int, s.split(":"))
        return dt.time(hh, mm)
    except Exception:
        return dt.datetime.now().time().replace(second=0, microsecond=0)

def default_time_for_index(i: int) -> dt.time:
    hour = max(0, min(23, 8 + 4 * i))
    return dt.time(hour, 0)

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

def set_taken(name, dose_time, date, val: bool):
    h = get_history_entry(name, dose_time, date)
    if h is None:
        st.session_state.history.append({
            "date": date,
            "name": name,
            "dose_time": dose_time,
            "taken": bool(val)
        })
    else:
        h["taken"] = bool(val)

def get_taken(name, dose_time, date):
    h = get_history_entry(name, dose_time, date)
    return bool(h["taken"]) if h else False

def parse_hhmm(time_str: str) -> dt.datetime:
    """Convert HH:MM string to a full datetime object for today."""
    today_date = dt.date.today()
    t = dt.datetime.strptime(time_str, "%H:%M").time()
    return dt.datetime.combine(today_date, t)

def now_local() -> dt.datetime:
    """Current local datetime"""
    return dt.datetime.now()

def status_for_dose_fixed(dose_time_str, taken):
    if taken:
        return "taken"
    target_dt = parse_hhmm(dose_time_str)
    return "upcoming" if now_local() < target_dt else "missed"

def adherence_score(history, days=7):
    if not history:
        return 0.0
    cutoff = today() - dt.timedelta(days=days - 1)
    recent = [h for h in history if h["date"] >= cutoff]
    if not recent:
        return 0.0
    total = len(recent)
    taken = sum(1 for h in recent if h["taken"])
    return round(100.0 * taken / max(total, 1), 1)

def update_streak(history):
    s = 0
    day = today()
    while True:
        entries = [h for h in history if h["date"] == day]
        if not entries:
            break
        total = len(entries)
        taken = sum(1 for h in entries if h["taken"])
        if total > 0 and taken == total:
            s += 1
            day -= dt.timedelta(days=1)
        else:
            break
    return s

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
        y -= 28
        c.setFont("Helvetica", 10)
        c.drawString(60, y, dt.datetime.now().strftime("Generated: %Y-%m-%d %H:%M"))
        y -= 18
        score = adherence_score(history, 7)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(60, y, f"7-Day Adherence: {score}%")
        y -= 24
        c.setFont("Helvetica-Bold", 12)
        c.drawString(
            60,
            y,
            f"Scheduled Doses for {dt.datetime.now().strftime('%A, %d %B %Y')}:"
        )
        y -= 16
        for m in meds_today:
            c.setFont("Helvetica", 10)
            c.drawString(
                60,
                y,
                f"- {m['name']} @ {m['dose_time']} | taken: {m['taken']}"
            )
            y -= 12

            if y < 80:
                c.showPage()
                y = h - 60

        c.save()
        buf.seek(0)
        return buf.getvalue()

    except Exception:
        return b""

st.title("MedTimer")
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    st.markdown("### Today")
with col2:
    st.metric("7-Day Adherence", f"{adherence_score(st.session_state.history,7)}%")
with col3:
    st.metric("Perfect Streak", f"{update_streak(st.session_state.history)} days")

st.header("Today's Checklist")

today_date = today()
weekday = WEEKDAYS[today_date.weekday()]
scheduled_today = []

if st.session_state.meds:
    for name, info in st.session_state.meds.items():

        if weekday not in info.get("days", WEEKDAYS):
            continue

        st.write(f"**{name}** — {info.get('note') or 'No note'}")

        doses_sorted = sorted(info.get("doses", []), key=lambda s: parse_time_str(s))

        for dose in doses_sorted:
            ensure_history_entry(name, dose, today_date)

            taken = get_taken(name, dose, today_date)
            status = status_for_dose_fixed(dose, taken)

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
                btn_key = f"btn_{name}_{dose}_{today_date}_{'taken' if taken else 'untaken'}"
                if taken:
                    if st.button("Undo", key=btn_key):
                        set_taken(name, dose, today_date, False)
                        st.rerun()
                else:
                    if st.button("Mark taken", key=btn_key):
                        set_taken(name, dose, today_date, True)
                        st.rerun()

            scheduled_today.append({
                "name": name,
                "dose_time": dose,
                "taken": get_taken(name, dose, today_date)
            })

        st.divider()
else:
    st.info("No medicines yet. Use Add/Edit section.")

st.header("Add / Edit Medicines")
mode = st.radio("Mode", ["Add", "Edit"])
preset_meds = [
    "Paracetamol","Aspirin","Ibuprofen","Amoxicillin","Vitamin D","Iron","Zinc",
    "Cough Syrup","Metformin","Atorvastatin","Omeprazole","Azithromycin","Cetirizine",
    "Salbutamol","Levothyroxine","Prednisone","Simvastatin","Furosemide","Losartan","Hydrochlorothiazide"
]

if mode == "Add":
    med_choice = st.selectbox("Select medicine or Custom", ["Custom"] + preset_meds)

    if med_choice == "Custom":
        name = st.text_input("Enter medicine name")
    else:
        name = med_choice
        st.caption(f"Preset medicine: {name}")

    note = st.text_input("Note")
    freq = st.number_input("Times per day", 1, 10, 1)

    st.write("Enter dose times:")
    new_times = []
    for i in range(freq):
        tm = st.time_input(
            f"Dose {i+1}",
            value=dt.datetime.strptime("08:00","%H:%M").time(),
            key=f"add_time_{i}"
        )
        new_times.append(tm.strftime("%H:%M"))

    st.write("Repeat on days:")
    day_cols = st.columns(7)
    selected_days = []
    
    for i, d in enumerate(WEEKDAYS):
        if day_cols[i].checkbox(d, True, key=f"add_day_{d}"):
            selected_days.append(d)
    if st.button("Add"):
        if not name.strip():
            st.warning("Enter a name.")
        elif name in st.session_state.meds:
            st.warning("Medicine exists. Use Edit.")
        else:
            st.session_state.meds[name] = {
                "doses": new_times,
                "note": note,
                "days": selected_days or WEEKDAYS
            }
            st.success(f"Added {name}")
            st.rerun()
else:
    meds = list(st.session_state.meds.keys())
    if meds:
        target = st.selectbox("Select medicine", meds)
        info = st.session_state.meds[target]
        new_name = st.text_input("Name", target)
        new_note = st.text_input("Note", info.get("note",""))
        freq = st.number_input("Times per day", 1, 10, value=len(info.get("doses",[])))
        st.write("Edit dose times:")
        new_times = []
        for i in range(freq):
            default = info["doses"][i] if i < len(info["doses"]) else "08:00"
            tm = st.time_input(
                f"Dose {i+1}",
                value=dt.datetime.strptime(default,"%H:%M").time(),
                key=f"edit_time_{i}"
            )
            new_times.append(tm.strftime("%H:%M"))
        st.write("Repeat on days:")
        cols = st.columns(7)
        new_days = []
        for i, d in enumerate(WEEKDAYS):
            if cols[i].checkbox(d, d in info.get("days", WEEKDAYS), key=f"edit_day_{d}"):
                new_days.append(d)
        if st.button("Save changes"):
            if new_name != target and new_name in st.session_state.meds:
                st.warning("Another medicine already has that name.")
            else:
                if new_name != target:
                    for h in st.session_state.history:
                        if h["name"] == target:
                            h["name"] = new_name
                    st.session_state.meds.pop(target)

                st.session_state.meds[new_name] = {
                    "doses": new_times,
                    "note": new_note,
                    "days": new_days or WEEKDAYS
                }
                st.success("Saved")
                st.rerun()
        if st.button("Delete Medicine", key=f"delete_{target}"):
            del st.session_state.meds[target]
            st.session_state.history = [
                h for h in st.session_state.history if h["name"] != target
            ]
            st.success(f"Deleted {target}")
            st.rerun()
    else:
        st.info("No medicines available. Switch to Add mode.")
        
st.header("Your Daily Well-Being Check 😊")
score = adherence_score(st.session_state.history, 7)

if score == 0:
    st.info("🌿 Let's begin today with a small step. Your health matters, one dose at a time.")
elif score <= 25:
    st.warning("☹️ Your health buddy is a bit concerned.\n\n“Even small progress is still progress.”")
elif score <= 50:
    st.warning("😐 You're getting there.\n\n“Staying consistent makes tomorrow easier.”")
elif score <= 75:
    st.success("🙂 Good work!\n\n“Every dose you take is a gift to your future self.”")
else:
    st.success("😊 Wonderful consistency!\n\n“Your commitment is keeping you strong every day.”")

st.header("Export Weekly PDF")
st.subheader("Weekly PDF Report")
sample_schedule = []
td = today()
wd = WEEKDAYS[td.weekday()]

for name, info in st.session_state.meds.items():
    if wd not in info.get("days", WEEKDAYS):
        continue
    for dose in info.get("doses", []):
        sample_schedule.append({
            "name": name,
            "dose_time": dose,
            "taken": get_taken(name, dose, td)
        })
pdf_bytes = build_report_pdf_bytes(st.session_state.history, sample_schedule)
if pdf_bytes:
    st.download_button(
        "Download PDF",
        pdf_bytes,
        file_name="MedTimer_Report.pdf",
        mime="application/pdf"
    )
else:
    st.info("PDF not available. Install reportlab.")
st.markdown("---")
cols = st.columns([2, 1])

with cols[0]:
    st.markdown("#### Motivation of the Day")
    tips = [
        "Taking medicines on time is a vote for your future self.",
        "Small habits, big impact—consistency builds confidence.",
        "You’re not alone—set gentle reminders and celebrate wins.",
        "Celebrate every day you complete your doses."
    ]
    st.info(tips[dt.datetime.now().day % len(tips)])

with cols[1]:
    st.markdown("#### Data")
    if st.button("Reset all data"):
        st.session_state.meds = {}
        st.session_state.history = []
        st.success("All data cleared")
        st.rerun()

screen = turtle.Screen()
screen.title("MedTimer – Emoji Feedback")
screen.bgcolor("#fffde7")

t = turtle.Turtle()
t.hideturtle()
t.speed(0)
t.width(4)
t.color("black")

def move(x, y):
    t.penup()
    t.goto(x, y)
    t.pendown()

def face(x, y, r=65):
    move(x, y - r)
    t.color("black", "#ffee58")
    t.begin_fill()
    t.circle(r)
    t.end_fill()
    t.color("black")

def eye_dot(x, y, r=5):
    move(x, y - r)
    t.begin_fill()
    t.circle(r)
    t.end_fill()

def eye_line(x, y, length=16):
    move(x - length/2, y)
    t.setheading(0)
    t.forward(length)

def sad_mouth(x, y):
    move(x - 40, y - 15)
    t.setheading(480)
    t.circle(40, 120)

def neutral_mouth(x, y):
    move(x - 25, y - 10)
    t.setheading(0)
    t.forward(50)

def kiss_mouth(x, y):
    move(x, y - 20)
    t.circle(8)

def smile_mouth(x, y):
    move(x - 30, y - 15)
    t.setheading(-60)
    t.circle(40, 120)

def label(txt, x, y):
    move(x, y)
    t.write(txt, align="center", font=("Arial", 12, "bold"))

def emoji_sad(x, y):
    face(x, y)
    eye_dot(x - 20, y + 22)
    eye_dot(x + 20, y + 22)
    sad_mouth(x+75, y-15)

def emoji_neutral(x, y):
    face(x-55, y+105)
    eye_line(x - 20, y + 25)
    eye_line(x + 20, y + 25)
    neutral_mouth(x, y)

def emoji_good(x, y):
    face(x, y)
    eye_dot(x - 20, y + 22)
    eye_dot(x + 20, y + 22)
    kiss_mouth(x, y)

def emoji_happy(x, y):
    face(x, y)
    eye_dot(x - 22, y + 25)
    eye_dot(x + 22, y + 25)
    smile_mouth(x, y)

emoji_sad(-240, 80)
label("Low adherence", -240, -40)

emoji_neutral(-80, 80)
label("Getting there", -80, -40)

emoji_good(80, 80)
label("Good progress", 80, -40)

emoji_happy(240, 80)
label("Excellent consistency", 240, -40)

turtle.done()
