/* Holiday skins for the wall: a painted-poster frame around the live widgets.
   Thanksgiving: Nov 1 → Thanksgiving Day.  Christmas: the day after Thanksgiving → Jan 1.
   settings.skin = "auto" | "off" | "christmas" | "thanksgiving"; ?skin=… in the URL
   overrides (used for "Preview on this phone"). Everything is CSS + inline SVG: no
   image files, works offline, and the real panels stay fully interactive underneath.
   Pair with Seasonal.force(): christmas => snow, thanksgiving => falling leaves. */
const Skins = (() => {
  const $ = s => document.querySelector(s);
  const DEFS = {
    christmas: {
      name: "Christmas", effect: "snow",
      vars: { "--bg": "#2a0909", "--panel": "#4d1414", "--panel2": "#3a0f0f", "--line": "#c99a46", "--ink": "#f6e9cf", "--ink-dim": "#dcb98a", "--now": "#f2c14e" },
      bg: "radial-gradient(120% 90% at 50% 20%, #6a1d1d 0%, #3d0f0f 45%, #210606 100%)",
      wood: ["#7a4a22", "#4a2a10"], gold: "#d9a84a", snowcaps: true,
      banner: { kicker: "Days until", title: "Christmas", font: "'Mountains of Christmas', 'Brush Script MT', cursive" },
      target: y => new Date(y, 11, 25),
      corners: "christmas"
    },
    thanksgiving: {
      name: "Thanksgiving", effect: "leaves",
      vars: { "--bg": "#2a160a", "--panel": "#5a3115", "--panel2": "#44250f", "--line": "#e0a040", "--ink": "#f8ead0", "--ink-dim": "#e2c08f", "--now": "#f5a623" },
      bg: "radial-gradient(120% 90% at 50% 20%, #7a4a1f 0%, #4a2a10 45%, #24130a 100%)",
      wood: ["#6b4523", "#3f2611"], gold: "#e0a040", snowcaps: false,
      banner: { kicker: "Days until", title: "Thanksgiving", font: "'Playfair Display', Georgia, serif" },
      target: y => thanksgiving(y),
      corners: "thanksgiving"
    }
  };

  function thanksgiving(y){ const dow = new Date(y, 10, 1).getDay(); return new Date(y, 10, 1 + ((4 - dow + 7) % 7) + 21); }
  function auto(now){
    now = now || new Date(); const y = now.getFullYear(), m = now.getMonth(), d = now.getDate();
    const tg = thanksgiving(y), today = new Date(y, m, d);
    if (m === 10 && today <= tg) return "thanksgiving";
    if ((m === 10 && today > tg) || m === 11 || (m === 0 && d === 1)) return "christmas";
    return null;
  }
  function pick(settings){
    const u = new URLSearchParams(location.search).get("skin");
    if (u) return u === "off" || u === "auto" ? (u === "auto" ? auto() : null) : (DEFS[u] ? u : null);
    const s = (settings && settings.skin) || "auto";
    if (s === "off") return null;
    if (s === "auto") return auto();
    return DEFS[s] ? s : null;
  }
  function daysUntil(target){ const t = new Date(); const a = new Date(t.getFullYear(), t.getMonth(), t.getDate()); return Math.round((target - a) / 864e5); }

  /* ---------- CSS (one style tag, scoped by html[data-skin]) ---------- */
  const css = `
@import url('https://fonts.googleapis.com/css2?family=Mountains+of+Christmas:wght@700&family=Playfair+Display:wght@700;900&family=Cinzel:wght@700&display=swap');
html[data-skin] body{background:var(--skin-bg) fixed}
html[data-skin] .wrap{padding:calc(34px * var(--density)) calc(38px * var(--density)) calc(32px * var(--density))}
html[data-skin] .main, html[data-skin] .card, html[data-skin] .bottomnav, html[data-skin] .cc-hero, html[data-skin] .tile, html[data-skin] .ph-card,
html[data-skin] .home-view-nav, html[data-skin] .sp, html[data-skin] .rt, html[data-skin] .km-card{
  background:linear-gradient(180deg, var(--panel) 0%, var(--panel2) 100%); border:2px solid var(--skin-gold);
  box-shadow:inset 0 0 0 1px rgba(255,220,150,.18), inset 0 14px 30px rgba(0,0,0,.25), 0 6px 18px rgba(0,0,0,.45); border-radius:16px; position:relative}
html[data-skin] .tile{border-radius:12px}
html[data-skin] .tile.on{background:linear-gradient(180deg, color-mix(in srgb, var(--now) 35%, var(--panel)), var(--panel2))}
html[data-skin] .tabs, html[data-skin] .cc-kpi, html[data-skin] .cc-chip, html[data-skin] .cc-qa, html[data-skin] .list-row, html[data-skin] .cd{
  background:rgba(0,0,0,.22); border-color:color-mix(in srgb, var(--skin-gold) 55%, transparent)}
html[data-skin] .tabs button.active, html[data-skin] .bottomnav button.active{background:var(--skin-gold); color:#2a0909}
html[data-skin] .bottomnav button{color:var(--ink-dim)}
html[data-skin] .date{font-family:'Cinzel', Georgia, serif; letter-spacing:.01em}
html[data-skin] .card h2, html[data-skin] .card h3, html[data-skin] .main h2, html[data-skin] .home-sec h3, html[data-skin] .cc-greet{
  font-family:'Cinzel', Georgia, serif; color:var(--now); letter-spacing:.06em}
html[data-skin] .gear{background:rgba(0,0,0,.25); border-color:color-mix(in srgb, var(--skin-gold) 60%, transparent); color:var(--ink)}
html[data-skin] .clock{color:var(--ink)}
/* snow caps on every panel (christmas) */
html[data-skin="christmas"] .main::before, html[data-skin="christmas"] .card::before, html[data-skin="christmas"] .cc-hero::before{
  content:""; position:absolute; left:-2px; right:-2px; top:-2px; height:18px; pointer-events:none; z-index:3;
  background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 18' preserveAspectRatio='none'><path d='M0 0h200v6c-8 0-10 9-18 9s-8-7-16-7-7 5-14 5-9-9-18-9-8 6-15 6-9-4-17-4-9 8-18 8-8-10-17-10-8 6-15 6-9-2-17-2-8 4-17 4-8-6-18-6V0z' fill='%23ffffff'/></svg>") repeat-x top/200px 18px}
/* the frame */
#skin-frame{position:fixed; inset:0; pointer-events:none; z-index:46}
#skin-frame .bar{position:absolute; background:linear-gradient(90deg, var(--skin-wood1), var(--skin-wood2) 50%, var(--skin-wood1)); box-shadow:inset 0 0 0 2px rgba(0,0,0,.35), inset 0 0 0 4px color-mix(in srgb, var(--skin-gold) 75%, transparent)}
#skin-frame .bar.t,#skin-frame .bar.b{left:0; right:0; height:22px; background:linear-gradient(180deg, var(--skin-wood1), var(--skin-wood2))}
#skin-frame .bar.t{top:0} #skin-frame .bar.b{bottom:0}
#skin-frame .bar.l,#skin-frame .bar.r{top:0; bottom:0; width:22px}
#skin-frame .bar.l{left:0} #skin-frame .bar.r{right:0}
#skin-frame svg{position:absolute; overflow:visible}
#skin-frame .lights{left:26px; right:26px; top:14px; height:34px; width:auto}
#skin-frame .lights-b{left:26px; right:26px; bottom:14px; top:auto; height:34px; width:auto}
#skin-frame .bulb{animation:twinkle 2.4s ease-in-out infinite}
@keyframes twinkle{0%,100%{opacity:1}50%{opacity:.45}}
#skin-frame .snowtop{left:0; right:0; top:0; height:30px; width:100%}
#skin-frame .corner{width:150px; height:150px}
#skin-frame .corner.tl{left:6px; top:4px} #skin-frame .corner.tr{right:6px; top:4px; transform:scaleX(-1)}
#skin-frame .corner.bl{left:8px; bottom:6px} #skin-frame .corner.br{right:8px; bottom:6px; transform:scaleX(-1)}
#skin-frame .leaves{left:0; right:0; top:0; height:60px; width:100%}
@keyframes sway{0%,100%{transform:rotate(-2deg)}50%{transform:rotate(2deg)}}
#skin-frame .lantern{transform-origin:top center; animation:sway 4s ease-in-out infinite}
/* the countdown banner in the header */
#skin-banner{display:none}
html[data-skin] header{min-height:124px; align-items:center; padding:0 118px}
html[data-skin] .bottomnav{margin:0 118px}
html[data-skin] #skin-banner{display:flex; flex-direction:column; align-items:center; justify-content:center; gap:2px;
  background:linear-gradient(180deg, var(--panel), var(--panel2)); border:2px solid var(--skin-gold); border-radius:16px; padding:10px 28px 10px; position:relative; min-width:300px;
  box-shadow:inset 0 0 0 1px rgba(255,220,150,.18), 0 8px 22px rgba(0,0,0,.45)}
html[data-skin="christmas"] #skin-banner::before{content:""; position:absolute; left:-2px; right:-2px; top:-2px; height:18px; z-index:3;
  background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 18' preserveAspectRatio='none'><path d='M0 0h200v6c-8 0-10 9-18 9s-8-7-16-7-7 5-14 5-9-9-18-9-8 6-15 6-9-4-17-4-9 8-18 8-8-10-17-10-8 6-15 6-9-2-17-2-8 4-17 4-8-6-18-6V0z' fill='%23ffffff'/></svg>") repeat-x top/200px 18px}
#skin-banner .k{font-family:'Cinzel', Georgia, serif; font-size:13px; letter-spacing:.18em; text-transform:uppercase; color:var(--ink-dim); margin-top:8px}
#skin-banner .t{font-family:var(--skin-font); font-size:44px; line-height:1; color:var(--now); text-shadow:0 2px 0 rgba(0,0,0,.35), 0 0 18px color-mix(in srgb, var(--now) 45%, transparent); margin:-2px 0 6px}
#skin-banner .digits{display:flex; gap:8px}
#skin-banner .dg{width:46px; height:58px; border-radius:8px; background:linear-gradient(180deg,#1c0505,#3a0d0d); border:2px solid var(--skin-gold); color:#fff; font:800 40px/54px 'Cinzel', Georgia, serif; text-align:center;
  box-shadow:inset 0 -2px 0 rgba(255,255,255,.08), 0 4px 10px rgba(0,0,0,.5); position:relative}
#skin-banner .dg::after{content:""; position:absolute; left:0; right:0; top:50%; height:1px; background:rgba(0,0,0,.55)}
#skin-banner .sub{font-family:'Cinzel', Georgia, serif; font-size:12px; letter-spacing:.12em; color:var(--ink-dim); margin-top:6px; text-transform:uppercase}
#skin-banner .sub b{color:var(--ink)}
#skin-banner .side{position:absolute; top:-6px; width:34px; height:60px}
#skin-banner .side.l{left:-18px} #skin-banner .side.r{right:-18px}
@media(max-width:760px){ html[data-skin] header{flex-wrap:wrap; padding:0 56px} html[data-skin] .bottomnav{margin:0 40px} html[data-skin] #skin-banner{order:3; width:100%; min-width:0} #skin-frame .corner{width:90px; height:90px} #skin-frame .lights-b{display:none} }
`;

  /* ---------- SVG parts ---------- */
  const NS = "http://www.w3.org/2000/svg";
  function svgEl(cls, vb){ const e = document.createElementNS(NS, "svg"); e.setAttribute("class", cls); if (vb) e.setAttribute("viewBox", vb); return e; }
  function lightsString(width, bottom){
    const svg = svgEl(bottom ? "lights-b" : "lights", `0 0 ${width} 34`); svg.setAttribute("preserveAspectRatio", "none");
    const cols = ["#ff4d4d", "#ffd23f", "#4dd2ff", "#7cf37c", "#ff8ad8", "#ffa94d"];
    let path = `M0 6`; const step = 44; const n = Math.max(6, Math.floor(width / step));
    for (let i = 0; i <= n; i++){ const x = i * (width / n); path += ` Q ${x + width / n / 2} 18 ${x + width / n} 6`; }
    const wire = document.createElementNS(NS, "path"); wire.setAttribute("d", path); wire.setAttribute("fill", "none"); wire.setAttribute("stroke", "#1a3a1a"); wire.setAttribute("stroke-width", "2"); svg.appendChild(wire);
    for (let i = 0; i < n; i++){
      const x = (i + 0.5) * (width / n), c = cols[i % cols.length];
      const g = document.createElementNS(NS, "g"); g.setAttribute("class", "bulb"); g.style.animationDelay = (i % 7) * 0.33 + "s";
      const cap = document.createElementNS(NS, "rect"); cap.setAttribute("x", x - 3); cap.setAttribute("y", 14); cap.setAttribute("width", 6); cap.setAttribute("height", 5); cap.setAttribute("fill", "#555"); g.appendChild(cap);
      const glow = document.createElementNS(NS, "ellipse"); glow.setAttribute("cx", x); glow.setAttribute("cy", 25); glow.setAttribute("rx", 10); glow.setAttribute("ry", 10); glow.setAttribute("fill", c); glow.setAttribute("opacity", ".28"); g.appendChild(glow);
      const b = document.createElementNS(NS, "ellipse"); b.setAttribute("cx", x); b.setAttribute("cy", 25); b.setAttribute("rx", 4.2); b.setAttribute("ry", 6); b.setAttribute("fill", c); g.appendChild(b);
      const hi = document.createElementNS(NS, "ellipse"); hi.setAttribute("cx", x - 1.4); hi.setAttribute("cy", 22); hi.setAttribute("rx", 1.2); hi.setAttribute("ry", 2); hi.setAttribute("fill", "#fff"); hi.setAttribute("opacity", ".7"); g.appendChild(hi);
      svg.appendChild(g);
    }
    return svg;
  }
  function snowTop(width){
    const svg = svgEl("snowtop", `0 0 ${width} 30`); svg.setAttribute("preserveAspectRatio", "none");
    let d = `M0 0 H${width} V12`; const n = Math.floor(width / 60);
    for (let i = n; i >= 0; i--){ const x = i * (width / n); d += ` C ${x + 20} 12 ${x + 15} ${18 + (i % 3) * 5} ${x} ${16 + (i % 2) * 6} C ${x - 10} ${22 + (i % 3) * 4} ${x - 25} 12 ${x - 30} 12`; }
    d += " V0 Z";
    const p = document.createElementNS(NS, "path"); p.setAttribute("d", d); p.setAttribute("fill", "#ffffff"); svg.appendChild(p);
    const p2 = document.createElementNS(NS, "path"); p2.setAttribute("d", d); p2.setAttribute("fill", "#dfe9f5"); p2.setAttribute("transform", "translate(0,-5)"); p2.setAttribute("opacity", ".6"); svg.insertBefore(p2, p);
    return svg;
  }
  const LANTERN = (x, y, s) => `<g class="lantern" transform="translate(${x},${y}) scale(${s})"><rect x="-1" y="-20" width="2" height="22" fill="#2a1a08"/><path d="M-9 0h18l2 4h-22z" fill="#2b2b2b"/><rect x="-8" y="4" width="16" height="22" rx="2" fill="#f7d98a" opacity=".92"/><rect x="-8" y="4" width="16" height="22" rx="2" fill="none" stroke="#2b2b2b" stroke-width="2"/><line x1="0" y1="4" x2="0" y2="26" stroke="#2b2b2b" stroke-width="1.5"/><ellipse cx="0" cy="17" rx="4" ry="6" fill="#ffb347"/><ellipse cx="0" cy="15" rx="2" ry="3.5" fill="#fff2c0"/><path d="M-10 26h20l-2 4h-16z" fill="#2b2b2b"/><ellipse cx="0" cy="18" rx="18" ry="16" fill="#ffcc66" opacity=".16"/></g>`;
  const BOW = (x, y, s) => `<g transform="translate(${x},${y}) scale(${s})"><path d="M0 0c-14-14-30-10-28 2 2 10 18 8 28-2z" fill="#c8102e"/><path d="M0 0c14-14 30-10 28 2-2 10-18 8-28-2z" fill="#c8102e"/><path d="M0 0c-12-8-22-6-22 1 0 6 12 6 22-1z" fill="#e3263f"/><path d="M0 0c12-8 22-6 22 1 0 6-12 6-22-1z" fill="#e3263f"/><path d="M-3 2l-8 24 8-4 3-20z" fill="#a50d26"/><path d="M3 2l8 24-8-4-3-20z" fill="#a50d26"/><circle r="5" fill="#ffd23f"/></g>`;
  const GIFT = (x, y, s, c1, c2) => `<g transform="translate(${x},${y}) scale(${s})"><rect x="-18" y="-10" width="36" height="28" rx="2" fill="${c1}"/><rect x="-20" y="-16" width="40" height="8" rx="1" fill="${c1}" stroke="rgba(0,0,0,.2)"/><rect x="-4" y="-16" width="8" height="34" fill="${c2}"/><rect x="-20" y="-13" width="40" height="3" fill="${c2}"/><path d="M0-16c-6-10-14-8-12-2 1 4 8 4 12 2zM0-16c6-10 14-8 12-2-1 4-8 4-12 2z" fill="${c2}"/></g>`;
  const HOLLY = (x, y, s) => `<g transform="translate(${x},${y}) scale(${s})"><path d="M0 0c-8-10-20-8-24 0 6 2 8 10 4 14 8 2 16-2 20-14z" fill="#2e7d32"/><path d="M0 0c8-10 20-8 24 0-6 2-8 10-4 14-8 2-16-2-20-14z" fill="#388e3c"/><circle cx="-3" cy="4" r="4" fill="#d32f2f"/><circle cx="4" cy="2" r="4" fill="#e53935"/><circle cx="1" cy="9" r="4" fill="#c62828"/></g>`;
  const CANDY = (x, y, s) => `<g transform="translate(${x},${y}) scale(${s}) rotate(-20)"><path d="M0 40V8a8 8 0 0 1 16 0" fill="none" stroke="#fff" stroke-width="7" stroke-linecap="round"/><path d="M0 40V8a8 8 0 0 1 16 0" fill="none" stroke="#d32f2f" stroke-width="7" stroke-linecap="round" stroke-dasharray="6 6"/></g>`;
  const ORNAMENT = (x, y, s, c) => `<g transform="translate(${x},${y}) scale(${s})"><rect x="-3" y="-14" width="6" height="6" fill="#d9a84a"/><circle r="11" fill="${c}"/><ellipse cx="-4" cy="-4" rx="3" ry="4.5" fill="#fff" opacity=".45"/><path d="M-11 2q11 6 22 0" stroke="#d9a84a" stroke-width="2" fill="none"/></g>`;
  const PUMPKIN = (x, y, s) => `<g transform="translate(${x},${y}) scale(${s})"><rect x="-3" y="-30" width="6" height="12" rx="2" fill="#5a3d1a"/><ellipse cx="-14" cy="0" rx="14" ry="20" fill="#e5791f"/><ellipse cx="14" cy="0" rx="14" ry="20" fill="#e5791f"/><ellipse cx="0" cy="0" rx="16" ry="22" fill="#f08c2a"/><ellipse cx="-5" cy="-6" rx="4" ry="8" fill="#fff" opacity=".12"/></g>`;
  const LEAF = (x, y, s, c, r) => `<g transform="translate(${x},${y}) rotate(${r}) scale(${s})"><path d="M0-16c10 2 16 10 14 20-6 4-14 4-20-2-4-8-2-14 6-18z" fill="${c}"/><path d="M0-16 L0 8" stroke="rgba(0,0,0,.25)" stroke-width="1.5"/></g>`;
  const ACORN = (x, y, s) => `<g transform="translate(${x},${y}) scale(${s})"><path d="M-8 0h16v3c0 8-4 13-8 13s-8-5-8-13z" fill="#8a5a2b"/><path d="M-10 0q10-8 20 0v2h-20z" fill="#5a3d1a"/><rect x="-1" y="-6" width="2" height="5" fill="#5a3d1a"/></g>`;
  const WHEAT = (x, y, s, r) => `<g transform="translate(${x},${y}) rotate(${r}) scale(${s})"><line x1="0" y1="0" x2="0" y2="40" stroke="#c9a04a" stroke-width="2"/>${[0,6,12,18,24].map(i=>`<ellipse cx="-4" cy="${i}" rx="3" ry="5" fill="#e3b85a" transform="rotate(-25 -4 ${i})"/><ellipse cx="4" cy="${i}" rx="3" ry="5" fill="#e3b85a" transform="rotate(25 4 ${i})"/>`).join("")}</g>`;

  function corner(kind, where){
    const svg = svgEl("corner " + where, "0 0 150 150");
    let inner = "";
    if (kind === "christmas"){
      if (where === "tl" || where === "tr") inner = BOW(40, 36, 1.1) + LANTERN(110, 8, 1.15) + HOLLY(70, 98, .9) + ORNAMENT(26, 96, .8, "#c8102e") + ORNAMENT(48, 120, .7, "#2e7d32");
      else inner = GIFT(44, 104, 1.1, "#c8102e", "#ffd23f") + GIFT(92, 112, .85, "#1565c0", "#fff") + GIFT(70, 76, .7, "#2e7d32", "#ffd23f") + CANDY(118, 60, .9) + HOLLY(118, 118, .8);
    } else {
      if (where === "tl" || where === "tr") inner = [["#d35400",-30],["#e67e22",10],["#c0392b",45],["#f1c40f",-60],["#a04000",80]].map((l,i)=>LEAF(30+i*22, 30+(i%2)*18, 1+(i%3)*.15, l[0], l[1])).join("") + ACORN(110, 92, 1.1) + ACORN(126, 108, .9) + WHEAT(70, 60, .9, 25);
      else inner = PUMPKIN(50, 110, 1.2) + PUMPKIN(100, 120, .8) + LEAF(120, 70, 1.1, "#c0392b", 30) + LEAF(20, 70, 1, "#e67e22", -40) + WHEAT(130, 40, 1, 15) + ACORN(84, 76, 1);
    }
    svg.innerHTML = inner; return svg;
  }
  function leafGarland(width){
    const svg = svgEl("leaves", `0 0 ${width} 60`); svg.setAttribute("preserveAspectRatio", "none");
    const cols = ["#d35400", "#e67e22", "#c0392b", "#f1c40f", "#a04000", "#e8a33d"]; let s = `<path d="M0 22 Q ${width/2} 46 ${width} 22" stroke="#5a3d1a" stroke-width="4" fill="none"/>`;
    const n = Math.floor(width / 34);
    for (let i = 0; i <= n; i++){ const x = i * (width / n), t = x / width, y = 22 + Math.sin(Math.PI * t) * 24; s += LEAF(x, y, .75 + (i % 3) * .12, cols[i % cols.length], (i * 47) % 360); }
    svg.innerHTML = s; return svg;
  }

  /* ---------- apply ---------- */
  let current = null, styleEl = null, frameEl = null, bannerEl = null, tick = null;
  function ensure(){
    if (!styleEl){ styleEl = document.createElement("style"); styleEl.id = "skin-css"; styleEl.textContent = css; document.head.appendChild(styleEl); }
    if (!frameEl){ frameEl = document.createElement("div"); frameEl.id = "skin-frame"; document.body.appendChild(frameEl); }
    if (!bannerEl){ bannerEl = document.createElement("div"); bannerEl.id = "skin-banner"; const h = document.querySelector("header"); const d = h && h.querySelector(".date"); if (d && d.nextSibling) h.insertBefore(bannerEl, d.nextSibling); else if (h) h.appendChild(bannerEl); }
  }
  function buildFrame(kind){
    frameEl.innerHTML = ""; const w = window.innerWidth;
    ["t","b","l","r"].forEach(k => { const b = document.createElement("div"); b.className = "bar " + k; frameEl.appendChild(b); });
    if (kind === "christmas"){ frameEl.appendChild(snowTop(w)); frameEl.appendChild(lightsString(w - 52, false)); frameEl.appendChild(lightsString(w - 52, true)); }
    else { frameEl.appendChild(leafGarland(w)); }
    ["tl","tr","bl","br"].forEach(c => frameEl.appendChild(corner(kind, c)));
  }
  function renderBanner(kind){
    const def = DEFS[kind], y = new Date().getFullYear();
    let target = def.target(y); if (daysUntil(target) < 0 && kind === "christmas") target = def.target(y + 1);
    const n = daysUntil(target), nn = Math.max(0, Math.min(99, n));
    const digits = String(nn).padStart(2, "0").split("").map(d => `<div class="dg">${d}</div>`).join("");
    let sub = "";
    const m = new Date().getMonth(), d = new Date().getDate();
    if (kind === "christmas"){
      if (n === 0) sub = "<b>Merry Christmas!</b>";
      else if (n < 0) sub = "<b>Happy New Year!</b>";
      else if (m === 11) sub = `Advent · <b>Day ${d}</b> of 24`;
      else sub = `<b>${target.toLocaleDateString([], {weekday: "long", month: "long", day: "numeric"})}</b>`;
    } else {
      sub = n === 0 ? "<b>Happy Thanksgiving!</b>" : `<b>${target.toLocaleDateString([], {weekday: "long", month: "long", day: "numeric"})}</b>`;
    }
    const sideL = kind === "christmas" ? `<svg class="side l" viewBox="0 0 34 60">${LANTERN(17, 2, .9)}</svg>` : `<svg class="side l" viewBox="0 0 34 60">${LEAF(17, 22, .8, "#e67e22", -30)}${ACORN(17, 46, .8)}</svg>`;
    const sideR = kind === "christmas" ? `<svg class="side r" viewBox="0 0 34 60">${LANTERN(17, 2, .9)}</svg>` : `<svg class="side r" viewBox="0 0 34 60">${LEAF(17, 22, .8, "#c0392b", 30)}${ACORN(17, 46, .8)}</svg>`;
    bannerEl.innerHTML = `${sideL}${sideR}<div class="k">${n === 0 ? "" : def.banner.kicker}</div><div class="t">${def.banner.title}</div><div class="digits">${n === 0 ? "" : digits}</div><div class="sub">${sub}</div>`;
    bannerEl.querySelector(".digits").style.display = n === 0 ? "none" : "";
  }
  function apply(settings){
    ensure();
    const kind = pick(settings);
    const root = document.documentElement;
    if (!kind){ if (current){ root.removeAttribute("data-skin"); ["--skin-bg","--skin-gold","--skin-wood1","--skin-wood2","--skin-font"].forEach(v => root.style.removeProperty(v)); Object.keys(DEFS.christmas.vars).forEach(v => root.style.removeProperty(v)); frameEl.innerHTML = ""; bannerEl.innerHTML = ""; current = null; clearInterval(tick); if (typeof FH !== "undefined") FH.apply(FH.get()); } return null; }
    const def = DEFS[kind];
    root.setAttribute("data-skin", kind);
    Object.entries(def.vars).forEach(([k, v]) => root.style.setProperty(k, v));
    root.style.setProperty("--skin-bg", def.bg); root.style.setProperty("--skin-gold", def.gold);
    root.style.setProperty("--skin-wood1", def.wood[0]); root.style.setProperty("--skin-wood2", def.wood[1]); root.style.setProperty("--skin-font", def.banner.font);
    if (current !== kind){ buildFrame(kind); current = kind; }
    renderBanner(kind);
    clearInterval(tick); tick = setInterval(() => renderBanner(kind), 60 * 1000);
    return kind;
  }
  window.addEventListener("resize", () => { if (current) buildFrame(current); });
  // auto schedule flips at midnight: re-check every 10 minutes
  setInterval(() => { if (typeof FH !== "undefined") { const k = pick(FH.get()); if (k !== current) apply(FH.get()); } }, 10 * 60 * 1000);

  return { apply, pick, auto, thanksgiving, DEFS, effect: () => current ? DEFS[current].effect : null, current: () => current };
})();
window.Skins = Skins;
