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
    st.info("☹️ Let's begin today with a small step. Your health matters, one dose at a time.")
elif score <= 25:
    st.warning("☹️ Your health buddy is a bit concerned.\n\n“Even small progress is still progress.”")
elif score <= 50:
    st.warning("😐 You're getting there.\n\n“Staying consistent makes tomorrow easier.”")
elif score <= 75:
    st.success("🙂 Good work!\n\n“Every dose you take is a gift to your future self.”")
else:
    st.success("🙂 Wonderful consistency!\n\n“Your commitment is keeping you strong every day.”")

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

