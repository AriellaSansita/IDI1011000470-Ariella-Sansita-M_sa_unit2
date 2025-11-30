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
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

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
# SESSION STATE init
# -----------------------
if "page" not in st.session_state:
    st.session_state.page = "today"

if "meds" not in st.session_state:
    st.session_state.meds = {
        "Aspirin": {"time":"12:00","note":"After lunch","taken_today":False,"days":WEEKDAYS.copy(),"freq":"Once"},
        "Vitamin D": {"time":"18:00","note":"With dinner","taken_today":False,"days":["Mon","Wed","Fri"],"freq":"Once"},
        "Iron": {"time":"08:00","note":"Before breakfast","taken_today":False,"days":["Mon","Tue","Wed","Thu","Fri"],"freq":"Once"},
    }

if "history" not in st.session_state:
    st.session_state.history = []

if "daily_scores" not in st.session_state:
    st.session_state.daily_scores = {}

if "last_rollover_date" not in st.session_state:
    st.session_state.last_rollover_date = date.today().isoformat()

# -----------------------
# HELPERS
# -----------------------
def go(p): st.session_state.page = p

def today_str(): return date.today().isoformat()

def now_time_str_server(): return datetime.now().strftime("%H:%M")

def date_is_even(d: date):
    return (d.toordinal() % 2) == 0

def reset_daily_rollover():
    last = date.fromisoformat(st.session_state.last_rollover_date)
    today = date.today()
    if last < today:
        yesterday = today - timedelta(days=1)
        y_str = yesterday.isoformat()

        scheduled_y = 0
        for med, info in st.session_state.meds.items():
            scheduled_y += scheduled_for_med_on_date(info, yesterday)

        taken_y = sum(1 for h in st.session_state.history if h["date"] == y_str)
        score_y = int((taken_y / scheduled_y) * 100) if scheduled_y > 0 else 0

        if y_str not in st.session_state.daily_scores:
            st.session_state.daily_scores[y_str] = {
                "scheduled": scheduled_y,
                "taken": taken_y,
                "score": score_y
            }

        for m in st.session_state.meds.values():
            m["taken_today"] = False

        st.session_state.last_rollover_date = today.isoformat()

def occurrences_per_day_from_freq(freq):
    if freq == "Once": return 1
    if freq == "Twice": return 2
    if freq == "Thrice": return 3
    return 1

def scheduled_for_med_on_date(med_info, target_date: date):
    days = med_info.get("days", [])
    freq = med_info.get("freq", "Once")
    weekday_name = WEEKDAYS[target_date.weekday()]

    if days:
        day_selected = weekday_name in days
    else:
        day_selected = True

    if freq == "Every other day":
        if not day_selected:
            return 0
        return 1 if date_is_even(target_date) else 0

    occ = occurrences_per_day_from_freq(freq)
    return occ if day_selected else 0

def compute_scheduled_and_taken_for_date(target_date: date):
    scheduled = sum(scheduled_for_med_on_date(info, target_date) for info in st.session_state.meds.values())
    taken = sum(1 for h in st.session_state.history if h["date"] == target_date.isoformat())
    score = int((taken / scheduled) * 100) if scheduled > 0 else 0
    return scheduled, taken, score

def mark_taken(med):
    st.session_state.meds[med]["taken_today"] = True
    st.session_state.history.append({
        "med": med,
        "date": today_str(),
        "time": now_time_str_server()
    })
    sched, taken, score = compute_scheduled_and_taken_for_date(date.today())
    st.session_state.daily_scores[today_str()] = {"scheduled": sched, "taken": taken, "score": score}
    st.rerun()

def unmark_taken(med):
    st.session_state.meds[med]["taken_today"] = False
    for i in range(len(st.session_state.history)-1, -1, -1):
        if st.session_state.history[i]["med"] == med and st.session_state.history[i]["date"] == today_str():
            st.session_state.history.pop(i)
            break
    sched, taken, score = compute_scheduled_and_taken_for_date(date.today())
    st.session_state.daily_scores[today_str()] = {"scheduled": sched, "taken": taken, "score": score}
    st.rerun()

def delete_med(med):
    st.session_state.meds.pop(med, None)
    st.session_state.history = [h for h in st.session_state.history if h["med"] != med]
    sched, taken, score = compute_scheduled_and_taken_for_date(date.today())
    st.session_state.daily_scores[today_str()] = {"scheduled": sched, "taken": taken, "score": score}
    st.rerun()

def draw_smiley(score, size_px=260):
    img = Image.new("RGB", (size_px, size_px), "white")
    d = ImageDraw.Draw(img)

    if score >= 80:
        face = "#b7f5c2"
    elif score >= 50:
        face = "#fff2b2"
    else:
        face = "#ffb3b3"

    m = size_px * 0.08
    d.ellipse([m, m, size_px-m, size_px-m], fill=face, outline="black")
    eye_r = int(size_px * 0.04)
    d.ellipse([size_px*0.32-eye_r, size_px*0.38-eye_r, size_px*0.32+eye_r, size_px*0.38+eye_r], fill="black")
    d.ellipse([size_px*0.68-eye_r, size_px*0.38-eye_r, size_px*0.68+eye_r, size_px*0.38+eye_r], fill="black")

    d.arc([size_px*0.28, size_px*0.46, size_px*0.72, size_px*0.72], start=0, end=180, fill="black", width=4)

    return img

# -----------------------
reset_daily_rollover()
sched_today, taken_today, score_today = compute_scheduled_and_taken_for_date(date.today())
st.session_state.daily_scores[today_str()] = {
    "scheduled": sched_today,
    "taken": taken_today,
    "score": score_today
}

# -----------------------
# HEADER + NAV
# -----------------------
st.markdown("<h1 style='text-align:center; margin-bottom:8px;'>MedTimer</h1>", unsafe_allow_html=True)

nav1, nav2, nav3, nav4 = st.columns([1,1,1,1])
with nav1:
    if st.button("Today"): go("today")
with nav2:
    if st.button("All Meds"): go("all_meds")
with nav3:
    if st.button("Add / Edit"): go("add")
with nav4:
    if st.button("Summary"): go("summary")

st.write("")

# client-local time (white)
st.markdown(
    """
    <div style='font-size:14px; color:white;'>
      Current time: <span id="client_time" style="color:white;">--:--:--</span>
    </div>
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

# -----------------------
# PAGE: TODAY
# -----------------------
if st.session_state.page == "today":
    st.header("Today's Checklist")
    left, right = st.columns([2,1])

    with left:
        if len(st.session_state.meds) == 0:
            st.info("No medicines added yet.")
        else:
            for idx, (med, info) in enumerate(st.session_state.meds.items()):
                due = info.get("time","--:--")
                note = info.get("note","")
                taken = info.get("taken_today", False)
                now_server = now_time_str_server()

                if taken:
                    bg = "#b7f5c2"; status_text = "Taken"
                else:
                    bg = "#fff7b0" if now_server <= due else "#ffb3b3"
                    status_text = "Upcoming" if now_server <= due else "Missed"

                st.markdown(
                    f"""
                    <div style='background:{bg}; padding:16px; border-radius:12px; margin-bottom:12px;'>
                      <div style='font-size:18px; font-weight:600; color:black;'>{med} — {due}</div>
                      <div style='font-size:15px; color:black;'>{note}</div>
                      <div style='font-size:14px; color:black;'><i>{status_text}</i></div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                c1, c2, c3 = st.columns([1,1,1])
                with c1:
                    if (not taken) and st.button(f"Take {med}", key=f"take_{idx}"):
                        mark_taken(med)
                with c2:
                    if taken and st.button(f"Undo {med}", key=f"undo_{idx}"):
                        unmark_taken(med)
                with c3:
                    if st.button(f"Delete {med}", key=f"del_{idx}"):
                        delete_med(med)

    with right:
        st.header("Daily Summary")
        sd = st.session_state.daily_scores[today_str()]

        # --- FIXED PROGRESS BAR ---
        progress_value = sd["score"] / 100 if sd["scheduled"] > 0 else 0
        if not isinstance(progress_value, (int, float)):
            progress_value = 0
        progress_value = max(0, min(progress_value, 1))
        st.progress(progress_value)

        st.write(f"**Score:** {sd['score']}%")
        st.write(f"**Scheduled:** {sd['scheduled']}")
        st.write(f"**Taken:** {sd['taken']}")

        img = draw_smiley(sd["score"])
        st.image(img)

# -----------------------
elif st.session_state.page == "all_meds":
    st.header("All Medications")
    if len(st.session_state.meds) == 0:
        st.info("No medicines yet.")
    else:
        df = pd.DataFrame([
            {
                "Name": name,
                "Time": info["time"],
                "Note": info["note"],
                "Days": ",".join(info["days"]) if info["days"] else "Every day",
                "Freq": info["freq"],
                "Taken Today": info["taken_today"]
            }
            for name, info in st.session_state.meds.items()
        ])
        st.dataframe(df)

# -----------------------
elif st.session_state.page == "add":
    st.header("Add / Edit Medicines")
    mode = st.radio("Mode", ["Add New", "Edit Existing"])

    if mode == "Add New":
        name = st.text_input("Medicine name")
        time_val = st.time_input("Time")
        note = st.text_input("Note")

        cols = st.columns(7)
        day_checks = {wd: cols[i].checkbox(wd) for i, wd in enumerate(WEEKDAYS)}
        selected_days = [d for d, chk in day_checks.items() if chk]

        freq = st.selectbox("Frequency", ["Once", "Twice", "Thrice", "Every other day"])

        if st.button("Add"):
            st.session_state.meds[name] = {
                "time": time_val.strftime("%H:%M"),
                "note": note,
                "taken_today": False,
                "days": selected_days,
                "freq": freq
            }
            st.rerun()

    else:
        meds_list = list(st.session_state.meds.keys())
        if len(meds_list) == 0:
            st.info("No meds to edit.")
        else:
            target = st.selectbox("Select", meds_list)
            info = st.session_state.meds[target]

            name = st.text_input("Name", value=target)
            time_val = st.time_input("Time", value=datetime.strptime(info["time"], "%H:%M").time())
            note = st.text_input("Note", value=info["note"])

            cols = st.columns(7)
            day_checks = {wd: cols[i].checkbox(wd, value=(wd in info["days"])) for i, wd in enumerate(WEEKDAYS)}
            selected_days = [d for d, chk in day_checks.items() if chk]

            freq = st.selectbox("Frequency", ["Once", "Twice", "Thrice", "Every other day"])

            if st.button("Save"):
                st.session_state.meds.pop(target)
                st.session_state.meds[name] = {
                    "time": time_val.strftime("%H:%M"),
                    "note": note,
                    "taken_today": False,
                    "days": selected_days,
                    "freq": freq
                }
                st.rerun()

# -----------------------
# END
# -----------------------
