/* FamilyHub live 3D house — built on three.js (static/vendor/three.min.js, MIT).
   Extrudes the traced floor plan (FHHome layout + plan, units = feet) into a dollhouse-cut
   3D model: floors by room type, walls cut at the real doors (with door leaves, the patio
   slider and a garage door that follows the HA cover), windows where the plan has them,
   the staircase, furniture oriented to the wall each piece sits on, a real point light per
   room that switches with Home Assistant, glowing TVs, and tappable device pins projected
   over the canvas.

   FHHome.render3D(container, h, {id, height, pins, labels, controls, floorButtons, zoom, hint})
     - one WebGL context per `id` (default "main"); the canvas is re-parented into
       whatever container you pass, so re-rendering the surrounding HTML is free.
     - call again with fresh `h` to update light/TV/pin/garage state without rebuilding.
   FHHome.focus3D(id, room) flies into a room, FHHome.reset3D(id) returns to the whole house.
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
    wallTop:0xe9e2d6, wall:0xcfc5b6,
    fabric:0xb9b2a7, fabricDk:0x6f6a64, woodDk:0x5a4030, white:0xeeeae2, dark:0x2f3136, steel:0x9aa0a8,
    car:0x334155, car2:0x7a2f2f, plant:0x3f7a3a, pot:0x8c5a3a, screenOff:0x15171b, screenOn:0x7fc4ff,
    door:0x6b4a33, duvet:0x9fb0c6, pillow:0xf4f1ea, glass:0x1d2a3c, rug:0x4e525c, rug2:0x6d6a66
  };
  const styleOf=k=>{ k=String(k||"").toLowerCase();
    if(/garage/.test(k)) return "concrete"; if(/patio|porch/.test(k)) return "deck";
    if(/bath|laundry|kitchen|pantry|butler|mud/.test(k)) return "tile";
    if(/bedroom|master|loft|flex|sitting|closet|linen/.test(k)) return "carpet"; return "wood"; };
  const isOutside=r=>!!(r.open||/patio|porch/i.test(r.key||r.name||""));
  const isGarage=r=>/garage/i.test(r.key||r.name||"");

  /* ---------- materials + primitives ---------- */
  const mats={};
  function mat(c, o){ const key=c+"|"+JSON.stringify(o||{}); if(!mats[key]) mats[key]=new THREE.MeshStandardMaterial(Object.assign({color:c, roughness:.92, metalness:0}, o||{})); return mats[key]; }
  function box(w,h,d,c,x,y,z,o){ const m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d), mat(c,o)); m.position.set(x,y+h/2,z); m.castShadow=true; m.receiveShadow=true; return m; }
  function cyl(r,h,c,x,y,z,seg){ const m=new THREE.Mesh(new THREE.CylinderGeometry(r,r,h,seg||18), mat(c)); m.position.set(x,y+h/2,z); m.castShadow=true; m.receiveShadow=true; return m; }
  function sph(r,c,x,y,z){ const m=new THREE.Mesh(new THREE.SphereGeometry(r,14,10), mat(c)); m.position.set(x,y,z); m.castShadow=true; return m; }
  function plant(g,x,z,big){ const s=big?1.4:1; g.add(cyl(0.55*s,0.9*s,COL.pot,x,0,z,12)); g.add(sph(0.9*s,COL.plant,x,1.6*s,z)); g.add(sph(0.65*s,0x4f8f44,x+0.5*s,2.1*s,z-0.3*s)); g.add(sph(0.6*s,0x37702f,x-0.5*s,2.0*s,z+0.4*s)); }
  function lamp(g,x,z){ g.add(cyl(0.45,0.12,COL.dark,x,0,z,14)); g.add(cyl(0.06,4.6,COL.dark,x,0.1,z,8)); const sh=new THREE.Mesh(new THREE.CylinderGeometry(0.75,0.95,1.1,16,1,true), new THREE.MeshStandardMaterial({color:0xf1e6d2, emissive:0xffd9a0, emissiveIntensity:0.25, side:THREE.DoubleSide, roughness:1})); sh.position.set(x,5.1,z); g.add(sh); }
  function rug(g,w,d,x,z,c){ const m=new THREE.Mesh(new THREE.BoxGeometry(w,0.06,d), mat(c||COL.rug,{roughness:1})); m.position.set(x,0.03,z); m.receiveShadow=true; g.add(m); }

  /* ---------- procedural surface textures (no image files) ---------- */
  const texCache={};
  function makeTex(kind){
    if(texCache[kind]) return texCache[kind];
    const c=document.createElement("canvas"); c.width=c.height=256; const g=c.getContext("2d");
    const rnd=(a,b)=>a+Math.random()*(b-a);
    if(kind==="wood"||kind==="deck"){
      const base=kind==="wood"?[158,118,80]:[132,100,70];
      for(let row=0;row<8;row++){ const y=row*32, off=(row%2)*96;
        for(let x=-96;x<256;x+=128){ const k=rnd(-14,14); g.fillStyle=`rgb(${base[0]+k},${base[1]+k*0.8},${base[2]+k*0.6})`; g.fillRect(x+off,y,127,31);
          for(let i=0;i<6;i++){ g.fillStyle=`rgba(60,35,15,${rnd(.04,.12)})`; g.fillRect(x+off+rnd(0,120),y+rnd(2,28),rnd(20,80),1); } }
        g.fillStyle="rgba(40,25,10,.55)"; g.fillRect(0,y+31,256,1); }
      for(let row=0;row<8;row++){ const off=(row%2)*96; for(let x=-96;x<256;x+=128){ g.fillStyle="rgba(40,25,10,.45)"; g.fillRect(x+off+127,row*32,1,32); } }
    } else if(kind==="tile"){
      g.fillStyle="#b9b5ad"; g.fillRect(0,0,256,256);
      for(let y=0;y<256;y+=64) for(let x=0;x<256;x+=64){ const k=rnd(-8,8); g.fillStyle=`rgb(${190+k},${186+k},${178+k})`; g.fillRect(x+1,y+1,62,62); }
      g.strokeStyle="rgba(90,86,80,.7)"; g.lineWidth=2; for(let i=0;i<=256;i+=64){ g.beginPath(); g.moveTo(i,0); g.lineTo(i,256); g.moveTo(0,i); g.lineTo(256,i); g.stroke(); }
    } else if(kind==="carpet"){
      g.fillStyle="#8f8a83"; g.fillRect(0,0,256,256); for(let i=0;i<9000;i++){ g.fillStyle=`rgba(${rnd(60,200)},${rnd(60,190)},${rnd(60,180)},.18)`; g.fillRect(rnd(0,256),rnd(0,256),1.5,1.5); }
    } else if(kind==="concrete"){
      g.fillStyle="#7b7d81"; g.fillRect(0,0,256,256); for(let i=0;i<6000;i++){ g.fillStyle=`rgba(${rnd(90,160)},${rnd(90,160)},${rnd(95,165)},.22)`; g.fillRect(rnd(0,256),rnd(0,256),2,2); }
      g.strokeStyle="rgba(50,50,55,.5)"; g.lineWidth=2; g.beginPath(); g.moveTo(128,0); g.lineTo(128,256); g.moveTo(0,128); g.lineTo(256,128); g.stroke();
    } else { g.fillStyle="#9b7752"; g.fillRect(0,0,256,256); }
    const t=new THREE.CanvasTexture(c); t.wrapS=t.wrapT=THREE.RepeatWrapping; t.colorSpace=THREE.SRGBColorSpace; t.anisotropy=4;
    texCache[kind]=t; return t;
  }
  function floorMat(kind, w, d){
    const t=makeTex(kind).clone(); t.needsUpdate=true; const per=kind==="tile"?4:kind==="wood"||kind==="deck"?8:6; t.repeat.set(Math.max(0.5,w/per), Math.max(0.5,d/per));
    return new THREE.MeshStandardMaterial({map:t, roughness:kind==="tile"?.55:.9, metalness:0});
  }

  /* ---------- oriented placement: a group whose local -z faces wall `side`, +z points into the room,
     origin at fraction t along that wall, `off` feet into the room ---------- */
  function placed(r, side, t, off){
    t=t==null?0.5:t; let x,z,rot;
    if(side==="n"){ x=r.gx+r.gw*t; z=r.gy+off; rot=0; }
    else if(side==="s"){ x=r.gx+r.gw*(1-t); z=r.gy+r.gd-off; rot=Math.PI; }
    else if(side==="w"){ x=r.gx+off; z=r.gy+r.gd*(1-t); rot=Math.PI/2; }
    else { x=r.gx+r.gw-off; z=r.gy+r.gd*t; rot=-Math.PI/2; }
    const g=new THREE.Group(); g.position.set(x,0,z); g.rotation.y=rot; return g;
  }
  const along=(r,side)=>(side==="n"||side==="s")?r.gw:r.gd;   // wall length
  const deep =(r,side)=>(side==="n"||side==="s")?r.gd:r.gw;   // room depth away from that wall
  const opposite=s=>({n:"s",s:"n",e:"w",w:"e"}[s]);
  const cw=s=>({n:"e",e:"s",s:"w",w:"n"}[s]);                 // the wall clockwise of `side`

  /* ---------- furniture ---------- */
  function furnish(g, r){
    const k=String(r.key||r.name).toLowerCase(), w=r.gw, d=r.gd, x0=r.gx, z0=r.gy, cx=x0+w/2, cz=z0+d/2;
    if(/bedroom|master/.test(k) && !/closet/.test(k)){
      const side=r.bed||"n", L=along(r,side), D=deep(r,side); if(L<7||D<8) return;
      const master=/master/.test(k)||w*d>170, bw=master?6.4:5.2, bd=master?7:6.6;
      const p=placed(r, side, 0.5, 0.5);                                          // bed centred on its wall
      p.add(box(bw+0.4,3.2,0.35,COL.woodDk,0,0,0.15));                               // headboard
      p.add(box(bw+0.2,0.9,bd+0.2,COL.woodDk,0,0,bd/2+0.3));                        // frame
      p.add(box(bw,0.8,bd,COL.white,0,0.9,bd/2+0.3));                                // mattress
      p.add(box(bw-0.2,0.45,bd*0.62,COL.duvet,0,1.7,bd*0.69+0.3));                   // duvet
      p.add(box(bw*0.42,0.5,1.3,COL.pillow,-bw*0.24,1.7,1.1)); p.add(box(bw*0.42,0.5,1.3,COL.pillow,bw*0.24,1.7,1.1));
      p.add(box(1.6,1.8,1.6,COL.woodDk,-bw/2-1.1,0,1.1)); p.add(box(1.6,1.8,1.6,COL.woodDk,bw/2+1.1,0,1.1)); // nightstands
      const rm=new THREE.Mesh(new THREE.BoxGeometry(bw+4,0.06,bd-0.5), mat(COL.rug2,{roughness:1})); rm.position.set(0,0.03,bd/2+2); rm.receiveShadow=true; p.add(rm);
      g.add(p);
      if(D>11){ const q=placed(r, opposite(side), 0.5, 0.4); q.add(box(Math.min(5,L-3),2.6,1.6,COL.woodDk,0,0,0.8)); g.add(q); } // dresser opposite
      if(master) plant(g, x0+w-1.3, z0+d-1.3, false);
      return;
    }
    if(/living|loft|flex|sitting/.test(k)){
      const side=r.tv||"n", L=along(r,side), D=deep(r,side);
      if(/sitting/.test(k)||L<9||D<9){ // reading corner: two chairs + table
        const p=placed(r, side, 0.5, 1); p.add(box(2.4,1.3,2.4,COL.fabric,-1.8,0,1.2)); p.add(box(2.4,1.1,0.6,COL.fabricDk,-1.8,1.3,0.3)); p.add(box(2.4,1.3,2.4,COL.fabric,1.8,0,1.2)); p.add(box(2.4,1.1,0.6,COL.fabricDk,1.8,1.3,0.3)); p.add(cyl(0.8,1.6,COL.woodDk,0,0,1.2,16)); g.add(p);
        plant(g, x0+0.9, z0+d-0.9, false); return; }
      const tv=placed(r, side, 0.5, 0.15);                                           // TV + console on its wall
      tv.add(box(Math.min(6,L-4),1.8,1.4,COL.woodDk,0,0,0.9)); g.add(tv);
      const sofaOff=Math.min(D-3.5, 10), sw=Math.min(8, L-3);
      const s=placed(r, opposite(side), 0.5, deep(r,side)-sofaOff);                 // sofa faces the TV
      s.add(box(sw,1.3,3,COL.fabricDk,0,0,1.5)); for(let i=0;i<3;i++) s.add(box(sw/3-0.15,0.55,2.4,COL.fabric,-sw/3+i*sw/3,1.3,1.3));
      s.add(box(sw,1.2,0.8,COL.fabricDk,0,1.3,0.4)); s.add(box(0.5,1.9,3,COL.fabricDk,-sw/2-0.25,0,1.5)); s.add(box(0.5,1.9,3,COL.fabricDk,sw/2+0.25,0,1.5));
      s.add(box(3.4,0.2,1.8,COL.woodDk,0,1.2,5.2)); [[-1.5,-0.7],[1.5,-0.7],[-1.5,0.7],[1.5,0.7]].forEach(q=>s.add(box(0.2,1.2,0.2,COL.woodDk,q[0],0,5.2+q[1]))); // coffee table
      const rm=new THREE.Mesh(new THREE.BoxGeometry(Math.min(L-3,sw+4),0.06,Math.min(D-4,8)), mat(COL.rug,{roughness:1})); rm.position.set(0,0.03,4.6); rm.receiveShadow=true; s.add(rm);
      if(L>12){ s.add(box(2.6,1.3,2.6,COL.fabric,-sw/2-2.2,0,4.2)); s.add(box(0.7,1.1,2.6,COL.fabricDk,-sw/2-3.2,1.3,4.2)); } // armchair
      g.add(s);
      lamp(g, x0+w-1.2, z0+d-1.2); plant(g, x0+1.3, z0+1.3, true);
      return;
    }
    if(/dining/.test(k)){ const vert=d>w; const tl=Math.min(7, (vert?d:w)-4), tw=3.4;
      g.add(box(vert?tw:tl,0.25,vert?tl:tw,COL.woodDk,cx,2.3,cz));
      [[-1,-1],[1,-1],[-1,1],[1,1]].forEach(q=>g.add(box(0.4,2.3,0.4,COL.woodDk,cx+q[0]*((vert?tw:tl)/2-0.4),0,cz+q[1]*((vert?tl:tw)/2-0.4))));
      for(let i=-1;i<=1;i++){ const a=i*2.1; if(vert){ g.add(box(1.4,1.5,1.4,COL.fabric,cx-2.6,0,cz+a)); g.add(box(0.3,1.6,1.4,COL.fabricDk,cx-3.15,1.5,cz+a)); g.add(box(1.4,1.5,1.4,COL.fabric,cx+2.6,0,cz+a)); g.add(box(0.3,1.6,1.4,COL.fabricDk,cx+3.15,1.5,cz+a)); }
        else { g.add(box(1.4,1.5,1.4,COL.fabric,cx+a,0,cz-2.6)); g.add(box(1.4,1.6,0.3,COL.fabricDk,cx+a,1.5,cz-3.15)); g.add(box(1.4,1.5,1.4,COL.fabric,cx+a,0,cz+2.6)); g.add(box(1.4,1.6,0.3,COL.fabricDk,cx+a,1.5,cz+3.15)); } }
      plant(g, x0+1.2, z0+1.2, true); return; }
    if(/kitchen/.test(k)){
      const side=r.counter||"e", wx=side==="w"?x0:x0+w, dir=side==="w"?1:-1;
      g.add(box(2,3,d-1.2,COL.white,wx+dir*1,0,cz)); g.add(box(2.15,0.2,d-1.1,COL.dark,wx+dir*1,3,cz));     // run of base cabinets + counter
      g.add(box(1.2,0.4,d-1.2,COL.white,wx+dir*0.6,6,cz));                                                  // uppers (just a hint)
      g.add(box(2.6,6.2,2.6,COL.steel,wx+dir*1.3,0,z0+d-1.5));                                               // fridge at the pantry end
      g.add(box(2.1,3.1,2.6,COL.dark,wx+dir*1.05,0,z0+d*0.55)); for(let i=0;i<4;i++) g.add(cyl(0.28,0.05,COL.dark,wx+dir*(0.5+i*0.35),3.21,z0+d*0.55-0.9+ (i%2)*0.6,10)); // range
      if(w>10){ const iw=4, il=Math.min(6.4,d-4), ix=wx+dir*8.4, iz=z0+0.8+il/2;                           // island parallel to the counter wall
        g.add(box(iw,3,il,COL.woodDk,ix,0,iz)); g.add(box(iw+0.3,0.2,il+0.3,COL.white,ix,3,iz));
        g.add(box(1.6,0.12,2.2,COL.steel,ix-dir*0.8,3.2,iz)); g.add(cyl(0.08,0.9,COL.steel,ix-dir*0.8,3.3,iz-0.8,8));                        // sink + tap
        for(let i=-1;i<=1;i++){ g.add(cyl(0.6,0.15,COL.dark,ix+dir*2.7,2.2,iz+i*1.9,14)); g.add(cyl(0.08,2.2,COL.dark,ix+dir*2.7,0,iz+i*1.9,8)); } } // stools
      return; }
    if(/bath/.test(k)){
      const ts=r.tub||"n", L=along(r,ts), D=deep(r,ts);
      if(L>=5&&D>=4){
        const tub=placed(r, ts, Math.min(0.35, 2.9/L), 0.3); tub.add(box(5.2,1.9,2.7,COL.white,0,0,1.35)); tub.add(box(4.6,0.3,2.1,0xcfe6ee,0,1.6,1.35)); g.add(tub);  // tub
        const wcSide=r.shower?opposite(ts):(L>8?ts:cw(ts)), wcT=r.shower?(1-1.3/along(r,wcSide)):(L>8?1-1.3/L:0.75);
        const wc=placed(r, wcSide, wcT, 0.3); wc.add(cyl(0.75,1.4,COL.white,0,0,1.1,14)); wc.add(box(1.3,2.3,0.7,COL.white,0,0,0.35)); g.add(wc);   // toilet
        const van=placed(r, opposite(ts), 0.5, 0.3); const vl=Math.min(L-1.6, r.gw*r.gd>80?7:4.5);
        van.add(box(vl,2.8,1.9,COL.woodDk,0,0,0.95)); van.add(box(vl+0.2,0.15,2.0,COL.white,0,2.8,0.95));
        for(let i=0;i<(vl>6?2:1);i++) van.add(box(1.3,0.1,0.9,0xd6dde4,vl>6?(i?1.6:-1.6):0,2.96,0.95));
        van.add(box(vl-0.4,2.4,0.08,0xbfd3e4,0,3.3,0.1,{metalness:.3,roughness:.1})); g.add(van);                                                                     // vanity + mirror
        if(r.shower){ const sx=/e/.test(r.shower)?x0+w-1.9:x0+1.9, sz=/s/.test(r.shower)?z0+d-1.9:z0+1.9;
          g.add(box(3.6,0.4,3.6,0xcfd4d8,sx,0,sz)); const gl=new THREE.Mesh(new THREE.BoxGeometry(3.6,4.2,3.6), new THREE.MeshStandardMaterial({color:0xbfd8ea,transparent:true,opacity:.28,roughness:.05,metalness:.1})); gl.position.set(sx,2.5,sz); g.add(gl); }
      }
      return; }
    if(/laundry/.test(k)){ const p=placed(r,"n",0.5,0.4); p.add(box(2.4,3,2.4,COL.white,-1.35,0,1.2)); p.add(box(2.4,3,2.4,COL.white,1.35,0,1.2)); p.add(cyl(0.9,0.1,COL.dark,-1.35,2.1,0.35,16).rotateX(Math.PI/2)); p.add(cyl(0.9,0.1,COL.dark,1.35,2.1,0.35,16).rotateX(Math.PI/2)); g.add(p); return; }
    if(/pantry|butler|closet|linen|mud/.test(k)){
      const longSide=w>=d?"n":"w", L=along(r,longSide);
      const p=placed(r,longSide,0.5,0.3); for(let i=0;i<4;i++) p.add(box(Math.max(1,L-1.2),0.12,1.1,COL.woodDk,0,1.2+i*1.3,0.55)); p.add(box(Math.max(1,L-1.2),0.4,1.1,COL.woodDk,0,0,0.55)); g.add(p);
      if(/mud/.test(k)){ const b=placed(r, opposite(longSide), 0.5, 0.3); b.add(box(Math.max(1,L-1.5),1.5,1.4,COL.woodDk,0,0,0.7)); g.add(b); }
      return; }
    if(/garage/.test(k)){ if(w<9||d<15) return;
      const car=(cxx,czz,c)=>{ g.add(box(6,2.2,15,c,cxx,0.9,czz)); g.add(box(5.2,2,7.5,COL.dark,cxx,3.1,czz+0.4)); [[-2.6,-5],[2.6,-5],[-2.6,5],[2.6,5]].forEach(p=>{ const wh=cyl(1.15,0.9,COL.dark,cxx+p[0],0,czz+p[1],16); wh.rotation.z=Math.PI/2; wh.position.y=1.15; g.add(wh); }); };
      car(cx-(w>16?4.6:0), cz+1, COL.car); if(w>16) car(cx+4.6, cz+1, COL.car2);
      g.add(cyl(1,5,COL.white,x0+1.5,0,z0+1.5,16));                                                   // water heater
      const sh=placed(r,"n",0.5,0.3); for(let i=0;i<3;i++) sh.add(box(Math.min(10,w-6),0.12,1.4,COL.steel,0,1.5+i*1.6,0.7)); g.add(sh); // shelving
      return; }
    if(/foyer/.test(k)){ if(d>8){ const side=w>d?"n":"w"; const p=placed(r, side==="w"?"w":"n", 0.3, 0.3); p.add(box(3.2,2.6,1.1,COL.woodDk,0,0,0.55)); g.add(p); rug(g, Math.min(w-1.5,4), Math.min(d-2,6), cx, z0+d-4, COL.rug2); } return; }
    if(/porch/.test(k)){ // chairs, planters and the porch posts
      g.add(box(1.8,1.6,1.8,COL.fabricDk,cx-1.6,0,cz)); g.add(box(1.8,1.6,1.8,COL.fabricDk,cx+1.6,0,cz)); g.add(cyl(0.9,1.5,COL.woodDk,cx,0,cz-2,16));
      plant(g,x0+0.9,z0+0.9,true); if(w>8) plant(g,x0+w-0.9,z0+0.9,false);
      const n=Math.max(2,Math.round(w/9)); for(let i=0;i<=n;i++) g.add(box(0.7,EXT_H+1.4,0.7,COL.wallTop,x0+0.35+(w-0.7)*i/n,0,z0+d-0.35));
      return; }
    if(/patio/.test(k)){ g.add(cyl(1.6,0.12,COL.dark,cx,2.3,cz,20)); g.add(cyl(0.12,2.3,COL.dark,cx,0,cz,8)); [[-2.4,0],[2.4,0],[0,-2.4],[0,2.4]].forEach(p=>g.add(box(1.5,1.4,1.5,COL.fabricDk,cx+p[0],0,cz+p[1]))); plant(g,x0+1,z0+d-1,false); return; }
  }

  /* ---------- stairs ---------- */
  function stairs(g, s){ // s = {gx,gy,gw,gd,up:"n"|"s"|"e"|"w"}
    const n=9, rise=0.55, vert=(s.up==="n"||s.up==="s"), run=(vert?s.gd:s.gw)/n;
    for(let i=0;i<n;i++){
      const t=(i+0.5)/n, h=(i+1)*rise;
      let x,z; if(s.up==="n"){ x=s.gx+s.gw/2; z=s.gy+s.gd*(1-t); } else if(s.up==="s"){ x=s.gx+s.gw/2; z=s.gy+s.gd*t; } else if(s.up==="w"){ x=s.gx+s.gw*(1-t); z=s.gy+s.gd/2; } else { x=s.gx+s.gw*t; z=s.gy+s.gd/2; }
      g.add(box(vert?s.gw-0.8:run, h, vert?run:s.gd-0.8, COL.woodDk, x, 0, z));
    }
    // handrail on both long sides
    const posts=5; for(let i=0;i<=posts;i++){ const t=i/posts, h=0.6+t*rise*n*0.95;
      if(vert){ const z=s.up==="n"?s.gy+s.gd*(1-t):s.gy+s.gd*t; g.add(box(0.12,h+2.4,0.12,COL.dark,s.gx+0.3,0,z)); g.add(box(0.12,h+2.4,0.12,COL.dark,s.gx+s.gw-0.3,0,z)); }
      else { const x=s.up==="w"?s.gx+s.gw*(1-t):s.gx+s.gw*t; g.add(box(0.12,h+2.4,0.12,COL.dark,x,0,s.gy+0.3)); g.add(box(0.12,h+2.4,0.12,COL.dark,x,0,s.gy+s.gd-0.3)); } }
  }
  function stairwell(g, s){ // opening in the upper floor + railing
    const pit=new THREE.Mesh(new THREE.BoxGeometry(s.gw-0.3,0.5,s.gd-0.3), mat(0x14161a)); pit.position.set(s.gx+s.gw/2,0.1,s.gy+s.gd/2); g.add(pit);
    const rail=(x0,z0,x1,z1)=>{ const n=Math.max(2,Math.round(Math.hypot(x1-x0,z1-z0)/1.2)); for(let i=0;i<=n;i++){ const t=i/n; g.add(box(0.1,3,0.1,COL.dark,x0+(x1-x0)*t,0,z0+(z1-z0)*t)); }
      const len=Math.hypot(x1-x0,z1-z0), m=box(len,0.12,0.12,COL.woodDk,(x0+x1)/2,2.95,(z0+z1)/2); m.rotation.y=-Math.atan2(z1-z0,x1-x0); g.add(m); };
    rail(s.gx+s.gw,s.gy,s.gx+s.gw,s.gy+s.gd); rail(s.gx,s.gy+s.gd,s.gx+s.gw,s.gy+s.gd);
  }

  /* ---------- walls (cut at the plan's doors), door leaves, windows ---------- */
  function buildFloor(rooms, floorN, ghost, plan){
    const g=new THREE.Group(); g.userData.wins=[]; g.userData.doors=[];
    const fr=rooms.filter(r=>(r.floor||1)===floorN);
    const eq=(a,b)=>Math.abs(a-b)<0.05;
    const overlap=(a0,a1,b0,b1)=>Math.min(a1,b1)-Math.max(a0,b0);
    const wallMat=ghost?mat(COL.wall,{transparent:true,opacity:.16,depthWrite:false}):mat(COL.wall);
    const topMat=ghost?wallMat:mat(COL.wallTop);
    const doors=plan?plan.doors.filter(d=>d.f===floorN):null, wins=plan?plan.windows.filter(d=>d.f===floorN):[];
    const roomAt=(x,z)=>fr.find(r=>x>=r.gx-0.3&&x<=r.gx+r.gw+0.3&&z>=r.gy-0.3&&z<=r.gy+r.gd+0.3&&!isOutside(r))||fr.find(r=>x>=r.gx-0.3&&x<=r.gx+r.gw+0.3&&z>=r.gy-0.3&&z<=r.gy+r.gd+0.3);
    const seg=(x0,z0,x1,z1,h)=>{
      const len=Math.hypot(x1-x0,z1-z0); if(len<0.15) return;
      const horiz=Math.abs(z1-z0)<0.01;
      const m=new THREE.Mesh(new THREE.BoxGeometry(horiz?len:T, h, horiz?T:len), wallMat);
      m.position.set((x0+x1)/2, h/2, (z0+z1)/2); m.castShadow=!ghost; m.receiveShadow=!ghost; g.add(m);
      if(!ghost){ const cap=new THREE.Mesh(new THREE.BoxGeometry((horiz?len:T)+0.02, 0.08, (horiz?T:len)+0.02), topMat); cap.position.set((x0+x1)/2, h+0.04, (z0+z1)/2); g.add(cap); }
    };
    const run=(x0,z0,x1,z1,h,gaps)=>{ // split a wall around gaps [[a,b],...] measured along the run
      const horiz=Math.abs(z1-z0)<0.01, a0=horiz?x0:z0, a1=horiz?x1:z1;
      let cur=a0; (gaps||[]).sort((p,q)=>p[0]-q[0]).forEach(([ga,gb])=>{ ga=Math.max(ga,a0); gb=Math.min(gb,a1); if(gb<=cur) return; horiz?seg(cur,z0,Math.max(cur,ga),z0,h):seg(x0,cur,x0,Math.max(cur,ga),h); cur=Math.max(cur,gb); });
      horiz?seg(cur,z0,a1,z0,h):seg(x0,cur,x0,a1,h);
    };
    // door gaps on an edge: from the plan when we have one, else guessed at the middle of shared edges
    const gapsOn=(horiz, c, a0, a1, neighbours, room)=>{
      if(doors){ return doors.filter(d=>d.dir===(horiz?"h":"v")&&Math.abs((horiz?d.z:d.x)-c)<0.3&&d.x!==undefined&&(horiz?d.x:d.z)>a0-0.1&&(horiz?d.x:d.z)<a1+0.1).map(d=>{ const p=horiz?d.x:d.z; return [p-d.w/2,p+d.w/2]; }); }
      const gaps=neighbours.map(s=>{ const lo=Math.max(a0, horiz?s.gx:s.gy), hi=Math.min(a1, horiz?s.gx+s.gw:s.gy+s.gd), m=(lo+hi)/2, hw=isOutside(s)?3:1.5; return [m-hw,m+hw]; });
      if(!neighbours.length&&isGarage(room)&&horiz&&c>room.gy+room.gd-0.1){ const m=(a0+a1)/2; gaps.push([m-8,m+8]); }
      if(!neighbours.length&&/foyer/i.test(room.key||"")&&horiz&&c>room.gy+room.gd-0.1){ const m=(a0+a1)/2; gaps.push([m-1.6,m+1.6]); }
      return gaps;
    };
    fr.forEach(r=>{
      if(!ghost){
        const f=new THREE.Mesh(new THREE.BoxGeometry(r.gw-0.04,0.32,r.gd-0.04), floorMat(styleOf(r.key), r.gw, r.gd));
        f.position.set(r.gx+r.gw/2,-0.16,r.gy+r.gd/2); f.userData.room=r; f.receiveShadow=true; g.add(f);
      }
      if(isOutside(r)){ if(!ghost){ const c=new THREE.Mesh(new THREE.BoxGeometry(r.gw,0.5,0.3), mat(COL.wallTop)); c.position.set(r.gx+r.gw/2,0.25,r.gy+r.gd-0.15); g.add(c); furnish(g,r); } return; }
      // NORTH (z=gy) and WEST (x=gx) edges are always drawn by this room; SOUTH/EAST only when no neighbour owns them.
      { const nb=fr.filter(s=>s!==r&&eq(s.gy+s.gd,r.gy)&&overlap(r.gx,r.gx+r.gw,s.gx,s.gx+s.gw)>1&&!isOutside(s));
        const ext=!nb.length;
        run(r.gx,r.gy,r.gx+r.gw,r.gy, ext?EXT_H:WALL_H, gapsOn(true,r.gy,r.gx,r.gx+r.gw,nb,r)); }
      { const nb=fr.filter(s=>s!==r&&eq(s.gx+s.gw,r.gx)&&overlap(r.gy,r.gy+r.gd,s.gy,s.gy+s.gd)>1&&!isOutside(s));
        const ext=!nb.length;
        run(r.gx,r.gy,r.gx,r.gy+r.gd, ext?EXT_H:WALL_H, gapsOn(false,r.gx,r.gy,r.gy+r.gd,nb,r)); }
      if(!fr.some(s=>s!==r&&!isOutside(s)&&eq(s.gy,r.gy+r.gd)&&overlap(r.gx,r.gx+r.gw,s.gx,s.gx+s.gw)>0.5)){
        run(r.gx,r.gy+r.gd,r.gx+r.gw,r.gy+r.gd,EXT_H,gapsOn(true,r.gy+r.gd,r.gx,r.gx+r.gw,[],r)); }
      if(!fr.some(s=>s!==r&&!isOutside(s)&&eq(s.gx,r.gx+r.gw)&&overlap(r.gy,r.gy+r.gd,s.gy,s.gy+s.gd)>0.5)){
        run(r.gx+r.gw,r.gy,r.gx+r.gw,r.gy+r.gd,EXT_H,gapsOn(false,r.gx+r.gw,r.gy,r.gy+r.gd,[],r)); }
      if(!ghost){ furnish(g,r); if(r.stairs) stairs(g,r.stairs); if(r.stairwell) stairwell(g,r.stairwell); }
    });
    if(ghost) return g;
    // door leaves, sliders, garage door
    (doors||[]).forEach(d=>{
      const horiz=d.dir==="h", room=roomAt(d.x,d.z);
      if(d.type==="door"||d.type==="front"){ const leaf=box(d.w-0.1,3.1,0.1,d.type==="front"?0x4a2f22:COL.door,0,0,0); const piv=new THREE.Group(); piv.position.set(horiz?d.x-d.w/2:d.x, 0, horiz?d.z:d.z-d.w/2); piv.rotation.y=(horiz?0:Math.PI/2)+(0.42*Math.PI); leaf.position.set((d.w-0.1)/2,1.55,0); piv.add(leaf); g.add(piv); }
      else if(d.type==="double"){ [-1,1].forEach(s=>{ const leaf=box(d.w/2-0.1,3.1,0.1,COL.door,0,0,0); const piv=new THREE.Group(); piv.position.set(horiz?d.x+s*d.w/2:d.x, 0, horiz?d.z:d.z+s*d.w/2); piv.rotation.y=(horiz?0:Math.PI/2)+(s<0?0.4*Math.PI:-0.6*Math.PI); leaf.position.set((d.w/2-0.1)/2,1.55,0); piv.add(leaf); g.add(piv); }); }
      else if(d.type==="slider"){ const pane=new THREE.Mesh(new THREE.BoxGeometry(horiz?d.w:T+0.06, EXT_H-0.3, horiz?T+0.06:d.w), new THREE.MeshStandardMaterial({color:COL.glass, emissive:0x7fa6e0, emissiveIntensity:0, roughness:.15, metalness:.2, transparent:true, opacity:.75})); pane.position.set(d.x,(EXT_H-0.3)/2,d.z); pane.userData.win=room?room.name:""; g.add(pane); g.userData.wins.push(pane);
        const fr2=box(horiz?d.w:0.2,0.15,horiz?0.2:d.w,COL.dark,d.x,0,d.z); g.add(fr2); }
      else if(d.type==="garage"){ const panel=box(horiz?d.w:0.3, EXT_H-0.2, horiz?0.3:d.w, 0xd9d4cb, d.x, 0, d.z); for(let i=1;i<4;i++){ const line=box(horiz?d.w:0.32,0.06,horiz?0.32:d.w,0xb9b3a8,d.x,i*(EXT_H-0.2)/4,d.z); g.add(line); g.userData.doors.push(line); } panel.userData.garage=true; g.add(panel); g.userData.doors.push(panel); }
    });
    wins.forEach(wd=>{ const horiz=wd.dir==="h", room=roomAt(wd.x,wd.z); if(room&&isGarage(room)) return;
      const m=new THREE.Mesh(new THREE.BoxGeometry(horiz?wd.w:T+0.06, 1.6, horiz?T+0.06:wd.w), new THREE.MeshStandardMaterial({color:COL.glass, emissive:0x7fa6e0, emissiveIntensity:0, roughness:.15, metalness:.2}));
      m.position.set(wd.x, EXT_H-1.6, wd.z); m.userData.win=room?room.name:""; g.add(m); g.userData.wins.push(m);
      const sill=box(horiz?wd.w+0.3:T+0.2,0.1,horiz?T+0.2:wd.w+0.3,COL.wallTop,wd.x,EXT_H-2.45,wd.z); g.add(sill); });
    // guessed windows when there's no plan: middle of long exterior walls
    if(!plan){ fr.forEach(r=>{ if(isOutside(r)||isGarage(r)) return;
      const edges=[[r.gx+r.gw/2,r.gy,true,r.gw],[r.gx+r.gw/2,r.gy+r.gd,true,r.gw],[r.gx,r.gy+r.gd/2,false,r.gd],[r.gx+r.gw,r.gy+r.gd/2,false,r.gd]];
      edges.forEach(([x,z,horiz,len])=>{ if(len<6) return; const other=fr.find(s=>s!==r&&x>s.gx-0.1&&x<s.gx+s.gw+0.1&&z>s.gy-0.1&&z<s.gy+s.gd+0.1); if(other) return;
        const m=new THREE.Mesh(new THREE.BoxGeometry(horiz?3.2:T+0.06,1.5,horiz?T+0.06:3.2), new THREE.MeshStandardMaterial({color:COL.glass, emissive:0x7fa6e0, emissiveIntensity:0, roughness:.15, metalness:.2})); m.position.set(x,EXT_H-1.6,z); m.userData.win=r.name; g.add(m); g.userData.wins.push(m); }); }); }
    return g;
  }

  /* ---------- device placement inside a room ---------- */
  function devicesByRoom(h, rooms){
    const tiles=FHHome.tilesOf(h), lc=s=>String(s||"").toLowerCase(), out=new Map(), used=new Set();
    rooms.forEach(r=>out.set(r, []));
    const want=t=>t.toggleable||t.activatable||t.domain==="media_player"||t.domain==="sensor"||t.domain==="binary_sensor"||t.domain==="lock"||t.domain==="climate"||t.domain==="cover";
    tiles.forEach(t=>{
      if(!want(t)||t.domain==="scene"||t.domain==="script") return;
      const hit=rooms.find(r=>lc(t.area)&&lc(t.area)===lc(r.name)) || rooms.find(r=>lc(t.name).includes(lc(r.key))) || rooms.find(r=>lc(t.area||"").includes(lc(r.key)));
      if(hit){ out.get(hit).push(t); used.add(t.entity_id); }
    });
    tiles.forEach(t=>{ if(used.has(t.entity_id)) return;
      if(t.domain==="lock"||t.domain==="alarm_control_panel"||(t.domain==="binary_sensor"&&/front/i.test(t.name))){
        const foyer=rooms.find(r=>/foyer|entry/i.test(r.key||r.name))||rooms.find(r=>(r.floor||1)===1&&/hall/i.test(r.key||r.name)); if(foyer){ out.get(foyer).push(t); used.add(t.entity_id); } }
      if(t.domain==="cover"&&/garage/i.test(t.name)){ const gar=rooms.find(r=>isGarage(r)); if(gar){ out.get(gar).push(t); used.add(t.entity_id); } }
      // outdoor HA areas that aren't rooms: driveway/yard → garage, back yard/garden → patio, front → porch
      if(!used.has(t.entity_id)&&t.area){ const a=lc(t.area); let host=null;
        if(/drive|yard|garden|outside|exterior/.test(a)&&!/back/.test(a)) host=rooms.find(r=>isGarage(r));
        if(/back|garden|pool|deck/.test(a)) host=rooms.find(r=>/patio/i.test(r.key||r.name));
        if(/front|entry|street/.test(a)) host=rooms.find(r=>/porch/i.test(r.key||r.name));
        if(host){ out.get(host).push(t); used.add(t.entity_id); } } });
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
    renderer.shadowMap.enabled=true; renderer.shadowMap.type=THREE.PCFSoftShadowMap;
    const el=document.createElement("div"); el.className="h3"; el.innerHTML='<div class="h3-overlay"></div>';
    el.prepend(renderer.domElement);
    const v={id, renderer, el, overlay:el.querySelector(".h3-overlay"), scene:new THREE.Scene(),
      camera:new THREE.PerspectiveCamera(32,1,0.5,600), orbit:{theta:0.55, phi:0.98, dist:80, tx:0, tz:0},
      built:null, lights:new Map(), screens:new Map(), anchors:[], raf:0, w:0, h:0, wins:[], garage:[]};
    v.hemi=new THREE.HemisphereLight(0x9fb3d9, 0x4a3b2e, 1.0); v.scene.add(v.hemi);
    v.sun=new THREE.DirectionalLight(0xfff1dd, 1.3); v.sun.position.set(-40,70,50); v.scene.add(v.sun); v.scene.add(v.sun.target);
    v.sun.castShadow=true; v.sun.shadow.mapSize.set(2048,2048); v.sun.shadow.bias=-0.0008; v.sun.shadow.normalBias=0.03;
    const sc=v.sun.shadow.camera; sc.near=10; sc.far=220; sc.left=sc.bottom=-50; sc.right=sc.top=50;
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
        const cx=(a[0].x+a[1].x)/2, cy=(a[0].y+a[1].y)/2, s=v.orbit.dist/900;
        const ct=Math.cos(v.orbit.theta), st=Math.sin(v.orbit.theta), px=-(cx-pinch.cx)*s, pz=-(cy-pinch.cy)*s;
        v.orbit.tx=pinch.tx+px*ct-pz*st; v.orbit.tz=pinch.tz+px*st+pz*ct; moved=true; req(); } });
    const up=e=>{ ptrs.delete(e.pointerId); if(ptrs.size<2) pinch=null; if(ptrs.size===0) last=null; };
    el.addEventListener("pointerup",up); el.addEventListener("pointercancel",up);
    el.addEventListener("wheel",e=>{ if(!v.controls) return; e.preventDefault(); v.orbit.dist=Math.max(18,Math.min(200,v.orbit.dist*(1+Math.sign(e.deltaY)*0.08))); req(); },{passive:false});
    v._rotateBy=d=>{ const from=v.orbit.theta, to=from+d, t0=performance.now(); const step=()=>{ const k=Math.min(1,(performance.now()-t0)/380), e=1-Math.pow(1-k,3); v.orbit.theta=from+(to-from)*e; requestRender(v); if(k<1) requestAnimationFrame(step); }; step(); };
    v._flyTo=(to,ms)=>{ const o=v.orbit, from={tx:o.tx,tz:o.tz,dist:o.dist,phi:o.phi}, t0=performance.now(); ms=ms||650;
      const step=()=>{ const k=Math.min(1,(performance.now()-t0)/ms), e=1-Math.pow(1-k,3); ["tx","tz","dist","phi"].forEach(p=>{ if(to[p]!=null) o[p]=from[p]+(to[p]-from[p])*e; }); requestRender(v); if(k<1) requestAnimationFrame(step); }; step(); };
  }

  function requestRender(v){ if(v.raf) return; v.raf=requestAnimationFrame(()=>{ v.raf=0; frame(v); }); }
  function frame(v){
    const o=v.orbit, cam=v.camera;
    const cy=o.dist*Math.sin(o.phi), r=o.dist*Math.cos(o.phi);
    cam.position.set(o.tx+r*Math.sin(o.theta), cy, o.tz+r*Math.cos(o.theta));
    cam.lookAt(o.tx, 0, o.tz);
    v.renderer.render(v.scene, cam);
    const w=v.w, h=v.h, tmp=new THREE.Vector3();
    v.anchors.forEach(a=>{ tmp.copy(a.pos).project(cam); const x=(tmp.x+1)/2*w+(a.dx||0), y=(1-tmp.y)/2*h+(a.dy||0); const vis=tmp.z<1&&x>-20&&x<w+20&&y>-20&&y<h+20;
      a.el.style.transform=`translate(${x.toFixed(1)}px,${y.toFixed(1)}px) translate(-50%,-50%)`; a.el.style.opacity=vis?"":"0"; a.el.style.pointerEvents=vis?"":"none"; });
  }
  function resize(v){ const w=v.el.clientWidth||1, h=v.el.clientHeight||1; if(w===v.w&&h===v.h) return; v.w=w; v.h=h; v.renderer.setSize(w,h,false); v.renderer.domElement.style.width="100%"; v.renderer.domElement.style.height="100%"; v.camera.aspect=w/h; v.camera.updateProjectionMatrix(); }

  function build(v, rooms, floorN){
    if(v.built){ v.root.remove(v.built); v.built.traverse(o=>{ if(o.geometry) o.geometry.dispose(); }); }
    v.lights.forEach(l=>v.scene.remove(l)); v.lights.clear(); v.screens.clear();
    const plan=FHHome.getPlan?FHHome.getPlan():null;
    const g=new THREE.Group();
    const main=buildFloor(rooms, floorN, false, plan); g.add(main);
    v.wins=main.userData.wins||[]; v.garage=main.userData.doors||[];
    if(floorN>1){ const ghost=buildFloor(rooms, floorN-1, true, plan); ghost.position.y=-LEVEL_H; g.add(ghost); }
    const ext=FHHome.layoutExtent(rooms);
    const plate=new THREE.Mesh(new THREE.PlaneGeometry(ext*2.2, ext*2.2), new THREE.MeshBasicMaterial({color:0x000000, transparent:true, opacity:0.22})); plate.rotation.x=-Math.PI/2; plate.position.set(ext/2,-0.45-(floorN>1?LEVEL_H:0),ext/2); g.add(plate);
    v.root.add(g); v.built=g;
    let minX=1e9,maxX=-1e9,minZ=1e9,maxZ=-1e9; rooms.filter(r=>(r.floor||1)===floorN).forEach(r=>{ minX=Math.min(minX,r.gx); maxX=Math.max(maxX,r.gx+r.gw); minZ=Math.min(minZ,r.gy); maxZ=Math.max(maxZ,r.gy+r.gd); });
    v.orbit.tx=(minX+maxX)/2; v.orbit.tz=(minZ+maxZ)/2+1;
    const span=Math.max(maxX-minX, maxZ-minZ); v.orbit.dist=span*(v.w&&v.h&&v.w<v.h?2.05:1.45)*(v.opts.zoom||1);
    v.home={tx:v.orbit.tx, tz:v.orbit.tz, dist:v.orbit.dist, phi:0.98};
    v.sun.position.set(v.orbit.tx-40, 70, v.orbit.tz+50); v.sun.target.position.set(v.orbit.tx, 0, v.orbit.tz);
    v.builtKey=floorN+"|"+rooms.length+"|"+v.w+"x"+v.h;
  }

  function pinLabel(t){ if(t.domain==="sensor") return (t.state||"")+(t.unit||""); if(t.domain==="climate"&&t.current_temperature!=null) return t.current_temperature+"°"; return ""; }

  function update(v, h, rooms, floorN){
    v.overlay.innerHTML=""; v.anchors=[];
    const fr=rooms.filter(r=>(r.floor||1)===floorN);
    const byRoom=devicesByRoom(h, fr);
    const night=nightFactor();
    v.hemi.intensity=1.05-0.6*night; v.sun.intensity=1.35-1.0*night; v.fill.intensity=0.35-0.15*night;
    v.renderer.toneMappingExposure=1.05-0.12*night;
    const E=esc;
    const litRooms=new Set(); fr.forEach(r=>{ const devs=byRoom.get(r)||[]; const l=r.light||devs.find(t=>t.domain==="light"); if(l&&l.on) litRooms.add(r.name); });
    (v.wins||[]).forEach(wm=>{ const lit=litRooms.has(wm.userData.win); wm.material.emissive.setHex(lit?0xffc98a:0x7fa6e0); wm.material.emissiveIntensity=lit?0.9:0.35*night; });
    // garage door follows the HA cover (closed = panel shown); no cover entity = closed
    const gar=fr.find(r=>isGarage(r)); const cover=gar?(byRoom.get(gar)||[]).find(t=>t.domain==="cover"):null;
    const garOpen=!!(cover&&/open/.test(cover.state||"")); (v.garage||[]).forEach(m=>{ m.visible=!garOpen; });
    fr.forEach(r=>{
      const cx=r.gx+r.gw/2, cz=r.gy+r.gd/2, devs=byRoom.get(r)||[];
      const light=r.light||devs.find(t=>t.domain==="light")||devs.find(t=>t.domain==="switch"&&/light|lamp|led/i.test(t.name));
      const media=r.media||devs.find(t=>t.domain==="media_player");
      const on=!!(light&&light.on);
      if(light){
        let L=v.lights.get(r.name); if(!L){ L=new THREE.PointLight(0xffd59a, 0, Math.max(r.gw,r.gd)*1.6, 1.6); v.scene.add(L); v.lights.set(r.name,L); }
        L.position.set(cx, WALL_H+1.2, cz); L.intensity=on?(55+Math.min(r.gw,r.gd)*6)*(0.6+0.6*night):0;
      }
      if(media&&!isOutside(r)){
        let S=v.screens.get(r.name);
        if(!S){ const side=r.tv||"n"; S=new THREE.Mesh(new THREE.BoxGeometry(4.6,2.6,0.16), new THREE.MeshStandardMaterial({color:COL.screenOff, emissive:COL.screenOn, emissiveIntensity:0, roughness:.4}));
          const p=placed(r, side, 0.5, T/2+0.2); S.position.set(0,3.3,0); p.add(S); v.built.add(p); v.screens.set(r.name,S); }
        S.material.emissiveIntensity=media.on?1.6:0;
      }
      if(v.opts.labels!==false && r.gw*r.gd>50){
        const lb=document.createElement("div"); lb.className="h3-lbl"; lb.textContent=r.name; v.overlay.appendChild(lb);
        v.anchors.push({el:lb, pos:new THREE.Vector3(cx, 0.4, cz+(devs.length?Math.min(2.2,r.gd/3):0))});
      }
      if(v.opts.pins!==false){
        const shown=devs.filter(t=>t.domain!=="binary_sensor"||["door","garage_door","window","motion"].includes(t.device_class)).slice(0,6);
        const n=shown.length;
        shown.forEach((t,i)=>{
          const p=document.createElement("button"); p.type="button"; p.className="h3-pin"+(t.on&&t.domain!=="sensor"?" on":"")+(t.domain==="sensor"?" ro":"");
          const lab=pinLabel(t); p.innerHTML=`<span class="ic">${FHHome.haIcon(t)}</span>${lab?`<span class="lb">${E(lab)}</span>`:""}`; p.title=t.name+" · "+FHHome.haStateLabel(t);
          if(t.domain==="media_player") p.onclick=()=>FHHome.remote(t.entity_id,t.name);
          else if(t.toggleable||t.activatable) p.onclick=()=>FHHome.toggle(t.entity_id);
          else p.classList.add("ro");
          v.overlay.appendChild(p);
          v.anchors.push({el:p, pos:new THREE.Vector3(cx, WALL_H+1.4, cz-0.8), dx:(i-(n-1)/2)*44});
        });
      }
    });
    if(v.opts.controls!==false){
      const bar=document.createElement("div"); bar.className="h3-bar";
      bar.innerHTML='<button type="button" class="h3-btn" data-rot="-1" title="Rotate">↺</button><button type="button" class="h3-btn" data-rot="1" title="Rotate">↻</button><button type="button" class="h3-btn" data-home="1" title="Whole house">⌂</button>';
      bar.querySelectorAll("[data-rot]").forEach(b=>{ b.onclick=()=>v._rotateBy(+b.dataset.rot*Math.PI/4); });
      bar.querySelector("[data-home]").onclick=()=>v._flyTo(v.home);
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
  FHHome.focus3D=function(id, room){
    const v=viewers[id||"main"]; if(!v||!room) return false;
    if((room.floor||1)!==FHHome.floor){ FHHome.floor=room.floor||1; FHHome.rerender(); }
    v._flyTo({tx:room.gx+room.gw/2, tz:room.gy+room.gd/2+1.5, dist:Math.max(room.gw,room.gd)*2.3*(v.w<v.h?1.4:1), phi:1.05}, 700);
    return true;
  };
  FHHome.reset3D=function(id){ const v=viewers[id||"main"]; if(v&&v.home) v._flyTo(v.home); };
})();
