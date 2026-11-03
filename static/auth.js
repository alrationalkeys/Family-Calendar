/* FamilyHub login gate (shared by the wall + phone pages).

   What it does, when FAMILYHUB_PIN is set on the server:
   - Attaches the stored PIN as an `X-FH-PIN` header to every /api request.
   - If a request comes back 401 (not unlocked, or stale PIN), clears the stale
     PIN and shows a full-screen unlock screen.
   - If the server has reads locked (FAMILYHUB_LOCK_READS=1) and we have no PIN
     yet, shows the unlock screen up front instead of flashing empty data.

   The static app shell stays public (so this screen can load); only /api data
   is protected. Loaded BEFORE theme.js so the fetch wrapper covers everything.
*/
(function () {
  const KEY = "fh_pin";
  const _fetch = window.fetch.bind(window);   // original, used for login (no wrapper)

  function getPin() { try { return localStorage.getItem(KEY) || ""; } catch (e) { return ""; } }
  function setPin(v) { try { v ? localStorage.setItem(KEY, v) : localStorage.removeItem(KEY); } catch (e) {} }

  function urlOf(input) {
    try { return typeof input === "string" ? input : (input && input.url) || ""; }
    catch (e) { return ""; }
  }
  function isApi(url) {
    if (!url) return false;
    if (url.startsWith("/api")) return true;
    try { const u = new URL(url, location.href); return u.origin === location.origin && u.pathname.startsWith("/api"); }
    catch (e) { return false; }
  }

  // --- wrap fetch: add the PIN header to same-origin /api calls, catch 401 ----
  window.fetch = function (input, init) {
    const url = urlOf(input);
    const api = isApi(url);
    let args = [input, init];
    if (api) {
      const pin = getPin();
      if (pin) {
        const base = (init && init.headers) || (typeof input !== "string" && input && input.headers) || {};
        const h = new Headers(base);
        if (!h.has("X-FH-PIN")) h.set("X-FH-PIN", pin);
        args = [input, { ...(init || {}), headers: h }];
      }
    }
    return _fetch.apply(window, args).then(function (resp) {
      if (api && resp.status === 401) {
        if (getPin()) setPin("");      // stored PIN is stale/rejected — drop it
        showGate();
      }
      return resp;
    });
  };

  // --- unlock screen ----------------------------------------------------------
  let gateEl = null, gateShown = false;

  function buildGate() {
    const wrap = document.createElement("div");
    wrap.id = "fh-gate";
    wrap.innerHTML =
      '<div class="fh-gate-card">' +
        '<div class="fh-gate-ico">🔒</div>' +
        '<h3>FamilyHub</h3>' +
        '<p class="fh-gate-sub">Enter your family PIN to unlock</p>' +
        '<input id="fh-gate-pin" type="password" inputmode="numeric" autocomplete="off" ' +
          'placeholder="PIN" aria-label="Family PIN" />' +
        '<div class="fh-gate-err" id="fh-gate-err"></div>' +
        '<button id="fh-gate-go">Unlock</button>' +
      '</div>';
    const css = document.createElement("style");
    css.textContent =
      '#fh-gate{position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;' +
        'background:var(--bg,#101216);padding:24px;font-family:var(--font,system-ui,sans-serif)}' +
      '#fh-gate .fh-gate-card{background:var(--panel,#1b1e24);color:var(--ink,#eceef2);border-radius:18px;' +
        'padding:30px 26px;width:320px;max-width:92vw;text-align:center;box-shadow:0 18px 50px rgba(0,0,0,.4)}' +
      '#fh-gate .fh-gate-ico{font-size:40px;margin-bottom:6px}' +
      '#fh-gate h3{margin:0 0 4px;font-size:20px}' +
      '#fh-gate .fh-gate-sub{margin:0 0 16px;font-size:13px;color:var(--ink-dim,#9aa2ad)}' +
      '#fh-gate input{width:100%;box-sizing:border-box;font-size:22px;text-align:center;letter-spacing:4px;' +
        'padding:12px;border-radius:12px;border:1px solid var(--line,#2c313a);background:var(--panel2,#23272f);' +
        'color:var(--ink,#eceef2);outline:none}' +
      '#fh-gate input:focus{border-color:var(--now,#e9a23b)}' +
      '#fh-gate .fh-gate-err{min-height:18px;margin:8px 0 2px;font-size:13px;color:#e0665a}' +
      '#fh-gate button{width:100%;margin-top:8px;font-size:17px;padding:12px;border:none;border-radius:12px;' +
        'background:var(--now,#e9a23b);color:#fff;cursor:pointer}' +
      '#fh-gate button:active{transform:scale(.98)}';
    wrap.appendChild(css);
    document.body.appendChild(wrap);

    const input = wrap.querySelector("#fh-gate-pin");
    const err = wrap.querySelector("#fh-gate-err");
    const go = wrap.querySelector("#fh-gate-go");
    async function submit() {
      const pin = input.value.trim();
      if (!pin) { input.focus(); return; }
      err.textContent = "";
      go.disabled = true;
      try {
        const r = await _fetch("/api/auth/login", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pin })
        });
        if (r.ok) { setPin(pin); location.reload(); return; }
        const j = await r.json().catch(() => ({}));
        err.textContent = (r.status === 429) ? (j.detail || "Too many tries — wait a moment")
                                             : "Incorrect PIN";
        input.value = ""; input.focus();
      } catch (e) {
        err.textContent = "Can't reach the server";
      } finally { go.disabled = false; }
    }
    go.onclick = submit;
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") submit(); });
    setTimeout(() => input.focus(), 50);
    return wrap;
  }

  function showGate() {
    if (gateShown) return;
    gateShown = true;
    const start = () => { gateEl = buildGate(); };
    if (document.body) start();
    else document.addEventListener("DOMContentLoaded", start, { once: true });
  }

  // --- startup probe: gate up front if reads are locked and we're not unlocked -
  async function init() {
    try {
      const s = await _fetch("/api/auth/status").then((r) => r.json());
      if (s && s.lock_reads && !getPin()) showGate();
    } catch (e) { /* server unreachable — let normal flow surface it */ }
  }
  init();

  window.FHAuth = { getPin, setPin, gate: showGate };
})();
