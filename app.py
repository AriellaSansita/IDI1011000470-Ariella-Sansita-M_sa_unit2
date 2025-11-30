import streamlit as st
from datetime import datetime, date
import pandas as pd

st.set_page_config(page_title="MedTimer", layout="centered")

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ---------------- SESSION STATE ----------------
if "page" not in st.session_state:
    st.session_state.page = "today"

if "meds" not in st.session_state:
    st.session_state.meds = {
        "Aspirin": {"time":"12:00","note":"After lunch","taken":False,"days":WEEKDAYS.copy()},
        "Vitamin D": {"time":"18:00","note":"With dinner","taken":False,"days":["Mon","Wed","Fri"]},
        "Iron": {"time":"08:00","note":"Before breakfast","taken":False,"days":["Mon","Tue","Wed","Thu","Fri"]},
    }

if "history" not in st.session_state:
    st.session_state.history = []

# ---------------- HELPERS ----------------
def go(p): st.session_state.page = p

def today(): return date.today().isoformat()

def compute_today():
    scheduled = sum(1 for m in st.session_state.meds.values())
    taken = sum(1 for m in st.session_state.meds.values() if m["taken"])
    score = int((taken/scheduled)*100) if scheduled else 0
    return scheduled, taken, score

def take_med(med):
    st.session_state.meds[med]["taken"] = True
    st.session_state.history.append({"med":med,"date":today()})
    st.rerun()

def undo_med(med):
    st.session_state.meds[med]["taken"] = False
    for i in range(len(st.session_state.history)-1, -1, -1):
        if st.session_state.history[i]["med"] == med:
            st.session_state.history.pop(i)
            break
    st.rerun()

def delete_med(med):
    st.session_state.meds.pop(med)
    st.session_state.history = [h for h in st.session_state.history if h["med"] != med]
    st.rerun()

# ---------------- HEADER ----------------
st.markdown("<h1 style='text-align:center;'>MedTimer</h1>", unsafe_allow_html=True)

c1,c2,c3 = st.columns(3)
with c1:
    if st.button("Today"): go("today")
with c2:
    if st.button("All Meds"): go("all_meds")
with c3:
    if st.button("Add / Edit"): go("add")

st.markdown("---")

# ---------------- TODAY PAGE ----------------
if st.session_state.page == "today":

    left, right = st.columns([2,1])

    with left:
        st.header("Today's Doses")

        for med, info in st.session_state.meds.items():
            taken = info["taken"]
            color = "#b7f5c2" if taken else "#bfe4ff"

            st.markdown(f"""
            <div style='background:{color}; padding:14px; border-radius:10px; margin-bottom:10px;'>
                <b style='color:black;'>{med} — {info['time']}</b><br>
                <span style='color:black;'>{info["note"]}</span>
            </div>
            """, unsafe_allow_html=True)

            b1, b2 = st.columns(2)
            with b1:
                if not taken and st.button("Take", key=f"t_{med}"):
                    take_med(med)
            with b2:
                if taken and st.button("Undo", key=f"u_{med}"):
                    undo_med(med)

    with right:
        st.header("Daily Summary")

        scheduled, taken, score = compute_today()

        if scheduled > 0:
            st.progress(score/100)

        st.markdown(f"**Score:** {score}%")
        st.markdown(f"**Scheduled doses:** {scheduled}")
        st.markdown(f"**Taken:** {taken}")

# ---------------- ALL MEDS PAGE ----------------
elif st.session_state.page == "all_meds":

    st.header("All Medications")

    if len(st.session_state.meds) == 0:
        st.info("No medicines yet.")
    else:
        df = pd.DataFrame([
            {
                "Name": name,
                "Time": info.get("time",""),
                "Note": info.get("note",""),
                "Days": ",".join(info.get("days",[])) if info.get("days") else "Every day",
                "Taken Today": info.get("taken", False)
            }
            for name, info in st.session_state.meds.items()
        ])
        st.dataframe(df, height=300)

# ---------------- ADD / EDIT PAGE ----------------
elif st.session_state.page == "add":

    st.header("Add / Edit Medicines")

    mode = st.radio("Mode", ["Add New", "Edit Existing"])

    if mode == "Add New":
        name = st.text_input("Medicine name")
        time_val = st.time_input("Time")
        note = st.text_input("Note")

        cols = st.columns(7)
        selected_days = [WEEKDAYS[i] for i in range(7) if cols[i].checkbox(WEEKDAYS[i])]

        if st.button("Add"):
            if name:
                st.session_state.meds[name] = {
                    "time": time_val.strftime("%H:%M"),
                    "note": note,
                    "taken": False,
                    "days": selected_days
                }
                st.rerun()

    else:
        if len(st.session_state.meds) == 0:
            st.info("No meds to edit.")
        else:
            target = st.selectbox("Select medicine", list(st.session_state.meds.keys()))
            info = st.session_state.meds[target]

            new_name = st.text_input("Name", value=target)
            new_time = st.time_input("Time", value=datetime.strptime(info["time"], "%H:%M").time())
            new_note = st.text_input("Note", value=info["note"])

            cols = st.columns(7)
            selected_days = [WEEKDAYS[i] for i in range(7)
                             if cols[i].checkbox(WEEKDAYS[i], value=WEEKDAYS[i] in info["days"])]

            c1,c2 = st.columns(2)

            with c1:
                if st.button("Save Changes"):
                    st.session_state.meds.pop(target)
                    st.session_state.meds[new_name] = {
                        "time": new_time.strftime("%H:%M"),
                        "note": new_note,
                        "taken": False,
                        "days": selected_days
                    }
                    st.rerun()

            with c2:
                if st.button("Delete Medicine"):
                    delete_med(target)

