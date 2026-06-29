/* Seasonal ambient effects for the wall display.
   Auto-detects the date and renders a subtle canvas animation:
     - Dec (+ snow toggle): falling snow, and a Santa hat on the header
     - Jul 4 / Dec 31-Jan 1: fireworks bursts
     - Oct (Halloween week): drifting bats / falling leaves
     - Spring: occasional falling petals
   Respects prefers-reduced-motion and a settings toggle (effects on/off).
   Lightweight: capped particle counts, pauses when the tab/display sleeps. */
const Seasonal = (() => {
  let canvas, ctx, raf, particles = [], mode = "none", running = false;
  let fireworkTimer = null;
  let intense = false;   // preview / "make it obvious" mode: more + bigger particles
  const N = (base) => Math.round(base * (intense ? 2.4 : 1));
  const BIG = (r) => intense ? r * 1.8 : r;

  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function detect() {
    const n = new Date();
    const m = n.getMonth() + 1, d = n.getDate();
    if ((m === 7 && d === 4) || (m === 12 && d === 31) || (m === 1 && d === 1)) return "fireworks";
    if (m === 12) return "snow";
    if (m === 10 && d >= 24) return "halloween";
    if (m === 3 || m === 4) return "petals";
    if (m === 1 || m === 2) return "snow";
    return "none";
  }

  function setup() {
    canvas = document.getElementById("seasonal");
    if (!canvas) {
      canvas = document.createElement("canvas");
      canvas.id = "seasonal";
      canvas.style.cssText = "position:fixed;inset:0;pointer-events:none;z-index:40;";
      document.body.appendChild(canvas);
    }
    ctx = canvas.getContext("2d");
    resize();
    window.addEventListener("resize", resize);
  }
  function resize() {
    if (!canvas) return;
    canvas.width = window.innerWidth; canvas.height = window.innerHeight;
  }

  // ---- particle factories ----
  function snowflake() {
    return { x: Math.random()*canvas.width, y: -10, r: BIG(2+Math.random()*4),
      sx: -0.5+Math.random(), sy: 0.8+Math.random()*2, o: 0.6+Math.random()*0.4 };
  }
  function petal() {
    const p = snowflake(); p.color = ["#f7c9d9","#ffd9b3","#e7c6ff"][Math.floor(Math.random()*3)];
    p.sy *= 0.7; return p;
  }
  function leaf() {
    const p = snowflake(); p.color = ["#d2691e","#cd853f","#b8860b","#a0522d"][Math.floor(Math.random()*4)];
    p.r = BIG(4+Math.random()*5); p.sy *= 0.8; return p;
  }
  function bat() {
    return { x: Math.random()*canvas.width, y: Math.random()*canvas.height*0.6,
      sx: 1+Math.random()*1.5, sy: -0.3+Math.random()*0.6, flap: Math.random()*6, r: BIG(10+Math.random()*8) };
  }
  function burst() {
    const cx = canvas.width*(0.2+Math.random()*0.6), cy = canvas.height*(0.15+Math.random()*0.35);
    const hue = Math.floor(Math.random()*360), n = N(50)+Math.floor(Math.random()*30);
    const out = [];
    for (let i=0;i<n;i++){ const a=(Math.PI*2*i)/n, sp=(intense?2:1)+Math.random()*(intense?6:4);
      out.push({ x:cx, y:cy, vx:Math.cos(a)*sp, vy:Math.sin(a)*sp, life:1, hue }); }
    return out;
  }

  function seed() {
    particles = [];
    clearInterval(fireworkTimer);   // always reset so switching modes is clean
    if (mode === "snow") for (let i=0;i<N(110);i++) particles.push(snowflake());
    else if (mode === "petals") for (let i=0;i<N(60);i++) particles.push(petal());
    else if (mode === "halloween") {
      for (let i=0;i<N(45);i++) particles.push(leaf());
      for (let i=0;i<N(6);i++) particles.push(bat());
    }
    else if (mode === "fireworks") {
      particles.push(...burst());   // one immediately so it's instant
      fireworkTimer = setInterval(()=>{ if (running) particles.push(...burst()); }, intense ? 450 : 900);
    }
  }

  function step() {
    if (!running) return;
    ctx.clearRect(0,0,canvas.width,canvas.height);

    if (mode === "fireworks") {
      particles = particles.filter(p => p.life > 0);
      particles.forEach(p => {
        p.x += p.vx; p.y += p.vy; p.vy += 0.04; p.life -= 0.010;
        ctx.globalAlpha = Math.max(p.life,0);
        ctx.fillStyle = `hsl(${p.hue},95%,62%)`;
        ctx.beginPath(); ctx.arc(p.x,p.y, intense?3.5:2.2, 0,7); ctx.fill();
      });
      ctx.globalAlpha = 1;
    } else if (mode === "halloween") {
      particles.forEach(p => {
        if (p.flap !== undefined) { // bat
          p.x += p.sx; p.y += p.sy + Math.sin(p.x/40)*0.4; p.flap += 0.3;
          if (p.x > canvas.width+20) { p.x = -20; p.y = Math.random()*canvas.height*0.5; }
          drawBat(p);
        } else { fall(p, true); }
      });
    } else {
      particles.forEach(p => fall(p, mode!=="snow"));
    }
    raf = requestAnimationFrame(step);
  }

  function fall(p, colored) {
    p.x += p.sx; p.y += p.sy;
    if (p.y > canvas.height+10) { p.y = -10; p.x = Math.random()*canvas.width; }
    ctx.globalAlpha = p.o ?? 0.7;
    ctx.fillStyle = colored && p.color ? p.color : "rgba(255,255,255,.9)";
    if (document.documentElement.getAttribute("data-theme")==="light" && !p.color)
      ctx.fillStyle = "rgba(150,170,200,.7)"; // snow visible on white
    ctx.beginPath(); ctx.arc(p.x,p.y,p.r,0,7); ctx.fill();
    ctx.globalAlpha = 1;
  }
  function drawBat(p){
    ctx.fillStyle = "rgba(30,20,40,.8)";
    const w = p.r, f = Math.sin(p.flap)*w*0.5;
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
    ctx.quadraticCurveTo(p.x-w, p.y-f, p.x-w*1.6, p.y);
    ctx.quadraticCurveTo(p.x-w, p.y+w*0.3, p.x, p.y+w*0.4);
    ctx.quadraticCurveTo(p.x+w, p.y+w*0.3, p.x+w*1.6, p.y);
    ctx.quadraticCurveTo(p.x+w, p.y-f, p.x, p.y);
    ctx.fill();
  }

  // ---- Santa hat on the header date (December) ----
  function santaHat(on) {
    let hat = document.getElementById("santa-hat");
    if (!on) { if (hat) hat.remove(); return; }
    if (hat) return;
    const date = document.getElementById("date");
    if (!date) return;
    hat = document.createElement("span");
    hat.id = "santa-hat";
    hat.textContent = "🎅";
    hat.style.cssText = "font-size:26px;margin-left:8px;vertical-align:middle;";
    date.appendChild(hat);
  }

  let lastEnabled = true, lastPrefs = {}, previewTimer = null;

  function start(enabled, prefs) {
    lastEnabled = enabled; lastPrefs = prefs || {};
    intense = false;
    clearTimeout(previewTimer);
    setup();
    mode = detect();
    if (lastPrefs[mode] === false) mode = "none";   // this effect turned off
    santaHat(enabled && new Date().getMonth()===11 && lastPrefs.snow !== false);
    if (!enabled || reduced || mode === "none") { stop(); ctx && ctx.clearRect(0,0,canvas.width,canvas.height); return; }
    running = true; seed();
    cancelAnimationFrame(raf); step();
  }
  // Force a specific effect on screen for a few seconds, regardless of date —
  // used by the settings "Preview" buttons so you can see each one in action.
  function preview(which, seconds) {
    clearTimeout(previewTimer);
    setup();
    intense = true;            // over-exaggerate so it's unmistakable
    mode = which;
    santaHat(which === "snow");
    running = true; seed();
    cancelAnimationFrame(raf); step();
    previewTimer = setTimeout(() => start(lastEnabled, lastPrefs), (seconds || 12) * 1000);
  }
  function stop() {
    running = false; cancelAnimationFrame(raf); clearInterval(fireworkTimer);
    if (ctx) ctx.clearRect(0,0,canvas.width,canvas.height);
  }

  return { start, stop, detect, preview };
})();
