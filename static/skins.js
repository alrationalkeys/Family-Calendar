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
      vars: { "--bg": "#2a0909", "--panel": "#4d1414", "--panel2": "#3a0f0f", "--line": "#c99a46", "--ink": "#f8ecd4", "--ink-dim": "#e6c99e", "--now": "#f2c14e" },
      bg: "radial-gradient(120% 90% at 50% 20%, #6a1d1d 0%, #3d0f0f 45%, #210606 100%)",
      wood: ["#7a4a22", "#4a2a10"], gold: "#d9a84a", snowcaps: true,
      banner: { kicker: "Days until", title: "Christmas", font: "'Mountains of Christmas', 'Brush Script MT', cursive" },
      target: y => new Date(y, 11, 25),
      corners: "christmas",
      // painted frame (Midjourney, keyed to transparent). zoom crops the thick posts partly off-screen;
      // pad = how far the live content stays from each screen edge; hpad = extra header side padding (lanterns)
      art: { src: "/skins/christmas-frame.png", zoom: 1.0, pad: { t: 180, r: 228, b: 158, l: 232 }, hpad: 60 }
    },
    thanksgiving: {
      name: "Thanksgiving", effect: "leaves",
      vars: { "--bg": "#2a160a", "--panel": "#5a3115", "--panel2": "#44250f", "--line": "#e0a040", "--ink": "#f8ead0", "--ink-dim": "#e2c08f", "--now": "#f5a623" },
      bg: "radial-gradient(120% 90% at 50% 20%, #7a4a1f 0%, #4a2a10 45%, #24130a 100%)",
      wood: ["#6b4523", "#3f2611"], gold: "#e0a040", snowcaps: false,
      banner: { kicker: "Days until", title: "Thanksgiving", font: "'Playfair Display', Georgia, serif" },
      target: y => thanksgiving(y),
      corners: "thanksgiving",
      art: { src: "/skins/thanksgiving-frame.png", zoom: 1.0, pad: { t: 195, r: 250, b: 172, l: 245 }, hpad: 80 }
    }
  };

  DEFS.birthday = {
    name: "Birthday", effect: "confetti", emoji: "🎂",
    vars: { "--bg": "#1b1030", "--panel": "#2a1a4a", "--panel2": "#20133a", "--line": "#f2c14e", "--ink": "#fff5e6", "--ink-dim": "#d9c6ef", "--now": "#ff6fae" },
    bg: "radial-gradient(120% 90% at 50% 20%, #4a2a7a 0%, #2a1650 45%, #150b2a 100%)",
    wood: ["#ff6fae", "#7a3cc9"], gold: "#f2c14e", snowcaps: false,
    banner: { kicker: "Happy Birthday", title: "", font: "'Mountains of Christmas', 'Brush Script MT', cursive" },
    target: null, corners: "birthday", manual: true,         // manual: picked from the menu or auto on a family birthday
    art: { src: "/skins/birthday-frame.png", zoom: 1.0, pad: { t: 170, r: 235, b: 150, l: 235 }, hpad: 40 }
  };
  DEFS.newyear = {
    name: "New Year's Eve", effect: "fireworks", emoji: "🎆",
    vars: { "--bg": "#070b1a", "--panel": "#141a33", "--panel2": "#0e1328", "--line": "#d4b25a", "--ink": "#f7f3e8", "--ink-dim": "#c9c2ad", "--now": "#f2cc6b" },
    bg: "radial-gradient(120% 90% at 50% 15%, #1d2650 0%, #0b1030 45%, #04060f 100%)",
    wood: ["#d4b25a", "#8a7432"], gold: "#e8c66a", snowcaps: false,
    banner: { kicker: "Countdown to", title: "", font: "'Cinzel', Georgia, serif" },
    target: y => new Date(y + 1, 0, 1), corners: "newyear"
  };
  function thanksgiving(y){ const dow = new Date(y, 10, 1).getDay(); return new Date(y, 10, 1 + ((4 - dow + 7) % 7) + 21); }
  function birthdayPeople(now){
    now = now || new Date(); const mmdd = String(now.getMonth() + 1).padStart(2, "0") + "-" + String(now.getDate()).padStart(2, "0");
    const list = (typeof people !== "undefined" && Array.isArray(people)) ? people : [];
    return list.filter(p => p && p.birthday && String(p.birthday).slice(-5) === mmdd);
  }
  function auto(now){
    now = now || new Date(); const y = now.getFullYear(), m = now.getMonth(), d = now.getDate();
    if (birthdayPeople(now).length) return "birthday";
    const tg = thanksgiving(y), today = new Date(y, m, d);
    if (m === 10 && today <= tg) return "thanksgiving";
    if ((m === 11 && d === 31) || (m === 0 && d === 1)) return "newyear";
    if ((m === 10 && today > tg) || m === 11) return "christmas";
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
/* ---- readability inside the panels: solid event chips, quiet grid lines, brighter small text ---- */
html[data-skin]{--skin-grid:rgba(255,255,255,.16)}
html[data-skin] .tg-ev, html[data-skin] .adev, html[data-skin] .mev, html[data-skin] .ev, html[data-skin] .agenda-ev .chip{
  background:color-mix(in srgb, var(--accent,#4f86c6) 82%, #000); color:#fff; border-left-color:rgba(255,255,255,.55); text-shadow:0 1px 2px rgba(0,0,0,.6); box-shadow:0 2px 6px rgba(0,0,0,.35)}
html[data-skin] .tg-ev .tm, html[data-skin] .ev .who, html[data-skin] .mev .mt{color:rgba(255,255,255,.82)}
html[data-skin] .tg-ev .evt{font-size:12.5px} html[data-skin] .adev{font-size:12px}
html[data-skin] .tg-day{border-left-color:var(--skin-grid); background-image:repeating-linear-gradient(var(--skin-grid) 0 1px, transparent 1px var(--hpx,46px))}
html[data-skin] .tg-head .dcol, html[data-skin] .tg-head .cnr, html[data-skin] .tg-allday, html[data-skin] .tg-allday .adcol, html[data-skin] .hour, html[data-skin] .agenda-ev, html[data-skin] .list-row{border-color:var(--skin-grid)}
html[data-skin] .mcell{background:rgba(0,0,0,.22)}
html[data-skin] .tg-gut .gh, html[data-skin] .tg-head .dcol .dn, html[data-skin] .tg-head .dcol .dwx, html[data-skin] .tg-allday .lbl, html[data-skin] .qty, html[data-skin] .empty{color:var(--ink); opacity:.85}
html[data-skin] .tg-gut .gh, html[data-skin] .tg-head .dcol .dwx{font-size:12px}
html[data-skin] #home-statusbar{color:var(--ink); font-size:14px; text-shadow:0 1px 2px rgba(0,0,0,.6)}
html[data-skin] .label{font-size:16px}
/* header text over the painting: a dark halo so lights and icicles behind it never fight the date/clock */
html[data-skin] .date, html[data-skin] .date small, html[data-skin] .clock, html[data-skin] .wx, html[data-skin] .wx .t{text-shadow:0 2px 4px rgba(0,0,0,.95), 0 0 16px rgba(0,0,0,.9), 0 0 30px rgba(0,0,0,.8)}
html[data-skin] .date small{color:var(--ink)}
/* snow caps on every panel (christmas) */
html[data-skin="christmas"] .main::before, html[data-skin="christmas"] .card::before, html[data-skin="christmas"] .cc-hero::before{
  content:""; position:absolute; left:-2px; right:-2px; top:-2px; height:18px; pointer-events:none; z-index:3;
  background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 18' preserveAspectRatio='none'><path d='M0 0h200v6c-8 0-10 9-18 9s-8-7-16-7-7 5-14 5-9-9-18-9-8 6-15 6-9-4-17-4-9 8-18 8-8-10-17-10-8 6-15 6-9-2-17-2-8 4-17 4-8-6-18-6V0z' fill='%23ffffff'/></svg>") repeat-x top/200px 18px}
/* the frame */
#skin-frame{position:fixed; inset:0; pointer-events:none; z-index:46}
/* painted artwork sits BEHIND the live panels (they float on top, like widgets on a poster) */
/* lite: phone-sized screens keep the colors but drop the frame, art, pads and banner */
html[data-skin][data-skin-lite="on"] #skin-art, html[data-skin][data-skin-lite="on"] #skin-frame, html[data-skin][data-skin-lite="on"] #skin-banner, html[data-skin][data-skin-lite="on"] #skin-fly, html[data-skin][data-skin-lite="on"] #skin-walk{display:none!important}
html[data-skin][data-skin-lite="on"] .wrap{padding:0!important}
html[data-skin][data-skin-lite="on"] header{padding:0!important; min-height:0!important}
html[data-skin][data-skin-lite="on"] .bottomnav{margin:0!important}
#skin-art{position:fixed; inset:0; z-index:0; pointer-events:none; background-repeat:no-repeat; background-position:center; background-size:var(--skin-art-size, 100% 100%); display:none}
html[data-skin][data-skin-art="on"] #skin-art{display:block}
html[data-skin][data-skin-art="on"] .wrap{position:relative; z-index:1; padding:var(--skin-pad-t) var(--skin-pad-r) var(--skin-pad-b) var(--skin-pad-l)}
html[data-skin][data-skin-art="on"] #skin-frame{display:none}
html[data-skin][data-skin-art="on"] header{padding:0 var(--skin-hpad, 0)}
html[data-skin][data-skin-art="on"] .bottomnav{margin:0}
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
#skin-frame .bulb.flick{animation:flicker .5s steps(2) 3}
@keyframes flicker{0%{opacity:1}50%{opacity:.08}100%{opacity:1}}
#skin-frame .flame, #skin-banner .flame{transform-origin:center 80%; animation:flame .9s ease-in-out infinite alternate}
@keyframes flame{from{transform:scaleY(.9) scaleX(1.05); opacity:.9}to{transform:scaleY(1.12) scaleX(.95); opacity:1}}
#skin-fly{position:fixed; left:0; top:0; z-index:47; pointer-events:none; display:none}
#skin-fly.go{display:block; animation:flyover var(--fly-s,16s) linear forwards}
@keyframes flyover{0%{transform:translate(-520px, var(--fly-y)) }25%{transform:translate(25vw, calc(var(--fly-y) - 22px))}50%{transform:translate(50vw, calc(var(--fly-y) + 10px))}75%{transform:translate(75vw, calc(var(--fly-y) - 16px))}100%{transform:translate(105vw, var(--fly-y))}}
#skin-fly .bob{animation:bob 1.1s ease-in-out infinite alternate}
@keyframes bob{from{transform:translateY(0)}to{transform:translateY(-5px)}}
#skin-walk{position:fixed; left:0; bottom:26px; z-index:47; pointer-events:none; display:none; font-size:40px; filter:drop-shadow(0 3px 3px rgba(0,0,0,.5))}
#skin-walk.go{display:block; animation:walk var(--walk-s,18s) linear forwards}
@keyframes walk{from{transform:translateX(105vw) scaleX(-1)}to{transform:translateX(-80px) scaleX(-1)}}
#skin-walk span{display:inline-block; animation:waddle .45s ease-in-out infinite alternate}
#skin-walk img{transform:scaleX(-1)}   /* the painted turkey faces left; the walk flips the whole thing, so flip him back */
@keyframes waddle{from{transform:rotate(-7deg) translateY(0)}to{transform:rotate(7deg) translateY(-3px)}}
html[data-skin][data-skin-banner="off"] #skin-banner{display:none}
html[data-skin][data-skin-banner="off"] header{min-height:0}
#skin-frame .snowtop{left:0; right:0; top:0; height:30px; width:100%}
#skin-frame .corner{width:150px; height:150px}
#skin-frame .corner.tl{left:6px; top:4px} #skin-frame .corner.tr{right:6px; top:4px; transform:scaleX(-1)}
#skin-frame .corner.bl{left:8px; bottom:6px} #skin-frame .corner.br{right:8px; bottom:6px; transform:scaleX(-1)}
#skin-frame .leaves{left:0; right:0; top:0; height:60px; width:100%}
@keyframes sway{0%,100%{transform:rotate(-2deg)}50%{transform:rotate(2deg)}}
#skin-frame .lantern{transform-origin:top center; animation:sway 4s ease-in-out infinite}
/* birthday: balloons bob along the sides, banner shows the name(s) */
#skin-frame .balloon{animation:float 5s ease-in-out infinite alternate; transform-origin:center bottom}
@keyframes float{from{transform:translateY(0) rotate(-3deg)}to{transform:translateY(-14px) rotate(3deg)}}
html[data-skin="birthday"] #skin-banner .t{font-size:34px}
html[data-skin="birthday"] #skin-banner .k{color:var(--now)}
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
#skin-banner .dg-sep{font:800 34px/58px 'Cinzel', Georgia, serif; color:var(--now); margin:0 -2px}
html[data-skin="newyear"] #skin-banner .t{font-size:40px; letter-spacing:.08em}
.twinkle{animation:twinkle 2.4s ease-in-out infinite alternate; transform-box:fill-box; transform-origin:center}
@keyframes twinkle{from{opacity:.45}to{opacity:1}}
/* painted hanging sign (Christmas, art mode): the card IS the sign; it hangs up into the garland */
html[data-skin="christmas"][data-skin-art="on"] #skin-banner{background:url("/skins/christmas-sign.png") center/100% 100% no-repeat; border:0; border-radius:0; box-shadow:none;
  min-width:340px; width:340px; height:207px; padding:64px 44px 26px; margin:-54px 0 -14px; gap:0; justify-content:flex-start}
html[data-skin="christmas"][data-skin-art="on"] #skin-banner::before{display:none}
html[data-skin="christmas"][data-skin-art="on"] #skin-banner .k{margin-top:0; font-size:11px; color:#e6c99e}
html[data-skin="christmas"][data-skin-art="on"] #skin-banner .t{font-size:36px; margin:0 0 4px}
html[data-skin="christmas"][data-skin-art="on"] #skin-banner .dg{width:36px; height:46px; font:800 30px/42px 'Cinzel', Georgia, serif; border-width:1.5px}
html[data-skin="christmas"][data-skin-art="on"] #skin-banner .sub{font-size:10.5px; margin-top:4px}
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
  const LANTERN = (x, y, s) => `<g class="lantern" transform="translate(${x},${y}) scale(${s})"><rect x="-1" y="-20" width="2" height="22" fill="#2a1a08"/><path d="M-9 0h18l2 4h-22z" fill="#2b2b2b"/><rect x="-8" y="4" width="16" height="22" rx="2" fill="#f7d98a" opacity=".92"/><rect x="-8" y="4" width="16" height="22" rx="2" fill="none" stroke="#2b2b2b" stroke-width="2"/><line x1="0" y1="4" x2="0" y2="26" stroke="#2b2b2b" stroke-width="1.5"/><g class="flame"><ellipse cx="0" cy="17" rx="4" ry="6" fill="#ffb347"/><ellipse cx="0" cy="15" rx="2" ry="3.5" fill="#fff2c0"/></g><path d="M-10 26h20l-2 4h-16z" fill="#2b2b2b"/><ellipse cx="0" cy="18" rx="18" ry="16" fill="#ffcc66" opacity=".16"/></g>`;
  const BOW = (x, y, s) => `<g transform="translate(${x},${y}) scale(${s})"><path d="M0 0c-14-14-30-10-28 2 2 10 18 8 28-2z" fill="#c8102e"/><path d="M0 0c14-14 30-10 28 2-2 10-18 8-28-2z" fill="#c8102e"/><path d="M0 0c-12-8-22-6-22 1 0 6 12 6 22-1z" fill="#e3263f"/><path d="M0 0c12-8 22-6 22 1 0 6-12 6-22-1z" fill="#e3263f"/><path d="M-3 2l-8 24 8-4 3-20z" fill="#a50d26"/><path d="M3 2l8 24-8-4-3-20z" fill="#a50d26"/><circle r="5" fill="#ffd23f"/></g>`;
  const GIFT = (x, y, s, c1, c2) => `<g transform="translate(${x},${y}) scale(${s})"><rect x="-18" y="-10" width="36" height="28" rx="2" fill="${c1}"/><rect x="-20" y="-16" width="40" height="8" rx="1" fill="${c1}" stroke="rgba(0,0,0,.2)"/><rect x="-4" y="-16" width="8" height="34" fill="${c2}"/><rect x="-20" y="-13" width="40" height="3" fill="${c2}"/><path d="M0-16c-6-10-14-8-12-2 1 4 8 4 12 2zM0-16c6-10 14-8 12-2-1 4-8 4-12 2z" fill="${c2}"/></g>`;
  const HOLLY = (x, y, s) => `<g transform="translate(${x},${y}) scale(${s})"><path d="M0 0c-8-10-20-8-24 0 6 2 8 10 4 14 8 2 16-2 20-14z" fill="#2e7d32"/><path d="M0 0c8-10 20-8 24 0-6 2-8 10-4 14-8 2-16-2-20-14z" fill="#388e3c"/><circle cx="-3" cy="4" r="4" fill="#d32f2f"/><circle cx="4" cy="2" r="4" fill="#e53935"/><circle cx="1" cy="9" r="4" fill="#c62828"/></g>`;
  const CANDY = (x, y, s) => `<g transform="translate(${x},${y}) scale(${s}) rotate(-20)"><path d="M0 40V8a8 8 0 0 1 16 0" fill="none" stroke="#fff" stroke-width="7" stroke-linecap="round"/><path d="M0 40V8a8 8 0 0 1 16 0" fill="none" stroke="#d32f2f" stroke-width="7" stroke-linecap="round" stroke-dasharray="6 6"/></g>`;
  const ORNAMENT = (x, y, s, c) => `<g transform="translate(${x},${y}) scale(${s})"><rect x="-3" y="-14" width="6" height="6" fill="#d9a84a"/><circle r="11" fill="${c}"/><ellipse cx="-4" cy="-4" rx="3" ry="4.5" fill="#fff" opacity=".45"/><path d="M-11 2q11 6 22 0" stroke="#d9a84a" stroke-width="2" fill="none"/></g>`;
  const PUMPKIN = (x, y, s) => `<g transform="translate(${x},${y}) scale(${s})"><rect x="-3" y="-30" width="6" height="12" rx="2" fill="#5a3d1a"/><ellipse cx="-14" cy="0" rx="14" ry="20" fill="#e5791f"/><ellipse cx="14" cy="0" rx="14" ry="20" fill="#e5791f"/><ellipse cx="0" cy="0" rx="16" ry="22" fill="#f08c2a"/><ellipse cx="-5" cy="-6" rx="4" ry="8" fill="#fff" opacity=".12"/></g>`;
  const LEAF = (x, y, s, c, r) => `<g transform="translate(${x},${y}) rotate(${r}) scale(${s})"><path d="M0-16c10 2 16 10 14 20-6 4-14 4-20-2-4-8-2-14 6-18z" fill="${c}"/><path d="M0-16 L0 8" stroke="rgba(0,0,0,.25)" stroke-width="1.5"/></g>`;
  const ACORN = (x, y, s) => `<g transform="translate(${x},${y}) scale(${s})"><path d="M-8 0h16v3c0 8-4 13-8 13s-8-5-8-13z" fill="#8a5a2b"/><path d="M-10 0q10-8 20 0v2h-20z" fill="#5a3d1a"/><rect x="-1" y="-6" width="2" height="5" fill="#5a3d1a"/></g>`;
  const WHEAT = (x, y, s, r) => `<g transform="translate(${x},${y}) rotate(${r}) scale(${s})"><line x1="0" y1="0" x2="0" y2="40" stroke="#c9a04a" stroke-width="2"/>${[0,6,12,18,24].map(i=>`<ellipse cx="-4" cy="${i}" rx="3" ry="5" fill="#e3b85a" transform="rotate(-25 -4 ${i})"/><ellipse cx="4" cy="${i}" rx="3" ry="5" fill="#e3b85a" transform="rotate(25 4 ${i})"/>`).join("")}</g>`;

  const BALLOON = (x, y, s, c, d) => `<g class="balloon" style="animation-delay:${d||0}s" transform="translate(${x},${y}) scale(${s})"><path d="M0 44 q-2 10 4 22" stroke="#555" stroke-width="1.2" fill="none"/><ellipse rx="16" ry="20" fill="${c}"/><ellipse cx="-6" cy="-7" rx="4" ry="6" fill="#fff" opacity=".4"/><path d="M-3 19 l3 6 3-6z" fill="${c}"/></g>`;
  const CAKE = (x, y, s) => `<g transform="translate(${x},${y}) scale(${s})"><rect x="-26" y="0" width="52" height="22" rx="4" fill="#f7a8c4"/><rect x="-26" y="0" width="52" height="7" rx="3" fill="#fff"/><rect x="-20" y="-16" width="40" height="18" rx="4" fill="#ffd6e7"/><rect x="-20" y="-16" width="40" height="6" rx="3" fill="#fff"/>${[-12,0,12].map(cx=>`<rect x="${cx-1.5}" y="-30" width="3" height="14" fill="#5bc0eb"/><ellipse cx="${cx}" cy="-33" rx="2.5" ry="4" fill="#ffb347"/><ellipse cx="${cx}" cy="-34" rx="1.2" ry="2" fill="#fff2c0"/>`).join("")}</g>`;
  const STREAMER = (x, y, s, c, r) => `<g transform="translate(${x},${y}) rotate(${r}) scale(${s})"><path d="M0 0 q8 10 0 20 t0 20 t0 20" stroke="${c}" stroke-width="4" fill="none" stroke-linecap="round"/></g>`;
  const STAR = (x, y, s, c, d) => `<g class="twinkle" style="animation-delay:${d||0}s" transform="translate(${x},${y}) scale(${s})"><path d="M0-12 3-4 12-4 5 2 8 11 0 6-8 11-5 2-12-4-3-4z" fill="${c}"/></g>`;
  const FLUTE = (x, y, s, r) => `<g transform="translate(${x},${y}) rotate(${r||0}) scale(${s})"><path d="M-7-30 h14 l-2 26 q-5 5-10 0z" fill="#f7e39a" opacity=".9"/><path d="M-7-30 h14 l-1 8 h-12z" fill="#fff" opacity=".55"/><rect x="-1" y="-4" width="2" height="22" fill="#e8e8f0"/><ellipse cx="0" cy="19" rx="9" ry="2.5" fill="#e8e8f0"/>${[0,1,2].map(i=>`<circle cx="${-3+i*3}" cy="${-12-i*5}" r="1" fill="#fff"/>`).join("")}</g>`;
  const BOTTLE = (x, y, s, r) => `<g transform="translate(${x},${y}) rotate(${r||0}) scale(${s})"><rect x="-4" y="-46" width="8" height="16" rx="2" fill="#d4b25a"/><path d="M-4-30 q-8 6-8 16 v38 h24 v-38 q0-10-8-16z" fill="#173b2a"/><rect x="-12" y="-2" width="24" height="14" fill="#f7f3e8"/><rect x="-12" y="-2" width="24" height="3" fill="#d4b25a"/></g>`;
  const CLOCK = (x, y, s) => `<g transform="translate(${x},${y}) scale(${s})"><circle r="22" fill="#f7f3e8" stroke="#d4b25a" stroke-width="4"/>${Array.from({length:12},(_,i)=>`<rect x="-1" y="-19" width="2" height="${i%3?3:6}" fill="#141a33" transform="rotate(${i*30})"/>`).join("")}<rect x="-1.5" y="-15" width="3" height="16" fill="#141a33"/><rect x="-1" y="-18" width="2" height="19" fill="#c8102e" transform="rotate(-6)"/><circle r="2.5" fill="#d4b25a"/></g>`;
  function corner(kind, where){
    const svg = svgEl("corner " + where, "0 0 150 150");
    let inner = "";
    if (kind === "newyear"){
      const gold = "#f2cc6b", silver = "#dfe6f2";
      if (where === "tl" || where === "tr") inner = STAR(30, 30, 1.3, gold, 0) + STAR(70, 18, .8, silver, .6) + STAR(104, 40, 1, gold, 1.2) + STAR(40, 76, .7, silver, .3) + CLOCK(96, 92, 1.05) + STREAMER(16, 96, .9, gold, -10);
      else inner = BOTTLE(42, 104, 1.05, -12) + FLUTE(88, 110, 1.15, 8) + FLUTE(116, 104, 1.05, -6) + STAR(120, 40, .9, gold, .4) + STAR(70, 52, .7, silver, 1);
      svg.innerHTML = inner; return svg;
    }
    if (kind === "birthday"){
      const cols = ["#ff6fae", "#5bc0eb", "#f2c14e", "#7cf37c", "#b388ff"];
      if (where === "tl" || where === "tr") inner = [0,1,2].map(i => BALLOON(30 + i * 36, 40 + (i % 2) * 18, .9 + (i % 2) * .15, cols[i], i * .7)).join("") + STREAMER(120, 10, 1, cols[3], 20) + STREAMER(10, 90, .9, cols[4], -15);
      else inner = CAKE(60, 110, 1.1) + BALLOON(118, 60, .8, cols[1], .4) + GIFT(120, 120, .8, cols[4], cols[2]) + STREAMER(20, 60, .9, cols[0], 10);
      svg.innerHTML = inner; return svg;
    }
    if (kind === "christmas"){
      if (where === "tl" || where === "tr") inner = BOW(40, 36, 1.1) + LANTERN(110, 8, 1.15) + HOLLY(70, 98, .9) + ORNAMENT(26, 96, .8, "#c8102e") + ORNAMENT(48, 120, .7, "#2e7d32");
      else inner = GIFT(44, 104, 1.1, "#c8102e", "#ffd23f") + GIFT(92, 112, .85, "#1565c0", "#fff") + GIFT(70, 76, .7, "#2e7d32", "#ffd23f") + CANDY(118, 60, .9) + HOLLY(118, 118, .8);
    } else {
      if (where === "tl" || where === "tr") inner = [["#d35400",-30],["#e67e22",10],["#c0392b",45],["#f1c40f",-60],["#a04000",80]].map((l,i)=>LEAF(30+i*22, 30+(i%2)*18, 1+(i%3)*.15, l[0], l[1])).join("") + ACORN(110, 92, 1.1) + ACORN(126, 108, .9) + WHEAT(70, 60, .9, 25);
      else inner = PUMPKIN(50, 110, 1.2) + PUMPKIN(100, 120, .8) + LEAF(120, 70, 1.1, "#c0392b", 30) + LEAF(20, 70, 1, "#e67e22", -40) + WHEAT(130, 40, 1, 15) + ACORN(84, 76, 1);
    }
    svg.innerHTML = inner; return svg;
  }
  function bunting(width, palette){
    const svg = svgEl("leaves", `0 0 ${width} 60`); svg.setAttribute("preserveAspectRatio", "none");
    const cols = palette || ["#ff6fae", "#5bc0eb", "#f2c14e", "#7cf37c", "#b388ff"]; let s = `<path d="M0 14 Q ${width/2} 40 ${width} 14" stroke="#fff" stroke-width="3" fill="none"/>`;
    const n = Math.floor(width / 48);
    for (let i = 0; i < n; i++){ const x0 = i * (width / n), x1 = (i + 1) * (width / n), t = (x0 + x1) / 2 / width, y = 14 + Math.sin(Math.PI * t) * 26 * 0.5 + 0; s += `<path d="M${x0} ${14 + Math.sin(Math.PI * x0 / width) * 13} L${(x0 + x1) / 2} ${y + 26} L${x1} ${14 + Math.sin(Math.PI * x1 / width) * 13}z" fill="${cols[i % cols.length]}"/>`; }
    svg.innerHTML = s; return svg;
  }
  function leafGarland(width){
    const svg = svgEl("leaves", `0 0 ${width} 60`); svg.setAttribute("preserveAspectRatio", "none");
    const cols = ["#d35400", "#e67e22", "#c0392b", "#f1c40f", "#a04000", "#e8a33d"]; let s = `<path d="M0 22 Q ${width/2} 46 ${width} 22" stroke="#5a3d1a" stroke-width="4" fill="none"/>`;
    const n = Math.floor(width / 34);
    for (let i = 0; i <= n; i++){ const x = i * (width / n), t = x / width, y = 22 + Math.sin(Math.PI * t) * 24; s += LEAF(x, y, .75 + (i % 3) * .12, cols[i % cols.length], (i * 47) % 360); }
    svg.innerHTML = s; return svg;
  }

  /* ---------- little surprises: Santa flies over, a turkey waddles by, bulbs flicker ---------- */
  const SLEIGH = `<svg width="400" height="110" viewBox="0 0 400 110"><g class="bob">
    <g stroke="#caa15a" stroke-width="1.5" fill="none"><path d="M60 62 Q120 50 180 58 Q240 50 300 58"/></g>
    ${[0,1,2].map(i=>`<g transform="translate(${70+i*78},34)"><path d="M10 40 L6 60 M28 40 L32 60 M14 40 L12 60 M24 40 L26 60" stroke="#6b4a2a" stroke-width="3"/><ellipse cx="19" cy="34" rx="20" ry="11" fill="#8b5a2b"/><ellipse cx="38" cy="26" rx="10" ry="8" fill="#9a6a3a"/><path d="M40 18 l4-14 M42 18 l9-10 M46 18 l12-6" stroke="#5a3a1a" stroke-width="2.5" fill="none"/><circle cx="47" cy="25" r="2.6" fill="${i===0?'#ff3b30':'#2a1a0a'}"/><ellipse cx="2" cy="30" rx="4" ry="7" fill="#8b5a2b"/></g>`).join("")}
    <g transform="translate(300,36)"><path d="M0 30 Q-6 48 10 50 H78 Q96 50 92 36 L82 14 H6 Z" fill="#c8102e" stroke="#8a0a1e" stroke-width="2"/><path d="M-4 56 H98" stroke="#caa15a" stroke-width="3"/><path d="M-4 56 q-10 0 -10 -8" stroke="#caa15a" stroke-width="3" fill="none"/>
      <rect x="18" y="0" width="30" height="20" rx="4" fill="#7b4a1e"/><rect x="48" y="-6" width="26" height="26" rx="4" fill="#2e7d32"/><rect x="50" y="-4" width="22" height="22" fill="none" stroke="#ffd23f" stroke-width="2"/>
      <circle cx="12" cy="4" r="9" fill="#f5cfa0"/><path d="M3 2 q9-16 20-2 l-2 2 q-8-8-16 0z" fill="#d32f2f"/><circle cx="24" cy="2" r="3" fill="#fff"/><path d="M4 10 q8 10 16 0 v6 q-8 8 -16 0z" fill="#fff"/><rect x="2" y="14" width="22" height="18" rx="4" fill="#d32f2f"/></g>
    <g fill="#ffd23f">${[0,1,2,3,4,5].map(i=>`<circle cx="${20+i*9}" cy="${70+(i%2)*6}" r="${2-i*0.2}" opacity="${.9-i*.12}"/>`).join("")}</g>
  </g></svg>`;
  let flyEl = null, walkEl = null, flyTimer = null, flickTimer = null;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const SANTA_IMG = "/skins/santa.png";
  const TURKEY_IMG = "/skins/turkey.png";   // painted sprite (green-screen keyed); emoji fallback     // painted sprite (green-screen keyed); vector SLEIGH is the fallback
  let bellCtx = null;
  function sleighBells(){
    try {
      if (typeof FH !== "undefined" && FH.get().speakAlerts === false) return;
      const AC = window.AudioContext || window.webkitAudioContext; if (!AC) return;
      bellCtx = bellCtx || new AC(); const ctx = bellCtx; if (ctx.state === "suspended") ctx.resume();
      const out = ctx.createGain(); out.gain.value = 0.12; out.connect(ctx.destination);
      const t0 = ctx.currentTime + 0.05;
      // a jingle pattern: shakes of 3-4 tiny bells, 9 shakes over ~3 s, fading in then out as Santa passes
      for (let k = 0; k < 9; k++){
        const tk = t0 + k * 0.34 + (k % 2) * 0.05, env = Math.sin(Math.PI * (k + 0.5) / 9);
        for (let b = 0; b < 4; b++){
          const tb = tk + Math.random() * 0.05, f = 2300 + Math.random() * 1700;
          [1, 2.76, 5.4].forEach((m, i) => {
            const o = ctx.createOscillator(), g = ctx.createGain();
            o.type = "sine"; o.frequency.value = f * m;
            g.gain.setValueAtTime(0, tb); g.gain.linearRampToValueAtTime(env * (i ? 0.25 / i : 0.5), tb + 0.004);
            g.gain.exponentialRampToValueAtTime(0.0001, tb + 0.35 - i * 0.08);
            o.connect(g); g.connect(out); o.start(tb); o.stop(tb + 0.4);
          });
        }
      }
    } catch (e) {}
  }
  function santaFly(){
    sleighBells();
    if (!flyEl){ flyEl = document.createElement("div"); flyEl.id = "skin-fly"; document.body.appendChild(flyEl); }
    flyEl.innerHTML = `<div class="bob"><img src="${SANTA_IMG}" alt="" style="width:460px;height:auto;display:block;filter:drop-shadow(0 6px 10px rgba(0,0,0,.45))" onerror="this.parentNode.innerHTML=${JSON.stringify(SLEIGH).replace(/"/g, "&quot;")}"></div>`;
    flyEl.classList.remove("go"); void flyEl.offsetWidth;
    flyEl.style.setProperty("--fly-y", (40 + Math.random() * 80) + "px"); flyEl.style.setProperty("--fly-s", (14 + Math.random() * 6) + "s");
    flyEl.classList.add("go"); setTimeout(() => flyEl && flyEl.classList.remove("go"), 22000);
  }
  function turkeyWalk(){
    if (!walkEl){ walkEl = document.createElement("div"); walkEl.id = "skin-walk"; document.body.appendChild(walkEl); }
    walkEl.innerHTML = `<span><img src="${TURKEY_IMG}" alt="" style="height:120px;width:auto;display:block" onerror="this.parentNode.textContent='🦃'"></span>`; walkEl.classList.remove("go"); void walkEl.offsetWidth;
    walkEl.style.setProperty("--walk-s", (16 + Math.random() * 6) + "s"); walkEl.classList.add("go"); setTimeout(() => walkEl && walkEl.classList.remove("go"), 24000);
  }
  function flickerBulb(){
    const bulbs = frameEl ? frameEl.querySelectorAll(".bulb") : []; if (!bulbs.length) return;
    const b = bulbs[Math.floor(Math.random() * bulbs.length)]; b.classList.add("flick"); setTimeout(() => b.classList.remove("flick"), 1600);
  }
  function startSurprises(kind){
    stopSurprises(); if (reduced) return;
    const painted = !!(DEFS[kind].art && artOn);     // painted frame has its own (static) lights: no bulb flicker
    const nextFly = () => { const m = new Date().getMonth(), d = new Date().getDate(); const base = (kind === "christmas" && m === 11 && d >= 24) ? 2 : 6;   // Christmas Eve/Day: every ~2 min
      flyTimer = setTimeout(() => { if (kind === "christmas") santaFly(); else if (kind === "thanksgiving") turkeyWalk(); nextFly(); }, (base + Math.random() * base) * 60 * 1000); };
    flyTimer = setTimeout(() => { if (kind === "christmas") santaFly(); else if (kind === "thanksgiving") turkeyWalk(); nextFly(); }, 20000);   // first one soon after it comes on
    if (kind === "christmas" && !painted) flickTimer = setInterval(flickerBulb, 7000);
  }
  function stopSurprises(){ clearTimeout(flyTimer); clearInterval(flickTimer); flyTimer = flickTimer = null; if (flyEl) flyEl.classList.remove("go"); if (walkEl) walkEl.classList.remove("go"); }
  function surprise(){ if (current === "christmas") santaFly(); else if (current === "thanksgiving") turkeyWalk(); }

  /* ---------- apply ---------- */
  let current = null, styleEl = null, frameEl = null, bannerEl = null, tick = null, artOn = true, artEl = null, slim = true;
  const SLIM_ZOOM = 1.22;
  function ensure(){
    if (!artEl){ artEl = document.createElement("div"); artEl.id = "skin-art"; document.body.insertBefore(artEl, document.body.firstChild); }
    if (!styleEl){ styleEl = document.createElement("style"); styleEl.id = "skin-css"; styleEl.textContent = css; document.head.appendChild(styleEl); }
    if (!frameEl){ frameEl = document.createElement("div"); frameEl.id = "skin-frame"; document.body.appendChild(frameEl); }
    if (!bannerEl){ bannerEl = document.createElement("div"); bannerEl.id = "skin-banner"; const h = document.querySelector("header"); const d = h && h.querySelector(".date"); if (d && d.nextSibling) h.insertBefore(bannerEl, d.nextSibling); else if (h) h.appendChild(bannerEl); }
  }
  function buildFrame(kind){
    frameEl.innerHTML = ""; const w = window.innerWidth;
    const def = DEFS[kind], root = document.documentElement;
    artEl.style.backgroundImage = "";
    if (def.art && artOn){
      // slim: zoom the painting so its border is cropped partly off-screen -> thinner frame, more room for the panels
      const z = def.art.zoom * (slim ? SLIM_ZOOM : 1);
      const inset = (p, full) => Math.max(40, Math.round(p * z - (z - 1) * full / 2));
      artEl.style.backgroundImage = `url("${def.art.src}")`;
      root.style.setProperty("--skin-art-size", `${Math.round(z * 100)}% ${Math.round(z * 100)}%`);
      root.style.setProperty("--skin-pad-t", inset(def.art.pad.t, 1080) + "px"); root.style.setProperty("--skin-pad-b", inset(def.art.pad.b, 1080) + "px");
      root.style.setProperty("--skin-pad-l", inset(def.art.pad.l, 1920) + "px"); root.style.setProperty("--skin-pad-r", inset(def.art.pad.r, 1920) + "px");
      root.style.setProperty("--skin-hpad", Math.round((def.art.hpad || 0) * z) + "px");
      return;
    }
    ["t","b","l","r"].forEach(k => { const b = document.createElement("div"); b.className = "bar " + k; frameEl.appendChild(b); });
    if (kind === "christmas"){ frameEl.appendChild(snowTop(w)); frameEl.appendChild(lightsString(w - 52, false)); frameEl.appendChild(lightsString(w - 52, true)); }
    else if (kind === "thanksgiving") { frameEl.appendChild(leafGarland(w)); }
    else if (kind === "birthday") { frameEl.appendChild(bunting(w)); }
    else if (kind === "newyear") { frameEl.appendChild(bunting(w, ["#f2cc6b", "#dfe6f2", "#141a33", "#d4b25a", "#9fb4d9"])); }
    ["tl","tr","bl","br"].forEach(c => frameEl.appendChild(corner(kind, c)));
  }
  let fastTick = null, cheered = "";
  function renderBanner(kind){
    const def = DEFS[kind], y = new Date().getFullYear();
    if (kind === "newyear"){
      const now = new Date(), mid = new Date(now.getFullYear() + (now.getMonth() === 11 ? 1 : 0), 0, 1), ms = mid - now;
      const ny = mid.getFullYear();
      if (ms > 0){
        const h = Math.floor(ms / 3600000), mn = Math.floor(ms % 3600000 / 60000), sc = Math.floor(ms % 60000 / 1000);
        const show = h > 0 ? [String(Math.min(h, 99)).padStart(2, "0"), String(mn).padStart(2, "0")] : ms < 120000 ? [String(mn).padStart(2, "0"), String(sc).padStart(2, "0")] : ["00", String(mn).padStart(2, "0")];
        const unit = h > 0 ? "hours · minutes" : ms < 120000 ? "minutes · seconds" : "hours · minutes";
        bannerEl.innerHTML = `<div class="k">${def.banner.kicker}</div><div class="t">${ny}</div><div class="digits">${show.join("").split("").map((d, i) => `<div class="dg">${d}</div>${i === 1 ? '<div class="dg-sep">:</div>' : ""}`).join("")}</div><div class="sub">${unit}</div>`;
        if (ms < 125000 && !fastTick) fastTick = setInterval(() => renderBanner(kind), 1000);
      } else {
        bannerEl.innerHTML = `<div class="k">Happy New Year</div><div class="t">${ny}!</div><div class="sub"><b>🥂 Cheers!</b></div>`;
        if (fastTick){ clearInterval(fastTick); fastTick = null; }
        if (cheered !== String(ny) && ms > -60000){ cheered = String(ny); try { window.dispatchEvent(new CustomEvent("skin:newyear", { detail: { year: ny } })); } catch (e) {} }
      }
      return;
    }
    if (kind === "christmas"){
      const nowd = new Date();
      if (nowd.getMonth() === 11 && nowd.getDate() > 25){
        const n2 = daysUntil(new Date(y + 1, 0, 1)), digits2 = String(Math.max(0, n2)).padStart(2, "0").split("").map(d => `<div class="dg">${d}</div>`).join("");
        bannerEl.innerHTML = `<div class="k">Days until</div><div class="t">New Year's</div><div class="digits">${digits2}</div><div class="sub"><b>Fireworks on the 31st</b></div>`;
        return;
      }
    }
    if (kind === "birthday"){
      const who = birthdayPeople().map(p => p.name.split(" ")[0]);
      const title = who.length ? who.join(" & ") + "!" : "🎉";
      bannerEl.innerHTML = `<div class="k">${def.banner.kicker}</div><div class="t">${title.replace(/</g, "&lt;")}</div><div class="sub"><b>${who.length ? "🎂 Make a wish" : "Party mode"}</b></div>`;
      return;
    }
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
  // The phone loads this file only for the settings menu (list/previews); the painted frame is for the wall.
  const WALL = !/phone\.html$/i.test(location.pathname);
  function apply(settings){
    if (!WALL) return null;
    ensure();
    const kind = pick(settings);
    const root = document.documentElement;
    root.setAttribute("data-skin-banner", (settings && settings.skinBanner === false) ? "off" : "on");
    const wantArt = !(settings && settings.skinArt === false);
    if (wantArt !== artOn){ artOn = wantArt; current = null; }   // rebuild the frame when the art toggle flips
    const wantSlim = !(settings && settings.skinSlim === false);
    if (wantSlim !== slim){ slim = wantSlim; current = null; }
    if (!kind){ if (current){ stopSurprises(); root.removeAttribute("data-skin"); ["--skin-bg","--skin-gold","--skin-wood1","--skin-wood2","--skin-font"].forEach(v => root.style.removeProperty(v)); Object.keys(DEFS.christmas.vars).forEach(v => root.style.removeProperty(v)); frameEl.innerHTML = ""; bannerEl.innerHTML = ""; if (artEl) artEl.style.backgroundImage = ""; current = null; clearInterval(tick); if (typeof FH !== "undefined") FH.apply(FH.get()); } return null; }
    const def = DEFS[kind];
    root.setAttribute("data-skin", kind);
    Object.entries(def.vars).forEach(([k, v]) => root.style.setProperty(k, v));
    root.style.setProperty("--skin-bg", def.bg); root.style.setProperty("--skin-gold", def.gold);
    root.style.setProperty("--skin-wood1", def.wood[0]); root.style.setProperty("--skin-wood2", def.wood[1]); root.style.setProperty("--skin-font", def.banner.font);
    root.setAttribute("data-skin-art", (def.art && artOn) ? "on" : "off");
    root.setAttribute("data-skin-lite", window.innerWidth < 900 ? "on" : "off");   // a phone looking at the wall page: colors only
    if (current !== kind){ buildFrame(kind); current = kind; startSurprises(kind); }
    if (fastTick && kind !== "newyear"){ clearInterval(fastTick); fastTick = null; }
    renderBanner(kind);
    clearInterval(tick); tick = setInterval(() => renderBanner(kind), 60 * 1000);
    return kind;
  }
  window.addEventListener("resize", () => { if (current){ buildFrame(current); document.documentElement.setAttribute("data-skin-lite", window.innerWidth < 900 ? "on" : "off"); } });
  // auto schedule flips at midnight: re-check every 10 minutes
  if (WALL) setInterval(() => { if (typeof FH !== "undefined") { const k = pick(FH.get()); if (k !== current) apply(FH.get()); } }, 10 * 60 * 1000);

  const list = () => Object.keys(DEFS).map(k => ({ key: k, name: DEFS[k].name, emoji: DEFS[k].emoji || (k === "christmas" ? "🎄" : k === "thanksgiving" ? "🦃" : "✨") }));
  return { apply, pick, auto, thanksgiving, DEFS, list, birthdayPeople, effect: () => current ? DEFS[current].effect : null, current: () => current, surprise };
})();
window.Skins = Skins;
