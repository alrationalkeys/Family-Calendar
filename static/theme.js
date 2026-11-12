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
    villageWithHouse: true,
    nightCheck: true, nightCheckTime: "22:30", peakAlerts: true, weeklySummary: true, batteryLow: 25, laundryAlerts: true, laundryQuietStart: "21:30", laundryQuietEnd: "07:30", wxAlerts: true, rainCheck: true, packageAlerts: true,
    welcomeNoCode: false,    // I'm home button disarms without the code  // Good night / Leaving put the Christmas village to sleep
    spotifyStartVolume: 45,  // % the wall's Spotify player starts at
    spotifyPlaylists: [],    // [{name, uri}] pinned on the Home tab's Spotify card
    icloudAlbumUrl: "",      // iCloud Shared Album public link -> slideshow photos
    assistantName: "Hub",    // what the family calls the voice assistant
    defaultCalendar: "",     // where new events go by default (a /api/sources/targets id)
    speakAlerts: true,       // wall speaks reminders / announcements / timers
    slideshowAfter: 5,       // minutes with no touch before the photo slideshow (0 = never)
    slideSeconds: 8,         // seconds each photo stays up
    photoFit: "fit",         // slideshow: "fit" = whole photo over blurred backdrop, "fill" = crop to screen
    announceAdds: true,      // wall says "Rachell added …" when a phone adds something
    announceQuietStart: null, // "HH:MM"; null = follow the screen-off night window; "" = never quiet
    announceQuietEnd: null,
    pushAdds: true,          // Home Assistant pushes adds to the other phones
    morningBriefing: false,  // auto-spoken briefing on first walk-up (off: button / ask)
    briefingHour: 6,         // ...but not before this hour
    doorbellTv: true,        // flash the doorbell snapshot on any Roku that is on
    doorbellSpeak: true,
    birthdays: [],           // [{name, date}] relatives: wall goes Birthday on their day
    skin: "auto",            // holiday skin: auto | off | christmas | thanksgiving
    skinBanner: true,        // the "Days until …" card in the header
    skinArt: true,           // painted frame artwork when the skin has one (off = vector frame)
    skinSlim: true,          // thinner painted frame (cropped), more room for the panels
    calendarTasks: true,
    sleepOnNightArm: true,
    sleepArmStates: ["armed_night", "armed_home"],
    sleepStayWindow: ["20:00", "05:00"],
    closeGarageOnModes: true,
    rokuApps: [],
    awayArm: "stay",
    homeAddress: "",
    leaveBuffer: 5,
    leaveAlerts: true,     // due-dated to-dos + chores show as all-day chips on the calendar
    nightTemp: null,         // Good Night thermostat (null = leave it)
    goodnightLightsOff: false, // Good night also turns off lights + TVs (default: locks, alarm, garage only)
    homeTemp: null,
    openGarageOnHome: true,  // "I'm home" button opens the garage (after disarming)          // "I'm home" thermostat setting
    awayTemp: null,          // Away thermostat setback     // wall says "someone's at the front door"
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
