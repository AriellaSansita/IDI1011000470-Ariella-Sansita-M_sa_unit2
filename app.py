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
# UX / CONSTANTS
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
    "Pair meds with a daily routine (e.g., breakfast).",
    "Use alarms 10 minutes before dose time.",
    "Store pills in a visible, consistent place.",
]

CARD_TEXT_COLOR = "black"  # ensure readability inside colored boxes

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
    # history entries are dicts: {"med": name, "date": "YYYY-MM-DD", "time": "HH:MM"}
    st.session_state.history = []

if "last_reset_date" not in st.session_state:
    st.session_state.last_reset_date = date.today().isoformat()

# -----------------------
# HELPERS
# -----------------------
def go(p):
    st.session_state.page = p

def now_time_str_server():
    # server time (kept for logging) - not shown to user
    return datetime.now().strftime("%H:%M")

def today_str():
    return date.today().isoformat()

def reset_daily_if_needed():
    last = date.fromisoformat(st.session_state.last_reset_date)
    if last < date.today():
        for k in st.session_state.meds:
            st.session_state.meds[k]["taken_today"] = False
        st.session_state.last_reset_date = today_str()

reset_daily_if_needed()

def mark_taken(med):
    st.session_state.meds[med]["taken_today"] = True
    st.session_state.history.append({"med": med, "date": today_str(), "time": now_time_str_server()})
    st.rerun()

def unmark_taken(med):
    st.session_state.meds[med]["taken_today"] = False
    # remove last entry for this med today if present
    for i in range(len(st.session_state.history)-1, -1, -1):
        e = st.session_state.history[i]
        if e["med"] == med and e["date"] == today_str():
            st.session_state.history.pop(i)
            break
    st.rerun()

def delete_med(med):
    st.session_state.meds.pop(med, None)
    st.session_state.history = [h for h in st.session_state.history if h["med"] != med]
    st.rerun()

def calculate_weekly_adherence():
    """
    Counts scheduled doses for a full 7-day week (Mon-Sun) and taken entries from history that fall within this week.
    Returns: score (int 0-100), scheduled (int), taken (int), week_start (date)
    """
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday
    week_end = week_start + timedelta(days=6)  # Sunday

    days_in_week = 7
    scheduled = len(st.session_state.meds) * days_in_week

    taken = 0
    for h in st.session_state.history:
        try:
            hd = date.fromisoformat(h["date"])
        except Exception:
            continue
        if week_start <= hd <= week_end:
            taken += 1

    score = int((taken / scheduled) * 100) if scheduled > 0 else 0
    # clamp
    if score < 0: score = 0
    if score > 100: score = 100
    return score, scheduled, taken, week_start, week_end

# -----------------------
# DRAW IMAGE (PIL)
# -----------------------
def draw_smiley(score, size_px=300):
    img = Image.new("RGB", (size_px, size_px), "white")
    d = ImageDraw.Draw(img)

    # Trophy for >= 90
    if score >= 90:
        # cup body
        box = [size_px*0.35, size_px*0.28, size_px*0.65, size_px*0.55]
        d.rectangle(box, fill="#FFD700", outline="black")
        # base
        base = [size_px*0.43, size_px*0.55, size_px*0.57, size_px*0.65]
        d.rectangle(base, fill="#FFD700", outline="black")
        # text
        d.text((size_px*0.35, size_px*0.12), "Great!", fill="black")
        return img

    # face color
    if score >= 80:
        face = "#b7f5c2"
    elif score >= 50:
        face = "#fff2b2"
    else:
        face = "#ffb3b3"

    margin = size_px * 0.08
    d.ellipse([margin, margin, size_px-margin, size_px-margin], fill=face, outline="black")

    # eyes
    eye_r = int(size_px * 0.04)
    d.ellipse([size_px*0.32-eye_r, size_px*0.38-eye_r, size_px*0.32+eye_r, size_px*0.38+eye_r], fill="black")
    d.ellipse([size_px*0.68-eye_r, size_px*0.38-eye_r, size_px*0.68+eye_r, size_px*0.38+eye_r], fill="black")

    # mouth shape
    if score >= 80:
        # smile arc
        d.arc([size_px*0.28, size_px*0.46, size_px*0.72, size_px*0.72], start=0, end=180, fill="black", width=4)
    elif score >= 50:
        # line
        d.line([size_px*0.36, size_px*0.62, size_px*0.64, size_px*0.62], fill="black", width=4)
    else:
        # sad arc
        d.arc([size_px*0.28, size_px*0.56, size_px*0.72, size_px*0.82], start=180, end=360, fill="black", width=4)

    return img

# -----------------------
# HEADER + NAV
# -----------------------
st.markdown("<h1 style='text-align:center; margin-bottom:6px;'>MedTimer</h1>", unsafe_allow_html=True)
# Removed subtitle per request (no "A senior-friendly daily medicine tracker")
st.markdown("---")

c1, c2, c3 = st.columns([1,1,1])
with c1:
    if st.button("Today"):
        go("today")
with c2:
    if st.button("All Meds"):
        go("all_meds")
with c3:
    if st.button("Add / Edit"):
        go("add")

st.write("")  # spacing

# Inject a tiny JS clock to show client (browser) local time.
# This displays "Current time: hh:mm:ss" using browser time.
st.markdown(
    """
    <div style='font-size:14px; color: #333;'>Current time: <span id="client_time">--:--:--</span></div>
    <script>
    function updateClientTime(){
        const el = document.getElementById('client_time');
        if(!el) return;
        const now = new Date();
        const hh = String(now.getHours()).padStart(2,'0');
        const mm = String(now.getMinutes()).padStart(2,'0');
        const ss = String(now.getSeconds()).padStart(2,'0');
        el.innerText = hh + ":" + mm + ":" + ss;
    }
    setInterval(updateClientTime, 1000);
    updateClientTime();
    </script>
    """,
    unsafe_allow_html=True
)

st.write("")  # spacing

# -----------------------
# PAGE: TODAY
# -----------------------
if st.session_state.page == "today":
    st.subheader("Today's Checklist")
    st.write("")  # small gap

    left, right = st.columns([2, 1])

    # LEFT: medicine cards (make them long/wide)
    with left:
        if len(st.session_state.meds) == 0:
            st.info("No medicines added — go to Add / Edit.")
        else:
            for idx, (med, info) in enumerate(st.session_state.meds.items()):
                due = info.get("time", "--:--")
                note = info.get("note", "")
                taken = info.get("taken_today", False)

                now_client = ""  # client time shown above; for status use server time for compare
                now_server = now_time_str_server()

                # compare times as HH:MM strings (works for 24h format)
                if taken:
                    bg = "#b7f5c2"
                    status_text = "Taken"
                else:
                    bg = "#bfe4ff" if now_server <= due else "#ffb3b3"
                    status_text = "Upcoming" if now_server <= due else "Missed"

                # ensure text inside colored box is black and card stretches full width
                st.markdown(
                    f"""
                    <div style='
                        background:{bg};
                        padding:16px;
                        border-radius:12px;
                        margin-bottom:12px;
                        width:100%;
                        display:block;
                        box-sizing:border-box;
                    '>
                        <div style='font-size:18px; color:{CARD_TEXT_COLOR}; font-weight:600;'>{med} — {due}</div>
                        <div style='font-size:15px; color:{CARD_TEXT_COLOR}; margin-top:6px;'>{note}</div>
                        <div style='font-size:14px; color:{CARD_TEXT_COLOR}; margin-top:6px;'><i>{status_text}</i></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # action buttons
                b1, b2, b3 = st.columns([1,1,1])
                with b1:
                    if not taken and st.button(f"Take {med}", key=f"take_{idx}"):
                        mark_taken(med)
                with b2:
                    if taken and st.button(f"Undo {med}", key=f"undo_{idx}"):
                        unmark_taken(med)
                with b3:
                    if st.button(f"Delete {med}", key=f"del_{idx}"):
                        delete_med(med)

    # RIGHT: weekly summary & graphic
    with right:
        st.subheader("Weekly Summary (Mon–Sun)")
        score, scheduled, taken, ws, we = calculate_weekly_adherence()

        # progress bar (use integer)
        st.progress(score / 100)
        st.markdown(f"**Score:** {score}%")
        st.markdown(f"**Scheduled doses:** {scheduled}")
        st.markdown(f"**Taken (this week):** {taken}")
        st.write("")  # gap

        st.info(random.choice(MOTIVATIONAL))
        st.success(random.choice(TIPS))

        # PIL-driven image
        img = draw_smiley(score, size_px=260)
        st.image(img, use_column_width=False)

        # download CSV of entire history
        if len(st.session_state.history) > 0:
            df_hist = pd.DataFrame(st.session_state.history)
        else:
            df_hist = pd.DataFrame(columns=["med", "date", "time"])
        st.download_button("Download Weekly CSV", data=df_hist.to_csv(index=False), file_name="med_history.csv", mime="text/csv")

# -----------------------
# PAGE: ALL MEDS
# -----------------------
elif st.session_state.page == "all_meds":
    st.subheader("All Medications")
    if len(st.session_state.meds) == 0:
        st.info("No medications yet.")
    else:
        df = pd.DataFrame([
            {"Name": name, "Time": info.get("time",""), "Note": info.get("note",""), "Taken Today": info.get("taken_today", False)}
            for name, info in st.session_state.meds.items()
        ])
        st.dataframe(df)

# -----------------------
# PAGE: ADD / EDIT
# -----------------------
elif st.session_state.page == "add":
    st.subheader("Add / Edit Medicines")

    mode = st.radio("Mode", ["Add New", "Edit Existing"])
    meds_list = list(st.session_state.meds.keys())

    if mode == "Add New":
        new_name = st.text_input("Medicine name")
        new_time = st.time_input("Time", value=datetime.strptime("08:00", "%H:%M").time())
        new_note = st.text_input("Note (optional)")
        if st.button("Add"):
            if new_name.strip() == "":
                st.warning("Enter a name.")
            elif new_name in st.session_state.meds:
                st.warning("Medicine already exists.")
            else:
                st.session_state.meds[new_name] = {"time": new_time.strftime("%H:%M"), "note": new_note, "taken_today": False}
                st.success("Added.")
                st.rerun()
    else:
        if len(meds_list) == 0:
            st.info("No meds to edit.")
        else:
            target = st.selectbox("Select", meds_list)
            info = st.session_state.meds[target]
            edit_name = st.text_input("Name", value=target)
            edit_time = st.time_input("Time", value=datetime.strptime(info["time"], "%H:%M").time())
            edit_note = st.text_input("Note", value=info.get("note",""))
            if st.button("Save changes"):
                # rename safely
                st.session_state.meds.pop(target, None)
                st.session_state.meds[edit_name] = {"time": edit_time.strftime("%H:%M"), "note": edit_note, "taken_today": False}
                # update history names for past entries
                for h in st.session_state.history:
                    if h["med"] == target:
                        h["med"] = edit_name
                st.success("Saved.")
                st.rerun()

# -----------------------
# FOOTER
# -----------------------
st.markdown("---")
st.markdown("<div style='text-align:center; font-size:12px; color:#666'>MedTimer — data stored in-session only. Deploy via Streamlit Cloud.</div>", unsafe_allow_html=True)

