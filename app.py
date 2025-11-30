

import streamlit as st
from datetime import datetime, date, timedelta
from PIL import Image, ImageDraw
import pandas as pd

st.set_page_config(page_title="MedTimer", layout="centered")

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ---------- SESSION INIT ----------
if "page" not in st.session_state:
    st.session_state.page = "today"

if "meds" not in st.session_state:
    st.session_state.meds = {
        "Aspirin": {"time": ["12:00"], "note": "After lunch", "days": WEEKDAYS.copy(), "freq": 1},
        "Vitamin D": {"time": ["18:00"], "note": "With dinner", "days": ["Mon","Wed","Fri"], "freq": 1},
        "Iron": {"time": ["08:00"], "note": "Before breakfast", "days": ["Mon","Tue","Wed","Thu","Fri"], "freq": 1},
    }

if "history" not in st.session_state:
    st.session_state.history = []

if "daily_scores" not in st.session_state:
    st.session_state.daily_scores = {}

if "last_rollover_date" not in st.session_state:
    st.session_state.last_rollover_date = date.today().isoformat()

if "client_time" not in st.session_state:
    st.session_state.client_time = "00:00"


# ---------- HELPERS ----------
def go(p): st.session_state.page = p
def today_str(): return date.today().isoformat()

def parse_time(hm): return datetime.strptime(hm, "%H:%M").time()

def is_taken(med, hm):
    return any(h["med"] == med and h["time"] == hm and h["date"] == today_str()
               for h in st.session_state.history)

def scheduled_today(med_info):
    if med_info["days"] and WEEKDAYS[date.today().weekday()] not in med_info["days"]:
        return 0
    return len(med_info["time"])

def compute_today():
    scheduled = sum(scheduled_today(info) for info in st.session_state.meds.values())
    taken = sum(1 for h in st.session_state.history if h["date"] == today_str())
    score = int((taken / scheduled) * 100) if scheduled > 0 else 0
    return scheduled, taken, score

def rollover():
    last = date.fromisoformat(st.session_state.last_rollover_date)
    today = date.today()
    if last < today:
        y = today - timedelta(days=1)
        ystr = y.isoformat()
        if ystr not in st.session_state.daily_scores:
            sched = sum(scheduled_today(info) for info in st.session_state.meds.values())
            taken = sum(1 for h in st.session_state.history if h["date"] == ystr)
            score = int((taken / sched) * 100) if sched > 0 else 0
            st.session_state.daily_scores[ystr] = {"scheduled": sched, "taken": taken, "score": score}
        st.session_state.last_rollover_date = today.isoformat()

def mark_taken(med, hm):
    st.session_state.history.append({"med": med, "date": today_str(), "time": hm})
    st.rerun()

def unmark_taken(med, hm):
    for i in range(len(st.session_state.history)-1, -1, -1):
        h = st.session_state.history[i]
        if h["med"] == med and h["time"] == hm and h["date"] == today_str():
            st.session_state.history.pop(i)
            break
    st.rerun()

def smile(score, size=200):
    img = Image.new("RGB", (size,size), "white")
    d = ImageDraw.Draw(img)
    face = "#b7f5c2" if score>=80 else ("#fff2b2" if score>=50 else "#ffb3b3")
    m = size*0.08
    d.ellipse([m,m,size-m,size-m], fill=face, outline="black")
    er = int(size*0.04)
    d.ellipse([size*0.32-er, size*0.36-er, size*0.32+er, size*0.36+er], fill="black")
    d.ellipse([size*0.68-er, size*0.36-er, size*0.68+er, size*0.36+er], fill="black")
    if score>=80:
        d.arc([size*0.28, size*0.48, size*0.72, size*0.78], 0, 180, fill="black", width=4)
    elif score>=50:
        d.line([size*0.36, size*0.62, size*0.64, size*0.62], fill="black", width=4)
    else:
        d.arc([size*0.28, size*0.62, size*0.72, size*0.9], 180, 360, fill="black", width=4)
    return img


# ---------- JS: Get client device time (hidden) ----------
st.markdown("""
<script>
function sendTime() {
    const now = new Date();
    const hm = now.getHours().toString().padStart(2,'0') + ":" +
               now.getMinutes().toString().padStart(2,'0');
    const input = document.getElementById("client_time_input");
    if (input) { input.value = hm; input.dispatchEvent(new Event("input")); }
}
setInterval(sendTime, 1000);
sendTime();
</script>
""", unsafe_allow_html=True)

client_time = st.text_input("",
    key="client_time_input",
    label_visibility="collapsed"
)

if client_time:
    st.session_state.client_time = client_time


# ---------- ROLLOVER ----------
rollover()


# ---------- HEADER ----------
st.markdown("<h1 style='text-align:center;'>MedTimer</h1>", unsafe_allow_html=True)

c1,c2,c3 = st.columns([1,1,1])
with c1:
    if st.button("Today"): go("today")
with c2:
    if st.button("All Meds"): go("all_meds")
with c3:
    if st.button("Add / Edit"): go("add")


# ---------- TODAY PAGE ----------
if st.session_state.page == "today":
    st.header("Today's Doses")

    left, right = st.columns([2,1])

    with left:
        any_doses = False
        now_t = parse_time(st.session_state.client_time)

        for med, info in st.session_state.meds.items():
            if info["days"] and WEEKDAYS[date.today().weekday()] not in info["days"]:
                continue

            for hm in info["time"]:
                any_doses = True
                hm_t = parse_time(hm)
                taken = is_taken(med, hm)

                if taken:
                    bg = "#b7f5c2"; status = "Taken"
                else:
                    bg = "#fff7b0" if now_t <= hm_t else "#ffb3b3"
                    status = "Upcoming" if now_t <= hm_t else "Missed"

                st.markdown(
                    f"""
                    <div style='background:{bg};
                                padding:15px;
                                border-radius:10px;
                                margin-bottom:10px;'>
                      <b>{med}</b> — {hm}<br>
                      <i>{info["note"]}</i><br>
                      <span style='color:black;'>{status}</span>
                    </div>
                    """,
                    unsafe_allow_html=True)

                cA, cB = st.columns([1,1])
                with cA:
                    if not taken and st.button(f"Take-{med}-{hm}", key=f"take_{med}_{hm}"):
                        mark_taken(med, hm)
                with cB:
                    if taken and st.button(f"Undo-{med}-{hm}", key=f"undo_{med}_{hm}"):
                        unmark_taken(med, hm)

        if not any_doses:
            st.info("No doses scheduled today.")

    with right:
        st.header("Daily Summary")
        sched, taken, score = compute_today()
        st.progress(score/100 if score <= 100 else 1)
        st.write(f"**Score:** {score}%")
        st.write(f"**Scheduled:** {sched}")
        st.write(f"**Taken:** {taken}")
        st.image(smile(score))


# ---------- ALL MEDS ----------
elif st.session_state.page == "all_meds":
    st.header("All Medications")
    if not st.session_state.meds:
        st.info("No medicines added.")
    else:
        rows = []
        for n, info in st.session_state.meds.items():
            rows.append({
                "Name": n,
                "Times": ", ".join(info["time"]),
                "Days": ", ".join(info["days"]) if info["days"] else "Every day",
                "Note": info["note"],
                "Freq": info["freq"],
            })
        st.dataframe(pd.DataFrame(rows), height=300)


# ---------- ADD / EDIT ----------
elif st.session_state.page == "add":
    st.header("Add / Edit Medicines")
    mode = st.radio("Mode", ["Add New", "Edit Existing"])

    # ----- Add -----
    if mode == "Add New":
        name = st.text_input("Medicine name")
        note = st.text_input("Note (optional)")
        freq = st.number_input("How many doses per day?", 1, 5, 1)

        times = []
        for i in range(freq):
            t = st.time_input(f"Dose time #{i+1}")
            times.append(t.strftime("%H:%M"))

        st.write("Repeat on days:")
        cols = st.columns(7)
        day_checks = {wd: cols[i].checkbox(wd) for i, wd in enumerate(WEEKDAYS)}
        sel = [d for d, c in day_checks.items() if c]

        if st.button("Add"):
            if not name.strip():
                st.warning("Enter a name")
            else:
                st.session_state.meds[name.strip()] = {
                    "time": times,
                    "note": note,
                    "days": sel,
                    "freq": freq,
                }
                st.success("Added")
                st.rerun()

    # ----- Edit -----
    else:
        meds = list(st.session_state.meds.keys())
        if not meds:
            st.info("No medicines to edit.")
        else:
            target = st.selectbox("Select medicine", meds)
            info = st.session_state.meds[target]

            new_name = st.text_input("Name", value=target)
            new_note = st.text_input("Note", value=info["note"])
            freq = st.number_input("How many doses per day?", 1, 5, info["freq"])

            new_times = []
            for i in range(freq):
                default = info["time"][i] if i < len(info["time"]) else "08:00"
                t = st.time_input(f"Dose time #{i+1}",
                                  value=datetime.strptime(default, "%H:%M").time())
                new_times.append(t.strftime("%H:%M"))

            st.write("Repeat on days:")
            cols = st.columns(7)
            day_checks = {
                wd: cols[i].checkbox(wd, value=(wd in info["days"]))
                for i, wd in enumerate(WEEKDAYS)
            }
            sel = [d for d, c in day_checks.items() if c]

            if st.button("Save"):
                st.session_state.meds.pop(target)
                st.session_state.meds[new_name] = {
                    "time": new_times,
                    "note": new_note,
                    "days": sel,
                    "freq": freq,
                }
                for h in st.session_state.history:
                    if h["med"] == target:
                        h["med"] = new_name
                st.success("Saved")
                st.rerun()

