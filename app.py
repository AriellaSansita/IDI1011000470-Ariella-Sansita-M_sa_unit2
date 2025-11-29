import streamlit as st
from datetime import datetime, date, timedelta
from PIL import Image, ImageDraw
import pandas as pd
import random

# -----------------------
# PAGE CONFIG
# -----------------------
st.set_page_config(page_title="MedTimer", layout="centered")

# -----------------------
# CONSTANTS / UX
# -----------------------
PRIMARY = "#2b7a78"
MOTIVATIONAL = [
    "One dose at a time — you're doing great!",
    "Taking meds is taking care of your future self.",
    "Small habits create big health.",
    "Consistency is strength. Keep going!",
]
TIPS = [
    "Keep water nearby when taking meds.",
    "Pair your meds with a daily routine.",
    "Use alarms 10 minutes before dose time.",
    "Store pills in a visible and safe place.",
]


# -----------------------
# SESSION STATE INIT
# -----------------------
if "page" not in st.session_state:
    st.session_state.page = "today"

if "meds" not in st.session_state:
    st.session_state.meds = {
        "Aspirin": {"time": "12:00", "note": "After lunch", "taken_today": False},
        "Vitamin D": {"time": "18:00", "note": "With dinner", "taken_today": False},
        "Iron": {"time": "08:00", "note": "Before breakfast", "taken_today": False},
    }

if "history" not in st.session_state:
    st.session_state.history = []

if "last_reset_date" not in st.session_state:
    st.session_state.last_reset_date = date.today().isoformat()


# -----------------------
# HELPERS
# -----------------------
def go(page):
    st.session_state.page = page


def now_time_str():
    return datetime.now().strftime("%H:%M")


def today_str():
    return date.today().isoformat()


def reset_daily():
    """Auto reset taken flags when day changes."""
    last = date.fromisoformat(st.session_state.last_reset_date)
    if last < date.today():
        for m in st.session_state.meds:
            st.session_state.meds[m]["taken_today"] = False
        st.session_state.last_reset_date = today_str()


reset_daily()


def mark_taken(med):
    st.session_state.meds[med]["taken_today"] = True
    st.session_state.history.append({"med": med, "date": today_str(), "time": now_time_str()})


def unmark_taken(med):
    st.session_state.meds[med]["taken_today"] = False
    # remove today's entry
    for i in range(len(st.session_state.history) - 1, -1, -1):
        if st.session_state.history[i]["med"] == med and st.session_state.history[i]["date"] == today_str():
            st.session_state.history.pop(i)
            break


def delete_med(med):
    st.session_state.meds.pop(med, None)
    st.session_state.history = [h for h in st.session_state.history if h["med"] != med]


def calculate_weekly_adherence():
    today = date.today()
    start = today - timedelta(days=today.weekday())
    days = (today - start).days + 1

    scheduled = len(st.session_state.meds) * days
    taken = sum(1 for h in st.session_state.history if start <= date.fromisoformat(h["date"]) <= today)

    score = int((taken / scheduled) * 100) if scheduled > 0 else 0
    return score, scheduled, taken


# -----------------------
# DRAW WITH PIL
# -----------------------
def draw_smiley(score):
    img = Image.new("RGB", (300, 300), "white")
    d = ImageDraw.Draw(img)

    # Trophy
    if score >= 90:
        d.rectangle([110, 130, 190, 190], fill="#FFD700", outline="black")
        d.rectangle([130, 190, 170, 210], fill="#FFD700", outline="black")
        d.text((115, 80), "Great!", fill="black")
        return img

    # Face color
    if score >= 80:
        color = "#b7f5c2"
    elif score >= 50:
        color = "#fff2b2"
    else:
        color = "#ffb3b3"

    d.ellipse([50, 50, 250, 250], fill=color, outline="black")

    # Eyes
    d.ellipse([110, 120, 140, 150], fill="black")
    d.ellipse([160, 120, 190, 150], fill="black")

    # Mouth
    if score >= 80:
        d.arc([100, 160, 200, 230], start=0, end=180, fill="black", width=5)
    elif score >= 50:
        d.line([110, 200, 190, 200], fill="black", width=5)
    else:
        d.arc([100, 140, 200, 230], start=180, end=360, fill="black", width=5)

    return img


# -----------------------
# HEADER
# -----------------------
st.markdown("<h1 style='text-align:center;'>MedTimer</h1>", unsafe_allow_html=True)
st.markdown("<div style='text-align:center; color:gray;'>A senior-friendly daily medicine tracker</div>", unsafe_allow_html=True)
st.markdown("---")

cols = st.columns(3)
with cols[0]:
    if st.button("Today"):
        go("today")
with cols[1]:
    if st.button("All Meds"):
        go("all_meds")
with cols[2]:
    if st.button("Add / Edit"):
        go("add")


# -----------------------
# TODAY PAGE
# -----------------------
if st.session_state.page == "today":
    st.subheader("Today's Checklist")
    st.write(f"Current time: **{now_time_str()}**")
    st.write("")

    left, right = st.columns([2, 1])

    # LEFT SIDE – medicines
    with left:
        if len(st.session_state.meds) == 0:
            st.info("No medicines added yet.")
        else:
            for idx, (med, info) in enumerate(st.session_state.meds.items()):
                due = info["time"]
                taken = info["taken_today"]

                now = now_time_str()
                if taken:
                    bg = "#b7f5c2"
                    status = "Taken"
                else:
                    bg = "#bfe4ff" if now <= due else "#ffb3b3"
                    status = "Upcoming" if now <= due else "Missed"

                st.markdown(
                    f"""
                    <div style='background:{bg}; padding:15px; border-radius:10px; margin-bottom:8px;'>
                        <b>{med}</b> — {due}<br>
                        <i>{status}</i>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                c1, c2, c3 = st.columns(3)
                with c1:
                    if not taken and st.button(f"Take {med}", key=f"take{idx}"):
                        mark_taken(med)
                        st.rerun()
                with c2:
                    if taken and st.button(f"Undo {med}", key=f"undo{idx}"):
                        unmark_taken(med)
                        st.rerun()
                with c3:
                    if st.button(f"Delete {med}", key=f"del{idx}"):
                        delete_med(med)
                        st.rerun()

    # RIGHT SIDE – weekly stats & graphic
    with right:
        st.subheader("Weekly Summary")

        score, scheduled, taken = calculate_weekly_adherence()
        st.progress(score / 100)
        st.write(f"Score: **{score}%**")
        st.write(f"Scheduled doses: {scheduled}")
        st.write(f"Taken: {taken}")

        st.info(random.choice(MOTIVATIONAL))
        st.success(random.choice(TIPS))

        img = draw_smiley(score)
        st.image(img)

        # Export CSV
        df = pd.DataFrame(st.session_state.history)
        st.download_button("Download Weekly CSV", df.to_csv(index=False), "week_history.csv", "text/csv")


# -----------------------
# ALL MEDS PAGE
# -----------------------
elif st.session_state.page == "all_meds":
    st.subheader("All Medications")

    if len(st.session_state.meds) == 0:
        st.info("No medicines added.")
    else:
        df = pd.DataFrame([
            {"Name": m, "Time": i["time"], "Note": i["note"], "Taken Today": i["taken_today"]}
            for m, i in st.session_state.meds.items()
        ])
        st.dataframe(df)


# -----------------------
# ADD / EDIT PAGE
# -----------------------
elif st.session_state.page == "add":
    st.subheader("Add / Edit Medicines")

    med_names = list(st.session_state.meds.keys())
    mode = st.radio("Choose action:", ["Add New", "Edit Existing"])

    if mode == "Add New":
        name = st.text_input("Medicine name")
        time = st.time_input("Time")
        note = st.text_input("Note (optional)")

        if st.button("Add"):
            if name.strip() == "":
                st.warning("Please enter a name.")
            elif name in st.session_state.meds:
                st.warning("Medicine already exists.")
            else:
                st.session_state.meds[name] = {
                    "time": time.strftime("%H:%M"),
                    "note": note,
                    "taken_today": False,
                }
                st.success("Added!")
                st.rerun()

    else:  # EDIT
        if len(med_names) == 0:
            st.info("No medicines to edit.")
        else:
            target = st.selectbox("Select medicine:", med_names)
            old = st.session_state.meds[target]

            new_name = st.text_input("New name", value=target)
            new_time = st.time_input("New time", value=datetime.strptime(old["time"], "%H:%M").time())
            new_note = st.text_input("New note", value=old["note"])

            if st.button("Save Changes"):
                st.session_state.meds.pop(target)
                st.session_state.meds[new_name] = {
                    "time": new_time.strftime("%H:%M"),
                    "note": new_note,
                    "taken_today": False,
                }
                st.success("Updated!")
                st.rerun()

