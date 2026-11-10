/* Shared smart-home pieces used by BOTH the wall (index.html) and the phone (phone.html):
   the house layout, the 2D floor-plan + isometric 3D renderers, and tile helpers.
   Each page supplies its own callbacks: FHHome.toggle(eid), FHHome.remote(eid,name),
   FHHome.rerender(). Keep this file dependency-free (uses FH from theme.js for the layout). */
(function(){
  const esc=s=>String(s==null?"":s).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));

  /* The home's real layout, traced from the D.R. Horton plan. Units are FEET
     (1 cell = 1 ft, 0.5 ft steps) and the plan is MIRRORED so the garage is on
     the RIGHT, matching the house. `floor` 1 = downstairs, 2 = upstairs; both
     floors share the same 38 ft x 58 ft footprint so they stack in 3D (the patio
     row is y 0-8, the house's back wall is y 8). Keys are HA name hints. */
  const DEFAULT_LAYOUT=[
    {floor:1, name:"Patio",      key:"patio",     gx:0,    gy:0,    gw:9.5, gd:8},
    {floor:1, name:"Dining",     key:"dining",    gx:0,    gy:8,    gw:13,  gd:13},
    {floor:1, name:"Living",     key:"living",    gx:13,   gy:8,    gw:14,  gd:19.5},
    {floor:1, name:"Bedroom 4",  key:"bedroom 4", gx:27,   gy:8,    gw:11,  gd:13.5},
    {floor:1, name:"Kitchen",    key:"kitchen",   gx:0,    gy:21,   gw:13,  gd:11.5},
    {floor:1, name:"Closet",     key:"closet 4",  gx:27,   gy:21.5, gw:5,   gd:6},
    {floor:1, name:"Bath 2",     key:"bath 2",    gx:32,   gy:21.5, gw:6,   gd:10},
    {floor:1, name:"Hall",       key:"hall",      gx:13,   gy:27.5, gw:19,  gd:7},
    {floor:1, name:"Butler's",   key:"butler",    gx:0,    gy:32.5, gw:5.5, gd:8},
    {floor:1, name:"Pantry",     key:"pantry",    gx:5.5,  gy:32.5, gw:7.5, gd:8},
    {floor:1, name:"Foyer",      key:"foyer",     gx:13,   gy:34.5, gw:6,   gd:18},
    {floor:1, name:"Garage",     key:"garage",    gx:19,   gy:34.5, gw:19,  gd:22},
    {floor:1, name:"Flex Room",  key:"flex",      gx:0,    gy:40.5, gw:13,  gd:12},
    {floor:1, name:"Porch",      key:"porch",     gx:0,    gy:52.5, gw:19,  gd:5.5},
    {floor:2, name:"Bath 1",        key:"bath 1",        gx:0,    gy:8,    gw:13.5, gd:13.5},
    {floor:2, name:"Bedroom 1",     key:"master",        gx:13.5, gy:8,    gw:15,   gd:13.5},
    {floor:2, name:"Sitting",       key:"sitting",       gx:28.5, gy:8,    gw:9.5,  gd:13.5},
    {floor:2, name:"Loft",          key:"loft",          gx:0,    gy:21.5, gw:18.5, gd:17},
    {floor:2, name:"Hall",          key:"upstairs hall", gx:18.5, gy:21.5, gw:5,    gd:5},
    {floor:2, name:"Master Closet", key:"master closet", gx:23.5, gy:21.5, gw:14.5, gd:5},
    {floor:2, name:"Stairs",        key:"stairs",        gx:18.5, gy:26.5, gw:10,   gd:12},
    {floor:2, name:"Laundry",       key:"laundry",       gx:28.5, gy:26.5, gw:9.5,  gd:9},
    {floor:2, name:"Closet",        key:"closet 2",      gx:31.5, gy:35.5, gw:6.5,  gd:4},
    {floor:2, name:"Bedroom 3",     key:"bedroom 3",     gx:0,    gy:38.5, gw:18.5, gd:13.5},
    {floor:2, name:"Bath 3",        key:"bath 3",        gx:18.5, gy:38.5, gw:6,    gd:13.5},
    {floor:2, name:"Bedroom 2",     key:"bedroom 2",     gx:24.5, gy:39.5, gw:13.5, gd:12.5},
  ];

  const HA_ICON = {
    light:"\u{1F4A1}", switch:"\u{1F50C}", fan:"\u{1F32C}️", cover:"\u{1F6AA}",
    lock:"\u{1F512}", climate:"\u{1F321}️", media_player:"\u{1F4FA}",
    scene:"✨", script:"▶️", alarm_control_panel:"\u{1F6E1}️",
    binary_sensor:"\u{1F6A6}", sensor:"\u{1F321}️"
  };
  function haIcon(t){
    if(t.domain==="lock") return t.state==="locked"?"\u{1F512}":"\u{1F513}";
    if(t.domain==="binary_sensor" && t.device_class==="motion") return "\u{1F3C3}";
    if(t.domain==="sensor" && t.device_class==="humidity") return "\u{1F4A7}";
    return HA_ICON[t.domain] || "⚙️";
  }
  function haStateLabel(t){
    if(t.domain==="climate"){
      const cur=t.current_temperature, tgt=t.target_temperature;
      return (cur!=null?cur+"° now":"") + (tgt!=null?" → "+tgt+"°":"") || t.state;
    }
    if(t.domain==="sensor") return (t.state||"")+(t.unit||"");
    if(t.domain==="scene"||t.domain==="script") return "Tap to run";
    const nice={on:"On",off:"Off",open:"Open",closed:"Closed",locked:"Locked",
      unlocked:"Unlocked",playing:"Playing",paused:"Paused",idle:"Idle",standby:"Standby",disarmed:"Disarmed",
      armed_home:"Armed (home)",armed_away:"Armed (away)",armed_night:"Armed (night)",unavailable:"Unavailable"};
    return nice[t.state] || t.state || "";
  }

  let homeFloor=1;
  const floorsIn=rooms=>[...new Set(rooms.map(r=>r.floor||1))].sort((a,b)=>a-b);
  function floorSwitcherHTML(rooms){
    const fs=floorsIn(rooms); if(fs.length<2) return "";
    return '<div class="fp-floors">'+fs.map(f=>
      `<button class="fp-fbtn${f===homeFloor?' active':''}" data-floor="${f}">${f===1?'Downstairs':f===2?'Upstairs':'Floor '+f}</button>`
    ).join("")+'</div>';
  }
  function bindFloorBtns(box){
    box.querySelectorAll(".fp-fbtn").forEach(b=>{ b.onclick=()=>{ homeFloor=+b.dataset.floor; FHHome.rerender(); }; });
  }
  function getLayout(){ const c=(window.FH&&FH.get().homeLayout); return (Array.isArray(c)&&c.length)?c:DEFAULT_LAYOUT; }
  function layoutExtent(rooms){ let m=0; rooms.forEach(r=>{ m=Math.max(m,r.gx+r.gw,r.gy+r.gd); }); return m||1; }
  function isCustomLayout(){ const c=(window.FH&&FH.get().homeLayout); return Array.isArray(c)&&c.length>0; }
  function tilesOf(h){ return (h.groups||[]).reduce((a,g)=>a.concat(g.tiles||[]),[]); }
  function resolveRooms(h){
    const tiles=tilesOf(h);
    const lc=s=>String(s||"").toLowerCase();
    const byId=id=>tiles.find(t=>t.entity_id===id);
    const byKey=(dom,k,dc)=>tiles.find(t=>t.domain===dom&&(!dc||t.device_class===dc)&&(lc(t.name).includes(lc(k))||lc(t.area||"").includes(lc(k))));
    return getLayout().map(r=>{
      const light=(r.light&&byId(r.light))||byKey("light",r.key);
      const cover=(r.cover&&byId(r.cover))||byKey("cover",r.key);
      const temp =(r.temp &&byId(r.temp)) ||byKey("sensor",r.key,"temperature");
      const media=byKey("media_player",r.key);
      const ctrl=light||cover;
      const on=light?light.on:(cover?cover.state!=="closed":(media?media.on:false));
      return {...r, light, cover, temp, media, ctrl, on};
    });
  }
  const fpNote=()=>'<div class="fp-note">Tap a room to toggle its light. Rooms light up as devices get an Area in Home Assistant.</div>';

  function renderFloorView(body,h,opts){
    opts=opts||{}; const all=resolveRooms(h);
    const fs=floorsIn(all); if(!fs.includes(homeFloor)) homeFloor=fs[0]||1;
    const rooms=all.filter(r=>(r.floor||1)===homeFloor);
    const budget=opts.budget||760;
    const CELL=Math.max(10,Math.min(74,budget/layoutExtent(all))), GAP=Math.min(4,CELL/6), RX=Math.min(10,CELL/2);
    let maxX=0,maxY=0; rooms.forEach(r=>{ maxX=Math.max(maxX,r.gx+r.gw); maxY=Math.max(maxY,r.gy+r.gd); });
    const W=maxX*CELL, H=maxY*CELL, P=10, small=CELL<16;
    let svg=`<div class="fp"><svg viewBox="${-P} ${-P} ${W+P*2} ${H+P*2}" role="img" aria-label="Floor plan">`;
    svg+=`<rect x="${-P/2}" y="${-P/2}" width="${W+P}" height="${H+P}" rx="14" fill="none" stroke="var(--line)" stroke-width="3"/>`;
    rooms.forEach((r,i)=>{
      const x=r.gx*CELL+GAP, y=r.gy*CELL+GAP, w=r.gw*CELL-GAP*2, hh=r.gd*CELL-GAP*2;
      const fits=w>CELL*4.5&&hh>CELL*2.2;
      svg+=`<g class="room${r.on?' on':''}${r.ctrl||r.media?' has':''}" data-i="${i}">`+
        `<rect x="${x}" y="${y}" width="${w}" height="${hh}" rx="${RX}"/>`+
        (fits?`<text class="rname" x="${x+10}" y="${y+(small?14:22)}">${esc(r.name)}</text>`:"")+
        (fits&&r.temp?`<text class="rtemp" x="${x+10}" y="${y+(small?27:40)}">${esc(r.temp.state)}${esc(r.temp.unit||"°")}</text>`:"")+
        ((r.ctrl||r.media)?`<circle class="rdot" cx="${x+w-12}" cy="${y+12}" r="${small?4:6}"/>`:"")+
      '</g>';
    });
    svg+='</svg></div>';
    body.innerHTML=floorSwitcherHTML(all)+svg+(opts.note===false?"":fpNote());
    bindFloorBtns(body);
    body.querySelectorAll(".room").forEach(g=>{
      const r=rooms[+g.dataset.i];
      if(r.ctrl) g.onclick=()=>FHHome.toggle(r.ctrl.entity_id);
      else if(r.media) g.onclick=()=>FHHome.remote(r.media.entity_id, r.media.name);
      else g.style.cursor="default";
    });
  }

  function renderIsoView(body,h,opts){
    opts=opts||{}; const all=resolveRooms(h);
    const TW=Math.max(8,Math.min(34,34*9.5/layoutExtent(all))), TH=TW/2, WH=TW*0.76;
    const iso=(gx,gy)=>[(gx-gy)*TW,(gx+gy)*TH];
    const fs=floorsIn(all); if(!fs.includes(homeFloor)) homeFloor=fs[0]||1;
    const rooms=all.filter(r=>(r.floor||1)===homeFloor).sort((a,b)=>(a.gx+a.gy)-(b.gx+b.gy));
    const pts=[]; let gEls="";
    rooms.forEach((r,i)=>{
      const p1=iso(r.gx,r.gy), p2=iso(r.gx+r.gw,r.gy), p3=iso(r.gx+r.gw,r.gy+r.gd), p4=iso(r.gx,r.gy+r.gd);
      const dn=p=>[p[0],p[1]+WH], p2d=dn(p2), p3d=dn(p3), p4d=dn(p4);
      [p1,p2,p3,p4,p2d,p3d,p4d].forEach(p=>pts.push(p));
      const poly=a=>a.map(p=>p[0].toFixed(1)+","+p[1].toFixed(1)).join(" ");
      const cx=(p1[0]+p3[0])/2, cy=(p1[1]+p3[1])/2;
      const big=r.gw*r.gd>60;
      gEls+=`<g class="r3d${r.on?' on':''}" data-i="${i}">`+
        `<polygon class="wl-r" points="${poly([p2,p3,p3d,p2d])}"/>`+
        `<polygon class="wl-f" points="${poly([p4,p3,p3d,p4d])}"/>`+
        `<polygon class="top" points="${poly([p1,p2,p3,p4])}"/>`+
        (big?`<text class="rlbl" x="${cx.toFixed(1)}" y="${(cy+2).toFixed(1)}">${esc(r.name)}</text>`:"")+
        (big&&r.temp?`<text class="rlbl rtmp" x="${cx.toFixed(1)}" y="${(cy+15).toFixed(1)}">${esc(r.temp.state)}${esc(r.temp.unit||"°")}</text>`:"")+
      '</g>';
    });
    const xs=pts.map(p=>p[0]), ys=pts.map(p=>p[1]), pad=26;
    const minX=Math.min(...xs)-pad, minY=Math.min(...ys)-pad;
    const vw=Math.max(...xs)-Math.min(...xs)+pad*2, vh=Math.max(...ys)-Math.min(...ys)+pad*2;
    let html=floorSwitcherHTML(all);
    html+=`<div class="iso"><svg viewBox="${minX.toFixed(1)} ${minY.toFixed(1)} ${vw.toFixed(1)} ${vh.toFixed(1)}" role="img" aria-label="3D home">${gEls}</svg></div>`;
    html+='<div class="iso-list">'+rooms.filter(r=>r.ctrl).map(r=>
      `<span class="iso-chip${r.on?' on':''}" data-eid="${esc(r.ctrl.entity_id)}">${esc(r.name)}${r.temp?' · '+esc(r.temp.state)+esc(r.temp.unit||"°"):''}</span>`).join("")+'</div>';
    if(opts.note!==false) html+=fpNote();
    body.innerHTML=html;
    bindFloorBtns(body);
    body.querySelectorAll(".r3d").forEach(g=>{ const r=rooms[+g.dataset.i]; if(r.ctrl) g.onclick=()=>FHHome.toggle(r.ctrl.entity_id); else g.style.cursor="default"; });
    body.querySelectorAll(".iso-chip").forEach(c=>{ c.onclick=()=>FHHome.toggle(c.dataset.eid); });
  }

  window.FHHome = {
    DEFAULT_LAYOUT, HA_ICON, haIcon, haStateLabel, esc,
    getLayout, layoutExtent, isCustomLayout, resolveRooms, tilesOf, floorsIn,
    renderFloorView, renderIsoView,
    get floor(){ return homeFloor; }, set floor(f){ homeFloor=f; },
    // pages override these
    toggle:function(){}, remote:function(){}, rerender:function(){}
  };
})();
