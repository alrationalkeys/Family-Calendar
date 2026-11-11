/* Automations card: every Home Assistant routine in plain English, with on/off switches, when it last
   ran, and the times/temperatures you can change. Used by phone Settings (and the wall's Settings >
   Everything tab, which embeds the phone page). Data: GET /api/ha/automations. */
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
  .au-set input[type=time], .au-set input[type=number]{width:auto; max-width:120px; margin:0; padding:6px 8px; font:inherit; font-size:14px;
    background:var(--panel2); color:var(--ink); border:1px solid var(--line); border-radius:8px}
  .au-sub{font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:var(--ink-dim); margin:10px 0 2px; font-weight:700}
  .au-missing{font-size:13px; color:var(--ink-dim); background:var(--panel2); border-radius:10px; padding:8px 10px; margin:4px 0 8px}
  details.au-more summary{font-size:13px; color:var(--ink-dim); cursor:pointer; padding:4px 0}`;
  let styled = false;
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  function ago(iso){
    if (!iso) return "hasn't run yet";
    const d = new Date(iso); if (isNaN(d)) return "";
    const t = d.toLocaleTimeString([], {hour:"numeric", minute:"2-digit"});
    const days = Math.floor((new Date().setHours(0,0,0,0) - new Date(d).setHours(0,0,0,0)) / 86400000);
    return "last ran " + (days === 0 ? `today ${t}` : days === 1 ? `yesterday ${t}` : d.toLocaleDateString([], {month:"short", day:"numeric"}) + " " + t);
  }
  const sw = (attrs, on) => `<label class="au-sw"><input type="checkbox" ${attrs} ${on ? "checked" : ""}><span></span></label>`;

  async function post(url, body){
    const h = {"Content-Type":"application/json"};
    const r = await fetch(url, {method:"POST", headers:h, body:JSON.stringify(body)});
    return r.ok ? r.json() : {ok:false};
  }

  function render(box, data, toast){
    if (!styled){ const s = document.createElement("style"); s.textContent = css; document.head.appendChild(s); styled = true; }
    if (!data || !data.connected){ box.innerHTML = '<div class="hint">Home Assistant isn’t reachable, so the routines can’t be shown right now.</div>'; return; }
    let html = "";
    (data.groups || []).forEach(g => {
      const allOn = g.automations.length && g.automations.every(a => a.on);
      html += `<div class="au-group"><div class="au-h"><b>${esc(g.title)}</b>${g.automations.length ? sw(`data-group="${g.key}" aria-label="All of ${esc(g.title)}"`, allOn) : ""}</div>`;
      html += `<div class="au-blurb">${esc(g.blurb)}</div>`;
      if (!g.installed && g.key !== "other") html += `<div class="au-missing">Not installed in Home Assistant yet: add <code>docs/ha/${g.key === "peak" ? "peak_thermostat" : g.key === "outdoor" ? "outdoor_lights" : "kitchen_lights"}.yaml</code> to the packages folder.</div>`;
      if (g.status.length) html += `<div class="au-chips">${g.status.map(s => `<span class="au-chip ${s.on ? "on" : ""}">${esc(s.name)}: ${s.on ? "yes" : "no"}</span>`).join("")}</div>`;
      if (g.settings.length){
        html += `<div class="au-sub">Settings</div>`;
        g.settings.forEach(s => {
          const id = "au-" + s.entity_id.replace(/\W/g, "_");
          let ctl = "";
          if (s.kind === "time") ctl = `<input type="time" id="${id}" data-helper="${esc(s.entity_id)}" value="${esc(s.value)}">`;
          else if (s.kind === "number") ctl = `<input type="number" id="${id}" data-helper="${esc(s.entity_id)}" value="${esc(parseFloat(s.value))}" min="${esc(s.min)}" max="${esc(s.max)}" step="${esc(s.step || 1)}"> <span class="u">${esc(s.unit)}</span>`;
          else if (s.kind === "toggle") ctl = sw(`id="${id}" data-helper="${esc(s.entity_id)}"`, s.value === "on");
          html += `<div class="au-set"><label for="${id}">${esc(s.name)}</label>${ctl}</div>`;
        });
      }
      if (g.automations.length){
        html += `<details class="au-more" ${g.key === "other" ? "" : ""}><summary>${g.automations.length} step${g.automations.length === 1 ? "" : "s"} — what each one does</summary>`;
        g.automations.forEach(a => {
          html += `<div class="au-row"><div class="t"><div class="n">${esc(a.name)}</div>${a.about ? `<div class="d">${esc(a.about)}</div>` : ""}<div class="l">${esc(ago(a.last))}</div></div>${sw(`data-auto="${esc(a.entity_id)}" aria-label="${esc(a.name)}"`, a.on)}</div>`;
        });
        html += `</details>`;
      }
      html += `</div>`;
    });
    if ((data.groups || []).some(g => !g.installed && g.key !== "other"))
      html += `<div class="au-note">Home Assistant reports <b>${data.ha_total ?? 0}</b> automation${data.ha_total === 1 ? "" : "s"} and <b>${data.helpers_found ?? 0}</b> FamilyHub setting${data.helpers_found === 1 ? "" : "s"}${(data.fh_ids || []).length ? ` (FamilyHub ones: ${esc(data.fh_ids.join(", "))})` : ""}. 0 settings means Home Assistant hasn't loaded the packages folder.</div>`;
        html += `<div class="au-note">Changes take effect right away in Home Assistant. Turning a routine off pauses it until you turn it back on.</div>`;
    box.innerHTML = html;

    const say = m => { try { (toast || (()=>{}))(m); } catch(e){} };
    box.querySelectorAll("input[data-auto]").forEach(el => el.onchange = async () => {
      const r = await post("/api/ha/automations/toggle", {entity_id: el.dataset.auto, on: el.checked});
      say(r.ok ? (el.checked ? "Turned on" : "Paused") : "Couldn’t reach Home Assistant");
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
    });
  }

  async function load(box, toast){
    if (!box) return;
    try { render(box, await fetch("/api/ha/automations").then(r => r.json()), toast); }
    catch(e){ box.innerHTML = '<div class="hint">Couldn’t load the routines.</div>'; }
  }
  window.FHAutomations = { load, render };
})();
