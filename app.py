import streamlit as st
from datetime import datetime, date, timedelta
from PIL import Image, ImageDraw
import pandas as pd

st.set_page_config(page_title="MedTimer", layout="centered")

# REMOVE TOP BAR
st.markdown("""<style>
header {visibility: hidden;}
</style>""", unsafe_allow_html=True)

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ---------- SESSION INIT ----------
if "page" not in st.session_state:
    st.session_state.page = "today"

if "meds" not in st.session_state:
    st.session_state.meds = {
        "Aspirin": {"time": ["12:00"], "note": "After lunch", "days": WEEKDAYS.copy(), "freq": 1},
    }

if "history" not in st.session_state:
    st.session_state.history = []

# ---------- HELPERS ----------
def go(p): st.session_state.page = p
def today_str(): return date.today().isoformat()

def parse_time(hm): return datetime.strptime(hm, "%H:%M").time()

def is_taken(med, hm):
    return any(h["med"] == med and h["time"] == hm and h["date"] == today_str()
               for h in st.session_state.history)

def schedule_today(med_info):
    if med_info["days"] and WEEKDAYS[date.today().weekday()] not in med_info["days"]:
        return 0
    return len(med_info["time"])

def compute_today():
    scheduled = sum(schedule_today(i) for i in st.session_state.meds.values())
    taken = sum(1 for h in st.session_state.history if h["date"] == today_str())
    score = int((taken / scheduled) * 100) if scheduled > 0 else 0
    return scheduled, taken, score

def mark_taken(med, hm):
    st.session_state.history.append({"med": med, "date": today_str(), "time": hm})
    st.rerun()

def unmark_taken(med, hm):
    for i in range(len(st.session_state.history)-1, -1, -1):
        h = st.session_state.history[i]
        if h["med"] == med and h["time"] == hm and h["date"] == today_str():
            st.session_state.history.pop(i)
            break
    st.rerun()

def smile(score, size=200):
    img = Image.new("RGB", (size,size), "white")
    d = ImageDraw.Draw(img)
    face = "#b7f5c2" if score>=80 else ("#fff2b2" if score>=50 else "#ffb3b3")
    m = size*0.08
    d.ellipse([m,m,size-m,size-m], fill=face, outline="black")
    return img

# ---------- HEADER ----------
st.markdown("<h1 style='text-align:center;'>MedTimer</h1>", unsafe_allow_html=True)

c1,c2,c3 = st.columns([1,1,1])
with c1:
    if st.button("Today"): go("today")
with c2:
    if st.button("All Meds"): go("all_meds")
with c3:
    if st.button("Add / Edit"): go("add")

# ---------- TODAY PAGE ----------
if st.session_state.page == "today":
    st.header("Today's Doses")

    left, right = st.columns([2,1])

    with left:
        now_t = parse_time(datetime.now().strftime("%H:%M"))
        for med, info in st.session_state.meds.items():
            for hm in info["time"]:
                taken = is_taken(med, hm)
                hm_t = parse_time(hm)

                if taken:
                    bg = "#b7f5c2"; status = "Taken"
                else:
                    bg = "#fff7b0" if now_t <= hm_t else "#ffb3b3"
                    status = "Upcoming" if now_t <= hm_t else "Missed"

                st.markdown(f"""
                <div style='background:{bg}; padding:16px; border-radius:12px; margin-bottom:10px; color:black;'>
                    <b style='color:black'>{med} — {hm}</b><br>
                    <span style='color:black'>{info["note"]}</span><br>
                    <i style='color:black'>{status}</i>
                </div>
                """, unsafe_allow_html=True)

                cA, cB = st.columns([1,1])
                with cA:
                    if not taken and st.button("Completed"):
                        mark_taken(med, hm)
                with cB:
                    if taken and st.button("Undo"):
                        unmark_taken(med, hm)

    with right:
        st.header("Daily Adherence")
        sched, taken, score = compute_today()
        st.progress(score/100 if score <= 100 else 1)
        st.write(f"Score: {score}%")
        st.write(f"Scheduled: {sched}")
        st.write(f"Taken: {taken}")
        st.image(smile(score))

# ---------- ALL MEDS ----------
elif st.session_state.page == "all_meds":
    st.header("All Medications")
    rows = []
    for n, info in st.session_state.meds.items():
        rows.append({
            "Name": n,
            "Times": ", ".join(info["time"]),
            "Days": ", ".join(info["days"]),
            "Note": info["note"]
        })
    st.dataframe(pd.DataFrame(rows), height=300)

# ---------- ADD / EDIT ----------
elif st.session_state.page == "add":
    st.header("Add / Edit Medicines")

    mode = st.radio("Mode", ["Add", "Edit"])

    if mode == "Add":
        name = st.text_input("Medicine name")
        note = st.text_input("Note")
        freq = st.number_input("How many times per day?", min_value=1, max_value=10, value=1)

        st.write("Enter dose times:")
        new_times = []
        for i in range(freq):
            tm = st.time_input(f"Dose {i+1}", value=datetime.strptime("08:00","%H:%M").time())
            new_times.append(tm.strftime("%H:%M"))

        st.write("Repeat on days:")
        day_cols = st.columns(7)
        selected_days = []
        for i,d in enumerate(WEEKDAYS):
            if day_cols[i].checkbox(d, True):
                selected_days.append(d)

        if st.button("Add"):
            st.session_state.meds[name] = {
                "time": new_times,
                "note": note,
                "days": selected_days,
                "freq": freq
            }
            st.rerun()

    else:
        meds = list(st.session_state.meds.keys())
        target = st.selectbox("Select medicine", meds)
        info = st.session_state.meds[target]

        new_name = st.text_input("Name", target)
        new_note = st.text_input("Note", info["note"])

        if st.button("Save"):
            st.session_state.meds[new_name] = info
            st.session_state.meds.pop(target)
            st.rerun()

