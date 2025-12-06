import streamlit as st
import datetime as dt
from datetime import datetime
from io import BytesIO
import math, wave, struct

# --- Config & minimal CSS ---
st.set_page_config("MedTimer – Daily Medicine Companion", "💊", layout="wide")
st.markdown("""
<style>
:root{--g:#c8e6c9;--y:#fff9c4;--r:#ffcdd2}
.pill{padding:6px 10px;border-radius:12px;font-weight:600}
.green{background:var(--g);color:#1b5e20}.yellow{background:var(--y);color:#5f5f00}.red{background:var(--r);color:#b71c1c}
.small{font-size:0.9rem}
</style>
""", unsafe_allow_html=True)

# --- Session state ---
if "meds" not in st.session_state or not isinstance(st.session_state.meds, dict):
    st.session_state.meds = {}
if "history" not in st.session_state:
    st.session_state.history = []  # {"date": date, "name": str, "dose_time": "HH:MM", "taken": bool}
if "streak" not in st.session_state:
    st.session_state.streak = 0

WEEKDAYS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

# --- Helpers ---
def today(): return dt.date.today()
def now(): return dt.datetime.now()
def time_to_str(t: dt.time) -> str: return t.strftime("%H:%M")
def parse_time_str(s: str) -> dt.time:
    try:
        hh, mm = map(int, s.split(":")); return dt.time(hh, mm)
    except Exception:
        return dt.datetime.now().time().replace(second=0, microsecond=0)
def default_time_for_index(i: int) -> dt.time:
    hour = max(0, min(23, 8 + 4*i)); return dt.time(hour, 0)

def get_history_entry(name, dose_time, date):
    for h in st.session_state.history:
        if h["date"] == date and h["name"] == name and h["dose_time"] == dose_time:
            return h
    return None

def ensure_history_entry(name, dose_time, date):
    if get_history_entry(name, dose_time, date) is None:
        st.session_state.history.append({"date": date, "name": name, "dose_time": dose_time, "taken": False})

def set_taken(name, dose_time, date, val):
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
    return round(100.0 * taken / max(total,1), 1)

def update_streak(history):
    s = 0; day = today()
    while True:
        entries = [h for h in history if h["date"] == day]
        if not entries: break
        total = len(entries); taken = sum(1 for h in entries if h["taken"])
        if total>0 and taken==total:
            s += 1; day -= dt.timedelta(days=1)
        else:
            break
    return s

def draw_trophy_image():
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB",(300,300),"white"); d=ImageDraw.Draw(img)
        d.rectangle([90,100,210,160], fill="#FFD700"); d.ellipse([60,100,120,160], fill="#FFD700"); d.ellipse([180,100,240,160], fill="#FFD700")
        d.rectangle([140,160,160,230], fill="#DAA520"); d.rectangle([110,230,190,250], fill="#8B4513")
        return img
    except Exception:
        return None

def generate_beep_wav(seconds=0.6, freq=880):
    framerate=44100; nframes=int(seconds*framerate); buf=BytesIO()
    with wave.open(buf,'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(framerate)
        for i in range(nframes):
            val = int(32767.0 * math.sin(2*math.pi*freq*(i/framerate)))
            w.writeframes(struct.pack('<h', val))
    buf.seek(0); return buf

def build_report_pdf_bytes(history, meds_today):
    # Try reportlab, fallback to tiny text-PDF if unavailable
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        buf = BytesIO(); c = canvas.Canvas(buf, pagesize=A4)
        w,h = A4; y = h - 60
        c.setFont("Helvetica-Bold", 16); c.drawString(60, y, "MedTimer – Weekly Adherence Report"); y -= 28
        c.setFont("Helvetica", 10); c.drawString(60,y, datetime.now().strftime("Generated: %Y-%m-%d %H:%M")); y -= 20
        score = adherence_score(history,7); c.setFont("Helvetica-Bold",12); c.drawString(60,y,f"7-Day Adherence: {score}%"); y -= 18
        cutoff = today() - dt.timedelta(days=6)
        for i in range(7):
            d = cutoff + dt.timedelta(days=i)
            entries = [h for h in history if h["date"]==d]; total=len(entries); taken=sum(1 for h in entries if h["taken"])
            c.setFont("Helvetica",10); c.drawString(60,y,f"{d}: {taken}/{total} doses taken"); y -= 14
            if y < 80: c.showPage(); y = h-60
        y -= 6; c.setFont("Helvetica-Bold",12); c.drawString(60,y,"Today's Scheduled Doses:"); y -= 16
        for m in meds_today:
            c.setFont("Helvetica",10); c.drawString(60,y,f"- {m['name']} @ {m['dose_time']} | taken: {m['taken']}"); y -= 12
            if y < 80: c.showPage(); y = h-60
        c.save(); buf.seek(0); return buf.getvalue()
    except Exception:
        # Simple plain-text PDF using reportlab missing -> return empty bytes
        return b""

# --- Header ---
col1,col2 = st.columns([2,1])
with col1:
    st.title("MedTimer – Daily Medicine Companion")
    st.write("Track doses, build streaks, and export a weekly report.")
with col2:
    st.metric("Today", today().strftime("%a, %d %b %Y"))

# --- Manage Medicines ---
st.subheader("Manage Medicines")
mode = st.radio("Mode", ["Add","Edit"], key="mode")

if mode == "Add":
    name = st.text_input("Medicine name", key="add_name")
    note = st.text_input("Note (optional)", key="add_note")
    freq = st.number_input("Times per day", min_value=1, max_value=8, value=1, step=1, key="add_freq")
    st.write("Dose times:")
    new_times=[]
    for i in range(freq):
        t = st.time_input(f"Dose {i+1}", value=default_time_for_index(i), key=f"add_time_{i}")
        new_times.append(time_to_str(t))
    st.write("Repeat on days:")
    cols = st.columns(7); sel_days=[]
    for i,d in enumerate(WEEKDAYS):
        if cols[i].checkbox(d, value=True, key=f"add_day_{d}"): sel_days.append(d)
    if st.button("Add medicine"):
        if not name.strip(): st.warning("Enter a name."); st.stop()
        if name in st.session_state.meds: st.warning("Name exists. Edit instead."); st.stop()
        st.session_state.meds[name] = {"doses": new_times, "note": note, "days": sel_days or WEEKDAYS}
        st.success("Added medicine."); st.experimental_rerun()

else:
    meds = list(st.session_state.meds.keys())
    if not meds:
        st.info("No medicines. Switch to Add to create one.")
    else:
        target = st.selectbox("Select", meds, key="edit_target")
        info = st.session_state.meds.get(target, {"doses":["08:00"], "note":"", "days":WEEKDAYS})
        new_name = st.text_input("Name", value=target, key="edit_name")
        new_note = st.text_input("Note", value=info.get("note",""), key="edit_note")
        freq = st.number_input("Times per day", min_value=1, max_value=8, value=max(1,len(info.get("doses",[]))), step=1, key="edit_freq")
        st.write("Dose times:")
        new_times=[]
        for i in range(freq):
            default = parse_time_str(info["doses"][i]) if i < len(info["doses"]) else default_time_for_index(i)
            t = st.time_input(f"Dose {i+1}", value=default, key=f"edit_time_{i}")
            new_times.append(time_to_str(t))
        st.write("Repeat on days:")
        cols = st.columns(7); new_days=[]
        existing = set(info.get("days",WEEKDAYS))
        for i,d in enumerate(WEEKDAYS):
            if cols[i].checkbox(d, value=(d in existing), key=f"edit_day_{d}"): new_days.append(d)
        c1,c2 = st.columns([1,2])
        with c2:
            if st.button("Save changes"):
                if new_name != target and new_name in st.session_state.meds:
                    st.warning("Another medicine uses that name."); st.stop()
                if new_name != target:
                    for h in st.session_state.history:
                        if h["name"]==target: h["name"]=new_name
                st.session_state.meds.pop(target,None)
                st.session_state.meds[new_name] = {"doses": new_times, "note": new_note, "days": new_days or WEEKDAYS}
                st.success("Saved."); st.experimental_rerun()
        with c1:
            if st.button("Delete medicine"):
                st.session_state.meds.pop(target,None)
                st.warning("Deleted."); st.experimental_rerun()

# --- Today's checklist ---
st.subheader("Today's Checklist")
today_date = today(); now_dt = now(); wd = WEEKDAYS[today_date.weekday()]
scheduled_today=[]
if st.session_state.meds:
    for name,info in st.session_state.meds.items():
        if wd not in info.get("days",WEEKDAYS): continue
        st.markdown(f"**{name}** — {info.get('note') or 'No note'}")
        for dose in info.get("doses",[]):
            ensure_history_entry(name,dose,today_date)
            taken = get_taken(name,dose,today_date)
            status = status_for_dose(dose,taken,now_dt)
            label = {"taken":"green","upcoming":"yellow","missed":"red"}[status]
            c1,c2,c3,c4 = st.columns([2.5,1.2,1.2,1.2])
            with c1: st.write(f"⏰ {dose}")
            with c2: st.markdown(f"<span class='pill {label} small'>{status.capitalize()}</span>", unsafe_allow_html=True)
            with c3:
                key = f"chk_{name}_{dose}_{today_date}"
                chk = st.checkbox("Taken", value=taken, key=key)
                if chk != taken: set_taken(name,dose,today_date,chk)
            with c4:
                if status=="missed" and not get_taken(name,dose,today_date): st.error("Missed")
                elif status=="upcoming" and not get_taken(name,dose,today_date): st.warning("Upcoming")
                else: st.success("Done")
            scheduled_today.append({"name":name,"dose_time":dose,"taken":get_taken(name,dose,today_date)})
        st.divider()
else:
    st.info("No medicines scheduled. Add some above.")

# --- Adherence & streak ---
score = adherence_score(st.session_state.history,7)
st.session_state.streak = update_streak(st.session_state.history)
st.progress(min(int(score),100))
c1,c2,c3 = st.columns(3)
with c1: st.metric("7-Day Adherence", f"{score}%")
with c2:
    today_taken = sum(1 for h in st.session_state.history if h["date"]==today_date and h["taken"])
    today_total = sum(1 for h in st.session_state.history if h["date"]==today_date)
    st.metric("Today's Doses", f"{today_taken}/{today_total}")
with c3: st.metric("Perfect Streak", f"{st.session_state.streak} days")

if score >= 85: st.success("Fantastic adherence! Keep it up 💪")
elif score >= 60: st.info("You're on track.")
else: st.warning("Let's build momentum — small steps!")

if score >= 85:
    img = draw_trophy_image()
    if img: st.image(img, caption="High Adherence Award")

# --- Beep for missed/imminent ---
imminent=False
for h in st.session_state.history:
    if h["date"]!=today_date or h["taken"]: continue
    med_dt = dt.datetime.combine(today_date, parse_time_str(h["dose_time"]))
    if med_dt < now_dt or (med_dt - now_dt) <= dt.timedelta(minutes=5):
        imminent=True; break
if imminent:
    st.audio(generate_beep_wav(), format="audio/wav")

# --- PDF export ---
st.subheader("Download & Export")
pdf_bytes = build_report_pdf_bytes(st.session_state.history, scheduled_today)
if pdf_bytes:
    st.download_button("Download weekly adherence report (PDF)", pdf_bytes, file_name="MedTimer_Report.pdf", mime="application/pdf")
else:
    st.caption("PDF generation not available in this environment.")

# --- Motivation ---
st.subheader("Motivation of the Day")
tips = [
    "Taking medicines on time is a vote for your future self.",
    "Small habits, big impact—consistency builds confidence.",
    "You’re not alone—set gentle reminders and celebrate wins.",
    "Celebrate every day you complete your doses."
]
st.info(tips[dt.datetime.now().day % len(tips)])

