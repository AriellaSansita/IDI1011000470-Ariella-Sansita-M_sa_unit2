import streamlit as st
import datetime as dt
import json, csv, math, wave, struct
from pathlib import Path
from io import BytesIO, StringIO

st.set_page_config(page_title="MedTimer", page_icon="⏰", layout="wide")

# ---------------- FILES ----------------
DATA = Path("data"); DATA.mkdir(exist_ok=True)
MEDS = DATA / "meds.json"
LOGS = DATA / "logs.json"

WEEKDAYS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

def load(p, d): return json.loads(p.read_text()) if p.exists() else d
def save(p, d): p.write_text(json.dumps(d, indent=2))

meds = load(MEDS, [])
logs = load(LOGS, {})

# ---------------- STATE ----------------
if "page" not in st.session_state: st.session_state.page = "Today"
if "taken" not in st.session_state: st.session_state.taken = set()
if "reminder" not in st.session_state: st.session_state.reminder = 10
if "date" not in st.session_state: st.session_state.date = dt.date.today().isoformat()

# ---------------- RESET DAILY ----------------
today = dt.date.today().isoformat()
if st.session_state.date != today:
    st.session_state.date = today
    st.session_state.taken = set()

# ---------------- HELPERS ----------------
def parse(t):
    try: h,m = map(int,t.split(":")); return dt.time(h,m)
    except: return None

def build_today():
    now = dt.datetime.now()
    items = []
    for m in meds:
        if WEEKDAYS[now.weekday()] not in m["days"]: continue
        t = parse(m["time"])
        if not t: continue
        when = dt.datetime.combine(now.date(), t)
        key = f"{today}|{m['name']}|{m['time']}"

        if key in st.session_state.taken: status = "taken"
        elif now > when + dt.timedelta(minutes=60): status = "missed"
        else: status = "upcoming"

        items.append({"name":m["name"],"time":t,"status":status,"key":key,"dt":when})
    return sorted(items,key=lambda x:x["time"])

def save_today():
    logs[today] = {"taken": list(st.session_state.taken),
                   "scheduled": len(build_today())}
    save(LOGS, logs)

def adherence(d):
    log = logs.get(d)
    if not log: return 0
    return int((len(log["taken"])/log["scheduled"])*100) if log["scheduled"] else 100

def weekly():
    total = taken = 0
    for i in range(7):
        d = (dt.date.today()-dt.timedelta(days=i)).isoformat()
        if d in logs:
            taken += len(logs[d]["taken"])
            total += logs[d]["scheduled"]
    return int((taken/total)*100) if total else 100

def streak():
    s = 0
    for i in range(30):
        d = (dt.date.today()-dt.timedelta(days=i)).isoformat()
        if adherence(d) >= 80: s+=1
        else: break
    return s

def csv_report():
    s = StringIO(); w = csv.writer(s)
    w.writerow(["Date","Scheduled","Taken","%"])
    for i in range(6,-1,-1):
        d = (dt.date.today()-dt.timedelta(days=i)).isoformat()
        log = logs.get(d,{"taken":[],"scheduled":0})
        pct = int((len(log["taken"])/log["scheduled"])*100) if log["scheduled"] else 0
        w.writerow([d,log["scheduled"],len(log["taken"]),pct])
    return s.getvalue().encode()

def beep():
    buf = BytesIO()
    with wave.open(buf,"wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100)
        for i in range(44100//2):
            val = int(32767*0.4*math.sin(2*math.pi*880*i/44100))
            w.writeframes(struct.pack("<h",val))
    buf.seek(0); return buf

save_today()

# ---------------- NAV ----------------
st.title("⏰ MedTimer")
b1,b2,b3,b4 = st.columns(4)

if b1.button("✅ Today"): st.session_state.page="Today"
if b2.button("📊 Reports"): st.session_state.page="Reports"
if b3.button("⚙️ Medicines"): st.session_state.page="Medicines"
if b4.button("🔔 Settings"): st.session_state.page="Settings"
st.divider()

# ---------------- TODAY ----------------
if st.session_state.page=="Today":
    st.header("✅ Today’s Medicines")
    schedule = build_today()
    now = dt.datetime.now()

    upcoming = [s for s in schedule if 0 <= (s["dt"]-now).seconds//60 <= st.session_state.reminder]

    if upcoming:
        st.warning("Upcoming soon:")
        for u in upcoming:
            st.write(f"• {u['name']} in {int((u['dt']-now).seconds/60)} min")
        if st.button("🔔 Play Reminder"): st.audio(beep())

    for s in schedule:
        color = {"taken":"green","upcoming":"orange","missed":"red"}[s["status"]]
        st.markdown(f"**{s['name']} @ {s['time']}**  :  :{color}[{s['status']}]")

        if s["status"]=="missed": st.warning("Missed dose")

        if s["status"]!="taken":
            if st.button(f"Mark Taken - {s['name']}", key=s["key"]):
                st.session_state.taken.add(s["key"])
                save_today()
                st.rerun()

# ---------------- REPORTS ----------------
elif st.session_state.page=="Reports":
    st.header("📊 Reports")
    score = weekly()
    st.progress(score/100)
    st.write(f"Weekly Adherence: **{score}%**")
    st.info(f"Streak: **{streak()} days**")

    st.download_button("⬇️ Download CSV", csv_report(), "report.csv")

# ---------------- MEDICINES ----------------
elif st.session_state.page=="Medicines":
    st.header("⚙️ Manage Medicines")

    with st.form("add"):
        name = st.text_input("Name")
        time = st.text_input("Time (HH:MM)")
        days = st.multiselect("Days",WEEKDAYS,WEEKDAYS)
        if st.form_submit_button("Add"):
            if name and parse(time):
                meds.append({"name":name,"time":time,"days":days})
                save(MEDS,meds)
                st.success("Added")
                st.rerun()

    for i,m in enumerate(meds):
        with st.expander(f"{m['name']} @ {m['time']}"):
            m["name"] = st.text_input("Name",m["name"],key=f"n{i}")
            m["time"] = st.text_input("Time",m["time"],key=f"t{i}")
            m["days"] = st.multiselect("Days",WEEKDAYS,m["days"],key=f"d{i}")

            if st.button("Save",key=f"s{i}"):
                save(MEDS,meds); st.success("Saved")

            if st.button("Delete",key=f"x{i}"):
                meds.pop(i); save(MEDS,meds); st.rerun()

# ---------------- SETTINGS ----------------
elif st.session_state.page=="Settings":
    st.header("🔔 Settings")
    st.session_state.reminder = st.number_input(
        "Reminder Minutes",0,180,st.session_state.reminder)

    st.markdown("🟢 Taken  |  🟡 Upcoming  |  🔴 Missed")

