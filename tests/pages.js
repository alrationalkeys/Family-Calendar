// Browser checks for the wall and the phone page: they load with no script errors and the main things work.
// Run through tests/run.sh (it starts a scratch server first). Usage: node tests/pages.js http://localhost:PORT
const { chromium } = require('playwright');
const base = process.argv[2] || 'http://localhost:8766';
const fails = [];
const ok = (cond, what) => { if (!cond) fails.push(what); console.log((cond ? '  ok   ' : '  FAIL ') + what); };

(async () => {
  const b = await chromium.launch();

  // ---------------- the wall ----------------
  const w = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  const werr = []; w.on('pageerror', e => werr.push(e.message));
  await w.route('**/api/display/state', async r => { const j = await (await r.fetch()).json(); r.fulfill({ json: { ...j, on: true, night: false, sleep_mode: false } }); });
  await w.goto(base + '/'); await w.waitForTimeout(4500);
  ok(await w.locator('#clock').innerText() !== '--:--', 'wall: clock is running');
  ok(await w.locator('#calbody').count() === 1, 'wall: calendar is drawn');
  ok((await w.locator('#todos .list-row').count()) >= 1, 'wall: to-do box lists the test to-do');
  for (const page of ['home', 'chores', 'lists', 'photos', 'calendar']) {
    await w.evaluate(p => showPage(p), page); await w.waitForTimeout(500);
    ok(await w.evaluate(p => curPage === p, page), 'wall: opens the ' + page + ' page');
  }
  // tick a to-do and bring it back (undo)
  await w.locator('#todos .list-row').first().click(); await w.waitForTimeout(900);
  ok(await w.locator('#todos .list-row.done').count() >= 1, 'wall: a ticked to-do stays, crossed out');
  await w.locator('#todos .list-row.done').first().click(); await w.waitForTimeout(900);
  ok(await w.locator('#todos .list-row.done').count() === 0, 'wall: tapping it again brings it back');
  // middle box modes
  for (const [mode, title] of [['today', 'TODAY'], ['todo', '‹'], ['groceries', 'GROCERIES']]) {
    await w.evaluate(m => FH.save({ sideBox2: m }).then(() => load()), mode); await w.waitForTimeout(900);
    ok((await w.locator('#panel-groceries h2').innerText()).toUpperCase().includes(title), 'wall: middle box shows ' + mode);
  }
  // a score celebration is shown and spoken
  await w.evaluate(() => { window._said = []; const o = sayAloud; sayAloud = s => { window._said.push(s); }; showNotification({ title: 'Goal', body: 'Goal, Testers! Testers 1, Others 0.', kind: 'score:#115740' }); });
  await w.waitForTimeout(300);
  ok(await w.evaluate(() => window._said.length === 1), 'wall: a score is spoken');
  // a phone announcement is spoken even with "say reminders out loud" off, and a line that never finishes can't block the next
  await w.evaluate(() => { window._said = []; FH.get().speakAlerts = false; let first = true;
    sayAloud = s => { window._said.push(s); if (first) { first = false; return new Promise(() => {}); } };
    showNotification({ title: 'Intercom', body: 'Dinner is ready', kind: 'announce' });
    showNotification({ title: 'Goal', body: 'Goal two', kind: 'score:#115740' }); });
  await w.waitForTimeout(800);
  ok(await w.evaluate(() => window._said[0] === 'Dinner is ready'), 'wall: a phone announcement is spoken even with reminders muted');
  await w.evaluate(() => { _sayQ = Promise.resolve(); FH.get().speakAlerts = true; });
  // hands-free: the wake word heard "set a 5 minute timer for eggs" -> the wall opens the voice box and starts the timer
  await w.evaluate(() => { cancelAllTimers(); sayAloud = s => { (window._said = window._said || []).push(s); }; });
  await w.evaluate(b => fetch(b + '/api/ai/wake/test', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: 'set a 5 minute timer for eggs' }) }), base);
  await w.waitForTimeout(2500);
  ok(await w.evaluate(() => timers.length === 1 && timers[0].total === 300 && /egg/i.test(timers[0].label)), 'wall: wake word + "5 minute timer for eggs" starts the Eggs timer');
  await w.evaluate(() => { cancelAllTimers(); document.getElementById('voiceov').classList.remove('on'); });
  // a voice timer starts counting only after the wall finishes saying "Timer set…"
  await w.evaluate(() => { cancelAllTimers(); window._done = null; sayAloud = () => new Promise(r => { window._done = r; }); });
  await w.evaluate(b => fetch(b + '/api/ai/wake/test', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: 'set a timer for 6 seconds' }) }), base);
  await w.waitForTimeout(2000);
  const before = await w.evaluate(() => timers.length);
  await w.evaluate(() => window._done && window._done()); await w.waitForTimeout(200);
  ok(before === 0 && await w.evaluate(() => timers.length === 1 && timers[0].total === 6), 'wall: a spoken timer starts after "Timer set" is said');
  await w.evaluate(() => { cancelAllTimers(); sayAloud = s => { (window._said = window._said || []).push(s); }; });
  // turning timers off by voice: by name, "how long left", and "stop" while one rings (handled on the wall, no server trip)
  ok(await w.evaluate(() => { cancelAllTimers(); startTimer(300, 'Chicken'); startTimer(600, 'Rice');
    const q = timerVoice({ query: true, label: 'Rice' }); const c = timerVoice({ cancel: true, label: 'Chicken' });
    return /Rice has (9|10) minutes left/.test(q) && c === 'Cancelled the chicken timer.' && timers.length === 1 && timers[0].label === 'Rice'; }), 'wall: voice cancels the chicken timer by name and tells time left');
  ok(await w.evaluate(() => { timers[0].end = Date.now() - 1000; timers[0].rang = true; startAlarm(); return timerVoice({ cancel: true }) === 'Okay.' && timers.length === 0 && !_alarm; }), 'wall: "stop" silences a ringing timer');
  // a weather warning's details open full size (the wall's 20 px checkbox style once shrank it), under no pop-up
  const wxw = await w.evaluate(() => { FHHome.wxHTML([{ id: 'x', big: true, event: 'Coastal Flood Advisory', headline: 'h' }]);
    const ov = document.createElement('div'); ov.id = 'fhwx-ov'; ov.innerHTML = '<div class="fhwx-box">x</div>'; document.body.appendChild(ov);
    const wdt = ov.firstChild.getBoundingClientRect().width; ov.remove(); return wdt; });
  ok(wxw > 300, 'wall: weather warning details open full size');
  // camera sound: hidden until a live feed with audio plays; a tap turns the video's sound on
  ok(await w.evaluate(() => { const v = document.getElementById('cam-video'); const fake = { _sound: false, hasAudio: () => true, sound(on) { this._sound = on; v.muted = !on; return on; } };
    camSound(fake, true); const b = document.getElementById('cam-snd'); const shown = b.style.display === ''; b.click();
    const on = !v.muted; camSound(null, false); v.muted = true; return shown && on && b.style.display === 'none'; }), 'wall: camera sound button turns sound on');
  ok(await w.evaluate(() => +getComputedStyle(document.getElementById('wx-wall')).zIndex < +getComputedStyle(document.getElementById('add-box')).zIndex), 'wall: the warning strip sits under the add sheet');
  // text from outside (email subjects, device names, ESPN) must show as text, never run as markup
  await w.evaluate(() => { window._pwned = 0; banner('<img src=x onerror="window._pwned=1">', '<b>bold?</b>'); });
  await w.waitForTimeout(300);
  ok(await w.evaluate(() => window._pwned === 0 && document.querySelector('#fh-banner b') === null), 'wall: banner text is escaped');
  // a one-day all-day event whose end equals its start (holidays, birthdays) belongs in the Today box
  await w.evaluate(() => { const d = dateStr(new Date()); cache.events = [{ id: 'h1', title: 'Test Holiday', start: d, end: d, all_day: true }]; FH.get().sideBox2 = 'today'; renderTodayBox(); });
  ok((await w.locator('#groceries').innerText()).includes('Test Holiday'), 'wall: Today box shows a one-day holiday');
  await w.evaluate(() => { FH.get().sideBox2 = 'groceries'; });
  ok(werr.length === 0, 'wall: no script errors' + (werr.length ? ' -> ' + werr.slice(0, 3).join(' | ') : ''));

  // ---------------- the phone ----------------
  const p = await b.newPage({ viewport: { width: 390, height: 844 } });
  const perr = []; p.on('pageerror', e => perr.push(e.message));
  await p.goto(base + '/phone.html'); await p.waitForTimeout(1200);
  for (const tab of ['home', 'cal', 'settings', 'add']) {
    await p.click('#nav-' + tab); await p.waitForTimeout(700);
    ok(await p.locator('#view-' + tab).isVisible(), 'phone: opens the ' + tab + ' tab');
  }
  // press and hold a light on the Home tab opens brightness + colour
  await p.click('#nav-home'); await p.waitForTimeout(1500);
  const held = await p.evaluate(async () => { const el = document.querySelector('.hm-dev[data-eid^="light."]'); if (!el) return 'no light';
    const r = el.getBoundingClientRect(); el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, clientX: r.x + 5, clientY: r.y + 5 }));
    await new Promise(res => setTimeout(res, 800)); const ov = document.getElementById('lpsheet');
    const okk = !!ov && ov.style.display === 'flex' && ov.querySelector('#lps-body').innerHTML.length > 20; if (ov) closeLightSheet(); return okk; });
  ok(held === true, 'phone: press and hold a light opens brightness / colour (' + held + ')');
  await p.click('#nav-settings'); await p.waitForTimeout(500);
  const folds = await p.evaluate(() => [...document.querySelectorAll('#view-settings details')].map(d => { d.open = true; d.dispatchEvent(new Event('toggle')); return 1; }).length);
  await p.waitForTimeout(2500);
  ok(folds > 10, 'phone: every settings section opens (' + folds + ')');
  ok(await p.locator('#gd-league option').count() >= 12, 'phone: Game day lists the leagues');
  await p.fill('#dg-q', 'front door'); await p.click('#dg-go'); await p.waitForTimeout(1200);
  ok((await p.inputValue('#dg-out')).includes('FamilyHub diagnostics'), 'phone: diagnostics gather');
  await p.fill('#vh-try', 'how many days until Christmas'); await p.click('#vh-go'); await p.waitForTimeout(1500);
  ok((await p.locator('#vh-out').innerText()).includes('Christmas is'), 'phone: Try a command answers');
  await p.click('#nav-add'); await p.waitForTimeout(300);
  ok(!(await p.locator('body').innerText()).includes('\\u{'), 'phone: no raw \\u{...} codes showing as text');
  ok(perr.length === 0, 'phone: no script errors' + (perr.length ? ' -> ' + perr.slice(0, 3).join(' | ') : ''));

  await b.close();
  console.log(fails.length ? '\n' + fails.length + ' browser check(s) FAILED' : '\nall browser checks passed');
  process.exit(fails.length ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
