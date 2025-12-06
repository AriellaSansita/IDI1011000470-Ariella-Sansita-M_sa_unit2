import streamlit as st
import datetime as dt
from datetime import datetime
from io import BytesIO
import math, wave, struct

# --- Config ---
st.set_page_config("MedTimer – Daily Medicine Companion", "💊", layout="wide")

# --- Session State ---
if "meds" not in st.session_state:
    st.session_state.meds = {}
if "history" not in st.session_state:
    st.session_state.history = []
if "streak" not in st.session_state:
    st.session_state.streak = 0

WEEKDAYS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
COMMON_MEDS = ["Paracetamol","Ibuprofen","Aspirin","Vitamin C","Amoxicillin","Cetirizine","Metformin"]

# --- Helpers ---
def today(): return dt.date.today()
def now(): return dt.datetime.now()
def parse_time_str(s): 
    try: hh,mm=map(int,s.split(":")); return dt.time(hh,mm)
    except: return dt.datetime.now().time().replace(second=0,microsecond=0)
def time_str(t): return t.strftime("%H:%M")
def default_time(i): return dt.time(min(23,8+4*i),0)

def get_history(name,dose,date):
    for h in st.session_state.history:
        if h["date"]==date and h["name"]==name and h["dose_time"]==dose:
            return h
    return None

def ensure_history(name,dose,date):
    if not get_history(name,dose,date):
        st.session_state.history.append({"date":date,"name":name,"dose_time":dose,"taken":False})

def set_taken(name,dose,date,val):
    h=get_history(name,dose,date)
    if h:h["taken"]=val
    else: st.session_state.history.append({"date":date,"name":name,"dose_time":dose,"taken":val})

def get_taken(name,dose,date):
    h=get_history(name,dose,date)
    return bool(h["taken"]) if h else False

def status_for_dose(dose,taken,now_dt):
    if taken: return "Taken"
    dt_obj = dt.datetime.combine(now_dt.date(), parse_time_str(dose))
    return "Upcoming" if dt_obj>now_dt else "Missed"

def adherence_score(history,days=7):
    cutoff = today()-dt.timedelta(days=days-1)
    recent=[h for h in history if h["date"]>=cutoff]
    if not recent: return 0.0
    total=len(recent); taken=sum(1 for h in recent if h["taken"])
    return round(100*taken/max(total,1),1)

def update_streak(history):
    s=0; day=today()
    while True:
        entries=[h for h in history if h["date"]==day]
        if not entries: break
        if all(h["taken"] for h in entries): s+=1; day-=dt.timedelta(days=1)
        else: break
    return s

def draw_trophy():
    try:
        from PIL import Image, ImageDraw
        img=Image.new("RGB",(300,300),"white"); d=ImageDraw.Draw(img)
        d.rectangle([90,100,210,160],fill="#FFD700"); d.ellipse([60,100,120,160],fill="#FFD700"); d.ellipse([180,100,240,160],fill="#FFD700")
        d.rectangle([140,160,160,230],fill="#DAA520"); d.rectangle([110,230,190,250],fill="#8B4513")
        return img
    except: return None

def beep(seconds=0.6,freq=880):
    framerate=44100; nframes=int(seconds*framerate); buf=BytesIO()
    with wave.open(buf,'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(framerate)
        for i in range(nframes):
            val=int(32767*math.sin(2*math.pi*freq*(i/framerate)))
            w.writeframes(struct.pack('<h',val))
    buf.seek(0); return buf

def build_pdf(history,meds_today):
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        buf=BytesIO(); c=canvas.Canvas(buf,pagesize=A4)
        w,h=A4;y=h-60
        c.setFont("Helvetica-Bold",16); c.drawString(60,y,"MedTimer – Weekly Report");y-=28
        c.setFont("Helvetica",10); c.drawString(60,y,datetime.now().strftime("Generated: %Y-%m-%d %H:%M"));y-=20
        score=adherence_score(history,7); c.setFont("Helvetica-Bold",12); c.drawString(60,y,f"7-Day Adherence: {score}%");y-=18
        for i in range(7):
            d=today()-dt.timedelta(days=6-i)
            entries=[h for h in history if h["date"]==d]
            total=len(entries); taken=sum(1 for h in entries if h["taken"])
            c.setFont("Helvetica",10); c.drawString(60,y,f"{d}: {taken}/{total} doses taken");y-=14
            if y<80: c.showPage();y=h-60
        y-=6;c.setFont("Helvetica-Bold",12); c.drawString(60,y,"Today's Scheduled Doses:");y-=16
        for m in meds_today:
            c.setFont("Helvetica",10); c.drawString(60,y,f"- {m['name']} @ {m['dose_time']} | taken: {m['taken']}");y-=12
            if y<80: c.showPage();y=h-60
        # All medicines summary
        y-=6;c.setFont("Helvetica-Bold",12); c.drawString(60,y,"All Medicines:");y-=16
        for m,info in st.session_state.meds.items():
            c.setFont("Helvetica-Bold",11); c.drawString(60,y,m);y-=14
            c.setFont("Helvetica",10)
            c.drawString(60,y,f"Times: {', '.join(info['doses'])}");y-=12
            c.drawString(60,y,f"Note: {info['note']}");y-=12
            c.drawString(60,y,f"Days: {', '.join(info['days'])}");y-=14
            if y<80: c.showPage();y=h-60
        c.save(); buf.seek(0); return buf.getvalue()
    except: return b""

# --- Header ---
col1,col2=st.columns([2,1])
with col1: st.title("MedTimer – Daily Medicine Companion"); st.write("Track doses, streaks, and export reports.")
with col2: st.metric("Today", today().strftime("%a, %d %b %Y"))

# --- Manage Medicines ---
st.subheader("Manage Medicines")
mode=st.radio("Mode",["Add","Edit"],key="mode")

if mode=="Add":
    # Custom Add: dropdown or free text
    med_choice=st.selectbox("Select or type medicine",["--Add new--"]+COMMON_MEDS,key="custom_add")
    if med_choice=="--Add new--":
        name=st.text_input("Medicine Name", key="new_name")
    else: name=med_choice
    note=st.text_input("Note (optional)",key="new_note")
    freq=st.number_input("Times per day",1,8,1,1,key="new_freq")
    new_times=[]
    for i in range(freq):
        t=st.time_input(f"Dose {i+1}",value=default_time(i),key=f"new_time_{i}")
        new_times.append(time_str(t))
    st.write("Repeat on days:")
    cols=st.columns(7); sel_days=[]
    for i,d in enumerate(WEEKDAYS):
        if cols[i].checkbox(d,value=True,key=f"new_day_{d}"): sel_days.append(d)
    if st.button("Add medicine"):
        if not name.strip(): st.warning("Enter a name."); st.stop()
        if name in st.session_state.meds: st.warning("Name exists. Edit instead."); st.stop()
        st.session_state.meds[name]={"doses":new_times,"note":note,"days":sel_days or WEEKDAYS}
        st.success("Added."); st.experimental_rerun()
else:
    meds=list(st.session_state.meds.keys())
    if not meds: st.info("No medicines. Switch to Add.")
    else:
        target=st.selectbox("Select",meds,key="edit_target")
        info=st.session_state.meds.get(target,{"doses":["08:00"],"note":"","days":WEEKDAYS})
        new_name=st.text_input("Name",value=target,key="edit_name")
        new_note=st.text_input("Note",value=info.get("note",""),key="edit_note")
        freq=st.number_input("Times per day",1,8,max(1,len(info.get("doses",[]))),1,key="edit_freq")
        new_times=[]
        for i in range(freq):
            t=st.time_input(f"Dose {i+1}",value=parse_time_str(info["doses"][i]) if i<len(info["doses"]) else default_time(i),key=f"edit_time_{i}")
            new_times.append(time_str(t))
        st.write("Repeat on days:")
        cols=st.columns(7); new_days=[]
        existing=set(info.get("days",WEEKDAYS))
        for i,d in enumerate(WEEKDAYS):
            if cols[i].checkbox(d,value=(d in existing),key=f"edit_day_{d}"): new_days.append(d)
        c1,c2=st.columns([1,2])
        with c2:
            if st.button("Save changes"):
                if new_name!=target and new_name in st.session_state.meds: st.warning("Name exists."); st.stop()
                if new_name!=target:
                    for h in st.session_state.history:
                        if h["name"]==target: h["name"]=new_name
                st.session_state.meds.pop(target,None)
                st.session_state.meds[new_name]={"doses":new_times,"note":new_note,"days":new_days or WEEKDAYS}
                st.success("Saved"); st.experimental_rerun()
        with c1:
            if st.button("Delete medicine"):
                st.session_state.meds.pop(target,None); st.warning("Deleted"); st.experimental_rerun()

# --- All Medicines Summary ---
st.subheader("All Medicines Summary")
if st.session_state.meds:
    for m,info in st.session_state.meds.items():
        st.write(f"### {m}")
        st.write(f"Times: {', '.join(info['doses'])}")
        st.write(f"Note: {info['note']}")
        st.write(f"Days: {', '.join(info['days'])}")
        st.write("---")
else: st.info("No medicines yet.")

# --- Today's Checklist ---
st.subheader("Today's Checklist")
today_date=today(); now_dt=now(); wd=WEEKDAYS[today_date.weekday()]
scheduled_today=[]
if st.session_state.meds:
    for name,info in st.session_state.meds.items():
        if wd not in info.get("days",WEEKDAYS): continue
        st.write(f"### {name}")
        for dose in info.get("doses",[]):
            ensure_history(name,dose,today_date)
            taken=get_taken(name,dose,today_date)
            status=status_for_dose(dose,taken,now_dt)
            col1,col2,col3=st.columns([2,1,1])
            with col1: st.write(f"⏰ {dose}")
            with col2:
                btn_label=status
                if st.button(btn_label,key=f"btn_{name}_{dose}"):
                    set_taken(name,dose,today_date,not taken)
                    st.experimental_rerun()
            with col3:
                if st.button("Edit",key=f"edit_{name}_{dose}"):
                    st.session_state["edit_name"]=name; st.session_state["edit_dose"]=dose
            scheduled_today.append({"name":name,"dose_time":dose,"taken":get_taken(name,dose,today_date)})
        st.divider()
else: st.info("No medicines scheduled today.")

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
else: st.warning("Let's build momentum!")

img=draw_trophy()
if img and score>=85: st.image(img,caption="High Adherence Award")

# --- Beep for missed/imminent ---
imminent=False
for h in st.session_state.history:
    if h["date"]!=today_date or h["taken"]: continue
    med_dt=dt.datetime.combine(today_date,parse_time_str(h["dose_time"]))
    if med_dt<now_dt or (med_dt-now_dt)<=dt.timedelta(minutes=5): imminent=True; break
if imminent: st.audio(beep(),format="audio/wav")

# --- PDF Export ---
st.subheader("Download Weekly Report")
pdf_bytes=build_pdf(st.session_state.history,scheduled_today)
if pdf_bytes: st.download_button("Download PDF",pdf_bytes,file_name="MedTimer_Report.pdf",mime="application/pdf")
else: st.caption("PDF generation unavailable.")

# --- Motivation ---
st.subheader("Motivation of the Day")
tips=[
    "Taking medicines on time is a vote for your future self.",
    "Small habits, big impact—consistency builds confidence.",
    "You’re not alone—set gentle reminders and celebrate wins.",
    "Celebrate every day you complete your doses."
]
st.info(tips[datetime.now().day%len(tips)])
