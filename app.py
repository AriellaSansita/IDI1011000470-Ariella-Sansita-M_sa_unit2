# app.py
import streamlit as st
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw
import pandas as pd

st.set_page_config(page_title="MedTimer", layout="centered")

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
CARD_TEXT_COLOR = "black"
ZONES = ["UTC", "Asia/Kolkata", "Europe/London", "Europe/Berlin", "America/New_York", "America/Los_Angeles"]

# -----------------------
# session init
# -----------------------
if "page" not in st.session_state:
    st.session_state.page = "today"

# meds: name -> {"time": ["HH:MM",...], "note": str, "days":[...], "freq": int}
if "meds" not in st.session_state:
    st.session_state.meds = {
        "Aspirin": {"time": ["12:00"], "note": "After lunch", "days": WEEKDAYS.copy(), "freq": 1},
        "Vitamin D": {"time": ["18:00"], "note": "With dinner", "days": ["Mon", "Wed", "Fri"], "freq": 1},
        "Iron": {"time": ["08:00"], "note": "Before breakfast", "days": ["Mon","Tue","Wed","Thu","Fri"], "freq": 1},
    }

# history: list of {"med","date","time"} for each taken dose
if "history" not in st.session_state:
    st.session_state.history = []

# daily_scores: date -> {"scheduled":int,"taken":int,"score":int}
if "daily_scores" not in st.session_state:
    st.session_state.daily_scores = {}

if "last_rollover_date" not in st.session_state:
    st.session_state.last_rollover_date = date.today().isoformat()

if "tz" not in st.session_state:
    st.session_state.tz = "Asia/Kolkata"

# -----------------------
# helpers
# -----------------------
def go(p): st.session_state.page = p
def today_str(): return date.today().isoformat()
def parse_hm(s): return datetime.strptime(s, "%H:%M").time()

def scheduled_for_med_on_date(med_info, target_date: date):
    days = med_info.get("days", [])
    if days and WEEKDAYS[target_date.weekday()] not in days:
        return 0
    return len(med_info.get("time", []))

def compute_scheduled_and_taken_for_date(target_date: date):
    scheduled = sum(scheduled_for_med_on_date(info, target_date) for info in st.session_state.meds.values())
    taken = sum(1 for h in st.session_state.history if h["date"] == target_date.isoformat())
    score = int((taken / scheduled) * 100) if scheduled > 0 else 0
    return scheduled, taken, score

def rollover_save_yesterday():
    last = date.fromisoformat(st.session_state.last_rollover_date)
    today = date.today()
    if last < today:
        yesterday = today - timedelta(days=1)
        ystr = yesterday.isoformat()
        if ystr not in st.session_state.daily_scores:
            s, t, sc = compute_scheduled_and_taken_for_date(yesterday)
            st.session_state.daily_scores[ystr] = {"scheduled": s, "taken": t, "score": sc}
        # reset nothing else because we track per-dose via history
        st.session_state.last_rollover_date = today.isoformat()

def is_taken(med, hm, date_str):
    return any(h["med"]==med and h["time"]==hm and h["date"]==date_str for h in st.session_state.history)

def mark_taken_for_time(med, hm):
    st.session_state.history.append({"med": med, "date": today_str(), "time": hm})
    s, t, sc = compute_scheduled_and_taken_for_date(date.today())
    st.session_state.daily_scores[today_str()] = {"scheduled": s, "taken": t, "score": sc}
    st.rerun()

def unmark_taken_for_time(med, hm):
    for i in range(len(st.session_state.history)-1, -1, -1):
        h = st.session_state.history[i]
        if h["med"]==med and h["time"]==hm and h["date"]==today_str():
            st.session_state.history.pop(i)
            break
    s, t, sc = compute_scheduled_and_taken_for_date(date.today())
    st.session_state.daily_scores[today_str()] = {"scheduled": s, "taken": t, "score": sc}
    st.rerun()

def draw_smile(score, size=200):
    img = Image.new("RGB", (size,size), "white")
    d = ImageDraw.Draw(img)
    face = "#b7f5c2" if score>=80 else ("#fff2b2" if score>=50 else "#ffb3b3")
    m = size*0.08
    d.ellipse([m,m,size-m,size-m], fill=face, outline="black")
    er = int(size*0.04)
    d.ellipse([size*0.32-er, size*0.36-er, size*0.32+er, size*0.36+er], fill="black")
    d.ellipse([size*0.68-er, size*0.36-er, size*0.68+er, size*0.36+er], fill="black")
    if score>=80:
        d.arc([size*0.28, size*0.48, size*0.72, size*0.78], start=0, end=180, fill="black", width=4)
    elif score>=50:
        d.line([size*0.36, size*0.62, size*0.64, size*0.62], fill="black", width=4)
    else:
        d.arc([size*0.28, size*0.62, size*0.72, size*0.9], start=180, end=360, fill="black", width=4)
    return img

# -----------------------
# run rollover and ensure today's score exists
# -----------------------
rollover_save_yesterday()
s_today, t_today, sc_today = compute_scheduled_and_taken_for_date(date.today())
st.session_state.daily_scores[today_str()] = {"scheduled": s_today, "taken": t_today, "score": sc_today}

# ---------- Header / nav ----------
st.markdown("<h1 style='text-align:center;'>MedTimer</h1>", unsafe_allow_html=True)
c1,c2,c3 = st.columns([1,1,1])
with c1:
    if st.button("Today"): go("today")
with c2:
    if st.button("All Meds"): go("all_meds")
with c3:
    if st.button("Add / Edit"): go("add")

st.write("")

# timezone select (pure python)
if "tz" not in st.session_state:
    st.session_state.tz = "Asia/Kolkata"
tz = st.selectbox("Select timezone (used for current-time display)", ZONES, index=ZONES.index(st.session_state.tz) if st.session_state.tz in ZONES else 0)
st.session_state.tz = tz
now_local = datetime.now(ZoneInfo(st.session_state.tz))

if st.session_state.page == "today":
    st.markdown(f"**Current time ({st.session_state.tz}):** {now_local.strftime('%H:%M:%S')}")
    st.header("Today's Checklist")
    left, right = st.columns([2,1])

    # LEFT: per-dose cards
    with left:
        any_scheduled = False
        for med, info in st.session_state.meds.items():
            days = info.get("days", [])
            if days and WEEKDAYS[date.today().weekday()] not in days:
                continue
            times = info.get("time", [])
            for hm in times:
                any_scheduled = True
                # compare now to dose time
                hm_time = parse_hm(hm)
                now_t = now_local.time()
                taken_flag = is_taken(med, hm, today_str())
                if taken_flag:
                    bg = "#b7f5c2"; status = "Taken"
                else:
                    bg = "#fff7b0" if now_t <= hm_time else "#ffb3b3"
                    status = "Upcoming" if now_t <= hm_time else "Missed"

                st.markdown(
                    f"""
                    <div style='background:{bg}; padding:12px; border-radius:10px; margin-bottom:8px; width:100%;'>
                      <div style='font-weight:700; font-size:16px; color:{CARD_TEXT_COLOR};'>{med} — {hm}</div>
                      <div style='font-size:14px; color:{CARD_TEXT_COLOR};'>{info.get("note","")}</div>
                      <div style='font-size:13px; color:{CARD_TEXT_COLOR}; margin-top:6px;'><i>{status}</i></div>
                    </div>
                    """, unsafe_allow_html=True)

                cA,cB = st.columns([1,1])
                with cA:
                    if not taken_flag and st.button(f"Take_{med}_{hm}", key=f"take_{med}_{hm}"):
                        mark_taken_for_time(med, hm)
                with cB:
                    if taken_flag and st.button(f"Undo_{med}_{hm}", key=f"undo_{med}_{hm}"):
                        unmark_taken_for_time(med, hm)

        if not any_scheduled:
            st.info("No doses scheduled for today.")

    # RIGHT: daily summary
    with right:
        st.header("Daily Summary")
        sd = st.session_state.daily_scores.get(today_str(), {"scheduled":0,"taken":0,"score":0})
        prog = sd["score"]/100 if sd["scheduled"]>0 else 0
        if not isinstance(prog, (int,float)): prog = 0
        prog = max(0, min(prog, 1))
        st.progress(prog)
        st.markdown(f"**Score:** {sd['score']}%")
        st.markdown(f"**Scheduled doses (today):** {sd['scheduled']}")
        st.markdown(f"**Taken (today):** {sd['taken']}")
        st.image(draw_smile(sd['score']), use_column_width=False)

elif st.session_state.page == "all_meds":
    st.header("All Medications")
    if not st.session_state.meds:
        st.info("No medicines added.")
    else:
        rows = []
        for n, info in st.session_state.meds.items():
            rows.append({
                "Name": n,
                "Times": ", ".join(info.get("time", [])),
                "Days": ", ".join(info.get("days", [])) if info.get("days") else "Every day",
                "Note": info.get("note",""),
                "Freq": info.get("freq", len(info.get("time",[])))
            })
        st.dataframe(pd.DataFrame(rows), height=300)

elif st.session_state.page == "add":
    st.header("Add / Edit Medicines")
    mode = st.radio("Mode", ["Add New", "Edit Existing"])

    if mode == "Add New":
        name = st.text_input("Medicine name")
        note = st.text_input("Note (optional)")
        times_count = st.number_input("How many times per day?", min_value=1, max_value=5, value=1, step=1)
        time_list = []
        for i in range(times_count):
            t = st.time_input(f"Time #{i+1}", value=datetime.strptime("08:00","%H:%M").time(), key=f"add_time_{i}")
            time_list.append(t.strftime("%H:%M"))

        st.markdown("Repeat on days (tick any). Leave none = Every day.")
        cols = st.columns(7)
        day_checks = {wd: cols[i].checkbox(wd) for i, wd in enumerate(WEEKDAYS)}
        selected_days = [d for d, chk in day_checks.items() if chk]

        if st.button("Add medicine"):
            if not name.strip():
                st.warning("Enter a name.")
            else:
                st.session_state.meds[name.strip()] = {"time": time_list, "note": note.strip(), "days": selected_days, "freq": times_count}
                st.success("Added.")
                st.rerun()

    else:
        meds = list(st.session_state.meds.keys())
        if not meds:
            st.info("No meds to edit.")
        else:
            target = st.selectbox("Choose medicine", meds)
            info = st.session_state.meds[target]
            new_name = st.text_input("Name", value=target)
            new_note = st.text_input("Note", value=info.get("note",""))
            old_freq = info.get("freq", len(info.get("time",[])))
            times_count = st.number_input("How many times per day?", min_value=1, max_value=5, value=old_freq, step=1)
            new_times = []
            for i in range(times_count):
                default = info.get("time", ["08:00"])[i] if i < len(info.get("time", [])) else "08:00"
                t = st.time_input(f"Time #{i+1}", value=datetime.strptime(default, "%H:%M").time(), key=f"edit_time_{i}")
                new_times.append(t.strftime("%H:%M"))
            st.markdown("Repeat on days (tick any). Leave none = Every day.")
            cols = st.columns(7)
            day_checks = {wd: cols[i].checkbox(wd, value=(wd in info.get("days", []))) for i, wd in enumerate(WEEKDAYS)}
            selected_days = [d for d, chk in day_checks.items() if chk]

            if st.button("Save"):
                st.session_state.meds.pop(target, None)
                st.session_state.meds[new_name.strip()] = {"time": new_times, "note": new_note.strip(), "days": selected_days, "freq": times_count}
                # update history med names
                for h in st.session_state.history:
                    if h["med"] == target:
                        h["med"] = new_name.strip()
                st.success("Saved.")
                st.rerun()

