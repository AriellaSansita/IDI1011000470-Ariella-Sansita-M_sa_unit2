import streamlit as st
import pandas as pd
import numpy as np
import datetime as dt
from datetime import datetime
from io import BytesIO
import os

# ------------------------------
# App Config
# ------------------------------
st.set_page_config(page_title="MedTimer – Daily Medicine Companion", page_icon="💊", layout="wide")

# Calm styling
st.markdown(
    """
    <style>
    :root { --primary: #2e7d32; --accent: #43a047; --warn: #e53935; --upcoming: #fdd835; }
    .big { font-size: 1.2rem; }
    .pill { padding: 0.2rem 0.6rem; border-radius: 16px; font-weight: 600; }
    .green { background: #c8e6c9; color: #1b5e20; }
    .yellow { background: #fff9c4; color: #5f5f00; }
    .red { background: #ffcdd2; color: #b71c1c; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------
# Session state init
# ------------------------------
if "meds" not in st.session_state or not isinstance(st.session_state.meds, dict):
    st.session_state.meds = {}  # {name: {"doses":[HH:MM], "note": str, "days":[Mon..Sun]}}
if "history" not in st.session_state:
    st.session_state.history = []  # list of {date, name, dose_time, taken}
if "streak" not in st.session_state:
    st.session_state.streak = 0

# ------------------------------
# Constants + helpers
# ------------------------------
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

def weekday_str(d: dt.date) -> str:
    return ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][d.weekday()]

def safe_rerun(*keys_to_clear):
    """Clear widget keys to avoid rerun loops, then rerun."""
    for k in keys_to_clear:
        try:
            del st.session_state[k]
        except KeyError:
            pass
    st.rerun()

def time_to_str(t: dt.time) -> str:
    return t.strftime("%H:%M")

def parse_time_str(s: str) -> dt.time:
    try:
        hh, mm = map(int, s.split(":"))
        return dt.time(hh, mm)
    except Exception:
        return dt.datetime.now().time().replace(second=0, microsecond=0)

def default_time_for_index(i: int) -> dt.time:
    """08:00, 12:00, 16:00, 20:00, ..."""
    base = 8 + 4 * i
    hour = max(0, min(23, base))
    return datetime.strptime(f"{hour:02d}:00", "%H:%M").time()

def status_for_dose(dose_time_str: str, taken: bool, now: dt.datetime) -> str:
    """Return 'taken', 'upcoming', or 'missed' for a single dose."""
    if taken:
        return "taken"
    med_time = parse_time_str(dose_time_str)
    med_dt = dt.datetime.combine(now.date(), med_time)
    return "upcoming" if med_dt > now else "missed"

def get_history_entry(name: str, dose_time: str, date: dt.date):
    for h in st.session_state.history:
        if h["date"] == date and h["name"] == name and h["dose_time"] == dose_time:
            return h
    return None

def ensure_history_entry(name: str, dose_time: str, date: dt.date):
    """Ensure a history row exists for today for this dose."""
    h = get_history_entry(name, dose_time, date)
    if h is None:
        st.session_state.history.append({
            "date": date,
            "name": name,
            "dose_time": dose_time,
            "taken": False
        })

def set_taken(name: str, dose_time: str, date: dt.date, value: bool):
    h = get_history_entry(name, dose_time, date)
    if h is None:
        st.session_state.history.append({
            "date": date, "name": name, "dose_time": dose_time, "taken": bool(value)
        })
    else:
        h["taken"] = bool(value)

def get_taken(name: str, dose_time: str, date: dt.date) -> bool:
    h = get_history_entry(name, dose_time, date)
    return bool(h["taken"]) if h else False

def adherence_score(history: list, days: int = 7) -> float:
    """% taken over last N days based on history entries present."""
    if not history:
        return 0.0
    cutoff = dt.date.today() - dt.timedelta(days=days - 1)
    recent = [h for h in history if h["date"] >= cutoff]
    if not recent:
        return 0.0
    total = len(recent)
    taken = sum(1 for h in recent if h["taken"])
    return round(100.0 * taken / max(total, 1), 1)

def update_streak(history: list) -> int:
    """Consecutive days with 100% adherence among recorded entries."""
    streak = 0
    day = dt.date.today()
    while True:
        day_entries = [h for h in history if h["date"] == day]
        if not day_entries:
            break
        total = len(day_entries)
        taken = sum(1 for h in day_entries if h["taken"])
        if total > 0 and taken == total:
            streak += 1
            day = day - dt.timedelta(days=1)
        else:
            break
    return streak

# ------------------------------
# Trophy (Pillow only, in-memory)
# ------------------------------
def draw_trophy_image() -> "PIL.Image.Image":
    """Generate trophy image using Pillow."""
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (400, 400), "white")
        d = ImageDraw.Draw(img)
        d.rectangle([120, 120, 280, 200], fill="#FFD700", outline="black")
        d.ellipse([80, 120, 140, 180], fill="#FFD700", outline="black")
        d.ellipse([260, 120, 320, 180], fill="#FFD700", outline="black")
        d.rectangle([185, 200, 215, 280], fill="#DAA520", outline="black")
        d.rectangle([140, 280, 260, 320], fill="#8B4513", outline="black")
        return img
    except Exception:
        return None

# ------------------------------
# PDF report (in-memory)
# ------------------------------
def build_report_pdf_bytes(history: list, meds_today: list) -> bytes:
    try:
        import fitz  # PyMuPDF
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)  # A4
        now = dt.datetime.now()
        y = 60
        def add_text(text, size=12):
            nonlocal y
            page.insert_text((60, y), text, fontsize=size)
            y += size + 8

        add_text("MedTimer – Weekly Adherence Report", 18)
        add_text(f"Generated: {now.strftime('%Y-%m-%d %H:%M')}")
        add_text("")

        score = adherence_score(history, days=7)
        add_text(f"7-Day Adherence Score: {score}%", 14)
        add_text("")

        cutoff = dt.date.today() - dt.timedelta(days=6)
        days = [cutoff + dt.timedelta(days=i) for i in range(7)]
        for dday in days:
            entries = [h for h in history if h["date"] == dday]
            total = len(entries)
            taken = sum(1 for h in entries if h["taken"])
            add_text(f"{dday}: {taken}/{total} doses taken")

        add_text("")
        add_text("Today's Scheduled Doses:", 14)
        for m in meds_today:
            add_text(f"- {m['name']} @ {m['dose_time']} | taken: {m['taken']}")
        buf = BytesIO()
        doc.save(buf)
        doc.close()
        buf.seek(0)
        return buf.getvalue()
    except Exception:
        return b""

# ------------------------------
# Header
# ------------------------------
col1, col2 = st.columns([2, 1])
with col1:
    st.title("MedTimer – Daily Medicine Companion")
    st.write("Track daily doses with a friendly, color-coded checklist and stay confident about adherence.")
with col2:
    st.metric("Today", dt.date.today().strftime("%a, %d %b %Y"))

# ------------------------------
# Add / Edit medicines (multi-dose & weekdays)
# ------------------------------
st.subheader("Manage Medicines")

mode = st.radio("Mode", ["Add", "Edit"], key="mode_radio")

if mode == "Add":
    name = st.text_input("Medicine name", key="add_name")
    note = st.text_input("Note (optional)", key="add_note")
    freq = st.number_input("How many times per day?", min_value=1, max_value=10, value=1, step=1, key="add_freq")

    st.write("Enter dose times:")
    new_times = []
    for i in range(freq):
        tm = st.time_input(f"Dose {i+1}", value=default_time_for_index(i), key=f"add_time_{i}")
        new_times.append(time_to_str(tm))

    st.write("Repeat on days:")
    day_cols = st.columns(7)
    selected_days = []
    for i, d in enumerate(WEEKDAYS):
        if day_cols[i].checkbox(d, value=True, key=f"add_day_{d}"):
            selected_days.append(d)

    if st.button("Add", key="add_btn"):
        if name.strip() == "":
            st.warning("Enter a name.")
        elif name in st.session_state.meds:
            st.warning("A medicine with this name already exists. Use a different name or Edit.")
        else:
            st.session_state.meds[name] = {"doses": new_times, "note": note, "days": selected_days}
            st.success("Added.")
            safe_rerun("add_btn")

else:
    meds = list(st.session_state.meds.keys())
    if not meds:
        st.info("No medicines yet. Switch to **Add** mode to create one.")
    else:
        target = st.selectbox("Select medicine", meds, key="edit_target")
        info = st.session_state.meds.get(target, {"doses": [], "note": "", "days": WEEKDAYS})

        new_name = st.text_input("Name", value=target, key="edit_name")
        new_note = st.text_input("Note (optional)", value=info.get("note", ""), key="edit_note")
        freq = st.number_input("Times per day", min_value=1, max_value=10, value=max(1, len(info.get("doses", []))), step=1, key="edit_freq")

        st.write("Edit dose times:")
        new_times = []
        for i in range(freq):
            default = info["doses"][i] if i < len(info["doses"]) else "08:00"
            tm = st.time_input(f"Dose {i+1}", value=parse_time_str(default), key=f"edit_time_{i}")
            new_times.append(time_to_str(tm))

        st.write("Repeat on days:")
        cols = st.columns(7)
        new_days = []
        existing_days = set(info.get("days", []))
        for i, d in enumerate(WEEKDAYS):
            if cols[i].checkbox(d, value=(d in existing_days), key=f"edit_day_{d}"):
                new_days.append(d)

        delete_col, save_col = st.columns([1, 2])
        with save_col:
            if st.button("Save changes", key="save_btn"):
                if new_name != target and new_name in st.session_state.meds:
                    st.warning("Another medicine already has that name. Choose a different name.")
                else:
                    # Update history if name changed
                    if new_name != target:
                        for h in st.session_state.history:
                            if h["name"] == target:
                                h["name"] = new_name
                    st.session_state.meds.pop(target, None)
                    st.session_state.meds[new_name] = {"doses": new_times, "note": new_note, "days": new_days}
                    st.success("Saved.")
                    safe_rerun("save_btn")
        with delete_col:
            if st.button("Delete medicine", key="del_btn"):
                st.session_state.meds.pop(target, None)
                st.warning("Deleted medicine.")
                safe_rerun("del_btn")

# ------------------------------
# Today's checklist (per-dose)
# ------------------------------
st.subheader("Today's Checklist")

today = dt.date.today()
now = dt.datetime.now()
today_weekday = weekday_str(today)

scheduled_today = []  # for PDF

if st.session_state.meds:
    # Ensure history rows exist for each scheduled dose today
    for name, info in st.session_state.meds.items():
        if today_weekday in info.get("days", []):
            for dose_time in info.get("doses", []):
                ensure_history_entry(name, dose_time, today)

    # Render rows
    for name, info in st.session_state.meds.items():
        if today_weekday not in info.get("days", []):
            continue

        st.markdown(f"**{name}** – {info.get('note','').strip() or 'No note'}")
        rows = []
        for dose_time in info.get("doses", []):
            taken_val = get_taken(name, dose_time, today)
            status = status_for_dose(dose_time, taken_val, now)
            label_class = {"taken": "green", "upcoming": "yellow", "missed": "red"}[status]

            c1, c2, c3, c4 = st.columns([2.5, 1.5, 2, 1.5])
            with c1:
                st.write(f"⏰ {dose_time}")
            with c2:
                st.markdown(f"<span class='pill {label_class}'>{status.capitalize()}</span>", unsafe_allow_html=True)
            with c3:
                # Checkbox mirrors history
                chk = st.checkbox("Taken", value=taken_val, key=f"taken_{name}_{dose_time}")
                if chk != taken_val:
                    set_taken(name, dose_time, today, chk)
            with c4:
                if status == "missed" and not taken_val:
                    st.error("Missed")
                elif status == "upcoming" and not taken_val:
                    st.warning("Upcoming")
                else:
                    st.success("Done")
            rows.append({"name": name, "dose_time": dose_time, "taken": get_taken(name, dose_time, today)})

        scheduled_today.extend(rows)
        st.divider()
else:
    st.info("No scheduled doses today. Add medicines above.")

# ------------------------------
# Adherence, streak, trophy, beep
# ------------------------------
score = adherence_score(st.session_state.history, days=7)
st.session_state.streak = update_streak(st.session_state.history)

st.progress(min(int(score), 100))
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("7-Day Adherence", f"{score}%")
with c2:
    today_taken = sum(1 for h in st.session_state.history if h["date"] == today and h["taken"])
    today_total = sum(1 for h in st.session_state.history if h["date"] == today)
    st.metric("Today's Doses", f"{today_taken}/{today_total}")
with c3:
    st.metric("Perfect Streak", f"{st.session_state.streak} days")

if score >= 85:
    st.success("Fantastic adherence! Keep it up 💪")
elif score >= 60:
    st.info("You're on track. A little more consistency and you'll be gold ✨")
else:
    st.warning("Let's build momentum—small steps today make a big difference.")

if score >= 85:
    img = draw_trophy_image()
    if img:
        st.image(img, caption="High Adherence Award")
    else:
        st.write("(Award graphic could not be generated in this environment.)")

# Beep for missed or imminent (within 5 minutes)
imminent = False
for h in st.session_state.history:
    if h["date"] != today or h["taken"]:
        continue
    med_dt = dt.datetime.combine(today, parse_time_str(h["dose_time"]))
    if med_dt < now or (med_dt - now) <= dt.timedelta(minutes=5):
        imminent = True
        break
if imminent:
    # Generate a short beep
    import wave, struct, math
    def generate_beep_wav(seconds: float = 0.7, freq: int = 880) -> BytesIO:
        framerate = 44100
        nframes = int(seconds * framerate)
        buf = BytesIO()
        with wave.open(buf, 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(framerate)
            for i in range(nframes):
                val = int(32767.0 * math.sin(2 * math.pi * freq * (i / framerate)))
                w.writeframes(struct.pack('<h', val))
        buf.seek(0)
        return buf
    st.audio(generate_beep_wav(), format="audio/wav")

# ------------------------------
# Downloads
# ------------------------------
st.subheader("Download & Export")

left, right = st.columns(2)
with left:
    # CSV of today's schedule
    if scheduled_today:
        df_today = pd.DataFrame(scheduled_today)
        csv_buf = df_today.to_csv(index=False).encode("utf-8")
        st.download_button("Download today's schedule (CSV)", csv_buf, file_name="meds_today.csv", mime="text/csv")
    else:
        st.caption("No items to download.")

with right:
    pdf_bytes = build_report_pdf_bytes(st.session_state.history, scheduled_today)
    if pdf_bytes:
        st.download_button("Download weekly adherence report (PDF)", pdf_bytes, file_name="MedTimer_Report.pdf", mime="application/pdf")
    else:
        st.caption("PDF report unavailable in this environment.")

# ------------------------------
# Gentle motivation
# ------------------------------
st.subheader("Motivation of the Day")
tips = [
    "Taking medicines on time is a vote for your future self.",
    "Small habits, big impact—consistency builds confidence.",
    "You’re not alone—set gentle reminders and celebrate wins."
]
