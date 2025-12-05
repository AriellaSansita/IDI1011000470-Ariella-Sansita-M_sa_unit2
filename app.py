
import io, os, math, wave, turtle, matplotlib.pyplot as plt, pandas as pd, streamlit as st
from PIL import Image, ImageDraw
from datetime import datetime, date, time as dtime, timedelta
try:
    import fitz  # PyMuPDF
    HAS_PDF = True
except Exception:
    HAS_PDF = False

# ---- Config & constants ----
st.set_page_config(page_title="MedTimer", page_icon="💊", layout="centered")
WEEKDAYS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
MAX_DOSES_PER_DAY = 8
UPCOMING_MIN = 120
TROPHY_THRESHOLD = 80
STREAK_THRESHOLD = 80

# ---- State ----
def init():
    s = st.session_state
    if "page" not in s: s.page = "today"
    if "meds" not in s:
        s.meds = {
            "Aspirin":{"time":["12:00"],"note":"After lunch","days":WEEKDAYS.copy(),"freq":1},
            "Vitamin D":{"time":["18:00"],"note":"With dinner","days":["Mon","Wed","Fri"],"freq":1},
            "Iron":{"time":["08:00"],"note":"Before breakfast","days":["Mon","Tue","Wed","Thu","Fri"],"freq":1}
        }
    if "history" not in s: s.history = []  # [{med,date,time}]
    if "daily_scores" not in s: s.daily_scores = {}  # date-> {scheduled,taken,score}
    if "last_rollover_date" not in s: s.last_rollover_date = date.today().isoformat()
    if "badge_history" not in s: s.badge_history = {}
init()

# ---- Helpers ----
def today_str(): return date.today().isoformat()
def parse_time(hm): return datetime.strptime(hm,"%H:%M").time()
def is_taken(med, hm, d=None):
    d = d or today_str()
    return any(h["med"]==med and h["time"]==hm and h["date"]==d for h in st.session_state.history)
def scheduled_on_day(info, widx):
    return 0 if info["days"] and WEEKDAYS[widx] not in info["days"] else len(info["time"])
def normalize_times(ts):
    out=[]
    for hm in ts:
        try: out.append(datetime.strptime(str(hm).strip(),"%H:%M").strftime("%H:%M"))
        except: pass
    return sorted(list(dict.fromkeys(out)))
def default_days(days): return days if days else WEEKDAYS.copy()
def name_exists(name, exclude=None):
    name=name.strip(); return any(k==name and k!=exclude for k in st.session_state.meds)
def now_with_offset(offset_min, simulate_on, simulate_hm):
    if simulate_on and simulate_hm:
        base=datetime.utcnow(); parts=datetime.strptime(simulate_hm,"%H:%M")
        return datetime.combine(base.date(), dtime(parts.hour, parts.minute))
    return datetime.utcnow()+timedelta(minutes=offset_min)
def status_for(now_t, hm_t, taken, window_min):
    if taken: return "Taken","#b7f5c2"
    now_dt=datetime.combine(date.today(),now_t); sched_dt=datetime.combine(date.today(),hm_t)
    if now_dt<=sched_dt:
        return ("Upcoming","#fff7b0") if (sched_dt-now_dt)<=timedelta(minutes=window_min) else ("Scheduled","#e6f0ff")
    return "Missed","#ffb3b3"
def mark_taken(med,hm):
    st.session_state.history.append({"med":med,"date":today_str(),"time":hm}); st.rerun()
def unmark_taken(med,hm):
    hist=st.session_state.history
    for i in range(len(hist)-1,-1,-1):
        h=hist[i]
        if h["med"]==med and h["time"]==hm and h["date"]==today_str():
            hist.pop(i); break
    st.rerun()
def compute_today():
    sched=sum(scheduled_on_day(i,date.today().weekday()) for i in st.session_state.meds.values())
    taken=sum(1 for h in st.session_state.history if h["date"]==today_str())
    score=int((taken/sched)*100) if sched>0 else 0
    return sched,taken,score
def rollover():
    s=st.session_state; last=date.fromisoformat(s.last_rollover_date); today=date.today()
    if last<today:
        y=today-timedelta(days=1); ystr=y.isoformat()
        if ystr not in s.daily_scores:
            yidx=y.weekday()
            sched=sum(scheduled_on_day(info,yidx) for info in s.meds.values())
            taken=sum(1 for h in s.history if h["date"]==ystr)
            score=int((taken/sched)*100) if sched>0 else 0
            s.daily_scores[ystr]={"scheduled":sched,"taken":taken,"score":score}
            if score>=95: s.badge_history[ystr]="Gold Adherence"
            elif score>=85: s.badge_history[ystr]="Silver Adherence"
            elif score>=70: s.badge_history[ystr]="Bronze Adherence"
        s.last_rollover_date=today.isoformat()
def current_streak(threshold=STREAK_THRESHOLD):
    dates=sorted(st.session_state.daily_scores.keys(),reverse=True); streak=0
    for d in dates:
        if st.session_state.daily_scores[d]["score"]>=threshold: streak+=1
        else: break
    return streak

# ---- Graphics ----
def smile(score,size=200):
    img=Image.new("RGB",(size,size),"white"); d=ImageDraw.Draw(img)
    face="#b7f5c2" if score>=80 else ("#fff2b2" if score>=50 else "#ffb3b3")
    m=size*0.08; d.ellipse([m,m,size-m,size-m],fill=face,outline="black")
    er=int(size*0.04)
    d.ellipse([size*0.32-er,size*0.36-er,size*0.32+er,size*0.36+er],fill="black")
    d.ellipse([size*0.68-er,size*0.36-er,size*0.68+er,size*0.36+er],fill="black")
    if score>=80: d.arc([size*0.28,size*0.48,size*0.72,size*0.78],0,180,fill="black",width=4)
    elif score>=50: d.line([size*0.36,size*0.62,size*0.64,size*0.62],fill="black",width=4)
    else: d.arc([size*0.28,size*0.62,size*0.72,size*0.9],180,360,fill="black",width=4)
    return img
def turtle_trophy_png(path="trophy.png",size=300):
    try:
        screen=turtle.Screen(); screen.setup(width=size,height=size)
        t=turtle.Turtle(); t.hideturtle(); t.speed(0); t.color("gold")
        t.penup(); t.goto(-30,-80); t.pendown(); t.begin_fill()
        for _ in range(2): t.forward(60); t.left(90); t.forward(30); t.left(90)
        t.end_fill(); t.penup(); t.goto(0,-20); t.pendown(); t.begin_fill(); t.circle(80,steps=50); t.end_fill()
        cv=screen.getcanvas(); eps="trophy.eps"; cv.postscript(file=eps,colormode="color"); turtle.bye()
        img=Image.open(eps); img.save(path); 
        try: os.remove(eps)
        except: pass
        return path
    except:
        img=Image.new("RGB",(size,size),"white"); d=ImageDraw.Draw(img)
        d.rectangle([size*0.35,size*0.7,size*0.65,size*0.82],fill="gold",outline="black")
        d.ellipse([size*0.25,size*0.25,size*0.75,size*0.75],fill="gold",outline="black")
        img.save(path); return path

# ---- Audio beep ----
def beep(freq=880,dur_ms=500,vol=0.2):
    sr=44100; n=int(sr*(dur_ms/1000.0)); buf=bytearray()
    for i in range(n):
        s=vol*math.sin(2*math.pi*freq*(i/sr)); val=int(max(-1,min(1,s))*32767)
        buf+=val.to_bytes(2,"little",signed=True)
    b=io.BytesIO()
    with wave.open(b,"wb") as wf: wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr); wf.writeframes(buf)
    b.seek(0); return b

QUOTES=["Small steps, big impact!","Consistency is key.","One dose at a time.","Healthy habits build days.","Your routine is your superpower."]

# ---- Sidebar (Python-only) ----
with st.sidebar:
    st.header("Settings")
    tz_offset=st.number_input("Time offset (min)",-720,720,0)
    simulate_on=st.checkbox("Test mode: simulate time")
    simulate_hm=st.text_input("Simulated HH:MM","09:00") if simulate_on else ""
    upcoming_window=st.slider("Upcoming window (min)",15,240,UPCOMING_MIN)
    refresh=st.slider("Auto-refresh (sec)",15,120,60)
    st.experimental_autorefresh(interval=refresh*1000,key="refresh")
    st.divider(); st.header("Accessibility")
    font_px=st.slider("Font size (px)",14,24,18); dark=st.checkbox("High contrast (dark mode)")

bg="#0E1117" if dark else "#FFFFFF"; fg="#FFFFFF" if dark else "#000000"
st.markdown(f"""
<style>
html,body,[class*="css"]{{font-size:{font_px}px;background:{bg} !important;color:{fg} !important}}
.med-card{{padding:15px;border-radius:12px;margin-bottom:10px}}
</style>
""", unsafe_allow_html=True)

# ---- Navigation ----
def go(p): st.session_state.page=p
st.markdown("<h1 style='text-align:center;'>MedTimer</h1>", unsafe_allow_html=True)
c1,c2,c3,c4=st.columns(4)
with c1: 
    if st.button("Today"): go("today")
with c2: 
    if st.button("All Meds"): go("all_meds")
with c3: 
    if st.button("Add / Edit"): go("add")
with c4: 
    if st.button("Reports"): go("reports")

# ---- Rollover ----
rollover()

# ---- TODAY ----
if st.session_state.page=="today":
    st.header("Today's Doses")
    left,right=st.columns([2,1])
    now_dt=now_with_offset(tz_offset,simulate_on,simulate_hm); now_t=dtime(now_dt.hour,now_dt.minute)
    need_beep=False
    with left:
        any=False
        for med,info in st.session_state.meds.items():
            if info["days"] and WEEKDAYS[date.today().weekday()] not in info["days"]: continue
            for hm in info["time"]:
                any=True; taken=is_taken(med,hm); status,bg=status_for(now_t,parse_time(hm),taken,upcoming_window)
                st.markdown(f"""
                <div class='med-card' style='background:{bg};color:black;'>
                  <b style='color:black;'>{med}</b> — <span style='color:black;'>{hm}</span><br>
                  <i style='color:black;'>{info.get("note","")}</i><br><span style='color:black;'>{status}</span>
                </div>""", unsafe_allow_html=True)
                cA,cB=st.columns(2)
                with cA:
                    if not taken and st.button(f"Take-{med}-{hm}",key=f"take_{med}_{hm}"): mark_taken(med,hm)
                with cB:
                    if taken and st.button(f"Undo-{med}-{hm}",key=f"undo_{med}_{hm}"): unmark_taken(med,hm)
                if status in ("Upcoming","Missed"): need_beep=True
        if not any: st.info("No doses scheduled today.")
    with right:
        st.header("Daily Summary")
        sched,taken,score=compute_today()
        st.progress(min(score,100)/100); st.write(f"**Score:** {score}%")
        st.write(f"**Scheduled:** {sched}"); st.write(f"**Taken:** {taken}")
        if score>=TROPHY_THRESHOLD and sched>0:
            st.success("🏆 Great adherence!")
            st.image(turtle_trophy_png(), use_column_width=True)
        else:
            st.image(smile(score), use_column_width=True)
        import random; st.caption(f"💬 {random.choice(QUOTES)}")
        fig,ax=plt.subplots(figsize=(3,3)); missed=max(0,sched-taken)
        ax.pie([taken,missed],labels=["Taken","Remaining"],colors=["#b7f5c2","#ffb3b3"],autopct="%1.0f%%",startangle=90); ax.axis("equal")
        st.pyplot(fig)
        if need_beep: st.audio(beep(),format="audio/wav")

# ---- ALL MEDS ----
elif st.session_state.page=="all_meds":
    st.header("All Medications")
    if not st.session_state.meds: st.info("No medicines added.")
    else:
        rows=[{"Name":n,"Times":", ".join(i["time"]),
               "Days":", ".join(i["days"]) if i["days"] else "Every day",
               "Note":i.get("note",""),"Freq":i.get("freq",len(i.get("time",[])))}
              for n,i in st.session_state.meds.items()]
        st.dataframe(pd.DataFrame(rows), height=300)

# ---- ADD / EDIT ----
elif st.session_state.page=="add":
    st.header("Add / Edit Medicines")
    mode=st.radio("Mode",["Add New","Edit Existing"])
    if mode=="Add New":
        name=st.text_input("Medicine name"); note=st.text_input("Note (optional)")
        freq=int(st.number_input("Doses per day",1,MAX_DOSES_PER_DAY,1))
        st.write("Dose times:"); times=[]; cols=st.columns(min(freq,4))
        for i in range(freq):
            with cols[i%len(cols)]: t=st.time_input(f"Time #{i+1}", value=datetime.strptime("09:00","%H:%M").time()); times.append(t.strftime("%H:%M"))
        st.write("Repeat on days:"); cols=st.columns(7)
        day_checks={wd:cols[i].checkbox(wd,True) for i,wd in enumerate(WEEKDAYS)}
        days=default_days([d for d,c in day_checks.items() if c])
        if st.button("Add"):
            if not name.strip(): st.warning("Enter a name")
            elif name_exists(name.strip()): st.warning("Name already exists")
            else:
                times=normalize_times(times)
                if not times: st.warning("Add at least one valid time")
                else:
                    st.session_state.meds[name.strip()]={"time":times,"note":note.strip(),"days":days,"freq":len(times)}
                    st.success("Added"); st.rerun()
    else:
        meds=list(st.session_state.meds.keys())
        if not meds: st.info("No medicines to edit.")
        else:
            target=st.selectbox("Select medicine",meds); info=st.session_state.meds[target]
            new_name=st.text_input("Name",value=target); new_note=st.text_input("Note",value=info.get("note",""))
            freq=int(st.number_input("Doses per day",1,MAX_DOSES_PER_DAY, max(1, info.get("freq", len(info.get("time",[]))))))
            st.write("Dose times:"); new_times=[]; cols=st.columns(min(freq,4))
            for i in range(freq):
                default=info["time"][i] if i<len(info["time"]) else "08:00"
                with cols[i%len(cols)]:
                    t=st.time_input(f"Time #{i+1}", value=datetime.strptime(default,"%H:%M").time(), key=f"edit_{target}_{i}")
                    new_times.append(t.strftime("%H:%M"))
            st.write("Repeat on days:"); cols=st.columns(7)
            day_checks={wd:cols[i].checkbox(wd, value=(wd in (info.get("days") or WEEKDAYS))) for i,wd in enumerate(WEEKDAYS)}
            days=default_days([d for d,c in day_checks.items() if c])
            c1,c2,c3=st.columns(3)
            with c1:
                if st.button("Save"):
                    if not new_name.strip(): st.warning("Name cannot be empty")
                    elif name_exists(new_name.strip(), exclude=target): st.warning("Name already exists")
                    else:
                        new_times=normalize_times(new_times)
                        if not new_times: st.warning("Add at least one valid time")
                        else:
                            if new_name.strip()!=target:
                                st.session_state.meds[new_name.strip()]=st.session_state.meds.pop(target)
                                for h in st.session_state.history:
                                    if h["med"]==target: h["med"]=new_name.strip()
                                target=new_name.strip()
                            st.session_state.meds[target]={"time":new_times,"note":new_note.strip(),"days":days,"freq":len(new_times)}
                            st.success("Updated"); st.rerun()
            with c2:
                if st.button("Delete", type="primary"):
                    st.session_state.meds.pop(target,None)
                    st.session_state.history=[h for h in st.session_state.history if h["med"]!=target]
                    st.success("Deleted"); st.rerun()
            with c3:
                if st.button("Clear today's marks"):
                    st.session_state.history=[h for h in st.session_state.history if h["date"]!=today_str()]
                    st.info("Cleared"); st.rerun()

# ---- REPORTS ----
elif st.session_state.page=="reports":
    st.header("Weekly Report & Sharing")
    days=[date.today()-timedelta(days=i) for i in range(7)]
    rows=[]
    for d in sorted([di.isoformat() for di in days]):
        idx=date.fromisoformat(d).weekday()
        sched=sum(scheduled_on_day(info,idx) for info in st.session_state.meds.values())
        taken=sum(1 for h in st.session_state.history if h["date"]==d)
        score=int((taken/sched)*100) if sched>0 else 0
        rows.append({"date":d,"scheduled":sched,"taken":taken,"score":score,"badge":st.session_state.badge_history.get(d,"")})
    df=pd.DataFrame(rows).sort_values("date")
    st.subheader("Summary (last 7 days)"); st.dataframe(df, height=240)
    st.write(f"**Current streak:** {current_streak()} day(s) at ≥{STREAK_THRESHOLD}%")
    st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"), "medtimer_weekly.csv","text/csv")
    if HAS_PDF:
        b=io.BytesIO(); doc=fitz.open(); p=doc.new_page(); y=50
        p.insert_text((50,y),"MedTimer Weekly Report", fontsize=14); y+=30
        for _,r in df.iterrows():
            line=f"{r['date']} | Scheduled:{r['scheduled']} | Taken:{r['taken']} | Score:{r['score']}% | Badge:{r['badge']}"
            p.insert_text((50,y), line, fontsize=10); y+=18
            if y>770: p=doc.new_page(); y=50
        doc.save(b); doc.close(); b.seek(0)
        st.download_button("Download PDF", b, "medtimer_weekly.pdf","application/pdf")
    else:
        st.info("PDF unavailable (install PyMuPDF to enable).")


