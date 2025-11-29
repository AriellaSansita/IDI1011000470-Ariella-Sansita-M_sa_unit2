import streamlit as st
from datetime import datetime

st.set_page_config(layout="centered")

# -----------------------
# INITIALIZE SESSION STATE
# -----------------------
if "page" not in st.session_state:
    st.session_state.page = "today"

if "meds" not in st.session_state:
    st.session_state.meds = {
        "Aspirin": {"time": "12:00", "taken": False},
        "Vitamin D": {"time": "18:00", "taken": False},
        "Iron": {"time": "08:00", "taken": False},
    }

# -----------------------
# NAVIGATION
# -----------------------
def go(page_name):
    st.session_state.page = page_name

# -----------------------
# HEADER
# -----------------------
st.markdown(
    "<h1 style='text-align:center; margin-bottom:10px;'>MedTimer</h1>",
    unsafe_allow_html=True,
)

# Navigation buttons (top)
cols = st.columns(3)
with cols[0]: 
    if st.button("Today", key="nav_today"): go("today")
with cols[1]:
    if st.button("All Meds", key="nav_all"): go("all_meds")
with cols[2]:
    if st.button("Add Med", key="nav_add"): go("add_med")

st.markdown("---")

# -----------------------
# PAGE: TODAY VIEW
# -----------------------
if st.session_state.page == "today":

    st.subheader("Today's Medication Checklist")

    now = datetime.now().strftime("%H:%M")

    for idx, (med, info) in enumerate(st.session_state.meds.items()):

        due_time = info["time"]
        taken = info["taken"]

        # Status logic
        if taken:
            status = "✅ Taken"
            color = "#b7f5c2"
        else:
            if now > due_time:
                status = "❌ Missed"
                color = "#ffb3b3"
            else:
                status = "⏳ Due"
                color = "#bfe4ff"

        # CARD LAYOUT
        st.markdown(
            f"""
            <div style='padding:15px; background:{color}; border-radius:12px; margin-bottom:10px;'>
                <b>{med}</b> — {due_time} <br>
                <i>{status}</i>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Mark as taken button
        if not taken:
            if st.button(f"Mark Taken: {med}", key=f"btn_{idx}"):
                st.session_state.meds[med]["taken"] = True
                st.rerun()

# -----------------------
# PAGE: ALL MEDS
# -----------------------
elif st.session_state.page == "all_meds":

    st.subheader("All Medications")
    
    for med, info in st.session_state.meds.items():
        st.write(f"**{med}** — {info['time']} — {'Taken' if info['taken'] else 'Not taken'}")

# -----------------------
# PAGE: ADD MED
# -----------------------
elif st.session_state.page == "add_med":

    st.subheader("Add a New Medication")

    med_name = st.text_input("Medication Name")
    med_time = st.time_input("Time")

    if st.button("Add", key="add_button"):
        if med_name.strip() != "":
            st.session_state.meds[med_name] = {
                "time": med_time.strftime("%H:%M"),
                "taken": False
            }
            go("today")
            st.rerun()
        else:
            st.warning("Enter a valid name!")
