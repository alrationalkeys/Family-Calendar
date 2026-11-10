/* FamilyHub live 3D house — built on three.js (static/vendor/three.min.js, MIT).
   Extrudes the traced floor plan (FHHome layout, units = feet) into a dollhouse-cut
   3D model: floors, walls with doorways, simple furniture per room type, a real point
   light per room that switches with Home Assistant, glowing TVs, and tappable device
   pins projected over the canvas.

   FHHome.render3D(container, h, {id, height, pins, labels, controls, floorButtons})
     - one WebGL context per `id` (default "main"); the canvas is re-parented into
       whatever container you pass, so re-rendering the surrounding HTML is free.
     - call again with fresh `h` to update light/TV/pin state without rebuilding.
   Falls back to FHHome.renderIsoView when WebGL / three.js is unavailable. */
(function(){
  if(!window.FHHome) return;
  const esc=FHHome.esc;
  const WALL_H=3.4, EXT_H=4.4, T=0.42, LEVEL_H=9.5;
  // styles for the canvas frame, device pins, room labels and the rotate buttons
  const css=document.createElement("style"); css.textContent=`
.h3{position:relative; width:100%; border-radius:22px; overflow:hidden; touch-action:none; user-select:none; -webkit-user-select:none;
  background:radial-gradient(120% 100% at 50% 0%, #1c2231 0%, #0b0d12 72%)}
.h3 canvas{position:absolute; inset:0; display:block}
.h3-overlay{position:absolute; inset:0; pointer-events:none}
.h3-overlay>*{position:absolute; left:0; top:0; pointer-events:auto; will-change:transform}
.h3-lbl{pointer-events:none!important; font:600 11px/1 var(--font,system-ui,sans-serif); color:#ece9e2; background:rgba(12,14,20,.58);
  padding:5px 9px; border-radius:999px; white-space:nowrap; backdrop-filter:blur(5px); -webkit-backdrop-filter:blur(5px); letter-spacing:.02em}
.h3-pin{width:38px; height:38px; border-radius:50%; border:1px solid rgba(255,255,255,.14); background:rgba(18,20,27,.8); color:#e3e6ec;
  display:flex; flex-direction:column; align-items:center; justify-content:center; font-size:16px; line-height:1; padding:0; cursor:pointer;
  backdrop-filter:blur(6px); -webkit-backdrop-filter:blur(6px); box-shadow:0 5px 16px rgba(0,0,0,.5); transition:background .2s, box-shadow .2s, transform .15s}
.h3-pin .lb{font-size:9px; font-weight:700; margin-top:1px; color:#fff; letter-spacing:.02em}
.h3-pin.on{background:rgba(233,162,59,.95); color:#1a1205; box-shadow:0 0 0 3px rgba(233,162,59,.22), 0 0 20px rgba(233,162,59,.55)}
.h3-pin.on .lb{color:#1a1205}
.h3-pin.ro{cursor:default; background:rgba(28,34,48,.82)}
.h3-bar{left:auto!important; right:10px; top:10px; display:flex; gap:8px; transform:none!important}
.h3-btn{width:40px; height:40px; border-radius:50%; border:1px solid rgba(255,255,255,.14); background:rgba(18,20,27,.75); color:#e3e6ec; font-size:18px; cursor:pointer;
  backdrop-filter:blur(6px); -webkit-backdrop-filter:blur(6px)}
.h3-btn:active{transform:scale(.92)}
.h3-hint{left:12px!important; bottom:10px; top:auto!important; transform:none!important; pointer-events:none!important; font:500 11px/1 var(--font,system-ui,sans-serif); color:rgba(236,233,226,.6)}
`; document.head.appendChild(css);
  const COL={
    wallTop:0xe9e2d6, wall:0xcfc5b6, wallIn:0xbdb3a4,
    wood:0x9b7752, tile:0xb9b5ad, carpet:0x8d8780, concrete:0x7b7d81, grass:0x4e7a3b, deck:0x8a6a4a,
    fabric:0xb9b2a7, fabricDk:0x6f6a64, woodDk:0x5a4030, white:0xeeeae2, dark:0x2f3136, steel:0x9aa0a8,
    car:0x334155, car2:0x7a2f2f, plant:0x3f7a3a, pot:0x8c5a3a, screenOff:0x15171b, screenOn:0x7fc4ff,
    bulbOff:0xd9d2c4, bulbOn:0xffe2a8
  };
  const styleOf=k=>{ k=String(k||"").toLowerCase();
    if(/garage/.test(k)) return "concrete"; if(/patio|porch/.test(k)) return "deck";
    if(/bath|laundry|kitchen|pantry|butler/.test(k)) return "tile";
    if(/bedroom|master|loft|flex|sitting|closet/.test(k)) return "carpet"; return "wood"; };
  const isOutside=k=>/patio|porch/i.test(k||"");
  const isGarage=k=>/garage/i.test(k||"");

  const mats={};
  function mat(c, o){ const key=c+"|"+JSON.stringify(o||{}); if(!mats[key]) mats[key]=new THREE.MeshStandardMaterial(Object.assign({color:c, roughness:.92, metalness:0}, o||{})); return mats[key]; }
  function box(w,h,d,c,x,y,z,o){ const m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d), mat(c,o)); m.position.set(x,y+h/2,z); return m; }
  function cyl(r,h,c,x,y,z,seg){ const m=new THREE.Mesh(new THREE.CylinderGeometry(r,r,h,seg||18), mat(c)); m.position.set(x,y+h/2,z); return m; }

  /* ---------- furniture: coarse props so each room reads at a glance ---------- */
  function furnish(g, r){
    const k=String(r.key||r.name).toLowerCase(), x0=r.gx, z0=r.gy, w=r.gw, d=r.gd, cx=x0+w/2, cz=z0+d/2;
    const fits=(fw,fd)=>w>fw+1.2&&d>fd+1.2;
    const inset=0.6;
    if(/bedroom|master/.test(k) && !/closet/.test(k)){
      if(fits(5.5,7)){ const bw=/master/.test(k)?6.2:5, bd=/master/.test(k)?7:6.5;
        g.add(box(bw,1.5,bd,COL.white,cx,0,z0+inset+bd/2));                       // mattress
        g.add(box(bw,1.2,0.6,COL.fabricDk,cx,0.4,z0+inset+0.2));                    // pillows row
        g.add(box(bw+0.3,2.4,0.3,COL.woodDk,cx,0,z0+inset-0.1));                    // headboard
        g.add(box(1.6,1.7,1.6,COL.woodDk,cx-bw/2-1.1,0,z0+inset+0.9));              // nightstands
        g.add(box(1.6,1.7,1.6,COL.woodDk,cx+bw/2+1.1,0,z0+inset+0.9));
        if(d>11) g.add(box(Math.min(5,w-3),2.6,1.6,COL.woodDk,cx,0,z0+d-inset-0.8)); // dresser
      }
      return;
    }
    if(/living|loft|sitting|flex/.test(k)){
      if(fits(7,3)){ const sw=Math.min(8,w-3);
        g.add(box(sw,1.6,3,COL.fabric,cx,0,cz+1.2)); g.add(box(sw,0.9,0.9,COL.fabricDk,cx,1.6,cz+2.2)); // sofa + back
        g.add(box(3,1.3,1.8,COL.woodDk,cx,0,cz-2.2));                                              // coffee table
        if(w>10) g.add(box(2.6,1.5,2.6,COL.fabricDk,cx-sw/2-1.6,0,cz-1));                             // armchair
        const rug=new THREE.Mesh(new THREE.CircleGeometry(Math.min(4,w/3),28), mat(0x5b5f68)); rug.rotation.x=-Math.PI/2; rug.position.set(cx,0.02,cz-0.6); g.add(rug);
      }
      return;
    }
    if(/dining/.test(k)){ if(fits(7,4)){ g.add(box(6,0.25,3.4,COL.woodDk,cx,2.3,cz)); g.add(box(0.5,2.3,0.5,COL.woodDk,cx-2.5,0,cz-1.2)); g.add(box(0.5,2.3,0.5,COL.woodDk,cx+2.5,0,cz-1.2)); g.add(box(0.5,2.3,0.5,COL.woodDk,cx-2.5,0,cz+1.2)); g.add(box(0.5,2.3,0.5,COL.woodDk,cx+2.5,0,cz+1.2));
      [-2,0,2].forEach(dx=>{ g.add(box(1.4,1.5,1.4,COL.fabric,cx+dx,0,cz-2.6)); g.add(box(1.4,1.5,1.4,COL.fabric,cx+dx,0,cz+2.6)); }); } return; }
    if(/kitchen/.test(k)){ if(fits(6,6)){
      g.add(box(w-inset*2,3,2,COL.white,cx,0,z0+inset+1));                       // back counter
      g.add(box(w-inset*2,0.2,2.1,COL.dark,cx,3,z0+inset+1));
      g.add(box(2,3,d-inset*2-2,COL.white,x0+inset+1,0,cz+1));                    // side counter
      g.add(box(2.6,6,2.6,COL.steel,x0+w-inset-1.3,0,z0+inset+1.3));              // fridge
      if(w>9&&d>8){ g.add(box(Math.min(6,w-6),3,3,COL.woodDk,cx+0.8,0,cz+1.5)); g.add(box(Math.min(6,w-6)+0.3,0.2,3.3,COL.white,cx+0.8,3,cz+1.5)); } // island
    } return; }
    if(/butler|pantry|closet/.test(k)){ g.add(box(Math.max(1,w-inset*2),5.5,1.1,COL.woodDk,cx,0,z0+inset+0.55)); if(d>4) g.add(box(1.1,5.5,Math.max(1,d-inset*2-1.2),COL.woodDk,x0+inset+0.55,0,cz+0.6)); return; }
    if(/bath/.test(k)){ if(fits(4,4)){
      g.add(box(2.6,1.8,5,COL.white,x0+inset+1.3,0,cz));                            // tub
      g.add(cyl(0.8,1.4,COL.white,x0+w-inset-1.2,0,z0+d-inset-1.3,14));            // toilet
      g.add(box(Math.min(4,w-4),2.8,1.8,COL.woodDk,x0+w-inset-Math.min(4,w-4)/2,0,z0+inset+0.9)); // vanity
    } return; }
    if(/laundry/.test(k)){ g.add(box(2.4,3,2.4,COL.white,x0+inset+1.2,0,z0+inset+1.2)); g.add(box(2.4,3,2.4,COL.white,x0+inset+3.8,0,z0+inset+1.2)); return; }
    if(/garage/.test(k)){ if(fits(8,15)){
      const car=(cxx,czz,c)=>{ g.add(box(6,2.2,15,c,cxx,0.9,czz)); g.add(box(5.2,2,7.5,COL.dark,cxx,3.1,czz+0.4)); [[-2.6,-5],[2.6,-5],[-2.6,5],[2.6,5]].forEach(p=>{ const wh=cyl(1.15,0.9,COL.dark,cxx+p[0],0,czz+p[1],16); wh.rotation.z=Math.PI/2; wh.position.y=1.15; g.add(wh); }); };
      car(cx-(w>16?4.5:0), cz, COL.car); if(w>16) car(cx+4.5, cz, COL.car2);
    } return; }
    if(/stairs/.test(k)){ const n=8, sd=Math.min(d-1,10)/n; for(let i=0;i<n;i++) g.add(box(3.4,(i+1)*0.7,sd,COL.woodDk,cx,0,z0+inset+sd*(i+0.5))); return; }
    if(/foyer|hall/.test(k)){ if(d>6&&w>4) g.add(box(Math.min(4,w-2),2.6,1.2,COL.woodDk,cx,0,z0+d-inset-0.7)); return; }
    if(/patio|porch/.test(k)){ if(fits(4,4)){ g.add(box(1.8,1.6,1.8,COL.fabricDk,cx-1.6,0,cz)); g.add(box(1.8,1.6,1.8,COL.fabricDk,cx+1.6,0,cz)); g.add(cyl(0.9,1.5,COL.woodDk,cx,0,cz-2,16));
      g.add(cyl(0.7,1.2,COL.pot,x0+inset+0.9,0,z0+inset+0.9,12)); g.add(cyl(1.1,1.3,COL.plant,x0+inset+0.9,1.2,z0+inset+0.9,10)); } return; }
  }

  /* ---------- walls with doorways / garage door, de-duplicated on shared edges ---------- */
  function buildFloor(rooms, floorN, ghost){
    const g=new THREE.Group();
    const fr=rooms.filter(r=>(r.floor||1)===floorN);
    const eq=(a,b)=>Math.abs(a-b)<0.05;
    const overlap=(a0,a1,b0,b1)=>Math.min(a1,b1)-Math.max(a0,b0);
    const wallMat=ghost?mat(COL.wall,{transparent:true,opacity:.16,depthWrite:false}):mat(COL.wall);
    const topMat=ghost?wallMat:mat(COL.wallTop);
    const seg=(x0,z0,x1,z1,h)=>{ // wall along a straight run (axis-aligned)
      const len=Math.hypot(x1-x0,z1-z0); if(len<0.2) return;
      const horiz=Math.abs(z1-z0)<0.01;
      const m=new THREE.Mesh(new THREE.BoxGeometry(horiz?len:T, h, horiz?T:len), wallMat);
      m.position.set((x0+x1)/2, h/2, (z0+z1)/2); g.add(m);
      if(!ghost){ const cap=new THREE.Mesh(new THREE.BoxGeometry((horiz?len:T)+0.02, 0.08, (horiz?T:len)+0.02), topMat); cap.position.set((x0+x1)/2, h+0.04, (z0+z1)/2); g.add(cap); }
    };
    const run=(x0,z0,x1,z1,h,gaps)=>{ // split a wall around door gaps [[a,b],...] measured along the run
      const horiz=Math.abs(z1-z0)<0.01, a0=horiz?x0:z0, a1=horiz?x1:z1;
      let cur=a0; (gaps||[]).sort((p,q)=>p[0]-q[0]).forEach(([ga,gb])=>{ if(gb<=cur) return; horiz?seg(cur,z0,Math.max(cur,ga),z0,h):seg(x0,cur,x0,Math.max(cur,ga),h); cur=Math.max(cur,gb); });
      horiz?seg(cur,z0,a1,z0,h):seg(x0,cur,x0,a1,h);
    };
    fr.forEach(r=>{
      if(!ghost){
        // floor slab
        const f=new THREE.Mesh(new THREE.BoxGeometry(r.gw-0.04,0.32,r.gd-0.04), mat(COL[styleOf(r.key)]));
        f.position.set(r.gx+r.gw/2,-0.16,r.gy+r.gd/2); f.userData.room=r; g.add(f);
      }
      if(isOutside(r.key)){ if(!ghost){ // low curb only
        const c=new THREE.Mesh(new THREE.BoxGeometry(r.gw,0.5,0.3), mat(COL.wallTop)); c.position.set(r.gx+r.gw/2,0.25,r.gy+r.gd-0.15); g.add(c); } return; }
      const sidesIn=k=>!isOutside(k);
      // NORTH edge (z=gy): always mine
      {
        const nb=fr.filter(s=>s!==r&&eq(s.gy+s.gd,r.gy)&&overlap(r.gx,r.gx+r.gw,s.gx,s.gx+s.gw)>2.8);
        const gaps=nb.filter(s=>sidesIn(s.key)||true).map(s=>{ const a=Math.max(r.gx,s.gx), b=Math.min(r.gx+r.gw,s.gx+s.gw), c=(a+b)/2, hw=(isOutside(s.key)?3:1.5); return [c-hw,c+hw]; });
        run(r.gx,r.gy,r.gx+r.gw,r.gy, nb.length?WALL_H:EXT_H, gaps);
      }
      // WEST edge (x=gx): always mine
      {
        const nb=fr.filter(s=>s!==r&&eq(s.gx+s.gw,r.gx)&&overlap(r.gy,r.gy+r.gd,s.gy,s.gy+s.gd)>2.8);
        const gaps=nb.map(s=>{ const a=Math.max(r.gy,s.gy), b=Math.min(r.gy+r.gd,s.gy+s.gd), c=(a+b)/2; return [c-1.5,c+1.5]; });
        run(r.gx,r.gy,r.gx,r.gy+r.gd, nb.length?WALL_H:EXT_H, gaps);
      }
      // SOUTH edge (z=gy+gd): mine only if no neighbour claims it as its north
      if(!fr.some(s=>s!==r&&eq(s.gy,r.gy+r.gd)&&overlap(r.gx,r.gx+r.gw,s.gx,s.gx+s.gw)>0.5)){
        const gaps=[]; if(isGarage(r.key)){ const c=r.gx+r.gw/2; gaps.push([c-8,c+8]); }
        else if(/foyer|porch/.test(String(r.key))){ const c=r.gx+r.gw/2; gaps.push([c-1.6,c+1.6]); }
        run(r.gx,r.gy+r.gd,r.gx+r.gw,r.gy+r.gd,EXT_H,gaps);
      }
      // EAST edge (x=gx+gw)
      if(!fr.some(s=>s!==r&&eq(s.gx,r.gx+r.gw)&&overlap(r.gy,r.gy+r.gd,s.gy,s.gy+s.gd)>0.5)){
        run(r.gx+r.gw,r.gy,r.gx+r.gw,r.gy+r.gd,EXT_H,[]);
      }
      if(!ghost) furnish(g,r);
    });
    return g;
  }

  /* ---------- device placement inside a room ---------- */
  function devicesByRoom(h, rooms){
    const tiles=FHHome.tilesOf(h), lc=s=>String(s||"").toLowerCase(), out=new Map(), used=new Set();
    rooms.forEach(r=>out.set(r, []));
    const want=t=>t.toggleable||t.activatable||t.domain==="media_player"||t.domain==="sensor"||t.domain==="binary_sensor"||t.domain==="lock"||t.domain==="climate";
    tiles.forEach(t=>{
      if(!want(t)||t.domain==="scene"||t.domain==="script") return;
      const hit=rooms.find(r=>lc(t.area)&&lc(t.area)===lc(r.name)) || rooms.find(r=>lc(t.name).includes(lc(r.key))) || rooms.find(r=>lc(t.area||"").includes(lc(r.key)));
      if(hit){ out.get(hit).push(t); used.add(t.entity_id); }
    });
    // things that belong at the front door
    tiles.forEach(t=>{ if(used.has(t.entity_id)) return;
      if(t.domain==="lock"||t.domain==="alarm_control_panel"||(t.domain==="binary_sensor"&&/front/i.test(t.name))){
        const foyer=rooms.find(r=>/foyer|entry/i.test(r.key||r.name))||rooms.find(r=>/hall/i.test(r.key||r.name)); if(foyer){ out.get(foyer).push(t); used.add(t.entity_id); } } });
    return out;
  }

  /* ---------- viewer instances ---------- */
  const viewers={};
  function getViewer(id){
    if(viewers[id]) return viewers[id];
    let renderer;
    try{ renderer=new THREE.WebGLRenderer({alpha:true, antialias:true, powerPreference:"low-power"}); }
    catch(e){ return null; }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio||1, 2));
    renderer.toneMapping=THREE.ACESFilmicToneMapping; renderer.toneMappingExposure=1.05;
    const el=document.createElement("div"); el.className="h3"; el.innerHTML='<div class="h3-overlay"></div>';
    el.prepend(renderer.domElement);
    const v={id, renderer, el, overlay:el.querySelector(".h3-overlay"), scene:new THREE.Scene(),
      camera:new THREE.PerspectiveCamera(32,1,0.5,600), orbit:{theta:0.55, phi:0.98, dist:80, tx:0, tz:0},
      built:null, lights:new Map(), screens:new Map(), pins:[], labels:[], anchors:[], raf:0, w:0, h:0, lastH:null};
    v.hemi=new THREE.HemisphereLight(0x9fb3d9, 0x4a3b2e, 1.0); v.scene.add(v.hemi);
    v.sun=new THREE.DirectionalLight(0xfff1dd, 1.3); v.sun.position.set(-40,70,50); v.scene.add(v.sun);
    v.fill=new THREE.DirectionalLight(0xbfd0ff, 0.35); v.fill.position.set(50,30,-30); v.scene.add(v.fill);
    v.root=new THREE.Group(); v.scene.add(v.root);
    setupControls(v);
    viewers[id]=v; return v;
  }
  function nightFactor(){ const hr=new Date().getHours()+new Date().getMinutes()/60; if(hr<6||hr>=20) return 1; if(hr<8) return 1-(hr-6)/2; if(hr>=18) return (hr-18)/2; return 0; }

  function setupControls(v){
    const el=v.el; let ptrs=new Map(), last=null, pinch=null, moved=false;
    const req=()=>requestRender(v);
    el.addEventListener("pointerdown",e=>{ if(!v.controls) return; if(e.target.closest(".h3-pin,.h3-btn")) return; ptrs.set(e.pointerId,{x:e.clientX,y:e.clientY}); el.setPointerCapture(e.pointerId); last={x:e.clientX,y:e.clientY}; moved=false; if(ptrs.size===2){ const a=[...ptrs.values()]; pinch={d:Math.hypot(a[0].x-a[1].x,a[0].y-a[1].y), dist:v.orbit.dist, cx:(a[0].x+a[1].x)/2, cy:(a[0].y+a[1].y)/2, tx:v.orbit.tx, tz:v.orbit.tz}; } });
    el.addEventListener("pointermove",e=>{ if(!ptrs.has(e.pointerId)) return; ptrs.set(e.pointerId,{x:e.clientX,y:e.clientY});
      if(ptrs.size===1&&last){ const dx=e.clientX-last.x, dy=e.clientY-last.y; if(Math.abs(dx)+Math.abs(dy)>2) moved=true; v.orbit.theta-=dx*0.0065; v.orbit.phi=Math.max(0.32,Math.min(1.45,v.orbit.phi+dy*0.005)); last={x:e.clientX,y:e.clientY}; req(); }
      else if(ptrs.size===2&&pinch){ const a=[...ptrs.values()]; const d=Math.hypot(a[0].x-a[1].x,a[0].y-a[1].y); v.orbit.dist=Math.max(18,Math.min(200,pinch.dist*pinch.d/Math.max(1,d)));
        const cx=(a[0].x+a[1].x)/2, cy=(a[0].y+a[1].y)/2, s=v.orbit.dist/900; // pan in camera-aligned ground plane
        const ct=Math.cos(v.orbit.theta), st=Math.sin(v.orbit.theta), px=-(cx-pinch.cx)*s, pz=-(cy-pinch.cy)*s;
        v.orbit.tx=pinch.tx+px*ct-pz*st; v.orbit.tz=pinch.tz+px*st+pz*ct; moved=true; req(); } });
    const up=e=>{ ptrs.delete(e.pointerId); if(ptrs.size<2) pinch=null; if(ptrs.size===0) last=null; };
    el.addEventListener("pointerup",up); el.addEventListener("pointercancel",up);
    el.addEventListener("wheel",e=>{ if(!v.controls) return; e.preventDefault(); v.orbit.dist=Math.max(18,Math.min(200,v.orbit.dist*(1+Math.sign(e.deltaY)*0.08))); req(); },{passive:false});
    el.addEventListener("click",e=>{ if(moved) return; const f=e.target.closest(".h3-floor"); if(f&&v.opts.pins){ /* reserved */ } });
    v._rotateBy=d=>{ const from=v.orbit.theta, to=from+d, t0=performance.now(); const step=()=>{ const k=Math.min(1,(performance.now()-t0)/380), e=1-Math.pow(1-k,3); v.orbit.theta=from+(to-from)*e; requestRender(v); if(k<1) requestAnimationFrame(step); }; step(); };
  }

  function requestRender(v){ if(v.raf) return; v.raf=requestAnimationFrame(()=>{ v.raf=0; frame(v); }); }
  function frame(v){
    const o=v.orbit, cam=v.camera;
    const cy=o.dist*Math.sin(o.phi), r=o.dist*Math.cos(o.phi);
    cam.position.set(o.tx+r*Math.sin(o.theta), cy, o.tz+r*Math.cos(o.theta));
    cam.lookAt(o.tx, 0, o.tz);
    v.renderer.render(v.scene, cam);
    // project anchors -> overlay
    const w=v.w, h=v.h, tmp=new THREE.Vector3();
    v.anchors.forEach(a=>{ tmp.copy(a.pos).project(cam); const x=(tmp.x+1)/2*w+(a.dx||0), y=(1-tmp.y)/2*h+(a.dy||0); const vis=tmp.z<1&&x>-20&&x<w+20&&y>-20&&y<h+20;
      a.el.style.transform=`translate(${x.toFixed(1)}px,${y.toFixed(1)}px) translate(-50%,-50%)`; a.el.style.opacity=vis?"":"0"; a.el.style.pointerEvents=vis?"":"none"; });
  }

  function resize(v){ const w=v.el.clientWidth||1, h=v.el.clientHeight||1; if(w===v.w&&h===v.h) return; v.w=w; v.h=h; v.renderer.setSize(w,h,false); v.renderer.domElement.style.width="100%"; v.renderer.domElement.style.height="100%"; v.camera.aspect=w/h; v.camera.updateProjectionMatrix(); }

  function build(v, rooms, floorN){
    if(v.built){ v.root.remove(v.built); v.built.traverse(o=>{ if(o.geometry) o.geometry.dispose(); }); }
    v.lights.forEach(l=>v.scene.remove(l)); v.lights.clear(); v.screens.clear();
    const g=new THREE.Group();
    g.add(buildFloor(rooms, floorN, false));
    if(floorN>1){ const ghost=buildFloor(rooms, floorN-1, true); ghost.position.y=-LEVEL_H; g.add(ghost); }
    // ground shadow plate
    const ext=FHHome.layoutExtent(rooms);
    const plate=new THREE.Mesh(new THREE.PlaneGeometry(ext*2.2, ext*2.2), new THREE.MeshBasicMaterial({color:0x000000, transparent:true, opacity:0.22})); plate.rotation.x=-Math.PI/2; plate.position.set(ext/2,-0.45-(floorN>1?LEVEL_H:0),ext/2); g.add(plate);
    v.root.add(g); v.built=g;
    // centre + default framing
    let minX=1e9,maxX=-1e9,minZ=1e9,maxZ=-1e9; rooms.filter(r=>(r.floor||1)===floorN).forEach(r=>{ minX=Math.min(minX,r.gx); maxX=Math.max(maxX,r.gx+r.gw); minZ=Math.min(minZ,r.gy); maxZ=Math.max(maxZ,r.gy+r.gd); });
    v.orbit.tx=(minX+maxX)/2; v.orbit.tz=(minZ+maxZ)/2+1;
    const span=Math.max(maxX-minX, maxZ-minZ); v.orbit.dist=span*(v.w&&v.h&&v.w<v.h?2.05:1.45)*(v.opts.zoom||1);
    v.builtKey=floorN+"|"+rooms.length+"|"+v.w+"x"+v.h;
  }

  function pinIcon(t){ return FHHome.haIcon(t); }
  function pinLabel(t){ if(t.domain==="sensor") return (t.state||"")+(t.unit||""); if(t.domain==="climate"&&t.current_temperature!=null) return t.current_temperature+"°"; return ""; }

  function update(v, h, rooms, floorN){
    // state-driven bits: lights, screens, pins, labels
    v.overlay.innerHTML=""; v.anchors=[];
    const fr=rooms.filter(r=>(r.floor||1)===floorN);
    const byRoom=devicesByRoom(h, fr);
    const night=nightFactor();
    v.hemi.intensity=1.05-0.6*night; v.sun.intensity=1.35-1.0*night; v.fill.intensity=0.35-0.15*night;
    v.renderer.toneMappingExposure=1.05-0.12*night;
    const E=esc;
    fr.forEach(r=>{
      const cx=r.gx+r.gw/2, cz=r.gy+r.gd/2, devs=byRoom.get(r)||[];
      const light=r.light||devs.find(t=>t.domain==="light")||devs.find(t=>t.domain==="switch"&&/light|lamp/i.test(t.name));
      const media=r.media||devs.find(t=>t.domain==="media_player");
      const on=!!(light&&light.on);
      // point light per room (only rooms that have one)
      if(light){
        let L=v.lights.get(r.name); if(!L){ L=new THREE.PointLight(0xffd59a, 0, Math.max(r.gw,r.gd)*1.6, 1.6); v.scene.add(L); v.lights.set(r.name,L); }
        L.position.set(cx, WALL_H+1.2, cz); L.intensity=on?(55+Math.min(r.gw,r.gd)*6)*(0.6+0.6*night):0;
      }
      // TV: thin glowing slab on the room's long wall
      if(media&&!isOutside(r.key)){
        let S=v.screens.get(r.name);
        if(!S){ S=new THREE.Mesh(new THREE.BoxGeometry(4.2,2.4,0.18), new THREE.MeshStandardMaterial({color:COL.screenOff, emissive:COL.screenOn, emissiveIntensity:0, roughness:.4}));
          const onNorth=r.gw>=r.gd; if(onNorth){ S.position.set(cx, 2.4, r.gy+T/2+0.12); } else { S.position.set(r.gx+T/2+0.12, 2.4, cz); S.rotation.y=Math.PI/2; }
          v.built.add(S); v.screens.set(r.name,S); }
        S.material.emissiveIntensity=media.on?1.6:0;
      }
      // labels
      if(v.opts.labels!==false && r.gw*r.gd>50){
        const lb=document.createElement("div"); lb.className="h3-lbl"; lb.textContent=r.name; v.overlay.appendChild(lb);
        v.anchors.push({el:lb, pos:new THREE.Vector3(cx, 0.4, cz+(devs.length?Math.min(2.2,r.gd/3):0))});
      }
      // pins
      if(v.opts.pins!==false){
        const shown=devs.filter(t=>t.domain!=="binary_sensor"||["door","garage_door","window","motion"].includes(t.device_class)).slice(0,6);
        const n=shown.length;
        shown.forEach((t,i)=>{
          const p=document.createElement("button"); p.type="button"; p.className="h3-pin"+(t.on&&t.domain!=="sensor"?" on":"")+(t.domain==="sensor"?" ro":"");
          const lab=pinLabel(t); p.innerHTML=`<span class="ic">${pinIcon(t)}</span>${lab?`<span class="lb">${E(lab)}</span>`:""}`; p.title=t.name+" · "+FHHome.haStateLabel(t);
          if(t.domain==="media_player") p.onclick=()=>FHHome.remote(t.entity_id,t.name);
          else if(t.toggleable||t.activatable) p.onclick=()=>FHHome.toggle(t.entity_id);
          else p.classList.add("ro");
          v.overlay.appendChild(p);
          // fan the room's pins out in screen space so they never stack
          v.anchors.push({el:p, pos:new THREE.Vector3(cx, WALL_H+1.4, cz-0.8), dx:(i-(n-1)/2)*44});
        });
      }
    });
    if(v.opts.controls!==false){
      const bar=document.createElement("div"); bar.className="h3-bar";
      bar.innerHTML='<button type="button" class="h3-btn" data-rot="-1" title="Rotate">↺</button><button type="button" class="h3-btn" data-rot="1" title="Rotate">↻</button>';
      bar.querySelectorAll("[data-rot]").forEach(b=>{ b.onclick=()=>v._rotateBy(+b.dataset.rot*Math.PI/4); });
      v.overlay.appendChild(bar);
      if(v.opts.hint!==false){ const hint=document.createElement("div"); hint.className="h3-hint"; hint.textContent=v.opts.pins===false?"Drag to look around":"Drag to orbit · pinch to zoom · tap a pin"; v.overlay.appendChild(hint); }
    }
    requestRender(v);
  }

  FHHome.render3D=function(container, h, opts){
    opts=opts||{}; const id=opts.id||"main";
    if(!window.THREE){ return FHHome.renderIsoView(container,h,opts); }
    const v=getViewer(id); if(!v){ return FHHome.renderIsoView(container,h,opts); }
    v.opts=opts; v.controls=opts.controls!==false;
    const all=FHHome.resolveRooms(h);
    const fs=FHHome.floorsIn(all); if(!fs.includes(FHHome.floor)) FHHome.floor=fs[0]||1;
    const floorN=FHHome.floor;
    container.innerHTML="";
    if(opts.floorButtons!==false && fs.length>1){
      const sw=document.createElement("div"); sw.className="fp-floors";
      sw.innerHTML=fs.map(f=>`<button class="fp-fbtn${f===floorN?' active':''}" data-floor="${f}">${f===1?'Downstairs':f===2?'Upstairs':'Floor '+f}</button>`).join("");
      sw.querySelectorAll(".fp-fbtn").forEach(b=>{ b.onclick=()=>{ FHHome.floor=+b.dataset.floor; FHHome.rerender(); }; });
      container.appendChild(sw);
    }
    v.el.style.height=(opts.height||container.dataset.h3h||360)+"px";
    container.appendChild(v.el);
    resize(v);
    const key=floorN+"|"+all.length+"|"+v.w+"x"+v.h;
    if(v.builtKey!==key){ build(v, all, floorN); }
    update(v, h, all, floorN);
    if(!v.ro){ v.ro=new ResizeObserver(()=>{ resize(v); requestRender(v); }); v.ro.observe(v.el); }
    return v;
  };
  FHHome.has3D=function(){ return !!window.THREE; };
})();
