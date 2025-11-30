# app.py
import streamlit as st
from datetime import datetime, date, timedelta
from PIL import Image, ImageDraw
import pandas as pd
import random

# -----------------------
# CONFIG
# -----------------------
st.set_page_config(page_title="MedTimer", layout="centered")

CARD_TEXT_COLOR = "black"
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

# -----------------------
# SESSION INIT
# -----------------------
if "page" not in st.session_state:
    st.session_state.page = "today"

# meds structure:
# name -> {"times": ["08:00","20:00"], "note": str, "taken_today": { "08:00": False, ... } }
if "meds" not in st.session_state:
    st.session_state.meds = {
        "Aspirin": {"times": ["12:00"], "note": "After lunch", "taken_today": {"12:00": False}},
        "Vitamin D": {"times": ["18:00"], "note": "With dinner", "taken_today": {"18:00": False}},
        "Iron": {"times": ["08:00"], "note": "Before breakfast", "taken_today": {"08:00": False}},
    }

if "history" not in st.session_state:
    # list of {"med": name, "date":"YYYY-MM-DD", "time":"HH:MM"}
    st.session_state.history = []

if "last_reset_date" not in st.session_state:
    st.session_state.last_reset_date = date.today().isoformat()

# -----------------------
# HELPERS
# -----------------------
def go(p): st.session_state.page = p

def server_now_str():
    return datetime.now().strftime("%H:%M")

def today_iso(): return date.today().isoformat()

def reset_daily_flags_if_needed():
    last = date.fromisoformat(st.session_state.last_reset_date)
    if last < date.today():
        for m in st.session_state.meds.values():
            for t in m["times"]:
                m["taken_today"][t] = False
        st.session_state.last_reset_date = today_iso()

reset_daily_flags_if_needed()

def mark_taken(med_name, time_str):
    st.session_state.meds[med_name]["taken_today"][time_str] = True
    st.session_state.history.append({"med": med_name, "date": today_iso(), "time": time_str})
    st.rerun()

def unmark_taken(med_name, time_str):
    st.session_state.meds[med_name]["taken_today"][time_str] = False
    # remove latest history record for that med/time today
    for i in range(len(st.session_state.history)-1, -1, -1):
        h = st.session_state.history[i]
        if h["med"] == med_name and h["date"] == today_iso() and h["time"] == time_str:
            st.session_state.history.pop(i)
            break
    st.rerun()

def delete_med(med_name):
    st.session_state.meds.pop(med_name, None)
    st.session_state.history = [h for h in st.session_state.history if h["med"] != med_name]
    st.rerun()

def calculate_weekly_adherence():
    # Count scheduled doses for full Monday-Sunday week
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday
    week_end = week_start + timedelta(days=6)
    scheduled = sum(len(info["times"]) for info in st.session_state.meds.values()) * 7  # 7 days
    taken = 0
    for h in st.session_state.history:
        try:
            hd = date.fromisoformat(h["date"])
        except Exception:
            continue
        if week_start <= hd <= week_end:
            taken += 1
    score = int((taken / scheduled) * 100) if scheduled > 0 else 0
    score = max(0, min(100, score))
    return {"score": score, "scheduled": scheduled, "taken": taken, "week_start": week_start, "week_end": week_end}


# -----------------------
# DRAW SMILEY (PIL)
# -----------------------
def draw_smiley(score, size=260):
    img = Image.new("RGB", (size, size), "white")
    d = ImageDraw.Draw(img)
    if score >= 90:
        # big smiley + trophy feel (simple)
        d.ellipse([20,20,size-20,size-20], fill="#b7f5c2", outline="black")
        d.ellipse([80,80,110,110], fill="black")
        d.ellipse([size-110,80,size-80,110], fill="black")
        d.arc([60,90,size-60,size-40], start=0, end=180, fill="black", width=6)
        d.text((size*0.38, size*0.05), "Great!", fill="black")
        return img
    # normal smiley / neutral / sad
    if score >= 80:
        face = "#b7f5c2"
    elif score >= 50:
        face = "#fff2b2"
    else:
        face = "#ffb3b3"
    margin = 12
    d.ellipse([margin, margin, size-margin, size-margin], fill=face, outline="black")
    # eyes
    eye_r = int(size*0.04)
    d.ellipse([size*0.32-eye_r, size*0.36-eye_r, size*0.32+eye_r, size*0.36+eye_r], fill="black")
    d.ellipse([size*0.68-eye_r, size*0.36-eye_r, size*0.68+eye_r, size*0.36+eye_r], fill="black")
    # mouth
    if score >= 80:
        d.arc([size*0.28, size*0.46, size*0.72, size*0.72], start=0, end=180, fill="black", width=5)
    elif score >= 50:
        d.line([size*0.36, size*0.62, size*0.64, size*0.62], fill="black", width=4)
    else:
        d.arc([size*0.28, size*0.56, size*0.72, size*0.86], start=180, end=360, fill="black", width=5)
    return img

# -----------------------
# HEADER + NAV
# -----------------------
st.markdown("<h1 style='text-align:center; font-size:36px; margin-bottom:6px;'>MedTimer</h1>", unsafe_allow_html=True)
# subtitle removed per request
st.markdown("---")

col1, col2, col3, col4 = st.columns([1,1,1,1])
with col1:
    if st.button("Today"): go("today")
with col2:
    if st.button("All Meds"): go("all_meds")
with col3:
    if st.button("Add / Edit"): go("add")
# removed Summary nav button per request

st.write("")  # spacing

# -----------------------
# Timezone selector + live clock (JS)
# -----------------------
# Provide a compact list of common timezones (user can paste others if needed).
COMMON_TZS = [
    "UTC","Europe/London","Europe/Paris","Asia/Kolkata","Asia/Kathmandu","Asia/Dubai",
    "Asia/Singapore","Asia/Tokyo","Australia/Sydney","America/New_York","America/Chicago","America/Denver","America/Los_Angeles"
]
st.markdown("**Choose your timezone (for live local time display):**")
tz = st.selectbox("Timezone", options=COMMON_TZS, index=COMMON_TZS.index("Asia/Kolkata") if "Asia/Kolkata" in COMMON_TZS else 0)
# JS uses the chosen tz string embedded in the HTML so the displayed clock updates to that zone
st.markdown(
    f"""
    <div style='font-size:14px; color:#333;'>Current time: <span id="client_time">--:--:--</span></div>
    <script>
    (function(){{
        const tz = "{tz}";
        function updateClientTime(){{
            try {{
                const now = new Date();
                const options = {{ hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false, timeZone: tz }};
                const str = new Intl.DateTimeFormat([], options).format(now);
                document.getElementById('client_time').innerText = str;
            }} catch(e) {{
                // fallback: local browser time
                const now = new Date();
                document.getElementById('client_time').innerText = now.toLocaleTimeString();
            }}
        }}
        setInterval(updateClientTime, 1000);
        updateClientTime();
    }})();
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
    st.write("")  # gap

    left, right = st.columns([2, 1])

    # LEFT: meds list
    with left:
        if len(st.session_state.meds) == 0:
            st.info("No medicines added yet.")
        else:
            # sort by earliest next time (optional)
            for midx, (med_name, info) in enumerate(st.session_state.meds.items()):
                # for each time entry, show a separate card to make marking clear
                for t in info["times"]:
                    taken = info["taken_today"].get(t, False)
                    now_server = server_now_str()
                    # upcoming if server time <= due ; missed if server time > due and not taken
                    if taken:
                        bg = "#b7f5c2"  # green
                        status = "Taken"
                    else:
                        # upcoming -> yellow ; missed -> red
                        if now_server <= t:
                            bg = "#fff2b2"  # yellow-ish
                            status = "Upcoming"
                        else:
                            bg = "#ffb3b3"
                            status = "Missed"

                    # wide card, black text
                    st.markdown(
                        f"""
                        <div style='background:{bg}; padding:16px; border-radius:12px; margin-bottom:10px; width:100%; display:block; box-sizing:border-box;'>
                            <div style='font-size:18px; font-weight:600; color:{CARD_TEXT_COLOR};'>{med_name} — {t}</div>
                            <div style='font-size:14px; color:{CARD_TEXT_COLOR}; margin-top:6px;'>{info.get("note","")}</div>
                            <div style='font-size:13px; color:{CARD_TEXT_COLOR}; margin-top:6px;'><i>{status}</i></div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    # action buttons (mark/undo/delete)
                    b1, b2, b3 = st.columns([1,1,1])
                    with b1:
                        if not taken and st.button(f"Take {med_name} {t}", key=f"take_{med_name}_{t}"):
                            mark_taken(med_name, t)
                    with b2:
                        if taken and st.button(f"Undo {med_name} {t}", key=f"undo_{med_name}_{t}"):
                            unmark_taken(med_name, t)
                    with b3:
                        if st.button(f"Delete {med_name}", key=f"del_{med_name}_{t}"):
                            # delete entirely (all times)
                            delete_med(med_name)

    # RIGHT: daily/weekly summary + smiley
    with right:
        st.subheader("Daily / Weekly Summary")
        sd = calculate_weekly_adherence()
        # clamp progress value
        progress_val = sd["score"] / 100 if sd["scheduled"] > 0 else 0
        progress_val = max(0.0, min(1.0, float(progress_val)))
        st.progress(progress_val)
        st.markdown(f"**Score:** {sd['score']}%")
        st.markdown(f"**Scheduled doses (week):** {sd['scheduled']}")
        st.markdown(f"**Taken (week):** {sd['taken']}")
        st.write("")
        st.info(random.choice(MOTIVATIONAL))
        st.success(random.choice(TIPS))
        img = draw_smiley(sd["score"], size=260)
        st.image(img, use_column_width=False)

# -----------------------
# PAGE: ALL MEDS
# -----------------------
elif st.session_state.page == "all_meds":
    st.subheader("All Medications")
    if len(st.session_state.meds) == 0:
        st.info("No meds added yet.")
    else:
        rows = []
        for name, info in st.session_state.meds.items():
            rows.append({
                "Name": name,
                "Times (per day)": ", ".join(info["times"]),
                "Note": info.get("note",""),
                "Taken Today": ", ".join([t for t,v in info["taken_today"].items() if v])
            })
        df = pd.DataFrame(rows)
        st.dataframe(df)

# -----------------------
# PAGE: ADD / EDIT
# -----------------------
elif st.session_state.page == "add":
    st.subheader("Add / Edit Medicines")
    mode = st.radio("Mode", ["Add New", "Edit Existing"])
    med_names = list(st.session_state.meds.keys())

    if mode == "Add New":
        name = st.text_input("Medicine name")
        times_per_day = st.number_input("Times per day (1-6)", min_value=1, max_value=6, value=1, step=1)
        # dynamically show that many time pickers
        times = []
        for i in range(times_per_day):
            t = st.time_input(f"Time #{i+1}", key=f"new_time_{i}")
            times.append(t.strftime("%H:%M"))
        note = st.text_input("Note (optional)")

        if st.button("Add Medicine"):
            if name.strip() == "":
                st.warning("Please enter a medicine name.")
            elif name in st.session_state.meds:
                st.warning("A medicine with that name already exists. Use Edit.")
            else:
                taken_map = {tt: False for tt in times}
                st.session_state.meds[name.strip()] = {"times": times, "note": note.strip(), "taken_today": taken_map}
                st.success("Added.")
                st.rerun()
    else:
        if len(med_names) == 0:
            st.info("No meds to edit.")
        else:
            sel = st.selectbox("Select medicine to edit", med_names)
            info = st.session_state.meds[sel]
            new_name = st.text_input("Name", value=sel)
            # times per day derived from len(info["times"])
            tp = st.number_input("Times per day (1-6)", min_value=1, max_value=6, value=len(info["times"]), step=1)
            new_times = []
            # show as many time inputs as tp (prefill existing times as possible)
            for i in range(tp):
                default_time = datetime.strptime(info["times"][i], "%H:%M").time() if i < len(info["times"]) else datetime.strptime("08:00","%H:%M").time()
                t = st.time_input(f"Time #{i+1}", value=default_time, key=f"edit_time_{i}")
                new_times.append(t.strftime("%H:%M"))
            new_note = st.text_input("Note", value=info.get("note",""))
            if st.button("Save changes"):
                # remove old and add new; update history med names if name changed
                st.session_state.meds.pop(sel, None)
                taken_map = {tt: False for tt in new_times}  # reset taken_today on edit
                st.session_state.meds[new_name.strip()] = {"times": new_times, "note": new_note.strip(), "taken_today": taken_map}
                # update history med name
                for h in st.session_state.history:
                    if h["med"] == sel:
                        h["med"] = new_name.strip()
                st.success("Saved.")
                st.rerun()

# -----------------------
# FOOTER
# -----------------------
st.markdown("---")
st.markdown("<div style='text-align:center; font-size:12px; color:#666'>MedTimer — data stored in-session only.</div>", unsafe_allow_html=True)
