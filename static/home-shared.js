/* Shared smart-home pieces used by BOTH the wall (index.html) and the phone (phone.html):
   the house layout, the 2D floor-plan + isometric 3D renderers, and tile helpers.
   Each page supplies its own callbacks: FHHome.toggle(eid), FHHome.remote(eid,name),
   FHHome.rerender(). Keep this file dependency-free (uses FH from theme.js for the layout). */
(function(){
  const esc=s=>String(s==null?"":s).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));

  /* The home's real layout, traced from the D.R. Horton "two story" plan sheets.
     Units are FEET. Everything below is written AS DRAWN on the sheet (garage on the
     LEFT) and then mirrored in code, because the house was built as the mirror image
     (garage on the RIGHT). x runs left→right across the 38 ft front, gy runs from the
     patio (0) through the back wall (8) to the front porch (~57). `floor` 1 = down,
     2 = up. `key` is the Home Assistant name/area hint. Optional furnishing hints:
     bed/tv/counter/desk = which wall ("n" back, "s" front, "e", "w") the piece sits on; table = which half the dining
     table takes ("c" centred); train = the half the village train table takes; fireplace (under the TV),
     sectional (an L couch instead of a sofa), screened (porch with screens + a ceiling fan). */
  const PLAN_W=38, MIRROR=true, Y0=2;   // Y0: the screened porch sticks 2 ft past the drawn patio, so shift everything down
  const ROOMS_DRAWN=[
    // ---- first floor ----
    {floor:1, name:"Back Porch", key:"patio",     gx:26,   gy:-2,   gw:12,   gd:10,   open:true, screened:true},   // the 12x10 screened porch option
    {floor:1, name:"Office",    key:"office",    gx:0,    gy:8,    gw:11,   gd:13,   desk:"e", tv:"w"},   // bedroom 4, used as the office
    {floor:1, name:"Living",    key:"living",    gx:11,   gy:8,    gw:14,   gd:18,   tv:"w", fireplace:true, sectional:true},
    {floor:1, name:"Breakfast", key:"breakfast", gx:25,   gy:8,    gw:13,   gd:13.4, table:"w", train:"e"},   // eat-in table + the village train
    {floor:1, name:"Kitchen",   key:"kitchen",   gx:25,   gy:21.4, gw:13,   gd:10.4, counter:"e"},
    {floor:1, name:"Bath 2",    key:"bath 2",    gx:0,    gy:21,   gw:6,    gd:10,   tub:"n"},
    {floor:1, name:"Closet",    key:"closet 4",  gx:6,    gy:21,   gw:5,    gd:5},
    {floor:1, name:"Hall",      key:"hall",      gx:6,    gy:26,   gw:19,   gd:10.2, stairs:{gx:13.2, gy:27.1, gw:7, gd:7.4, up:"n"}},
    {floor:1, name:"Mud Room",  key:"mud",       gx:0,    gy:31,   gw:6,    gd:5.2},
    {floor:1, name:"Garage",    key:"garage",    gx:0,    gy:36.2, gw:19.3, gd:20},
    {floor:1, name:"Foyer",     key:"foyer",     gx:19.3, gy:36.2, gw:5.7,  gd:16},
    {floor:1, name:"Pantry",    key:"pantry",    gx:25,   gy:31.8, gw:7.7,  gd:8.7},
    {floor:1, name:"Butler's",  key:"butler",    gx:32.7, gy:31.8, gw:5.3,  gd:8.7},
    {floor:1, name:"Dining Room", key:"dining room", gx:25, gy:40.5, gw:13,   gd:11.7, table:"c"},     // the flex room, used as the dining room
    {floor:1, name:"Front Porch", key:"porch",     gx:19.3, gy:52.2, gw:18.7, gd:5,    open:true},
    // ---- second floor ----
    {floor:2, name:"Sitting",       key:"sitting",       gx:0,    gy:8,    gw:9.5,  gd:13.8, tree:true},
    {floor:2, name:"Bedroom 1",     key:"master",        gx:9.5,  gy:8,    gw:15.3, gd:13.8, bed:"n", tv:"s"},
    {floor:2, name:"Bath 1",        key:"bath 1",        gx:24.8, gy:8,    gw:13.2, gd:13.8, tub:"none", shower:"ne"},   // walk-in glass shower, no tub
    {floor:2, name:"Master Closet", key:"master closet", gx:0,    gy:21.8, gw:19.3, gd:5.8},
    {floor:2, name:"Loft",          key:"loft",          gx:19.3, gy:21.8, gw:18.7, gd:18.5, tv:"s", sectional:true, treeT:0.9},   // TV on the bedroom-3 wall, tree by the windows
    {floor:2, name:"Laundry",       key:"laundry",       gx:0,    gy:27.6, gw:9.5,  gd:7.5},
    {floor:2, name:"Hall",          key:"upstairs hall", gx:9.5,  gy:27.6, gw:9.8,  gd:12.7, stairwell:{gx:9.5, gy:27.6, gw:3.8, gd:7.5}},
    {floor:2, name:"Closet",        key:"closet 2",      gx:0,    gy:35.1, gw:5.8,  gd:5.2},
    {floor:2, name:"Linen",         key:"linen",         gx:5.8,  gy:35.1, gw:3.7,  gd:5.2},
    {floor:2, name:"Bedroom 2",     key:"bedroom 2",     gx:0,    gy:40.3, gw:13.3, gd:12,   bed:"e"},
    {floor:2, name:"Bath 3",        key:"bath 3",        gx:13.3, gy:40.3, gw:6,    gd:10.8, tub:"s"},
    {floor:2, name:"Bedroom 3",     key:"bedroom 3",     gx:19.3, gy:40.3, gw:18.7, gd:12,   bed:"e"},
  ];
  /* Doors and windows, as drawn. dir "h" = sits in a wall that runs left-right (at gy),
     dir "v" = sits in a wall that runs front-back (at gx). x/z is the opening's centre,
     w its width. Types: door, double, opening (cased opening, no leaf), slider, front, garage. */
  const DOORS_DRAWN=[
    // first floor
    {f:1, dir:"h", x:22.2, z:52.2, w:3,   type:"front"},
    {f:1, dir:"h", x:9.65, z:56.2, w:16,  type:"garage"},
    {f:1, dir:"v", x:19.3, z:39,   w:3,   type:"door"},      // garage -> foyer
    {f:1, dir:"h", x:17,   z:36.2, w:3,   type:"door"},      // garage -> hall
    {f:1, dir:"v", x:25,   z:46.3, w:8,   type:"opening"},   // foyer <-> dining room
    {f:1, dir:"h", x:22.2, z:36.2, w:5.7, type:"opening"},   // foyer <-> hall
    {f:1, dir:"h", x:18,   z:26,   w:12,  type:"opening"},   // hall <-> living
    {f:1, dir:"v", x:25,   z:26,   w:9,   type:"opening"},   // kitchen open to living + hall
    {f:1, dir:"v", x:25,   z:14.7, w:12,  type:"opening"},   // living <-> dining
    {f:1, dir:"h", x:33,   z:8,    w:6,   type:"slider"},    // breakfast -> back porch
    {f:1, dir:"h", x:35.3, z:31.8, w:3,   type:"door"},      // kitchen -> butler's
    {f:1, dir:"v", x:25,   z:36,   w:3,   type:"door"},      // pantry (from hall)
    {f:1, dir:"v", x:32.7, z:36,   w:2.5, type:"door"},      // pantry <-> butler's
    {f:1, dir:"h", x:8.5,  z:21,   w:2.8, type:"door"},      // bedroom 4 -> closet vestibule
    {f:1, dir:"h", x:8.5,  z:26,   w:3,   type:"double"},    // vestibule -> hall
    {f:1, dir:"v", x:6,    z:23.5, w:2.5, type:"door"},      // bath 2
    {f:1, dir:"v", x:6,    z:33.5, w:2.5, type:"door"},      // mud room
    // second floor
    {f:2, dir:"v", x:9.5,  z:14,   w:5,   type:"opening"},   // sitting <-> bedroom 1
    {f:2, dir:"v", x:24.8, z:12,   w:2.8, type:"door"},      // bedroom 1 -> bath 1
    {f:2, dir:"h", x:22,   z:21.8, w:4,   type:"double"},    // bedroom 1 -> hall
    {f:2, dir:"v", x:19.3, z:24.7, w:2.5, type:"door"},      // master closet -> hall/loft
    {f:2, dir:"v", x:19.3, z:33,   w:8,   type:"opening"},   // hall <-> loft
    {f:2, dir:"v", x:9.5,  z:31.5, w:2.5, type:"door"},      // laundry
    {f:2, dir:"h", x:2.9,  z:40.3, w:4,   type:"double"},    // bedroom 2 closet
    {f:2, dir:"h", x:11.3, z:40.3, w:2.8, type:"door"},      // bedroom 2
    {f:2, dir:"h", x:16.3, z:40.3, w:2.5, type:"door"},      // bath 3
    {f:2, dir:"h", x:24,   z:40.3, w:3,   type:"door"},      // bedroom 3
    {f:2, dir:"v", x:9.5,  z:37.7, w:2.5, type:"door"},      // linen (from the hall)
  ];
  const WINDOWS_DRAWN=[
    {f:1, dir:"h", x:5.5,  z:8,    w:4}, {f:1, dir:"v", x:0,  z:14.5, w:4},      // office
    {f:1, dir:"h", x:15,   z:8,    w:4}, {f:1, dir:"h", x:21, z:8,    w:4},      // living
    {f:1, dir:"v", x:38,   z:14.7, w:4},                                           // breakfast
    {f:1, dir:"v", x:38,   z:24,   w:3},                                           // kitchen
    {f:1, dir:"h", x:31.5, z:52.2, w:5}, {f:1, dir:"v", x:38, z:46,   w:4},      // dining room
    {f:1, dir:"v", x:0,    z:26,   w:2.5},                                         // bath 2
    {f:2, dir:"v", x:0,    z:14,   w:4}, {f:2, dir:"h", x:4.7, z:8,   w:3},      // sitting
    {f:2, dir:"h", x:17,   z:8,    w:5},                                           // bedroom 1
    {f:2, dir:"h", x:29,   z:8,    w:3},                                           // bath 1
    {f:2, dir:"v", x:0,    z:31.5, w:2.5},                                         // laundry
    {f:2, dir:"v", x:0,    z:46,   w:3}, {f:2, dir:"h", x:6.6, z:52.3, w:4},     // bedroom 2
    {f:2, dir:"h", x:28.6, z:52.3, w:5}, {f:2, dir:"v", x:38, z:45,   w:4},      // bedroom 3
    {f:2, dir:"v", x:38,   z:29,   w:4},                                           // loft
  ];
  const flipSide=s=>({e:"w",w:"e"}[s]||s);
  function mirrorRoom(r){
    const o={...r, gx:MIRROR?PLAN_W-r.gx-r.gw:r.gx, gy:r.gy+Y0};
    ["bed","tv","counter","tub","desk","table","train"].forEach(k=>{ if(o[k]) o[k]=flipSide(o[k]); });
    if(o.shower) o.shower=o.shower.replace(/[ew]/g,c=>flipSide(c));
    if(r.stairs) o.stairs={...r.stairs, gx:PLAN_W-r.stairs.gx-r.stairs.gw, gy:r.stairs.gy+Y0};
    if(r.stairwell) o.stairwell={...r.stairwell, gx:PLAN_W-r.stairwell.gx-r.stairwell.gw, gy:r.stairwell.gy+Y0};
    return o;
  }
  const mirrorOpening=d=>({...d, x:MIRROR?PLAN_W-d.x:d.x, z:d.z+Y0});
  const DEFAULT_LAYOUT=ROOMS_DRAWN.map(mirrorRoom);
  const DEFAULT_PLAN={doors:DOORS_DRAWN.map(mirrorOpening), windows:WINDOWS_DRAWN.map(mirrorOpening)};

  const HA_ICON = {
    light:"\u{1F4A1}", switch:"\u{1F50C}", fan:"\u{1F32C}️", cover:"\u{1F6AA}",
    lock:"\u{1F512}", climate:"\u{1F321}️", media_player:"\u{1F4FA}",
    scene:"✨", script:"▶️", alarm_control_panel:"\u{1F6E1}️",
    binary_sensor:"\u{1F6A6}", sensor:"\u{1F321}️", camera:"\u{1F4F7}"
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
    if(t.domain==="camera") return "Tap to view";
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
  function getLayout(){ const c=(typeof FH!=="undefined"&&FH.get().homeLayout); return (Array.isArray(c)&&c.length)?c:DEFAULT_LAYOUT; }
  /* doors/windows only exist for the built-in plan; a custom homeLayout falls back to guessed doorways */
  function getPlan(){ return isCustomLayout()?null:DEFAULT_PLAN; }
  function layoutExtent(rooms){ let m=0; rooms.forEach(r=>{ m=Math.max(m,r.gx+r.gw,r.gy+r.gd); }); return m||1; }
  function isCustomLayout(){ const c=(typeof FH!=="undefined"&&FH.get().homeLayout); return Array.isArray(c)&&c.length>0; }
  /* which plan room a device belongs to: anything "back" + porch/patio/deck goes to the back porch,
     then the HA Area by name, then the room key in the device name, then the key in its Area */
  function roomFor(t, rooms){
    const lc=s=>String(s||"").toLowerCase(), txt=lc(t.name)+" "+lc(t.area);
    if(/\bback\b/.test(txt)&&/porch|patio|deck/.test(txt)){ const b=rooms.find(r=>/patio|back porch/.test(lc(r.key)+" "+lc(r.name))); if(b) return b; }
    return rooms.find(r=>lc(t.area)&&lc(t.area)===lc(r.name)) || rooms.find(r=>lc(t.name).includes(lc(r.key))) || rooms.find(r=>lc(t.area).includes(lc(r.key))) || null;
  }
  function tilesOf(h){ return (h.groups||[]).reduce((a,g)=>a.concat(g.tiles||[]),[]); }
  function resolveRooms(h){
    const tiles=tilesOf(h);
    const lc=s=>String(s||"").toLowerCase();
    const byId=id=>tiles.find(t=>t.entity_id===id);
    const layout=getLayout();
    const byKey=(dom,k,dc,r)=>tiles.find(t=>t.domain===dom&&(!dc||t.device_class===dc)&&(lc(t.name).includes(lc(k))||lc(t.area||"").includes(lc(k)))&&roomFor(t,layout)===r);
    return layout.map(r=>{
      const light=(r.light&&byId(r.light))||byKey("light",r.key,null,r);
      const cover=(r.cover&&byId(r.cover))||byKey("cover",r.key,null,r);
      const temp =(r.temp &&byId(r.temp)) ||byKey("sensor",r.key,"temperature",r);
      const media=byKey("media_player",r.key,null,r);
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

  /* ---- light colour + brightness panel (phone room pop-up, wall light pop-up, routine builder) ----
     A CSS colour wheel (no canvas): drag round the ring for the colour, towards the middle for paler.
     send(data) gets light.turn_on data: {brightness_pct} | {rgb_color:[r,g,b]} | {color_temp_kelvin}. */
  const SWATCHES=[["Warm white",[255,183,110],2700],["Daylight",[255,236,214],4000],["Cool white",[222,234,255],5500],
    ["Red",[255,0,0]],["Orange",[255,110,0]],["Yellow",[255,215,0]],["Green",[0,210,70]],["Teal",[0,200,190]],
    ["Blue",[0,70,255]],["Purple",[140,0,255]],["Pink",[255,50,160]]];
  function hsvRgb(h,s){ const f=n=>{ const k=(n+h/60)%6; return Math.round(255*(1-s*Math.max(0,Math.min(k,4-k,1)))); }; return [f(5),f(3),f(1)]; }
  function rgbHs(rgb){ const [r,g,b]=(rgb||[255,255,255]).map(x=>x/255), mx=Math.max(r,g,b), mn=Math.min(r,g,b), d=mx-mn;
    let h=0; if(d){ h=mx===r?((g-b)/d)%6:mx===g?(b-r)/d+2:(r-g)/d+4; h*=60; if(h<0) h+=360; } return [h, mx?d/mx:0]; }
  let lightCssDone=false;
  function lightCss(){
    if(lightCssDone) return; lightCssDone=true;
    const st=document.createElement("style");
    st.textContent=`.fhl{display:flex; flex-direction:column; gap:12px; padding:6px 0}
      .fhl-dim{display:flex; align-items:center; gap:10px} .fhl-dim input{flex:1; accent-color:#f0a030; height:28px} .fhl-dim small{width:42px; text-align:right; color:var(--ink-dim)}
      .fhl-sw{display:flex; flex-wrap:wrap; gap:8px}
      .fhl-sw button{width:34px; height:34px; border-radius:50%; border:2px solid rgba(127,127,127,.35); cursor:pointer; padding:0}
      .fhl-sw button.on{border-color:var(--ink); transform:scale(1.12)}
      .fhl-wheel{position:relative; width:min(230px,70vw); aspect-ratio:1; border-radius:50%; margin:2px auto; touch-action:none; cursor:crosshair;
        background:radial-gradient(circle closest-side,#fff,rgba(255,255,255,0)),conic-gradient(red,yellow,lime,cyan,blue,magenta,red)}
      .fhl-dot{position:absolute; width:26px; height:26px; margin:-13px 0 0 -13px; border-radius:50%; border:3px solid #fff; box-shadow:0 0 0 1px rgba(0,0,0,.4),0 2px 6px rgba(0,0,0,.4); pointer-events:none}`;
    document.head.appendChild(st);
  }
  function lightPanelHTML(t, opts){
    lightCss(); opts=opts||{};
    const br=t.on?(t.brightness||100):(opts.pct||100);
    let h="";
    if(t.dimmable!==false && opts.dim!==false) h+=`<div class="fhl-dim"><span>🔅</span><input type="range" min="1" max="100" value="${br}" data-fhl="dim" aria-label="Brightness"><small>${br}%</small><span>🔆</span></div>`;
    if(t.color||t.whites){
      const sw=SWATCHES.filter(x=>t.color||x[2]);
      h+=`<div class="fhl-sw">${sw.map((x,i)=>`<button data-fhl-sw="${SWATCHES.indexOf(x)}" title="${x[0]}" aria-label="${x[0]}" style="background:rgb(${x[1].join(",")})"></button>`).join("")}</div>`;
    }
    if(t.color) h+=`<div class="fhl-wheel" data-fhl="wheel"><div class="fhl-dot" style="display:none"></div></div>`;
    return `<div class="fhl">${h}</div>`;
  }
  function bindLightPanel(root, t, send){
    const dim=root.querySelector('[data-fhl="dim"]');
    if(dim){ const lab=dim.nextElementSibling; dim.oninput=()=>{ lab.textContent=dim.value+"%"; }; dim.onchange=()=>send({brightness_pct:+dim.value}); }
    root.querySelectorAll("[data-fhl-sw]").forEach(b=>b.onclick=()=>{ const x=SWATCHES[+b.dataset.fhlSw];
      root.querySelectorAll("[data-fhl-sw]").forEach(o=>o.classList.toggle("on",o===b));
      send(x[2]&&t.whites?{color_temp_kelvin:x[2]}:{rgb_color:x[1]}); place(x[1]); });
    const wh=root.querySelector('[data-fhl="wheel"]'); if(!wh) return;
    const dot=wh.querySelector(".fhl-dot");
    function place(rgb){ if(!rgb) return; const [h,s]=rgbHs(rgb), a=(h-90)*Math.PI/180, r=wh.clientWidth/2;
      dot.style.display=""; dot.style.left=(r+Math.cos(a)*s*r)+"px"; dot.style.top=(r+Math.sin(a)*s*r)+"px"; dot.style.background=`rgb(${rgb.join(",")})`; }
    let last=0, pend=null, down=false;
    const pick=(e)=>{ const b=wh.getBoundingClientRect(), r=b.width/2, dx=e.clientX-b.left-r, dy=e.clientY-b.top-r;
      const s=Math.min(1,Math.hypot(dx,dy)/r); let h=Math.atan2(dx,-dy)*180/Math.PI; if(h<0) h+=360;
      const rgb=hsvRgb(h,s); place(rgb); pend=rgb;
      if(Date.now()-last>450){ last=Date.now(); send({rgb_color:rgb}); pend=null; } };
    wh.addEventListener("pointerdown",e=>{ down=true; wh.setPointerCapture(e.pointerId); pick(e); });
    wh.addEventListener("pointermove",e=>{ if(down) pick(e); });
    const up=()=>{ if(!down) return; down=false; if(pend){ send({rgb_color:pend}); pend=null; } };
    wh.addEventListener("pointerup",up); wh.addEventListener("pointercancel",up);
    if(t.rgb) requestAnimationFrame(()=>place(t.rgb));
  }

  window.FHHome = {
    lightPanelHTML, bindLightPanel, SWATCHES,
    DEFAULT_LAYOUT, DEFAULT_PLAN, HA_ICON, haIcon, haStateLabel, esc,
    getLayout, getPlan, roomFor, layoutExtent, isCustomLayout, resolveRooms, tilesOf, floorsIn,
    renderFloorView, renderIsoView,
    get floor(){ return homeFloor; }, set floor(f){ homeFloor=f; },
    // pages override these
    toggle:function(){}, remote:function(){}, camera:function(){}, rerender:function(){}
  };
})();
