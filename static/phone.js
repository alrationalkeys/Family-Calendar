const $ = s => document.querySelector(s);
const PALETTE = ["#4f86c6","#d96b8a","#7c5cff","#5cb88a","#e9a23b","#e0533d","#3db5c9","#9aa0a6"];
let chosenColor = null, categories = [], people = [], calTargets = [{id:"local",label:"FamilyHub only (this screen)"}];
async function loadCalTargets(){ try{ const r=await fetch("/api/sources/targets").then(r=>r.json()); if(r.targets&&r.targets.length){ calTargets=r.targets; if(formKind==="event") renderForm(); } }catch(e){} }
function calOptions(){
  const want=FH.get().defaultCalendar||"";
  const def = calTargets.some(t=>t.id===want) ? want : (calTargets.find(t=>t.id!=="local")||calTargets[0]).id;
  return calTargets.map(t=>`<option value="${t.id}"${t.id===def?" selected":""}>${t.label}</option>`).join("");
}

/* build color swatches */
function buildColors(el){
  if(!el) return;
  el.innerHTML="";
  PALETTE.forEach(c=>{
    const s=document.createElement("div"); s.className="swatch"; s.style.background=c;
    s.onclick=()=>{ el.querySelectorAll(".swatch").forEach(x=>x.classList.remove("sel"));
      s.classList.add("sel"); chosenColor=c; };
    el.appendChild(s);
  });
}
buildColors($("#magicColors"));

/* toast */
function toast(msg){
  const t=$("#toast"); t.textContent=msg; t.classList.add("show");
  setTimeout(()=>t.classList.remove("show"), 2200);
}

/* ---- magic quick-add ---- */
let previewTimer;
$("#magic").addEventListener("input", ()=>{
  clearTimeout(previewTimer);
  const text=$("#magic").value.trim();
  if(text.length<4){ $("#preview").classList.remove("show"); return; }
  previewTimer=setTimeout(()=>preview(text), 700);
});

async function preview(text){
  try{
    const r=await fetch("/api/ai/route",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({text})}).then(r=>r.json());
    const p=$("#preview");
    const items=(r.items||[]).map(it=>{
      const label=it.title||it.item||"";
      const extra=it.start?` · ${new Date(it.start).toLocaleString([],{weekday:"short",hour:"numeric",minute:"2-digit"})}`
        : it.slot?` · ${it.slot} ${it.date||""}` : it.qty?` · ${it.qty}`:"";
      return `<div class="pi">${label}${extra}</div>`;
    }).join("");
    p.innerHTML=`<div class="pk">${r.kind}</div>${items}`;
    p.classList.add("show");
  }catch(e){ $("#preview").classList.remove("show"); }
}

$("#magicGo").onclick=async()=>{
  const text=$("#magic").value.trim(); if(!text)return;
  $("#magicGo").disabled=true;
  try{
    const resp=await post("/api/ai/quick-add",{text,color:chosenColor}); const r=await resp.json().catch(()=>({}));
    const made=(r.created||[]).length;
    if(!resp.ok || !made){ toast(r.detail||r.error||"I couldn't tell what to add. Try the form above."); $("#magicGo").disabled=false; return; }
    // events come back as kind=event but aren't saved by quick-add; save them to the calendar
    if(r.kind==="event"){
      for(const ev of r.created){
        await post("/api/calendar/events",{title:ev.title,start:ev.start,end:ev.end||ev.start,color:chosenColor||null,destination:(FH.get().defaultCalendar||"local")}).catch(()=>{});
      }
    }
    const where={event:"the calendar", todo:"the to-do list", grocery:"the groceries", meal:"the meal plan"}[r.kind]||"the list";
    toast(`Added ${made} to ${where}`);
    $("#magic").value=""; $("#preview").classList.remove("show");
  }catch(e){ toast("Couldn't add — try the form below"); }
  $("#magicGo").disabled=false;
};

/* ---- manual forms ---- */
let formKind="event";
const today=(d=>{const p=n=>String(n).padStart(2,"0");return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}`;})(new Date());

function catOptions(){
  // no categories defined yet -> the select is hidden (body.nocats) so forms stay clean;
  // people colours already do the colour-coding. Define categories in Settings if wanted.
  document.body.classList.toggle("nocats", !categories.length);
  return `<option value="">No category</option>`+
    categories.map(c=>`<option value="${c.id}">${c.name}</option>`).join("");
}

function peopleOptions(){
  return `<option value="">Unassigned</option>`+
    people.map(p=>`<option value="${p.id}">${p.name}</option>`).join("");
}
// Who's on it: tap one or more people (none = everyone / unassigned). Read back with whoIds(id).
function whoChips(id){
  if(!people.length) return "";
  return `<div class="who" id="${id}" role="group" aria-label="Who">`+
    people.map(p=>`<button type="button" data-id="${p.id}" style="--pc:${p.color||'#888'}" onclick="this.classList.toggle('on')">${FHHome.esc(p.name)}</button>`).join("")+`</div>`;
}
function whoIds(id){ return [...document.querySelectorAll(`#${id} button.on`)].map(b=>+b.dataset.id); }
function whoBody(id){ const ids=whoIds(id); return {person_id: ids[0]||null, person_ids: ids}; }
function recurOptions(){
  return ["","daily","weekly","monthly"].map(r=>
    `<option value="${r}">${r?r[0].toUpperCase()+r.slice(1):"No repeat"}</option>`).join("");
}
function starsOptions(){
  return `<option value="0">No stars</option>`+
    [1,2,3,4,5].map(s=>`<option value="${s}">${"⭐".repeat(s)}</option>`).join("");
}

function renderForm(){
  const f=$("#form");
  const colorRow=`<div class="colors" id="fColors"></div>`;
  if(formKind==="event"){
    f.innerHTML=`<input id="e_title" placeholder="Event title">
      <input id="e_loc" placeholder="Where (optional) — the wall says when to leave">
      <label class="chk"><input type="checkbox" id="e_allday" onchange="toggleAllDay()"> All day</label>
      <div class="two"><input id="e_date" type="date" value="${today}"><input id="e_time" type="time" value="09:00"><input id="e_end_date" type="date" title="Last day" style="display:none"></div>
      <div class="two"><select id="e_repeat" title="Repeats" onchange="toggleRepeat()">
          <option value="">Doesn't repeat</option><option value="daily">Every day</option><option value="weekly">Every week</option>
          <option value="weekly;interval=2">Every other week</option><option value="monthly">Every month</option></select>
        <select id="e_ends" title="Ends" style="display:none" onchange="toggleRepeat()"><option value="never">Never ends</option><option value="count">After…</option><option value="until">Until…</option></select>
        <input id="e_count" type="number" min="1" value="4" placeholder="times" style="display:none; flex:0 0 84px"><input id="e_until" type="date" style="display:none"></div>
      <div class="two dur"><span class="durlbl">Lasts</span>
        <select id="e_dur_h" title="Hours">${Array.from({length:24},(_,h)=>`<option value="${h}"${h===1?' selected':''}>${h} h</option>`).join('')}</select>
        <select id="e_dur_m" title="Minutes">${Array.from({length:12},(_,i)=>`<option value="${i*5}">${String(i*5).padStart(2,'0')} min</option>`).join('')}</select>
      </div>
      ${whoChips("e_person")}
      <select id="e_cal" title="Which calendar">${calOptions()}</select>
      <select id="e_cat">${catOptions()}</select>${colorRow}
      <button class="go" onclick="saveEvent()">Add event</button>`;
  } else if(formKind==="chore"){
    f.innerHTML=`<input id="c_title" placeholder="Chore (e.g. Take out trash)">
      ${whoChips("c_person")}<select id="c_stars">${starsOptions()}</select>
      <div class="two"><input id="c_due" type="date" value="${today}"><select id="c_recur">${recurOptions()}</select></div>
      <select id="c_cat">${catOptions()}</select>${colorRow}
      <button class="go" onclick="saveChore()">Add chore</button>`;
  } else if(formKind==="todo"){
    const tls=["To-Do", ...(FH.get().todoLists||[])], pre=new URLSearchParams(location.search).get("list")||"To-Do";
    if(!tls.includes(pre)) tls.push(pre);
    f.innerHTML=`<input id="t_title" placeholder="What needs doing?">
      <select id="t_list">${tls.map(n=>`<option ${n===pre?"selected":""}>${FHHome.esc(n)}</option>`).join("")}</select>
      ${whoChips("t_person")}<input id="t_due" type="date" title="Due">
      <div class="two"><select id="t_recur">${recurOptions()}</select><select id="t_cat">${catOptions()}</select></div>${colorRow}
      <button class="go" onclick="saveTodo()">Add to-do</button>`;
  } else if(formKind==="grocery"){
    f.innerHTML=`<div class="two"><input id="g_item" placeholder="Item" style="flex:2"><input id="g_qty" placeholder="Qty" style="flex:1"></div>
      <select id="g_cat">${catOptions()}</select>${colorRow}
      <button class="go" onclick="saveGrocery()">Add grocery</button>`;
  } else if(formKind==="routine"){
    const days=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map(d=>`<label class="chk dchk"><input type="checkbox" data-d="${d}" checked> ${d}</label>`).join("");
    f.innerHTML=`<div class="two"><input id="r_emoji" placeholder="🌅" style="flex:0 0 64px; text-align:center"><input id="r_name" placeholder="Routine name (Morning, Bedtime…)" style="flex:1"></div>
      <div class="two"><select id="r_person">${peopleOptions()}</select>
        <select id="r_tod"><option value="morning">Morning</option><option value="afternoon">After school</option><option value="bedtime">Bedtime</option><option value="any">Any time</option></select></div>
      <div class="days">${days}</div>
      <textarea id="r_steps" rows="6" placeholder="One step per line. Add minutes for a timer:&#10;Brush teeth 2&#10;Get dressed&#10;Pack backpack 5&#10;Eat breakfast 15"></textarea>
      <select id="r_stars">${starsOptions()}</select>
      <div class="hint">Stars are earned when every step is checked off on the wall. Resets daily.</div>
      <button class="go" onclick="saveRoutine()">Add routine</button>`;
  } else if(formKind==="countdown"){
    f.innerHTML=`<div class="two"><input id="cd_emoji" placeholder="🎄" style="flex:0 0 64px; text-align:center"><input id="cd_title" placeholder="Countdown to… (Disney trip, Christmas)" style="flex:1"></div>
      <input id="cd_date" type="date">
      <select id="cd_person">${peopleOptions()}</select>${colorRow}
      <div class="hint">Shows as a chip above the wall calendar: "🎄 Christmas · 51 days".</div>
      <button class="go" onclick="saveCountdown()">Add countdown</button>`;
  } else {
    f.innerHTML=`<input id="m_title" placeholder="Meal">
      <div class="two"><input id="m_date" type="date" value="${today}">
      <select id="m_slot"><option>breakfast</option><option>lunch</option><option selected>dinner</option><option>snack</option></select></div>
      <select id="m_cat">${catOptions()}</select>${colorRow}
      <button class="go" onclick="saveMeal()">Add meal</button>`;
  }
  buildColors($("#fColors"));
}

document.querySelectorAll(".seg button").forEach(b=>{
  b.onclick=()=>{
    document.querySelectorAll(".seg button").forEach(x=>x.classList.remove("active"));
    b.classList.add("active"); formKind=b.dataset.f; chosenColor=null; renderForm();
  };
});

function plusHourLocal(start){ // 1h later, kept in LOCAL time (no UTC shift)
  const d=new Date(new Date(start).getTime()+3600000), p=n=>String(n).padStart(2,"0");
  return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:00`;
}
function nextDay(dateStr){ // YYYY-MM-DD -> next day (all-day end is exclusive in calendars)
  const d=new Date(dateStr+"T00:00:00"); d.setDate(d.getDate()+1); const p=n=>String(n).padStart(2,"0");
  return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}`;
}
function toggleAllDay(){ const ad=$("#e_allday").checked; $("#e_time").style.display=ad?"none":""; $("#e_end_date").style.display=ad?"":"none"; }
function toggleRepeat(){ const rep=!!$("#e_repeat").value, m=$("#e_ends").value; $("#e_ends").style.display=rep?"":"none"; $("#e_count").style.display=(rep&&m==="count")?"":"none"; $("#e_until").style.display=(rep&&m==="until")?"":"none"; }
function eventRecurrence(){ let s=$("#e_repeat")?$("#e_repeat").value:""; if(!s) return null; const m=$("#e_ends").value;
  if(m==="count") s+=";count="+Math.max(1,parseInt($("#e_count").value,10)||1); else if(m==="until"&&$("#e_until").value) s+=";until="+$("#e_until").value; return s; }
async function saveEvent(){
  const title=$("#e_title").value.trim(); if(!title)return;
  const date=$("#e_date").value; if(!date){ toast("Pick a date"); return; }
  const allday=$("#e_allday").checked;
  let payload;
  const destination=$("#e_cal")?$("#e_cal").value:"local";
  const {person_id, person_ids}=whoBody("e_person");
  const recurrence=eventRecurrence();
  const loc=($("#e_loc")&&$("#e_loc").value.trim())||null;
  if(allday){
    const last=$("#e_end_date").value;                                // multi-day trip: last day inclusive
    payload={title, start:date, end:nextDay(last&&last>date?last:date), all_day:true, destination, person_id, person_ids, color:chosenColor, recurrence, location:loc};
  } else {
    const time=$("#e_time").value; if(!time){ toast("Pick a time"); return; }
    const start=`${date}T${time}:00`;
    const mins=($("#e_dur_h")?(parseInt($("#e_dur_h").value,10)*60+parseInt($("#e_dur_m").value,10)):60)||5;   // 0 h 0 min -> 5 min
    const d=new Date(start); d.setMinutes(d.getMinutes()+mins);
    const p=n=>String(n).padStart(2,"0");
    const end=`${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:00`;
    payload={title, start, end, destination, person_id, person_ids, color:chosenColor, recurrence, location:loc};
  }
  FH.save({defaultCalendar:destination});
  try{
    const r=await post("/api/calendar/events", payload);
    const data=await r.json().catch(()=>({}));
    if(!r.ok){ toast(data.detail||data.error||"Couldn't add event"); return; }
    toast(data.warning || (data.target==="local" ? "Event added" : data.target==="icloud" ? `Event added to iCloud${data.calendar?" › "+data.calendar:""}` : "Event added to Google"));
    $("#e_title").value=""; if($("#e_loc")) $("#e_loc").value="";
  }catch(e){ toast("Couldn't reach the server"); }
}
async function saveChore(){
  const title=$("#c_title").value.trim(); if(!title)return;
  const r=await post("/api/chores/",{title, ...whoBody("c_person"),
    category_id:num($("#c_cat").value), color:chosenColor, due_date:$("#c_due").value||null,
    recurrence:$("#c_recur").value||null, stars:parseInt($("#c_stars").value)||0});
  if(!r.ok){ toast("Couldn't add chore"); return; }
  toast("Chore added"); $("#c_title").value="";
}
async function saveTodo(){
  const title=$("#t_title").value.trim(); if(!title)return;
  const r=await post("/api/todos/",{title, ...whoBody("t_person"), category_id:num($("#t_cat").value), color:chosenColor,
    due_date:$("#t_due").value||null, recurrence:$("#t_recur").value||null, list_name:($("#t_list")||{}).value||null});
  if(!r.ok){ toast("Couldn't add to-do"); return; }
  toast("To-do added"); $("#t_title").value="";
}
async function saveGrocery(){
  const item=$("#g_item").value.trim(); if(!item)return;
  await post("/api/groceries/",{item,qty:$("#g_qty").value||null,category_id:num($("#g_cat").value),color:chosenColor});
  toast("Grocery added"); $("#g_item").value=""; $("#g_qty").value="";
}
async function saveMeal(){
  const title=$("#m_title").value.trim(); if(!title)return;
  await post("/api/meals/",{date:$("#m_date").value,slot:$("#m_slot").value,title,
    category_id:num($("#m_cat").value),color:chosenColor});
  toast("Meal added"); $("#m_title").value="";
}
async function saveRoutine(){
  const name=$("#r_name").value.trim(); if(!name){ toast("Give it a name"); return; }
  const steps=$("#r_steps").value.split("\n").map(l=>l.trim()).filter(Boolean).map(l=>{
    const m=l.match(/^(.*?)(?:\s+(\d+)\s*(?:m|min|mins|minutes)?)?$/i);
    return {title:(m&&m[1]||l).trim(), minutes:m&&m[2]?parseInt(m[2]):null};
  });
  if(!steps.length){ toast("Add at least one step"); return; }
  const days=[...document.querySelectorAll("#form input[data-d]")].filter(c=>c.checked).map(c=>c.dataset.d);
  const r=await post("/api/routines/",{name, emoji:$("#r_emoji").value.trim()||null, person_id:num($("#r_person").value),
    time_of_day:$("#r_tod").value, days:days.length===7?"":days.join(","), steps, stars:parseInt($("#r_stars").value)||0});
  if(!r.ok){ toast("Couldn't add routine"); return; }
  toast("Routine added — it's on the wall's Chores page"); $("#r_name").value=""; $("#r_steps").value="";
}
async function saveCountdown(){
  const title=$("#cd_title").value.trim(); if(!title){ toast("What are we counting down to?"); return; }
  const date=$("#cd_date").value; if(!date){ toast("Pick the date"); return; }
  const r=await post("/api/routines/countdowns",{title, date, emoji:$("#cd_emoji").value.trim()||null, color:chosenColor, person_id:num($("#cd_person").value)});
  if(!r.ok){ toast("Couldn't add countdown"); return; }
  toast("Countdown added"); $("#cd_title").value="";
}
function num(v){ return v?parseInt(v):null; }
// X-FH-Who: this phone's owner (Settings → "Your name on this phone") so the wall can say
// "Rachell added …" and HA can skip pushing the add back to the person who made it.
function whoAmI(){ try{ return localStorage.getItem("fh_who")||""; }catch(e){ return ""; } }
/* hands-free wake word on the wall (services/wake.py) */
async function loadWake(s){
  const sel=$("#set-wake"), sens=$("#set-wakesens"), st=$("#wake-state"); if(!sel) return;
  let w={}; try{ w=await fetch("/api/ai/wake").then(r=>r.json()); }catch(e){}
  const esc=FHHome.esc; const opts=(w.choices||[{id:"hey_jarvis",name:"Hey Jarvis"}]).map(c=>`<option value="${esc(c.id)}">${esc(c.name)}</option>`).join("");
  sel.innerHTML=opts+'<option value="off">Off (tap the mic)</option>';
  sel.value=String(s.wakeWord||"hey_jarvis"); if(!sel.value) sel.value="hey_jarvis";
  sens.value=String(s.wakeSensitivity||"normal");
  sel.onchange=()=>{ FH.save({wakeWord:sel.value}); toast(sel.value==="off"?"Hands-free is off":"The wall will answer to “"+sel.selectedOptions[0].text+"”"); setTimeout(()=>loadWake(FH.get()),7000); };
  sens.onchange=()=>FH.save({wakeSensitivity:sens.value});
  st.textContent = !w.installed ? "Not installed on the wall yet: on the wall PC run  bash setup/install-wakeword.sh"
    : w.running ? `Listening for “${w.name}” (mic: ${w.mic}). Woke ${w.wakes||0} times since the last restart${w.last_text?`; last heard “${w.last_text}”`:""}.`
    : (w.word ? `Not listening: ${w.error||"starting…"}` : "Off. Tap the mic on the wall to talk.");
  const go=$("#wake-go"); if(go && !go._wired){ go._wired=true;
    go.onclick=async()=>{ const t=$("#wake-try").value.trim()||"set a 5 minute timer for eggs";
      try{ await post("/api/ai/wake/test",{text:t}); toast("Sent: watch the wall"); }catch(e){ toast("Couldn't reach the wall"); } }; }
}
function post(url,body){ const h={"Content-Type":"application/json"}; const w=whoAmI(); if(w) h["X-FH-Who"]=w; return fetch(url,{method:"POST",headers:h,body:JSON.stringify(body)}); }

/* boot */
/* ---- voice input (Web Speech API) ---- */
const micBtn = document.getElementById("micBtn");
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SR) {
  const rec = new SR();
  rec.lang = "en-US"; rec.interimResults = true; rec.continuous = false;
  let listening = false;
  micBtn.onclick = () => {
    if (listening) { rec.stop(); return; }
    rec.start();
  };
  rec.onstart = () => { listening = true; micBtn.classList.add("rec"); micBtn.textContent = "● Listening"; };
  rec.onend = () => { listening = false; micBtn.classList.remove("rec"); micBtn.textContent = "🎤 Speak";
    const t = $("#magic").value.trim(); if (t.length >= 4) preview(t); };
  rec.onresult = (e) => {
    let txt = "";
    for (let i = 0; i < e.results.length; i++) txt += e.results[i][0].transcript;
    $("#magic").value = txt;
  };
} else {
  micBtn.style.display = "none";  // browser doesn't support it
}

/* ---- vision: photo of a flyer -> events ---- */
const camBtn = document.getElementById("camBtn");
const camInput = document.getElementById("camInput");
camBtn.onclick = () => camInput.click();
camInput.onchange = async () => {
  const file = camInput.files[0]; if (!file) return;
  camBtn.textContent = "📷 Reading…"; camBtn.disabled = true;
  try {
    const b64 = await new Promise((res, rej) => {
      const r = new FileReader();
      r.onload = () => res(r.result.split(",")[1]);
      r.onerror = rej; r.readAsDataURL(file);
    });
    const r = await fetch("/api/ai/vision", {method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({image_b64: b64, media_type: file.type || "image/jpeg"})}).then(r=>r.json());
    if (r.error) { toast(r.error); }
    else {
      const events = r.events || [];
      if (!events.length) { toast("No events found in photo"); }
      else {
        for (const ev of events) {
          await post("/api/calendar/events",{title: ev.title, start: ev.start, end: ev.end || ev.start}).catch(()=>{});
        }
        toast(`Added ${events.length} event${events.length>1?"s":""} from photo`);
      }
    }
  } catch (e) { toast("Couldn't read photo"); }
  camBtn.textContent = "📷 Photo"; camBtn.disabled = false; camInput.value = "";
};

/* ===================== CALENDAR (agenda) VIEW ===================== */
let agDays=7;
$("#cal-range").querySelectorAll("button").forEach(b=>b.onclick=()=>{ agDays=+b.dataset.v; $("#cal-range").querySelectorAll("button").forEach(x=>x.classList.toggle("active",x===b)); loadAgenda(); });
async function loadAgenda(){
  const box=$("#cal-list");
  try{
    const [cal,dash]=await Promise.all([ fetch(`/api/calendar/events?days=${agDays+1}`).then(r=>r.json()), fetch("/api/dashboard").then(r=>r.json()) ]);
    const E=FHHome.esc, today=new Date(); today.setHours(0,0,0,0); const todayKey=today.toISOString().slice(0,10);
    const end=new Date(today); end.setDate(end.getDate()+agDays);
    const items=[];
    (cal.events||[]).forEach(e=>{ const s=new Date(e.start); if(isNaN(s)) return; const d=e.all_day&&e.start.length===10?new Date(e.start+"T00:00"):s; if(d<today||d>=end) return; items.push({d, e}); });
    const showTasks=FH.get().calendarTasks!==false;
    if(showTasks){
      (dash.todos||[]).forEach(t=>{ const due=(t.just_done&&t.was_due)||t.due_date; if(!due) return; const d=new Date(due+"T00:00"); if(d>=end) return; items.push({d:d<today?today:d, e:{title:t.title, all_day:true, color:t.color, task:{kind:"todo",id:t.id}, late:d<today&&!t.just_done, done:!!(t.done||t.just_done)}}); });
      (dash.chores||[]).forEach(c=>{ const due=(c.just_done&&c.was_due)||c.due_date; const d=due?new Date(due+"T00:00"):today; if(d>=end) return; items.push({d:d<today?today:d, e:{title:(c.stars?"\u2B50 ":"")+c.title, all_day:true, color:c.color, task:{kind:"chore",id:c.id}, late:d<today, done:!!(c.done||c.just_done)}}); });
    }
    items.sort((a,b)=>(a.d-b.d) || ((a.e.task?0:1)-(b.e.task?0:1)) || ((a.e.all_day?0:1)-(b.e.all_day?0:1)));
    if(!items.length){ box.innerHTML=`<div class="hint">Nothing in the next ${agDays} days.</div>`; return; }
    let html="", last="";
    items.forEach(({d,e})=>{
      const key=d.toDateString();
      if(key!==last){ last=key; const isT=d.toISOString().slice(0,10)===todayKey || d.getTime()===today.getTime(); html+=`<div class="ag-day${isT?' today':''}">${isT?"Today":d.toLocaleDateString([],{weekday:"long",month:"short",day:"numeric"})}</div>`; }
      const time = e.task ? (e.done?"\u2611":"\u2610") : e.all_day ? "all day" : d.toLocaleTimeString([],{hour:"numeric",minute:"2-digit"});
      html+=`<div class="ag-ev${e.task?' task':''}${e.done?' done':''}" ${e.task?`data-kind="${e.task.kind}" data-id="${e.task.id}"`:""}><span class="ag-time">${time}</span><span class="ag-dot" style="background:${E(e.color||'#4f86c6')}"></span><span class="ag-title">${E(e.title)}</span>${e.task?`<span class="ag-kind">${e.task.kind==="chore"?"chore":"to-do"}${e.late?" \u00b7 overdue":""}</span>`:""}</div>`;
    });
    box.innerHTML=html;
    box.querySelectorAll(".ag-ev.task").forEach(row=>row.onclick=async()=>{
      row.classList.toggle("done"); row.querySelector(".ag-time").textContent=row.classList.contains("done")?"\u2611":"\u2610"; if(navigator.vibrate) navigator.vibrate(10);
      try{ const res=await post(`/api/${row.dataset.kind==="todo"?"todos":"chores"}/${row.dataset.id}/toggle`,{}); if(!res.ok) throw new Error(res.status);
        const r=await res.json(), um=FH.get().undoMinutes??30;
        toast(r.undone?"\u21A9\uFE0F Back on the list":"Checked off"+(um?` \u00b7 tap again within ${um} min to undo`:"")); }
      catch(e){ row.classList.toggle("done"); toast("Couldn't reach the wall"); }
      setTimeout(loadAgenda, 600);
    });
  }catch(e){ box.innerHTML='<div class="hint">Couldn\u2019t load the calendar.</div>'; }
}

/* ===================== SETTINGS VIEW ===================== */
/* top-nav view switch */
$("#nav-add").onclick=()=>switchView("add");
$("#nav-home").onclick=()=>switchView("home");
$("#nav-tv").onclick=()=>switchView("tv");
$("#nav-cal").onclick=()=>switchView("cal");
$("#nav-settings").onclick=()=>switchView("settings");
let curView="add", hmTimer=null;
function switchView(v){
  curView=v;
  ["add","home","cal","tv","settings"].forEach(k=>{ $("#view-"+k).hidden=(k!==v); $("#nav-"+k).classList.toggle("active",k===v); });
  if(v==="cal"){ loadAgenda(); }
  document.body.classList.toggle("home-dark", v==="home");
  if(v==="settings"){ loadSettingsUI(); FH.load().then(()=>loadSettingsUI()).catch(()=>{}); loadDispCfg(); loadPeople(); loadRC(); loadSPL(); loadSPW(); loadSources(); loadPhotosUI(); loadMail(); loadDbInfo(); loadWallVersion(false); loadPinState(); if(window.FHAutomations) FHAutomations.load($("#au-box"), toast); }
  if(v==="tv"){ loadTVs(); }
  clearInterval(hmTimer);
  if(v==="home"){ loadHM(); hmTimer=setInterval(()=>{ if(!document.hidden) loadHM(); }, 30000); hmLive(true); } else hmLive(false);
  if(!document.body.classList.contains("embed")) try{ localStorage.setItem("fh_view", v); }catch(e){}
}

/* ===================== Home tab: the house in your pocket ===================== */
/* live: the server's SSE stream bumps a version on every HA state change -> reload right away
   (the 30 s timer stays as a backup). Closed while the Home tab isn't showing or the app is in the background. */
let hmES=null, hmESv=null, hmESt=0;
function hmLive(on){
  if(!on||document.hidden||!("EventSource" in window)){ if(hmES){ try{hmES.close();}catch(e){} hmES=null; } return; }
  if(hmES) return;
  try{ hmES=new EventSource("/api/ha/events"); }catch(e){ return; }
  hmES.onmessage=m=>{ let d={}; try{ d=JSON.parse(m.data); }catch(e){ return; }
    if(hmESv!==null&&d.version!==hmESv&&curView==="home"){ clearTimeout(hmESt); hmESt=setTimeout(loadHM, 250); }
    hmESv=d.version; };
  hmES.onerror=()=>{ try{hmES.close();}catch(e){} hmES=null; setTimeout(()=>{ if(curView==="home") hmLive(true); }, 5000); };
}
document.addEventListener("visibilitychange",()=>{ hmLive(curView==="home"); if(!document.hidden&&curView==="home") loadHM(); });
let hmView="rooms", hmLast=null, hmSig="", hmHealth=null, hmAlerts=[], hmLaundry=[];
FHHome.toggle = async (eid)=>{
  if(navigator.vibrate) navigator.vibrate(8);
  const t=(FHHome.tilesOf(hmLast||{})).find(x=>x.entity_id===eid)||{}, name=t.name||"", d=t.domain||eid.split(".")[0], wasOn=!!t.on;
  const scene=d==="scene"||d==="script";
  const verb=scene?"Running":d==="lock"?(wasOn?"Unlocking":"Locking"):d==="cover"?(wasOn?"Closing":"Opening"):(wasOn?"Turning off":"Turning on");
  toast(`${verb} ${name}…`);
  try{ const r=await post("/api/ha/toggle",{entity_id:eid}); let j={}; try{ j=await r.json(); }catch(e){}
    if(r.ok===false||j.ok===false) throw new Error();
    toast(scene?`✓ ${name} done`:d==="lock"?(wasOn?`🔓 ${name} unlocked`:`🔒 ${name} locked`):d==="cover"?`✓ ${name} ${wasOn?"closing":"opening"}`:`✓ ${name} ${wasOn?"off":"on"}`);
  }catch(e){ toast(`Couldn't reach ${name||"it"}. Try again`); }
  setTimeout(loadHM, 350); };
FHHome.remote = (eid,name)=>{ switchView("tv"); setTimeout(()=>openTV(eid,name), 150); };
let _camT=null, _camEid=null, _camStream=null;
function openCam(eid,name){ camSound(null, false); _camEid=eid; const ov=$("#camov"); $("#cam-title").textContent="📷 "+(name||"Camera"); ov.classList.remove("live"); ov.classList.add("on");
  const tick=()=>{ if(_camEid!==eid||ov.classList.contains("live")) return; $("#cam-img").src=`/api/ha/camera/${encodeURIComponent(eid)}?v=1&t=${Date.now()}`; }; tick(); clearInterval(_camT); _camT=setInterval(tick,3000);
  $("#cam-foot").textContent="Connecting to the live feed…";
  if(_camStream) _camStream.stop();
  if(window.ADCStream){ _camStream=new ADCStream($("#cam-video"), eid, {onstatus:(st)=>{ if(_camEid!==eid) return;
      if(st==="live"){ ov.classList.add("live"); $("#cam-foot").innerHTML='<span class="live-dot"></span>Live · tap ✕ to close'; camSound(_camStream, true); }
      else if(st==="failed"){ ov.classList.remove("live"); $("#cam-foot").innerHTML='Live view isn\u2019t answering · new picture every 3 s<br><button id="cam-retry" style="margin-top:10px;border:0;border-radius:18px;padding:8px 16px;background:rgba(255,255,255,.18);color:#fff;font:inherit;font-weight:700">Try live again</button>'; const rb=$("#cam-retry"); if(rb) rb.onclick=()=>{ if(_camStream){ _camStream._retries=0; _camStream.start(); } }; }
      else { ov.classList.remove("live"); $("#cam-foot").textContent="Connecting to the live feed… (doorbells can take a few seconds to wake)"; } }}); _camStream.start(); } }
function closeCam(){ $("#camov").classList.remove("on","live"); clearInterval(_camT); _camEid=null; camSound(null, false); if(_camStream){ _camStream.stop(); _camStream=null; } }
/* camera sound: a speaker button shows once the live feed is playing and carries audio; tap = on/off (starts muted) */
function camSound(stream, show){ const b=$("#cam-snd"); if(!b) return; if(!show||!stream){ b.style.display="none"; return; }
  b.style.display=stream.hasAudio()?"":"none"; if(b.style.display&&!camSound._again){ camSound._again=1; setTimeout(()=>{ camSound._again=0; if(_camStream===stream) camSound(stream, true); }, 2500); }
  b.textContent=stream._sound?"\u{1F50A}":"\u{1F507}";
  b.onclick=(e)=>{ e.stopPropagation(); const on=stream.sound(!stream._sound); b.textContent=on?"\u{1F50A}":"\u{1F507}"; }; }

$("#cam-close").onclick=closeCam;
FHHome.camera = (eid,name)=>openCam(eid,name);
FHHome.rerender = ()=>{ if(hmLast) renderHM(hmLast, true); };
$("#hm-tabs").querySelectorAll("button").forEach(b=>{ b.onclick=()=>{ hmView=b.dataset.v; $("#hm-tabs").querySelectorAll("button").forEach(x=>x.classList.toggle("active",x===b)); if(hmLast) renderHM(hmLast, true); }; });

let hmWx=null, hmWxAt=0, hmPresence=null;
/* I'm home = the Surety Home scene: if the alarm is armed, ask for the panel code (sent to the alarm, never saved) */
function hmWelcome(btn, mode){
  mode=mode||"welcome";
  const tiles=FHHome.tilesOf(hmLast||{}), alarm=tiles.find(t=>t.domain==="alarm_control_panel");
  if(!(alarm && /^armed|pending|arming/.test(alarm.state||"")) || FH.get().welcomeNoCode===true) return hmMode(mode, btn);
  let ov=$("#wkov");
  if(!ov){ ov=document.createElement("div"); ov.id="wkov";
    ov.innerHTML=`<div class="wk-card"><h3 id="wk-h"></h3><div class="wk-sub" id="wk-s"></div>
      <div class="wk-dots" id="wk-dots"></div><div class="wk-keys">${[1,2,3,4,5,6,7,8,9,"⌫",0,"✓"].map(k=>`<button data-k="${k}">${k}</button>`).join("")}</div>
      <button class="wk-x">Cancel</button></div>`;
    document.body.appendChild(ov); }
  $("#wk-h").textContent=mode==="morning"?"☀️ Good morning":"🏡 Welcome home";
  $("#wk-s").textContent=mode==="morning"?"Alarm code to disarm":"Alarm code to disarm and open the garage";
  let buf=""; const dots=()=>{ $("#wk-dots").textContent="•".repeat(buf.length)||" "; }; dots();
  ov.classList.add("on");
  ov.querySelector(".wk-x").onclick=()=>{ buf=""; ov.classList.remove("on"); };
  ov.querySelectorAll(".wk-keys button").forEach(b=>b.onclick=()=>{ if(navigator.vibrate) navigator.vibrate(6);
    const k=b.dataset.k;
    if(k==="⌫") buf=buf.slice(0,-1);
    else if(k==="✓"){ const c=buf; buf=""; ov.classList.remove("on"); hmMode(mode, btn, c||null); return; }
    else if(buf.length<8) buf+=k;
    dots(); });
}
async function hmMode(mode, btn, code){
  if(navigator.vibrate) navigator.vibrate(10);
  if(btn){ btn.disabled=true; btn.querySelector(".ic").textContent="⏳"; }
  let r={}; try{ r=await post("/api/ha/mode",{mode, source:"phone", who:whoAmI(), code:code||null, open_garage:mode==="welcome"}).then(x=>x.json()); }catch(e){}
  toast(r.say||"Done"); setTimeout(loadHM, 900);
}
async function hmWeather(){
  if(Date.now()-hmWxAt<10*60*1000) return hmWx;
  hmWxAt=Date.now();
  try{ const w=await fetch("/api/weather").then(r=>r.json()); if(w&&!w.error) hmWx=w; }catch(e){}
  return hmWx;
}
let hmVillage=null;     // Christmas village status (tile hides while it doesn't answer)
async function loadHM(){
  let h=null;
  fetch("/api/village/status").then(r=>r.json()).then(v=>{ const was=JSON.stringify(hmVillage); hmVillage=v; if(hmLast&&JSON.stringify(v)!==was) renderHM(hmLast,true); }).catch(()=>{});
  try{ [h]=await Promise.all([fetch("/api/ha/home").then(r=>r.json()), hmWeather(), fetch("/api/ha/presence").then(r=>r.json()).then(r=>{ hmPresence=r.people||[]; }).catch(()=>{}), FHHome.health().then(d=>{ hmHealth=d; }), FHHome.wxAlerts().then(d=>{ hmAlerts=d; }), FHHome.laundry().then(d=>{ hmLaundry=d; })]); }catch(e){}
  if(!h){ $("#hm-hero").innerHTML=""; $("#hm-body").innerHTML='<div class="hm-offline">Can\'t reach the wall right now.</div>'; return; }
  renderHM(h,false);
}
const HM_ROOM_ICON=[[/bedroom|master/,"🛏"],[/living/,"🛋"],[/kitchen/,"🍳"],[/dining/,"🍽"],[/bath/,"🛁"],[/garage/,"🚗"],[/laundry/,"🧺"],[/porch|patio/,"🌿"],[/loft|sitting/,"🎮"],[/flex|office/,"💼"],[/closet|pantry|butler/,"👔"],[/foyer|hall|entry/,"🚪"]];
const hmRoomIcon=r=>{ const k=String(r.key||r.name).toLowerCase(); const hit=HM_ROOM_ICON.find(([re])=>re.test(k)); return hit?hit[1]:"🏠"; };
const hmSceneIcon=n=>{ n=String(n).toLowerCase(); if(/night|sleep|bed/.test(n)) return "🌙"; if(/morning|wake|sunrise/.test(n)) return "☀️"; if(/leav|away|out/.test(n)) return "🚪"; if(/movie|film|tv/.test(n)) return "🎬"; if(/dinner|eat/.test(n)) return "🍽"; if(/party/.test(n)) return "🎉"; if(/relax|chill/.test(n)) return "🕯"; return "✨"; };
/* hero: the live 3D house with the greeting and the weather over it (Tom-style) */
function renderHero(h, tiles){
  const hero=$("#hm-hero"), E=FHHome.esc;
  if(hmView==="3d"||!h.connected){ hero.innerHTML=""; return; }
  const now=new Date(), hr=now.getHours();
  const greet=hr<5?"Good night":hr<12?"Good morning":hr<17?"Good afternoon":hr<21?"Good evening":"Good night";
  const temps=tiles.filter(t=>t.domain==="sensor"&&t.device_class==="temperature");
  const inside=temps.filter(t=>!/out|exterior|porch|patio/i.test(t.name)).map(t=>parseFloat(t.state)).filter(n=>!isNaN(n));
  const hum=tiles.find(t=>t.domain==="sensor"&&t.device_class==="humidity"&&!/out/i.test(t.name));
  const outdoor=temps.find(t=>/out|exterior/i.test(t.name));
  const lightsOn=tiles.filter(t=>(t.domain==="light"||t.domain==="switch")&&t.on).length;
  const playing=tiles.filter(t=>t.domain==="media_player"&&t.on).length;
  const openers=tiles.filter(t=>(t.domain==="cover"&&t.state==="open")||(t.domain==="binary_sensor"&&["door","garage_door","window","opening"].includes(t.device_class)&&t.on));
  const wx=hmWx;
  let line1="";
  const oT=wx?wx.temp:(outdoor?Math.round(parseFloat(outdoor.state)):null);
  if(oT!=null) line1+=`<b>${oT}°</b> ${wx?E(String(wx.desc||"").toLowerCase()):"outside"}`;
  if(inside.length){ const avg=Math.round(inside.reduce((a,b)=>a+b,0)/inside.length); line1+=(line1?", ":"")+`inside <b>${avg}°</b>`+(hum?` and <b>${Math.round(parseFloat(hum.state))}%</b>`:""); }
  const bits=[now.toLocaleDateString([],{weekday:'long', month:'long', day:'numeric'})];
  if(wx&&wx.high!=null) bits.push(`high ${wx.high}° · low ${wx.low}°`);
  bits.push(lightsOn?`<span class="warn">${lightsOn} light${lightsOn>1?'s':''} on</span>`:`<span class="good">lights off</span>`);
  if(playing) bits.push(`${playing} playing`);
  if(hmPresence&&hmPresence.length){ const home=hmPresence.filter(p=>p.home).map(p=>p.name), away=hmPresence.filter(p=>!p.home).map(p=>p.name);
    bits.push((home.length?`<span class="good">${E(home.join(', '))} home</span>`:'nobody home')+(away.length?` · ${E(away.join(', '))} away`:'')); }
  if(openers.length) bits.push(`<span class="warn">${E(openers.map(o=>o.name.replace(/contact|sensor/ig,'').trim()).join(', '))} open</span>`);
  else bits.push('<span class="good">all closed</span>');
  const txt=`<div class="hm-greet">${greet}</div><div class="hm-wx">${line1||E(now.toLocaleDateString([],{weekday:'long', month:'long', day:'numeric'}))}</div><div class="hm-wx2">${bits.join(' · ')}</div>`;
  if(FHHome.has3D&&FHHome.has3D()){
    if(!hero.querySelector(".hm-hero3d")) hero.innerHTML='<div class="hm-hero3d"><div class="hm-h3"></div><div class="hm-hero-txt"></div><div class="hm-live"></div></div>';
    FHHome.render3D(hero.querySelector(".hm-h3"), h, {id:"hero", height:300, pins:false, labels:false, controls:true, floorButtons:false, hint:false, zoom:1.4});
    hero.querySelector(".hm-hero-txt").innerHTML=txt;
    const lv=hero.querySelector(".hm-live"); lv.className="hm-live"+(h.live===false?" off":""); lv.textContent="● "+(h.demo?"Demo":"Live");
  } else {
    hero.innerHTML=`<div class="hm-hero-plain">${txt}</div>`;
  }
}
/* short state word under each device icon, so a glance tells you open/closed, on/off, locked */
function hmDevState(t){
  if(t.domain==="cover") return t.state==="opening"?"Opening":t.state==="closing"?"Closing":t.state==="open"?"Open":"Closed";
  if(t.domain==="lock") return t.state==="locked"?"Locked":t.state==="unlocked"?"Unlocked":t.state;
  if(t.domain==="media_player") return t.on?(t.state==="playing"?"Playing":"On"):"Off";
  if(t.domain==="scene"||t.domain==="script") return "Run";
  if(t.domain==="camera") return "View";
  if(t.domain==="fan") return t.on?"On":"Off";
  return t.on?"On":"Off";
}
/* short label for a device inside a room card: drop the room's own name and a trailing "light" */
function hmShort(t, strip){
  let n=String(t.name||"");
  (strip||[]).filter(Boolean).sort((a,b)=>b.length-a.length).forEach(w=>{ n=n.replace(new RegExp("\\b"+String(w).replace(/[.*+?^${}()|[\]\\]/g,"\\$&")+"\\b","ig"),""); });
  n=n.replace(/\s+/g," ").trim().replace(/^(room|'s)\b\s*/i,"").replace(/\s*\broom$/i,"").trim();
  const m=n.replace(/\s*\b(light|lights|lamp)$/i,"").trim();
  const kind={light:"Light",switch:"Plug",fan:"Fan",media_player:"TV",cover:"Door",lock:"Lock",camera:"Camera"}[t.domain]||"";
  return m||n||kind||t.name;
}
function hmDevButton(t, strip){
  const E=FHHome.esc;
  const tap = t.domain==="media_player" ? `onclick="FHHome.remote('${E(t.entity_id)}','${E(String(t.name).replace(/['"\\]/g,""))}')"` : t.domain==="camera" ? `onclick="FHHome.camera('${E(t.entity_id)}','${E(String(t.name).replace(/['"\\]/g,""))}')"` : (t.toggleable||t.activatable) ? `onclick="hmTap(this,'${E(t.entity_id)}','${E(t.domain)}','${E(String(t.name).replace(/['"\\]/g,""))}')"` : "";
  // "on" = lit / open / unlocked: covers and locks use amber because open/unlocked is the state to notice
  const warn = (t.domain==="cover"||t.domain==="lock");
  const lit = t.domain==="lock" ? t.state!=="locked" : t.on;
  return `<button class="hm-dev${lit?' on':''}${warn?' warn':''}" data-eid="${E(t.entity_id)}" title="${E(t.name)} · ${E(FHHome.haStateLabel(t))}" ${tap}><span class="ic">${FHHome.haIcon(t)}</span>${strip?`<span class="nm">${E(hmShort(t,strip))}</span>`:''}<span class="st">${hmDevState(t)}</span></button>`;
}
/* ---- room pop-up: every device in a room by name, with its controls ---- */
let _rmKey=null, _rmBusy=0;
function roomDevices(key){
  const tiles=FHHome.tilesOf(hmLast||{}), rooms=FHHome.resolveRooms(hmLast||{});
  const skip=t=>t.domain==="scene"||t.domain==="script"||t.domain==="alarm_control_panel"||t.domain==="automation";
  if(key.room){ const r=rooms.find(x=>x.name===key.room&&String(x.floor||1)===String(key.floor));
    return {room:r, title:key.room, devs:r?tiles.filter(t=>!skip(t)&&FHHome.roomFor(t,rooms)===r):[]}; }
  return {room:null, title:key.area, devs:tiles.filter(t=>!skip(t)&&t.area===key.area&&!FHHome.roomFor(t,rooms))};
}
function rmState(t){
  if(t.domain==="binary_sensor"){ const dc=t.device_class||"";
    if(/door|window|opening|garage/.test(dc)) return [t.on?"Open":"Closed", t.on?"amb":""];
    if(/motion|occupancy|presence/.test(dc)) return [t.on?"Motion now":"No motion", t.on?"hot":""];
    if(dc==="moisture") return [t.on?"Wet!":"Dry", t.on?"amb":""];
    if(dc==="battery") return [t.on?"Low battery":"Battery OK", t.on?"amb":""];
    return [t.on?"On":"Off", t.on?"hot":""]; }
  if(t.domain==="light"&&t.on&&t.brightness!=null) return ["On · "+t.brightness+"%","hot"];
  if(t.domain==="lock") return [t.state==="locked"?"Locked":"Unlocked", t.state==="locked"?"":"amb"];
  if(t.domain==="cover") return [hmDevState(t), t.state==="closed"?"":"amb"];
  const l=FHHome.haStateLabel(t); return [l, t.on&&t.domain!=="sensor"?"hot":""];
}
function rmRow(t, strip){
  const E=FHHome.esc, [st,cls]=rmState(t), id=E(t.entity_id), nm=E(t.name), d=t.domain;
  let ctl="";
  if(d==="light"||d==="switch"||d==="fan") ctl=`<label class="rm-sw"><input type="checkbox" data-tg="${id}" ${t.on?"checked":""}><span></span></label>`;
  else if(d==="media_player") ctl=`<div class="rm-btns"><button data-tg="${id}">${t.on?"Turn off":"Turn on"}</button><button class="pri" data-remote="${id}" data-n="${nm}">Remote</button></div>`;
  else if(d==="cover") ctl=`<div class="rm-btns"><button data-svc="cover/open_cover" data-e="${id}">Open</button><button data-svc="cover/close_cover" data-e="${id}">Close</button></div>`;
  else if(d==="lock") ctl=`<div class="rm-btns">${t.state==="locked"?`<button data-svc="lock/unlock" data-e="${id}">Unlock</button>`:`<button class="pri" data-svc="lock/lock" data-e="${id}">Lock</button>`}</div>`;
  else if(d==="climate") ctl=`<div class="rm-btns"><button class="pri" data-th="${id}">Control</button></div>`;
  else if(d==="camera") ctl=`<div class="rm-btns"><button class="pri" data-cam="${id}" data-n="${nm}">View</button></div>`;
  let extra="";
  if(d==="light"&&t.dimmable) extra=`<div class="rm-dim"><span>🔅</span><input type="range" min="1" max="100" value="${t.on?(t.brightness||100):0}" data-dim="${id}" aria-label="${nm} brightness"><small>${t.on?(t.brightness||100)+"%":"off"}</small></div>`;
  if(d==="light"&&(t.color||t.whites)) extra+=`<button class="rm-colbtn" data-col="${id}">🎨 ${t.color?"Color":"White"}</button><div class="rm-colp" data-colp="${id}" hidden></div>`;
  return `<div class="rm-row" data-eid="${id}"><div class="rm-top"><div class="rm-ic">${FHHome.haIcon(t)}</div><div class="rm-t"><b>${nm}</b><span class="${cls}">${E(st)}</span></div>${ctl}</div>${extra}<div class="rm-eid">${id}</div></div>`;
}
function renderRoom(){
  if(!_rmKey||_rmBusy>Date.now()) return;
  if(_rmKey.climate) return renderThermostat();
  const {room, title, devs}=roomDevices(_rmKey), E=FHHome.esc;
  const order={light:0,switch:1,fan:2,cover:3,lock:4,media_player:5,climate:6,camera:7,binary_sensor:8,sensor:9};
  devs.sort((a,b)=>((order[a.domain]??10)-(order[b.domain]??10))||a.name.localeCompare(b.name));
  $("#rm-title").textContent=(room?hmRoomIcon(room)+" ":"🌳 ")+title;
  $("#rm-3d").hidden=!(room&&FHHome.has3D&&FHHome.has3D());
  const lit=devs.filter(t=>(t.domain==="light"||t.domain==="switch")&&t.on).length, ls=devs.filter(t=>t.domain==="light"||t.domain==="switch").length;
  $("#rm-sum").textContent=devs.length?`${devs.length} device${devs.length>1?"s":""}`+(ls?` · ${lit} of ${ls} light${ls>1?"s":""} on`:""):"Nothing in this room yet. Give a device this Area in Home Assistant.";
  const html=devs.map(t=>rmRow(t)).join(""), list=$("#rm-list");
  if(list.dataset.sig===html) return; list.dataset.sig=html; list.innerHTML=html;
  const done=(ms)=>setTimeout(loadHM, ms||400);
  list.querySelectorAll("[data-tg]").forEach(el=>el.onclick=async(e)=>{ if(navigator.vibrate) navigator.vibrate(10);
    try{ await post("/api/ha/toggle",{entity_id:el.dataset.tg}); }catch(err){ toast("Couldn't reach the wall"); } done(); });
  list.querySelectorAll("[data-svc]").forEach(el=>el.onclick=async()=>{ const [dm,sv]=el.dataset.svc.split("/");
    if(navigator.vibrate) navigator.vibrate(10); el.textContent="…";
    try{ await post("/api/ha/service",{domain:dm, service:sv, entity_id:el.dataset.e}); }catch(err){ toast("Couldn't reach the wall"); } done(1500); });
  list.querySelectorAll("[data-remote]").forEach(el=>el.onclick=()=>{ closeRoom(); FHHome.remote(el.dataset.remote, el.dataset.n); });
  list.querySelectorAll("[data-th]").forEach(el=>el.onclick=()=>openRoom({climate:el.dataset.th}));
  list.querySelectorAll("[data-cam]").forEach(el=>el.onclick=()=>{ closeRoom(); openCam(el.dataset.cam, el.dataset.n); });
  list.querySelectorAll("[data-col]").forEach(btn=>btn.onclick=()=>{
    const eid=btn.dataset.col, panel=list.querySelector(`[data-colp="${CSS.escape(eid)}"]`), t=devs.find(x=>x.entity_id===eid);
    if(!panel.hidden){ panel.hidden=true; panel.innerHTML=""; _rmBusy=0; return; }
    _rmBusy=Date.now()+120000;           // keep the pop-up still while a colour is being picked
    panel.innerHTML=FHHome.lightPanelHTML(t,{dim:false}); panel.hidden=false;
    FHHome.bindLightPanel(panel, t, async data=>{ _rmBusy=Date.now()+120000; if(navigator.vibrate) navigator.vibrate(6);
      try{ await post("/api/ha/service",{domain:"light", service:"turn_on", entity_id:eid, data}); }catch(err){ toast("Couldn't reach the wall"); } });
  });
  list.querySelectorAll("[data-dim]").forEach(el=>{ const lab=el.nextElementSibling;
    el.oninput=()=>{ _rmBusy=Date.now()+4000; lab.textContent=el.value+"%"; };
    el.onchange=async()=>{ _rmBusy=Date.now()+1500; if(navigator.vibrate) navigator.vibrate(6);
      try{ await post("/api/ha/service",{domain:"light", service:"turn_on", entity_id:el.dataset.dim, data:{brightness_pct:+el.value}}); }catch(err){ toast("Couldn't reach the wall"); }
      setTimeout(()=>{ _rmBusy=0; loadHM(); }, 1600); }; });
}
/* ---- thermostat pop-up: mode, setpoint(s), fan; taps are batched and sent after a short pause ---- */
let _thPend=null, _thTimer=null;
const TH_MODE={off:"Off", heat:"Heat", cool:"Cool", heat_cool:"Heat/Cool", auto:"Auto", dry:"Dry", fan_only:"Fan"};
function renderThermostat(){
  const E=FHHome.esc, tiles=FHHome.tilesOf(hmLast||{}), t=tiles.find(x=>x.entity_id===_rmKey.climate);
  $("#rm-3d").hidden=true;
  if(!t){ $("#rm-title").textContent="🌡 Thermostat"; $("#rm-sum").textContent="This thermostat isn't reporting right now."; $("#rm-list").innerHTML=""; return; }
  const mode=t.state, act=t.hvac_action||"", step=t.target_temp_step||1, mn=t.min_temp??45, mx=t.max_temp??95;
  const p=(_thPend&&_thPend.eid===t.entity_id)?_thPend:{};
  const low=p.low??t.target_temp_low, high=p.high??t.target_temp_high, one=p.temp??t.target_temperature;
  $("#rm-title").textContent="🌡 "+t.name;
  $("#rm-sum").textContent=t.current_humidity!=null?`Humidity ${Math.round(t.current_humidity)}%`:"";
  const peak=tiles.find(x=>x.entity_id==="binary_sensor.santee_cooper_peak_now");
  const actTxt={heating:"Heating",cooling:"Cooling",idle:"Idle",off:"Off",fan:"Fan only",drying:"Drying"}[act]||(mode==="off"?"Off":"");
  let h=`<div class="th-now"><div class="big">${t.current_temperature!=null?E(Math.round(t.current_temperature))+"°":"—"}</div><div class="act ${act==="heating"?"heat":act==="cooling"?"cool":""}">${E(actTxt)}<br><span style="font-weight:400;font-size:12px">inside now</span></div></div>`;
  if(peak&&peak.on) h+=`<div class="th-warn">⚡ <b>Santee Cooper peak hours right now.</b> Heat and AC are kept off to avoid the demand charge — turning it on now can cost more than the rest of the month.</div>`;
  const modes=(t.hvac_modes||["off","heat","cool","heat_cool"]).filter(m=>TH_MODE[m]);
  h+=`<div class="th-lab">Mode</div><div class="th-chips">${modes.map(m=>`<button data-mode="${m}" class="${m===mode?"on":""} ${m==="heat"?"heat":m==="cool"?"cool":""}">${TH_MODE[m]}</button>`).join("")}</div>`;
  const row=(cls,label,sub,key,val)=>`<div class="th-set ${cls}"><div class="l">${label}<small>${sub}</small></div><button data-adj="${key}" data-d="-1" aria-label="${label} down">−</button><div class="v">${val!=null?E(val)+"°":"—"}</div><button data-adj="${key}" data-d="1" aria-label="${label} up">+</button></div>`;
  // show the setpoints the thermostat actually reports (a range, or one number), not what the mode name suggests
  const range=(low!=null||high!=null)&&(mode==="heat_cool"||mode==="auto"||one==null);
  if(mode==="off") h+=`<div class="hint" style="margin-top:10px">The system is off. Pick Heat, Cool or Heat/Cool to turn it on.</div>`;
  else if(range) h+=`<div class="th-lab">Keep it between</div>`+row("heat","Heat to","heat comes on below","low",low)+row("cool","Cool to","AC comes on above","high",high);
  else { const c=mode==="heat"?"heat":mode==="cool"?"cool":(act==="heating"?"heat":act==="cooling"?"cool":"");
    h+=`<div class="th-lab">Set to</div>`+row(c,c==="heat"?"Heat to":c==="cool"?"Cool to":"Target",c==="heat"?"heat runs below this":c==="cool"?"AC runs above this":(mode==="auto"?"the thermostat decides heat or cool":""),"temp",one); }
  if(mode==="auto") h+=`<div class="hint" style="margin-top:6px">Auto: the thermostat decides on its own (usually following its Alarm.com schedule). Heat/Cool keeps it between two numbers you pick.</div>`;
  if(t.fan_modes&&t.fan_modes.length) h+=`<div class="th-lab">Fan</div><div class="th-chips">${t.fan_modes.map(f=>`<button data-fan="${E(f)}" class="${f===t.fan_mode?"on":""}">${E(f.charAt(0).toUpperCase()+f.slice(1).replace(/_/g," "))}</button>`).join("")}</div>`;
  h+=`<div class="hint" style="margin-top:12px">Your Alarm.com schedule can change this later; the peak-hours routine still turns the system off during peak.</div><div class="rm-eid" style="margin-left:0">${E(t.entity_id)}</div>`;
  const list=$("#rm-list"); if(list.dataset.sig===h) return; list.dataset.sig=h; list.innerHTML=h;
  const svc=async(service,data)=>{ if(navigator.vibrate) navigator.vibrate(10);
    try{ const r=await post("/api/ha/service",{domain:"climate", service, entity_id:t.entity_id, data}); if(r&&r.ok===false) toast(r.reason||"Thermostat didn't take it"); }catch(e){ toast("Couldn't reach the wall"); }
    _rmBusy=Date.now()+2500; setTimeout(()=>{ _rmBusy=0; _thPend=null; loadHM(); }, 2600); };
  list.querySelectorAll("[data-mode]").forEach(b=>b.onclick=()=>{ if(b.dataset.mode===mode) return; list.querySelectorAll("[data-mode]").forEach(x=>x.classList.toggle("on",x===b)); toast(`${t.name}: ${TH_MODE[b.dataset.mode]}`); svc("set_hvac_mode",{hvac_mode:b.dataset.mode}); });
  list.querySelectorAll("[data-fan]").forEach(b=>b.onclick=()=>{ list.querySelectorAll("[data-fan]").forEach(x=>x.classList.toggle("on",x===b)); svc("set_fan_mode",{fan_mode:b.dataset.fan}); });
  list.querySelectorAll("[data-adj]").forEach(b=>b.onclick=()=>{ if(navigator.vibrate) navigator.vibrate(6);
    const k=b.dataset.adj; _thPend=_thPend&&_thPend.eid===t.entity_id?_thPend:{eid:t.entity_id};
    const base={low,high,temp:one}[k]; let v=(_thPend[k]??base??(k==="high"?74:68))+step*(+b.dataset.d);
    v=Math.max(mn,Math.min(mx,Math.round(v/step)*step));
    if(k==="low"&&(_thPend.high??high)!=null&&v>(_thPend.high??high)-2) return toast("Heat has to stay at least 2° below cool");
    if(k==="high"&&(_thPend.low??low)!=null&&v<(_thPend.low??low)+2) return toast("Cool has to stay at least 2° above heat");
    _thPend[k]=v; b.parentElement.querySelector(".v").textContent=v+"°"; _rmBusy=Date.now()+3000;
    clearTimeout(_thTimer); _thTimer=setTimeout(()=>{ const pd=_thPend; if(!pd) return;
      const data=range?{target_temp_low:pd.low??low, target_temp_high:pd.high??high}:{temperature:pd.temp??one};
      toast(`${t.name}: `+(data.temperature!=null?data.temperature+"°":`${data.target_temp_low}°–${data.target_temp_high}°`)); svc("set_temperature",data); }, 1200); });
}
function openRoom(key){ _rmKey=key; _rmBusy=0; clearTimeout(_thTimer); _thPend=null; if(navigator.vibrate) navigator.vibrate(6); $("#rm-list").dataset.sig=""; renderRoom(); $("#rmov").classList.add("on"); }
function closeRoom(){ _rmKey=null; _rmBusy=0; $("#rmov").classList.remove("on"); }
$("#rm-close").onclick=closeRoom;
$("#rmov").onclick=(e)=>{ if(e.target.id==="rmov") closeRoom(); };
$("#rm-3d").onclick=()=>{ const k=_rmKey; if(!k) return; const r=FHHome.getLayout().find(x=>x.name===k.room&&String(x.floor||1)===String(k.floor)); closeRoom(); if(!r) return;
  if(hmView==="3d"){ FHHome.focus3D("main",r); const el=$("#hm-body .h3"); if(el) el.scrollIntoView({behavior:"smooth",block:"center"}); }
  else { window.scrollTo({top:0,behavior:"smooth"}); FHHome.focus3D("hero",r); } };
/* tap feedback: flip the button right away, buzz, say what's happening; the next poll confirms the real state */
async function hmTap(btn, eid, domain, name){
  if(_lpHeld){ _lpHeld=false; return; }          // that was a press-and-hold: the colour sheet opened instead
  if(navigator.vibrate) navigator.vibrate(12);
  const wasOn=btn.classList.contains("on"), st=btn.querySelector(".st");
  const verb = domain==="cover" ? (wasOn?"Closing":"Opening") : domain==="lock" ? (wasOn?"Locking":"Unlocking") : domain==="scene"||domain==="script" ? "Running" : (wasOn?"Turning off":"Turning on");
  if(!(domain==="scene"||domain==="script")){ btn.classList.toggle("on"); if(st) st.textContent=verb+"…"; }
  btn.classList.add("busy");
  toast(`${verb} ${name}`);
  try{ await post("/api/ha/toggle",{entity_id:eid}); }catch(e){ toast("Couldn't reach the wall"); btn.classList.toggle("on", wasOn); }
  setTimeout(()=>{ btn.classList.remove("busy"); loadHM(); }, domain==="cover"||domain==="lock" ? 1500 : 400);
}
function renderHM(h, force){
  hmLast=h; const E=FHHome.esc, body=$("#hm-body");
  if(!h.connected){ $("#hm-hero").innerHTML=""; body.innerHTML=`<div class="hm-offline">Home Assistant isn't connected${h.reason?` (${E(h.reason)})`:''}.<br>Check HA_URL / HA_TOKEN on the wall.</div>`; return; }
  const tiles=FHHome.tilesOf(h);
  if(_rmKey) renderRoom();
  const lights=tiles.filter(t=>t.domain==="light"||t.domain==="switch");
  const onCount=lights.filter(t=>t.on).length;
  const openers=tiles.filter(t=>(t.domain==="cover"&&t.state==="open")||(t.domain==="binary_sensor"&&["door","garage_door","window","opening"].includes(t.device_class)&&t.on));
  const temps=tiles.filter(t=>t.domain==="sensor"&&t.device_class==="temperature");
  const alarm=tiles.find(t=>t.domain==="alarm_control_panel");
  const locks=tiles.filter(t=>t.domain==="lock"), lockedN=locks.filter(t=>t.state==="locked").length;
  const power=tiles.find(t=>t.domain==="sensor"&&t.device_class==="power");
  const playingN=tiles.filter(t=>t.domain==="media_player"&&t.on).length;
  const sp=h.spotify;
  renderHero(h, tiles);

  // scene shortcuts: all-off first, then the HA scenes (max 4 tiles)
  const scenes=tiles.filter(t=>t.domain==="scene"&&!/night|leav|away|home/i.test(t.name)).slice(0,3);   // built-in Good night / Leaving cover those
  let html=FHHome.wxHTML(hmAlerts)+`<div class="hm-scenes">
    <button class="hm-scene" onclick="hmMode('goodnight',this)"><span class="ic">🌙</span>Good night</button>
    <button class="hm-scene" onclick="hmWelcome(this,'morning')"><span class="ic">☀️</span>Morning</button>
    <button class="hm-scene" onclick="hmMode('away',this)"><span class="ic">🚪</span>Leaving</button>
    <button class="hm-scene" onclick="hmWelcome(this)"><span class="ic">🏡</span>I'm home</button>
    <button class="hm-scene" id="hm-lights-off"><span class="ic">💡</span>All off</button>
    ${scenes.slice(0,0).map(s=>`<button class="hm-scene" onclick="FHHome.toggle('${E(s.entity_id)}')"><span class="ic">${hmSceneIcon(s.name)}</span>${E(s.name.replace(/scene/i,'').trim())}</button>`).join('')}
  </div>`;
  // status strip
  const st=[];
  st.push(onCount?`<span class="hm-chip warn">💡 ${onCount} light${onCount>1?'s':''} on</span>`:'<span class="hm-chip">💡 lights off</span>');
  st.push(playingN?`<span class="hm-chip ok">📺 ${playingN} playing</span>`:'<span class="hm-chip">📺 TVs off</span>');
  if(alarm) st.push(`<span class="hm-chip ${alarm.state==='disarmed'?'':'ok'}">🛡 ${E(FHHome.haStateLabel(alarm))}</span>`);
  if(locks.length) st.push(lockedN===locks.length?'<span class="hm-chip ok">🔒 locked</span>':`<span class="hm-chip warn">🔓 ${locks.length-lockedN} unlocked</span>`);
  if(openers.length) st.push(`<span class="hm-chip warn">⚠️ ${E(openers.map(o=>o.name.replace(/contact|sensor/ig,'').trim()).join(', '))} open</span>`);
  if(power) st.push(`<span class="hm-chip">⚡ ${E(power.state)} ${E(power.unit||'W')}</span>`);
  temps.filter(t=>/out|exterior/i.test(t.name)).slice(0,1).forEach(t=>st.push(`<span class="hm-chip">🌡 ${E(t.state)}${E(t.unit||'°')} outside</span>`));
  html+=`<div class="hm-status">${st.join('')}</div>`;
  const cams=tiles.filter(t=>t.domain==="camera");
  if(cams.length && hmView!=="all"){
    html+=`<div class="hm-sec">Cameras</div><div class="hm-cams">${cams.map(c=>`<div class="hm-cam" data-cam="${E(c.entity_id)}" data-name="${E(c.name)}"><img src="${E(c.snapshot)}?v=1&t=${Date.now()}" alt=""><div class="hm-cam-n">📷 ${E(c.name)}</div></div>`).join('')}</div>`;
  }

  if(sp){
    const playing=sp.state==="playing";
    html+=`<div class="hm-np${playing?'':' idle'}">
      <div class="hm-np-art">${sp.art?`<img src="${E(sp.art)}" alt="">`:'🎵'}</div>
      <div class="hm-np-main">
        <div class="hm-np-t">${E(sp.title||(playing?'Playing':'Nothing playing'))}</div>
        <div class="hm-np-s">${E([sp.artist,sp.album].filter(Boolean).join(' · ')||(sp.source?'on '+sp.source:'Tap play, or ask the wall'))}</div>
        <div class="hm-np-ctl">
          <button data-sp="prev">⏮</button><button class="main" data-sp="play_pause">${playing?'⏸':'▶'}</button><button data-sp="next">⏭</button>
          <span class="vols"><button class="pill vol" data-sp="vol" data-d="-1" title="Quieter"><b>−</b>🔉</button><button class="pill vol" data-sp="vol" data-d="1" title="Louder">🔊<b>+</b></button></span>
        </div>
        ${sp.sources&&sp.sources.length?`<div class="hm-np-dev">${sp.sources.slice(0,6).map(x=>`<button class="hm-dchip${x===sp.source?' on':''}" data-src="${E(x)}">${E(x)}</button>`).join('')}</div>`:''}
      </div>
    </div>`;
  }

  if(hmVillage&&hmVillage.reachable&&hmView!=="3d"){
    const v=hmVillage, awake=/awake|show/.test(v.mode||"");
    const vb=(d,ic,t)=>`<button class="hm-scene" data-vg="${d}"><span class="ic">${ic}</span>${t}</button>`;
    html+=`<div class="hm-sec">🎄 Village <span style="text-transform:none;letter-spacing:0;font-weight:500">· ${E(v.said||"")}</span></div>
      <div class="hm-scenes">${vb("tree","🌲","Tree show")}${vb("rachell","💖","Rachell's")}${vb("carol","🎶","Carolers")}
      ${vb("train","🚂","Train")}${vb("stop","⏹️","Stop train")}${awake?vb("sleep","🌙","Sleep"):vb("wake","☀️","Wake up")}</div>`;
  }

  if(hmView==="rooms"){
    const rooms=FHHome.resolveRooms(h);
    const byRoom=new Map();
    // put every controllable device in a room: explicit area, else name match, else "Other"
    const used=new Set();
    rooms.forEach(r=>{ byRoom.set(r.name+"|"+(r.floor||1), {room:r, devs:[]}); });
    tiles.forEach(t=>{
      if(!(t.toggleable||t.activatable||t.domain==="media_player"||t.domain==="sensor")) return;
      const hit=FHHome.roomFor(t, rooms);
      if(hit){ byRoom.get(hit.name+"|"+(hit.floor||1)).devs.push(t); used.add(t.entity_id); }
    });
    const other=tiles.filter(t=>!used.has(t.entity_id)&&t.domain!=="scene"&&t.domain!=="script"&&(t.toggleable||t.domain==="media_player"||t.domain==="sensor"));
    const cards=[...byRoom.values()].filter(x=>x.devs.length);
    if(!cards.length && !other.length){ html+='<div class="hm-offline">No devices yet. Add integrations in Home Assistant and give each device an Area.</div>'; }
    [1,2].forEach(f=>{
      const fl=cards.filter(c=>(c.room.floor||1)===f); if(!fl.length) return;
      html+=`<div class="hm-sec">${f===1?'Downstairs':'Upstairs'}</div><div class="hm-rooms">`;
      fl.forEach(({room,devs})=>{
        const on=devs.some(d=>d.on&&d.domain!=="sensor");
        const temp=devs.find(d=>d.domain==="sensor"&&d.device_class==="temperature");
        const onNames=devs.filter(d=>d.on&&d.domain!=="sensor").map(d=>d.name.replace(new RegExp(room.name+'( room)?','i'),'').trim()).filter(Boolean);
        html+=`<div class="hm-room${on?' on':''}" data-rn="${E(room.name)}" data-rf="${room.floor||1}" title="Tap for every device in this room">
          ${temp?`<div class="hm-room-t">${E(temp.state)}${E(temp.unit||'°')}</div>`:''}
          <div><div class="hm-room-n"><span class="hm-room-ic">${hmRoomIcon(room)}</span>${E(room.name)}</div><div class="hm-room-s">${on?E(onNames.slice(0,2).join(', ')||'On'):'All off'}</div></div>
          <div class="hm-room-devs">${devs.filter(d=>d.domain!=="sensor"&&d.domain!=="binary_sensor").map(d=>hmDevButton(d,[room.name,room.key,d.area])).join('')}</div>
        </div>`;
      });
      html+='</div>';
    });
    // devices whose HA Area isn't a room on the floor plan (Driveway, Yard, Shed…) get their own card per area
    const extraAreas=new Map();
    other.forEach(t=>{ if(t.area){ if(!extraAreas.has(t.area)) extraAreas.set(t.area,[]); extraAreas.get(t.area).push(t); } });
    const noArea=other.filter(t=>!t.area);
    if(extraAreas.size){
      html+=`<div class="hm-sec">Outside &amp; other</div><div class="hm-rooms">`;
      [...extraAreas.entries()].forEach(([area,devs])=>{
        const on=devs.some(d=>d.on&&d.domain!=="sensor"), temp=devs.find(d=>d.domain==="sensor"&&d.device_class==="temperature");
        const ic=/drive|yard|garden|outside|exterior|front|back|shed|pool|patio|deck/i.test(area)?"🌳":"🏠";
        html+=`<div class="hm-room${on?' on':''}" data-area="${E(area)}">
          ${temp?`<div class="hm-room-t">${E(temp.state)}${E(temp.unit||'°')}</div>`:''}
          <div><div class="hm-room-n"><span class="hm-room-ic">${ic}</span>${E(area)}</div><div class="hm-room-s">${on?E(devs.filter(d=>d.on&&d.domain!=="sensor").map(d=>d.name).slice(0,2).join(', ')):'All off'}</div></div>
          <div class="hm-room-devs">${devs.filter(d=>d.domain!=="sensor").map(d=>hmDevButton(d,[area])).join('')}</div>
        </div>`;
      });
      html+='</div>';
    }
    if(noArea.filter(d=>d.domain!=="sensor").length){
      html+=`<div class="hm-sec">Elsewhere</div><div class="hm-room hm-unassigned"><div><div class="hm-room-n">Unassigned</div><div class="hm-room-s">In Home Assistant: Settings → Areas → pick a room → Add device</div></div>
        <div class="hm-unl">${noArea.filter(d=>d.domain!=="sensor").map(t=>`<div class="hm-unl-row">${hmDevButton(t)}<div class="hm-unl-t"><b>${E(t.name)}</b><span>${E(t.entity_id)}</span></div></div>`).join('')}</div></div>`;
    }
    // climate: outside card + a row per temperature sensor / thermostat
    const wx=hmWx, outdoorT=temps.find(t=>/out|exterior/i.test(t.name));
    const hums=tiles.filter(t=>t.domain==="sensor"&&t.device_class==="humidity");
    const base=s=>String(s||"").toLowerCase().replace(/temp(erature)?|humidity|sensor|\(.*?\)/g,"").trim();
    const partner=t=>hums.find(hh=>base(hh.name)===base(t.name));
    const climates=tiles.filter(t=>t.domain==="climate");
    if(wx||temps.length||climates.length){
      html+='<div class="hm-sec">Climate</div>';
      const oT=wx?wx.temp:(outdoorT?Math.round(parseFloat(outdoorT.state)):null);
      if(oT!=null){
        const oh=outdoorT&&partner(outdoorT);
        html+=`<div class="hm-clim"><div class="hm-clim-top"><span>Outside</span><span>${wx?E(String(wx.desc||"").toLowerCase()):''}</span></div>
          <div class="hm-clim-big">${oT}°</div>
          <div class="hm-clim-grid">${wx&&wx.high!=null?`<div><span>High</span><b>${wx.high}°</b></div><div><span>Low</span><b>${wx.low}°</b></div>`:''}${oh?`<div><span>Humidity</span><b>${E(oh.state)}%</b></div>`:''}${wx&&wx.sunrise?`<div><span>Sunrise</span><b>${E(new Date(wx.sunrise).toLocaleTimeString([],{hour:'numeric',minute:'2-digit'}))}</b></div>`:''}</div></div>`;
      }
      climates.forEach(c=>{ html+=`<div class="hm-row hm-clim-row" data-clim="${E(c.entity_id)}" title="Tap to control"><div class="ric">🌡</div><div class="rt"><b>${E(c.name)}</b><span>${E(FHHome.haStateLabel(c))}</span></div><div class="rv">${c.current_temperature!=null?E(c.current_temperature)+'°':''}</div></div>`; });
      const num=t=>t&&!isNaN(parseFloat(t.state));
      // skip a thermostat's own temperature sensor (the thermostat row already shows it) and thermometers that are offline
      const ofClimate=t=>climates.some(c=>{ const b=base(c.name).replace(/thermostat/,"").trim(); return b && base(t.name).replace(/thermostat/,"").trim()===b; });
      temps.filter(t=>t!==outdoorT && !ofClimate(t) && num(t)).forEach(t=>{ const hh=partner(t);
        const sub=num(hh)?'humidity '+E(hh.state)+'%':(num(t)?'temperature':'offline — check its battery / Bluetooth range');
        html+=`<div class="hm-row"><div class="ric">${/out|porch|patio|walk/i.test(t.name)?'🌿':'🌡'}</div><div class="rt"><b>${E(t.name.replace(/temp(erature)?/i,'').trim())}</b><span>${sub}</span></div><div class="rv">${num(t)?E(t.state)+E(t.unit||'°'):'<small>—</small>'}</div></div>`; });
    }
  } else if(hmView==="all"){
    (h.groups||[]).filter(g=>g.group!=="Sensors").forEach(g=>{
      html+=`<div class="hm-sec">${E(g.group)}</div><div class="tile-grid">`;
      g.tiles.forEach(t=>{
        const scene=t.activatable, ro=!t.toggleable&&!t.activatable, un=t.state==="unavailable";
        const tap = t.domain==="media_player" ? `onclick="FHHome.remote('${E(t.entity_id)}','${E(String(t.name).replace(/['"\\]/g,""))}')"` : (!ro?`onclick="FHHome.toggle('${E(t.entity_id)}')"`:"");
        html+=`<div class="tile${t.on?' on':''}${scene?' scene':''}${ro?' ro':''}${un?' unavail':''}" ${tap}><div class="t-ico">${FHHome.haIcon(t)}</div><div class="t-name">${E(t.name)}</div>${scene?'':`<div class="t-state">${E(FHHome.haStateLabel(t))}</div>`}</div>`;
      });
      html+='</div>';
    });
  }

  const tail=hmView!=="day"?`<div style="margin-top:14px">${FHHome.laundryHTML(hmLaundry)}${FHHome.healthHTML(hmHealth)}</div>`:"";   // washer/dryer + needs attention at the bottom
  const sig=(html+tail).replace(/&t=\d+/g,"");
  if(!force && body.dataset.sig===sig){ body.querySelectorAll(".hm-cam img").forEach(im=>{ im.src=im.src.replace(/&t=\d+/,"&t="+Date.now()); }); return; }
  body.dataset.sig=sig; body.innerHTML=html;

  if(hmView==="plan"){ const holder=document.createElement("div"); body.appendChild(holder); FHHome.renderFloorView(holder,h,{budget:360}); }
  if(hmView==="day"&&window.FHTimeline){ const holder=document.createElement("div"); body.appendChild(holder); FHTimeline.render(holder); }
  if(hmView==="3d"){ const holder=document.createElement("div"); body.appendChild(holder);
    if(FHHome.has3D&&FHHome.has3D()) FHHome.render3D(holder,h,{id:"main", height:Math.min(560,Math.max(380,Math.round(window.innerHeight*0.62))), pins:true});
    else FHHome.renderIsoView(holder,h); }
  if(tail){ const tl=document.createElement("div"); tl.innerHTML=tail; body.appendChild(tl); }

  body.querySelectorAll(".hm-cam").forEach(c=>{ c.onclick=()=>openCam(c.dataset.cam, c.dataset.name); });
  body.querySelectorAll("[data-vg]").forEach(b=>{ b.onclick=async()=>{ if(navigator.vibrate) navigator.vibrate(8);
    const ic=b.innerHTML; b.disabled=true; let r={};
    try{ r=await post("/api/village/cmd",{do:b.dataset.vg}).then(x=>x.json()); }catch(e){}
    b.disabled=false; b.innerHTML=ic; if(!r.ok) toast(r.reason||"The village isn't answering");
    setTimeout(()=>fetch("/api/village/status").then(x=>x.json()).then(v=>{ hmVillage=v; if(hmLast) renderHM(hmLast,true); }).catch(()=>{}),1500); }; });
  // tap a room card (not one of its device buttons) -> pop-up with every device in it
  body.querySelectorAll(".hm-room[data-rn]").forEach(c=>{ c.onclick=(e)=>{ if(e.target.closest("button")) return;
    openRoom({room:c.dataset.rn, floor:c.dataset.rf}); }; });
  body.querySelectorAll("[data-clim]").forEach(c=>{ c.onclick=()=>openRoom({climate:c.dataset.clim}); });
  body.querySelectorAll(".hm-room[data-area]").forEach(c=>{ c.onclick=(e)=>{ if(e.target.closest("button")) return;
    openRoom({area:c.dataset.area}); }; });
  const lo=$("#hm-lights-off"); if(lo) lo.onclick=async()=>{ lo.textContent="…"; for(const t of lights.filter(t=>t.on)){ try{ await post("/api/ha/toggle",{entity_id:t.entity_id}); }catch(e){} } setTimeout(loadHM,500); };
  body.querySelectorAll(".hm-np [data-sp]").forEach(b=>{ b.onclick=async()=>{
    const a=b.dataset.sp; if(navigator.vibrate) navigator.vibrate(8);
    if(a==="vol"){ const v=Math.max(0,Math.min(1,(sp.volume??0.5)+0.1*(+b.dataset.d))); await post("/api/ha/spotify",{action:"volume",value:String(v)}).catch(()=>{}); }
    else await post("/api/ha/spotify",{action:a}).catch(()=>{});
    setTimeout(loadHM,600); }; });
  body.querySelectorAll(".hm-dchip").forEach(c=>{ c.onclick=async()=>{ await post("/api/ha/spotify",{action:"source",value:c.dataset.src}).catch(()=>{}); setTimeout(loadHM,800); }; });
}
// come back to the tab you were on last time
const EMBED = new URLSearchParams(location.search).get("embed");
if(EMBED==="settings"){ document.body.classList.add("embed"); setTimeout(()=>switchView("settings"),0); }
if(EMBED==="add"){
  const q=new URLSearchParams(location.search), kind=q.get("kind")||"event", d=q.get("date"), tm=q.get("time");
  document.body.classList.add("embed","embed-add");
  // match the wall: same light/dark theme, colours, corners and font as the screen around the pop-up
  const syncTheme=()=>{ try{
    const pr=parent.document.documentElement, cs=parent.getComputedStyle(pr), me=document.documentElement;
    const t=pr.getAttribute("data-theme"); if(t) me.setAttribute("data-theme",t);
    ["--bg","--panel","--panel2","--ink","--ink-dim","--line","--now","--good","--r","--font"].forEach(v=>{ const x=cs.getPropertyValue(v); if(x&&x.trim()) me.style.setProperty(v,x.trim()); });
    const bf=parent.getComputedStyle(parent.document.body).fontFamily; if(bf) document.body.style.fontFamily=bf;
  }catch(e){} };
  syncTheme(); setTimeout(syncTheme,300); setTimeout(syncTheme,1500);
  setTimeout(()=>{ switchView("add");
    const b=document.querySelector(`.seg button[data-f="${kind}"]`); if(b) b.click();
    // fill the date into whichever form is showing, now and whenever the type changes
    const fill=()=>{ if(d) ["e_date","t_due","c_due","m_date","cd_date"].forEach(id=>{ const el=$("#"+id); if(el) el.value=d; });
      if(tm&&$("#e_time")) $("#e_time").value=tm;
      const first=$("#form input:not([type=date]):not([type=time]):not([type=checkbox])"); if(first) first.focus(); };
    // the form redraws when people/calendars finish loading, so refill after every draw
    const _rf=renderForm; renderForm=function(){ const keep=$("#form input:focus"), v=keep&&keep.id?[keep.id,keep.value]:null; _rf.apply(this,arguments); fill();
      if(v&&$("#"+v[0])){ $("#"+v[0]).value=v[1]; } };
    fill();
  },0);
  // saved -> tell the wall (it refreshes and closes the pop-up)
  const _t=toast; toast=function(m){ _t(m); if(/\badded\b/i.test(String(m))&&!/couldn/i.test(String(m))) try{ parent.postMessage({fh:"added", msg:String(m)}, location.origin); }catch(e){} };
}
else try{ const v=localStorage.getItem("fh_view"); if(v&&v!=="add"&&$("#view-"+v)) setTimeout(()=>switchView(v),0); }catch(e){}

/* ---- TV remote (same /api/ha/media backend as the wall's remote) ---- */
let tvEid=null, tvList=[];
async function loadTVs(){
  const box=$("#tv-pick");
  try{
    const h=await fetch("/api/ha/home").then(r=>r.json());
    tvList=[]; (h.groups||[]).forEach(g=>(g.tiles||[]).forEach(t=>{ if(t.domain==="media_player"&&!/spotify/i.test(t.entity_id)) tvList.push(t); }));
    if(!h.connected&&!h.demo){ box.innerHTML=`<div class="hint">Home Assistant isn't connected (${h.reason||"check HA_URL/HA_TOKEN"}).</div>`; return; }
  }catch(e){ box.innerHTML='<div class="hint">Couldn\'t reach the wall.</div>'; return; }
  if(!tvList.length){ box.innerHTML='<div class="hint">No TVs yet. Add your Rokus in Home Assistant (Settings → Devices &amp; services → Roku).</div>'; return; }
  box.innerHTML="";
  tvList.forEach(t=>{
    const b=document.createElement("button"); b.className=(t.entity_id===tvEid?"cur":"");
    b.innerHTML=`${t.name}<span class="st">${t.on?"on":"off"}</span>`;
    b.onclick=()=>openTV(t.entity_id,t.name); box.appendChild(b);
  });
  if(!tvEid&&tvList.length===1) openTV(tvList[0].entity_id, tvList[0].name);
  else if(tvEid) $("#tv-remote").hidden=false;
}
async function openTV(eid,name){
  tvEid=eid; $("#tv-name").textContent=name; $("#tv-remote").hidden=false;
  $("#tv-pick").querySelectorAll("button").forEach((b,i)=>b.classList.toggle("cur", tvList[i]&&tvList[i].entity_id===eid));
  const apps=$("#tv-apps"); apps.innerHTML='<div class="hint">Loading channels…</div>';
  let info=null; try{ info=await fetch("/api/ha/media_info?entity_id="+encodeURIComponent(eid)).then(r=>r.json()); }catch(e){}
  if(tvEid!==eid) return;
  tvApps=(info&&info.sources&&info.sources.length)?info.sources:["Netflix","YouTube","Spectrum TV","Disney Plus","Hulu","Prime Video"];
  tvSource=info&&info.source; renderTVApps();
}
/* Favorite apps: pinned ones show first (shared by both phones via settings.rokuApps); the rest sit
   under "All apps". Edit mode: tap to pin/unpin, pinned order = the order you pin them. */
let tvApps=[], tvSource=null, tvEditing=false;
function renderTVApps(){
  const fav=(FH.get().rokuApps||[]).filter(a=>tvApps.includes(a));
  const pinned=fav.length?fav:tvApps.slice(0,6), rest=tvApps.filter(a=>!pinned.includes(a));
  const mk=(a,box)=>{ const b=document.createElement("button"); b.type="button";
    b.className="rbtn"+(a===tvSource?" cur":"")+(tvEditing?" pin"+(fav.includes(a)?" on":""):""); b.textContent=a;
    b.onclick=()=>{ if(tvEditing){ const f=(FH.get().rokuApps||[]).filter(x=>x!==a); if(!fav.includes(a)) f.push(a); FH.save({rokuApps:f}); renderTVApps(); } else sendTV("app",a); };
    box.appendChild(b); };
  const apps=$("#tv-apps"), all=$("#tv-apps-all"); apps.innerHTML=""; all.innerHTML="";
  (tvEditing?tvApps:pinned).forEach(a=>mk(a,apps));
  if(!tvEditing) rest.forEach(a=>mk(a,all));
  $("#tv-apps-all-wrap").hidden=tvEditing||!rest.length;
  $("#tv-apps-edit").textContent=tvEditing?"Done":"Edit";
}
$("#tv-apps-edit").onclick=()=>{ tvEditing=!tvEditing; if(tvEditing) toast("Tap the apps you want on top"); renderTVApps(); };
async function sendTV(action,value){
  if(!tvEid) return;
  if(navigator.vibrate) navigator.vibrate(8);
  try{ await post("/api/ha/media",{entity_id:tvEid, action, value:value||""}); }catch(e){ toast("TV didn't respond"); }
  if(action==="power") setTimeout(loadTVs, 800);
}
document.querySelectorAll("#tv-remote .rbtn[data-m]").forEach(b=>{ b.onclick=()=>sendTV(b.dataset.m); });

function saveNested(group,key,val){
  const cur={...(FH.get()[group]||{})}; cur[key]=val; FH.save({[group]:cur});
}

/* accent + new-person color swatches */
let personColor=PALETTE[0];
function buildAccent(){
  const el=$("#set-accent"); el.innerHTML="";
  const cur=FH.get().accent;
  PALETTE.forEach(c=>{
    const s=document.createElement("div"); s.className="swatch"+(c===cur?" sel":""); s.style.background=c;
    s.onclick=()=>{ FH.save({accent:c}); buildAccent(); };
    el.appendChild(s);
  });
}
function buildPersonColors(){
  const el=$("#person-colors"); el.innerHTML="";
  PALETTE.forEach((c,i)=>{
    const s=document.createElement("div"); s.className="swatch"+(c===personColor?" sel":""); s.style.background=c;
    s.onclick=()=>{ personColor=c; buildPersonColors(); };
    el.appendChild(s);
  });
}

async function loadVoiceHistory(){
  const box=$("#vh-list"); if(!box) return;
  let log=[]; try{ log=(await fetch("/api/ai/voice/log").then(r=>r.json())).log||[]; }catch(e){}
  box.textContent="";
  if(!log.length){ box.textContent="Nothing yet — talk to the wall, then tap Refresh."; return; }
  for(const e of log){
    const row=document.createElement("div"); row.style.cssText="padding:6px 0;border-bottom:1px solid rgba(127,127,127,.2)";
    const when=document.createElement("small"); when.style.opacity=".6"; when.textContent=(e.at||"").replace("T"," ").slice(5,16)+"  ";
    const heard=document.createElement("b"); heard.textContent=e.heard?("“"+e.heard+"”"):"(nothing heard)";
    const reply=document.createElement("div"); reply.style.opacity=".8"; reply.textContent="→ "+(e.reply||"")+(e.took?"  ["+e.took+"]":"");
    row.append(when,heard,reply); box.append(row);
  }
}
async function loadAiCost(){
  const box=$("#ai-cost"); if(!box) return;
  let c=null; try{ c=await fetch("/api/ai/cost").then(r=>r.json()); }catch(e){}
  if(!c){ box.textContent="Couldn't load the AI cost."; return; }
  const E=FHHome.esc, m=d=>d>=0.995?"$"+d.toFixed(2):(d*100<0.05?(d?"under 0.1\u00a2":"0\u00a2"):(d*100).toFixed(d*100<10?1:0)+"\u00a2");
  box.innerHTML=`<b>What the AI has cost (approximate)</b>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin:8px 0;text-align:center">
      ${[["Today",c.today],["7 days",c.week],["This month",c.month],["Total",c.total]].map(([l,v])=>`<div style="background:rgba(127,127,127,.12);border-radius:10px;padding:8px 2px"><div style="font-size:17px;font-weight:700">${m(v)}</div><small>${l}</small></div>`).join("")}
    </div>
    ${(c.by_feature||[]).map(f=>`<div style="display:flex;justify-content:space-between;padding:3px 0"><span>${E(f.label)} <small style="opacity:.6">\u00d7${f.n}${f.searches?` \u00b7 ${f.searches} web search${f.searches==1?"":"es"}`:""}</small></span><b>${m(f.cost)}</b></div>`).join("")||"<small>Nothing yet. Ask the wall something.</small>"}
    <small style="opacity:.65;display:block;margin-top:6px">${c.since?`Counted since ${E(c.since)} (${c.calls} AI requests). `:""}Estimates from token counts at list prices; the exact bill is on the Anthropic Console under Cost.</small>`;
}
async function loadCloudVoice(){
  const box=$("#cv-box"); if(!box) return;
  let c=null; try{ c=await fetch("/api/ai/voice/cloud").then(r=>r.json()); }catch(e){}
  if(!c){ box.innerHTML=""; return; }
  const E=FHHome.esc, s=FH.get();
  if(!c.key){ box.innerHTML=`<div class="hint"><b>The wall's voice</b> — using the built-in voice. For a nicer one (and Santa at Christmas), make a free ElevenLabs account, create an API key, and add <code>ELEVENLABS_API_KEY=…</code> to the <code>.env</code> file on the wall, then restart FamilyHub.</div>`; return; }
  const opts=sel=>`<option value="">Built-in voice</option>`+(sel&&!c.voices.some(v=>v.id===sel)?`<option value="${E(sel)}" selected>(a voice that is no longer in your account)</option>`:"")+c.voices.map(v=>`<option value="${E(v.id)}"${v.id===sel?" selected":""}>${E(v.name)}${v.kind&&v.kind!=="premade"?" ("+E(v.kind)+")":""}</option>`).join("");
  const left=c.limit!=null?`${Math.max(0,c.limit-c.used).toLocaleString()} of ${c.limit.toLocaleString()} credits left this month${c.resets?` (resets ${new Date(c.resets*1000).toLocaleDateString([], {month:"short",day:"numeric"})})`:""}.`:"";
  const none=!c.voices.length?`<div class="hint" style="color:#c0392b;margin:0 0 6px">No ElevenLabs voices came back${c.voices_error?": "+E(c.voices_error):""}. Most often the API key isn't allowed to read voices: on elevenlabs.io open API Keys, edit the key, set <b>Voices</b> to Read and <b>Text to Speech</b> to Access. Then come back here.</div>`:"";
  box.innerHTML=`<div class="hint" style="margin:0 0 4px"><b>The wall's voice</b></div>${none}
    <div class="srow"><span>Everyday</span><span style="display:flex;gap:6px;width:62%"><select id="cv-day" style="margin:0;flex:1;min-width:0">${opts(s.cloudVoiceId)}</select><button class="tool" type="button" data-cvt="cv-day" style="margin:0;flex:0 0 46px;width:46px">▶</button></span></div>
    <div class="srow"><span>🎅 Christmas</span><span style="display:flex;gap:6px;width:62%"><select id="cv-santa" style="margin:0;flex:1;min-width:0">${opts(s.santaVoiceId)}</select><button class="tool" type="button" data-cvt="cv-santa" style="margin:0;flex:0 0 46px;width:46px">▶</button></span></div>
    <label class="chk"><input type="checkbox" id="cv-on"${s.santaVoice!==false?" checked":""}> Use the Christmas voice from the day after Thanksgiving to Christmas Day${c.santa_now?" (now)":""}</label>
    <div class="hint" id="cv-msg">${E(c.error||"")}${c.error?"<br>":""}${left} When the credits run out, or the internet is down, the wall uses the built-in voice. Voices listed are the ones in your ElevenLabs account (add more under Voices there).</div>`;
  $("#cv-day").onchange=e=>{ FH.save({cloudVoiceId:e.target.value}); };
  $("#cv-santa").onchange=e=>{ FH.save({santaVoiceId:e.target.value}); };
  $("#cv-on").onchange=e=>{ FH.save({santaVoice:e.target.checked}); };
  box.querySelectorAll("[data-cvt]").forEach(b=>b.onclick=async()=>{
    const id=$("#"+b.dataset.cvt).value, msg=$("#cv-msg");
    const text=(b.dataset.cvt==="cv-santa"&&id)?"Ho ho ho! Merry Christmas! The washer is done.":"Good morning! Here's what's happening today.";
    b.disabled=true;
    const player=new Audio();                                  // made in the tap itself, or iPhones refuse to play it later
    try{ const r=await post("/api/ai/voice/cloud/test",{voice_id:id,text}); if(!r.ok){ const j=await r.json().catch(()=>({})); msg.textContent=j.detail||"That voice didn't work."; } else { const u=URL.createObjectURL(await r.blob()); player.src=u; player.onended=()=>URL.revokeObjectURL(u); player.play().catch(()=>{ msg.textContent="Your phone blocked the sound. Tap \u25B6 once more."; }); } }
    catch(e){ msg.textContent="Couldn't reach FamilyHub."; }
    b.disabled=false; });
}
function setupDiag(){
  const go=$("#dg-go"); if(!go||go._wired) return; go._wired=true;
  const out=$("#dg-out"), msg=$("#dg-msg");
  const run=async()=>{ msg.textContent="Gathering\u2026"; try{ out.value=await fetch("/api/ha/diag?q="+encodeURIComponent($("#dg-q").value.trim())).then(r=>r.text()); msg.textContent="Ready. Tap Copy, then paste it into the chat."; }catch(e){ msg.textContent="Couldn't reach FamilyHub."; } };
  go.onclick=run; $("#dg-q").addEventListener("keydown",e=>{ if(e.key==="Enter") run(); });
  $("#dg-copy").onclick=async()=>{ if(!out.value){ await run(); }
    let ok=false; try{ await navigator.clipboard.writeText(out.value); ok=true; }catch(e){}
    if(!ok){ try{ out.removeAttribute("readonly"); out.focus(); out.select(); out.setSelectionRange(0, out.value.length); ok=document.execCommand("copy"); out.setAttribute("readonly",""); }catch(e){} }
    msg.textContent=ok?"Copied. Paste it into the chat.":"Couldn't copy automatically: press and hold in the box, Select All, Copy."; };
}
function setupVoiceHistory(){
  setupDiag();
  const go=$("#vh-go"); if(!go||go._wired) return; go._wired=true;
  const run=async()=>{ const t=$("#vh-try").value.trim(); if(!t) return; $("#vh-out").textContent="…";
    try{ const r=await post("/api/ai/command",{text:t}).then(r=>r.json()); $("#vh-out").textContent="→ "+(r.say||(r.briefing?"(the wall reads the briefing)":"done")); $("#vh-try").value=""; }
    catch(e){ $("#vh-out").textContent="Couldn't reach FamilyHub."; }
    loadVoiceHistory(); };
  go.onclick=run; $("#vh-try").addEventListener("keydown",e=>{ if(e.key==="Enter") run(); });
  $("#vh-refresh").onclick=()=>{ loadVoiceHistory(); loadAiCost(); };
  $("#vh-clear").onclick=async()=>{ await fetch("/api/ai/voice/log",{method:"DELETE"}).catch(()=>{}); loadVoiceHistory(); };
  const d=go.closest("details"); if(d) d.addEventListener("toggle",()=>{ if(d.open){ loadVoiceHistory(); loadAiCost(); loadCloudVoice(); } });
}
async function setupVillage(){
  const E=FHHome.esc, box=$("#vl-lights"); if(!box) return;
  const c=$("#vl-auto"); if(document.activeElement!==c) c.checked=FH.get().villageAuto!==false;
  if(!c._wired){ c._wired=true; c.onchange=()=>{ FH.save({villageAuto:c.checked}); toast("Saved"); }; }
  if(box._done) return;
  let h=null; try{ h=await fetch("/api/ha/home").then(r=>r.json()); }catch(e){}
  const tiles=((h&&h.groups)||[]).flatMap(g=>g.tiles||[]).filter(t=>t.domain==="light"||t.domain==="switch");
  if(!tiles.length){ box.innerHTML=`<div class="hint" style="margin:0">No lights found in Home Assistant.</div>`; return; }
  box._done=true;
  const on=new Set(FH.get().villageOpenLights||[]);
  box.innerHTML=tiles.map(t=>`<label class="chk" style="margin:2px 0"><input type="checkbox" value="${E(t.entity_id)}"${on.has(t.entity_id)?" checked":""}> ${E(t.name)}</label>`).join("");
  box.onchange=()=>{ FH.save({villageOpenLights:[...box.querySelectorAll("input:checked")].map(i=>i.value)}); toast("Saved"); };
}
async function setupTvLights(){
  const E=FHHome.esc, box=$("#tvb-list"); if(!box) return;
  let h=null; try{ h=await fetch("/api/ha/home").then(r=>r.json()); }catch(e){}
  const tiles=((h&&h.groups)||[]).flatMap(g=>g.tiles||[]), nm=id=>(tiles.find(t=>t.entity_id===id)||{}).name||id;
  const lights=tiles.filter(t=>t.domain==="light"), tvs=tiles.filter(t=>t.domain==="media_player");
  const ls=$("#tvb-light"), ts=$("#tvb-tv");
  if(document.activeElement!==ls) ls.innerHTML=lights.length?lights.map(t=>`<option value="${E(t.entity_id)}">${E(t.name)}</option>`).join(""):`<option value="">No lights found</option>`;
  if(document.activeElement!==ts) ts.innerHTML=tvs.length?tvs.map(t=>`<option value="${E(t.entity_id)}">${E(t.name)}</option>`).join(""):`<option value="">No TVs found</option>`;
  const save=(list,redraw)=>FH.save({tvBacklights:list}).then(()=>{ toast("Saved"); if(redraw) setupTvLights(); });   // a field edit must not rebuild the list under your finger
  const cur=()=>(FH.get().tvBacklights||[]).map(p=>({follow:true,dim:true,play:30,idle:70,...p}));
  const list=cur();
  box.innerHTML=list.length?list.map((p,i)=>`<div style="border:1px solid rgba(127,127,127,.25);border-radius:12px;padding:8px 10px;margin:0 0 8px">
      <div class="srow" style="margin:0"><b>${E(nm(p.light))}</b><span style="opacity:.7">behind ${E(nm(p.tv))}</span><button class="tool" type="button" data-tvx="${i}" style="margin:0">Remove</button></div>
      <label class="chk"><input type="checkbox" data-tvk="follow" data-i="${i}"${p.follow?" checked":""}> Turn on and off with the TV</label>
      <label class="chk"><input type="checkbox" data-tvk="dim" data-i="${i}"${p.dim?" checked":""}> Dim for what's on the screen:</label>
      <div class="srow" style="margin:0 0 0 30px"><span>While something is playing</span><span><input type="number" data-tvk="play" data-i="${i}" value="${+p.play||30}" min="1" max="100" style="width:64px;display:inline-block;margin:0 4px 0 0">%</span></div>
      <div class="srow" style="margin:0 0 0 30px"><span>Paused or on the menu</span><span><input type="number" data-tvk="idle" data-i="${i}" value="${+p.idle||70}" min="1" max="100" style="width:64px;display:inline-block;margin:0 4px 0 0">%</span></div>
    </div>`).join(""):`<div class="hint" style="margin-top:0">No backlights paired yet.</div>`;
  box.querySelectorAll("[data-tvx]").forEach(b=>b.onclick=()=>{ const l=cur(); l.splice(+b.dataset.tvx,1); save(l,true); });
  box.querySelectorAll("[data-tvk]").forEach(c=>c.onchange=()=>{ const l=cur(), p=l[+c.dataset.i]; if(!p) return; p[c.dataset.tvk]=c.type==="checkbox"?c.checked:Math.max(1,Math.min(100,+c.value||1)); save(l); });
  const add=$("#tvb-add"); if(!add._wired){ add._wired=true; add.onclick=()=>{ if(!ls.value||!ts.value) return; const l=cur();
    if(l.some(p=>p.light===ls.value)){ toast("That light is already paired"); return; }
    l.push({light:ls.value, tv:ts.value, follow:true, dim:true, play:30, idle:70}); save(l,true); }; }
}
function gdRender(){
  const E=FHHome.esc, S=FH.get(), box=$("#gd-teams"); if(!box) return;
  const teams=S.teams||[];
  box.innerHTML=teams.length?teams.map((t,i)=>`<div class="srow"><span><i style="display:inline-block;width:14px;height:14px;border-radius:50%;background:${E(t.color)};border:2px solid ${E(t.alt)};vertical-align:-2px;margin-right:8px"></i>${E(t.name)}</span><button class="tool" type="button" data-gdx="${i}" style="margin:0">Remove</button></div>`).join(""):`<div class="hint" style="margin-top:0">No teams yet. Pick a league and a team below.</div>`;
  box.querySelectorAll("[data-gdx]").forEach(b=>b.onclick=()=>{ const t=(FH.get().teams||[]).slice(); t.splice(+b.dataset.gdx,1); FH.save({teams:t}).then(gdRender); });
}
async function gdLights(){
  const E=FHHome.esc, box=$("#gd-lights"); if(!box||box._done) return;
  let h=null; try{ h=await fetch("/api/ha/home").then(r=>r.json()); }catch(e){}
  const lights=((h&&h.groups)||[]).flatMap(g=>g.tiles||[]).filter(t=>t.domain==="light"&&(t.modes||[]).some(m=>/rgb|hs|xy/.test(m)));
  if(!lights.length){ box.innerHTML=`<div class="hint" style="margin:0">No color lights found in Home Assistant.</div>`; return; }
  box._done=true;
  const on=new Set(FH.get().gameLights||[]);
  box.innerHTML=lights.map(t=>`<label class="chk" style="margin:2px 0"><input type="checkbox" value="${E(t.entity_id)}"${on.has(t.entity_id)?" checked":""}> ${E(t.name)}</label>`).join("");
  box.onchange=()=>{ FH.save({gameLights:[...box.querySelectorAll("input:checked")].map(i=>i.value)}); toast("Saved"); };
}
function setupGameDay(){
  gdRender(); gdLights();
  const lg=$("#gd-league"); if(!lg||lg._wired) return; lg._wired=true;
  let list=[];
  const E=FHHome.esc, tm=$("#gd-team");
  let ask=0;
  const load=async()=>{ const mine=++ask; list=[]; tm.innerHTML=`<option value="">Loading…</option>`;
    try{ const r=await fetch("/api/games/teams?league="+encodeURIComponent(lg.value)); if(!r.ok) throw 0; const got=await r.json();
      if(mine!==ask) return;                                   // a newer league was picked meanwhile
      list=got; tm.innerHTML=list.map((t,i)=>`<option value="${i}">${E(t.name)}</option>`).join(""); }
    catch(e){ if(mine===ask){ list=[]; tm.innerHTML=`<option value="">Couldn't load teams</option>`; } } };
  fetch("/api/games/leagues").then(r=>r.json()).then(ls=>{ lg.innerHTML=ls.map(l=>`<option value="${E(l.key)}">${E(l.label)}</option>`).join(""); load(); }).catch(()=>{});
  lg.onchange=load;
  $("#gd-add").onclick=()=>{ if(tm.value==="") return; const t=list[+tm.value]; if(!t) return; const cur=(FH.get().teams||[]).slice();
    if(cur.some(x=>x.league===t.league&&x.id===t.id)){ toast("Already added"); return; }
    cur.push(t); FH.save({teams:cur}).then(()=>{ gdRender(); toast("Added "+t.name); }); };
  $("#gd-test").onclick=async()=>{ const r=await post("/api/games/test",{}).then(r=>r.json()).catch(()=>null);
    $("#gd-msg").textContent=!r?"Couldn't reach FamilyHub.":r.ok?"Sent. The lights go now; the wall cheers within half a minute.":(r.reason||"Didn't work.");
    if(r&&r.ok) setTimeout(async()=>{ const g=await fetch("/api/games").then(r=>r.json()).catch(()=>null), f=(g&&g.flash)||{}, bad=Object.keys(f).filter(k=>String(f[k]).startsWith("failed"));
      if(bad.length) $("#gd-msg").textContent="Home Assistant refused: "+bad.map(k=>k.replace("light.","")+" ("+f[k].slice(8)+")").join(", "); }, 9000); };
}
function loadSettingsUI(){
  setupVoiceHistory();
  { const S=FH.get(), bind=(id,key,fmt)=>{ const el=$(id); if(!el) return;
      if(document.activeElement!==el){ if(el.type==="checkbox") el.checked=S[key]!==false; else el.value=S[key]??""; }   // always show what's saved now
      if(el._wired) return; el._wired=true;
      el.onchange=()=>{ FH.save({[key]: el.type==="checkbox"?el.checked:(fmt?fmt(el.value):el.value)}); toast("Saved"); }; };
    bind("#al-night","nightCheck"); bind("#al-night-t","nightCheckTime"); bind("#al-peak","peakAlerts"); bind("#al-peakdry","peakDryer"); bind("#al-offline","offlineAlert"); bind("#al-gfci","outdoorPowerAlert"); bind("#set-awaykeep","awayKeepRoutineLights"); { const c=$("#set-box2"); if(c){ const S2=FH.get(); if(document.activeElement!==c) c.value=["today","todo","groceries"].includes(S2.sideBox2)?S2.sideBox2:(S2.secondTodo?"todo":"groceries"); if(!c._wired){ c._wired=true; c.onchange=()=>{ FH.save({sideBox2:c.value, secondTodo:c.value==="todo"}); toast("Saved"); }; } } } bind("#al-month","monthlyReport");
    { const show=async prev=>{ const out=$("#al-month-out"); out.textContent="…"; const d=new Date(); if(prev) d.setDate(0);
        const m=d.getFullYear()+"-"+String(d.getMonth()+1).padStart(2,"0");
        try{ const r=await fetch("/api/ha/report?month="+m).then(x=>x.json()); out.textContent=r.name+"\n"+r.lines.join("\n"); }catch(e){ out.textContent="Couldn't load the report."; } };
      const a=$("#al-month-now"), b=$("#al-month-prev"); if(a&&!a._wired){ a._wired=true; a.onclick=()=>show(false); b.onclick=()=>show(true); } } bind("#gd-chip","gameChip"); bind("#gd-speak","gameSpeak"); bind("#gd-plays","gamePlays"); bind("#gd-flash","gameFlash"); bind("#gd-delay","gameDelay",v=>Math.max(0,+v||0)); setupGameDay(); setupTvLights(); setupVillage(); bind("#al-week","weeklySummary"); bind("#al-wx","wxAlerts"); bind("#al-rain","rainCheck"); bind("#al-pkg","packageAlerts"); bind("#al-laundry","laundryAlerts");
    bind("#al-gar","garageAlert"); bind("#al-gar-min","garageOpenMin",v=>+v||15); bind("#al-gar-day","garageOpenDayMin",v=>+v||0); bind("#al-gar-rem","garageRemindMin",v=>+v||30);
    bind("#al-xm-motion","xmasMotion"); bind("#al-xm-min","xmasMotionMin",v=>+v||5); bind("#al-xm-until","xmasMotionUntil"); bind("#al-xm-flash","xmasFlash");
    bind("#al-xm-wind","xmasWind"); bind("#al-xm-gust","windGust",v=>+v||30); bind("#al-xm-off","xmasOffline"); bind("#al-xm-rain","xmasRain"); bind("#al-xm-eve","xmasEveningCheck"); bind("#al-xm-rem","xmasRemindHours",v=>+v||3); bind("#al-xm-rgust","rainGust",v=>+v||20);
    { const sel=$("#al-xm-plug"); if(sel&&!sel._wired){ sel._wired=true;
      fetch("/api/ha/home").then(r=>r.json()).then(h=>{ const cur=FH.get().xmasPlug||"";
        (h.groups||[]).flatMap(g=>g.tiles||[]).filter(t=>/^(switch|light)\./.test(t.entity_id)).sort((a,b)=>a.name.localeCompare(b.name))
          .forEach(t=>{ const o=document.createElement("option"); o.value=t.entity_id; o.textContent=t.name; sel.appendChild(o); });
        sel.value=cur; }).catch(()=>{});
      sel.onchange=()=>{ FH.save({xmasPlug:sel.value}); toast("Saved"); fetch("/api/ha/xmas").then(r=>r.json()).then(x=>{ const el=$("#al-xmas-plug"); if(el) el.textContent=x.plug?` · plug: ${x.name||x.plug}`:""; }).catch(()=>{}); }; } }
    fetch("/api/ha/xmas").then(r=>r.json()).then(x=>{ const el=$("#al-xmas-plug"); if(el) el.textContent=x.plug?` · plug: ${x.name||x.plug}`:" · no Christmas plug found (name it with “Christmas” in Home Assistant)"; }).catch(()=>{});
    const out=$("#al-ld-out"), show=t=>{ out.style.display="block"; out.textContent=t; };
    const lt=$("#al-ld-test"); if(lt&&!lt._wired){ lt._wired=true; lt.onclick=async()=>{ show("Sending…");
      let r={}; try{ r=await post("/api/ha/laundry/test",{}).then(x=>x.json()); }catch(e){ r={error:"Couldn't reach FamilyHub"}; }
      show(r.ok?`Sent to: ${r.to.join(", ")}. Check your phones.`:`Didn't send: ${r.error||"unknown"}${(r.to||[]).length?"\nTried: "+r.to.join(", "):""}`); }; }
    const ll=$("#al-ld-log"); if(ll&&!ll._wired){ ll._wired=true; ll.onclick=async()=>{
      let r={}; try{ r=await fetch("/api/ha/laundry").then(x=>x.json()); }catch(e){}
      const seen=(r.seen||[]).map(x=>`${x.at}  ${x.entity.replace(/^(sensor|binary_sensor)\./,"")}: ${x.from} → ${x.to}`).join("\n")||"(nothing yet since FamilyHub last restarted)";
      const sent=(r.sent||[]).map(x=>`${x.at}  ${x.text}${x.quiet?" (silent)":""} → ${x.to.length?x.to.join(", "):"no phones"}${x.error?"  ⚠ "+x.error:""}`).join("\n")||"(none)";
      show(`Live link to Home Assistant: ${r.live?"yes":"NO, changes are only seen every 30 s or not at all"}\n\nWasher/dryer changes seen:\n${seen}\n\nMessages sent:\n${sent}`); }; }
    bind("#al-batt","batteryLow",v=>Math.max(5,Math.min(60,+v||25)));
    const t=$("#al-night-test"); if(t&&!t._wired){ t._wired=true; t.onclick=async()=>{ let r={}; try{ r=await fetch("/api/ha/night-check").then(x=>x.json()); }catch(e){}
      toast((r.issues||[]).length?"Right now: "+r.issues.join("; "):"All buttoned up ✓"); }; } }
  { const nc=$("#set-nocode"); if(nc){ nc.checked=FH.get().welcomeNoCode===true; nc.onchange=e=>{ FH.save({welcomeNoCode:e.target.checked});
      toast(e.target.checked?"I'm home will disarm with one tap":"I'm home will ask for the code"); if(window.FHAutomations&&$("#hm-modes")) FHAutomations.houseModes($("#hm-modes")); }; } }
  { const hb=$("#hm-modes"); if(hb && window.FHAutomations && !hb._wired){ hb._wired=true; const d=hb.closest("details");
      const go=()=>FHAutomations.houseModes(hb); if(d) d.addEventListener("toggle",()=>{ if(d.open) go(); }); go(); } }
  const s=FH.get();
  // theme pill
  document.querySelectorAll("#set-theme button").forEach(b=>{
    b.classList.toggle("active", b.dataset.v===s.theme);
    b.onclick=()=>{ FH.save({theme:b.dataset.v}); loadSettingsUI(); };
  });
  buildAccent(); buildPersonColors();
  $("#set-font").value=s.font; $("#set-font").onchange=e=>FH.save({font:e.target.value});
  $("#set-density").value=s.density; $("#set-density").onchange=e=>FH.save({density:e.target.value});
  $("#set-textsize").value=s.textSize||"normal"; $("#set-textsize").onchange=e=>FH.save({textSize:e.target.value});
  // panels
  document.querySelectorAll("#view-settings input[data-panel]").forEach(c=>{
    c.checked=!!(s.panels||{})[c.dataset.panel];
    c.onchange=()=>saveNested("panels",c.dataset.panel,c.checked);
  });
  $("#set-kbd").checked=!!s.onscreenKbd; $("#set-kbd").onchange=e=>FH.save({onscreenKbd:e.target.checked});
  $("#set-slideafter").value=String(s.slideshowAfter??5); $("#set-slideafter").onchange=e=>{ FH.save({slideshowAfter:+e.target.value}); toast(+e.target.value?"Slideshow after "+e.target.selectedOptions[0].text:"Slideshow off"); };
  $("#set-slidesecs").value=String(s.slideSeconds??8); $("#set-slidesecs").onchange=e=>{ FH.save({slideSeconds:+e.target.value}); toast("Saved"); };
  $("#set-photofit").checked=(s.photoFit||"fit")==="fit"; $("#set-photofit").onchange=e=>FH.save({photoFit:e.target.checked?"fit":"fill"});
  $("#set-speak").checked=s.speakAlerts!==false; $("#set-speak").onchange=e=>FH.save({speakAlerts:e.target.checked});
  $("#set-who").value=whoAmI(); $("#set-who").onchange=e=>{ try{ localStorage.setItem("fh_who", e.target.value.trim()); }catch(_){} toast("Saved on this phone"); };
  $("#set-announce-adds").checked=s.announceAdds!==false; $("#set-announce-adds").onchange=e=>FH.save({announceAdds:e.target.checked});
  const q=$("#set-announce-quiet"); q.value = s.announceQuietStart==="" ? "never" : (s.announceQuietStart==="20:00" ? "evening" : "night");
  q.onchange=e=>{ const v=e.target.value; FH.save(v==="never"?{announceQuietStart:"",announceQuietEnd:""}: v==="evening"?{announceQuietStart:"20:00",announceQuietEnd:"07:00"}:{announceQuietStart:null,announceQuietEnd:null}); };
  $("#set-push-adds").checked=s.pushAdds!==false; $("#set-push-adds").onchange=e=>FH.save({pushAdds:e.target.checked});
  $("#set-doorbell-speak").checked=s.doorbellSpeak!==false; $("#set-doorbell-speak").onchange=e=>FH.save({doorbellSpeak:e.target.checked});
  $("#set-doorbell-tv").checked=s.doorbellTv!==false; $("#set-doorbell-tv").onchange=e=>FH.save({doorbellTv:e.target.checked});
  $("#set-doorbell-test").onclick=async()=>{ try{ await post("/api/ha/doorbell/test",{}); toast("Ring sent — watch the wall, phones and TVs"); }catch(e){ toast("Couldn't reach the wall"); } };
  $("#set-brief").checked=s.morningBriefing!==false; $("#set-brief").onchange=e=>FH.save({morningBriefing:e.target.checked});
  $("#set-briefhour").value=String(s.briefingHour||6); $("#set-briefhour").onchange=e=>FH.save({briefingHour:+e.target.value});
  { const r=$("#set-spvol"), v=$("#set-spvol-v"); if(r){ r.value=s.spotifyStartVolume??45; v.textContent=r.value+"%";
    r.oninput=()=>{ v.textContent=r.value+"%"; }; r.onchange=()=>{ FH.save({spotifyStartVolume:Number(r.value)}); toast("Spotify will start at "+r.value+"%"); }; } }
  loadWake(s);
  $("#set-aname").value=s.assistantName||"Hub"; $("#set-aname").onchange=e=>{ const v=e.target.value.trim().slice(0,30)||"Hub"; FH.save({assistantName:v}); toast(`It'll answer to "${v}"`); };
  // holidays
  document.querySelectorAll("#view-settings input[data-hol]").forEach(c=>{
    c.checked=!!(s.holidays||{})[c.dataset.hol];
    c.onchange=()=>saveNested("holidays",c.dataset.hol,c.checked);
  });
  // effects
  $("#set-skin-slim").checked=s.skinSlim!==false; $("#set-skin-slim").onchange=e=>FH.save({skinSlim:e.target.checked});
  $("#set-skin-art").checked=s.skinArt!==false; $("#set-skin-art").onchange=e=>FH.save({skinArt:e.target.checked});
  if(window.Skins&&!$("#set-skin-previews").children.length) Skins.list().forEach(k=>{ const a=document.createElement("a"); a.className="tool"; a.href="/?skin="+k.key; a.target=document.body.classList.contains("embed")?"_top":"_blank"; a.style.cssText="text-align:center; text-decoration:none"; a.textContent="👀 "+k.emoji+" "+k.name; $("#set-skin-previews").appendChild(a); });
  $("#set-skin-banner").checked=s.skinBanner!==false; $("#set-skin-banner").onchange=e=>FH.save({skinBanner:e.target.checked});
  $("#set-home").value=s.homeAddress||""; $("#set-home").onchange=e=>FH.save({homeAddress:e.target.value.trim()});
  $("#set-leavebuf").value=s.leaveBuffer??5; $("#set-leavebuf").onchange=e=>FH.save({leaveBuffer:Math.max(0,Math.min(30,parseInt(e.target.value,10)||0))});
  $("#set-leave").checked=s.leaveAlerts!==false; $("#set-leave").onchange=e=>FH.save({leaveAlerts:e.target.checked});
  $("#set-sleeparm").checked=s.sleepOnNightArm!==false; $("#set-sleeparm").onchange=e=>FH.save({sleepOnNightArm:e.target.checked});
  $("#set-caltasks").checked=s.calendarTasks!==false; $("#set-caltasks").onchange=e=>FH.save({calendarTasks:e.target.checked});
  if(window.Skins&&$("#set-skin").options.length<=2) Skins.list().forEach(k=>{ const o=document.createElement("option"); o.value=k.key; o.textContent=k.emoji+" "+k.name; $("#set-skin").appendChild(o); });
  $("#set-skin").value=s.skin||"auto"; $("#set-skin").onchange=e=>{ FH.save({skin:e.target.value}); toast("Wall updated"); };
  $("#set-effects").checked=!!s.effects; $("#set-effects").onchange=e=>FH.save({effects:e.target.checked});
  $("#set-weatherfx").checked=s.weatherFx!==false; $("#set-weatherfx").onchange=e=>FH.save({weatherFx:e.target.checked});
  document.querySelectorAll("#view-settings input[data-eff]").forEach(c=>{
    c.checked=!!(s.effectPrefs||{})[c.dataset.eff];
    c.onchange=()=>saveNested("effectPrefs",c.dataset.eff,c.checked);
  });
}

/* night screen-off (shared endpoint with the wall) */
let dispCfg=null;
async function loadDispCfg(){
  try{ dispCfg=await fetch("/api/display/config").then(r=>r.json()); }catch(e){ dispCfg=null; return; }
  $("#disp-enabled").checked=!!dispCfg.enabled;
  $("#disp-start").value=dispCfg.off_start||"22:00";
  $("#disp-end").value=dispCfg.off_end||"06:30";
}
function saveDisp(){
  const patch={enabled:$("#disp-enabled").checked, off_start:$("#disp-start").value, off_end:$("#disp-end").value};
  fetch("/api/display/config",{method:"PUT",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({...(dispCfg||{}),...patch})}).then(r=>r.json()).then(c=>{dispCfg=c;}).catch(()=>{});
}
["disp-enabled","disp-start","disp-end"].forEach(id=>{ const el=$("#"+id); if(el) el.onchange=saveDisp; });

/* family members */
function loadTodoLists(){
  const box=$("#tl-list"); if(!box) return; const esc=FHHome.esc, L=FH.get().todoLists||[];
  box.innerHTML=`<div class="srow" style="padding:6px 0"><span>📝 <b>To-Do</b> <span style="color:var(--ink-dim)">(main list)</span></span></div>`+
    L.map((n,i)=>`<div class="srow" style="padding:6px 0"><span>📝 <b>${esc(n)}</b></span><span style="display:flex; gap:6px">
      <button class="tl-mv" data-i="${i}" style="border:0; background:var(--panel2); color:var(--ink); border-radius:9px; padding:7px 10px">↑</button>
      <button class="tl-rm" data-i="${i}" style="border:0; background:var(--panel2); color:#e5534b; border-radius:9px; padding:7px 11px; font:inherit; font-size:13px; font-weight:600">Remove</button></span></div>`).join("");
  box.querySelectorAll(".tl-rm").forEach(b=>b.onclick=()=>{ const n=L[+b.dataset.i];
    if(!confirm(`Remove the "${n}" list? Its to-dos move to the main To-Do list.`)) return;
    fetch("/api/todos/").then(r=>r.json()).then(all=>Promise.all(all.filter(t=>t.list_name===n).map(t=>fetch("/api/todos/"+t.id+"/list",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({list_name:null})})))).catch(()=>{});
    FH.save({todoLists:L.filter((_,i)=>i!==+b.dataset.i)}); loadTodoLists(); });
  box.querySelectorAll(".tl-mv").forEach(b=>b.onclick=()=>{ const i=+b.dataset.i; if(!i) return; const m=L.slice(); [m[i-1],m[i]]=[m[i],m[i-1]]; FH.save({todoLists:m}); loadTodoLists(); });
  const add=$("#tl-add"); if(add&&!add._wired){ add._wired=true; add.onclick=()=>{ const n=$("#tl-name").value.trim().slice(0,40);
    if(!n) return; if(/^to-?\s?do$/i.test(n)||(FH.get().todoLists||[]).includes(n)){ toast("You already have that list"); return; }
    FH.save({todoLists:[...(FH.get().todoLists||[]), n]}); $("#tl-name").value=""; toast("📝 Added "+n); loadTodoLists(); }; }
}
function loadBdays(){
  const box=$("#bday-list"); if(!box) return; const esc=FHHome.esc;
  const list=(FH.get().birthdays||[]).slice().sort((a,b)=>String(a.date).slice(-5).localeCompare(String(b.date).slice(-5)));
  const md=d=>{ const p=String(d).slice(-5).split("-"); return new Date(2000,+p[0]-1,+p[1]).toLocaleDateString([], {month:"long", day:"numeric"}); };
  const age=d=>{ if(String(d).length<10) return ""; const y=+String(d).slice(0,4), now=new Date(), mmdd=String(d).slice(5);
    let a=now.getFullYear()-y; const today=String(now.getMonth()+1).padStart(2,"0")+"-"+String(now.getDate()).padStart(2,"0"); if(today<mmdd) a++; return ` · turns ${a}`; };
  box.innerHTML=list.length?list.map((b,i)=>`<div class="srow" style="padding:6px 0"><span>🎂 <b>${esc(b.name)}</b> <span style="color:var(--ink-dim)">${md(b.date)}${age(b.date)}</span></span><button style="border:0; background:var(--panel2); color:#e5534b; border-radius:9px; padding:7px 11px; font:inherit; font-size:13px; font-weight:600" data-bd="${esc(b.name)}|${esc(b.date)}">Remove</button></div>`).join(""):'<div class="hint">None yet.</div>';
  box.querySelectorAll("[data-bd]").forEach(btn=>btn.onclick=()=>{ const [n,d]=btn.dataset.bd.split("|");
    FH.save({birthdays:(FH.get().birthdays||[]).filter(b=>!(b.name===n&&b.date===d))}); loadBdays(); });
  const add=$("#bday-add"); if(add&&!add._wired){ add._wired=true; add.onclick=()=>{
    const name=$("#bday-name").value.trim(), date=$("#bday-date").value;
    if(!name||!date){ toast("Add a name and a date"); return; }
    FH.save({birthdays:[...(FH.get().birthdays||[]), {name, date}]}); $("#bday-name").value=""; $("#bday-date").value=""; toast("🎂 Added "+name); loadBdays(); }; }
}
async function loadPeople(){
  loadBdays(); loadTodoLists();
  let list=[];
  try{ list=await fetch("/api/categories/people").then(r=>r.json()); }catch(e){}
  people=list;
  // anything that offers a person picker must follow the live list
  try{ renderForm(); }catch(e){}
  try{ if($("#src-form")) renderSrcForm(); }catch(e){}
  const box=$("#people-list"); box.innerHTML="";
  if(!list.length){ box.innerHTML='<div class="sub" style="margin:0">No people yet — add your family below.</div>'; return; }
  list.forEach(p=>{
    const row=document.createElement("div"); row.className="prow";
    row.innerHTML=`<div class="pav" style="background:${p.color}">${(p.name||"?").slice(0,1).toUpperCase()}</div>`+
      `<div class="pname">${p.name}${p.birthday?`<div class="hint" style="margin:0">🎂 ${fmtBday(p.birthday)}${bdayAge(p.birthday)}</div>`:''}</div>`+
      `<button data-act="bday" title="Birthday">🎂</button><button data-act="edit">Edit</button><button class="del" data-act="del">Delete</button>`;
    row.querySelector('[data-act="edit"]').onclick=()=>renamePerson(p);
    row.querySelector('[data-act="bday"]').onclick=()=>setBirthday(p);
    row.querySelector('[data-act="del"]').onclick=()=>deletePerson(p);
    box.appendChild(row);
  });
}
function fmtBday(b){ const m=String(b||"").match(/(\d{2})-(\d{2})$/); if(!m) return b; return new Date(2000,+m[1]-1,+m[2]).toLocaleDateString([],{month:"long",day:"numeric"}); }
function bdayAge(b){ b=String(b||""); if(!/^\d{4}-\d{2}-\d{2}$/.test(b)) return "";
  const now=new Date(), t=String(now.getMonth()+1).padStart(2,"0")+"-"+String(now.getDate()).padStart(2,"0");
  const a=now.getFullYear()-(+b.slice(0,4))-(t<b.slice(5)?1:0); return ` · ${a}`; }
function setBirthday(p){
  // a real date picker (with the year) in a small sheet; the year is optional-free: picker always has one
  const old=document.getElementById("bd-sheet"); if(old) old.remove();
  const cur=String(p.birthday||""), val=/^\d{4}-\d{2}-\d{2}$/.test(cur)?cur:"";
  const ov=document.createElement("div"); ov.id="bd-sheet";
  ov.style.cssText="position:fixed; inset:0; z-index:200; background:rgba(0,0,0,.5); display:flex; align-items:flex-end; justify-content:center";
  ov.innerHTML=`<div style="background:var(--panel); color:var(--ink); width:100%; max-width:520px; border-radius:20px 20px 0 0; padding:18px 16px calc(18px + env(safe-area-inset-bottom))">
    <b style="font-size:17px">🎂 ${FHHome.esc(p.name)}'s birthday</b>
    <div class="hint" style="margin:4px 0 10px">${cur&&!val?"Saved as "+fmtBday(cur)+" (no year). Pick the full date to add the year.":"The wall turns into a party that day."}</div>
    <input type="date" id="bd-in" value="${val}" style="width:100%; font-size:16px">
    <div style="display:flex; gap:8px; margin-top:12px">
      ${cur?'<button id="bd-clear" style="flex:1; border:0; border-radius:12px; padding:12px; background:var(--panel2); color:#e5534b; font:inherit; font-weight:700">Clear</button>':''}
      <button id="bd-cancel" style="flex:1; border:0; border-radius:12px; padding:12px; background:var(--panel2); color:var(--ink); font:inherit; font-weight:700">Cancel</button>
      <button id="bd-save" class="go" style="flex:2; margin:0">Save</button></div></div>`;
  document.body.appendChild(ov);
  const save=async v=>{ await fetch("/api/categories/people/"+p.id,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:p.name,color:p.color,birthday:v||null})}).catch(()=>{});
    ov.remove(); toast(v?"Birthday saved":"Birthday cleared"); loadPeople(); };
  ov.onclick=e=>{ if(e.target===ov) ov.remove(); };
  ov.querySelector("#bd-cancel").onclick=()=>ov.remove();
  const c=ov.querySelector("#bd-clear"); if(c) c.onclick=()=>save(null);
  ov.querySelector("#bd-save").onclick=()=>{ const v=ov.querySelector("#bd-in").value; if(!v){ toast("Pick a date"); return; } save(v); };
}
async function renamePerson(p){
  const name=prompt("Rename person:", p.name); if(name===null) return;
  const nm=name.trim(); if(!nm) return;
  await fetch("/api/categories/people/"+p.id,{method:"PUT",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({name:nm,color:p.color,birthday:p.birthday||null})}).catch(()=>{});
  toast("Saved"); loadPeople();
}
async function deletePerson(p){
  if(!confirm(`Remove ${p.name}? Their items become unassigned.`)) return;
  await fetch("/api/categories/people/"+p.id,{method:"DELETE"}).catch(()=>{});
  toast("Removed"); loadPeople();
}
$("#person-add").onclick=async()=>{
  const name=$("#person-name").value.trim(); if(!name){ toast("Enter a name"); return; }
  await fetch("/api/categories/people",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({name,color:personColor})}).catch(()=>{});
  $("#person-name").value=""; toast("Person added"); loadPeople();
};

/* ---- intercom ---- */
async function announce(text){
  text=(text||"").trim(); if(!text){ toast("Type something to say"); return; }
  const who=$("#ann-who").value.trim(); try{ localStorage.setItem("fh_ann_who", who); }catch(e){}
  const r=await post("/api/announce",{text, who:who||null});
  toast(r.ok?"The wall will say it now":"Couldn't reach the wall");
  $("#ann-text").value="";
}
$("#ann-go").onclick=()=>announce($("#ann-text").value);
$("#ann-text").addEventListener("keydown",e=>{ if(e.key==="Enter") announce($("#ann-text").value); });
document.querySelectorAll("[data-ann]").forEach(b=>{ b.onclick=()=>announce(b.dataset.ann); });
try{ $("#ann-who").value=localStorage.getItem("fh_ann_who")||""; }catch(e){}

/* ---- meal planner ---- */
let mealPlan=[];
$("#mp-go").onclick=async()=>{
  const btn=$("#mp-go"); btn.disabled=true; btn.textContent="Planning…";
  const box=$("#mp-preview"); box.classList.remove("show");
  try{
    const r=await post("/api/ai/meal-plan",{days:+$("#mp-days").value, prefs:$("#mp-prefs").value}).then(r=>r.json());
    mealPlan=r.meals||[];
    if(!mealPlan.length){ toast(r.skipped&&r.skipped.length?"Those days already have dinners":"Nothing planned"); }
    else{
      box.innerHTML=`<div class="pk">${r.source==="ai"?"Suggested by AI":"Suggested"} — untick any you don't want</div>`+mealPlan.map((m,i)=>{
        const d=new Date(m.date+"T12:00:00");
        return `<label class="chk" style="margin:6px 0;align-items:flex-start"><input type="checkbox" data-i="${i}" checked> <span><b>${d.toLocaleDateString([],{weekday:"short"})}</b> ${m.title}${m.minutes?` <span class="sub" style="display:inline;font-size:12px">· ${m.minutes} min</span>`:""}<div class="sub" style="margin:0;font-size:12px">${(m.ingredients||[]).join(", ")}</div></span></label>`; }).join("")+
        `<label class="chk" style="margin:10px 0 6px"><input type="checkbox" id="mp-groc" checked> Add ingredients to Groceries</label><button class="go" id="mp-apply" style="margin:0">Add to the meal plan</button>`;
      box.classList.add("show");
      $("#mp-apply").onclick=async()=>{
        const chosen=[...box.querySelectorAll("input[data-i]")].filter(c=>c.checked).map(c=>mealPlan[+c.dataset.i]);
        if(!chosen.length){ toast("Nothing ticked"); return; }
        const res=await post("/api/ai/meal-plan/apply",{meals:chosen, add_groceries:$("#mp-groc").checked}).then(r=>r.json()).catch(()=>({}));
        toast(`Added ${res.meals||0} dinner${res.meals===1?"":"s"}${res.groceries?` + ${res.groceries.length} groceries`:""}`); box.classList.remove("show"); };
    }
  }catch(e){ toast("Couldn't plan — try again"); }
  btn.disabled=false; btn.textContent="Plan it";
};

/* ---- calendars (sources) ---- */
let srcKind="caldav";
function renderSrcForm(){
  const f=$("#src-form");
  if(srcKind==="caldav"){
    f.innerHTML=`<input id="s_label" placeholder="Name (e.g. Mom's iCloud)">
      <input id="s_user" placeholder="Apple ID email" autocapitalize="none">
      <input id="s_pass" type="password" placeholder="App-specific password">
      <select id="s_person">${peopleOptions()}</select>
      <label class="chk"><input type="checkbox" id="s_rem" checked> Also sync <b>Reminders</b> into the To-Do list (two-way)</label>
      <div class="hint">appleid.apple.com → Sign-In and Security → App-Specific Passwords → generate one for "FamilyHub". Your real Apple password is never used.</div>
      <div class="two"><button class="go" onclick="testCaldav()" style="background:var(--panel2);color:var(--ink)">Test login</button><button class="go" onclick="addSource()">Connect iCloud</button></div>
      <div class="preview" id="s_test"></div>`;
  } else if(srcKind==="ics"){
    f.innerHTML=`<input id="s_label" placeholder="Name (e.g. Work Outlook, School, Trash day)">
      <input id="s_url" placeholder="https://… .ics or webcal:// link" autocapitalize="none">
      <select id="s_person">${peopleOptions()}</select>
      <div class="hint"><b>Outlook / Office 365:</b> Outlook web → Settings → Calendar → Shared calendars → Publish a calendar → copy the <b>ICS</b> link.<br><b>Google (read-only, no OAuth):</b> calendar settings → "Secret address in iCal format".<br>Also sports schedules, school districts, TeamSnap, trash pickup, tee times.</div>
      <button class="go" onclick="addSource()">Subscribe</button>`;
  } else {
    f.innerHTML=`<input id="s_label" placeholder="Name (e.g. Dad's Google)">
      <select id="s_person">${peopleOptions()}</select>
      <div class="hint">Two-way Google needs a one-time OAuth setup on a computer: drop <code>credentials.json</code> in the FamilyHub folder, run the auth flow once, copy <code>token.json</code> next to it (README → Connect calendars). Then tap Connect here. For read-only with zero setup, use the ICS tab with your Google "secret address" instead.</div>
      <button class="go" onclick="addSource()">Connect Google</button>`;
  }
}
document.querySelectorAll("#src-kind button").forEach(b=>{ b.onclick=()=>{ document.querySelectorAll("#src-kind button").forEach(x=>x.classList.remove("active")); b.classList.add("active"); srcKind=b.dataset.v; renderSrcForm(); }; });
function fmtAgo(iso){ const s=Math.round((Date.now()-new Date(iso))/1000); return s<60?`${s}s ago`:s<3600?`${Math.round(s/60)} min ago`:`${Math.round(s/3600)} h ago`; }
async function loadSyncStatus(){
  const el=$("#src-status"); if(!el) return;
  try{ const st=(await fetch("/api/sources/status").then(r=>r.json())).status||{};
    const lines=Object.entries(st).map(([k,v])=>`${k.startsWith("rem:")?"Reminders":"Calendar"} · ${v.label||""}: ${v.ok?`${v.count} items, ${fmtAgo(v.at)}`:`ERROR ${v.error} (${fmtAgo(v.at)})`}`);
    el.textContent=lines.length?lines.join("\n"):"No sync yet — calendars fetch when the wall refreshes (every 60 s), Reminders every 5 min.";
    el.style.color=Object.values(st).some(v=>!v.ok)?"#e0533d":"";
  }catch(e){ el.textContent="—"; }
}
$("#src-sync").onclick=async()=>{ const b=$("#src-sync"); b.disabled=true; b.textContent="Syncing…";
  try{ const r=await post("/api/sources/sync",{}).then(r=>r.json()); toast(`${r.events} events · ${(r.reminders&&r.reminders.pulled)||0} new reminders`); }catch(e){ toast("Sync failed"); }
  b.disabled=false; b.textContent="Sync now"; loadSyncStatus(); };
async function loadSources(){
  try{ people=await fetch("/api/categories/people").then(r=>r.json()); }catch(e){}
  renderSrcForm(); loadSyncStatus();
  const box=$("#src-list"); box.innerHTML="";
  let list=[]; try{ list=await fetch("/api/sources/").then(r=>r.json()); }catch(e){}
  if(!list.length){ box.innerHTML='<div class="sub" style="margin:0">No calendars connected yet — the wall shows only events added here until you connect one.</div>'; return; }
  const ico={caldav:"🍎",google:"🟢",ics:"🔗"};
  list.forEach(sr=>{
    const row=document.createElement("div"); row.className="prow";
    const who=people.find(p=>p.id===sr.person_id);
    row.innerHTML=`<div class="pav" style="background:${who?who.color:'#9aa0a6'}">${ico[sr.kind]||"📅"}</div><div class="pname">${sr.label}<div class="sub" style="margin:0;font-size:12px">${sr.kind==="caldav"?"iCloud":sr.kind==="ics"?"ICS feed":"Google"}${who?" · "+who.name:""}</div></div><button class="del" data-act="del">Remove</button>`;
    row.querySelector('[data-act="del"]').onclick=async()=>{ if(!confirm(`Remove ${sr.label}?`)) return; await fetch("/api/sources/"+sr.id,{method:"DELETE"}).catch(()=>{}); loadSources(); };
    box.appendChild(row);
  });
}
async function testCaldav(){
  const username=$("#s_user").value.trim(), password=$("#s_pass").value;
  if(!username||!password){ toast("Enter the Apple ID + app password first"); return; }
  const box=$("#s_test"); box.innerHTML='<div class="pk">Testing against Apple…</div>'; box.classList.add("show");
  try{
    const r=await post("/api/sources/caldav/test",{username,password}).then(r=>r.json());
    box.innerHTML=`<div class="pk">${r.verdict}</div><div class="sub" style="margin:2px 0 6px;font-size:12px">user: ${r.username_used} · password length: ${r.password_length} (Apple's are 16 letters + 3 dashes = 19)</div>`+
      r.results.map(x=>`<div class="pi" style="font-family:ui-monospace,monospace;font-size:12px">${x.variant} ${x.path}: ${x.ok?"OK":("HTTP "+(x.status||"?")+" "+(x.reason||x.error||""))}${x.www_authenticate?" · "+x.www_authenticate:""}${x.location?" → "+x.location:""}</div>`).join("");
  }catch(e){ box.innerHTML='<div class="pk">Test failed to run</div>'; }
}
async function addSource(){
  const label=($("#s_label").value||"").trim(); if(!label){ toast("Give it a name"); return; }
  const person_id=num($("#s_person").value);
  let r;
  if(srcKind==="caldav"){
    const username=$("#s_user").value.trim(), password=$("#s_pass").value;
    if(!username||!password){ toast("Apple ID + app password needed"); return; }
    r=await post("/api/sources/caldav",{label,username,password,person_id,sync_reminders:$("#s_rem").checked});
  } else if(srcKind==="ics"){
    let url=$("#s_url").value.trim().replace(/^webcal:\/\//i,"https://"); if(!url){ toast("Paste the link"); return; }
    r=await post("/api/sources/ics",{label,url,person_id});
  } else {
    r=await post("/api/sources/google",{label,person_id});
  }
  if(!r||!r.ok){ toast("Couldn't connect"); return; }
  toast("Connected — events appear on the wall within a minute"); loadSources(); fetch("/api/sources/targets?refresh=1").then(()=>loadCalTargets()).catch(()=>{});
}

/* ---- photos: upload + shared album ---- */
async function loadPhotosUI(){
  $("#album-url").value=FH.get().icloudAlbumUrl||"";
  try{ const r=await fetch("/api/photos/").then(r=>r.json());
    $("#ph-count").textContent=`${r.local||0} uploaded · ${r.album||0} from the shared album`; }catch(e){}
}
$("#ph-upload").onclick=()=>$("#ph-files").click();
$("#ph-files").onchange=async()=>{
  const files=[...$("#ph-files").files]; if(!files.length) return;
  const fd=new FormData(); files.forEach(f=>fd.append("files",f,f.name));
  $("#ph-upload").disabled=true; $("#ph-upload").textContent=`Uploading ${files.length}…`;
  try{ const r=await fetch("/api/photos/upload",{method:"POST",body:fd}); const j=await r.json();
    if(!r.ok) throw new Error(j.detail||"upload failed");
    toast(`Added ${j.saved.length} photo${j.saved.length>1?"s":""} to the wall`); }
  catch(e){ toast(e.message||"Upload failed"); }
  $("#ph-upload").disabled=false; $("#ph-upload").textContent="📷 Upload photos to the wall"; $("#ph-files").value=""; loadPhotosUI();
};
$("#album-save").onclick=async()=>{
  const url=$("#album-url").value.trim();
  if(url && !/icloud\.com\/sharedalbum\/#/.test(url)){ toast("That isn't an iCloud shared-album link"); return; }
  await FH.save({icloudAlbumUrl:url});
  try{ const r=await fetch("/api/photos/album/refresh",{method:"POST"}).then(r=>r.json());
    toast(url ? (r.album ? `Album linked — ${r.album} photos` : "Linked, but no photos came back yet (is Public Website on?)") : "Shared album removed"); }
  catch(e){ toast("Saved"); }
  loadPhotosUI();
};

/* ---- email import inbox ---- */
async function loadMail(){
  const box=$("#mail-box"); box.innerHTML="";
  let st={configured:false}; try{ st=await fetch("/api/mail/status").then(r=>r.json()); }catch(e){}
  if(!st.configured){
    box.innerHTML='<div class="sub" style="margin:0">Not set up. Give FamilyHub a mailbox (a free Gmail + app password) in <code>.env</code> — <code>FAMILYHUB_MAIL_HOST / USER / PASS</code> — then forward school emails, schedules and invites to it. Events show up here to approve.</div>';
    return;
  }
  let pend=[]; try{ pend=(await fetch("/api/mail/pending").then(r=>r.json())).pending||[]; }catch(e){}
  const top=document.createElement("div"); top.className="srow";
  top.innerHTML=`<span>${pend.length?pend.length+" waiting":"Nothing waiting"}</span><button class="go" id="mail-poll" style="width:auto;margin:0;padding:8px 14px">Check now</button>`;
  box.appendChild(top);
  top.querySelector("#mail-poll").onclick=async()=>{ toast("Checking…"); try{ const r=await fetch("/api/mail/poll",{method:"POST"}).then(r=>r.json()); toast(r.error?("Mail error: "+r.error):`Checked — ${r.processed||0} new`); }catch(e){ toast("Couldn't check"); } loadMail(); };
  pend.forEach(m=>{
    const card=document.createElement("div"); card.className="preview show"; card.style.marginTop="10px";
    const evs=m.events.map((e,i)=>{ const d=e.start?new Date(e.start):null;
      const when=d&&!isNaN(d)?(e.all_day?d.toLocaleDateString([],{weekday:"short",month:"short",day:"numeric"}):d.toLocaleString([],{weekday:"short",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})):(e.start||"");
      return `<label class="chk" style="margin:4px 0"><input type="checkbox" data-i="${i}" checked> ${e.title}<span class="sub" style="display:inline;margin-left:6px;font-size:12px">${when}</span></label>`; }).join("");
    card.innerHTML=`<div class="pk">${m.subject}</div><div class="sub" style="margin:2px 0 6px;font-size:12px">${(m.sender||"").replace(/<.*>/,"").trim()}</div>${evs}
      <div class="two" style="margin-top:8px"><button class="go" data-act="ok" style="margin:0">Add to calendar</button><button class="go" data-act="no" style="margin:0;background:var(--panel2);color:var(--ink)">Dismiss</button></div>`;
    card.querySelector('[data-act="ok"]').onclick=async()=>{
      const indexes=[...card.querySelectorAll("input[data-i]")].filter(c=>c.checked).map(c=>+c.dataset.i);
      if(!indexes.length){ toast("Nothing ticked"); return; }
      const r=await post(`/api/mail/${m.id}/approve`,{indexes}).then(r=>r.json()).catch(()=>({}));
      toast(`Added ${r.created||0} event${r.created===1?"":"s"}`); loadMail(); };
    card.querySelector('[data-act="no"]').onclick=async()=>{ await post(`/api/mail/${m.id}/dismiss`,{}).catch(()=>{}); loadMail(); };
    box.appendChild(card);
  });
}

/* FamilyHub's own Spotify link (wall = official Spotify device) */
async function loadSPW(){
  const st=$("#spw-status"); let s=null;
  try{ s=await fetch("/api/spotify/status").then(r=>r.json()); }catch(e){ st.textContent="Couldn't reach the wall."; return; }
  $("#spw-connect").hidden=!(s.configured&&!s.linked); $("#spw-linked").hidden=!s.linked;
  if(!s.configured){ st.innerHTML="Add <b>SPOTIFY_CLIENT_ID</b> and <b>SPOTIFY_CLIENT_SECRET</b> to the wall's .env (same values you gave Home Assistant), restart FamilyHub, then come back here."; return; }
  if(!s.linked){ st.textContent="Not connected yet. Needs Spotify Premium."; return; }
  st.innerHTML=`Connected as <b>${s.user||"Spotify"}</b>${s.product&&s.product!=="premium"?' <span style="color:#d33">(not Premium — playback won\'t start)</span>':''}. Wall speaker "${s.wall_device_name||"FamilyHub"}": <b>${s.wall_online?"online":"not seen yet (reload the wall)"}</b>.`;
  if(!s.wall_online){
    try{ const l=await fetch("/api/spotify/player_log").then(r=>r.json());
      if(l.log&&l.log.length){ st.innerHTML+=`<div style="margin-top:6px;font-family:ui-monospace,monospace;font-size:12px;white-space:pre-line">Wall player log:\n${l.log.slice(-6).map(x=>`${x.t} ${x.stage}: ${x.detail}`).join("\n")}</div>`; }
      else st.innerHTML+=`<div style="margin-top:6px">The wall hasn't reported anything yet — tap Reload the wall below, wait 30 s, refresh.</div>`;
    }catch(e){}
  }
}
$("#spw-login").onclick=async()=>{
  try{ const r=await fetch("/api/spotify/login").then(r=>r.json()); if(r.url){ window.open(r.url,"_blank"); toast("Approve in Spotify, then paste the address it lands on"); } else toast(r.detail||"Couldn't start login"); }
  catch(e){ toast("Couldn't start login"); }
};
$("#spw-finish").onclick=async()=>{
  const text=$("#spw-code").value.trim(); if(!text){ toast("Paste the address first"); return; }
  const r=await post("/api/spotify/code",{text}); const j=await r.json().catch(()=>({}));
  if(r.ok){ toast("Spotify connected"+(j.user?" as "+j.user:"")); $("#spw-code").value=""; fetch("/api/display/reload",{method:"POST"}); loadSPW(); }
  else toast(j.detail||"Spotify rejected it");
};
$("#spw-test").onclick=async()=>{ const r=await post("/api/spotify/cmd",{action:"say", value:"play something"}); const j=await r.json().catch(()=>({})); toast(j.say||j.detail||"sent"); };
$("#spw-unlink").onclick=async()=>{ if(!confirm("Unlink Spotify from the wall?")) return; await post("/api/spotify/unlink",{}); loadSPW(); };

/* Spotify playlist pins (stored in settings.spotifyPlaylists) */
function spotifyUri(s){
  s=(s||"").trim();
  let m=s.match(/open\.spotify\.com\/(playlist|album|track|artist)\/([A-Za-z0-9]+)/); if(m) return `spotify:${m[1]}:${m[2]}`;
  m=s.match(/^spotify:(playlist|album|track|artist):[A-Za-z0-9]+$/); if(m) return s;
  return null;
}
function loadSPL(){
  const box=$("#spl-list"); if(!box) return; box.innerHTML="";
  const pls=FH.get().spotifyPlaylists||[];
  if(!pls.length){ box.innerHTML='<div class="sub" style="margin:0">No playlists pinned yet.</div>'; return; }
  pls.forEach((p,i)=>{
    const row=document.createElement("div"); row.className="prow";
    row.innerHTML=`<div class="pav" style="background:#1db954">🎵</div><div class="pname">${p.name}<div class="sub" style="margin:0;font-size:12px">${p.uri}</div></div><button class="del" data-act="del">Remove</button>`;
    row.querySelector('[data-act="del"]').onclick=()=>{ FH.save({spotifyPlaylists:pls.filter((_,j)=>j!==i)}); loadSPL(); };
    box.appendChild(row);
  });
}
$("#spl-add").onclick=()=>{
  const name=$("#spl-name").value.trim(), uri=spotifyUri($("#spl-uri").value);
  if(!name){ toast("Give it a name"); return; }
  if(!uri){ toast("That doesn't look like a Spotify link"); return; }
  FH.save({spotifyPlaylists:[...(FH.get().spotifyPlaylists||[]),{name,uri}]});
  $("#spl-name").value=""; $("#spl-uri").value=""; toast("Pinned"); loadSPL();
};

async function loadWallVersion(check){
  const el=$("#wall-ver"); let v=null;
  try{ v=await fetch("/api/admin/version"+(check?"?check=1":"")).then(r=>r.json()); }catch(e){ el.textContent="Couldn't reach the wall."; return null; }
  if(!v.git){ el.textContent="Not a git checkout — update by hand."; return v; }
  let s=(v.address?`Wall address: ${v.address}\n`:"")+`Running ${v.commit} (${v.date}) — ${v.subject||""}`;
  if(check){ s+= v.behind>0 ? `\n${v.behind} update${v.behind>1?"s":""} available → ${v.latest.commit}: ${v.latest.subject}` : "\nUp to date."; }
  if(v.update&&v.update.error) s+="\nLast update failed: "+v.update.error;
  el.textContent=s; el.style.whiteSpace="pre-line"; return v;
}
async function loadPinState(){ try{ const r=await fetch("/api/admin/pin").then(r=>r.json()); $("#pin-state").textContent=r.on?"PIN is ON. Changes need the PIN.":"PIN is OFF. Anyone on your Wi-Fi can change things."; $("#pin-off").hidden=!r.on; }catch(e){ $("#pin-state").textContent="Couldn't reach the wall."; } }
$("#pin-save").onclick=async()=>{
  const pin=$("#pin-new").value.trim(); if(!/^\d{4,8}$/.test(pin)){ toast("Use 4 to 8 digits"); return; }
  const r=await post("/api/admin/pin",{pin});
  if(r.ok){ if(window.FHAuth) FHAuth.setPin(pin); $("#pin-new").value=""; toast("PIN is on. The wall asks for it once."); loadPinState(); }
  else if(r.status!==401) toast((await r.json().catch(()=>({}))).detail||"Couldn't set the PIN");
};
$("#pin-off").onclick=async()=>{ const r=await post("/api/admin/pin",{pin:""}); if(r.ok){ if(window.FHAuth) FHAuth.setPin(""); toast("PIN is off"); loadPinState(); } };
$("#wall-update").onclick=async()=>{
  const before=await loadWallVersion(true); if(!before||!before.git) return;
  if(before.behind===0){ toast("Already up to date"); return; }
  const r=await fetch("/api/admin/update",{method:"POST"}); if(!r.ok){ toast("Couldn't start the update"); return; }
  toast("Updating… the wall restarts itself"); $("#wall-ver").textContent="Updating…";
  const t0=Date.now();
  const poll=async()=>{
    try{ const v=await fetch("/api/admin/version").then(r=>r.json());
      if(v.commit&&v.commit!==before.commit){ toast("Updated to "+v.commit); loadWallVersion(false); return; }
      if(v.update&&v.update.error){ toast("Update failed: "+v.update.error); loadWallVersion(false); return; }
    }catch(e){}
    if(Date.now()-t0<180000) setTimeout(poll,3000); else { toast("Still updating — check again in a minute"); loadWallVersion(false); }
  };
  setTimeout(poll,4000);
};
/* Settings sections: one open at a time, and the one you open scrolls to the top */
document.querySelectorAll("details.fold").forEach(d=>d.addEventListener("toggle",()=>{
  if(!d.open) return;
  document.querySelectorAll("details.fold[open]").forEach(o=>{ if(o!==d) o.open=false; });
  setTimeout(()=>d.scrollIntoView({behavior:"smooth", block:"start"}), 60);
  if(d.dataset.fold==="auto" && window.FHAutomations) FHAutomations.load($("#au-box"), toast);
}));
$("#wall-desktop").onclick=async()=>{ const r=await fetch("/api/admin/desktop",{method:"POST"}).then(x=>x.json()).catch(()=>({})); toast(r.ok?"The wall is showing Ubuntu's desktop":"Couldn't do that: "+(r.reason||"wall not reachable")); };
$("#wall-kiosk").onclick=async()=>{ const r=await fetch("/api/admin/kiosk",{method:"POST"}).then(x=>x.json()).catch(()=>({})); toast(r.ok?"FamilyHub is coming back on the wall":"Couldn't do that: "+(r.reason||"wall not reachable")); };
$("#wall-osk-off").onclick=async()=>{ const r=await fetch("/api/admin/screen-keyboard",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({on:false})}).then(x=>x.json()).catch(()=>({})); toast(r.ok?"Done. Tap Restart the wall computer to finish":"Couldn't turn it off: "+(r.reason||"wall not reachable")); };
$("#wall-reboot").onclick=async()=>{ if(!confirm("Restart the wall computer? The screen is back in about a minute.")) return;
  const r=await fetch("/api/admin/reboot",{method:"POST"}).then(x=>x.json()).catch(()=>({ok:true})); toast(r.ok?"Restarting the wall computer…":r.reason); };
$("#wall-restart").onclick=async()=>{ const r=await fetch("/api/admin/restart",{method:"POST"}); toast(r.ok?"Restarting FamilyHub (back in ~5 s)":"Couldn't reach the wall"); setTimeout(()=>loadWallVersion(false),8000); };
$("#wall-reload").onclick=async()=>{ const r=await fetch("/api/display/reload",{method:"POST"}); toast(r.ok?"Wall will reload in a few seconds":"Couldn't reach the wall"); };
$("#wall-wake").onclick=async()=>{ const r=await fetch("/api/display/wake",{method:"POST"}); toast(r.ok?"Screen waking":"Couldn't reach the wall"); };
async function loadDbInfo(){
  const el=$("#dbinfo"); if(!el) return;
  try{ const i=await fetch("/api/admin/dbinfo").then(r=>r.json());
    // the Start fresh card only matters while the sample family is still in the database
    const cleared=(i.settings_keys||[]).includes("demo_cleared");
    $("#startfresh").hidden = cleared;
    if(!cleared) el.textContent=`people ${i.people} · to-dos ${i.todos}`;
  }catch(e){}
}
$("#clear-demo").onclick=async()=>{
  if(!confirm("Delete the sample family, events, chores, lists, routines and rewards? This can't be undone.")) return;
  const r=await post("/api/admin/clear-demo",{confirm:true}).then(r=>r.json()).catch(()=>null);
  if(!r){ toast("Couldn't clear"); return; }
  toast("Cleared — add your family below"); loadPeople(); loadRC();
};
async function loadRC(){
  const box=$("#rc-list"); if(!box) return; box.innerHTML="";
  let rs=[], cs=[];
  try{ rs=await fetch("/api/routines/").then(r=>r.json()); }catch(e){}
  try{ cs=await fetch("/api/routines/countdowns").then(r=>r.json()); }catch(e){}
  if(!rs.length && !cs.length){ box.innerHTML='<div class="sub" style="margin:0">None yet.</div>'; return; }
  rs.forEach(r=>{
    const row=document.createElement("div"); row.className="prow";
    row.innerHTML=`<div class="pav" style="background:${r.color||'#9aa0a6'}">${r.emoji||'✅'}</div><div class="pname">${r.name}<div class="sub" style="margin:0;font-size:12px">${r.steps.length} steps · ${r.time_of_day}${r.person?' · '+r.person:''}${r.days?' · '+r.days:''}</div></div><button class="del" data-act="del">Delete</button>`;
    row.querySelector('[data-act="del"]').onclick=async()=>{ if(!confirm(`Delete routine "${r.name}"?`)) return; await fetch("/api/routines/"+r.id,{method:"DELETE"}).catch(()=>{}); loadRC(); };
    box.appendChild(row);
  });
  cs.forEach(c=>{
    const row=document.createElement("div"); row.className="prow";
    row.innerHTML=`<div class="pav" style="background:${c.color||'#9aa0a6'}">${c.emoji||'🎉'}</div><div class="pname">${c.title}<div class="sub" style="margin:0;font-size:12px">${c.date} · ${c.days_left===0?'today':c.days_left+' days'}</div></div><button class="del" data-act="del">Delete</button>`;
    row.querySelector('[data-act="del"]').onclick=async()=>{ if(!confirm(`Delete countdown "${c.title}"?`)) return; await fetch("/api/routines/countdowns/"+c.id,{method:"DELETE"}).catch(()=>{}); loadRC(); };
    box.appendChild(row);
  });
}

async function init(){
  await FH.load();   // apply saved theme/accent/font
  try{ categories=await fetch("/api/categories/").then(r=>r.json()); }catch(e){ categories=[]; }
  try{ people=await fetch("/api/categories/people").then(r=>r.json()); }catch(e){ people=[]; }
  renderForm();
  loadCalTargets();
}
init();

/* ---- press and hold a light (Home tab buttons or a room's list) = brightness + colour wheel, like the wall ---- */
let _lpHeld=false, _lpT=null;
document.addEventListener("pointerdown", e=>{
  const el=e.target.closest('.hm-dev[data-eid^="light."], .rm-row[data-eid^="light."]'); if(!el) return;
  if(el.classList.contains("rm-row")&&e.target.closest("label,button,input,.rm-colp")) return;   // the row's own switch / slider / colours
  _lpHeld=false; clearTimeout(_lpT);
  const x0=e.clientX, y0=e.clientY, cancel=()=>{ clearTimeout(_lpT); document.removeEventListener("pointerup",cancel); document.removeEventListener("pointercancel",cancel); document.removeEventListener("pointermove",mv); };
  const mv=ev=>{ if(Math.abs(ev.clientX-x0)>10||Math.abs(ev.clientY-y0)>10) cancel(); };   // scrolling, not holding
  document.addEventListener("pointerup",cancel); document.addEventListener("pointercancel",cancel); document.addEventListener("pointermove",mv);
  _lpT=setTimeout(()=>{ cancel(); _lpHeld=true; setTimeout(()=>{ _lpHeld=false; }, 800); if(navigator.vibrate) navigator.vibrate(20); openLightSheet(el.dataset.eid); }, 500);
});
document.addEventListener("contextmenu", e=>{ if(e.target.closest('.hm-dev[data-eid^="light."], .rm-row[data-eid^="light."]')) e.preventDefault(); });
function openLightSheet(eid){
  const t=FHHome.tilesOf(hmLast||{}).find(x=>x.entity_id===eid); if(!t) return;
  let ov=document.getElementById("lpsheet");
  if(!ov){ ov=document.createElement("div"); ov.id="lpsheet";
    ov.style.cssText="position:fixed;inset:0;z-index:9000;background:rgba(0,0,0,.55);display:flex;align-items:flex-end;justify-content:center";
    ov.innerHTML='<div style="background:var(--panel,#1c1c1c);color:var(--ink,#eee);width:100%;max-width:560px;border-radius:20px 20px 0 0;padding:16px 16px calc(16px + env(safe-area-inset-bottom));max-height:88vh;overflow:auto">'+
      '<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px"><b id="lps-name" style="flex:1;font-size:18px"></b><button id="lps-tg" style="border:0;border-radius:12px;padding:9px 14px;font:inherit;font-weight:700;background:var(--panel2,#333);color:inherit"></button><button id="lps-x" aria-label="Close" style="border:0;border-radius:50%;width:38px;height:38px;background:var(--panel2,#333);color:inherit;font-size:16px">✕</button></div>'+
      '<div id="lps-state" style="color:var(--ink-dim,#aaa);font-size:13px;margin-bottom:8px"></div><div id="lps-body"></div></div>';
    document.body.appendChild(ov);
    ov.addEventListener("click", e=>{ if(e.target===ov) closeLightSheet(); });
    ov.querySelector("#lps-x").onclick=closeLightSheet; }
  _rmBusy=Date.now()+600000;                       // don't redraw underneath while a colour is being picked
  const draw=()=>{
    ov.querySelector("#lps-name").textContent=t.name;
    ov.querySelector("#lps-state").textContent=t.on?("On"+(t.brightness!=null?" · "+t.brightness+"%":"")):"Off";
    ov.querySelector("#lps-tg").textContent=t.on?"Turn off":"Turn on";
    const body=ov.querySelector("#lps-body");
    if(!t.dimmable&&!t.color&&!t.whites){ body.innerHTML='<div style="color:var(--ink-dim,#aaa);font-size:14px;line-height:1.4">Home Assistant says this one can only switch on and off. Brightness and color need the LED controller itself in Home Assistant, not the switch or plug that powers it.</div>'; return; }
    body.innerHTML=FHHome.lightPanelHTML(t);
    FHHome.bindLightPanel(body, t, async data=>{ if(navigator.vibrate) navigator.vibrate(6);
      try{ await post("/api/ha/service",{domain:"light", service:"turn_on", entity_id:eid, data}); t.on=true;
        ov.querySelector("#lps-state").textContent="On"; ov.querySelector("#lps-tg").textContent="Turn off"; }catch(err){ toast("Couldn't reach the wall"); } });
  };
  ov.querySelector("#lps-tg").onclick=async()=>{ try{ await post("/api/ha/toggle",{entity_id:eid}); t.on=!t.on; draw(); }catch(err){ toast("Couldn't reach the wall"); } };
  draw(); ov.style.display="flex";
}
function closeLightSheet(){ const ov=document.getElementById("lpsheet"); if(ov) ov.style.display="none"; _rmBusy=0; setTimeout(loadHM, 300); }
