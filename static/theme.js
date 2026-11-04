/* Shared theme + settings for FamilyHub.
   Settings live in the backend (/api/settings) so the wall and phone stay in sync,
   with a localStorage cache for instant paint. Applies theme, accent, fonts, and
   density by setting CSS variables + data attributes on <html>. */
const FH = (() => {
  const DEFAULTS = {
    theme: "light",          // light | soft | dark
    accent: "#e9a23b",
    font: "inter",           // inter | serif | rounded | mono
    density: "comfortable",  // compact | comfortable | spacious
    panels: { scoreboard: false, todos: true, groceries: true, meals: true },
    onscreenKbd: true,       // show the on-screen keyboard when a field is tapped
    wallMic: true,           // show the voice-command mic button on the wall
    heroEnabled: false,      // day/night house banner behind the header
    heroDay: "",             // image URL shown in daytime
    heroNight: "",           // image URL shown at night
    holidays: { us_federal: false, christian: false, jewish: false, observances: false },
    effects: true,
    weatherFx: true,         // drive ambient effects from live weather (rain/snow/fog) instead of date
    effectPrefs: { snow: true, fireworks: true, halloween: true, petals: true },
    dayStart: 6,             // first hour in the day/week time-grid (0–23)
    dayEnd: 20,              // last hour shown (1–24)
    hourPx: 46,              // zoom: pixel height of one hour row (26–120)
    panelSizes: [1.1, 1.1, 0.9],   // relative heights of the side panels
    textSize: "normal",      // normal | large  (bigger, easier-to-read content)
    homeLayout: [],          // custom floor-plan rooms; [] = built-in sample
    spotifyPlaylists: [],    // [{name, uri}] pinned on the Home tab's Spotify card
    icloudAlbumUrl: "",      // iCloud Shared Album public link -> slideshow photos
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
                 holidays: { ...DEFAULTS.holidays, ...(s.holidays||{}) },
                 effectPrefs: { ...DEFAULTS.effectPrefs, ...(s.effectPrefs||{}) } };
    // migrate: older caches may lack the scoreboard panel key
    if (settings.panels.scoreboard === undefined) settings.panels.scoreboard = false;
    const r = document.documentElement;
    r.setAttribute("data-theme", settings.theme);
    r.setAttribute("data-textsize", settings.textSize || "normal");
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
