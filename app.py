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

# history: list of {"med","date","time"} for each taken event
if "history" not in st.session_state:
    st.session_state.history = []

# daily_scores: dict date-> {"scheduled":int,"taken":int,"score":int}
if "daily_scores" not in st.session_state:
    st.session_state.daily_scores = {}

# track last date when we saved/rolled over
if "last_rollover_date" not in st.session_state:
    st.session_state.last_rollover_date = date.today().isoformat()

# -----------------------
# HELPERS
# -----------------------
def go(p): st.session_state.page = p

def today_str(): return date.today().isoformat()

def now_time_str_server(): return datetime.now().strftime("%H:%M")

def date_is_even(d: date):
    # simple rule for "every other day" — even ordinal
    return (d.toordinal() % 2) == 0

def reset_daily_rollover():
    """If we detect that date changed since last_rollover_date, save yesterday's stats and reset taken_today."""
    last = date.fromisoformat(st.session_state.last_rollover_date)
    today = date.today()
    if last < today:
        # Save stats for each day from (last + 1) up to yesterday if there were skipped days.
        # But simplest: save for 'last' (yesterday) only, and also ensure not duplicating.
        # We'll compute yesterday = today - 1
        yesterday = today - timedelta(days=1)
        y_str = yesterday.isoformat()
        # compute scheduled & taken for yesterday from meds & history
        scheduled_y = 0
        for med, info in st.session_state.meds.items():
            scheduled_y += scheduled_for_med_on_date(info, yesterday)
        taken_y = sum(1 for h in st.session_state.history if h["date"] == y_str)
        score_y = int((taken_y / scheduled_y) * 100) if scheduled_y > 0 else 0
        # only save if not already present
        if y_str not in st.session_state.daily_scores:
            st.session_state.daily_scores[y_str] = {"scheduled": scheduled_y, "taken": taken_y, "score": score_y}
        # Reset today's taken flags
        for m in st.session_state.meds.values():
            m["taken_today"] = False
        st.session_state.last_rollover_date = today.isoformat()

def occurrences_per_day_from_freq(freq):
    if freq == "Once": return 1
    if freq == "Twice": return 2
    if freq == "Thrice": return 3
    # Every other day handled in scheduled_for_med_on_date
    return 1

def scheduled_for_med_on_date(med_info, target_date: date):
    """
    Determine how many scheduled occurrences there are for this med on the given date.
    - If med_info['days'] is empty => every day
    - freq controls occurrences per scheduled day (Once/Twice/Thrice)
    - Every other day: use simple even/odd rule (date ordinal even => scheduled)
    """
    days = med_info.get("days", [])
    freq = med_info.get("freq", "Once")
    weekday_name = WEEKDAYS[target_date.weekday()]  # Mon..Sun
    # check day selection
    day_selected = False
    if not days:
        day_selected = True
    else:
        day_selected = weekday_name in days
    if freq == "Every other day":
        # require day_selected AND even-date rule
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
    # add history and set flag; mark time as server time for record
    st.session_state.meds[med]["taken_today"] = True
    st.session_state.history.append({"med": med, "date": today_str(), "time": now_time_str_server()})
    # Also update today's daily_scores in-memory (not persisted across reloads except in session_state)
    sched, taken, score = compute_scheduled_and_taken_for_date(date.today())
    st.session_state.daily_scores[today_str()] = {"scheduled": sched, "taken": taken, "score": score}
    st.rerun()

def unmark_taken(med):
    st.session_state.meds[med]["taken_today"] = False
    # remove last matching history entry for today
    for i in range(len(st.session_state.history)-1, -1, -1):
        h = st.session_state.history[i]
        if h["med"] == med and h["date"] == today_str():
            st.session_state.history.pop(i)
            break
    sched, taken, score = compute_scheduled_and_taken_for_date(date.today())
    st.session_state.daily_scores[today_str()] = {"scheduled": sched, "taken": taken, "score": score}
    st.rerun()

def delete_med(med):
    st.session_state.meds.pop(med, None)
    # remove history entries for that med
    st.session_state.history = [h for h in st.session_state.history if h["med"] != med]
    # recompute today's stats
    sched, taken, score = compute_scheduled_and_taken_for_date(date.today())
    st.session_state.daily_scores[today_str()] = {"scheduled": sched, "taken": taken, "score": score}
    st.rerun()

# -----------------------
# DRAW PIL smiley
# -----------------------
def draw_smiley(score, size_px=260):
    img = Image.new("RGB", (size_px, size_px), "white")
    d = ImageDraw.Draw(img)
    if score >= 90:
        d.rectangle([size_px*0.33, size_px*0.28, size_px*0.66, size_px*0.56], fill="#FFD700", outline="black")
        d.rectangle([size_px*0.43, size_px*0.56, size_px*0.57, size_px*0.68], fill="#FFD700", outline="black")
        d.text((size_px*0.35, size_px*0.12), "Great!", fill="black")
        return img
    if score >= 80: face = "#b7f5c2"
    elif score >= 50: face = "#fff2b2"
    else: face = "#ffb3b3"
    m = size_px * 0.08
    d.ellipse([m, m, size_px-m, size_px-m], fill=face, outline="black")
    eye_r = int(size_px * 0.04)
    d.ellipse([size_px*0.32-eye_r, size_px*0.38-eye_r, size_px*0.32+eye_r, size_px*0.38+eye_r], fill="black")
    d.ellipse([size_px*0.68-eye_r, size_px*0.38-eye_r, size_px*0.68+eye_r, size_px*0.38+eye_r], fill="black")
    if score >= 80:
        d.arc([size_px*0.28, size_px*0.46, size_px*0.72, size_px*0.72], start=0, end=180, fill="black", width=4)
    elif score >= 50:
        d.line([size_px*0.36, size_px*0.62, size_px*0.64, size_px*0.62], fill="black", width=4)
    else:
        d.arc([size_px*0.28, size_px*0.56, size_px*0.72, size_px*0.82], start=180, end=360, fill="black", width=4)
    return img

# -----------------------
# ROLLOVER CHECK (save yesterday if we crossed midnight)
# -----------------------
reset_daily_rollover()  # will save yesterday and reset flags when needed

# Also ensure today's daily_scores exists (so UI shows immediate numbers)
sched_today, taken_today, score_today = compute_scheduled_and_taken_for_date(date.today())
st.session_state.daily_scores[today_str()] = {"scheduled": sched_today, "taken": taken_today, "score": score_today}

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

st.write("")  # gap

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
                # status
                if taken:
                    bg = "#b7f5c2"; status_text = "Taken"
                else:
                    bg = "#bfe4ff" if now_server <= due else "#ffb3b3"
                    status_text = "Upcoming" if now_server <= due else "Missed"

                st.markdown(
                    f"""
                    <div style='background:{bg}; padding:16px; border-radius:12px; margin-bottom:12px; width:100%; box-sizing:border-box;'>
                      <div style='font-size:18px; font-weight:600; color:{CARD_TEXT_COLOR};'>{med} — {due}</div>
                      <div style='font-size:15px; color:{CARD_TEXT_COLOR}; margin-top:6px;'>{note}</div>
                      <div style='font-size:14px; color:{CARD_TEXT_COLOR}; margin-top:6px;'><i>{status_text}</i></div>
                      <div style='font-size:13px; color:#333; margin-top:6px;'><b>Repeats:</b> {', '.join(info.get('days',[])) or 'Every day'} · <b>Freq:</b> {info.get('freq','Once')}</div>
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
        st.header("Daily Summary (Today)")
        sd = st.session_state.daily_scores.get(today_str(), {"scheduled":0,"taken":0,"score":0})
        st.progress(sd["score"]/100 if sd["scheduled"]>0 else 0)
        st.markdown(f"**Score:** {sd['score']}%")
        st.markdown(f"**Scheduled doses (today):** {sd['scheduled']}")
        st.markdown(f"**Taken (today):** {sd['taken']}")
        st.write("")
        st.info(random.choice(MOTIVATIONAL))
        st.success(random.choice(TIPS))
        img = draw_smiley(sd["score"], size_px=260)
        st.image(img)

# -----------------------
# PAGE: ALL MEDS
# -----------------------
elif st.session_state.page == "all_meds":
    st.header("All Medications")
    if len(st.session_state.meds) == 0:
        st.info("No medicines yet.")
    else:
        df = pd.DataFrame([
            {"Name": name, "Time": info.get("time",""), "Note": info.get("note",""), "Days": ",".join(info.get("days",[])) if info.get("days") else "Every day", "Freq": info.get("freq","Once"), "Taken Today": info.get("taken_today", False)}
            for name, info in st.session_state.meds.items()
        ])
        st.dataframe(df, height=300)

# -----------------------
# PAGE: ADD / EDIT
# -----------------------
elif st.session_state.page == "add":
    st.header("Add / Edit Medicines")
    mode = st.radio("Mode", ["Add New", "Edit Existing"])
    preset_options = ["(none)","Every day","Weekdays (Mon–Fri)","Weekends (Sat–Sun)","Every other day","Twice per day","Thrice per day"]

    if mode == "Add New":
        name = st.text_input("Medicine name")
        time_val = st.time_input("Time", value=datetime.strptime("08:00","%H:%M").time())
        note = st.text_input("Note (optional)")

        c1, c2 = st.columns([1,1])
        with c1:
            preset = st.selectbox("Quick preset (sets days/freq)", preset_options, index=0)
        with c2:
            freq = st.selectbox("Frequency", ["Once","Twice","Thrice","Every other day"])

        st.markdown("**Repeat on days (tick any)**")
        cols = st.columns(7)
        # compute default_days based on preset
        default_days = []
        if preset == "Every day":
            default_days = WEEKDAYS.copy()
        elif preset == "Weekdays (Mon–Fri)":
            default_days = WEEKDAYS[:5]
        elif preset == "Weekends (Sat–Sun)":
            default_days = WEEKDAYS[5:]
        elif preset == "Every other day":
            default_days = ["Mon","Wed","Fri","Sun"]
            freq = "Every other day"
        elif preset == "Twice per day":
            default_days = WEEKDAYS.copy()
            freq = "Twice"
        elif preset == "Thrice per day":
            default_days = WEEKDAYS.copy()
            freq = "Thrice"

        day_checks = {}
        for i, wd in enumerate(WEEKDAYS):
            checked = wd in default_days
            day_checks[wd] = cols[i].checkbox(wd, value=checked, key=f"add_day_{wd}")

        selected_days = [d for d, chk in day_checks.items() if chk]

        if st.button("Add medicine"):
            if name.strip() == "":
                st.warning("Enter a name.")
            elif name.strip() in st.session_state.meds:
                st.warning("Already exists. Edit instead.")
            else:
                st.session_state.meds[name.strip()] = {
                    "time": time_val.strftime("%H:%M"),
                    "note": note.strip(),
                    "taken_today": False,
                    "days": selected_days,
                    "freq": freq
                }
                st.success("Added.")
                st.rerun()

    else:  # edit existing
        meds_list = list(st.session_state.meds.keys())
        if len(meds_list) == 0:
            st.info("No meds to edit.")
        else:
            target = st.selectbox("Choose medicine to edit", meds_list)
            info = st.session_state.meds[target]
            new_name = st.text_input("Name", value=target)
            new_time = st.time_input("Time", value=datetime.strptime(info.get("time","08:00"), "%H:%M").time())
            new_note = st.text_input("Note", value=info.get("note",""))
            preset = st.selectbox("Quick preset (overrides days if chosen)", preset_options, index=0)
            freq = st.selectbox("Frequency", ["Once","Twice","Thrice","Every other day"], index=0 if info.get("freq","Once")=="Once" else (1 if info.get("freq")=="Twice" else 2))
            st.markdown("**Repeat on days (tick any)**")
            cols = st.columns(7)
            default_days = []
            if preset == "Every day":
                default_days = WEEKDAYS.copy()
            elif preset == "Weekdays (Mon–Fri)":
                default_days = WEEKDAYS[:5]
            elif preset == "Weekends (Sat–Sun)":
                default_days = WEEKDAYS[5:]
            elif preset == "Every other day":
                default_days = ["Mon","Wed","Fri","Sun"]
                freq = "Every other day"
            elif preset == "Twice per day":
                default_days = WEEKDAYS.copy()
                freq = "Twice"
            elif preset == "Thrice per day":
                default_days = WEEKDAYS.copy()
                freq = "Thrice"
            else:
                default_days = info.get("days", []) if info.get("days") else WEEKDAYS.copy()

            edit_checks = {}
            for i, wd in enumerate(WEEKDAYS):
                checked = wd in default_days
                if preset == "(none)":
                    checked = wd in info.get("days", []) if info.get("days") else True
                edit_checks[wd] = cols[i].checkbox(wd, value=checked, key=f"edit_day_{wd}")

            selected_days = [d for d, chk in edit_checks.items() if chk]

            if st.button("Save changes"):
                st.session_state.meds.pop(target, None)
                st.session_state.meds[new_name.strip()] = {
                    "time": new_time.strftime("%H:%M"),
                    "note": new_note.strip(),
                    "taken_today": False,
                    "days": selected_days,
                    "freq": freq
                }
                # update history med names
                for h in st.session_state.history:
                    if h["med"] == target:
                        h["med"] = new_name.strip()
                st.success("Saved.")
                st.rerun()

# -----------------------
# PAGE: SUMMARY (new page)
# -----------------------
elif st.session_state.page == "summary":
    st.header("Summary — Daily / Weekly / Monthly")
    st.write("This page shows saved daily scores (every day is saved at the first app load after midnight).")

    # Build dataframe of daily_scores
    ds = st.session_state.daily_scores.copy()
    # ensure today's current stats also present (not only saved ones)
    ds[today_str()] = st.session_state.daily_scores.get(today_str(), {"scheduled": sched_today, "taken": taken_today, "score": score_today})

    if len(ds) == 0:
        st.info("No daily data recorded yet.")
    else:
        df = pd.DataFrame([
            {"date": d, "scheduled": v["scheduled"], "taken": v["taken"], "score": v["score"]}
            for d, v in ds.items()
        ])
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')

        st.subheader("Daily scores (all recorded days)")
        # show table
        st.dataframe(df.reset_index(drop=True), height=260)
        # daily bar chart (show all days)
        st.markdown("**Daily % (each day)**")
        daily_series = pd.Series(df['score'].values, index=df['date'].dt.strftime('%Y-%m-%d'))
        st.bar_chart(daily_series)

        st.write("")  # gap
        # Weekly aggregation (Monday-Sunday average)
        st.subheader("Weekly (Mon–Sun) average %")
        df['year_week'] = df['date'].dt.strftime('%G-W%V')  # ISO year-week
        weekly = df.groupby('year_week')['score'].mean().round(0).astype(int)
        st.bar_chart(weekly)

        st.write("")
        # Monthly aggregation
        st.subheader("Monthly average %")
        df['year_month'] = df['date'].dt.strftime('%Y-%m')
        monthly = df.groupby('year_month')['score'].mean().round(0).astype(int)
        st.bar_chart(monthly)

        st.write("")
        # CSV download of daily scores
        csv = df[['date','scheduled','taken','score']].to_csv(index=False)
        st.download_button("Download daily scores CSV", csv, file_name="daily_scores.csv", mime="text/csv")

# -----------------------
# END (no footer text)
# -----------------------
