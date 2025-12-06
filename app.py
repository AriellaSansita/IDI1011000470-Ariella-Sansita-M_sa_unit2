import streamlit as st
import datetime as dt
from datetime import datetime
from io import BytesIO
import math, wave, struct

# --- Session state ---
if "meds" not in st.session_state or not isinstance(st.session_state.meds, dict):
    st.session_state.meds = {}
if "history" not in st.session_state:
    st.session_state.history = []
if "streak" not in st.session_state:
    st.session_state.streak = 0

WEEKDAYS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
CUSTOM_MED_LIST = ["Aspirin", "Paracetamol", "Vitamin C", "Ibuprofen", "Amoxicillin", "Cetirizine", "Metformin"]

# --- Helpers ---
def today(): return dt.date.today()
def now(): return dt.datetime.now()
def time_to_str(t: dt.time) -> str: return t.strftime("%H:%M")
def parse_time_str(s: str) -> dt.time:
    try:
        hh, mm = map(int, s.split(":"))
        return dt.time(hh, mm)
    except Exception:
        return dt.datetime.now().time().replace(second=0, microsecond=0)
def default_time_for_index(i: int) -> dt.time:
    hour = max(0, min(23, 8 + 4*i)); return dt.time(hour,0)

def get_history_entry(name, dose_time, date):
    for h in st.session_state.history:
        if h["date"] == date and h["name"] == name and h["dose_time"] == dose_time:
            return h
    return None

def ensure_history_entry(name, dose_time, date):
    if get_history_entry(name,dose_time,date) is None:
        st.session_state.history.append({"date":date,"name":name,"dose_time":dose_time,"taken":False})

def set_taken(name,dose_time,date,val):
    h=get_history_entry(name,dose_time,date)
    if h: h["taken"]=val
    else: st.session_state.history.append({"date":date,"name":name,"dose_time":dose_time,"taken":val})

def get_taken(name,dose_time,date):
    h=get_history_entry(name,dose_time,date)
    return h["taken"] if h else False

def status_for_dose(dose_time_str,taken,now_dt):
    if taken: return "Taken"
    med_time=parse_time_str(dose_time_str)
    med_dt=dt.datetime.combine(now_dt.date(),med_time)
    return "Upcoming" if med_dt>now_dt else "Missed"

def adherence_score(history,days=7):
    if not history: return 0.0
    cutoff=today()-dt.timedelta(days=days-1)
    recent=[h for h in history if h["date"]>=cutoff]
    if not recent: return 0.0
    total=len(recent)
    taken=sum(1 for h in recent if h["taken"])
    return round(100*taken/max(total,1),1)

def update_streak(history):
    s=0; day=today()
    while True:
        entries=[h for h in history if h["date"]==day]
        if not entries: break
        total=len(entries); taken=sum(1 for h in entries if h["taken"])
        if total>0 and taken==total:
            s+=1; day-=dt.timedelta(days=1)
        else: break
    return s

def draw_trophy_image():
    try:
        from PIL import Image, ImageDraw
        img=Image.new("RGB",(300,300),"white"); d=ImageDraw.Draw(img)
        d.rectangle([90,100,210,160],fill="#FFD700"); d.ellipse([60,100,120,160],fill="#FFD700"); d.ellipse([180,100,240,160],fill="#FFD700")
        d.rectangle([140,160,160,230],fill="#DAA520"); d.rectangle([110,230,190,250],fill="#8B4513")
        return img
    except: return None

def generate_beep_wav(seconds=0.6,freq=880):
    framerate=44100; nframes=int(seconds*framerate); buf=BytesIO()
    with wave.open(buf,'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(framerate)
        for i in range(nframes):
            val=int(32767.0*math.sin(2*math.pi*freq*(i/framerate)))
            w.writeframes(struct.pack('<h',val))
    buf.seek(0); return buf

def build_report_pdf_bytes(history, meds_today):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        buf=BytesIO(); c=canvas.Canvas(buf,pagesize=A4)
        w,h=A4; y=h-60
        c.setFont("Helvetica-Bold",16); c.drawString(60,y,"MedTimer – Weekly Adherence Report"); y-=28
        c.setFont("Helvetica",10); c.drawString(60,y,datetime.now().strftime("Generated: %Y-%m-%d %H:%M")); y-=20
        score=adherence_score(history,7); c.setFont("Helvetica-Bold",12); c.drawString(60,y,f"7-Day Adherence: {score}%"); y-=18
        cutoff=today()-dt.timedelta(days=6)
        for i in range(7):
            d=cutoff+dt.timedelta(days=i)
            entries=[h for h in history if h["date"]==d]; total=len(entries); taken=sum(1 for h in entries if h["taken"])
            c.setFont("Helvetica",10); c.drawString(60,y,f"{d}: {taken}/{total} doses taken"); y-=14
            if y<80: c.showPage(); y=h-60
        y-=6; c.setFont("Helvetica-Bold",12); c.drawString(60,y,"Today's Scheduled Doses:"); y-=16
        for m in meds_today:
            c.setFont("Helvetica",10); c.drawString(60,y,f"- {m['name']} @ {m['dose_time']} | Taken: {m['taken']}"); y-=12
            if y<80: c.showPage(); y=h-60
        c.save(); buf.seek(0); return buf.getvalue()
    except: return b""

# --- Header ---
col1,col2=st.columns([2,1])
with col1:
    st.title("MedTimer – Daily Medicine Companion")
    st.write("Track doses, build streaks, and export a weekly report.")
with col2:
    st.metric("Today", today().strftime("%a, %d %b %Y"))

# --- Manage Medicines ---
st.subheader("Manage Medicines")
mode=st.radio("Mode",["Add","Edit"],key="mode")

# --- Add Medicine ---
if mode=="Add":
    # Custom Add
    med_choice=st.selectbox("Choose medicine or type your own",["--Custom--"]+CUSTOM_MED_LIST)
    name_text=st.text_input("If custom, type medicine name",key="custom_name")
    name=name_text if med_choice=="--Custom--" else med_choice

    note=st.text_input("Note (optional)",key="add_note")
    freq=st.number_input("Times per day",1,8,1,1,key="add_freq")
    new_times=[]
    for i in range(freq):
        t=st.time_input(f"Dose {i+1}",value=default_time_for_index(i),key=f"add_time_{i}")
        new_times.append(time_to_str(t))
    sel_days=[d for d in WEEKDAYS if st.checkbox(d,value=True,key=f"add_day_{d}")]
    if st.button("Add Medicine"):
        if not name.strip(): st.warning("Enter a name."); st.stop()
        if name in st.session_state.meds: st.warning("Name exists. Edit instead."); st.stop()
        st.session_state.meds[name]={"doses":new_times,"note":note,"days":sel_days or WEEKDAYS}
        st.success(f"Added {name}"); st.experimental_rerun()

# --- Edit Medicine ---
else:
    meds=list(st.session_state.meds.keys())
    if meds:
        target=st.selectbox("Select medicine",meds,key="edit_target")
        info=st.session_state.meds[target]
        new_name=st.text_input("Name",value=target,key="edit_name")
        new_note=st.text_input("Note",value=info.get("note",""),key="edit_note")
        freq=st.number_input("Times per day",1,8,value=max(1,len(info.get("doses",[]))),step=1,key="edit_freq")
        new_times=[]
        for i in range(freq):
            default=parse_time_str(info["doses"][i]) if i<len(info.get("doses",[])) else default_time_for_index(i)
            t=st.time_input(f"Dose {i+1}",value=default,key=f"edit_time_{i}")
            new_times.append(time_to_str(t))
        new_days=[d for d in WEEKDAYS if st.checkbox(d,d in info.get("days",WEEKDAYS),key=f"edit_day_{d}")]
        c1,c2=st.columns([1,2])
        with c2:
            if st.button("Save Changes"):
                if new_name!=target and new_name in st.session_state.meds:
                    st.warning("Another medicine has that name"); st.stop()
                if new_name!=target:
                    for h in st.session_state.history:
                        if h["name"]==target: h["name"]=new_name
                st.session_state.meds.pop(target,None)
                st.session_state.meds[new_name]={"doses":new_times,"note":new_note,"days":new_days or WEEKDAYS}
                st.success("Saved"); st.experimental_rerun()
        with c1:
            if st.button("Delete Medicine"):
                st.session_state.meds.pop(target,None)
                st.warning("Deleted"); st.experimental_rerun()
    else:
        st.info("No medicines to edit. Switch to Add.")

# --- Today's Checklist ---
st.subheader("Today's Checklist")
today_date=today(); now_dt=now(); wd=WEEKDAYS[today_date.weekday()]
scheduled_today=[]
if st.session_state.meds:
    for name,info in st.session_state.meds.items():
        if wd not in info.get("days",WEEKDAYS): continue
        st.write(f"Medicine: {name} — {info.get('note','No note')}")
        for dose in info.get("doses",[]):
            ensure_history_entry(name,dose,today_date)
            taken=get_taken(name,dose,today_date)
            status=status_for_dose(dose,taken,now_dt)
            col1,col2,col3=st.columns([1,1,1])
            with col1:
                if st.button(f"{dose} — {status}",key=f"{name}_{dose}"):
                    set_taken(name,dose,today_date,not taken)
                    st.experimental_rerun()
            with col2:
                if st.button("Edit",key=f"edit_{name}_{dose}"):
                    st.warning("Use Edit mode above to change doses or times")
            scheduled_today.append({"name":name,"dose_time":dose,"taken":get_taken(name,dose,today_date)})
        st.write("---")
else:
    st.info("No medicines scheduled today.")

# --- Adherence & Streak ---
score=adherence_score(st.session_state.history,7)
st.session_state.streak=update_streak(st.session_state.history)
st.progress(min(int(score),100))
c1,c2,c3=st.columns(3)
with c1: st.metric("7-Day Adherence",f"{score}%")
with c2:
    today_taken=sum(1 for h in st.session_state.history if h["date"]==today_date and h["taken"])
    today_total=sum(1 for h in st.session_state.history if h["date"]==today_date)
    st.metric("Today's Doses",f"{today_taken}/{today_total}")
with c3: st.metric("Perfect Streak",f"{st.session_state.streak} days")

if score>=85: st.success("Fantastic adherence! Keep it up 💪")
elif score>=60: st.info("You're on track.")
else: st.warning("Let's build momentum — small steps!")

# --- Beep for missed/imminent ---
imminent=False
for h in st.session_state.history:
    if h["date"]!=today_date or h["taken"]: continue
    med_dt=dt.datetime.combine(today_date,parse_time_str(h["dose_time"]))
    if med_dt<now_dt or (med_dt-now_dt)<=dt.timedelta(minutes=5):
        imminent=True; break
if imminent: st.audio(generate_beep_wav(),format="audio/wav")

# --- PDF Export ---
st.subheader("Download & Export")
pdf_bytes=build_report_pdf_bytes(st.session_state.history,scheduled_today)
if pdf_bytes:
    st.download_button("Download weekly adherence report (PDF)",pdf_bytes,file_name="MedTimer_Report.pdf",mime="application/pdf")
else: st.caption("PDF generation not available")

# --- Motivation ---
st.subheader("Motivation of the Day")
tips=[
    "Taking medicines on time is a vote for your future self.",
    "Small habits, big impact—consistency builds confidence.",
    "You’re not alone—set gentle reminders and celebrate wins.",
    "Celebrate every day you complete your doses."
]
st.info(tips[datetime.now().day%len(tips)])

# --- Display All Medicines Info ---
st.subheader("All Medicines")
if st.session_state.meds:
    for m,info in st.session_state.meds.items():
        st.write(f"### {m}")
        st.write(f"Times: {', '.join(info['doses'])}")
        st.write(f"Note: {info['note']}")
        st.write(f"Days: {', '.join(info['days'])}")
        st.write("---")
else:
    st.info("No medicines yet.")
