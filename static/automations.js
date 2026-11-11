/* Automations card: every Home Assistant routine in plain English, with on/off switches, when it last
   ran, the settings you can change (times, temperatures, which lights), and a simple "New routine"
   builder. Used by phone Settings (and the wall's Settings > Everything tab, which embeds the phone page).
   Data: GET /api/ha/automations. */
(function(){
  const css = `
  .au-group{border-top:1px solid var(--line); padding:12px 0 4px}
  .au-group:first-child{border-top:0; padding-top:2px}
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
    return `<div class="au-list">` + groups.filter(g => g[1].length).map(([t, items]) =>
      `<div class="grp">${esc(t)}</div>` + items.map(i => `<label><input type="checkbox" value="${esc(i.id)}" ${chosen.includes(i.id) ? "checked" : ""}>${esc(i.name)}</label>`).join("")
    ).join("") + `</div>`;
  }
  const picked = el => [...el.querySelectorAll(".au-list input:checked")].map(i => i.value);
  const nameOf = (id) => { const c = (last && last.choices) || {}; for (const k in c) { const f = c[k].find(x => x.id === id); if (f) return f.name; } return id; };

  function render(box, data, toast){
    if (!styled){ const s = document.createElement("style"); s.textContent = css; document.head.appendChild(s); styled = true; }
    last = data; lastBox = box; lastToast = toast;
    if (!data || !data.connected){ box.innerHTML = '<div class="hint">Home Assistant isn’t reachable, so the routines can’t be shown right now.</div>'; return; }
    const ch = data.choices || {};
    let html = "";
    // ---- your own routines first ----
    html += `<div class="au-group"><div class="au-h"><b>Your routines</b></div>
      <div class="au-blurb">Make your own: pick when, then what happens. No code, saved straight into Home Assistant.</div>`;
    (data.mine || []).forEach(a => {
      html += `<div class="au-row"><div class="t"><div class="n">${esc(a.name)}</div><div class="d">${esc(a.about)}</div><div class="l">${esc(ago(a.last))}</div></div>
        ${a.editable !== false ? `<button class="ed" data-edit="${esc(a.id)}">Edit</button>` : ""}${sw(`data-auto="${esc(a.entity_id)}" aria-label="${esc(a.name)}"`, a.on)}</div>`;
    });
    html += `<button class="au-new" data-new>＋ New routine</button></div>`;
    // ---- built-in groups ----
    (data.groups || []).forEach(g => {
      const allOn = g.automations.length && g.automations.every(a => a.on);
      html += `<div class="au-group"><div class="au-h"><b>${esc(g.title)}</b>${g.automations.length ? sw(`data-group="${g.key}" aria-label="All of ${esc(g.title)}"`, allOn) : ""}</div>`;
      html += `<div class="au-blurb">${esc(g.blurb)}</div>`;
      if (!g.installed && g.key !== "other") html += `<div class="au-missing">Not installed in Home Assistant yet: add <code>docs/ha/${esc(g.file || g.key)}.yaml</code> to the packages folder.</div>`;
      if (g.status.length) html += `<div class="au-chips">${g.status.map(s => `<span class="au-chip ${s.on ? "on" : ""}">${esc(s.name)}: ${s.on ? "yes" : "no"}</span>`).join("")}</div>`;
      if (g.settings.length){
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
        html += `<details class="au-more"><summary>${g.automations.length} step${g.automations.length === 1 ? "" : "s"} — what each one does</summary>`;
        g.automations.forEach(a => {
          html += `<div class="au-row"><div class="t"><div class="n">${esc(a.name)}</div>${a.about ? `<div class="d">${esc(a.about)}</div>` : ""}<div class="l">${esc(ago(a.last))}</div></div>${sw(`data-auto="${esc(a.entity_id)}" aria-label="${esc(a.name)}"`, a.on)}</div>`;
        });
        html += `</details>`;
      }
      html += `</div>`;
    });
    if (!(data.fh_ids || []).length && (data.groups || []).some(g => !g.installed && g.key !== "other"))
      html += `<div class="au-note">Home Assistant reports <b>${data.ha_total ?? 0}</b> automation${data.ha_total === 1 ? "" : "s"} and <b>${data.helpers_found ?? 0}</b> FamilyHub setting${data.helpers_found === 1 ? "" : "s"}. 0 settings means Home Assistant hasn't loaded the packages folder.</div>`;
    html += `<div class="au-note">Changes take effect right away and stay after Home Assistant restarts. Turning a routine off pauses it until you turn it back on.</div>`;
    box.innerHTML = html;

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
      if (r.ok) setTimeout(() => load(box, toast), 800);        // descriptions show the new value
    });
    // light lists: Change -> checklist of lights + plugs, Done saves
    box.querySelectorAll("[data-pick]").forEach(p => {
      const s = data.groups.flatMap(g => g.settings).find(x => x.entity_id === p.dataset.pick);
      const btn = p.querySelector(".chg");
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
  const DO = [["on","Turn on"],["off","Turn off"],["dim","Dim lights to…"],["thermostat","Thermostat"],["lock","Lock doors"],["close","Close garage"],["notify","Notify our phones"],["say","Say it on the wall"]];
  const DAYS = [["mon","M"],["tue","T"],["wed","W"],["thu","T"],["fri","F"],["sat","S"],["sun","S"]];
  let spec = null, editId = null;

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
  function openBuilder(id, s){
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
      const cur = all.find(x => x.id === w.entity) || all[0];
      if (cur && !w.entity) w.entity = cur.id;
      const tos = !cur ? [] : cur.d === "lock" ? [["unlocked","is unlocked"],["locked","is locked"]] : cur.d === "cover" ? [["open","opens"],["closed","closes"]]
        : cur.d === "motion" ? [["on","detects motion"],["off","goes quiet"]] : cur.d === "leak" ? [["on","detects water"]] : [["on","opens"],["off","closes"]];
      if (!tos.some(t => t[0] === w.to)) w.to = tos.length ? tos[0][0] : "on";
      return all.length ? `<div class="rb-row"><select data-w="entity">${all.map(x => `<option value="${esc(x.id)}" ${x.id === w.entity ? "selected" : ""}>${esc(x.name)}</option>`).join("")}</select>
        <select data-w="to">${tos.map(([v,t]) => `<option value="${v}" ${w.to === v ? "selected" : ""}>${t}</option>`).join("")}</select></div>` : `<div class="hint">No doors or sensors found in Home Assistant.</div>`;
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
    const label = (DO.find(d => d[0] === a.type) || ["", a.type])[1];
    const lists = {
      on: [["Lights", ch.lights], ["Plugs & switches", ch.switches], ["TVs", ch.media]],
      off: [["Lights", ch.lights], ["Plugs & switches", ch.switches], ["TVs", ch.media]],
      dim: [["Lights", ch.lights]], thermostat: [["Thermostats", ch.climates]], lock: [["Locks", ch.locks]], close: [["Garage doors", ch.covers]],
    }[a.type];
    let body = "";
    if (lists){
      a.entities = a.entities || [];
      body += `<div class="names">${a.entities.length ? esc(a.entities.map(nameOf).join(", ")) : "Tap Pick to choose"}</div>
        <details ${a.entities.length ? "" : "open"}><summary style="font-size:13px; cursor:pointer">Pick</summary>${checklist(lists.map(([t, it]) => [t, it || []]), a.entities)}</details>`;
    }
    if (a.type === "dim") body += `<div class="rb-row"><input type="number" min="1" max="100" data-a="pct" value="${esc(a.pct || 50)}" style="width:90px"> %</div>`;
    if (a.type === "thermostat") body += `<div class="rb-row"><select data-a="mode">${[["heat","Heat"],["cool","Cool"],["heat_cool","Heat/Cool"],["auto","Auto"],["off","Off"]].map(([v,t]) => `<option value="${v}" ${a.mode === v ? "selected" : ""}>${t}</option>`).join("")}</select>
      ${a.mode === "heat" || a.mode === "cool" || !a.mode ? `<input type="number" min="45" max="95" data-a="temp" value="${esc(a.temp || 68)}" style="width:90px"> °` : ""}</div>`;
    if (a.type === "notify" || a.type === "say") body += `<div class="rb-row"><input type="text" data-a="message" maxlength="200" placeholder="${a.type === "say" ? "e.g. Time to take the dogs out" : "e.g. The garage door opened"}" value="${esc(a.message || "")}"></div>`;
    return `<div class="rb-act" data-i="${i}"><div class="hd"><span>${esc(label)}</span><button data-rm="${i}" aria-label="Remove">✕</button></div>${body}</div>`;
  }
  function toSpec(){            // builder state -> what the server expects
    const s = JSON.parse(JSON.stringify(spec)), w = s.when;
    if (w.type === "sunset" || w.type === "sunrise"){ s.when = {type:"sun", event:w.type, offset:+(w.offset || 0)}; }
    return s;
  }
  function summaryText(){
    const w = spec.when, nm = nameOf;
    let t = w.type === "time" ? `At ${w.at || "?"}` : (w.type === "sunset" || w.type === "sunrise") ? (+(w.offset||0) ? `${Math.abs(w.offset)} min ${w.offset < 0 ? "before" : "after"} ${w.type}` : `At ${w.type}`)
      : w.type === "device" ? `When ${nm(w.entity)} ${({on:"opens / detects motion", off:"closes / goes quiet", open:"opens", closed:"closes", unlocked:"is unlocked", locked:"is locked"})[w.to] || w.to}`
      : w.type === "arrive" ? (w.person ? `When ${nm(w.person)} gets home` : "When the first person gets home")
      : w.type === "leave" ? (w.person ? `When ${nm(w.person)} leaves` : "When everyone has left") : `When the alarm ${({armed_home:"is armed Stay", armed_away:"is armed Away", armed_night:"is armed Night", disarmed:"is disarmed", triggered:"goes off"})[w.to] || "changes"}`;
    const d = spec.days || [];
    if (d.length && d.length < 7) t += d.join() === "mon,tue,wed,thu,fri" ? " on weekdays" : d.join() === "sat,sun" ? " on weekends" : " on " + d.map(x => x[0].toUpperCase() + x.slice(1, 3)).join(", ");
    if (spec.dark) t += ", only after dark"; if (spec.home) t += ", only if someone's home";
    const acts = spec.do.map(a => { const l = (a.entities || []).map(nm).join(", ") || "…";
      return ({on:`turn on ${l}`, off:`turn off ${l}`, dim:`set ${l} to ${a.pct || 50}%`, thermostat:`set ${l} to ${a.mode === "off" ? "off" : (a.mode || "heat").replace("_","/") + (a.mode === "heat" || a.mode === "cool" || !a.mode ? " " + (a.temp || 68) + "°" : "")}`,
        lock:`lock ${l}`, close:`close ${l}`, notify:`send our phones "${a.message || "…"}"`, say:`say on the wall "${a.message || "…"}"`})[a.type]; });
    return t + " → " + (acts.length ? acts.join("; ") : "add something to do");
  }
  function draw(){
    const sh = document.getElementById("au-sheet");
    const w = spec.when;
    sh.innerHTML = `<h3>${editId ? "Edit routine" : "New routine"}<button data-x aria-label="Close">✕</button></h3>
      <div class="rb-step"><div class="rb-lab">1 · When</div><div class="rb-chips">${WHEN.map(([k,t]) => `<button data-when="${k}" class="${w.type === k ? "on" : ""}">${t}</button>`).join("")}</div>${whenUI()}</div>
      <div class="rb-step"><div class="rb-lab">2 · Which days</div><div class="rb-chips">${DAYS.map(([k,t]) => `<button data-day="${k}" class="${spec.days.includes(k) ? "on" : ""}" style="width:42px; padding:9px 0">${t}</button>`).join("")}</div>
        <div class="rb-chips" style="margin-top:6px"><button data-days="all">Every day</button><button data-days="wk">Weekdays</button><button data-days="we">Weekends</button></div></div>
      <div class="rb-step"><div class="rb-lab">3 · Only if (optional)</div>
        <label class="rb-chk"><input type="checkbox" data-flag="dark" ${spec.dark ? "checked" : ""}> It's dark out</label>
        <label class="rb-chk"><input type="checkbox" data-flag="home" ${spec.home ? "checked" : ""}> Someone's home</label></div>
      <div class="rb-step"><div class="rb-lab">4 · Then do this</div>${spec.do.map(actUI).join("")}
        <div class="rb-chips" style="margin-top:8px">${DO.map(([k,t]) => `<button data-add="${k}">＋ ${t}</button>`).join("")}</div></div>
      <div class="rb-step"><div class="rb-lab">Name (optional)</div><input type="text" data-name maxlength="80" placeholder="e.g. Porch light when we get home" value="${esc(spec.name || "")}"></div>
      <div class="rb-sum" id="rb-sum">${esc(summaryText())}</div>
      <div class="rb-err" id="rb-err"></div>
      <div class="rb-btns">${editId ? `<button class="del" data-del>Delete</button>` : ""}<button data-x>Cancel</button><button class="save" data-save>Save routine</button></div>`;
    const $$ = q => sh.querySelectorAll(q), sum = () => { sh.querySelector("#rb-sum").textContent = summaryText(); };
    $$("[data-x]").forEach(b => b.onclick = closeBuilder);
    $$("[data-when]").forEach(b => b.onclick = () => { const k = b.dataset.when; spec.when = k === "time" ? {type:"time", at:"18:00"} : {type:k, offset:0}; draw(); });
    $$("[data-w]").forEach(el => el.onchange = el.oninput = () => { spec.when[el.dataset.w] = el.dataset.w === "offset" ? +el.value : el.value; if (el.dataset.w === "entity"){ spec.when.to = null; draw(); } else sum(); });
    $$("[data-day]").forEach(b => b.onclick = () => { const k = b.dataset.day; spec.days = spec.days.includes(k) ? spec.days.filter(x => x !== k) : DAYS.map(d => d[0]).filter(d => d === k || spec.days.includes(d)); draw(); });
    $$("[data-days]").forEach(b => b.onclick = () => { spec.days = {all:DAYS.map(d=>d[0]), wk:["mon","tue","wed","thu","fri"], we:["sat","sun"]}[b.dataset.days]; draw(); });
    $$("[data-flag]").forEach(el => el.onchange = () => { spec[el.dataset.flag] = el.checked; sum(); });
    $$("[data-add]").forEach(b => b.onclick = () => { spec.do.push({type:b.dataset.add, entities:[], mode:"heat", temp:68, pct:50}); draw(); });
    $$("[data-rm]").forEach(b => b.onclick = () => { spec.do.splice(+b.dataset.rm, 1); draw(); });
    $$(".rb-act").forEach(box => { const a = spec.do[+box.dataset.i];
      box.querySelectorAll(".au-list input").forEach(cb => cb.onchange = () => { a.entities = picked(box); box.querySelector(".names").textContent = a.entities.length ? a.entities.map(nameOf).join(", ") : "Tap Pick to choose"; sum(); });
      box.querySelectorAll("[data-a]").forEach(el => el.onchange = el.oninput = () => { a[el.dataset.a] = el.type === "number" ? +el.value : el.value; if (el.dataset.a === "mode") draw(); else sum(); });
    });
    const nm = sh.querySelector("[data-name]"); nm.oninput = () => { spec.name = nm.value; };
    sh.querySelector("[data-save]").onclick = async () => {
      const err = sh.querySelector("#rb-err"); err.textContent = "";
      if (!spec.do.length){ err.textContent = "Add at least one thing for it to do (step 4)."; return; }
      if (spec.do.some(a => ["on","off","dim","thermostat","lock","close"].includes(a.type) && !(a.entities || []).length)){ err.textContent = "Pick the devices for each step in 4."; return; }
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
  window.FHAutomations = { load, render, openBuilder };
})();
