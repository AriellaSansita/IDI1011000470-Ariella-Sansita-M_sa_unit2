import streamlit as st
from datetime import datetime

# ------------------------------------------------------
#                 INITIALIZE APP STATE
# ------------------------------------------------------
if "medicines" not in st.session_state:
    st.session_state.medicines = []


# ------------------------------------------------------
#                 FUNCTION: MARK TAKEN
# ------------------------------------------------------
def mark_taken(med_name, med_time):
    """Marks a specific time of a medicine as taken."""
    for med in st.session_state.medicines:
        if med["name"] == med_name:
            for t in med["times"]:
                if t["time"] == med_time:
                    t["taken"] = True


# ------------------------------------------------------
#                 FUNCTION: ADD MED
# ------------------------------------------------------
def add_medicine(name, times_list, note):
    st.session_state.medicines.append({
        "name": name,
        "times": [{"time": t, "taken": False} for t in times_list],
        "note": note
    })


# ------------------------------------------------------
#                 PAGE TITLE
# ------------------------------------------------------
st.title("💊 Medicine Tracker (100% Python)")


# ------------------------------------------------------
#                 ADD MEDICINE SECTION
# ------------------------------------------------------
st.header("Add Medicine")

new_name = st.text_input("Medicine name:")
new_note = st.text_input("Note (optional):")
num_times = st.number_input("How many times per day?", min_value=1, max_value=10, step=1)

times = []
for i in range(int(num_times)):
    t = st.text_input(f"Time {i+1} (HH:MM):", key=f"time_{i}")
    if t:
        times.append(t)

if st.button("Add"):
    if new_name and len(times) > 0:
        add_medicine(new_name, times, new_note)
        st.success(f"Added {new_name}")
    else:
        st.error("Enter name and times!")


# ------------------------------------------------------
#                 TODAY'S CHECKLIST
# ------------------------------------------------------
st.header("Today's Checklist")

now = datetime.now().strftime("%H:%M")

for med in st.session_state.medicines:
    st.subheader(med["name"])
    if med["note"]:
        st.write(med["note"])

    for t in med["times"]:
        status = "✔️ Taken" if t["taken"] else "⏳ Pending"

        cols = st.columns([3, 1])
        with cols[0]:
            st.write(f"**{med['name']} — {t['time']}**  ({status})")

        with cols[1]:
            if not t["taken"]:
                if st.button(f"Mark {med['name']} {t['time']}", key=f"btn_{med['name']}_{t['time']}"):
                    mark_taken(med["name"], t["time"])


# ------------------------------------------------------
#                 RESET ALL (OPTIONAL)
# ------------------------------------------------------
if st.button("Reset All"):
    for med in st.session_state.medicines:
        for t in med["times"]:
            t["taken"] = False
    st.success("Reset all statuses.")

