import streamlit as st
from datetime import datetime, date, timedelta
import pandas as pd

st.set_page_config(page_title="MedTimer", layout="centered")

WEEKDAYS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

# ------------------ SESSION STATE ------------------
if "page" not in st.session_state:
    st.session_state.page = "today"

if "meds" not in st.session_state:
    st.session_state.meds = {
        "Aspirin": {"times":["12:00"],"note":"After lunch","taken_today":[],"days":WEEKDAYS.copy()}
    }

if "history" not in st.session_state:
    st.session_state.history = []

if "daily_scores" not in st.session_state:
    st.session_state.daily_scores = {}

if "last_date" not in st.session_state:
    st.session_state.last_date = date.today().isoformat()

# ------------------ HELPERS ------------------
def go(p): st.session_state.page = p
def today(): return date.today().isoformat()
def now(): return datetime.now().strftime("%H:%M")

def rollover():
    if st.session_state.last_date != today():
        y = st.session_state.last_date
        taken = sum(1 for h in st.session_state.history if h["date"]==y)
        scheduled = 0
        for m in st.session_state.meds.values():
            scheduled += len(m["times"])
            m["taken_today"] = []
        score = int((taken/scheduled)*100) if scheduled else 0
        st.session_state.daily_scores[y] = {"taken":taken,"scheduled":scheduled,"score":score}
        st.session_state.last_date = today()

rollover()

def mark(med,time):
    st.session_state.meds[med]["taken_today"].append(time)
    st.session_state.history.append({"med":med,"time":time,"date":today()})
    st.rerun()

def undo(med,time):
    st.session_state.meds[med]["taken_today"].remove(time)
    for i in range(len(st.session_state.history)-1,-1,-1):
        if st.session_state.history[i]["med"]==med and st.session_state.history[i]["time"]==time:
            st.session_state.history.pop(i)
            break
    st.rerun()

def delete_med(med):
    st.session_state.meds.pop(med)
    st.rerun()

# ------------------ NAV ------------------
st.markdown("<h1 style='text-align:center;'>MedTimer</h1>", unsafe_allow_html=True)
c1,c2,c3,c4 = st.columns(4)
with c1: st.button("Today",on_click=go,args=("today",))
with c2: st.button("All Meds",on_click=go,args=("all",))
with c3: st.button("Add / Edit",on_click=go,args=("add",))
with c4: st.button("Summary",on_click=go,args=("summary",))

st.write("")

# ------------------ TODAY ------------------
if st.session_state.page=="today":
    st.header("Today's Doses")

    for med,info in st.session_state.meds.items():
        for t in info["times"]:
            taken = t in info["taken_today"]
            bg = "#b7f5c2" if taken else "#bfe4ff"

            st.markdown(f"""
            <div style='background:{bg};padding:14px;border-radius:12px;margin-bottom:10px;'>
            <div style='color:black;font-size:18px;font-weight:600;'>{med} — {t}</div>
            <div style='color:black;font-size:14px;'>{info["note"]}</div>
            </div>
            """,unsafe_allow_html=True)

            c1,c2 = st.columns(2)
            with c1:
                if not taken and st.button("Take",key=f"t{med}{t}"):
                    mark(med,t)
            with c2:
                if taken and st.button("Undo",key=f"u{med}{t}"):
                    undo(med,t)

    taken = sum(len(m["taken_today"]) for m in st.session_state.meds.values())
    scheduled = sum(len(m["times"]) for m in st.session_state.meds.values())
    score = int((taken/scheduled)*100) if scheduled else 0

    st.subheader("Daily Score")
    st.progress(score/100)
    st.write(f"Score: {score}%")
    st.write(f"Scheduled: {scheduled}")
    st.write(f"Taken: {taken}")

# ------------------ ALL MEDS ------------------
elif st.session_state.page=="all":
    st.header("All Medications")
    for med,info in st.session_state.meds.items():
        st.markdown(f"**{med}** — {', '.join(info['times'])}")
        st.write(info["note"])
        if st.button("Delete",key=f"d{med}"):
            delete_med(med)

# ------------------ ADD / EDIT ------------------
elif st.session_state.page=="add":
    st.header("Add Medicine")

    name = st.text_input("Medicine name")
    note = st.text_input("Note")
    freq = st.number_input("How many times per day?",1,6,1)

    times=[]
    for i in range(freq):
        times.append(st.time_input(f"Time {i+1}").strftime("%H:%M"))

    if st.button("Add"):
        st.session_state.meds[name]={
            "times":times,
            "note":note,
            "taken_today":[],
            "days":WEEKDAYS.copy()
        }
        st.success("Added")
        st.rerun()

