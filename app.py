
import streamlit as st
from datetime import datetime, date, timedelta
from PIL import Image, ImageDraw

st.set_page_config(page_title="MedTimer", layout="centered")

WEEKDAYS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

# -------------------------
# SESSION STATE INIT
# -------------------------
if "meds" not in st.session_state:
    st.session_state.meds = {
        "Aspirin": {
            "doses": ["12:00"],
            "note": "After lunch",
            "days": WEEKDAYS.copy()
        }
    }

if "history" not in st.session_state:
    st.session_state.history = []

if "daily_scores" not in st.session_state:
    st.session_state.daily_scores = {}

if "last_rollover" not in st.session_state:
    st.session_state.last_rollover = date.today().isoformat()

# -------------------------
# HELPERS
# -------------------------
def today_str():
    return date.today().isoformat()

def now_server():
    return datetime.now().strftime("%H:%M")

def rollover_if_needed():
    last = date.fromisoformat(st.session_state.last_rollover)
    today = date.today()
    if today > last:
        yesterday = today - timedelta(days=1)
        y = yesterday.isoformat()

        scheduled = 0
        for m,info in st.session_state.meds.items():
            scheduled += len(info["doses"])

        taken = sum(1 for h in st.session_state.history if h["date"] == y)

        score = int((taken/scheduled)*100) if scheduled>0 else 0
        st.session_state.daily_scores[y] = {
            "scheduled": scheduled,
            "taken": taken,
            "score": score
        }

        st.session_state.last_rollover = today.isoformat()

def draw_face(score, size=220):
    img = Image.new("RGB", (size,size), "white")
    d = ImageDraw.Draw(img)

    face = "#ffb3b3" if score < 50 else "#fff2b2" if score < 80 else "#b7f5c2"
    m = size*0.08
    d.ellipse([m,m,size-m,size-m], fill=face, outline="black")

    er = int(size*0.04)
    d.ellipse([size*0.35-er,size*0.38-er,size*0.35+er,size*0.38+er], fill="black")
    d.ellipse([size*0.65-er,size*0.38-er,size*0.65+er,size*0.38+er], fill="black")

    if score < 50:
        d.arc([size*0.3,size*0.58,size*0.7,size*0.82],180,360,fill="black",width=4)
    elif score < 80:
        d.line([size*0.38,size*0.65,size*0.62,size*0.65],fill="black",width=4)
    else:
        d.arc([size*0.3,size*0.5,size*0.7,size*0.7],0,180,fill="black",width=4)

    return img

def mark_taken(med, t):
    st.session_state.history.append({
        "med": med,
        "dose": t,
        "date": today_str(),
        "time": now_server()
    })
    st.experimental_rerun()

def undo(med, t):
    for i in range(len(st.session_state.history)-1,-1,-1):
        h = st.session_state.history[i]
        if h["med"] == med and h["dose"] == t and h["date"] == today_str():
            st.session_state.history.pop(i)
            break
    st.experimental_rerun()

# -------------------------
# ROLLOVER DAILY
# -------------------------
rollover_if_needed()

# -------------------------
# LOCAL TIME (white)
# -------------------------
st.markdown("""
<div style='color:white; font-size:14px;'>
Current time: <span id='ct'>--:--:--</span>
</div>
<script>
function upd(){
  let n=new Date();
  let h=String(n.getHours()).padStart(2,'0');
  let m=String(n.getMinutes()).padStart(2,'0');
  let s=String(n.getSeconds()).padStart(2,'0');
  document.getElementById('ct').innerHTML=h+":"+m+":"+s;
}
setInterval(upd,1000); upd();
</script>
""", unsafe_allow_html=True)

# hide the circled box completely
st.markdown("<style>#client_time_input{display:none !important;}</style>", unsafe_allow_html=True)

# -------------------------
# HEADER
# -------------------------
st.markdown("<h1 style='text-align:center;'>MedTimer</h1>", unsafe_allow_html=True)

# =========================
# SECTION 1 – TODAY’S DOSES
# =========================
st.header("Today’s Doses")

scheduled = 0
taken = 0

for med,info in st.session_state.meds.items():
    for t in info["doses"]:
        scheduled += 1
        is_taken = any(h["med"]==med and h["dose"]==t and h["date"]==today_str()
                       for h in st.session_state.history)

        bg = "#b7f5c2" if is_taken else "#fff5b0"
        status = "Taken" if is_taken else ("Upcoming" if now_server()<=t else "Missed")

        st.markdown(
            f"""
            <div style='background:{bg};
                        padding:15px;
                        border-radius:10px;
                        margin-bottom:10px;'>
              <b style='color:black;'>{med} — {t}</b><br>
              <i style='color:black;'>{info['note']}</i><br>
              <span style='color:black;'>{status}</span>
            </div>
            """,
            unsafe_allow_html=True
        )

        c1,c2 = st.columns([1,1])
        with c1:
            if not is_taken and st.button(f"Take {med}-{t}", key=f"take_{med}_{t}"):
                mark_taken(med, t)
        with c2:
            if is_taken and st.button("Undo", key=f"undo_{med}_{t}"):
                undo(med, t)

        if is_taken:
            taken += 1

score = int((taken/scheduled)*100) if scheduled>0 else 0

st.subheader("Daily Summary")
st.progress(score/100 if scheduled>0 else 0)
st.write(f"**Score:** {score}%")
st.write(f"**Scheduled:** {scheduled}")
st.write(f"**Taken:** {taken}")

st.image(draw_face(score))

# =========================
# SECTION 2 – ADD / EDIT
# =========================
st.header("Add / Edit Medicines")

mode = st.radio("Mode", ["Add", "Edit"])

if mode == "Add":
    name = st.text_input("Medicine name")
    note = st.text_input("Note")
    freq = st.number_input("How many times per day?", min_value=1, max_value=10, value=1)

    st.write("Enter dose times:")
    new_times = []
    for i in range(freq):
        tm = st.time_input(f"Dose {i+1}", value=datetime.strptime("08:00","%H:%M").time())
        new_times.append(tm.strftime("%H:%M"))

    st.write("Repeat on days:")
    day_cols = st.columns(7)
    selected_days = []
    for i,d in enumerate(WEEKDAYS):
        if day_cols[i].checkbox(d, True):
            selected_days.append(d)

    if st.button("Add"):
        if name.strip()=="":
            st.warning("Enter a name.")
        else:
            st.session_state.meds[name] = {
                "doses": new_times,
                "note": note,
                "days": selected_days
            }
            st.success("Added.")
            st.experimental_rerun()

else:
    meds = list(st.session_state.meds.keys())
    if meds:
        target = st.selectbox("Select medicine", meds)
        info = st.session_state.meds[target]

        new_name = st.text_input("Name", target)
        new_note = st.text_input("Note", info["note"])
        freq = st.number_input("Times per day", min_value=1, max_value=10, value=len(info["doses"]))

        st.write("Edit dose times:")
        new_times = []
        for i in range(freq):
            default = info["doses"][i] if i < len(info["doses"]) else "08:00"
            tm = st.time_input(f"Dose {i+1}", value=datetime.strptime(default,"%H:%M").time())
            new_times.append(tm.strftime("%H:%M"))

        st.write("Repeat on days:")
        cols = st.columns(7)
        new_days = []
        for i,d in enumerate(WEEKDAYS):
            if cols[i].checkbox(d, d in info["days"]):
                new_days.append(d)

        if st.button("Save changes"):
            st.session_state.meds.pop(target)
            st.session_state.meds[new_name] = {
                "doses": new_times,
                "note": new_note,
                "days": new_days
            }
            st.success("Saved.")
            st.experimental_rerun()

# =========================
# SECTION 3 – ALL MEDS
# =========================
st.header("All Medications")

if st.session_state.meds:
    for m,info in st.session_state.meds.items():
        st.write(f"### {m}")
        st.write(f"Times: {', '.join(info['doses'])}")
        st.write(f"Note: {info['note']}")
        st.write(f"Days: {', '.join(info['days'])}")
        st.write("---")
else:
    st.info("No medicines yet")
