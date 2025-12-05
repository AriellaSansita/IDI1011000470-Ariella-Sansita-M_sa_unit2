

import streamlit as st
import pandas as pd
import numpy as np
import datetime as dt
from io import BytesIO
import os

# Optional libraries for extras
try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    Image = None

# ------------------------------
# App Config
# ------------------------------
st.set_page_config(page_title="MedTimer – Daily Medicine Companion", page_icon="💊", layout="wide")

# Simple style for calm colors and large fonts
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
# Session State Init
# ------------------------------
if "meds" not in st.session_state:
    st.session_state.meds = []  # list of dicts: {name, time (HH:MM), taken(bool)}
if "history" not in st.session_state:
    st.session_state.history = []  # adherence history entries per day
if "streak" not in st.session_state:
    st.session_state.streak = 0  # consecutive perfect adherence days

# ------------------------------
# Helpers
# ------------------------------
def time_to_str(t: dt.time) -> str:
    return t.strftime("%H:%M")

def parse_time_str(s: str) -> dt.time:
    try:
        hh, mm = map(int, s.split(":"))
        return dt.time(hh, mm)
    except Exception:
        return dt.datetime.now().time().replace(second=0, microsecond=0)

def status_for_med(med_time: dt.time, taken: bool, now: dt.datetime) -> str:
    """Return 'taken', 'upcoming', or 'missed'"""
    if taken:
        return "taken"
    med_dt = dt.datetime.combine(now.date(), med_time)
    if med_dt > now:
        return "upcoming"
    else:
        return "missed"

def adherence_score(history: list, days: int = 7) -> float:
    """Compute adherence over the last N days from history entries.
    History entries: {date, name, scheduled_time, taken}
    """
    if not history:
        return 0.0
    cutoff = dt.date.today() - dt.timedelta(days=days - 1)
    filtered = [h for h in history if h["date"] >= cutoff]
    if not filtered:
        return 0.0
    total = len(filtered)
    taken = sum(1 for h in filtered if h["taken"])
    return round(100.0 * taken / max(total, 1), 1)

def update_streak(history: list) -> int:
    """Compute consecutive days with 100% adherence (today, yesterday, ...)."""
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
# Turtle drawing with robust fallbacks
# ------------------------------
def draw_trophy_png(output_path: str = "turtle_award.png") -> str:
    """Try to create a trophy using turtle and save as PNG; if turtle/PS conversion fails, draw with Pillow.
    Returns path to PNG file.
    """
    try:
        import turtle
        screen = turtle.Screen()
        screen.setup(width=400, height=400)
        t = turtle.Turtle()
        t.hideturtle()
        t.speed(0)
        # Draw cup
        t.color("gold")
        t.pensize(5)
        t.up(); t.goto(-80, 50); t.down()
        t.begin_fill()
        for _ in range(2):
            t.forward(160); t.circle(40, 90); t.forward(160); t.circle(40, 90)
        t.end_fill()
        # Handles
        t.up(); t.goto(-120, 120); t.down()
        t.circle(40)
        t.up(); t.goto(120, 120); t.down()
        t.circle(40)
        # Stem and base
        t.up(); t.goto(0, 50); t.setheading(-90); t.down()
        t.begin_fill()
        t.forward(80)
        t.left(90); t.forward(40); t.left(90); t.forward(20); t.left(90); t.forward(80); t.left(90); t.forward(60)
        t.end_fill()
        # Export via PostScript
        canvas = screen.getcanvas()
        ps_path = output_path.replace(".png", ".ps")
        canvas.postscript(file=ps_path, colormode='color')
        turtle.bye()
        try:
            from PIL import Image
            img = Image.open(ps_path)
            img = img.convert("RGB")
            img.save(output_path, "PNG")
            try:
                os.remove(ps_path)
            except Exception:
                pass
            return output_path
        except Exception:
            pass
    except Exception:
        pass

    # Fallback: draw with Pillow (guaranteed)
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (400, 400), "white")
        d = ImageDraw.Draw(img)
        # Trophy cup
        d.rectangle([120, 120, 280, 200], fill="#FFD700", outline="black")
        d.ellipse([80, 120, 140, 180], fill="#FFD700", outline="black")
        d.ellipse([260, 120, 320, 180], fill="#FFD700", outline="black")
        # Stem
        d.rectangle([185, 200, 215, 280], fill="#DAA520", outline="black")
        # Base
        d.rectangle([140, 280, 260, 320], fill="#8B4513", outline="black")
        img.save(output_path, "PNG")
        return output_path
    except Exception:
        return ""

# ------------------------------
# Beep tone generation (optional)
# ------------------------------
def generate_beep_wav(seconds: float = 0.7, freq: int = 880) -> BytesIO:
    """Generate a simple sine beep WAV in memory."""
    import wave, struct, math
    framerate = 44100
    nframes = int(seconds * framerate)
    buf = BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(framerate)
        for i in range(nframes):
            val = int(32767.0 * math.sin(2 * math.pi * freq * (i / framerate)))
            w.writeframes(struct.pack('<h', val))
    buf.seek(0)
    return buf

# ------------------------------
# Report PDF
# ------------------------------
def build_report_pdf(history: list, meds_today: list, output_path: str = "MedTimer_Report.pdf") -> str:
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
        # Adherence summary
        score = adherence_score(history, days=7)
        add_text(f"7-Day Adherence Score: {score}%", 14)
        add_text("")
        # Per-day summary (last 7 days)
        cutoff = dt.date.today() - dt.timedelta(days=6)
        days = [cutoff + dt.timedelta(days=i) for i in range(7)]
        for dday in days:
            entries = [h for h in history if h["date"] == dday]
            total = len(entries)
            taken = sum(1 for h in entries if h["taken"])
            add_text(f"{dday}: {taken}/{total} doses taken")
        add_text("")
        # Today's checklist snapshot
        add_text("Today's Medicines:", 14)
        for med in meds_today:
            add_text(f"- {med['name']} @ {med['time']} | taken: {med['taken']}")
        doc.save(output_path)
        return output_path
    except Exception:
        return ""

# ------------------------------
# UI – Header
# ------------------------------
col1, col2 = st.columns([2, 1])
with col1:
    st.title("MedTimer – Daily Medicine Companion")
    st.write("A friendly, color-coded tracker to help you remember medicines and feel confident about adherence.")
with col2:
    st.metric("Today", dt.date.today().strftime("%a, %d %b %Y"))

# ------------------------------
# Add / Edit Medicines
# ------------------------------
st.subheader("Add / Edit Medicines")
with st.form("add_med_form", clear_on_submit=True):
    med_name = st.text_input("Medicine name", placeholder="e.g., Metformin")
    med_time = st.time_input("Schedule time", value=dt.datetime.now().time().replace(second=0, microsecond=0))
    submitted = st.form_submit_button("Add medicine")
    if submitted and med_name.strip():
        st.session_state.meds.append({"name": med_name.strip(), "time": time_to_str(med_time), "taken": False})
        st.success(f"Added: {med_name} at {time_to_str(med_time)}")

# Edit/Delete
if st.session_state.meds:
    st.write("**Your schedule (today):**")
    for idx, med in enumerate(st.session_state.meds):
        c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 1, 1])
        with c1:
            st.text_input("Name", value=med["name"], key=f"name_{idx}", on_change=lambda i=idx: st.session_state.meds.__setitem__(i, {**st.session_state.meds[i], "name": st.session_state.get(f"name_{i}", st.session_state.meds[i]["name"]) }))
        with c2:
            t_val = parse_time_str(med["time"])
            new_t = st.time_input("Time", key=f"time_{idx}", value=t_val)
            st.session_state.meds[idx]["time"] = time_to_str(new_t)
        with c3:
            taken = st.checkbox("Taken", value=med["taken"], key=f"taken_{idx}")
            st.session_state.meds[idx]["taken"] = taken
        with c4:
            if st.button("Save", key=f"save_{idx}"):
                st.success("Saved changes")
        with c5:
            if st.button("Delete", key=f"del_{idx}"):
                st.session_state.meds.pop(idx)
                st.warning("Deleted medicine")
                st.experimental_rerun()
else:
    st.info("No medicines yet. Add your first above.")

# ------------------------------
# Checklist & Status
# ------------------------------
st.subheader("Today's Checklist")
now = dt.datetime.now()

if st.session_state.meds:
    df = pd.DataFrame(st.session_state.meds)
    # Determine status
    statuses = []
    for row in st.session_state.meds:
        med_time = parse_time_str(row["time"])
        statuses.append(status_for_med(med_time, row["taken"], now))
    df["status"] = statuses

    # Color-coded display
    for i, row in df.iterrows():
        status = row["status"]
        label_class = {"taken": "green", "upcoming": "yellow", "missed": "red"}.get(status, "yellow")
        colA, colB, colC = st.columns([5, 2, 2])
        with colA:
            st.write(f"**{row['name']}** @ {row['time']}")
        with colB:
            st.markdown(f"<span class='pill {label_class}'>{status.capitalize()}</span>", unsafe_allow_html=True)
        with colC:
            if status == "missed":
                st.error("Missed – take action")
            elif status == "upcoming":
                st.warning("Upcoming")
            else:
                st.success("Done")

    # Log today's entries into history (idempotent for this run)
    # We ensure one record per med per day; update taken status live.
    today = dt.date.today()
    for m in st.session_state.meds:
        # find existing
        existing = [h for h in st.session_state.history if h["date"] == today and h["name"] == m["name"] and h["scheduled_time"] == m["time"]]
        if existing:
            for e in existing:
                e["taken"] = bool(m["taken"])  # update live
        else:
            st.session_state.history.append({
                "date": today,
                "name": m["name"],
                "scheduled_time": m["time"],
                "taken": bool(m["taken"])
            })

    # Weekly adherence and streak
    score = adherence_score(st.session_state.history, days=7)
    st.session_state.streak = update_streak(st.session_state.history)

    st.progress(min(int(score), 100))
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("7-Day Adherence", f"{score}%")
    with c2:
        st.metric("Today's Doses", f"{sum(1 for s in statuses if s == 'taken')}/{len(statuses)}")
    with c3:
        st.metric("Perfect Streak", f"{st.session_state.streak} days")

    # Motivational messages
    if score >= 85:
        st.success("Fantastic adherence! Keep it up 💪")
    elif score >= 60:
        st.info("You're on track. A little more consistency and you'll be gold ✨")
    else:
        st.warning("Let's build momentum—small steps today make a big difference.")

    # Award graphic via turtle (with Pillow fallback)
    if score >= 85:
        img_path = draw_trophy_png()
        if img_path and os.path.exists(img_path):
            st.image(img_path, caption="High Adherence Award", use_column_width=False)
        else:
            st.write("(Award graphic could not be generated in this environment.)")

    # Optional: Play a beep if there is a missed or imminent (within 5 minutes) dose
    imminent = False
    for m in st.session_state.meds:
        med_time = parse_time_str(m["time"])
        med_dt = dt.datetime.combine(today, med_time)
        if not m["taken"]:
            if med_dt < now:
                imminent = True  # missed
            elif (med_dt - now) <= dt.timedelta(minutes=5):
                imminent = True
    if imminent:
        tone = generate_beep_wav()
        st.audio(tone, format="audio/wav")

else:
    st.info("Add medicines to see your checklist.")

# ------------------------------
# Download & Export
# ------------------------------
st.subheader("Download & Export")
colx, coly = st.columns(2)

with colx:
    # CSV of today's schedule
    if st.session_state.meds:
        df = pd.DataFrame(st.session_state.meds)
        csv_buf = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download today's schedule (CSV)", csv_buf, file_name="meds_today.csv", mime="text/csv")
    else:
        st.caption("Add items to enable CSV download.")

with coly:
    # PDF weekly report
    pdf_path = build_report_pdf(st.session_state.history, st.session_state.meds)
    if pdf_path and os.path.exists(pdf_path):
        with open(pdf_path, "rb") as f:
            st.download_button("Download weekly adherence report (PDF)", f.read(), file_name="MedTimer_Report.pdf", mime="application/pdf")
    else:
        st.caption("PDF report unavailable in this environment.")

# ------------------------------
# Eco/Calm Tips (rotating)
# ------------------------------
st.subheader("Motivation of the Day")
tips = [
    "Taking medicines on time is a vote for your future self.",
    "Small habits, big impact—consistency builds confidence.",
    "You’re not alone—set gentle reminders and celebrate wins.",
    "Hydration helps—pair your dose with a glass of water.",
]
seed = int(dt.datetime.now().strftime("%Y%m%d"))
np.random.seed(seed)
st.info(np.random.choice(tips))
