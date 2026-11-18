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
  ok(await w.evaluate(() => window._said.length === 1), 'wall: a score is spoken');
  ok(werr.length === 0, 'wall: no script errors' + (werr.length ? ' -> ' + werr.slice(0, 3).join(' | ') : ''));

  // ---------------- the phone ----------------
  const p = await b.newPage({ viewport: { width: 390, height: 844 } });
  const perr = []; p.on('pageerror', e => perr.push(e.message));
  await p.goto(base + '/phone.html'); await p.waitForTimeout(1200);
  for (const tab of ['home', 'cal', 'settings', 'add']) {
    await p.click('#nav-' + tab); await p.waitForTimeout(700);
    ok(await p.locator('#view-' + tab).isVisible(), 'phone: opens the ' + tab + ' tab');
  }
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
