
elif st.session_state.page == "add":
    st.header("Add / Edit Medicines")
    mode = st.radio("Mode", ["Add New", "Edit Existing"])

    # ---------- Helpers ----------
    def _normalize_times(times_list):
        """Return unique, sorted HH:MM strings."""
        # Keep only non-empty, valid strings; sort; deduplicate
        cleaned = []
        for hm in times_list:
            hm = str(hm).strip()
            try:
                dt = datetime.strptime(hm, "%H:%M")
                cleaned.append(dt.strftime("%H:%M"))
            except Exception:
                # ignore invalid formats
                pass
        # unique & sorted
        return sorted(list(dict.fromkeys(cleaned)))

    def _default_days_if_empty(days_sel):
        return days_sel if days_sel else WEEKDAYS.copy()

    def _name_exists(name, exclude=None):
        name = name.strip()
        return any(k == name and k != exclude for k in st.session_state.meds.keys())

    # ---------- Add New ----------
    if mode == "Add New":
        name = st.text_input("Medicine name")
        note = st.text_input("Note (optional)")

        freq_val = st.number_input("How many doses per day?", min_value=1, max_value=8, value=1)
        freq = int(freq_val)

        st.write("Set dose times:")
        times = []
        cols = st.columns(min(freq, 4))
        for i in range(freq):
            with cols[i % len(cols)]:
                t = st.time_input(f"Dose time #{i+1}", value=datetime.strptime("09:00", "%H:%M").time())
                times.append(t.strftime("%H:%M"))

        st.write("Repeat on days:")
        cols = st.columns(7)
        day_checks = {wd: cols[i].checkbox(wd, value=True) for i, wd in enumerate(WEEKDAYS)}
        sel_days = [d for d, checked in day_checks.items() if checked]
        sel_days = _default_days_if_empty(sel_days)

        if st.button("Add"):
            # Validations
            if not name.strip():
                st.warning("Please enter a medicine name.")
            elif _name_exists(name.strip()):
                st.warning(f"'{name.strip()}' already exists. Use a different name or edit the existing one.")
            else:
                times = _normalize_times(times)
                if len(times) == 0:
                    st.warning("Please add at least one valid dose time.")
                else:
                    st.session_state.meds[name.strip()] = {
                        "time": times,
                        "note": note.strip(),
                        "days": sel_days,
                        "freq": len(times),
                    }
                    st.success(f"Added '{name.strip()}' with {len(times)} dose(s).")
                    st.rerun()

    # ---------- Edit Existing ----------
    else:
        meds = list(st.session_state.meds.keys())
        if not meds:
            st.info("No medicines to edit.")
        else:
            target = st.selectbox("Select medicine", meds)
            info = st.session_state.meds[target]

            new_name = st.text_input("Name", value=target)
            new_note = st.text_input("Note", value=info.get("note", ""))

            # Times editor based on freq (allow changing count)
            freq_val = st.number_input("How many doses per day?", min_value=1, max_value=8, value=max(1, info.get("freq", len(info.get("time", [])))))
            freq = int(freq_val)

            st.write("Dose times:")
            new_times = []
            cols = st.columns(min(freq, 4))
            for i in range(freq):
                default = info["time"][i] if i < len(info["time"]) else "08:00"
                with cols[i % len(cols)]:
                    t = st.time_input(
                        f"Dose time #{i+1}",
                        value=datetime.strptime(default, "%H:%M").time(),
                        key=f"edit_time_{target}_{i}"
                    )
                    new_times.append(t.strftime("%H:%M"))

            st.write("Repeat on days:")
            cols = st.columns(7)
            day_checks = {
                wd: cols[i].checkbox(wd, value=(wd in (info.get("days") or WEEKDAYS)))
                for i, wd in enumerate(WEEKDAYS)
            }
            sel_days = [d for d, checked in day_checks.items() if checked]
            sel_days = _default_days_if_empty(sel_days)

            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("Save"):
                    # Validation
                    if not new_name.strip():
                        st.warning("Name cannot be empty.")
                    elif _name_exists(new_name.strip(), exclude=target):
                        st.warning(f"'{new_name.strip()}' already exists. Choose a different name.")
                    else:
                        new_times = _normalize_times(new_times)
                        if len(new_times) == 0:
                            st.warning("Please specify at least one valid time.")
                        else:
                            # Rename key safely (if name changed)
                            if new_name.strip() != target:
                                st.session_state.meds[new_name.strip()] = st.session_state.meds.pop(target)
                                # Update history entries to new name
                                for h in st.session_state.history:
                                    if h["med"] == target:
                                        h["med"] = new_name.strip()
                                target = new_name.strip()

                            # Save edited fields
                            st.session_state.meds[target] = {
                                "time": new_times,
                                "note": new_note.strip(),
                                "days": sel_days,
                                "freq": len(new_times),
                            }
                            st.success("Medicine updated.")
                            st.rerun()

            with c2:
                if st.button("Delete medicine", type="primary"):
                    st.session_state.meds.pop(target, None)
                    # Optionally remove history entries for this med
                    st.session_state.history = [h for h in st.session_state.history if h["med"] != target]
                    st.success(f"Deleted '{target}'.")
                    st.rerun()

            with c3:
                if st.button("Clear today's taken marks"):
                    st.session_state.history = [h for h in st.session_state.history if h["date"] != date.today().isoformat()]
                    st.info("Cleared today's marks.")
                    st.rerun()
