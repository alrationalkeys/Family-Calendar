/* Automations card: every Home Assistant routine in plain English, with on/off switches, when it last
   ran, the settings you can change (times, temperatures, which lights), and a simple "New routine"
   builder. Used by phone Settings (and the wall's Settings > Everything tab, which embeds the phone page).
   Data: GET /api/ha/automations. */
(function(){
  const css = `
  .au-group{border-top:1px solid var(--line)}
  .au-group:first-child{border-top:0}
  .au-group>summary{display:flex; align-items:center; gap:10px; padding:12px 0; cursor:pointer; list-style:none}
  .au-group>summary::-webkit-details-marker{display:none}
  .au-group>summary .gi{font-size:20px; width:26px; text-align:center; flex:none}
  .au-group>summary .gt{flex:1; min-width:0; display:flex; flex-direction:column}
  .au-group>summary .gt b{font-size:15.5px}
  .au-group>summary .gt small{font-size:12.5px; color:var(--ink-dim)}
  .au-group>summary .gt small.warn{color:#c0392b}
  .au-group>summary::after{content:"›"; font-size:22px; color:var(--ink-dim); transition:transform .15s}
  .au-group[open]>summary::after{transform:rotate(90deg)}
  .au-group .gb{padding:0 0 10px}
  .ts-row{display:flex; flex-wrap:wrap; align-items:center; gap:4px 10px; padding:9px 0; border-bottom:1px solid var(--line)}
  .ts-row .ts-t{flex:1 1 100%; font-size:14px} .ts-row .ts-v{flex:1; color:var(--ink-dim); font-size:13.5px}
  .ts-row .chg{border:0; background:var(--panel2); color:var(--ink); border-radius:9px; padding:6px 12px; font:inherit; font-size:13px; font-weight:600}
  .ts-form{background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:10px; margin:8px 0}
  .au-h{display:flex; align-items:center; justify-content:space-between; gap:10px}
  .au-h b{font-size:16px}
  .au-blurb{font-size:13px; color:var(--ink-dim); margin:4px 0 8px; line-height:1.4}
  .au-chips{display:flex; gap:6px; flex-wrap:wrap; margin:0 0 8px}
  .au-chip{font-size:12px; padding:3px 9px; border-radius:999px; background:var(--panel2); color:var(--ink-dim)}
  .au-chip.on{background:color-mix(in srgb, var(--now) 22%, var(--panel2)); color:var(--ink); font-weight:600}
  .au-row{display:flex; align-items:center; gap:10px; padding:8px 0}
  .au-row .t{flex:1; min-width:0}
  .au-row .n{font-size:14px; font-weight:600}
  .au-row .d{font-size:12.5px; color:var(--ink-dim); line-height:1.35; margin-top:2px}
  .au-row .l{font-size:11.5px; color:var(--ink-dim); margin-top:2px; opacity:.8}
  .au-row .ed{border:0; background:var(--panel2); color:var(--ink); border-radius:9px; padding:7px 11px; font:inherit; font-size:13px; font-weight:600; flex:none}
  .au-sw{position:relative; width:46px; height:28px; flex:none}
  .au-sw input{opacity:0; width:0; height:0; position:absolute}
  .au-sw span{position:absolute; inset:0; background:var(--panel2); border:1px solid var(--line); border-radius:999px; transition:.2s; cursor:pointer}
  .au-sw span::after{content:""; position:absolute; left:3px; top:3px; width:20px; height:20px; border-radius:50%; background:#fff; box-shadow:0 1px 3px rgba(0,0,0,.3); transition:.2s}
  .au-sw input:checked + span{background:var(--now); border-color:var(--now)}
  .au-sw input:checked + span::after{transform:translateX(18px)}
  .au-sw input:focus-visible + span{outline:2px solid var(--now); outline-offset:2px}
  .au-set{display:flex; align-items:center; justify-content:space-between; gap:10px; padding:6px 0}
  .au-set > label:not(.au-sw){font-size:13.5px; flex:1}
  .au-set .u{font-size:13px; color:var(--ink-dim); margin-left:-4px}
  .au-note{font-size:12.5px; color:var(--ink-dim); margin-top:8px; line-height:1.4}
  .au-set input[type=time], .au-set input[type=number], .au-set input[type=date]{width:auto; max-width:120px; margin:0; padding:6px 8px; font:inherit; font-size:14px;
    background:var(--panel2); color:var(--ink); border:1px solid var(--line); border-radius:8px}
  .au-sub{font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:var(--ink-dim); margin:10px 0 2px; font-weight:700}
  .au-missing{font-size:13px; color:var(--ink-dim); background:var(--panel2); border-radius:10px; padding:8px 10px; margin:4px 0 8px}
  .au-card{background:var(--panel2); border-radius:14px; padding:12px 12px 10px; margin:0 0 10px}
  .au-ch{display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:6px}
  .au-ch b{font-size:15.5px}
  .au-line{display:flex; flex-wrap:wrap; align-items:center; gap:6px; font-size:14px; padding:5px 0; line-height:1.5}
  .au-line.row{justify-content:space-between}
  .au-line.note{font-size:12.5px; color:var(--ink-dim); padding-top:2px}
  .au-line.sub{padding-left:22px}
  .au-line.hd{padding-top:9px; padding-bottom:0}
  .au-line.hd .lbl{color:var(--ink); font-weight:600; min-width:0}
  .au-line .dim{color:var(--ink-dim); font-size:12.5px}
  .au-line .lbl{min-width:92px; color:var(--ink-dim); font-size:13.5px}
  .au-line.row .lbl{color:var(--ink); font-size:14px}
  .au-line .in{margin:0; padding:5px 7px; font:inherit; font-size:14px; background:var(--panel); color:var(--ink); border:1px solid var(--line); border-radius:8px; width:auto}
  .au-line input[type=number].in{width:58px; text-align:center}
  .au-line input.date{min-width:150px; min-height:34px}
  .au-line .num{display:inline-flex; align-items:center; gap:2px}
  .pill{font-size:12px; padding:2px 9px; border-radius:999px; background:var(--panel); color:var(--ink-dim)}
  .pill.on{background:color-mix(in srgb, var(--now) 25%, var(--panel)); color:var(--ink); font-weight:600}
  .au-pick .miss{color:#c0392b}
  .au-card .au-pick{padding:2px 0 6px}
  details.au-more summary{font-size:13px; color:var(--ink-dim); cursor:pointer; padding:4px 0}
  .au-pick{padding:6px 0}
  .au-pick > .top{display:flex; align-items:center; justify-content:space-between; gap:10px}
  .au-pick > .top label{font-size:13.5px}
  .au-pick .names{font-size:12.5px; color:var(--ink-dim); margin-top:2px; line-height:1.35}
  .au-pick button.chg, .au-new{border:0; background:var(--panel2); color:var(--ink); border-radius:9px; padding:7px 12px; font:inherit; font-size:13px; font-weight:600; flex:none; cursor:pointer}
  .au-new{background:var(--now); color:#fff; width:100%; padding:12px; font-size:15px; margin:6px 0 4px; border-radius:12px}
  .au-list{max-height:260px; overflow:auto; margin-top:6px; border:1px solid var(--line); border-radius:10px; padding:4px 8px; background:var(--panel2)}
  .au-list label{display:flex; align-items:center; gap:10px; padding:7px 2px; font-size:14px; border-bottom:1px solid var(--line)}
  .au-list label:last-child{border-bottom:0}
  .au-list input{width:20px; height:20px; margin:0; accent-color:var(--now); flex:none}
  .au-list .grp{font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:var(--ink-dim); font-weight:700; padding:8px 2px 2px}
  /* routine builder sheet */
  #au-ov{position:fixed; inset:0; z-index:90; background:rgba(0,0,0,.55); display:none; align-items:flex-end; justify-content:center}
  #au-ov.on{display:flex}
  #au-sheet{width:100%; max-width:600px; max-height:92vh; overflow:auto; background:var(--panel); color:var(--ink); border-radius:22px 22px 0 0;
    padding:16px 16px calc(20px + env(safe-area-inset-bottom)); box-shadow:0 -10px 40px rgba(0,0,0,.4)}
  #au-sheet h3{margin:0 0 4px; font-size:20px; display:flex; justify-content:space-between; align-items:center}
  #au-sheet h3 button{border:0; background:var(--panel2); color:var(--ink); width:38px; height:38px; border-radius:50%; font-size:16px}
  .rb-step{margin:14px 0 0}
  .rb-lab{font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:var(--ink-dim); font-weight:700; margin-bottom:6px}
  .rb-chips{display:flex; flex-wrap:wrap; gap:6px}
  .rb-chips button{border:0; background:var(--panel2); color:var(--ink); border-radius:999px; padding:9px 13px; font:inherit; font-size:14px; font-weight:600; cursor:pointer}
  .rb-chips button.on{background:var(--now); color:#fff}
  .rb-row{display:flex; gap:8px; align-items:center; margin-top:8px; flex-wrap:wrap}
  #au-sheet input[type=text], #au-sheet input[type=time], #au-sheet input[type=number], #au-sheet select{font:inherit; font-size:15px; padding:9px 10px; border-radius:10px;
    border:1px solid var(--line); background:var(--panel2); color:var(--ink); margin:0; max-width:100%}
  #au-sheet input[type=text]{width:100%}
  .rb-chk{display:flex; align-items:center; gap:10px; font-size:14.5px; padding:6px 0}
  .rb-chk input, .au-list input{-webkit-appearance:checkbox !important; appearance:auto !important; width:20px !important; height:20px !important; min-width:20px;
    padding:0 !important; border:0 !important; background:none !important; accent-color:var(--now); margin:0 !important; flex:none; display:inline-block !important; opacity:1 !important; position:static !important}
  .rb-act{background:var(--panel2); border-radius:14px; padding:10px 12px; margin-top:8px}
  .rb-act .hd{display:flex; justify-content:space-between; align-items:center; font-weight:700; font-size:14.5px}
  .rb-act .hd>span{flex:1} .rb-act .hd button[data-mv]{margin-right:4px; font-size:16px}
  .rb-act .hd button{border:0; background:transparent; color:var(--ink-dim); font-size:18px; cursor:pointer}
  .rb-act .names{font-size:13px; color:var(--ink-dim); margin:4px 0}
  .rb-act .au-list{background:var(--panel)}
  .rb-sum{margin-top:16px; background:color-mix(in srgb, var(--now) 14%, var(--panel2)); border-radius:12px; padding:10px 12px; font-size:14px; line-height:1.45}
  .rb-btns{display:flex; gap:8px; margin-top:14px}
  .rb-btns button{flex:1; border:0; border-radius:12px; padding:13px; font:inherit; font-size:15px; font-weight:700; cursor:pointer; background:var(--panel2); color:var(--ink)}
  .rb-btns .save{background:var(--now); color:#fff; flex:2}
  .rb-btns .del{color:#d9534f}
  .rb-err{color:#d9534f; font-size:13.5px; margin-top:8px; min-height:1em}`;
  let styled = false, last = null, lastBox = null, lastToast = null;
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  function ago(iso){
    if (!iso) return "hasn't run yet";
    const d = new Date(iso); if (isNaN(d)) return "";
    const t = d.toLocaleTimeString([], {hour:"numeric", minute:"2-digit"});
    const days = Math.floor((new Date().setHours(0,0,0,0) - new Date(d).setHours(0,0,0,0)) / 86400000);
    return "last ran " + (days === 0 ? `today ${t}` : days === 1 ? `yesterday ${t}` : d.toLocaleDateString([], {month:"short", day:"numeric"}) + " " + t);
  }
  const sw = (attrs, on) => `<label class="au-sw"><input type="checkbox" ${attrs} ${on ? "checked" : ""}><span></span></label>`;
  async function post(url, body, method){
    const r = await fetch(url, {method: method || "POST", headers: {"Content-Type":"application/json"}, body: body ? JSON.stringify(body) : undefined});
    return r.ok ? r.json() : {ok:false, reason: r.status === 401 || r.status === 403 ? "Enter the Family PIN first" : "Couldn’t reach the wall"};
  }
  const say = m => { try { (lastToast || (()=>{}))(m); } catch(e){} };

  /* checklist of devices: groups = [[title, items]], chosen = [ids] */
  function checklist(groups, chosen){
    // grouped by room (Home Assistant Areas), then lights / plugs within each room
    const rooms = new Map();
    groups.filter(g => g[1].length).forEach(([t, items]) => items.forEach(i => {
      const r = i.area || "Other";
      if (!rooms.has(r)) rooms.set(r, []);
      rooms.get(r).push({...i, kind: t});
    }));
    const order = [...rooms.keys()].sort((a, b) => (b === "Quick picks") - (a === "Quick picks") || (a === "Other") - (b === "Other") || a.localeCompare(b));
    const many = groups.filter(g => g[1].length).length > 1;
    return `<div class="au-list">` + order.map(r => `<div class="grp">${esc(r)}</div>` + rooms.get(r).map(i =>
      `<label><input type="checkbox" value="${esc(i.id)}" ${chosen.includes(i.id) ? "checked" : ""}>${esc(i.name)}${many && /plug|switch/i.test(i.kind) && !/plug|switch/i.test(i.name) ? ` <span class="dim">(plug)</span>` : ""}</label>`).join("")
    ).join("") + `</div>`;
  }
  const picked = el => [...el.querySelectorAll(".au-list input:checked")].map(i => i.value);
  const GROUP_NAMES = {"*lights": "All lights", "*indoor": "All indoor lights", "*outdoor": "All outside lights", "*tvs": "All TVs",
    "*entry": "Entry lights (porch, driveway, foyer, kitchen)", "*locks": "All locks", "*garage": "Garage door", "*all": "Both thermostats"};
  const GROUP_FOR = {on: ["*lights", "*indoor", "*outdoor", "*entry", "*tvs"], off: ["*lights", "*indoor", "*outdoor", "*tvs"], dim: ["*indoor", "*outdoor", "*entry"],
    lock: ["*locks"], close: ["*garage"], thermostat: ["*all"]};
  const nameOf = (id) => { if (GROUP_NAMES[id]) return GROUP_NAMES[id]; const c = (last && last.choices) || {}; for (const k in c) { const f = c[k].find(x => x.id === id); if (f) return f.name; } return id; };

  /* ---------- Alarm.com-style cards: one card per schedule, plain words, inline controls ---------- */
  const helperMap = g => Object.fromEntries((g.settings || []).map(s => [s.entity_id, s]));
  function ctl(H, eid, opts){                       // one inline control for a setting (or "" if it isn't there)
    const s = H[eid]; if (!s) return "";
    const id = "au-" + eid.replace(/\W/g, "_"), o = opts || {};
    if (s.kind === "time") return `<input type="time" class="in" id="${id}" data-helper="${esc(eid)}" value="${esc(s.value)}">`;
    if (s.kind === "date") return `<input type="date" class="in date" id="${id}" data-helper="${esc(eid)}" value="${esc(s.value)}">`;
    if (s.kind === "number") return `<span class="num"><input type="number" class="in" id="${id}" data-helper="${esc(eid)}" value="${esc(parseFloat(s.value))}" min="${esc(s.min)}" max="${esc(s.max)}" step="${esc(s.step || 1)}">${o.unit ?? (s.unit === "°F" ? "°" : esc(s.unit))}</span>`;
    if (s.kind === "toggle") return sw(`id="${id}" data-helper="${esc(eid)}"`, s.value === "on");
    return "";
  }
  function pick(H, eid, label){                     // which lights: names, Change -> checklist
    const s = H[eid]; if (!s) return "";
    const ids = s.value || [], names = s.labels || [];
    const shown = ids.length ? ids.map((x, i) => names[i] && names[i] !== x ? esc(names[i]) : `<span class="miss">⚠ ${esc(x)} (not found, pick again)</span>`).join(", ") : `<span class="miss">None picked yet: tap Change</span>`;
    const fix = (s.fixes || []).length ? `<button class="au-new au-fix" style="margin-top:8px">Fix it: use ${esc(s.fixes.map(f => f.name).join(", "))}</button>` : "";
    return `<div class="au-pick" data-pick="${esc(eid)}"><div class="top"><label>${esc(label)}</label><button class="chg">Change</button></div><div class="names">${shown}</div>${fix}</div>`;
  }
  const card = (title, right, body) => `<div class="au-card"><div class="au-ch"><b>${title}</b>${right || ""}</div>${body}</div>`;
  const line = (inner, cls) => `<div class="au-line ${cls || ""}">${inner}</div>`;
  const LAYOUT = {
    peak(H, g){
      const st = g.status || [], peakNow = st.find(x => /peak now/i.test(x.name)), summer = st.find(x => /summer/i.test(x.name));
      return card("📅 Schedule", ctl(H, "input_boolean.sched_enabled"),
          `<div class="ts-box" data-ts>Loading the schedule…</div>` +
          line(`Each time sets the thermostats it's for until the next time. Peak hours still win.`, "note"))
        + card("⚡ Peak hours (Santee Cooper)", ctl(H, "input_boolean.peak_enabled"),
          line(`Heat and AC are <b>off</b> during peak${peakNow ? ` · <span class="pill ${peakNow.on ? "on" : ""}">${peakNow.on ? "Peak right now" : "Not peak now"}</span>` : ""}`) +
          line(`<span class="lbl">❄️ Winter peak</span><span class="dim">Nov–Mar</span>`, "hd") +
          line(`${ctl(H, "input_datetime.peak_winter_start")} to ${ctl(H, "input_datetime.peak_winter_end")}`, "sub") +
          line(`warm up to ${ctl(H, "input_number.peak_preheat")} an hour before`, "sub") +
          line(`<span class="lbl">🌞 Summer peak</span><span class="dim">Apr–Oct</span>`, "hd") +
          line(`${ctl(H, "input_datetime.peak_summer_start")} to ${ctl(H, "input_datetime.peak_summer_end")}`, "sub") +
          line(`cool down to ${ctl(H, "input_number.peak_precool")} an hour before`, "sub") +
          line(`<span class="lbl">🛟 Safety</span>`, "hd") +
          line(`back on if the house drops below ${ctl(H, "input_number.peak_safe_low")}`, "sub") +
          line(`or goes above ${ctl(H, "input_number.peak_safe_high")}`, "sub"));
    },
    outdoor(H, g){
      const st = g.status || [], xmas = st.find(x => /christmas/i.test(x.name)), hall = st.find(x => /halloween/i.test(x.name));
      const sw11 = H["input_datetime.fh_outdoor_switchover"];
      return card("🏡 Front lights · every night", "",
          pick(H, "input_text.fh_outdoor_night_lights", "Lights") +
          line(`On at <b>sunset</b> · off at <b>sunrise</b>`) +
          line(`In holiday season they come on at ${esc(sw11 ? fmtT(sw11.value) : "11:50 PM")} instead, after the holiday lights.`, "note"))
        + card("🎃🎄 Holiday lights outside", "",
          pick(H, "input_text.fh_outdoor_holiday_lights", "Plug") +
          line(`On at <b>sunset</b> · off at ${ctl(H, "input_datetime.fh_outdoor_switchover")}`) +
          line(`<span class="lbl">Halloween (all of October)</span>${ctl(H, "input_boolean.fh_outdoor_halloween")}`, "row") +
          line(`<span class="lbl">Christmas season (below)</span>${ctl(H, "input_boolean.fh_outdoor_christmas")}`, "row") +
          line(`<span class="lbl">Turn them on tonight anyway</span>${ctl(H, "input_boolean.holiday_lights_force")}`, "row"))
        + card("🎄 Christmas lights inside", "",
          pick(H, "input_text.fh_outdoor_window_lights", "Plugs") +
          line(`On at <b>sunset</b> · off at ${ctl(H, "input_datetime.fh_outdoor_windows_off")}`) +
          line(`Only during Christmas season.`, "note"))
        + card("🗓 Christmas season", xmas ? `<span class="pill ${xmas.on ? "on" : ""}">${xmas.on ? "On now" : "Not yet"}</span>` : "",
          line(`<span class="lbl">Starts</span>${ctl(H, "input_datetime.fh_outdoor_xmas_start")}`) +
          line(`Leave the date empty to start the day after Thanksgiving.`, "note") +
          line(`<span class="lbl">Ends</span>January ${ctl(H, "input_number.fh_outdoor_xmas_last_day", {unit: ""})}`));
    },
    kitchen(H){
      return card("💡 Which lights", "",
          pick(H, "input_text.fh_kitchen_upper_lights", "Upper lights") + pick(H, "input_text.fh_kitchen_lower_lights", "Lower lights") +
          pick(H, "input_text.fh_kitchen_patio_lights", "Back patio"))
        + card("🌆 Evening", "",
          line(`Uppers + patio on at ${ctl(H, "input_datetime.fh_kitchen_evening_on")}, uppers at ${ctl(H, "input_number.fh_kitchen_evening_bright")}`) +
          line(`Patio off at ${ctl(H, "input_datetime.fh_kitchen_patio_off")}`) +
          line(`Uppers off at ${ctl(H, "input_datetime.fh_kitchen_uppers_off")}`))
        + card("🌙 Night-light on motion", "",
          line(`Lowers from ${ctl(H, "input_datetime.fh_kitchen_lower_motion_from")}, uppers from ${ctl(H, "input_datetime.fh_kitchen_upper_motion_from")}`) +
          line(`until ${ctl(H, "input_datetime.fh_kitchen_motion_until")}, at ${ctl(H, "input_number.fh_kitchen_motion_bright")}`) +
          line(`Off after ${ctl(H, "input_number.fh_kitchen_quiet_minutes", {unit: " min"})} with no motion`))
        + card("🌅 Morning", "", line(`Everything off at ${ctl(H, "input_datetime.fh_kitchen_morning_off")}`));
    },
  };
  function fmtT(v){ const m = String(v || "").match(/^(\d{1,2}):(\d{2})/); if (!m) return v || ""; const h = +m[1]; return `${(h % 12) || 12}:${m[2]} ${h < 12 ? "AM" : "PM"}`; }

  function render(box, data, toast){
    if (!styled){ const s = document.createElement("style"); s.textContent = css; document.head.appendChild(s); styled = true; }
    last = data; lastBox = box; lastToast = toast;
    if (!data || !data.connected){ box.innerHTML = '<div class="hint">Home Assistant isn’t reachable, so the routines can’t be shown right now.</div>'; return; }
    const ch = data.choices || {};
    const wasOpen = new Set([...box.querySelectorAll("details.au-group[open]")].map(d => d.dataset.k));   // keep open across refreshes
    const ICON = {peak: "🌡", outdoor: "🏡", kitchen: "🍳", other: "⚙️"};
    const head = (k, icon, title, sub, warn) => `<details class="au-group" data-k="${k}" ${wasOpen.has(k) ? "open" : ""}><summary><span class="gi">${icon}</span><span class="gt"><b>${esc(title)}</b><small class="${warn ? "warn" : ""}">${esc(sub)}</small></span></summary><div class="gb">`;
    let html = "";
    // ---- your own routines first ----
    const mine = data.mine || [];
    html += head("mine", "✨", "Your routines", mine.length ? `${mine.length} made by you` : "Make your own: pick when, then what happens") +
      `<div class="au-blurb">Pick when, then what happens. Saved straight into Home Assistant.</div>`;
    (data.mine || []).forEach(a => {
      html += `<div class="au-row"><div class="t"><div class="n">${esc(a.name)}</div><div class="d">${esc(a.about)}</div><div class="l">${esc(ago(a.last))}</div></div>
        ${a.editable !== false ? `<button class="ed" data-edit="${esc(a.id)}">Edit</button>` : ""}${sw(`data-auto="${esc(a.entity_id)}" aria-label="${esc(a.name)}"`, a.on)}</div>`;
    });
    html += `<button class="au-new" data-new>＋ New routine</button></div></details>`;
    // ---- built-in groups ----
    (data.groups || []).forEach(g => {
      const allOn = g.automations.length && g.automations.every(a => a.on);
      const missing = (g.settings || []).some(x => x.kind === "lights" && ((x.value || []).length === 0 || (x.labels || []).some((n, i) => n === (x.value || [])[i])));
      const sub = !g.installed && g.key !== "other" ? "Not set up yet" : !allOn ? "Paused" : missing ? "Pick the lights (some are missing)" : ({peak: "Daily schedule + peak hours", outdoor: "Front, holiday and Christmas lights", kitchen: "Evening, night-light, morning"}[g.key] || `${g.automations.length} routines`);
      html += head(g.key, ICON[g.key] || "⚙️", g.title, sub, missing || !allOn);
      html += `<div class="au-blurb">${esc(g.blurb)}</div>`;
      if (g.installed && (g.key === "outdoor" || g.key === "kitchen"))
        html += `<button class="au-new" data-convert="${g.key}" style="margin:0 0 10px">✨ Turn these into my own routines (edit each one)</button>`;
      if (g.automations.length) html += `<div class="au-line row" style="padding:0 0 8px"><span class="lbl">All of these on</span>${sw(`data-group="${g.key}" aria-label="All of ${esc(g.title)}"`, allOn)}</div>`;
      if (!g.installed && g.key !== "other") html += `<div class="au-missing">Not installed in Home Assistant yet: add <code>docs/ha/${esc(g.file || g.key)}.yaml</code> to the packages folder.</div>`;
      if (g.status.length && !LAYOUT[g.key]) html += `<div class="au-chips">${g.status.map(s => `<span class="au-chip ${s.on ? "on" : ""}">${esc(s.name)}: ${s.on ? "yes" : "no"}</span>`).join("")}</div>`;
      if (g.settings.length && LAYOUT[g.key]){
        html += LAYOUT[g.key](helperMap(g), g);
      } else if (g.settings.length){
        html += `<div class="au-sub">Settings</div>`;
        g.settings.forEach(s => {
          const id = "au-" + s.entity_id.replace(/\W/g, "_");
          if (s.kind === "lights"){
            html += `<div class="au-pick" data-pick="${esc(s.entity_id)}"><div class="top"><label>${esc(s.name)}</label><button class="chg">Change</button></div>
              <div class="names">${s.labels && s.labels.length ? esc(s.labels.join(", ")) : "None picked"}</div></div>`;
            return;
          }
          let ctl = "";
          if (s.kind === "date") ctl = `<input type="date" id="${id}" data-helper="${esc(s.entity_id)}" value="${esc(s.value)}">`;
          else if (s.kind === "time") ctl = `<input type="time" id="${id}" data-helper="${esc(s.entity_id)}" value="${esc(s.value)}">`;
          else if (s.kind === "number") ctl = `<input type="number" id="${id}" data-helper="${esc(s.entity_id)}" value="${esc(parseFloat(s.value))}" min="${esc(s.min)}" max="${esc(s.max)}" step="${esc(s.step || 1)}"> <span class="u">${esc(s.unit)}</span>`;
          else if (s.kind === "toggle") ctl = sw(`id="${id}" data-helper="${esc(s.entity_id)}"`, s.value === "on");
          html += `<div class="au-set"><label for="${id}">${esc(s.name)}</label>${ctl}</div>`;
        });
      }
      if (g.automations.length){
        html += `<details class="au-more"><summary>Behind the scenes (${g.automations.length} step${g.automations.length === 1 ? "" : "s"})</summary>`;
        g.automations.forEach(a => {
          html += `<div class="au-row"><div class="t"><div class="n">${esc(a.name)}</div>${a.about ? `<div class="d">${esc(a.about)}</div>` : ""}<div class="l">${esc(ago(a.last))}</div></div>${sw(`data-auto="${esc(a.entity_id)}" aria-label="${esc(a.name)}"`, a.on)}</div>`;
        });
        html += `</details>`;
      }
      html += `</div></details>`;
    });
    if (!(data.fh_ids || []).length && (data.groups || []).some(g => !g.installed && g.key !== "other"))
      html += `<div class="au-note">Home Assistant reports <b>${data.ha_total ?? 0}</b> automation${data.ha_total === 1 ? "" : "s"} and <b>${data.helpers_found ?? 0}</b> FamilyHub setting${data.helpers_found === 1 ? "" : "s"}. 0 settings means Home Assistant hasn't loaded the packages folder.</div>`;
    html += `<div class="au-note">Changes take effect right away and stay after Home Assistant restarts. Turning a routine off pauses it until you turn it back on.</div>`;
    box.innerHTML = html;

    const tsBox = box.querySelector("[data-ts]");
    if (tsBox) thermoSched(tsBox);
    box.querySelectorAll("[data-convert]").forEach(b => b.onclick = async () => {
      const g = (data.groups || []).find(x => x.key === b.dataset.convert);
      if (!confirm(`Rebuild "${g ? g.title : b.dataset.convert}" as your own routines? Same times and lights, each one editable under Your routines. The built-in versions get switched off.`)) return;
      b.disabled = true; b.textContent = "Building your routines…";
      const r = await post("/api/ha/automations/convert", {keys: [b.dataset.convert]});
      if (!r.ok){ say(r.reason || "Couldn’t build them"); b.disabled = false; b.textContent = "✨ Turn these into my own routines (edit each one)"; return; }
      say(`Made ${r.made.length} routine${r.made.length === 1 ? "" : "s"}` + (r.skipped && r.skipped.length ? ` (skipped ${r.skipped.length} with no lights picked)` : ""));
      setTimeout(() => load(box, toast), 1500);
    });
    box.querySelectorAll("input[data-auto]").forEach(el => el.onchange = async () => {
      const r = await post("/api/ha/automations/toggle", {entity_id: el.dataset.auto, on: el.checked});
      say(r.ok ? (el.checked ? "Turned on" : "Paused") : (r.reason || "Couldn’t reach Home Assistant"));
    });
    box.querySelectorAll("input[data-group]").forEach(el => el.onchange = async () => {
      const g = (data.groups || []).find(x => x.key === el.dataset.group); if (!g) return;
      await Promise.all(g.automations.map(a => post("/api/ha/automations/toggle", {entity_id: a.entity_id, on: el.checked})));
      say(el.checked ? `${g.title}: on` : `${g.title}: paused`); load(box, toast);
    });
    box.querySelectorAll("[data-helper]").forEach(el => el.onchange = async () => {
      const value = el.type === "checkbox" ? el.checked : el.value;
      const r = await post("/api/ha/automations/setting", {entity_id: el.dataset.helper, value});
      say(r.ok ? "Saved" : (r.reason || "Couldn’t save"));
      if (r.ok) setTimeout(() => {                                // descriptions show the new value…
        const busy = box.querySelector(".au-list") || (document.activeElement && box.contains(document.activeElement) && /INPUT|SELECT/.test(document.activeElement.tagName));
        if (!busy) load(box, toast);                              // …unless you're in the middle of something
      }, 800);
    });
    // light lists: Change -> checklist of lights + plugs, Done saves
    box.querySelectorAll("[data-pick]").forEach(p => {
      const s = data.groups.flatMap(g => g.settings).find(x => x.entity_id === p.dataset.pick);
      const btn = p.querySelector(".chg");
      const fx = p.querySelector(".au-fix");
      if (fx) fx.onclick = async () => {                       // swap each stale id for the device it meant
        const map = Object.fromEntries((s.fixes || []).map(f => [f.from, f.to]));
        const ids = (s.value || []).map(x => map[x] || x);
        fx.disabled = true; fx.textContent = "…";
        const r = await post("/api/ha/automations/setting", {entity_id: s.entity_id, value: ids});
        say(r.ok ? "Fixed" : (r.reason || "Couldn’t save")); load(box, toast);
      };
      btn.onclick = async () => {
        const open = p.querySelector(".au-list");
        if (!open){ p.insertAdjacentHTML("beforeend", checklist([["Lights", ch.lights || []], ["Plugs & switches", ch.switches || []]], s.value || [])); btn.textContent = "Done"; return; }
        const ids = picked(p);
        const r = await post("/api/ha/automations/setting", {entity_id: s.entity_id, value: ids});
        say(r.ok ? "Saved" : (r.reason || "Couldn’t save"));
        if (r.ok) load(box, toast); else { open.remove(); btn.textContent = "Change"; }
      };
    });
    box.querySelectorAll("[data-new]").forEach(b => b.onclick = () => openBuilder(null, null));
    box.querySelectorAll("[data-edit]").forEach(b => b.onclick = async () => {
      const r = await fetch("/api/ha/automations/routine/" + encodeURIComponent(b.dataset.edit)).then(x => x.json()).catch(() => ({}));
      if (r.ok) openBuilder(r.id, r.spec); else say(r.reason || "Couldn’t open it");
    });
  }

  /* ---------------- New routine builder ---------------- */
  const WHEN = [["time","🕒 A time"],["sunset","🌇 Sunset"],["sunrise","🌅 Sunrise"],["device","🚪 Door / motion"],["arrive","🏠 Someone gets home"],["leave","🚗 Everyone leaves"],["alarm","🛡 Alarm"]];
  const DO = [["on","Turn on"],["off","Turn off"],["dim","Dim lights to…"],["thermostat","Thermostat"],["lock","Lock doors"],["close","Close garage"],["notify","Notify our phones"],["say","Say it on the wall"],["wait","Then wait…"]];
  const DAYS = [["mon","M"],["tue","T"],["wed","W"],["thu","T"],["fri","F"],["sat","S"],["sun","S"]];
  let spec = null, editId = null, houseMode = null;
  const MODE_DO = [["off","Turn off"],["on","Turn on"],["dim","Dim / color"],["lock","Lock"],["close","Close garage"],["arm","Arm the alarm"],
    ["open_garage","Open the garage (after disarm)"],["thermostat","Thermostat"],["schedule","Thermostats back to schedule"],["village","Christmas village"],["say","Say it on the wall"]];
  const MODE_TITLE = {goodnight: "🌙 Good night", away: "🚪 Leaving", welcome: "🏡 I'm home"};
  const doList = () => houseMode ? MODE_DO.filter(d => d[0] !== "open_garage" || houseMode === "welcome") : DO;

  function ensureSheet(){
    let ov = document.getElementById("au-ov");
    if (ov) return ov;
    ov = document.createElement("div"); ov.id = "au-ov";
    ov.innerHTML = `<div id="au-sheet" role="dialog" aria-modal="true"></div>`;
    document.body.appendChild(ov);
    ov.addEventListener("click", e => { if (e.target === ov) closeBuilder(); });
    return ov;
  }
  function closeBuilder(){ const ov = document.getElementById("au-ov"); if (ov) ov.classList.remove("on"); }
  /* ---- thermostat schedule: any number of times, per thermostat (services/thermo_sched.py) ---- */
  const TS_DAYS = [["mon","M"],["tue","T"],["wed","W"],["thu","T"],["fri","F"],["sat","S"],["sun","S"]];
  async function thermoSched(el, keep){
    let d = keep;
    if (!d){ try { d = await fetch("/api/ha/thermostat-schedule").then(r => r.json()); } catch(e){ el.textContent = "Couldn’t load the schedule."; return; } }
    const stats = d.thermostats || [], nm = id => (stats.find(x => x.id === id) || {name: id.replace("climate.", "")}).name;
    const who = s => s.targets.length >= stats.length && stats.length > 1 ? "Both" : s.targets.map(nm).join(" + ");
    const dayTxt = ds => ds.length === 7 ? "Every day" : ds.join() === "mon,tue,wed,thu,fri" ? "Weekdays" : ds.join() === "sat,sun" ? "Weekends"
      : ds.map(x => x[0].toUpperCase() + x.slice(1, 3)).join(" ");
    const icon = at => { const h = +at.slice(0, 2); return h < 5 || h >= 20 ? "🌙" : h < 12 ? "🌅" : h < 17 ? "☀️" : "🌆"; };
    const slots = d.slots || [];
    let html = slots.map((s, i) => `<div class="ts-row" data-i="${i}"><div class="ts-t"><b>${icon(s.at)} ${esc(fmtT(s.at))}</b> · ${esc(dayTxt(s.days))} · ${esc(who(s))}</div>
        <div class="ts-v">heat ${s.heat}° · cool ${s.cool}°</div><button class="chg" data-ts-ed="${i}">Edit</button></div>`).join("");
    html += `<button class="au-new" data-ts-add style="margin-top:8px">＋ Add a time</button>`;
    if (!d.saved) html += `<div class="hint" style="margin-top:6px">This is your current day / night schedule. Change anything and it switches to the new schedule.</div>`;
    if (d.saved === true && d.package_ready === false) html += `<div class="au-missing">Re-download <code>peak_thermostat.yaml</code> once so "back on after peak" uses these times.</div>`;
    el.innerHTML = html;
    const save = async (next) => {
      const r = await post("/api/ha/thermostat-schedule", {slots: next});
      if (!r.ok){ say(r.reason || "Couldn’t save"); return false; }
      say("Saved — the thermostats are on it"); d.slots = r.slots; d.saved = true; thermoSched(el, d); return true;
    };
    const edit = (i) => {
      const s = i == null ? {at: "07:00", days: TS_DAYS.map(x => x[0]), targets: stats.map(x => x.id), heat: 66, cool: 72} : JSON.parse(JSON.stringify(slots[i]));
      const row = i == null ? el.querySelector("[data-ts-add]") : el.querySelector(`.ts-row[data-i="${i}"]`);
      const f = document.createElement("div"); f.className = "ts-form";
      const draw = () => { f.innerHTML = `<div class="rb-row"><input type="time" data-f="at" value="${esc(s.at)}"></div>
        <div class="rb-chips">${TS_DAYS.map(([k, t]) => `<button data-fd="${k}" class="${s.days.includes(k) ? "on" : ""}" style="width:38px; padding:8px 0">${t}</button>`).join("")}</div>
        <div class="rb-chips" style="margin-top:6px"><button data-fq="all">Every day</button><button data-fq="wk">Weekdays</button><button data-fq="we">Weekends</button></div>
        <div class="rb-chips" style="margin-top:8px">${stats.map(t => `<button data-ft="${esc(t.id)}" class="${s.targets.includes(t.id) ? "on" : ""}">${esc(t.name)}</button>`).join("")}</div>
        <div class="rb-row">heat <input type="number" min="45" max="85" data-f="heat" value="${s.heat}" style="width:74px">° &nbsp; cool <input type="number" min="55" max="95" data-f="cool" value="${s.cool}" style="width:74px">°</div>
        <div class="rb-btns" style="margin-top:8px">${i == null ? "" : `<button class="del" data-fx="del">Delete</button>`}<button data-fx="cancel">Cancel</button><button class="save" data-fx="save">Save</button></div>`;
        f.querySelectorAll("[data-f]").forEach(x => x.oninput = x.onchange = () => { s[x.dataset.f] = x.type === "number" ? +x.value : x.value; });
        f.querySelectorAll("[data-fd]").forEach(b => b.onclick = () => { const k = b.dataset.fd; s.days = s.days.includes(k) ? s.days.filter(x => x !== k) : TS_DAYS.map(x => x[0]).filter(x => x === k || s.days.includes(x)); draw(); });
        f.querySelectorAll("[data-fq]").forEach(b => b.onclick = () => { s.days = {all: TS_DAYS.map(x => x[0]), wk: ["mon","tue","wed","thu","fri"], we: ["sat","sun"]}[b.dataset.fq]; draw(); });
        f.querySelectorAll("[data-ft]").forEach(b => b.onclick = () => { const k = b.dataset.ft; s.targets = s.targets.includes(k) ? s.targets.filter(x => x !== k) : [...s.targets, k]; draw(); });
        f.querySelector('[data-fx="cancel"]').onclick = () => thermoSched(el, d);
        const del = f.querySelector('[data-fx="del"]');
        if (del) del.onclick = () => { if (slots.length < 2){ say("Keep at least one time"); return; } if (confirm("Delete this time?")) save(slots.filter((_, j) => j !== i)); };
        f.querySelector('[data-fx="save"]').onclick = () => { const next = slots.slice(); if (i == null) next.push(s); else next[i] = s; save(next); };
      };
      draw(); row.replaceWith(f);
    };
    el.querySelectorAll("[data-ts-ed]").forEach(b => b.onclick = () => edit(+b.dataset.tsEd));
    el.querySelector("[data-ts-add]").onclick = () => edit(null);
  }

  function bindSteps(sh, sum){
    const $$ = q => sh.querySelectorAll(q);
    $$("[data-rm]").forEach(b => b.onclick = () => { spec.do.splice(+b.dataset.rm, 1); draw(); });
    $$("[data-mv]").forEach(b => b.onclick = () => { const i = +b.dataset.mv, j = i + (+b.dataset.d); if (j < 0 || j >= spec.do.length) return; [spec.do[i], spec.do[j]] = [spec.do[j], spec.do[i]]; draw(); });
    $$(".rb-act").forEach(box => { const a = spec.do[+box.dataset.i];
      box.querySelectorAll(".au-list input").forEach(cb => cb.onchange = () => { a.entities = picked(box); box.querySelector(".names").textContent = a.entities.length ? a.entities.map(nameOf).join(", ") : "Tap Pick to choose"; sum(); });
      box.querySelectorAll("[data-a]").forEach(el => el.onchange = el.oninput = () => { a[el.dataset.a] = el.type === "number" ? +el.value : el.value; if (["mode","white","until"].includes(el.dataset.a)) draw(); else sum(); });
      box.querySelectorAll("[data-ab]").forEach(el => el.onchange = () => { a[el.dataset.ab] = el.checked; sum(); });
      const cp = box.querySelector(".rb-color");
      if (cp && window.FHHome) FHHome.bindLightPanel(cp, {color: true, rgb: a.rgb}, d => { if (d.rgb_color){ a.rgb = d.rgb_color; sum(); } });
    });
  }
  function modeSummary(steps){
    return (steps || []).map(a => { const l = (a.entities || []).map(nameOf).join(", ") || "…";
      return ({on: `turn on ${l}${a.dark ? " (after dark)" : ""}`, off: `turn off ${l}`, dim: `set ${l} to ${a.pct || 50}%`, lock: `lock ${l}`, close: `close ${l}`,
        arm: `arm the alarm (${({stay: "Stay", away: "Away", night: "Night"})[a.arm || "stay"]})`, open_garage: "open the garage once disarmed",
        thermostat: a.mode === "off" ? `turn ${l} off` : `set ${l} to ${a.temp || "?"}°`, schedule: "thermostats back to the schedule",
        village: a.village === "wake" ? "wake the Christmas village" : "put the Christmas village to sleep", say: `say "${a.message || "…"}"`})[a.type] || a.type; }).join(" → ");
  }
  function drawMode(sh){
    sh.innerHTML = `<h3>${MODE_TITLE[houseMode]}<button data-x aria-label="Close">✕</button></h3>
      <div class="au-blurb">${houseMode === "welcome" ? (window.FH && FH.get().welcomeNoCode === true ? "First it disarms the alarm (one tap, no code). Then, in this order:" : "First it disarms the alarm with the code you type. Then, in this order:") : "When the button is tapped, in this order:"}</div>
      <div class="rb-step">${spec.do.map((a, i) => actUI(a, i).replace('<button data-rm=', `<button data-mv="${i}" data-d="-1" aria-label="Move up">↑</button><button data-mv="${i}" data-d="1" aria-label="Move down">↓</button><button data-rm=`)).join("")}
        <div class="rb-chips" style="margin-top:8px">${doList().map(([k,t]) => `<button data-add="${k}">＋ ${t}</button>`).join("")}</div></div>
      <div class="rb-sum" id="rb-sum">${esc(modeSummary(spec.do))}</div>
      <div class="rb-err" id="rb-err"></div>
      <div class="rb-btns"><button class="del" data-reset>Back to normal</button><button data-x>Cancel</button><button class="save" data-save>Save</button></div>`;
    const sum = () => { sh.querySelector("#rb-sum").textContent = modeSummary(spec.do); };
    sh.querySelectorAll("[data-x]").forEach(b => b.onclick = closeBuilder);
    sh.querySelectorAll("[data-add]").forEach(b => b.onclick = () => { spec.do.push({type: b.dataset.add, entities: [], mode: "keep", temp: 68, pct: 50, arm: "stay", village: "sleep"}); draw(); });
    bindSteps(sh, sum);
    sh.querySelector("[data-save]").onclick = async () => {
      const err = sh.querySelector("#rb-err"); err.textContent = "";
      const empty = spec.do.findIndex(a => ["on","off","dim","lock","close","thermostat"].includes(a.type) && !(a.entities || []).length);
      if (empty >= 0){
        const lab = ([...DO, ...MODE_DO].find(d => d[0] === spec.do[empty].type) || ["", "A step"])[1];
        err.textContent = `The "${lab}" step has nothing picked. Tap Pick on it and choose, or tap ✕ to remove that step.`;
        const box = sh.querySelector(`.rb-act[data-i="${empty}"]`);
        if (box){ box.style.outline = "2px solid #c0392b"; box.scrollIntoView({behavior: "smooth", block: "center"}); const d = box.querySelector("details"); if (d) d.open = true; }
        return;
      }
      const r = await post("/api/ha/modes/" + houseMode, {steps: spec.do});
      if (!r.ok){ err.textContent = r.reason || "Couldn’t save"; return; }
      closeBuilder(); say(`${MODE_TITLE[houseMode]} saved`); if (modeBox) houseModes(modeBox);
    };
    sh.querySelector("[data-reset]").onclick = async () => {
      if (!confirm("Put this button back to how it worked out of the box?")) return;
      await post("/api/ha/modes/" + houseMode, null, "DELETE"); closeBuilder(); say("Back to normal"); if (modeBox) houseModes(modeBox);
    };
  }
  let modeBox = null;
  async function houseModes(el){
    modeBox = el;
    if (!last){ try { last = await fetch("/api/ha/automations").then(r => r.json()); } catch(e){} }
    let d = {};
    try { d = await fetch("/api/ha/modes").then(r => r.json()); } catch(e){ el.textContent = "Couldn’t load the buttons."; return; }
    if (!styled){ const st = document.createElement("style"); st.textContent = css; document.head.appendChild(st); styled = true; }
    el.innerHTML = ["goodnight", "away", "welcome"].map(m => `<div class="ts-row"><div class="ts-t"><b>${MODE_TITLE[m]}</b>${d[m] && d[m].custom ? ' <span class="dim">· customized</span>' : ""}</div>
      <div class="ts-v">${esc(modeSummary((d[m] || {}).steps))}</div><button class="chg" data-hm="${m}">Edit steps</button></div>`).join("");
    el.querySelectorAll("[data-hm]").forEach(b => b.onclick = () => {
      houseMode = b.dataset.hm; editId = null;
      spec = {when: {type: "time"}, days: [], do: JSON.parse(JSON.stringify((d[houseMode] || {}).steps || []))};
      ensureSheet().classList.add("on"); draw();
    });
  }

  function openBuilder(id, s){
    houseMode = null;
    editId = id;
    spec = s ? JSON.parse(JSON.stringify(s)) : {name:"", when:{type:"time", at:"18:00"}, days:DAYS.map(d=>d[0]), dark:false, home:false, do:[]};
    if (spec.when.type === "sun") spec.when.type = spec.when.event === "sunset" ? "sunset" : "sunrise";
    ensureSheet().classList.add("on"); draw();
  }
  function whenUI(){
    const w = spec.when, ch = (last && last.choices) || {};
    if (w.type === "time") return `<div class="rb-row"><input type="time" data-w="at" value="${esc(w.at || "18:00")}"></div>`;
    if (w.type === "sunset" || w.type === "sunrise"){
      const opts = [[-60,"1 hour before"],[-30,"30 min before"],[-15,"15 min before"],[0,"Right at "+w.type],[15,"15 min after"],[30,"30 min after"],[60,"1 hour after"]];
      return `<div class="rb-row"><select data-w="offset">${opts.map(([v,t]) => `<option value="${v}" ${+(w.offset||0) === v ? "selected" : ""}>${t}</option>`).join("")}</select></div>`;
    }
    if (w.type === "device"){
      const all = [...(ch.sensors||[]).map(x=>({...x, d:x.kind})), ...(ch.locks||[]).map(x=>({...x, d:"lock"})), ...(ch.covers||[]).map(x=>({...x, d:"cover"}))];
      if (w.entity && !all.some(x => x.id === w.entity)) all.unshift({id: w.entity, name: nameOf(w.entity), d: /motion|occupancy|presence/.test(w.entity) ? "motion" : "door"});
      const cur = all.find(x => x.id === w.entity) || all[0];
      // grouped + labelled: "Front Door" the sensor vs the lock, motion vs camera detections
      const GRP = [["motion", "Motion sensors"], ["door", "Doors & windows (open / closed)"], ["lock", "Locks"], ["cover", "Garage doors"],
                   ["camera", "Camera detections (person, animal, vehicle, package)"], ["leak", "Water leak"]];
      const label = x => {
        let n = x.name.replace(/\s+occupancy$/i, " (stays on while someone's there)");
        if (x.area && !n.toLowerCase().includes(x.area.toLowerCase())) n += ` · ${x.area}`;
        if (x.d === "camera") n = n.replace(/^(.*?)\s+(person|animal|vehicle|package)\s+detected$/i, (m, cam, what) => `${cam} camera: ${what.toLowerCase()}`);
        return n;
      };
      const opts = GRP.map(([k, t]) => { const xs = all.filter(x => x.d === k); return xs.length ? `<optgroup label="${esc(t)}">${xs.map(x => `<option value="${esc(x.id)}" ${x.id === w.entity ? "selected" : ""}>${esc(label(x))}</option>`).join("")}</optgroup>` : ""; }).join("");
      if (cur && !w.entity) w.entity = cur.id;
      const tos = !cur ? [] : cur.d === "lock" ? [["unlocked","is unlocked"],["locked","is locked"]] : cur.d === "cover" ? [["open","opens"],["closed","closes"]]
        : cur.d === "motion" ? [["on","detects motion"],["off","goes quiet"]] : cur.d === "leak" ? [["on","detects water"]]
        : cur.d === "camera" ? [["on","sees it"]] : [["on","opens"],["off","closes"]];
      if (!tos.some(t => t[0] === w.to)) w.to = tos.length ? tos[0][0] : "on";
      return all.length ? `<div class="rb-row"><select data-w="entity">${opts}</select>
        <select data-w="to">${tos.map(([v,t]) => `<option value="${v}" ${w.to === v ? "selected" : ""}>${t}</option>`).join("")}</select></div>`
        + (w.to === "off" || w.to === "closed" ? `<div class="rb-row"><span>for</span><input type="number" min="0" max="240" data-w="for" value="${esc(w.for || 0)}" style="width:80px"><span>minutes (0 = right away)</span></div>` : "")
        : `<div class="hint">No doors or sensors found in Home Assistant.</div>`;
    }
    if (w.type === "arrive" || w.type === "leave"){
      const ppl = ch.people || [];
      return `<div class="rb-row"><select data-w="person"><option value="">${w.type === "arrive" ? "Anyone (the first one home)" : "Everyone (when the house is empty)"}</option>${ppl.map(p => `<option value="${esc(p.id)}" ${w.person === p.id ? "selected" : ""}>${esc(p.name)}</option>`).join("")}</select></div>`
        + (ppl.length ? "" : `<div class="hint">Uses the Home Assistant app's location on your phones.</div>`);
    }
    if (w.type === "alarm"){
      const o = [["armed_home","is armed Stay"],["armed_away","is armed Away"],["armed_night","is armed Night"],["disarmed","is disarmed"],["triggered","goes off"]];
      if (!w.to) w.to = "armed_home";
      return `<div class="rb-row"><span>When the alarm</span><select data-w="to">${o.map(([v,t]) => `<option value="${v}" ${w.to === v ? "selected" : ""}>${t}</option>`).join("")}</select></div>`;
    }
    return "";
  }
  function actUI(a, i){
    const ch = (last && last.choices) || {};
    const label = ([...DO, ...MODE_DO].find(d => d[0] === a.type) || ["", a.type])[1];
    const lists = {
      on: [["Lights", ch.lights], ["Plugs & switches", ch.switches], ["TVs", ch.media]],
      off: [["Lights", ch.lights], ["Plugs & switches", ch.switches], ["TVs", ch.media]],
      dim: [["Lights", ch.lights]], thermostat: [["Thermostats", ch.climates]], lock: [["Locks", ch.locks]], close: [["Garage doors", ch.covers]],
    }[a.type];
    if (lists && houseMode && GROUP_FOR[a.type]) lists.unshift(["Quick picks", GROUP_FOR[a.type].map(id => ({id, name: GROUP_NAMES[id], area: "Quick picks"}))]);
    let body = "";
    if (lists){
      a.entities = a.entities || [];
      body += `<div class="names">${a.entities.length ? esc(a.entities.map(nameOf).join(", ")) : "Tap Pick to choose"}</div>
        <details ${a.entities.length ? "" : "open"}><summary style="font-size:13px; cursor:pointer">Pick</summary>${checklist(lists.map(([t, it]) => [t, it || []]), a.entities)}</details>`;
    }
    if (a.type === "dim") body += `<div class="rb-row"><input type="number" min="1" max="100" data-a="pct" value="${esc(a.pct || 50)}" style="width:90px"> %
      <select data-a="white">${[["","as they are"],["warm","warm white"],["daylight","daylight"],["cool","cool white"],["color","a color…"]].map(([v,t]) => `<option value="${v}" ${(a.white || "") === v ? "selected" : ""}>${t}</option>`).join("")}</select></div>`
      + (a.white === "color" && window.FHHome ? `<div class="rb-color">${FHHome.lightPanelHTML({color: true, whites: false, rgb: a.rgb}, {dim: false})}</div>` : "");
    if (a.type === "thermostat") body += `<div class="rb-row"><select data-a="mode">${[...(houseMode ? [["keep","Keep its mode"]] : []), ["heat","Heat"],["cool","Cool"],["heat_cool","Heat/Cool"],["auto","Auto"],["off","Off"]].map(([v,t]) => `<option value="${v}" ${a.mode === v ? "selected" : ""}>${t}</option>`).join("")}</select>
      ${a.mode === "heat" || a.mode === "cool" || !a.mode || a.mode === "keep" ? `<input type="number" min="45" max="95" data-a="temp" value="${esc(a.temp || 68)}" style="width:90px"> °` : ""}</div>`;
    if (a.type === "on" && houseMode) body += `<label class="rb-chk"><input type="checkbox" data-ab="dark" ${a.dark ? "checked" : ""}> Only after dark</label>`;
    if (a.type === "arm") body += `<div class="rb-row"><select data-a="arm">${[["stay","Stay (dogs can roam)"],["away","Away"],["night","Night"]].map(([v,t]) => `<option value="${v}" ${(a.arm || "stay") === v ? "selected" : ""}>${t}</option>`).join("")}</select></div>`
      + (houseMode === "away" ? `<div class="hint" style="margin:4px 0 0">Won't arm if a door or window is open; it tells you which.</div>` : "");
    if (a.type === "open_garage") body += `<div class="hint" style="margin:0">Only once the alarm is disarmed (if it didn't disarm, the garage stays shut).</div>`;
    if (a.type === "schedule") body += `<div class="hint" style="margin:0">Sets both thermostats to whatever the schedule says right now (skipped during peak).</div>`;
    if (a.type === "village") body += `<div class="rb-row"><select data-a="village">${[["sleep","Put it to sleep for the night"],["wake","Wake it up"]].map(([v,t]) => `<option value="${v}" ${(a.village || "sleep") === v ? "selected" : ""}>${t}</option>`).join("")}</select></div>`;
    if (a.type === "wait"){
      const u = a.until || "minutes", motion = (ch.sensors || []).filter(x => x.kind === "motion");
      body += `<div class="rb-row"><select data-a="until">${[["minutes","a number of minutes"],["time","until a time"],["sunrise","until sunrise"],["sunset","until sunset"],["quiet","until the motion is quiet"]].map(([v,t]) => `<option value="${v}" ${u === v ? "selected" : ""}>${t}</option>`).join("")}</select></div>`;
      if (u === "minutes") body += `<div class="rb-row"><input type="number" min="1" max="720" data-a="minutes" value="${esc(a.minutes || 5)}" style="width:90px"> minutes</div>`;
      if (u === "time") body += `<div class="rb-row"><input type="time" data-a="at" value="${esc(a.at || "23:00")}"></div>`;
      if (u === "quiet") body += `<div class="rb-row"><select data-a="entity">${motion.map(x => `<option value="${esc(x.id)}" ${a.entity === x.id ? "selected" : ""}>${esc(x.name)}${x.area && !x.name.includes(x.area) ? " · " + esc(x.area) : ""}</option>`).join("")}</select></div>
        <div class="rb-row">for <input type="number" min="1" max="240" data-a="minutes" value="${esc(a.minutes || 10)}" style="width:80px"> minutes</div>`;
      body += `<div class="hint" style="margin:4px 0 0">Then add what happens after, e.g. Turn off.</div>`;
    }
    if (a.type === "notify" || a.type === "say") body += `<div class="rb-row"><input type="text" data-a="message" maxlength="200" placeholder="${a.type === "say" ? "e.g. Time to take the dogs out" : "e.g. The garage door opened"}" value="${esc(a.message || "")}"></div>`;
    return `<div class="rb-act" data-i="${i}"><div class="hd"><span>${esc(label)}</span><button data-rm="${i}" aria-label="Remove">✕</button></div>${body}</div>`;
  }
  const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  function mdUI(k){
    const v = (spec.dates && spec.dates[k]) || (k === "from" ? "11-27" : "01-06"), m = +v.slice(0, 2), d = +v.slice(3, 5);
    return `<select data-md="${k}" data-part="m">${MONTHS.map((t, i) => `<option value="${i + 1}" ${m === i + 1 ? "selected" : ""}>${t}</option>`).join("")}</select>
      <input type="number" min="1" max="31" data-md="${k}" data-part="d" value="${d}" style="width:64px">`;
  }
  function toSpec(){            // builder state -> what the server expects
    const s = JSON.parse(JSON.stringify(spec)), w = s.when;
    if (w.type === "sunset" || w.type === "sunrise"){ s.when = {type:"sun", event:w.type, offset:+(w.offset || 0)}; }
    return s;
  }
  function summaryText(){
    const w = spec.when, nm = nameOf;
    let t = w.type === "time" ? `At ${w.at || "?"}` : (w.type === "sunset" || w.type === "sunrise") ? (+(w.offset||0) ? `${Math.abs(w.offset)} min ${w.offset < 0 ? "before" : "after"} ${w.type}` : `At ${w.type}`)
      : w.type === "device" ? `When ${nm(w.entity)} ${(/motion|occupancy|presence/.test(w.entity || "") ? {on:"detects motion", off:"goes quiet"} : {on:"opens", off:"closes"})[w.to] || ({open:"opens", closed:"closes", unlocked:"is unlocked", locked:"is locked"})[w.to] || w.to}`
      : w.type === "arrive" ? (w.person ? `When ${nm(w.person)} gets home` : "When the first person gets home")
      : w.type === "leave" ? (w.person ? `When ${nm(w.person)} leaves` : "When everyone has left") : `When the alarm ${({armed_home:"is armed Stay", armed_away:"is armed Away", armed_night:"is armed Night", disarmed:"is disarmed", triggered:"goes off"})[w.to] || "changes"}`;
    const d = spec.days || [];
    if (d.length && d.length < 7) t += d.join() === "mon,tue,wed,thu,fri" ? " on weekdays" : d.join() === "sat,sun" ? " on weekends" : " on " + d.map(x => x[0].toUpperCase() + x.slice(1, 3)).join(", ");
    if (w.type === "device" && +(w.for || 0) && (w.to === "off" || w.to === "closed")) t += ` for ${w.for} min`;
    const md = v => { const m = +String(v || "").slice(0, 2), d = +String(v || "").slice(3, 5); return m ? `${MONTHS[m - 1]} ${d}` : "?"; };
    if (spec.between) t += `, only between ${spec.between.after || "?"} and ${spec.between.before || "?"}`;
    if (spec.dates) t += `, ${spec.dates_except ? "except" : "only"} ${md(spec.dates.from)} to ${md(spec.dates.to)}`;
    if (spec.dark) t += ", only after dark"; if (spec.home) t += ", only if someone's home"; if (spec.ifoff) t += ", only if those lights are off";
    const acts = spec.do.map(a => { const l = (a.entities || []).map(nm).join(", ") || "…";
      return ({on:`turn on ${l}`, off:`turn off ${l}`, dim:`set ${l} to ${a.pct || 50}%${a.white === "color" ? (a.rgb ? " in rgb(" + a.rgb.join(",") + ")" : " in a color") : a.white === "daylight" ? " daylight" : a.white ? " " + a.white + " white" : ""}`, thermostat:`set ${l} to ${a.mode === "off" ? "off" : (a.mode || "heat").replace("_","/") + (a.mode === "heat" || a.mode === "cool" || !a.mode ? " " + (a.temp || 68) + "°" : "")}`,
        lock:`lock ${l}`, close:`close ${l}`, notify:`send our phones "${a.message || "…"}"`, say:`say on the wall "${a.message || "…"}"`,
        wait: (a.until || "minutes") === "minutes" ? `wait ${a.minutes || 5} min` : a.until === "time" ? `wait until ${a.at || "?"}` : a.until === "quiet" ? `wait until ${nm(a.entity)} is quiet ${a.minutes || 10} min` : `wait until ${a.until}`})[a.type]; });
    return t + " → " + (acts.length ? acts.join("; ") : "add something to do");
  }
  function draw(){
    const sh = document.getElementById("au-sheet");
    const w = spec.when;
    if (houseMode) return drawMode(sh);
    sh.innerHTML = `<h3>${editId ? "Edit routine" : "New routine"}<button data-x aria-label="Close">✕</button></h3>
      <div class="rb-step"><div class="rb-lab">1 · When</div><div class="rb-chips">${WHEN.map(([k,t]) => `<button data-when="${k}" class="${w.type === k ? "on" : ""}">${t}</button>`).join("")}</div>${whenUI()}</div>
      <div class="rb-step"><div class="rb-lab">2 · Which days</div><div class="rb-chips">${DAYS.map(([k,t]) => `<button data-day="${k}" class="${spec.days.includes(k) ? "on" : ""}" style="width:42px; padding:9px 0">${t}</button>`).join("")}</div>
        <div class="rb-chips" style="margin-top:6px"><button data-days="all">Every day</button><button data-days="wk">Weekdays</button><button data-days="we">Weekends</button></div></div>
      <div class="rb-step"><div class="rb-lab">3 · Only if (optional)</div>
        <label class="rb-chk"><input type="checkbox" data-flag="dark" ${spec.dark ? "checked" : ""}> It's dark out</label>
        <label class="rb-chk"><input type="checkbox" data-flag="home" ${spec.home ? "checked" : ""}> Someone's home</label>
        <label class="rb-chk"><input type="checkbox" data-opt="between" ${spec.between ? "checked" : ""}> Between certain times</label>
        ${spec.between ? `<div class="rb-row"><input type="time" data-b="after" value="${esc(spec.between.after || "20:00")}"><span>and</span><input type="time" data-b="before" value="${esc(spec.between.before || "08:00")}"></div>` : ""}
        <label class="rb-chk"><input type="checkbox" data-opt="dates" ${spec.dates ? "checked" : ""}> Certain dates of the year (holidays)</label>
        ${spec.dates ? `<div class="rb-row"><select data-dx>${[["only","Only"],["except","Except"]].map(([v,t]) => `<option value="${v}" ${(spec.dates_except ? "except" : "only") === v ? "selected" : ""}>${t}</option>`).join("")}</select>${mdUI("from")}<span>to</span>${mdUI("to")}</div>` : ""}
        <label class="rb-chk"><input type="checkbox" data-flag="ifoff" ${spec.ifoff ? "checked" : ""}> The lights it turns on are off (don't change them if someone set them)</label></div>
      <div class="rb-step"><div class="rb-lab">4 · Then do this</div>${spec.do.map(actUI).join("")}
        <div class="rb-chips" style="margin-top:8px">${doList().map(([k,t]) => `<button data-add="${k}">＋ ${t}</button>`).join("")}</div></div>
      <div class="rb-step"><div class="rb-lab">Name (optional)</div><input type="text" data-name maxlength="80" placeholder="e.g. Porch light when we get home" value="${esc(spec.name || "")}"></div>
      <div class="rb-sum" id="rb-sum">${esc(summaryText())}</div>
      <div class="rb-err" id="rb-err"></div>
      <div class="rb-btns">${editId ? `<button class="del" data-del>Delete</button>` : ""}<button data-x>Cancel</button><button class="save" data-save>Save routine</button></div>`;
    const $$ = q => sh.querySelectorAll(q), sum = () => { sh.querySelector("#rb-sum").textContent = summaryText(); };
    $$("[data-x]").forEach(b => b.onclick = closeBuilder);
    $$("[data-when]").forEach(b => b.onclick = () => { const k = b.dataset.when; spec.when = k === "time" ? {type:"time", at:"18:00"} : {type:k, offset:0}; draw(); });
    $$("[data-w]").forEach(el => el.onchange = el.oninput = () => { spec.when[el.dataset.w] = (el.dataset.w === "offset" || el.dataset.w === "for") ? +el.value : el.value; if (el.dataset.w === "entity" || (el.dataset.w === "to" && el.tagName === "SELECT")){ if (el.dataset.w === "entity") spec.when.to = null; draw(); } else sum(); });
    $$("[data-day]").forEach(b => b.onclick = () => { const k = b.dataset.day; spec.days = spec.days.includes(k) ? spec.days.filter(x => x !== k) : DAYS.map(d => d[0]).filter(d => d === k || spec.days.includes(d)); draw(); });
    $$("[data-days]").forEach(b => b.onclick = () => { spec.days = {all:DAYS.map(d=>d[0]), wk:["mon","tue","wed","thu","fri"], we:["sat","sun"]}[b.dataset.days]; draw(); });
    $$("[data-flag]").forEach(el => el.onchange = () => { spec[el.dataset.flag] = el.checked; sum(); });
    $$("[data-opt]").forEach(el => el.onchange = () => { const k = el.dataset.opt;
      if (!el.checked){ delete spec[k]; if (k === "dates") delete spec.dates_except; }
      else spec[k] = k === "between" ? {after:"20:00", before:"08:00"} : {from:"11-27", to:"01-06"};
      draw(); });
    $$("[data-b]").forEach(el => el.onchange = el.oninput = () => { spec.between[el.dataset.b] = el.value; sum(); });
    $$("[data-dx]").forEach(el => el.onchange = () => { spec.dates_except = el.value === "except"; sum(); });
    $$("[data-md]").forEach(el => el.onchange = el.oninput = () => { const k = el.dataset.md, row = el.parentNode;
      const m = +row.querySelector(`[data-md="${k}"][data-part="m"]`).value, d = Math.max(1, Math.min(31, +row.querySelector(`[data-md="${k}"][data-part="d"]`).value || 1));
      spec.dates[k] = String(m).padStart(2, "0") + "-" + String(d).padStart(2, "0"); sum(); });
    $$("[data-add]").forEach(b => b.onclick = () => {
      const k = b.dataset.add, step = {type:k, entities:[], mode:"heat", temp:68, pct:50};
      if (k === "off" && spec.do.some(a => a.type === "wait"))
        step.entities = [...new Set(spec.do.filter(a => a.type === "on" || a.type === "dim").flatMap(a => a.entities || []))];
      if (k === "wait"){ step.until = "minutes"; step.minutes = 5;
        const m = (((last && last.choices) || {}).sensors || []).find(x => x.kind === "motion"); if (m) step.entity = spec.when.type === "device" && spec.when.entity ? spec.when.entity : m.id; }
      spec.do.push(step); draw(); });
    $$("[data-rm]").forEach(b => b.onclick = () => { spec.do.splice(+b.dataset.rm, 1); draw(); });
    $$(".rb-act").forEach(box => { const a = spec.do[+box.dataset.i];
      box.querySelectorAll(".au-list input").forEach(cb => cb.onchange = () => { a.entities = picked(box); box.querySelector(".names").textContent = a.entities.length ? a.entities.map(nameOf).join(", ") : "Tap Pick to choose"; sum(); });
      box.querySelectorAll("[data-a]").forEach(el => el.onchange = el.oninput = () => { a[el.dataset.a] = el.type === "number" ? +el.value : el.value; if (el.dataset.a === "mode" || el.dataset.a === "white" || el.dataset.a === "until") draw(); else sum(); });
      const cp = box.querySelector(".rb-color");
      if (cp && window.FHHome) FHHome.bindLightPanel(cp, {color: true, rgb: a.rgb}, d => { if (d.rgb_color){ a.rgb = d.rgb_color; sum(); } });
    });
    const nm = sh.querySelector("[data-name]"); nm.oninput = () => { spec.name = nm.value; };
    sh.querySelector("[data-save]").onclick = async () => {
      const err = sh.querySelector("#rb-err"); err.textContent = "";
      if (!spec.do.length){ err.textContent = "Add at least one thing for it to do (step 4)."; return; }
      const empty = spec.do.findIndex(a => ["on","off","dim","thermostat","lock","close"].includes(a.type) && !(a.entities || []).length);
      if (empty >= 0){
        const lab = (DO.find(d => d[0] === spec.do[empty].type) || ["", "A step"])[1];
        err.textContent = `The "${lab}" step has nothing picked. Tap Pick on it and choose, or tap ✕ to remove that step.`;
        const box = sh.querySelector(`.rb-act[data-i="${empty}"]`);
        if (box){ box.style.outline = "2px solid #c0392b"; box.scrollIntoView({behavior: "smooth", block: "center"}); const d = box.querySelector("details"); if (d) d.open = true; }
        return;
      }
      if (!spec.days.length){ err.textContent = "Pick at least one day."; return; }
      const r = await post("/api/ha/automations/routine", {id: editId, spec: toSpec()});
      if (!r.ok){ err.textContent = r.reason || "Couldn’t save"; return; }
      closeBuilder(); say(editId ? "Routine updated" : "Routine saved — it's live"); setTimeout(() => load(lastBox, lastToast), 1200);
    };
    const del = sh.querySelector("[data-del]");
    if (del) del.onclick = async () => {
      if (!confirm("Delete this routine?")) return;
      const r = await post("/api/ha/automations/routine/" + encodeURIComponent(editId), null, "DELETE");
      if (!r.ok){ sh.querySelector("#rb-err").textContent = r.reason || "Couldn’t delete"; return; }
      closeBuilder(); say("Routine deleted"); setTimeout(() => load(lastBox, lastToast), 800);
    };
  }

  async function load(box, toast){
    if (!box) return;
    try { render(box, await fetch("/api/ha/automations").then(r => r.json()), toast); }
    catch(e){ box.innerHTML = '<div class="hint">Couldn’t load the routines.</div>'; }
  }
  window.FHAutomations = { load, render, openBuilder, houseModes };
})();
