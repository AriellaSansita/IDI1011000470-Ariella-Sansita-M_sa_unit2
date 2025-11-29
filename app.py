# app.py
import streamlit as st
from datetime import datetime, date, timedelta
import matplotlib.pyplot as plt
import pandas as pd
import io
import random
import json

# -----------------------
# PAGE CONFIG
# -----------------------
st.set_page_config(
    page_title="MedTimer — Premium",
    layout="centered",
    initial_sidebar_state="auto",
)

# -----------------------
# CONSTANTS / UX
# -----------------------
PRIMARY = "#2b7a78"     # calm teal
SECOND = "#88d8b0"      # light green
WARN = "#ffd166"        # yellow
DANGER = "#ff6b6b"      # red
BG = "#f7fff7"

LARGE_HEADER = "<h1 style='text-align:center; font-size:34px; margin-bottom:4px;'>MedTimer</h1>"
SUBHEADER_STYLE = "<h3 style='font-size:20px; margin-bottom:4px;'>{}</h3>"

MOTIVATIONAL = [
    "Small steps, big changes — you're doing great!",
    "Taking meds = taking care of your future self. Well done!",
    "Consistency builds health. Keep it up!",
    "One dose at a time. You've got this.",
]

TIPS = [
    "Keep a glass of water near your meds to make taking them easier.",
    "Set a phone alarm 10 minutes before scheduled time.",
    "Pair medication with a daily routine (e.g., breakfast) to remember it.",
    "Store pills in an easy-to-reach, consistent place."
]

# -----------------------
# SESSION STATE INIT
# -----------------------
if "page" not in st.session_state:
    st.session_state.page = "today"

if "meds" not in st.session_state:
    # meds: dict of med_name -> {"time":"HH:MM", "note": "", "taken_today": False}
    st.session_state.meds = {
        "Aspirin": {"time": "12:00", "note": "After lunch", "taken_today": False},
        "Vitamin D": {"time": "18:00", "note": "With dinner", "taken_today": False},
        "Iron": {"time": "08:00", "note": "Before breakfast", "taken_today": False},
    }

# history: list of {"med": name, "date": "YYYY-MM-DD", "time": "HH:MM"}
if "history" not in st.session_state:
    st.session_state.history = []

# allow manual daily reset if needed
if "last_reset_date" not in st.session_state:
    st.session_state.last_reset_date = date.today().isoformat()

# -----------------------
# HELPER FUNCTIONS
# -----------------------
def go(page_name: str):
    st.session_state.page = page_name

def now_time_str():
    return datetime.now().strftime("%H:%M")

def today_str():
    return date.today().isoformat()

def mark_taken(med_name: str):
    """Mark a medicine as taken for today and append to history"""
    st.session_state.meds[med_name]["taken_today"] = True
    entry = {"med": med_name, "date": today_str(), "time": now_time_str()}
    st.session_state.history.append(entry)

def unmark_taken(med_name: str):
    """Unmark for today (also remove today's last entry for that med if present)"""
    st.session_state.meds[med_name]["taken_today"] = False
    # remove history entry for today for this med (if any) — remove last occurrence
    for i in range(len(st.session_state.history)-1, -1, -1):
        e = st.session_state.history[i]
        if e["med"] == med_name and e["date"] == today_str():
            st.session_state.history.pop(i)
            break

def add_med(name: str, time_obj, note=""):
    t = time_obj.strftime("%H:%M")
    st.session_state.meds[name] = {"time": t, "note": note, "taken_today": False}

def edit_med(old_name: str, new_name: str, new_time_obj, new_note: str):
    t = new_time_obj.strftime("%H:%M")
    info = st.session_state.meds.pop(old_name)
    info["time"] = t
    info["note"] = new_note
    info["taken_today"] = False
    st.session_state.meds[new_name] = info
    # update history med names for past entries if name changed?
    for entry in st.session_state.history:
        if entry["med"] == old_name:
            entry["med"] = new_name

def delete_med(name: str):
    if name in st.session_state.meds:
        st.session_state.meds.pop(name)
    # remove history entries for that med
    st.session_state.history = [e for e in st.session_state.history if e["med"] != name]

def reset_daily_if_needed():
    """Resets 'taken_today' automatically at midnight (first run of the day)."""
    last = datetime.fromisoformat(st.session_state.last_reset_date).date()
    if last < date.today():
        for med in st.session_state.meds:
            st.session_state.meds[med]["taken_today"] = False
        st.session_state.last_reset_date = date.today().isoformat()

def week_start_date(target_date: date):
    """Return Monday of the week containing target_date."""
    return target_date - timedelta(days=target_date.weekday())

def calculate_weekly_adherence():
    """
    Calculates scheduled doses and taken doses for the current week (Mon->today)
    Uses 'history' for taken records.
    """
    today = date.today()
    start = week_start_date(today)
    days = (today - start).days + 1  # inclusive of today
    # scheduled instances = number of meds * days
    total_scheduled = len(st.session_state.meds) * days
    # count taken entries in history between start and today inclusive
    taken_count = 0
    for e in st.session_state.history:
        ed = datetime.fromisoformat(e["date"]).date()
        if start <= ed <= today:
            # count each history entry (duplicates possible if user marked multiple times)
            taken_count += 1
    # avoid division by zero
    score = int((taken_count / total_scheduled) * 100) if total_scheduled > 0 else 0
    return {"start": start, "today": today, "days": days, "scheduled": total_scheduled, "taken": taken_count, "score": score}

def draw_smiley(score):
    """Return a matplotlib figure of a smiley/neutral/sad face or trophy based on score."""
    fig, ax = plt.subplots(figsize=(3,3))
    ax.set_xlim(0,10)
    ax.set_ylim(0,10)
    ax.axis('off')
    # Trophy if score >= 90
    if score >= 90:
        # simple trophy
        # base
        ax.add_patch(plt.Rectangle((3.2,0.6), 3.6, 0.6, fill=True, color="#ffd700", ec="black"))
        # cup
        ax.add_patch(plt.Rectangle((2.7,2), 5.6, 3.5, fill=True, color="#ffd700", ec="black"))
        # stem
        ax.add_patch(plt.Rectangle((4.4,1.2), 1.2, 0.8, fill=True, color="#ffd700", ec="black"))
        # handles
        ax.plot([2.7,1.8],[4.7,6.0], lw=4, color="#ffd700")
        ax.plot([8.3,9.2],[4.7,6.0], lw=4, color="#ffd700")
        ax.text(5,5.6, "Great!", ha="center", va="center", fontsize=14, weight="bold")
    else:
        # face circle
        face_color = "#b7f5c2" if score >= 80 else ("#fff2b2" if score >= 50 else "#ffb3b3")
        ax.add_patch(plt.Circle((5,5), 4, color=face_color, ec="black", lw=1.5))
        # eyes
        ax.add_patch(plt.Circle((3.4,6.3), 0.4, color="black"))
        ax.add_patch(plt.Circle((6.6,6.3), 0.4, color="black"))
        # mouth
        if score >= 80:
            x = [3.2,4.3,6.7,7.8]
            y = [4.1,3.5,3.5,4.1]
            ax.plot(x,y, lw=3, solid_capstyle="round")
        elif score >= 50:
            x = [3.2,5,7.0]
            y = [4.6,4.1,4.6]
            ax.plot(x,y, lw=3, solid_capstyle="round")
        else:
            x = [3.2,5,7.0]
            y = [6.2,6.6,6.2]
            ax.plot(x,y, lw=3, solid_capstyle="round")
        ax.text(5,1.0, f"Weekly adherence: {score}%", ha="center", va="center", fontsize=12)
    fig.tight_layout()
    return fig

def export_weekly_csv():
    """Create a CSV in-memory for the weekly history and meds."""
    df = pd.DataFrame(st.session_state.history)
    if df.empty:
        df = pd.DataFrame(columns=["med","date","time"])
    csv = df.to_csv(index=False)
    return csv

# -----------------------
# AUTO-RESET CHECK
# -----------------------
reset_daily_if_needed()

# -----------------------
# HEADER + NAV
# -----------------------
st.markdown(LARGE_HEADER, unsafe_allow_html=True)
st.markdown("<div style='text-align:center; color: #4a4a4a; margin-bottom:8px;'>A warm, senior-friendly daily medicine companion</div>", unsafe_allow_html=True)
st.markdown("---")

cols = st.columns([1,1,1])
with cols[0]:
    if st.button("Today", key="nav_today"): go("today")
with cols[1]:
    if st.button("All Meds", key="nav_all"): go("all_meds")
with cols[2]:
    if st.button("Add / Edit", key="nav_add"): go("add_med")

st.markdown("")

# -----------------------
# PAGE: TODAY
# -----------------------
if st.session_state.page == "today":
    st.markdown(SUBHEADER_STYLE.format("Today's Medication Checklist"), unsafe_allow_html=True)
    st.write("")  # spacing

    # large time indicator
    st.markdown(f"<div style='font-size:14px; color:#666'>Current time: <b>{now_time_str()}</b></div>", unsafe_allow_html=True)
    st.write("")

    # left: checklist; right: summary + graphic
    left, right = st.columns([2,1])

    with left:
        if len(st.session_state.meds) == 0:
            st.info("No medicines added yet. Click 'Add / Edit' to add medicines.")
        else:
            for idx, (med, info) in enumerate(st.session_state.meds.items()):
                due_time = info["time"]
                taken = info["taken_today"]
                note = info.get("note", "")

                # status logic: compare HH:MM strings is OK for this format
                now = now_time_str()
                if taken:
                    status = "✅ Taken"
                    color = "#b7f5c2"
                else:
                    if now > due_time:
                        status = "❌ Missed"
                        color = "#ffb3b3"
                    else:
                        status = "⏳ Upcoming"
                        color = "#bfe4ff"

                st.markdown(
                    f"""
                    <div style='padding:12px; background:{color}; border-radius:12px; margin-bottom:10px;'>
                        <div style='display:flex; justify-content:space-between; align-items:center;'>
                            <div>
                                <b style='font-size:18px'>{med}</b><br>
                                <span style='color:#444'>{due_time} · {note}</span><br>
                                <i style='color:#333'>{status}</i>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                # action buttons for each med
                btn_col1, btn_col2, btn_col3 = st.columns([1,1,1])
                with btn_col1:
                    if not taken:
                        if st.button(f"Mark Taken: {med}", key=f"take_{idx}"):
                            mark_taken(med)
                            st.experimental_rerun()
                    else:
                        if st.button(f"Undo: {med}", key=f"undo_{idx}"):
                            unmark_taken(med)
                            st.experimental_rerun()
                with btn_col2:
                    if st.button(f"Edit: {med}", key=f"edit_{idx}"):
                        # prefill edit page by storing temp vars
                        st.session_state.edit_target = med
                        go("add_med")
                with btn_col3:
                    if st.button(f"Delete: {med}", key=f"del_{idx}"):
                        delete_med(med)
                        st.experimental_rerun()

    with right:
        st.markdown(SUBHEADER_STYLE.format("Weekly Summary"), unsafe_allow_html=True)
        summary = calculate_weekly_adherence()
        # big progress
        st.progress(summary["score"] / 100)
        st.markdown(f"**Score:** {summary['score']}%")
        st.markdown(f"**Scheduled:** {summary['scheduled']} doses")
        st.markdown(f"**Taken (week):** {summary['taken']} doses")
        st.write("")  # spacing

        # motivational / tips
        st.markdown("**Motivation**")
        st.info(random.choice(MOTIVATIONAL))

        st.markdown("**Quick Tip**")
        st.success(random.choice(TIPS))

        # draw figure
        fig = draw_smiley(summary["score"])
        st.pyplot(fig)

        # Download weekly CSV
        csv = export_weekly_csv()
        st.download_button("Download weekly history (CSV)", data=csv, file_name="med_history_week.csv", mime="text/csv")

    st.markdown("---")
    # small utilities
    util_col1, util_col2 = st.columns(2)
    with util_col1:
        if st.button("Reset all 'taken today' flags (use only if needed)"):
            for m in st.session_state.meds:
                st.session_state.meds[m]["taken_today"] = False
            st.success("All taken flags reset.")
            st.experimental_rerun()
    with util_col2:
        if st.button("Clear history (WARNING)"):
            st.session_state.history = []
            st.success("History cleared.")
            st.experimental_rerun()

# -----------------------
# PAGE: ALL MEDS
# -----------------------
elif st.session_state.page == "all_meds":
    st.markdown(SUBHEADER_STYLE.format("All Medications"), unsafe_allow_html=True)
    if len(st.session_state.meds) == 0:
        st.info("No meds. Go to Add / Edit to create medications.")
    else:
        df_list = []
        for med, info in st.session_state.meds.items():
            df_list.append({"Name": med, "Time": info["time"], "Note": info.get("note",""), "Taken Today": info["taken_today"]})
        df = pd.DataFrame(df_list)
        st.dataframe(df.style.set_properties(**{'font-size':'14px'}), height=300)

    st.markdown("---")
    st.markdown("### History preview (most recent 20 entries)")
    if len(st.session_state.history) == 0:
        st.write("No history recorded yet. Mark medicines as taken to build history.")
    else:
        recent = pd.DataFrame(st.session_state.history[-20:][::-1])
        st.table(recent)

# -----------------------
# PAGE: ADD / EDIT MEDS
# -----------------------
elif st.session_state.page == "add_med":
    st.markdown(SUBHEADER_STYLE.format("Add or Edit a Medication"), unsafe_allow_html=True)

    # If editing, prefill fields
    edit_target = st.session_state.get("edit_target", None)
    if edit_target and edit_target in st.session_state.meds:
        pre = st.session_state.meds[edit_target]
        default_name = edit_target
        default_time = datetime.strptime(pre["time"], "%H:%M").time()
        default_note = pre.get("note", "")
    else:
        default_name = ""
        default_time = datetime.strptime("08:00", "%H:%M").time()
        default_note = ""

    with st.form("add_edit_form"):
        name = st.text_input("Medication name", value=default_name)
        t = st.time_input("Time", value=default_time)
        note = st.text_input("Note (optional)", value=default_note)
        submitted = st.form_submit_button("Save")

        if submitted:
            if name.strip() == "":
                st.warning("Please enter a valid medication name.")
            else:
                if edit_target and edit_target in st.session_state.meds:
                    # perform edit
                    edit_med(edit_target, name.strip(), t, note.strip())
                    st.success(f"Edited {edit_target} → {name.strip()}")
                    st.session_state.pop("edit_target", None)
                    go("today")
                    st.experimental_rerun()
                else:
                    if name.strip() in st.session_state.meds:
                        st.warning("A medication with this name already exists. Use Edit instead.")
                    else:
                        add_med(name.strip(), t, note.strip())
                        st.success(f"Added {name.strip()}")
                        go("today")
                        st.experimental_rerun()

    st.write("---")
    st.markdown("### Quick actions")
    # quick-delete via selectbox
    if len(st.session_state.meds) > 0:
        to_delete = st.selectbox("Delete a medicine", options=["(none)"] + list(st.session_state.meds.keys()))
        if to_delete and to_delete != "(none)":
            if st.button("Delete selected"):
                delete_med(to_delete)
                st.success(f"Deleted {to_delete}")
                st.experimental_rerun()

# -----------------------
# FOOTER / SMALL HELP
# -----------------------
st.markdown("---")
st.markdown("<div style='text-align:center; font-size:12px; color:#666'>MedTimer — friendly UI for medication adherence. Data stored in-session only. Deployable to Streamlit Cloud.</div>", unsafe_allow_html=True)
