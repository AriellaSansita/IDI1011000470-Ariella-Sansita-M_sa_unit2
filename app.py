import streamlit as st
import datetime as dt
import json
from pathlib import Path

# ---------------- CONFIG ----------------
st.set_page_config(page_title="MedTimer", page_icon="⏰", layout="wide")

# ---------------- DATA ----------------
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
MEDS_PATH = DATA_DIR / "meds.json"
LOG_PATH = DATA_DIR / "log.json"
WEEKDAYS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

def load(p, d): return json.loads(p.read_text()) if p.exists() else d
def save(p, x): p.write_text(json.dumps(x, indent=2))

if "meds" not in st.session_state:
    st.session_state.meds = load(MEDS_PATH, [])

if "log" not in st.session_state:
    st.session_state.log = load(LOG_PATH, {})

if "taken_today" not in st.session_state:
    st.session_state.taken_today = set()

# ---------------- HELPERS ----------------
def today(): return dt.date.today().isoformat()

def parse_time(t):
    try:
        h,m = map(int,t.split(":"))
        return dt.time(h,m)
    except: return None

def schedule():
    out=[]
    now = dt.datetime.now()
    for m in st.session_state.meds:
        t=parse_time(m["time"])
        if not t: continue
        dtm = dt.datetime.combine(dt.date.today(),t)
        k=f"{today()}|{m['name']}|{m['time']}"
        if k in st.session_state.taken_today: s="taken"
        elif now<dtm: s="upcoming"
        else: s="missed"
        out.append((m["name"],m["time"],s,k))
    return out

def streak():
    s=0
    for i in range(30):
        d=(dt.date.today()-dt.timedelta(days=i)).isoformat()
        if d in st.session_state.log and st.session_state.log[d]["taken"]:
            s+=1
        else: break
    return s

def save_today():
    st.session_state.log[today()]={"taken":list(st.session_state.taken_today)}
    save(LOG_PATH, st.session_state.log)

# ---------------- STYLE ----------------
st.markdown("""
<style>
body{background:#f6f9fc;}
.card{background:white;padding:24px;border-radius:18px;
box-shadow:0 4px 20px rgba(0,0,0,.05);margin-bottom:20px;}
.center{height:420px;display:flex;flex-direction:column;
align-items:center;justify-content:center;text-align:center;}
.tip{background:#3fb5a3;color:white;}
.pill{font-size:60px;}
.green{color:#2e7d32;} .yellow{color:#f9a825;} .red{color:#c62828;}
</style>
""", unsafe_allow_html=True)

# ---------------- LAYOUT ----------------
left, center, right = st.columns([1.1,2.2,1.1])

# ---------------- LEFT: ADD MEDICINE ----------------
with left:
    st.markdown("<div class='card'>",unsafe_allow_html=True)
    st.subheader("Add Medicine")

    name=st.text_input("Medicine Name *")
    time=st.text_input("Time (HH:MM) *")
    if st.button("➕ Add Medicine"):
        if name and parse_time(time):
            st.session_state.meds.append({"name":name,"time":time})
            save(MEDS_PATH,st.session_state.meds)
            st.success("Medicine added!")
        else:
            st.error("Invalid input")

    if st.button("🗑️ Clear All"):
        st.session_state.meds=[]
        st.session_state.log={}
        save(MEDS_PATH,[])
        save(LOG_PATH,{})
        st.success("All cleared!")

    st.markdown("</div>",unsafe_allow_html=True)

# ---------------- CENTER: TODAY ----------------
with center:
    st.markdown("<div class='card center'>",unsafe_allow_html=True)
    st.subheader("Today's Checklist")
    sched=schedule()

    if not sched:
        st.markdown("<div class='pill'>💊</div>",unsafe_allow_html=True)
        st.write("No medicines yet")
    else:
        for n,t,s,k in sched:
            c="green" if s=="taken" else "yellow" if s=="upcoming" else "red"
            st.markdown(f"<b>{n}</b> {t} <span class='{c}'>({s})</span>",unsafe_allow_html=True)
            if s!="taken":
                if st.button(f"Mark Taken: {n}",key=k):
                    st.session_state.taken_today.add(k)
                    save_today()
                    st.rerun()

    st.markdown("</div>",unsafe_allow_html=True)

# ---------------- RIGHT SIDE ----------------
with right:
    # Weekly
    st.markdown("<div class='card'>",unsafe_allow_html=True)
    w=len(st.session_state.taken_today)
    st.subheader("Weekly Adherence")
    st.markdown(f"## 🔴 {w*10}%")
    st.progress(min(w/10,1.0))
    st.caption("Reach 80% for a badge!")
    st.markdown("</div>",unsafe_allow_html=True)

    # Mascot
    st.markdown("<div class='card center'>",unsafe_allow_html=True)
    st.markdown("🐢")
    st.subheader("Keep going!")
    st.write(f"Streak: {streak()} day(s)")
    st.markdown("</div>",unsafe_allow_html=True)

    # Tip
    st.markdown("<div class='card tip'>",unsafe_allow_html=True)
    st.subheader("💡 Tip of the Day")
    st.write("If you miss a dose, just take the next one on schedule.")
    st.markdown("</div>",unsafe_allow_html=True)
