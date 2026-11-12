/* "What ran today": a day timeline of heat/AC, lights, plugs and TVs from Home Assistant's history,
   with the Santee Cooper peak window shaded, plus a power chart when HA has power sensors.
   FHTimeline.render(el) — fetches /api/ha/timeline?day=…, keeps its own day + cache, refreshes each minute. */
(function(){
  const css=`
  .tl{--tl-heat:#d95926; --tl-cool:#3987e5; --tl-light:#c98500; --tl-plug:#199e70; --tl-tv:#9085e9;
      --tl-grid:rgba(255,255,255,.08); --tl-peak:rgba(255,255,255,.07); --tl-good:#3ba55c; --tl-warn:#e0a020;
      color:var(--ink,#eee); font-size:14px}
  .tl-nav{display:flex; align-items:center; justify-content:space-between; gap:8px; margin:4px 0 10px}
  .tl-nav b{font-size:16px} .tl-nav button{border:0; background:var(--panel2,#2a2a2a); color:inherit; border-radius:10px; width:40px; height:36px; font-size:18px}
  .tl-nav button:disabled{opacity:.3}
  .tl-stats{display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px; margin-bottom:12px}
  .tl-stat{background:var(--panel2,#2a2a2a); border-radius:12px; padding:9px 11px}
  .tl-stat small{display:block; color:var(--ink-dim,#aaa); font-size:12px} .tl-stat b{font-size:19px; font-variant-numeric:tabular-nums}
  .tl-stat .ok{color:var(--tl-good)} .tl-stat .bad{color:var(--tl-warn)}
  .tl-card{background:var(--panel2,#222); border-radius:14px; padding:10px 10px 6px; margin-bottom:12px; position:relative}
  .tl-card h4{margin:0 0 2px; font-size:13px; letter-spacing:.06em; text-transform:uppercase; color:var(--ink-dim,#aaa)}
  .tl-legend{display:flex; flex-wrap:wrap; gap:4px 12px; font-size:12.5px; color:var(--ink-dim,#aaa); margin:4px 0 6px}
  .tl-legend i{display:inline-block; width:12px; height:8px; border-radius:2px; margin-right:5px; vertical-align:middle}
  .tl svg{display:block; width:100%; overflow:visible; touch-action:pan-y}
  .tl svg text{fill:var(--ink-dim,#aaa); font-size:11px}
  .tl svg .nm{fill:var(--ink,#eee); font-size:12px}
  .tl svg .gh{fill:var(--ink-dim,#aaa); font-size:11px; letter-spacing:.06em; text-transform:uppercase; font-weight:700}
  .tl-tip{position:absolute; pointer-events:none; background:#0d0d0c; color:#f0efec; border:1px solid rgba(255,255,255,.15); border-radius:9px;
     padding:6px 9px; font-size:12.5px; line-height:1.35; white-space:nowrap; transform:translate(-50%,-100%); display:none; z-index:3}
  .tl details{margin-top:4px} .tl summary{color:var(--ink-dim,#aaa); font-size:13px; cursor:pointer; padding:4px 0}
  .tl table{width:100%; border-collapse:collapse; font-size:13px} .tl td{padding:4px 2px; border-bottom:1px solid var(--tl-grid); vertical-align:top}
  .tl td:last-child{text-align:right; color:var(--ink-dim,#aaa); font-variant-numeric:tabular-nums}
  .tl-empty{color:var(--ink-dim,#aaa); padding:14px 4px}`;
  let styled=false, day=null, cache={}, timer=null, host=null;
  const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  const iso=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
  const clock=m=>{ m=Math.round(m); const h=Math.floor(m/60)%24, mm=m%60; return `${(h%12)||12}${mm?":"+String(mm).padStart(2,"0"):""} ${h<12?"AM":"PM"}`; };
  const dur=m=>{ m=Math.round(m); if(m<60) return m+" min"; const h=Math.floor(m/60), r=m%60; return h+"h"+(r?" "+r+"m":""); };
  const COLOR={heat:"var(--tl-heat)", cool:"var(--tl-cool)", light:"var(--tl-light)", plug:"var(--tl-plug)", tv:"var(--tl-tv)"};
  const GROUP={climate:"Heating & cooling", light:"Lights", plug:"Plugs & switches", tv:"TVs"};

  async function load(force){
    const d=day||iso(new Date());
    if(!force&&cache[d]) return cache[d];
    try{ cache[d]=await fetch("/api/ha/timeline?day="+d).then(r=>r.json()); }catch(e){ cache[d]={ok:false, reason:"Couldn’t load the day"}; }
    return cache[d];
  }

  function lanes(data, W){
    const L=0, R=W, x=m=>L+(R-L)*m/1440, rows=data.rows||[];
    const LANE=30, GH=22, TOP=18;
    let y=TOP, out="", lastK=null;
    const [p0,p1]=data.peak||[0,0];
    const groups=[...new Set(rows.map(r=>r.kind))];
    const H=TOP+rows.length*LANE+groups.length*GH+6;
    out+=`<rect x="${x(p0)}" y="0" width="${x(p1)-x(p0)}" height="${H}" fill="var(--tl-peak)"/>`;
    out+=`<text x="${(x(p0)+x(p1))/2}" y="11" text-anchor="middle">Peak</text>`;
    [0,360,720,1080,1440].forEach(m=>{ out+=`<line x1="${x(m)}" x2="${x(m)}" y1="16" y2="${H}" stroke="var(--tl-grid)"/>`; });
    rows.forEach((r,i)=>{
      if(r.kind!==lastK){ y+=GH; out+=`<text class="gh" x="0" y="${y-6}">${GROUP[r.kind]}</text>`; lastK=r.kind; }
      out+=`<text class="nm" x="0" y="${y+11}">${esc(r.name.replace(/\s*thermostat\s*/i," ").trim())}</text>`;
      out+=`<rect x="${L}" y="${y+16}" width="${R-L}" height="8" rx="3" fill="var(--tl-grid)"/>`;
      (r.spans||[]).forEach(([a,b,k])=>{
        const c=r.kind==="climate"?COLOR[k]:COLOR[r.kind], w=Math.max(2,x(b)-x(a));
        out+=`<rect class="sp" x="${x(a)}" y="${y+15}" width="${w}" height="10" rx="3" fill="${c}"
           data-tip="${esc(r.name)} · ${r.kind==="climate"?(k==="heat"?"heating":"cooling"):"on"}<br>${clock(a)} – ${clock(b)} (${dur(b-a)})"/>`;
        out+=`<rect class="hit" x="${x(a)-4}" y="${y+6}" width="${w+8}" height="24" fill="transparent" data-tip="${esc(r.name)} · ${r.kind==="climate"?(k==="heat"?"heating":"cooling"):"on"}<br>${clock(a)} – ${clock(b)} (${dur(b-a)})"/>`;
      });
      y+=LANE;
    });
    if(data.now_min!=null) out+=`<line x1="${x(data.now_min)}" x2="${x(data.now_min)}" y1="14" y2="${H}" stroke="var(--ink,#eee)" stroke-width="1.5" stroke-dasharray="3 3"/>`;
    const axis=[0,360,720,1080,1440].map((m,i)=>`<text x="${x(m)}" y="${H+14}" text-anchor="${i===0?"start":i===4?"end":"middle"}">${["12 AM","6 AM","12 PM","6 PM","12 AM"][i]}</text>`).join("");
    return `<svg viewBox="0 0 ${W} ${H+18}" height="${H+18}">${out}${axis}</svg>`;
  }

  function powerChart(p, data, W){
    const H=120, T=8, B=H-18, pts=p.points; if(pts.length<2) return "";
    const max=Math.max(1000, ...pts.map(q=>q[1]))*1.1, x=m=>W*m/1440, y=v=>B-(B-T)*v/max;
    const [p0,p1]=data.peak||[0,0];
    let d=""; pts.forEach(([m,v],i)=>{ d+=(i?" L":"M")+x(m).toFixed(1)+" "+y(v).toFixed(1); });
    const area=d+` L${x(pts[pts.length-1][0]).toFixed(1)} ${B} L${x(pts[0][0]).toFixed(1)} ${B} Z`;
    const kw=v=>v>=1000?(v/1000).toFixed(1)+" kW":Math.round(v)+" W";
    const grid=[max/2, max/1.1].map(v=>`<line x1="0" x2="${W}" y1="${y(v)}" y2="${y(v)}" stroke="var(--tl-grid)"/>`).join("")+`<line x1="0" x2="${W}" y1="${B}" y2="${B}" stroke="var(--tl-grid)"/>`
      ; const labels=[max/2, max/1.1].map(v=>`<text x="2" y="${y(v)+12}" style="paint-order:stroke; stroke:var(--panel2,#222); stroke-width:3px">${kw(v)}</text>`).join("");
    const axis=[0,360,720,1080,1440].map((m,i)=>`<text x="${x(m)}" y="${H-2}" text-anchor="${i===0?"start":i===4?"end":"middle"}">${["12 AM","6 AM","12 PM","6 PM","12 AM"][i]}</text>`).join("");
    return `<svg class="pw" viewBox="0 0 ${W} ${H}" height="${H}" data-max="${max}" data-pts='${JSON.stringify(pts)}'>
      <rect x="${x(p0)}" y="0" width="${x(p1)-x(p0)}" height="${B}" fill="var(--tl-peak)"/>${grid}
      <path d="${area}" fill="var(--tl-cool)" opacity=".18"/><path d="${d}" fill="none" stroke="var(--tl-cool)" stroke-width="2" stroke-linejoin="round"/>${labels}
      <line class="xh" x1="0" x2="0" y1="${T}" y2="${B}" stroke="var(--ink,#eee)" stroke-width="1" visibility="hidden"/>
      <circle class="xd" r="4" fill="var(--tl-cool)" stroke="#1a1a19" stroke-width="2" visibility="hidden"/>${axis}</svg>`;
  }

  function stats(data){
    const s=data.stats||{}, hv=(s.heat_min||0)+(s.cool_min||0), pk=s.hvac_peak_min||0;
    return `<div class="tl-stats">
      <div class="tl-stat"><small>Heat ran</small><b>${dur(s.heat_min||0)}</b></div>
      <div class="tl-stat"><small>AC ran</small><b>${dur(s.cool_min||0)}</b></div>
      <div class="tl-stat"><small>Heat/AC during peak</small><b class="${pk?"bad":"ok"}">${pk?"⚠ "+dur(pk):"✓ none"}</b></div>
      <div class="tl-stat"><small>Light-hours</small><b>${((s.light_min||0)/60).toFixed(1)} h</b></div></div>`;
  }

  function table(data){
    const rows=(data.rows||[]).filter(r=>r.spans&&r.spans.length);
    if(!rows.length) return "";
    return `<details><summary>Show as a list</summary><table>${rows.map(r=>`<tr><td>${esc(r.name)}</td><td>${r.spans.map(([a,b,k])=>
      `${clock(a)}–${clock(b)}${r.kind==="climate"?" "+(k==="heat"?"heat":"AC"):""}`).join("<br>")}</td></tr>`).join("")}</table></details>`;
  }

  function bindTips(card){
    const tip=card.querySelector(".tl-tip");
    const show=(e,html)=>{ const r=card.getBoundingClientRect(); tip.innerHTML=html; tip.style.display="block";
      const px=Math.min(r.width-70, Math.max(70, e.clientX-r.left)); tip.style.left=px+"px"; tip.style.top=(e.clientY-r.top-10)+"px"; };
    card.querySelectorAll(".hit").forEach(h=>{ h.addEventListener("pointerenter",e=>show(e,h.dataset.tip)); h.addEventListener("pointerdown",e=>show(e,h.dataset.tip));
      h.addEventListener("pointerleave",()=>{ tip.style.display="none"; }); });
    const pw=card.querySelector("svg.pw"); if(!pw) return;
    const pts=JSON.parse(pw.dataset.pts), max=+pw.dataset.max, xh=pw.querySelector(".xh"), xd=pw.querySelector(".xd");
    const move=e=>{ const r=pw.getBoundingClientRect(), vb=pw.viewBox.baseVal, m=(e.clientX-r.left)/r.width*1440;
      let best=pts[0]; pts.forEach(q=>{ if(Math.abs(q[0]-m)<Math.abs(best[0]-m)) best=q; });
      const X=vb.width*best[0]/1440, Y=(vb.height-18)-((vb.height-18)-8)*best[1]/max;
      xh.setAttribute("x1",X); xh.setAttribute("x2",X); xh.setAttribute("visibility","visible"); xd.setAttribute("cx",X); xd.setAttribute("cy",Y); xd.setAttribute("visibility","visible");
      show(e, `${clock(best[0])}<br><b>${best[1]>=1000?(best[1]/1000).toFixed(2)+" kW":best[1]+" W"}</b>`); };
    pw.addEventListener("pointermove",move); pw.addEventListener("pointerdown",move);
    pw.addEventListener("pointerleave",()=>{ tip.style.display="none"; xh.setAttribute("visibility","hidden"); xd.setAttribute("visibility","hidden"); });
  }

  async function draw(el, force){
    host=el;
    const data=await load(force); if(host!==el) return;
    const today=iso(new Date()), d=day||today, dd=new Date(d+"T12:00:00");
    const label=d===today?"Today":dd.toLocaleDateString([], {weekday:"long", month:"short", day:"numeric"});
    const W=Math.max(280, Math.round(el.clientWidth||340)-20);
    let html=`<div class="tl"><div class="tl-nav"><button data-tl="-1" aria-label="Previous day">‹</button><b>${label}</b><button data-tl="1" aria-label="Next day" ${d>=today?"disabled":""}>›</button></div>`;
    if(!data.ok){ html+=`<div class="tl-empty">${esc(data.reason||"Couldn’t load the day")}</div></div>`; el.innerHTML=html; bindNav(el); return; }
    html+=stats(data);
    html+=`<div class="tl-card"><h4>What ran when</h4><div class="tl-legend"><span><i style="background:var(--tl-heat)"></i>Heat</span><span><i style="background:var(--tl-cool)"></i>AC</span>
      <span><i style="background:var(--tl-light)"></i>Lights</span><span><i style="background:var(--tl-plug)"></i>Plugs</span><span><i style="background:var(--tl-tv)"></i>TVs</span>
      <span><i style="background:rgba(255,255,255,.18)"></i>Peak hours</span></div>
      ${(data.rows||[]).length?lanes(data,W):'<div class="tl-empty">Nothing in Home Assistant’s history for this day.</div>'}${table(data)}<div class="tl-tip"></div></div>`;
    (data.power||[]).slice(0,3).forEach(p=>{ html+=`<div class="tl-card"><h4>Power · ${esc(p.name)}</h4>${powerChart(p,data,W)}<div class="tl-tip"></div></div>`; });
    if(!(data.power||[]).length) html+=`<div class="tl-empty" style="font-size:13px">No power meter in Home Assistant yet, so this shows when things ran, not watts. Heat/AC is the big one: every heating or cooling bar is the most power the house uses.</div>`;
    html+="</div>";
    el.innerHTML=html; bindNav(el); el.querySelectorAll(".tl-card").forEach(bindTips);
  }
  function bindNav(el){
    el.querySelectorAll("[data-tl]").forEach(b=>b.onclick=()=>{ const cur=new Date((day||iso(new Date()))+"T12:00:00"); cur.setDate(cur.getDate()+(+b.dataset.tl));
      const t=iso(new Date()); day=iso(cur)>=t?null:iso(cur); draw(el); });
  }
  function render(el){
    if(!styled){ const s=document.createElement("style"); s.textContent=css; document.head.appendChild(s); styled=true; }
    draw(el);
    clearInterval(timer); timer=setInterval(()=>{ if(host&&document.body.contains(host)&&!document.hidden&&!day) draw(host,true); else if(!host||!document.body.contains(host)) clearInterval(timer); }, 60000);
  }
  window.FHTimeline={render};
})();
