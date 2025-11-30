import streamlit as st
from datetime import datetime, date, timedelta
from PIL import Image, ImageDraw
import pandas as pd
import random

st.set_page_config(page_title="MedTimer", layout="centered")

CARD_TEXT_COLOR = "black"
WEEKDAYS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

MOTIVATIONAL = [
    "One dose at a time — you're doing great!",
    "Taking meds is taking care of your future self.",
    "Small habits create big health.",
    "Consistency is strength. Keep going!"
]

TIPS = [
    "Keep water nearby when taking meds.",
    "Pair meds with a daily routine (e.g., breakfast).",
    "Use alarms 10 minutes before dose time.",
    "Store pills in a visible, consistent place."
]

# -----------------------
# SESSION STATE
# -----------------------
if "page" not in st.session_state:
    st.session_state.page = "today"

if "meds" not in st.session_state:
    st.session_state.meds = {
        "Aspirin":{"time":"12:00","note":"After lunch","taken_today":False,"days":WEEKDAYS.copy(),"freq":"Once"},
        "Vitamin D":{"time":"18:00","note":"With dinner","taken_today":False,"days":["Mon","Wed","Fri"],"freq":"Once"},
        "Iron":{"time":"08:00","note":"Before breakfast","taken_today":False,"days":["Mon","Tue","Wed","Thu","Fri"],"freq":"Once"}
    }

if "history" not in st.session_state:
    st.session_state.history = []

if "daily_scores" not in st.session_state:
    st.session_state.daily_scores = {}

if "last_rollover_date" not in st.session_state:
    st.session_state.last_rollover_date = date.today().isoformat()

# -----------------------
# FUNCTIONS
# -----------------------
def go(p): st.session_state.page = p
def today_str(): return date.today().isoformat()
def now_time(): return datetime.now().strftime("%H:%M")

def compute_today():
    sched = len(st.session_state.meds)
    taken = sum(1 for m in st.session_state.meds.values() if m["taken_today"])
    score = int((taken/sched)*100) if sched else 0
    return sched, taken, score

def mark_taken(med):
    st.session_state.meds[med]["taken_today"] = True
    st.session_state.history.append({"med":med,"date":today_str(),"time":now_time()})
    st.rerun()

def unmark_taken(med):
    st.session_state.meds[med]["taken_today"] = False
    st.rerun()

def delete_med(med):
    st.session_state.meds.pop(med)
    st.rerun()

# -----------------------
# SMILEY DRAW (FIXED)
# -----------------------
def draw_smiley(score, size_px=240):
    img = Image.new("RGB",(size_px,size_px),"white")
    d = ImageDraw.Draw(img)

    face = "#b7f5c2" if score >= 80 else "#fff2b2" if score >=50 else "#ffb3b3"
    m = size_px*0.1
    d.ellipse([m,m,size_px-m,size_px-m],fill=face,outline="black")

    eye = int(size_px*0.05)
    d.ellipse([size_px*0.35-eye,size_px*0.35-eye,size_px*0.35+eye,size_px*0.35+eye],fill="black")
    d.ellipse([size_px*0.65-eye,size_px*0.35-eye,size_px*0.65+eye,size_px*0.35+eye],fill="black")

    d.arc([size_px*0.3,size_px*0.45,size_px*0.7,size_px*0.78],start=0,end=180,fill="black",width=4)
    return img

# -----------------------
# HEADER
# -----------------------
st.markdown("<h1 style='text-align:center;'>MedTimer</h1>",unsafe_allow_html=True)

nav1,nav2,nav3 = st.columns(3)
with nav1:
    if st.button("Today"): go("today")
with nav2:
    if st.button("All Meds"): go("all_meds")
with nav3:
    if st.button("Add / Edit"): go("add")

# -----------------------
# TODAY PAGE
# -----------------------
if st.session_state.page == "today":
    st.header("Today's Doses")

    left,right = st.columns([2,1])

    with left:
        for med,info in st.session_state.meds.items():
            due = info["time"]
            taken = info["taken_today"]
            now = now_time()

            if taken:
                bg = "#b7f5c2"; status = "Taken"
            else:
                bg = "#fff2a8" if now <= due else "#ffb3b3"
                status = "Upcoming" if now <= due else "Missed"

            st.markdown(f"""
            <div style="background:{bg};padding:14px;border-radius:12px;margin-bottom:10px;">
            <b style="color:black;">{med} — {due}</b><br>
            <span style="color:black;">{info['note']}</span><br>
            <i>{status}</i>
            </div>
            """,unsafe_allow_html=True)

            c1,c2,c3 = st.columns(3)
            with c1:
                if not taken and st.button(f"Take {med}",key=f"t{med}"):
                    mark_taken(med)
            with c2:
                if taken and st.button("Undo",key=f"u{med}"):
                    unmark_taken(med)
            with c3:
                if st.button("Delete",key=f"d{med}"):
                    delete_med(med)

    with right:
        sched,taken,score = compute_today()
        prog = min(max(score/100,0),1)

        st.header("Daily Summary")
        st.progress(prog)
        st.markdown(f"**Score:** {score}%")
        st.markdown(f"**Scheduled:** {sched}")
        st.markdown(f"**Taken:** {taken}")
        st.info(random.choice(MOTIVATIONAL))
        st.success(random.choice(TIPS))
        st.image(draw_smiley(score))

# -----------------------
# ALL MEDS PAGE (UNCHANGED TABLE)
# -----------------------
elif st.session_state.page == "all_meds":
    st.header("All Medications")
    if len(st.session_state.meds)==0:
        st.info("No medicines yet.")
    else:
        df = pd.DataFrame([
            {"Name": name,
             "Time": info.get("time",""),
             "Note": info.get("note",""),
             "Days": ",".join(info.get("days",[])) if info.get("days") else "Every day",
             "Freq": info.get("freq","Once"),
             "Taken Today": info.get("taken_today", False)}
            for name,info in st.session_state.meds.items()
        ])
        st.dataframe(df,height=300)

# -----------------------
# ADD / EDIT PAGE
# -----------------------
elif st.session_state.page == "add":
    st.header("Add / Edit Medicines")
    mode = st.radio("Mode",["Add New","Edit Existing"])

    if mode == "Add New":
        name = st.text_input("Medicine name")
        time_val = st.time_input("Time")
        note = st.text_input("Note")

        if st.button("Add medicine"):
            st.session_state.meds[name] = {
                "time": time_val.strftime("%H:%M"),
                "note": note,
                "taken_today": False,
                "days": WEEKDAYS.copy(),
                "freq": "Once"
            }
            st.rerun()

    else:
        target = st.selectbox("Select medicine",list(st.session_state.meds.keys()))
        info = st.session_state.meds[target]

        new_time = st.time_input("Time",datetime.strptime(info["time"],"%H:%M").time())
        new_note = st.text_input("Note",info["note"])

        if st.button("Save Changes"):
            info["time"] = new_time.strftime("%H:%M")
            info["note"] = new_note
            st.rerun()

        st.error("DANGER ZONE")
        if st.button("DELETE THIS MEDICINE"):
            delete_med(target)

