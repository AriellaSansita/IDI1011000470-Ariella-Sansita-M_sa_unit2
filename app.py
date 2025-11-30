# app.py
import streamlit as st
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw
import pandas as pd
import random

st.set_page_config(page_title="MedTimer", layout="centered")

# ---------- Simple constants ----------
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
CARD_TEXT_COLOR = "black"

MOTIVATIONAL = [
    "One dose at a time — you're doing great!",
    "You're building a healthy habit. Keep it up!",
    "Consistency matters — nice work!",
]
TIPS = [
    "Keep water nearby when taking meds.",
    "Pair meds with a daily activity (e.g., breakfast).",
]

# ---------- Session init ----------
if "page" not in st.session_state:
    st.session_state.page = "today"

# meds: name -> {"times": ["08:00","20:00"], "note": "", "days": ["Mon",...]}
if "meds" not in st.session_state:
    st.session_state.meds = {
        "Aspirin": {"times": ["12:00"], "note": "After lunch", "days": WEEKDAYS.copy()},
        "Vitamin D": {"times": ["18:00"], "note": "With dinner", "days": ["Mon","Wed","Fri"]},
        "Iron": {"times": ["08:00"], "note": "Before breakfast", "days": ["Mon","Tue","Wed","Thu","Fri"]},
    }

# history: list of {"med":str, "date": "YYYY-MM-DD", "time": "HH:MM"}
if "history" not in st.session_state:
    st.session_state.history = []

# daily_scores saved on rollover (date -> {"scheduled":int,"taken":int,"score":int})
if "daily_scores" not in st.session_state:
    st.session_state.daily_scores = {}

# last rollover date string
if "last_rollover_date" not in st.session_state:
    st.session_state.last_rollover_date = date.today().isoformat()

# ---------- Helpers ----------
def go(p): st.session_state.page = p
def today_str(): return date.today().isoformat()
def parse_hm(s): return datetime.strptime(s, "%H:%M").time()

def scheduled_for_med_on_date(med_info, target_date: date):
    """Count occurrences scheduled for the med on target_date."""
    days = med_info.get("days", [])
    weekday = WEEKDAYS[target_date.weekday()]
    if days and weekday not in days:
        return 0
    times = med_info.get("times", [])
    return len(times) if times else 0

def compute_scheduled_and_taken_for_date(target_date: date):
    scheduled = sum(scheduled_for_med_on_date(m, target_date) for m in st.session_state.meds.values())
    taken = sum(1 for h in st.session_state.history if h["date"] == target_date.isoformat())
    score = int((taken / scheduled) * 100) if scheduled > 0 else 0
    return scheduled, taken, score

def mark_taken_for_time(med, hm_str):
    """Mark a specific med time as taken for today."""
    st.session_state.history.append({"med": med, "date": today_str(), "time": hm_str})
    # update today's saved entry
    sched, taken, score = compute_scheduled_and_taken_for_date(date.today())
    st.session_state.daily_scores[today_str()] = {"scheduled": sched, "taken": taken, "score": score}
    st.rerun()

def unmark_taken_for_time(med, hm_str):
    """Remove last matching history entry for med/time today."""
    for i in range(len(st.session_state.history)-1, -1, -1):
        h = st.session_state.history[i]
        if h["med"] == med and h["date"] == today_str() and h["time"] == hm_str:
            st.session_state.history.pop(i)
            break
    sched, taken, score = compute_scheduled_and_taken_for_date(date.today())
    st.session_state.daily_scores[today_str()] = {"scheduled": sched, "taken": taken, "score": score}
    st.rerun()

def draw_smile(score, size=240):
    img = Image.new("RGB", (size, size), "white")
    d = ImageDraw.Draw(img)
    # nice smiling face for good scores; neutral/sad for others
    if score >= 80:
        face = "#b7f5c2"
    elif score >= 50:
        face = "#fff2b2"
    else:
        face = "#ffb3b3"
    m = size * 0.08
    d.ellipse([m, m, size-m, size-m], fill=face, outline="black")
    eye_r = int(size*0.04)
    d.ellipse([size*0.32-eye_r, size*0.36-eye_r, size*0.32+eye_r, size*0.36+eye_r], fill="black")
    d.ellipse([size*0.68-eye_r, size*0.36-eye_r, size*0.68+eye_r, size*0.36+eye_r], fill="black")
    if score >= 80:
        d.arc([size*0.28, size*0.48, size*0.72, size*0.78], start=0, end=180, fill="black", width=5)
    elif score >= 50:
        d.line([size*0.36, size*0.62, size*0.64, size*0.62], fill="black", width=4)
    else:
        d.arc([size*0.28, size*0.62, size*0.72, size*0.9], start=180, end=360, fill="black", width=5)
    return img

def rollover_save_yesterday():
    last = date.fromisoformat(st.session_state.last_rollover_date)
    today = date.today()
    if last < today:
        yesterday = today - timedelta(days=1)
        y_str = yesterday.isoformat()
        if y_str not in st.session_state.daily_scores:
            sched, taken, score = compute_scheduled_and_taken_for_date(yesterday)
            st.session_state.daily_scores[y_str] = {"scheduled": sched, "taken": taken, "score": score}
        st.session_state.last_rollover_date = today.isoformat()

# ---------- Perform rollover check ----------
rollover_save_yesterday()
# ensure today's entry exists
s, t, sc = compute_scheduled_and_taken_for_date(date.today())
st.session_state.daily_scores[today_str()] = {"scheduled": s, "taken": t, "score": sc}

# ---------- Header & nav ----------
st.markdown("<h1 style='text-align:center;'>MedTimer</h1>", unsafe_allow_html=True)
col1, col2, col3 = st.columns([1,1,1])
with col1:
    if st.button("Today"): go("today")
with col2:
    if st.button("All Meds"): go("all_meds")
with col3:
    if st.button("Add / Edit"): go("add")

st.write("")

# ---------- Timezone selection (only on home page visible) ----------
# simple list of common zones
ZONES = [
    "UTC", "Europe/London", "Europe/Berlin", "Asia/Kolkata",
    "Asia/Shanghai", "Asia/Tokyo", "Australia/Sydney",
    "America/New_York", "America/Chicago", "America/Los_Angeles"
]
if "tz" not in st.session_state:
    st.session_state.tz = "UTC"
if st.session_state.page == "today":
    tz_choice = st.selectbox("Choose your timezone (used for current time):", ZONES, index=ZONES.index(st.session_state.tz) if st.session_state.tz in ZONES else 0)
    st.session_state.tz = tz_choice
    # show current time in chosen zone (calculated on load)
    now = datetime.now(ZoneInfo(st.session_state.tz))
    st.markdown(f"<div style='font-size:14px; color:#000;'>Current time ({st.session_state.tz}): <b>{now.strftime('%H:%M:%S')}</b></div>", unsafe_allow_html=True)

st.write("")

# ---------- PAGE: TODAY (home) ----------
if st.session_state.page == "today":
    st.header("Today's Checklist")
    left, right = st.columns([2, 1])

    # left: meds list (single card per med with all times)
    with left:
        if not st.session_state.meds:
            st.info("No medicines. Go to Add / Edit to add.")
        else:
            now_local = datetime.now(ZoneInfo(st.session_state.tz)).time()
            for mname, info in st.session_state.meds.items():
                times = info.get("times", []) or []
                note = info.get("note", "")
                days = info.get("days", WEEKDAYS.copy())
                # count scheduled today for this med
                wd = WEEKDAYS[date.today().weekday()]
                scheduled_today = []
                if not days or wd in days:
                    scheduled_today = times.copy()
                # compute taken_count today for this med
                taken_times = [h["time"] for h in st.session_state.history if h["med"]==mname and h["date"]==today_str()]

                # card background neutral white; internal colors for labels
                st.markdown(
                    f"""
                    <div style='background:#ffffff; padding:14px; border-radius:12px; margin-bottom:12px; width:100%; box-sizing:border-box;'>
                      <div style='font-size:18px; font-weight:700; color:{CARD_TEXT_COLOR};'>{mname}</div>
                      <div style='font-size:14px; color:{CARD_TEXT_COLOR}; margin-top:6px;'>{note}</div>
                    """,
                    unsafe_allow_html=True
                )

                # list times inside card and show per-time button/status
                for hm in scheduled_today:
                    # parse to compare
                    try:
                        hm_t = parse_hm(hm)
                    except Exception:
                        hm_t = None
                    # determine status: Taken / Upcoming (yellow) / Missed (red)
                    is_taken = hm in taken_times
                    status = "Taken" if is_taken else ("Upcoming" if (hm_t and now_local <= hm_t) else "Missed")
                    color = "#b7f5c2" if is_taken else ("#ffd966" if status=="Upcoming" else "#ffb3b3")
                    # show line with status + button
                    st.markdown(
                        f"""
                        <div style='background:{color}; padding:8px; border-radius:8px; margin:6px 0;'>
                          <div style='display:flex; justify-content:space-between; align-items:center;'>
                            <div style='color:black; font-size:14px;'>
                              <b>{hm}</b> · <span style='font-size:13px;'> {status}</span>
                            </div>
                        """,
                        unsafe_allow_html=True
                    )
                    cols = st.columns([1,1,6])
                    with cols[0]:
                        if not is_taken:
                            if st.button(f"Mark {mname}_{hm}", key=f"take_{mname}_{hm}"):
                                mark_taken_for_time(mname, hm)
                        else:
                            if st.button(f"Undo {mname}_{hm}", key=f"undo_{mname}_{hm}"):
                                unmark_taken_for_time(mname, hm)
                    with cols[2]:
                        st.markdown("</div></div>", unsafe_allow_html=True)

                # summary line inside card
                st.markdown(
                    f"<div style='font-size:13px; color:#333; margin-top:8px;'><b>Taken today:</b> {len([h for h in st.session_state.history if h['med']==mname and h['date']==today_str()])} of {len(scheduled_today) if scheduled_today else 0}</div>",
                    unsafe_allow_html=True
                )
                st.markdown("</div>", unsafe_allow_html=True)

    # right: daily summary and smile
    with right:
        st.header("Daily Summary (Today)")
        sched, taken, score = st.session_state.daily_scores.get(today_str(), {"scheduled":0,"taken":0,"score":0}).values()
        st.progress(score/100 if sched>0 else 0)
        st.markdown(f"**Score:** {score}%")
        st.markdown(f"**Scheduled doses (today):** {sched}")
        st.markdown(f"**Taken (today):** {taken}")
        st.write("")
        st.info(random.choice(MOTIVATIONAL))
        st.success(random.choice(TIPS))
        st.image(draw_smile(score), use_column_width=False)

# ---------- PAGE: ALL MEDS ----------
elif st.session_state.page == "all_meds":
    st.header("All Medicines")
    if not st.session_state.meds:
        st.info("No medicines added.")
    else:
        rows = []
        for n, info in st.session_state.meds.items():
            rows.append({
                "Name": n,
                "Times": ", ".join(info.get("times",[])),
                "Days": ", ".join(info.get("days",[])) if info.get("days") else "Every day",
                "Note": info.get("note","")
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, height=300)

# ---------- PAGE: ADD / EDIT ----------
elif st.session_state.page == "add":
    st.header("Add / Edit Medicines")
    mode = st.radio("Mode", ["Add New", "Edit Existing"])

    if mode == "Add New":
        name = st.text_input("Medicine name")
        note = st.text_input("Note (optional)")
        # frequency label (Once/Twice/Thrice); remove extra freq dropdown
        freq = st.selectbox("Frequency", ["Once", "Twice", "Thrice"])
        st.markdown("**Repeat on days (tick any). Leave all unticked = Every day**")
        cols = st.columns(7)
        selected_days = []
        for i, wd in enumerate(WEEKDAYS):
            if cols[i].checkbox(wd, key=f"add_day_{wd}"):
                selected_days.append(wd)

        # time inputs depending on frequency
        times = []
        if freq == "Once":
            t1 = st.time_input("Time", value=datetime.strptime("08:00","%H:%M").time())
            times = [t1.strftime("%H:%M")]
        elif freq == "Twice":
            t1 = st.time_input("Time 1", value=datetime.strptime("08:00","%H:%M").time(), key="t1")
            t2 = st.time_input("Time 2", value=datetime.strptime("20:00","%H:%M").time(), key="t2")
            times = [t1.strftime("%H:%M"), t2.strftime("%H:%M")]
        else:  # Thrice
            t1 = st.time_input("Time 1", value=datetime.strptime("08:00","%H:%M").time(), key="tt1")
            t2 = st.time_input("Time 2", value=datetime.strptime("13:00","%H:%M").time(), key="tt2")
            t3 = st.time_input("Time 3", value=datetime.strptime("20:00","%H:%M").time(), key="tt3")
            times = [t1.strftime("%H:%M"), t2.strftime("%H:%M"), t3.strftime("%H:%M")]

        if st.button("Add medicine"):
            if not name.strip():
                st.warning("Enter a medicine name.")
            elif name.strip() in st.session_state.meds:
                st.warning("Already exists. Use Edit.")
            else:
                st.session_state.meds[name.strip()] = {"times": times, "note": note.strip(), "days": selected_days}
                st.success("Added.")
                st.rerun()

    else:  # Edit existing
        meds = list(st.session_state.meds.keys())
        if not meds:
            st.info("No meds to edit.")
        else:
            target = st.selectbox("Choose medicine", meds)
            info = st.session_state.meds[target]
            new_name = st.text_input("Name", value=target)
            new_note = st.text_input("Note", value=info.get("note",""))
            freq = st.selectbox("Frequency", ["Once","Twice","Thrice"])
            st.markdown("**Repeat on days (tick any). Leave all unticked = Every day**")
            cols = st.columns(7)
            selected_days = []
            for i, wd in enumerate(WEEKDAYS):
                checked = wd in info.get("days", []) if info.get("days") else False
                if cols[i].checkbox(wd, value=checked, key=f"edit_day_{wd}"):
                    selected_days.append(wd)

            times = []
            if freq == "Once":
                t1 = st.time_input("Time", value=parse_hm(info.get("times",["08:00"])[0]))
                times = [t1.strftime("%H:%M")]
            elif freq == "Twice":
                base = info.get("times", ["08:00","20:00"])
                t1 = st.time_input("Time 1", value=parse_hm(base[0]), key="e1")
                t2 = st.time_input("Time 2", value=parse_hm(base[1]) if len(base)>1 else datetime.strptime("20:00","%H:%M").time(), key="e2")
                times = [t1.strftime("%H:%M"), t2.strftime("%H:%M")]
            else:
                base = info.get("times", ["08:00","13:00","20:00"])
                t1 = st.time_input("Time 1", value=parse_hm(base[0]), key="et1")
                t2 = st.time_input("Time 2", value=parse_hm(base[1]) if len(base)>1 else datetime.strptime("13:00","%H:%M").time(), key="et2")
                t3 = st.time_input("Time 3", value=parse_hm(base[2]) if len(base)>2 else datetime.strptime("20:00","%H:%M").time(), key="et3")
                times = [t1.strftime("%H:%M"), t2.strftime("%H:%M"), t3.strftime("%H:%M")]

            if st.button("Save changes"):
                # replace key if name changed
                st.session_state.meds.pop(target, None)
                st.session_state.meds[new_name.strip()] = {"times": times, "note": new_note.strip(), "days": selected_days}
                # update history med names
                for h in st.session_state.history:
                    if h["med"] == target:
                        h["med"] = new_name.strip()
                st.success("Saved.")
                st.rerun()
