import streamlit as st
from datetime import datetime, date
import pandas as pd

st.set_page_config(page_title="MedTimer", layout="centered")

WEEKDAYS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

# ---------------- SESSION STATE ----------------
if "page" not in st.session_state:
    st.session_state.page = "today"

if "meds" not in st.session_state:
    st.session_state.meds = {}

if "history" not in st.session_state:
    st.session_state.history = []

# ---------------- NAV ----------------
nav1, nav2, nav3 = st.columns(3)
with nav1:
    if st.button("Today’s Doses"):
        st.session_state.page = "today"
with nav2:
    if st.button("All Meds"):
        st.session_state.page = "all_meds"
with nav3:
    if st.button("Add / Edit"):
        st.session_state.page = "add"

st.write("")

# ---------------- TODAY PAGE ----------------
if st.session_state.page == "today":
    st.header("Today's Doses")

    left, right = st.columns([2,1])

    with left:
        if len(st.session_state.meds) == 0:
            st.info("No medicines added.")
        else:
            for med, info in st.session_state.meds.items():
                for i, dose in enumerate(info["doses"]):
                    key = f"{med}_{i}_{date.today()}"
                    taken = any(h["key"] == key for h in st.session_state.history)

                    if taken:
                        bg = "#b7f5c2"
                        status = "Taken"
                    else:
                        bg = "#fff2b2"
                        status = "Upcoming"

                    st.markdown(
                        f"""
                        <div style='background:{bg}; padding:14px; border-radius:10px; margin-bottom:10px;'>
                        <b style='color:black'>{med} — {dose}</b><br>
                        <span style='color:black'>{info["note"]}</span><br>
                        <i>{status}</i>
                        </div>
                        """, unsafe_allow_html=True
                    )

                    c1, c2 = st.columns(2)
                    with c1:
                        if not taken and st.button("Take", key=f"take_{key}"):
                            st.session_state.history.append({"key":key})
                            st.experimental_rerun()

                    with c2:
                        if taken and st.button("Undo", key=f"undo_{key}"):
                            st.session_state.history = [h for h in st.session_state.history if h["key"]!=key]
                            st.experimental_rerun()

    with right:
        taken_today = len(st.session_state.history)
        scheduled_today = sum(len(m["doses"]) for m in st.session_state.meds.values())
        score = int((taken_today/scheduled_today)*100) if scheduled_today>0 else 0

        st.header("Daily Summary")
        st.progress(score/100)
        st.markdown(f"**Score:** {score}%")
        st.markdown(f"**Scheduled:** {scheduled_today}")
        st.markdown(f"**Taken:** {taken_today}")

# ---------------- ALL MEDS PAGE ----------------
elif st.session_state.page == "all_meds":
    st.header("All Medications")

    if len(st.session_state.meds) == 0:
        st.info("No medicines yet.")
    else:
        df = pd.DataFrame([
            {
                "Name": name,
                "Time": ", ".join(info["doses"]),
                "Note": info.get("note",""),
                "Days": ",".join(info.get("days",[])),
                "Taken Today": False
            }
            for name, info in st.session_state.meds.items()
        ])
        st.dataframe(df, height=300)

# ---------------- ADD / EDIT PAGE (YOUR CODE WITH DELETE ADDED) ----------------
elif st.session_state.page == "add":

    st.header("Add / Edit Medicines")
    mode = st.radio("Mode", ["Add", "Edit"])

    if mode == "Add":
        name = st.text_input("Medicine name")
        note = st.text_input("Note")
        freq = st.number_input("How many times per day?", min_value=1, max_value=50, value=1)

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
            if name.strip()=="":
                st.warning("Enter a name.")
            else:
                st.session_state.meds[name] = {
                    "doses": new_times,
                    "note": note,
                    "days": selected_days
                }
                st.success("Added.")
                st.experimental_rerun()

    else:
        meds = list(st.session_state.meds.keys())
        if meds:
            target = st.selectbox("Select medicine", meds)
            info = st.session_state.meds[target]

            new_name = st.text_input("Name", target)
            new_note = st.text_input("Note", info["note"])
            freq = st.number_input("Times per day", min_value=1, max_value=50, value=len(info["doses"]))

            st.write("Edit dose times:")
            new_times = []
            for i in range(freq):
                default = info["doses"][i] if i < len(info["doses"]) else "08:00"
                tm = st.time_input(f"Dose {i+1}", value=datetime.strptime(default,"%H:%M").time())
                new_times.append(tm.strftime("%H:%M"))

            st.write("Repeat on days:")
            cols = st.columns(7)
            new_days = []
            for i,d in enumerate(WEEKDAYS):
                if cols[i].checkbox(d, d in info["days"]):
                    new_days.append(d)

            col1, col2 = st.columns(2)

            with col1:
                if st.button("Save changes"):
                    st.session_state.meds.pop(target)
                    st.session_state.meds[new_name] = {
                        "doses": new_times,
                        "note": new_note,
                        "days": new_days
                    }
                    st.success("Saved.")
                    st.experimental_rerun()

            with col2:
                if st.button("Delete"):
                    st.session_state.meds.pop(target)
                    st.success("Deleted.")
                    st.experimental_rerun()
