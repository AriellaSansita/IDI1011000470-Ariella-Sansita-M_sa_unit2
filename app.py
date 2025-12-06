import streamlit as st
import datetime as dt
from datetime import datetime
from io import BytesIO
import math, wave, struct

# -------------------------
# Config & CSS
# -------------------------
st.set_page_config("MedTimer – Daily Medicine Companion", "💊", layout="wide")
st.markdown(
    """
    <style>
    :root{--g:#c8e6c9;--y:#fff9c4;--r:#ffcdd2}
    .pill{padding:6px 10px;border-radius:12px;font-weight:600;display:inline-block}
    .green{background:var(--g);color:#1b5e20}.yellow{background:var(--y);color:#5f5f00}.red{background:var(--r);color:#b71c1c}
    .muted{color:#666;font-size:0.9rem}
    .small{font-size:0.9rem}
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------
# Session state init
# -------------------------
if "meds" not in st.session_state or not isinstance(st.session_state.meds, dict):
    st.session_state.meds = {}
if "history" not in st.session_state:
    st.session_state.history = []  # {"date": date, "name": str, "dose_time": "HH:MM", "taken": bool}
if "streak" not in st.session_state:
    st.session_state.streak = 0

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# -------------------------
# Helpers
# -------------------------
def today(): return dt.date.today()
def now(): return dt.datetime.now()
def time_to_str(t: dt.time) -> str: return t.strftime("%H:%M")
def parse_time_str(s: str) -> dt.time:
    try:
        hh, mm = map(int, s.split(":")); return dt.time(hh, mm)
    except Exception:
        return dt.datetime.now().time().replace(second=0, microsecond=0)
def default_time_for_index(i: int) -> dt.time:
    hour = max(0, min(23, 8 + 4 * i)); return dt.time(hour, 0)

def get_history_entry(name, dose_time, date):
    for h in st.session_state.history:
        if h["date"] == date and h["name"] == name and h["dose_time"] == dose_time:
            return h
    return None

def ensure_history_entry(name, dose_time, date):
    if get_history_entry(name, dose_time, date) is None:
        st.session_state.history.append({"date": date, "name": name, "dose_time": dose_time, "taken": False})

def set_taken(name, dose_time, date, val: bool):
    h = get_history_entry(name, dose_time, date)
    if h is None:
        st.session_state.history.append({"date": date, "name": name, "dose_time": dose_time, "taken": bool(val)})
    else:
        h["taken"] = bool(val)

def get_taken(name, dose_time, date):
    h = get_history_entry(name, dose_time, date); return bool(h["taken"]) if h else False

def status_for_dose(dose_time_str, taken, now_dt):
    if taken: return "taken"
    med_time = parse_time_str(dose_time_str)
    med_dt = dt.datetime.combine(now_dt.date(), med_time)
    return "upcoming" if med_dt > now_dt else "missed"

def adherence_score(history, days=7):
    if not history: return 0.0
    cutoff = today() - dt.timedelta(days=days-1)
    recent = [h for h in history if h["date"] >= cutoff]
    if not recent: return 0.0
    total = len(recent); taken = sum(1 for h in recent if h["taken"])
    return round(100.0 * taken / max(total, 1), 1)

def update_streak(history):
    s = 0; day = today()
    while True:
        entries = [h for h in history if h["date"] == day]
        if not entries: break
        total = len(entries); taken = sum(1 for h in entries if h["taken"])
        if total > 0 and taken == total:
            s += 1; day -= dt.timedelta(days=1)
        else:
            break
    return s

def draw_turtle_image(size=220):
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
        d = ImageDraw.Draw(img)
        cx, cy = size//2, size//2
        d.ellipse([cx-70, cy-50, cx+70, cy+80], fill="#6aa84f", outline="#2e7d32")  # shell
        d.ellipse([cx-40, cy-20, cx+40, cy+40], fill="#a3d18a")  # pattern
        d.ellipse([cx+60, cy-10, cx+95, cy+25], fill="#6aa84f", outline="#2e7d32")  # head
        d.ellipse([cx-80, cy+40, cx-60, cy+70], fill="#6aa84f")  # leg left
        d.ellipse([cx+40, cy+60, cx+60, cy+90], fill="#6aa84f")  # leg right
        d.ellipse([cx+80, cy+2, cx+86, cy+8], fill="black")  # eye
        return img
    except Exception:
        return None

def generate_beep_wav(seconds=0.6, freq=880):
    framerate = 44100; nframes = int(seconds * framerate); buf = BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(framerate)
        for i in range(nframes):
            val = int(32767.0 * math.sin(2 * math.pi * freq * (i / framerate)))
            w.writeframes(struct.pack('<h', val))
    buf.seek(0); return buf

# Pure-Python minimal PDF generator (no external deps)
def build_report_pdf_bytes(history, meds_today):
    import io
    from datetime import datetime
    buf = io.BytesIO()
    # Very small, text-only single-page PDF — works without reportlab
    # Note: this is intentionally minimal but compatible with PDF viewers.
    content_lines = []
    content_lines.append("MedTimer – Weekly Adherence Report")
    content_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    content_lines.append("")
    score = adherence_score(history, 7)
    content_lines.append(f"7-Day Adherence: {score}%")
    content_lines.append("")
    start = today() - dt.timedelta(days=6)
    for i in range(7):
        d = start + dt.timedelta(days=i)
        entries = [h for h in history if h['date'] == d]
        taken = sum(1 for h in entries if h['taken'])
        total = len(entries)
        content_lines.append(f"{d}: {taken}/{total} doses taken")
    content_lines.append("")
    content_lines.append("Today's Scheduled Doses:")
    for m in meds_today:
        content_lines.append(f"- {m['name']} @ {m['dose_time']} | taken: {m['taken']}")

    # Build a very basic PDF by embedding text in a single content stream.
    # This is not fancy but is valid PDF structure for simple text.
    text = "\n".join(content_lines)
    # PDF objects
    objs = []
    objs.append(b"%PDF-1.4\n")
    # Font object
    objs.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
    # Pages
    objs.append(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n")
    # Page with content 4
    objs.append(b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n")
    stream = ("BT /F1 12 Tf 50 800 Td (" + text.replace("(", "\\(").replace(")", "\\)") + ") Tj ET\n").encode("latin-1", "replace")
    objs.append(b"4 0 obj << /Length " + str(len(stream)).encode() + b" >> stream\n" + stream + b"endstream endobj\n")
    # Font
    objs.append(b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n")
    # Combine and write xref (simple approach)
    startxref = 0
    out = io.BytesIO()
    offsets = []
    for o in objs:
        offsets.append(out.tell())
        out.write(o)
    # xref
    xref_pos = out.tell()
    out.write(b"xref\n0 " + str(len(objs)+1).encode() + b"\n0000000000 65535 f \n")
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(b"trailer << /Size " + str(len(objs)+1).encode() + b" /Root 1 0 R >>\nstartxref\n")
    out.write(str(xref_pos).encode() + b"\n%%EOF")
    buf.write(out.getvalue())
    buf.seek(0)
    return buf.getvalue()

# -------------------------
# Page header / quick metrics
# -------------------------
st.title("MedTimer — Single Page")
st.write("All features on one page (no collapsibles). Buttons toggle taken/undo. Turtle mascot included.")

col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    st.markdown("### Today's Medicines")
with col2:
    score = adherence_score(st.session_state.history, 7)
    st.metric("7-Day Adherence", f"{score}%")
with col3:
    st.metric("Perfect Streak", f"{update_streak(st.session_state.history)} days")

st.markdown("---")

# -------------------------
# SECTION: Today's Checklist
# -------------------------
st.subheader("Today's Checklist")
today_date = today(); now_dt = now(); weekday = WEEKDAYS[today_date.weekday()]
scheduled_today = []
if st.session_state.meds:
    for name, info in st.session_state.meds.items():
        if weekday not in info.get("days", WEEKDAYS):
            continue
        st.markdown(f"**{name}** — {info.get('note') or 'No note'}")
        # sort doses by time
        doses_sorted = sorted(info.get("doses", []), key=lambda s: parse_time_str(s))
        for dose in doses_sorted:
            ensure_history_entry(name, dose, today_date)
            taken = get_taken(name, dose, today_date)
            status = status_for_dose(dose, taken, now_dt)
            label = {"taken": "green", "upcoming": "yellow", "missed": "red"}[status]
            c1, c2, c3 = st.columns([2.2, 1.2, 1.2])
            with c1:
                st.write(f"⏰ {dose}")
            with c2:
                st.markdown(f"<span class='pill {label} small'>{status.capitalize()}</span>", unsafe_allow_html=True)
            with c3:
                # Toggle buttons
                btn_key = f"btn_{name}_{dose}_{today_date}"
                if get_taken(name, dose, today_date):
                    if st.button("Undo", key=btn_key):
                        set_taken(name, dose, today_date, False)
                        st.rerun()
                else:
                    if st.button("Mark taken", key=btn_key):
                        set_taken(name, dose, today_date, True)
                        st.rerun()
            scheduled_today.append({"name": name, "dose_time": dose, "taken": get_taken(name, dose, today_date)})
        st.divider()
else:
    st.info("No medicines scheduled. Use the Add section below to create one.")

# small adherence panel
col_a, col_b = st.columns([1, 2])
with col_a:
    today_taken = sum(1 for h in st.session_state.history if h["date"] == today_date and h["taken"])
    today_total = sum(1 for h in st.session_state.history if h["date"] == today_date)
    st.metric("Today's Doses", f"{today_taken}/{today_total}")
with col_b:
    if score >= 85:
        st.success("Fantastic adherence! Keep it up 💪")
    elif score >= 60:
        st.info("You're on track.")
    else:
        st.warning("Let's build momentum — small steps!")

if score >= 85:
    img = draw_turtle_image()
    if img:
        st.image(img, caption="Turtle Trophy")

# Beep if missed or imminent
imminent = False
for h in st.session_state.history:
    if h["date"] != today_date or h["taken"]:
        continue
    med_dt = dt.datetime.combine(today_date, parse_time_str(h["dose_time"]))
    if med_dt < now_dt or (med_dt - now_dt) <= dt.timedelta(minutes=5):
        imminent = True; break
if imminent:
    st.audio(generate_beep_wav(), format="audio/wav")

st.markdown("---")

# -------------------------
# SECTION: Add Medicine
# -------------------------
st.subheader("Add Medicine")
presets = ["Custom Add", "Paracetamol", "Aspirin", "Ibuprofen", "Amoxicillin", "Vitamin D", "Iron", "Zinc"]
preset_choice = st.selectbox("Choose medicine (or Custom Add)", presets, index=0)
if preset_choice == "Custom Add":
    name = st.text_input("Medicine name", key="add_name")
else:
    name = preset_choice
    st.markdown(f"<div class='muted'>Preset selected: <strong>{name}</strong></div>", unsafe_allow_html=True)
note = st.text_input("Note (optional)", key="add_note")
freq = st.number_input("Times per day", min_value=1, max_value=8, value=1, step=1, key="add_freq")
st.write("Dose times:")
new_times = []
for i in range(freq):
    t = st.time_input(f"Dose {i+1}", value=default_time_for_index(i), key=f"add_time_{i}")
    new_times.append(time_to_str(t))
st.write("Repeat on days:")
cols = st.columns(7); sel_days = []
for i, d in enumerate(WEEKDAYS):
    if cols[i].checkbox(d, value=True, key=f"add_day_{d}"): sel_days.append(d)
if st.button("Add medicine"):
    if not name or not name.strip():
        st.warning("Please enter a medicine name.")
    elif name in st.session_state.meds:
        st.warning("A medicine with this name already exists. Use Edit to modify.")
    else:
        st.session_state.meds[name] = {"doses": new_times, "note": note, "days": sel_days or WEEKDAYS}
        st.success(f"Added {name}.")
        st.rerun()

st.markdown("---")

# -------------------------
# SECTION: Edit / Delete
# -------------------------
st.subheader("Edit / Delete Medicines")
meds_list = list(st.session_state.meds.keys())
if not meds_list:
    st.info("No medicines to edit. Add some above.")
else:
    sel = st.selectbox("Select medicine", meds_list, key="edit_select")
    info = st.session_state.meds.get(sel, {"doses": ["08:00"], "note": "", "days": WEEKDAYS})
    new_name = st.text_input("Name", value=sel, key="edit_name")
    new_note = st.text_input("Note", value=info.get("note", ""), key="edit_note")
    freq = st.number_input("Times per day", min_value=1, max_value=8, value=max(1, len(info.get("doses", []))), step=1, key="edit_freq")
    st.write("Dose times:")
    new_times = []
    for i in range(freq):
        default = parse_time_str(info["doses"][i]) if i < len(info["doses"]) else default_time_for_index(i)
        t = st.time_input(f"Dose {i+1}", value=default, key=f"edit_time_{i}")
        new_times.append(time_to_str(t))
    st.write("Repeat on days:")
    cols = st.columns(7); new_days = []; existing = set(info.get("days", WEEKDAYS))
    for i, d in enumerate(WEEKDAYS):
        if cols[i].checkbox(d, value=(d in existing), key=f"edit_day_{d}"): new_days.append(d)
    c1, c2 = st.columns([1, 2])
    with c2:
        if st.button("Save changes"):
            if new_name != sel and new_name in st.session_state.meds:
                st.warning("Another medicine already has that name.")
            else:
                if new_name != sel:
                    for h in st.session_state.history:
                        if h["name"] == sel:
                            h["name"] = new_name
                st.session_state.meds.pop(sel, None)
                st.session_state.meds[new_name] = {"doses": new_times, "note": new_note, "days": new_days or WEEKDAYS}
                st.success("Saved.")
                st.rerun()
    with c1:
        if st.button("Delete medicine"):
            st.session_state.meds.pop(sel, None)
            st.warning("Deleted.")
            st.rerun()

st.markdown("---")

# -------------------------
# SECTION: Export PDF
# -------------------------
st.subheader("Export Weekly PDF")
sample_schedule = []
td = today(); wd = WEEKDAYS[td.weekday()]
for name, info in st.session_state.meds.items():
    if wd not in info.get("days", WEEKDAYS): continue
    for dose in info.get("doses", []):
        sample_schedule.append({"name": name, "dose_time": dose, "taken": get_taken(name, dose, td)})
pdf_bytes = build_report_pdf_bytes(st.session_state.history, sample_schedule)
if pdf_bytes:
    st.download_button("Download weekly adherence report (PDF)", pdf_bytes, file_name="MedTimer_Report.pdf", mime="application/pdf")
else:
    st.info("PDF generation failed. (Fallback should rarely happen.)")

st.markdown("---")

# -------------------------
# Footer: motivation + reset
# -------------------------
cols = st.columns([2, 1])
with cols[0]:
    st.markdown("#### Motivation of the Day")
    tips = [
        "Taking medicines on time is a vote for your future self.",
        "Small habits, big impact—consistency builds confidence.",
        "You’re not alone—set gentle reminders and celebrate wins.",
        "Celebrate every day you complete your doses."
    ]
    st.info(tips[dt.datetime.now().day % len(tips)])
with cols[1]:
    st.markdown("#### Data")
    if st.button("Reset all data"):
        st.session_state.meds = {}
        st.session_state.history = []
        st.session_state.streak = 0
        st.success("All data cleared.")
        st.rerun()
