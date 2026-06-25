/* Shared theme + settings for FamilyHub.
   Settings live in the backend (/api/settings) so the wall and phone stay in sync,
   with a localStorage cache for instant paint. Applies theme, accent, fonts, and
   density by setting CSS variables + data attributes on <html>. */
const FH = (() => {
  const DEFAULTS = {
    theme: "light",          // light | dark
    accent: "#e9a23b",
    font: "inter",           // inter | serif | rounded | mono
    density: "comfortable",  // compact | comfortable | spacious
    panels: { todos: true, groceries: true, meals: true },
    holidays: { us_federal: false, christian: false, jewish: false, observances: false },
    effects: true,
    dayStart: 6,             // first hour in the day/week time-grid (0–23)
    dayEnd: 23,              // last hour shown (1–24)
  };

  const FONTS = {
    inter: `"Inter","Segoe UI",system-ui,sans-serif`,
    serif: `"Iowan Old Style","Palatino",Georgia,serif`,
    rounded: `"SF Pro Rounded","Segoe UI",system-ui,sans-serif`,
    mono: `"SF Mono","Cascadia Code",ui-monospace,monospace`,
  };
  const DENSITY = { compact: ".82", comfortable: "1", spacious: "1.18" };

  let settings = { ...DEFAULTS };

  function apply(s) {
    settings = { ...DEFAULTS, ...s, panels: { ...DEFAULTS.panels, ...(s.panels||{}) },
                 holidays: { ...DEFAULTS.holidays, ...(s.holidays||{}) } };
    const r = document.documentElement;
    r.setAttribute("data-theme", settings.theme);
    r.style.setProperty("--now", settings.accent);
    r.style.setProperty("--font", FONTS[settings.font] || FONTS.inter);
    r.style.setProperty("--density", DENSITY[settings.density] || "1");
    try { localStorage.setItem("fh_settings", JSON.stringify(settings)); } catch(e){}
  }

  async function load() {
    // instant paint from cache
    try { const c = localStorage.getItem("fh_settings"); if (c) apply(JSON.parse(c)); }
    catch(e){ apply(DEFAULTS); }
    // then sync from server
    try { const s = await fetch("/api/settings").then(r=>r.json()); apply(s); }
    catch(e){}
    return settings;
  }

  async function save(patch) {
    const next = { ...settings, ...patch };
    apply(next);
    try { await fetch("/api/settings", { method:"PUT",
      headers:{"Content-Type":"application/json"}, body: JSON.stringify(next) }); }
    catch(e){}
    return next;
  }

  function get() { return settings; }
  return { load, save, get, apply, DEFAULTS, FONTS, DENSITY };
})();
