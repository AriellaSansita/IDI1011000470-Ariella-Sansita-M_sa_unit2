import streamlit as st
import datetime as dt
from datetime import datetime
from io import BytesIO
import math, wave, struct

st.set_page_config("MedTimer", "💊", layout="wide")

if "meds" not in st.session_state or not isinstance(st.session_state.meds, dict):
    st.session_state.meds = {}

if "history" not in st.session_state:
    st.session_state.history = []

if "streak" not in st.session_state:
    st.session_state.streak = 0

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

def today():
    return dt.date.today()

def now():
    return dt.datetime.now()

def time_to_str(t: dt.time) -> str:
    return t.strftime("%H:%M")

def parse_time_str(s: str) -> dt.time:
    hh, mm = map(int, s.split(":"))
    return dt.time(hh, mm)

def default_time_for_index(i: int) -> dt.time:
    hour = max(0, min(23, 8 + 4 * i))
    return dt.time(hour, 0)

def get_history_entry(name, dose_time, date):
    for h in st.session_state.history:
        if h["date"] == date and h["name"] == name and h["dose_time"] == dose_time:
            return h
    return None

def ensure_history_entry(name, dose_time, date):
    if get_history_entry(name, dose_time, date) is None:
        st.session_state.history.append({
            "date": date,
            "name": name,
            "dose_time": dose_time,
            "taken": False
        })

def set_taken(name, dose_time, date, val: bool):
    h = get_history_entry(name, dose_time, date)
    if h is None:
        st.session_state.history.append({
            "date": date,
            "name": name,
            "dose_time": dose_time,
            "taken": bool(val)
        })
    else:
        h["taken"] = bool(val)

def get_taken(name, dose_time, date):
    h = get_history_entry(name, dose_time, date)
    return bool(h["taken"]) if h else False

def status_for_dose(dose_time_str, taken, now_dt):
    if taken:
        return "taken"
    med_time = parse_time_str(dose_time_str)
    current_time = now_dt.time().replace(second=0, microsecond=0)
    if med_time > current_time:
        return "upcoming"
    else:
        return "missed"

def adherence_score(history, days=7):
    if not history:
        return 0.0
    cutoff = today() - dt.timedelta(days=days - 1)
    recent = [h for h in history if h["date"] >= cutoff]
    if not recent:
        return 0.0
    total = len(recent)
    taken = sum(1 for h in recent if h["taken"])
    return round(100.0 * taken / max(total, 1), 1)

def update_streak(history):
    s = 0
    day = today()
    while True:
        entries = [h for h in history if h["date"] == day]
        if not entries:
            break
        total = len(entries)
        taken = sum(1 for h in entries if h["taken"])
        if total > 0 and taken == total:
            s += 1
            day -= dt.timedelta(days=1)
        else:
            break
    return s

def draw_turtle_image(size=220):
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
        d = ImageDraw.Draw(img)
        cx, cy = size // 2, size // 2
        d.ellipse([cx-70, cy-50, cx+70, cy+80], fill="#6aa84f", outline="#2e7d32")
        d.ellipse([cx-40, cy-20, cx+40, cy+40], fill="#a3d18a")
        d.ellipse([cx+60, cy-10, cx+95, cy+25], fill="#6aa84f", outline="#2e7d32")
        d.ellipse([cx-80, cy+40, cx-60, cy+70], fill="#6aa84f")
        d.ellipse([cx+40, cy+60, cx+60, cy+90], fill="#6aa84f")
        d.ellipse([cx+80, cy+2, cx+86, cy+8], fill="black")
        return img
    except Exception:
        return None

def generate_beep_wav(seconds=0.6, freq=880):
    framerate = 44100
    nframes = int(seconds * framerate)
    buf = BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(framerate)
        for i in range(nframes):
            val = int(32767.0 * math.sin(2 * math.pi * freq * (i / framerate)))
            w.writeframes(struct.pack('<h', val))
    buf.seek(0)
    return buf

def build_report_pdf_bytes(history, meds_today):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        w, h = A4
        y = h - 60
        c.setFont("Helvetica-Bold", 16)
        c.drawString(60, y, "MedTimer – Weekly Adherence Report")
        y -= 28
        c.setFont("Helvetica", 10)
        c.drawString(60, y, datetime.now().strftime("Generated: %Y-%m-%d %H:%M"))
        y -= 18
        score = adherence_score(history, 7)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(60, y, f"7-Day Adherence: {score}%")
        y -= 18
        cutoff = today() - dt.timedelta(days=6)
        for i in range(7):
            d = cutoff + dt.timedelta(days=i)
            entries = [h for h in history if h["date"] == d]
            total = len(entries)
            taken = sum(1 for h in entries if h["taken"])
            c.setFont("Helvetica", 10)
            c.drawString(60, y, f"{d}: {taken}/{total} doses taken")
            y -= 14
            if y < 80:
                c.showPage()
                y = h - 60
        y -= 6
        c.setFont("Helvetica-Bold", 12)
        c.drawString(60, y, "Today's Scheduled Doses:")
        y -= 16
        for m in meds_today:
            c.setFont("Helvetica", 10)
            c.drawString(60, y, f"- {m['name']} @ {m['dose_time']} | taken: {m['taken']}")
            y -= 12
            if y < 80:
                c.showPage()
                y = h - 60
        c.save()
        buf.seek(0)
        return buf.getvalue()
    except Exception:
        return b""

st.title("MedTimer")

col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    st.markdown("### Today")
with col2:
    st.metric("7-Day Adherence", f"{adherence_score(st.session_state.history,7)}%")
with col3:
    st.metric("Perfect Streak", f"{update_streak(st.session_state.history)} days")

st.header("Today's Checklist")

today_date = today()
now_dt = now()
weekday = WEEKDAYS[today_date.weekday()]
scheduled_today = []

if st.session_state.meds:
    for name, info in st.session_state.meds.items():
        if weekday not in info.get("days", WEEKDAYS):
            continue
        st.write(f"**{name}** — {info.get('note') or 'No note'}")
        doses_sorted = sorted(info.get("doses", []), key=lambda s: parse_time_str(s))
        for dose in doses_sorted:
            ensure_history_entry(name, dose, today_date)
            taken = get_taken(name, dose, today_date)
            status = status_for_dose(dose, taken, now_dt)
            c1, c2, c3 = st.columns([2.2, 1.2, 1.2])
            with c1:
                st.write(f"⏰ {dose}")
            with c2:
                if status == "taken":
                    st.success("Taken")
                elif status == "upcoming":
                    st.warning("Upcoming")
                else:
                    st.error("Missed")
            with c3:
                btn_key = f"btn_{name}_{dose}_{today_date}_{'taken' if taken else 'untaken'}"
                if taken:
                    if st.button("Undo", key=btn_key):
                        set_taken(name, dose, today_date, False)
                        st.rerun()
                else:
                    if st.button("Mark taken", key=btn_key):
                        set_taken(name, dose, today_date, True)
                        st.rerun()
            scheduled_today.append({
                "name": name,
                "dose_time": dose,
                "taken": get_taken(name, dose, today_date)
            })
        st.divider()
else:
    st.info("No medicines yet. Use Add/Edit section.")
