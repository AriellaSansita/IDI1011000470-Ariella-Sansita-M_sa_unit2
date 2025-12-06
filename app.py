import streamlit as st
import datetime as dt
from datetime import datetime
from io import BytesIO
import math, wave, struct

# -------------------------
# Page config
# -------------------------
st.set_page_config("MedTimer", "💊", layout="wide")

# -------------------------
# Session state init
# -------------------------
if "meds" not in st.session_state or not isinstance(st.session_state.meds, dict):
    st.session_state.meds = {}
if "history" not in st.session_state:
    st.session_state.history = []
if "streak" not in st.session_state:
    st.session_state.streak = 0

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# -------------------------
# Helpers
# -------------------------
def today(): return dt.date.today()
def now(): return dt.datetime.now()
def time_to_str(t: dt.time) -> str: return t.strftime("%H:%M")
def parse_time_str(s: str) -> dt.time:
    try:
        hh, mm = map(int, s.split(":")); return dt.time(hh, mm)
    except Exception:
        return dt.datetime.now().time().replace(second=0, microsecond=0)
def default_time_for_index(i: int) -> dt.time:
    hour = max(0, min(23, 8 + 4 * i)); return dt.time(hour, 0)

def get_history_entry(name, dose_time, date):
    for h in st.session_state.history:
        if h["date"] == date and h["name"] == name and h["dose_time"] == dose_time:
            return h
    return None

def ensure_history_entry(name, dose_time, date):
    if get_history_entry(name, dose_time, date) is None:
        st.session_state.history.append({"date": date, "name": name, "dose_time": dose_time, "taken": False})

def set_taken(name, dose_time, date, val: bool):
    h = get_history_entry(name, dose_time, date)
    if h is None:
        st.session_state.history.append({"date": date, "name": name, "dose_time": dose_time, "taken": bool(val)})
    else:
        h["taken"] = bool(val)

def get_taken(name, dose_time, date):
    h = get_history_entry(name, dose_time, date); return bool(h["taken"]) if h else False

def status_for_dose(dose_time_str, taken, now_dt):
    if taken: return "taken"
    med_time = parse_time_str(dose_time_str)
    med_dt = dt.datetime.combine(now_dt.date(), med_time)
    return "upcoming" if med_dt > now_dt else "missed"

def adherence_score(history, days=7):
    if not history: return 0.0
    cutoff = today() - dt.timedelta(days=days-1)
    recent = [h for h in history if h["date"] >= cutoff]
    if not recent: return 0.0
    total = len(recent); taken = sum(1 for h in recent if h["taken"])
    return round(100.0 * taken / max(total, 1), 1)

def update_streak(history):
    s = 0; day = today()
    while True:
        entries = [h for h in history if h["date"] == day]
        if not entries: break
        total = len(entries); taken = sum(1 for h in entries if h["taken"])
        if total > 0 and taken == total:
            s += 1; day -= dt.timedelta(days=1)
        else:
            break
    return s

def draw_turtle_image(size=220):
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
        d = ImageDraw.Draw(img)
        cx, cy = size//2, size//2
        d.ellipse([cx-70, cy-50, cx+70, cy+80], fill="#6aa84f", outline="#2e7d32")  # shell
        d.ellipse([cx-40, cy-20, cx+40, cy+40], fill="#a3d18a")  # pattern
        d.ellipse([cx+60, cy-10, cx+95, cy+25], fill="#6aa84f", outline="#2e7d32")  # head
        d.ellipse([cx-80, cy+40, cx-60, cy+70], fill="#6aa84f")  # leg left
        d.ellipse([cx+40, cy+60, cx+60, cy+90], fill="#6aa84f")  # leg right
        d.ellipse([cx+80, cy+2, cx+86, cy+8], fill="black")  # eye
        return img
    except Exception:
        return None

def generate_beep_wav(seconds=0.6, freq=880):
    framerate = 44100; nframes = int(seconds * framerate); buf = BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(framerate)
        for i in range(nframes):
            val = int(32767.0 * math.sin(2 * math.pi * freq * (i / framerate)))
            w.writeframes(struct.pack('<h', val))
    buf.seek(0); return buf

def build_report_pdf_bytes(history, meds_today):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        buf = BytesIO(); c = canvas.Canvas(buf, pagesize=A4)
        w, h = A4; y = h - 60
        c.setFont("Helvetica-Bold", 16); c.drawString(60, y, "MedTimer – Weekly Adherence Report"); y -= 28
        c.setFont("Helvetica", 10); c.drawString(60, y, datetime.now().strftime("Generated: %Y-%m-%d %H:%M")); y -= 18
        score = adherence_score(history, 7); c.setFont("Helvetica-Bold", 12); c.drawString(60, y, f"7-Day Adherence: {score}%"); y -= 18
        cutoff = today() - dt.timedelta(days=6)
        for i in range(7):
            d = cutoff + dt.timedelta(days=i)
            entries = [h for h in history if h["date"] == d]; total = len(entries); taken = sum(1 for h in entries if h["taken"])
            c.setFont("Helvetica", 10); c.drawString(60, y, f"{d}: {taken}/{total} doses taken"); y -= 14
            if y < 80: c.showPage(); y = h - 60
        y -= 6; c.setFont("Helvetica-Bold", 12); c.drawString(60, y, "Today's Scheduled Doses:"); y -= 16
        for m in meds_today:
            c.setFont("Helvetica", 10); c.drawString(60, y, f"- {m['name']} @ {m['dose_time']} | taken: {m['taken']}"); y -= 12
            if y < 80: c.showPage(); y = h - 60
        c.save(); buf.seek(0); return buf.getvalue()
    except Exception:
        return b""

# -------------------------
# Page header / metrics
# -------------------------
st.title("MedTimer")
col1, col2, col3 = st.columns([2,1,1])
with col1: st.markdown("### Today")
with col2: st.metric("7-Day Adherence", f"{adherence_score(st.session_state.history,7)}%")
with col3: st.metric("Perfect Streak", f"{update_streak(st.session_state.history)} days")

# -------------------------
# Today's Checklist
# -------------------------
st.header("Today's Checklist")
today_date = today(); now_dt = now(); weekday = WEEKDAYS[today_date.weekday()]
scheduled_today = []
if st.session_state.meds:
    for name, info in st.session_state.meds.items():
        if weekday not in info.get("days", WEEKDAYS): continue
        st.write(f"**{name}** — {info.get('note') or 'No note'}")
        doses_sorted = sorted(info.get("doses", []), key=lambda s: parse_time_str(s))
        for dose in doses_sorted:
            ensure_history_entry(name, dose, today_date)
            taken = get_taken(name, dose, today_date)
            status = status_for_dose(dose, taken, now_dt)
            c1,c2,c3 = st.columns([2.2,1.2,1.2])
            with c1: st.write(f"⏰ {dose}")
            with c2:
                if status=="taken": st.success("Taken")  # Green
                elif status=="upcoming": st.warning("Upcoming")  # Orange (closest to yellow)
                else: st.error("Missed")  # Red
            with c3:
                btn_key = f"btn_{name}_{dose}_{today_date}_{'taken' if taken else 'untaken'}"
                if taken:
                    if st.button("Undo", key=btn_key): set_taken(name,dose,today_date,False); st.rerun()
                else:
                    if st.button("Mark taken", key=btn_key): set_taken(name,dose,today_date,True); st.rerun()
            scheduled_today.append({"name":name,"dose_time":dose,"taken":get_taken(name,dose,today_date)})
        st.divider()
else: st.info("No medicines yet. Use Add/Edit section.")

# -------------------------
# Add / Edit Medicines
# -------------------------
st.header("Add / Edit Medicines")
mode = st.radio("Mode", ["Add","Edit"])

# Preset medicines (~100 can be added)
preset_meds = ["Paracetamol","Aspirin","Ibuprofen","Amoxicillin","Vitamin D","Iron","Zinc",
               "Cough Syrup","Metformin","Atorvastatin","Omeprazole","Azithromycin","Cetirizine",
               "Salbutamol","Levothyroxine","Prednisone","Simvastatin","Furosemide","Losartan","Hydrochlorothiazide"]

if mode=="Add":
    med_choice = st.selectbox("Select medicine or Custom", ["Custom"]+preset_meds)
    if med_choice=="Custom": name=st.text_input("Enter medicine name")
    else: name=med_choice; st.caption(f"Preset medicine: {name}")

    note = st.text_input("Note")
    freq = st.number_input("Times per day",1,10,1)

    st.write("Enter dose times:")
    new_times=[]
    for i in range(freq):
        tm = st.time_input(f"Dose {i+1}", value=datetime.strptime("08:00","%H:%M").time(), key=f"add_time_{i}")
        new_times.append(tm.strftime("%H:%M"))

    st.write("Repeat on days:")
    day_cols = st.columns(7)
    selected_days=[]
    for i,d in enumerate(WEEKDAYS):
        if day_cols[i].checkbox(d, True, key=f"add_day_{d}"): selected_days.append(d)

    if st.button("Add"):
        if not name.strip(): st.warning("Enter a name.")
        elif name in st.session_state.meds: st.warning("Medicine exists. Use Edit.")
        else:
            st.session_state.meds[name]={"doses":new_times,"note":note,"days":selected_days or WEEKDAYS}
            st.success(f"Added {name}"); st.rerun()
else:
    meds=list(st.session_state.meds.keys())
    if meds:
        target=st.selectbox("Select medicine", meds)
        info=st.session_state.meds[target]
        new_name=st.text_input("Name", target)
        new_note=st.text_input("Note", info.get("note",""))
        freq=st.number_input("Times per day",1,10,value=len(info.get("doses",[])))

        st.write("Edit dose times:")
        new_times=[]
        for i in range(freq):
            default=info["doses"][i] if i<len(info["doses"]) else "08:00"
            tm=st.time_input(f"Dose {i+1}", value=datetime.strptime(default,"%H:%M").time(), key=f"edit_time_{i}")
            new_times.append(tm.strftime("%H:%M"))

        st.write("Repeat on days:")
        cols=st.columns(7)
        new_days=[]
        for i,d in enumerate(WEEKDAYS):
            if cols[i].checkbox(d,d in info.get("days",WEEKDAYS),key=f"edit_day_{d}"): new_days.append(d)

        if st.button("Save changes"):
            if new_name!=target and new_name in st.session_state.meds: st.warning("Another medicine already has that name.")
            else:
                if new_name!=target:
                    for h in st.session_state.history:
                        if h["name"]==target: h["name"]=new_name
                    st.session_state.meds.pop(target)
                st.session_state.meds[new_name]={"doses":new_times,"note":new_note,"days":new_days or WEEKDAYS}
                st.success("Saved"); st.rerun()

        # Added delete button
        if st.button("Delete Medicine", key=f"delete_{target}"):
            del st.session_state.meds[target]
            st.session_state.history = [h for h in st.session_state.history if h["name"] != target]
            st.success(f"Deleted {target}")
            st.rerun()
    else: st.info("No medicines available. Switch to Add mode.")

# -------------------------
# PDF Export
# -------------------------
st.header("Export Weekly PDF")
st.subheader("Weekly PDF Report")
sample_schedule=[]
td=today(); wd=WEEKDAYS[td.weekday()]
for name,info in st.session_state.meds.items():
    if wd not in info.get("days",WEEKDAYS): continue
    for dose in info.get("doses",[]): sample_schedule.append({"name":name,"dose_time":dose,"taken":get_taken(name,dose,td)})
pdf_bytes=build_report_pdf_bytes(st.session_state.history,sample_schedule)
if pdf_bytes: st.download_button("Download PDF", pdf_bytes, file_name="MedTimer_Report.pdf", mime="application/pdf")
else: st.info("PDF not available. Install reportlab.")

# -------------------------
# Footer: motivation + reset
# -------------------------
st.markdown("---")
cols=st.columns([2,1])
with cols[0]:
    st.markdown("#### Motivation of the Day")
    tips=["Taking medicines on time is a vote for your future self.",
          "Small habits, big impact—consistency builds confidence.",
          "You’re not alone—set gentle reminders and celebrate wins.",
          "Celebrate every day you complete your doses."]
    st.info(tips[dt.datetime.now().day % len(tips)])
with cols[1]:
    st.markdown("#### Data")
    if st.button("Reset all data"):
        st.session_state.meds={}; st.session_state.history=[]; st.session_state.streak=0
        st.success("All data cleared"); st.rerun()
