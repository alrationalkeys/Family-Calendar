"""Logic that can be checked without a server: wording, decisions, safety rules."""
import datetime


def test_scoring_play_wording():
    from app.services.gameday import play_words as w
    assert w("nfl", "CeeDee Lamb 12 Yd pass from Dak Prescott (Brandon Aubrey Kick)") == "12-yard touchdown pass to CeeDee Lamb from Dak Prescott"
    assert w("nfl", "Breece Hall 3 Yd Run (Greg Zuerlein Kick)") == "3-yard rushing touchdown by Breece Hall"
    assert w("nfl", "Brandon Aubrey 58 Yd Field Goal") == "58-yard field goal by Brandon Aubrey"
    assert w("nhl", "Artemi Panarin (12) Wrist Shot, assists: Mika Zibanejad, Adam Fox") == "Goal by Artemi Panarin, assisted by Mika Zibanejad, Adam Fox"


def _board(us, them, state):
    return {"events": [{"id": "1", "date": "2026-11-15T18:00Z", "status": {"type": {"state": state, "shortDetail": "Q2"}},
            "competitions": [{"competitors": [
                {"homeAway": "home", "score": str(us), "winner": us > them and state == "post", "team": {"id": "20", "abbreviation": "NYJ"}},
                {"homeAway": "away", "score": str(them), "team": {"id": "2", "abbreviation": "BUF", "shortDisplayName": "Bills"}}]}]}]}


def test_game_day_celebrates_the_right_things(monkeypatch):
    from app.services import gameday as g
    jets = {"league": "nfl", "id": "20", "name": "New York Jets", "short": "Jets"}
    calls = []
    monkeypatch.setattr(g, "celebrate", lambda gm, title, body, s, big=False, **k: calls.append((title, big)))
    monkeypatch.setattr(g, "_asleep", lambda: False)
    monkeypatch.setattr(g, "_say", lambda *a: None)
    g._S["last"].clear()
    for us, them, st in [(7, 0, "in"), (13, 0, "in"), (14, 0, "in"), (17, 3, "in"), (17, 3, "post")]:
        g.check(g._parse("nfl", _board(us, them, st), {"20": jets}), {"teams": [jets]})
    titles = [c[0] for c in calls]
    assert titles == ["🎉 Touchdown, Jets!", "🎉 Field goal, Jets!", "🏆 Jets win!"], titles   # first sighting and the extra point: silent
    assert calls[-1][1] is True


def test_game_day_light_goes_back_on_if_it_was_on(monkeypatch):
    """Nov 17: a Govee strip that was on ended up off after a goal. It must be put back, and checked."""
    from app.services import gameday as g, ha_svc
    state = {"state": "on", "attributes": {"brightness": 120, "color_mode": "color_temp", "color_temp_kelvin": 3000}}
    calls = []

    def call(dom, svc, e, extra=None):
        calls.append(svc)
        state["state"] = "off" if (svc == "turn_off" or calls.count("turn_on") == 2) else "on"   # drops off after the first restore
        return {"ok": True}
    monkeypatch.setattr(ha_svc, "demo_mode", lambda: False)
    monkeypatch.setattr(ha_svc, "_request", lambda *a, **k: dict(state))
    monkeypatch.setattr(ha_svc, "call_service", call)
    monkeypatch.setattr(g, "_via", lambda e: "govee_light_local")
    monkeypatch.setattr(g.time, "sleep", lambda s: None)
    g._S["flash"] = {}
    g._flash_one("light.back_porch", [1, 2, 3], [255, 255, 255], 3)
    assert state["state"] == "on"
    assert "turn_off" not in calls
    assert g._S["flash"]["light.back_porch"].startswith("held")          # not a rapid blink for a non-Zigbee light


def test_game_day_never_touches_a_light_it_cannot_read(monkeypatch):
    from app.services import gameday as g, ha_svc
    calls = []
    monkeypatch.setattr(ha_svc, "demo_mode", lambda: False)
    monkeypatch.setattr(ha_svc, "_request", lambda *a, **k: (_ for _ in ()).throw(OSError("down")))
    monkeypatch.setattr(ha_svc, "call_service", lambda *a, **k: calls.append(a) or {"ok": True})
    monkeypatch.setattr(g.time, "sleep", lambda s: None)
    g._flash_one("light.x", [1, 2, 3], [4, 5, 6], 3)
    assert calls == []


def test_tv_backlight_decisions():
    from app.services.tv_backlight import want
    p = {"light": "light.tv", "tv": "media_player.tv", "follow": True, "dim": True, "play": 30, "idle": 70}
    assert want(p, "off", True) == ("turn_off", None)
    assert want(p, "off", False) is None
    assert want(p, "playing", False) == ("turn_on", {"brightness_pct": 30})
    assert want(p, "paused", True) == ("turn_on", {"brightness_pct": 70})
    assert want({**p, "follow": False}, "playing", False) is None        # kept off by hand: leave it off


def test_offline_alert_only_while_armed(monkeypatch):
    from app.services import offline_watch as o
    sent, now = [], [1000.0]
    monkeypatch.setattr(o.time, "time", lambda: now[0])
    o._S.update(down={}, told={}, armed_at=0.0, was_armed=False)

    def states(alarm, cam):
        return [{"entity_id": "alarm_control_panel.iq", "state": alarm, "attributes": {}},
                {"entity_id": "camera.driveway", "state": cam, "attributes": {"friendly_name": "Driveway"}}]
    for _ in range(5):
        o.tick({}, states("disarmed", "unavailable"), lambda t, tag: sent.append(t)); now[0] += 60
    assert sent == []
    o._S.update(down={}, told={})
    o.tick({}, states("armed_away", "idle"), lambda t, tag: sent.append(t)); now[0] += 60
    o.tick({}, states("armed_away", "unavailable"), lambda t, tag: sent.append(t)); now[0] += 60
    assert sent == []                                                    # a one-minute blip pages nobody
    o.tick({}, states("armed_away", "unavailable"), lambda t, tag: sent.append(t)); now[0] += 60
    o.tick({}, states("armed_away", "unavailable"), lambda t, tag: sent.append(t)); now[0] += 60
    assert len(sent) == 1 and "Driveway" in sent[0]
    o.tick({}, states("armed_away", "idle"), lambda t, tag: sent.append(t))
    assert "Back online" in sent[-1]


def test_ai_request_helper_picks_the_right_call():
    from app.services import ai_model as m

    class NS:
        def __init__(self, log, name, fail=None): self.log, self.name, self.fail = log, name, fail
        def create(self, **kw):
            self.log.append(self.name)
            if self.fail: raise self.fail
            return "ok"

    class C:
        def __init__(self, fail=None):
            self.log = []; self.messages = NS(self.log, "plain"); self.beta = type("B", (), {})(); self.beta.messages = NS(self.log, "beta", fail)
    c = C(); m.create(c, model="claude-opus-5-5"); assert c.log == ["beta"]
    c = C(TypeError("old sdk")); m.create(c, model="claude-opus-5-5"); assert c.log == ["beta", "plain"]
    c = C(); m.create(c, model="claude-haiku-5-5"); assert c.log == ["plain"]
    assert m.effort("claude-haiku-4-5") == {} and m.effort("claude-opus-5-5", "medium") == {"output_config": {"effort": "medium"}}
    assert m.web_search_tool("claude-haiku-5-5")["type"] == "web_search_20250305"


def test_santa_season_and_days_until():
    from app.services.cloud_voice import santa_season
    assert not santa_season(datetime.date(2026, 11, 26)) and santa_season(datetime.date(2026, 11, 27))
    assert santa_season(datetime.date(2026, 12, 25)) and not santa_season(datetime.date(2026, 12, 26))
    from app.services.voice_cmd import _days_until, _holiday
    assert _holiday("easter", 2027) == datetime.date(2027, 3, 28)
    assert _holiday("thanksgiving", 2026) == datetime.date(2026, 11, 26)
    assert _days_until("days until Disney") == "" and "Christmas" in _days_until("how many sleeps until Christmas?")


def test_house_modes_never_disarm_without_a_tap():
    """Standing rule: voice / AI / routines cannot disarm. Only a tapped house button may."""
    import inspect
    from app.services import house_modes
    src = inspect.getsource(house_modes)
    assert "tapped" in src
    sig = inspect.signature(house_modes.run)
    assert sig.parameters["tapped"].default is False


def test_garage_watch_can_only_close():
    import inspect
    from app.services import garage_watch
    src = inspect.getsource(garage_watch)
    assert "close_cover" in src and "open_cover" not in src


# ---- from the second audit (Nov 18) ---------------------------------------------------------------

def test_two_celebrations_in_a_row_leave_the_light_as_it_was(monkeypatch):
    """Overlapping flashes used to read the team colour as 'how it was' and leave the light stuck on."""
    import threading
    from app.services import gameday as g, ha_svc
    state = {"state": "off", "attributes": {}}
    lock = threading.Lock()

    def call(dom, svc, e, extra=None):
        with lock:
            state["state"] = "on" if svc == "turn_on" else "off"
        return {"ok": True}
    monkeypatch.setattr(ha_svc, "demo_mode", lambda: False)
    monkeypatch.setattr(ha_svc, "_request", lambda *a, **k: dict(state))
    monkeypatch.setattr(ha_svc, "call_service", call)
    monkeypatch.setattr(g, "_via", lambda e: "zha")
    real_sleep = g.time.sleep
    monkeypatch.setattr(g.time, "sleep", lambda s: real_sleep(0.01))
    ts = [threading.Thread(target=g.flash, args=(["light.kitchen"], "#ff0000", "#ffffff", 2)) for _ in range(2)]
    for t in ts: t.start()
    for t in ts: t.join(20)
    assert state["state"] == "off"


def test_score_glitch_does_not_celebrate_twice(monkeypatch):
    from app.services import gameday as g
    jets = {"league": "nfl", "id": "20", "name": "New York Jets", "short": "Jets"}
    calls = []
    monkeypatch.setattr(g, "celebrate", lambda gm, title, *a, **k: calls.append(title))
    monkeypatch.setattr(g, "_asleep", lambda: False)
    monkeypatch.setattr(g, "_say", lambda *a: None)
    g._S["last"].clear()
    for us in (21, 21, 0, 21, 21):                     # the feed blanks for one look, then comes back
        g.check(g._parse("nfl", _board(us, 7, "in"), {"20": jets}), {"teams": [jets]})
    assert calls == []


def test_walk_off_score_gets_one_celebration(monkeypatch):
    from app.services import gameday as g
    jets = {"league": "nfl", "id": "20", "name": "New York Jets", "short": "Jets"}
    calls = []
    monkeypatch.setattr(g, "celebrate", lambda gm, title, *a, **k: calls.append(title))
    monkeypatch.setattr(g, "_asleep", lambda: False)
    monkeypatch.setattr(g, "_say", lambda *a: None)
    g._S["last"].clear()
    g.check(g._parse("nfl", _board(14, 17, "in"), {"20": jets}), {"teams": [jets]})
    g.check(g._parse("nfl", _board(20, 17, "post"), {"20": jets}), {"teams": [jets]})
    assert calls == ["🏆 Jets win!"]


def test_soccer_scorer_is_not_named_from_an_older_goal():
    from app.services.gameday import _scorer
    comp = {"details": [{"scoringPlay": True, "team": {"id": "359"}, "clock": {"displayValue": "23'"}, "type": {"text": "Goal"},
                         "athletesInvolved": [{"displayName": "Bukayo Saka"}]}]}
    assert "Saka" in _scorer(comp, "359", 1)
    assert _scorer(comp, "359", 2) == ""               # score says 2, the list still has 1 goal


def test_tv_backlight_fires_once_through_a_quick_state_flip(monkeypatch):
    from app.services import tv_backlight as t
    started = []
    monkeypatch.setattr(t, "pairs", lambda s=None: [{"light": "light.tv", "tv": "media_player.tv", "follow": True, "dim": True, "play": 30, "idle": 70}])
    monkeypatch.setattr(t.threading, "Thread", lambda target, args, **k: type("T", (), {"start": lambda self: started.append(args[1])})())
    t._S["last"].clear()
    for old, new in [("standby", "idle"), ("idle", "home"), ("home", "unavailable"), ("unavailable", "home"), ("home", "playing")]:
        t.on_state("media_player.tv", {"state": old}, {"state": new})
    assert started == ["idle", "playing"]              # power-on fires once; the drop-out and return change nothing


def test_diagnostics_never_list_where_people_are():
    from app.services import diag
    states = [{"entity_id": "sensor.alex_phone_geocoded_location", "state": "12 Some Street", "attributes": {"Location": [1.0, 2.0], "friendly_name": "Alex phone location"}},
              {"entity_id": "device_tracker.alex_phone", "state": "home", "attributes": {"latitude": 1, "friendly_name": "Alex phone"}},
              {"entity_id": "sensor.alex_phone_battery_level", "state": "80", "attributes": {"friendly_name": "Alex phone battery"}}]
    hits = [h["entity_id"] for h in diag._match(states, "alex phone")]
    assert hits == ["sensor.alex_phone_battery_level"]
    assert "hunter2" not in diag._hide("rtsp://admin:hunter2@192.168.1.50/stream") and "192.168" not in diag._hide("host 192.168.1.50")


def test_dryer_peak_alert_does_not_depend_on_the_thermostat_alert(monkeypatch):
    from app.services import watch
    called = []
    monkeypatch.setattr(watch.ha_svc, "peak_now", lambda: True)
    monkeypatch.setattr(watch, "_peak_dryer", lambda s: called.append(1))
    monkeypatch.setattr(watch, "_states", lambda: [])
    watch._peak_tick({"peakAlerts": False, "peakDryer": True})
    assert called == [1]


def test_colours_are_hex_or_dropped():
    from app.services.color import clean, resolve, DEFAULT_COLOR
    assert clean("#4f86c6") == "#4f86c6" and clean('red"><img src=x onerror=1>') is None
    assert resolve('x" onmouseover="1', None, "#112233") == "#112233" and resolve(None, None, None) == DEFAULT_COLOR


def test_score_chip_waits_as_long_as_the_cheer(monkeypatch):
    from app.services import gameday as g
    now = [1000.0]
    monkeypatch.setattr(g.time, "time", lambda: now[0])
    g._S["pub"].clear()
    game = {"key": "k", "us": 7, "them": 0, "state": "in", "detail": "Q1"}
    assert g._held(game, 15)["us"] == 7
    game = {**game, "us": 14}
    assert g._held(game, 15)["us"] == 7            # just scored: the chip still shows the old score
    now[0] += 10; assert g._held(game, 15)["us"] == 7
    now[0] += 6;  assert g._held(game, 15)["us"] == 14


def test_night_mode_ends_when_a_missed_disarm_is_read_back(monkeypatch):
    """Nov 18: the disarm happened while the live link was down, and the wall stayed dark all day."""
    from app.services import display_svc as d, ha_live
    monkeypatch.setattr(d, "_run", lambda cmd: True)
    monkeypatch.setattr(d, "_sleep_settings", lambda: (True, {"armed_night", "armed_home"}))
    d._state.update(sleep_mode=False, alarm=None, alarm_checked=0.0, sleep_since=None)
    monkeypatch.setattr(ha_live, "states", lambda: [{"entity_id": "alarm_control_panel.iq", "state": "armed_night", "attributes": {}}])
    d.on_alarm("armed_night")
    assert d._state["sleep_mode"]
    monkeypatch.setattr(ha_live, "states", lambda: [{"entity_id": "alarm_control_panel.iq", "state": "disarmed", "attributes": {}}])
    d._state["alarm_checked"] = 0.0
    d._poll_alarm()                                   # no change event ever arrived; the current state says disarmed
    assert not d._state["sleep_mode"]


def test_night_mode_gives_up_in_the_daytime_when_the_alarm_cannot_be_read(monkeypatch):
    from app.services import display_svc as d, ha_live
    monkeypatch.setattr(d, "_run", lambda cmd: True)
    monkeypatch.setattr(ha_live, "states", lambda: None)
    monkeypatch.setattr(ha_live, "connected", lambda: True)
    d._state.update(sleep_mode=True, sleep_since=d.time.time() - 3 * 3600, alarm="armed_night", alarm_seen=d.time.time() - 3 * 3600, alarm_checked=0.0)
    monkeypatch.setattr(d, "_stay_counts_as_bedtime", lambda now=None: True)      # still night: stay dark
    d._poll_alarm(); assert d._state["sleep_mode"]
    monkeypatch.setattr(d, "_stay_counts_as_bedtime", lambda now=None: False)     # daytime and blind for hours: light up
    d._state["alarm_checked"] = 0.0
    d._poll_alarm(); assert not d._state["sleep_mode"]


def test_village_follows_the_house(monkeypatch):
    """Outside lights on in the evening -> open; bedtime -> close; once closed, the lights can't reopen it tonight."""
    from app.services import village as v
    sent = []
    monkeypatch.setattr(v, "_get", lambda kind, path, timeout=2.0: sent.append(path) or "AUTOMATIC\nfollows FamilyHub: closed")
    monkeypatch.setattr(v, "_settings", lambda: {"villageOpenLights": ["light.porch"]})
    monkeypatch.setattr(v, "_evening_now", lambda: True)
    monkeypatch.setattr(v, "_bedtime_now", lambda: False)
    monkeypatch.setattr(v.threading, "Thread", lambda target, args, **k: type("T", (), {"start": lambda self: target(*args)})())
    v._auto({"opened": None, "closed": None})
    lit = {"state": "on", "attributes": {"friendly_name": "Porch"}}
    v.on_state("light.kitchen", {"state": "off"}, lit, {})
    assert sent == []                                            # not an outside light
    v.on_state("light.porch", {"state": "off"}, lit, {})
    assert sent == ["/cmd?do=open"]
    v.on_state("scene.go_to_sleep", {"state": "2026-11-18T21:00:00"}, {"state": "2026-11-18T23:00:00", "attributes": {"friendly_name": "Go to sleep"}}, {})
    assert sent[-1] == "/cmd?do=close"
    n = len(sent)
    v.on_state("light.porch", {"state": "off"}, lit, {})         # lights flick on again after bedtime
    assert len(sent) == n
    assert v.command("sleep")["ok"]                               # "sleep" goes out as close on these boards
    assert sent[-1] == "/cmd?do=close"


def test_village_never_starts_the_train_by_itself():
    """The dogs: nothing automatic in FamilyHub may send the train. Only the train commands someone asks for."""
    import inspect
    from app.services import village as v
    auto = inspect.getsource(v.open_for_evening) + inspect.getsource(v.close_for_night) + inspect.getsource(v.on_state) + inspect.getsource(v._catch_up)
    assert "/go" not in auto and "do=train" not in auto and "do=wake" not in auto
    fw = open("docs/village/firmware/VillageEffects/VillageEffects.ino").read()
    assert fw.count("trainGo(") - fw.count("void trainGo(") == 4      # whistle-then-go, the delayed start, and the two trainAuto-gated ones
    assert "if (S.trainAuto) trainGo(S.wakeLaps)" in fw and "if (S.trainAuto) trainGo(1)" in fw
    assert "int trainAuto = 0;" in open("docs/village/firmware/VillageEffects/VillageTypes.h").read()


def test_village_finds_a_board_that_moved(monkeypatch):
    """The router gave the train board a new address: FamilyHub asks Board A where it is and remembers it."""
    from app.services import village
    village._found.clear()
    calls = []

    def fake_fetch(host, path, timeout):
        calls.append((host, path))
        if host == village.DEFAULT_FX and path == "/links":
            return "192.168.1.134\n192.168.1.122"
        if host == "192.168.1.122":
            return "train ok"
        raise OSError("no answer")

    monkeypatch.setattr(village, "_fetch", fake_fetch)
    monkeypatch.setattr(village, "_settings", lambda: {})
    assert village._get("train", "/status") == "train ok"
    assert village._found["train"] == "192.168.1.122"
    calls.clear()
    assert village._get("train", "/status") == "train ok"        # straight to the remembered address
    assert calls == [("192.168.1.122", "/status")]
    village._found.clear()


def test_village_not_kept_shut_by_a_restart_or_a_daytime_close(monkeypatch):
    """Home Assistant restarting makes the bedtime scene go unavailable -> timestamp: that is not good night. And a
    close during the day (6 AM-3 PM) must not keep the village shut that evening."""
    from app.services import village as v
    sent = []
    monkeypatch.setattr(v, "_get", lambda kind, path, timeout=2.0: sent.append(path) or "AUTOMATIC\nfollows FamilyHub: closed")
    monkeypatch.setattr(v, "_settings", lambda: {"villageOpenLights": ["light.porch"]})
    monkeypatch.setattr(v, "_bedtime_now", lambda: False)
    monkeypatch.setattr(v.threading, "Thread", lambda target, args, **k: type("T", (), {"start": lambda self: target(*args)})())
    v._auto({"opened": None, "closed": None})
    scene = {"state": "2026-11-20T14:02:00", "attributes": {"friendly_name": "Go to sleep"}}
    v.on_state("scene.go_to_sleep", {"state": "unavailable"}, scene, {})
    assert sent == []
    monkeypatch.setattr(v, "_evening_now", lambda: False)
    monkeypatch.setattr(v, "_daytime", lambda: True)
    v.close_for_night("test")
    assert not v._auto().get("closed")
    monkeypatch.setattr(v, "_evening_now", lambda: True)
    v.on_state("light.porch", {"state": "off"}, {"state": "on", "attributes": {}}, {})
    assert sent[-1] == "/cmd?do=open"


def test_gameday_survives_a_restart_mid_game(monkeypatch):
    """Updating the wall during a game: the next goal and the win are still cheered (scores are kept in the db)."""
    from app.services import gameday as gd
    said = []
    monkeypatch.setattr(gd, "celebrate", lambda g, title, body, s, **k: said.append(title))
    monkeypatch.setattr(gd, "_asleep", lambda: False)
    team = {"id": "1", "short": "Devils"}
    g = lambda us, state, won=None: {"key": "nhl|1|ev", "league": "nhl", "team": team, "opp": "Rangers", "us": us, "them": 1,
                                    "state": state, "won": won}
    gd._S["last"].clear()
    gd.check([g(1, "in")], {})
    gd._S["last"].clear()                      # the restart: memory gone
    gd._load_last()
    gd.check([g(2, "in")], {})
    gd.check([g(3, "post", True)], {})
    assert said == ["🎉 Goal, Devils!", "🏆 Devils win!"]
    gd._S["last"].clear()


def test_routine_keeps_going_past_a_dead_light():
    """A light with no power (tripped GFCI) must not stop the other lights in the same routine from coming on."""
    import json as _j
    from app.services import automations
    cfg = automations.build({"name": "Sunset", "when": {"type": "sun", "event": "sunset"},
                             "do": [{"type": "on", "entities": ["light.porch", "light.driveway", "switch.side_plug"]}]})
    flat = _j.dumps(cfg)
    assert flat.count('"continue_on_error": true') >= 3
    for e in ("light.porch", "light.driveway", "switch.side_plug"):
        assert f'"entity_id": "{e}"' in flat                   # each light is its own step


def test_village_learns_new_addresses_from_board_announcements():
    """New router (Deco, 192.168.68.x): the boards' own 'I'm here' broadcasts give FamilyHub their new addresses."""
    from app.services import village
    village._found.clear()
    assert village.heard("village-fx", "192.168.68.57") and village.heard("village-train", "192.168.68.58")
    assert village._found == {"fx": "192.168.68.57", "train": "192.168.68.58"}
    assert not village.heard("village-fx", "8.8.8.8")          # never anything outside the home network
    assert not village.heard("somebody-else", "192.168.68.9")
    village._found.clear()


def test_wake_word_strips_itself_and_records_until_quiet():
    """Hands-free: "Hey Jarvis, set a 5 minute timer for eggs" -> the command without the wake word, and the
    recording ends once the cook stops talking (not at the 12 s cap)."""
    import numpy as np
    from app.services import wake
    s = wake.strip_wake
    assert s("Jarvis, set a 5 minute timer for eggs.", "hey_jarvis") == "Set a 5 minute timer for eggs"
    assert s("vis. Set a timer for ten minutes", "hey_jarvis") == "Set a timer for ten minutes"
    assert s("Hey Jarvis what's for dinner?", "hey_jarvis") == "What's for dinner"
    assert s("Hey Hub add milk", "hey_hub_v0.1") == "Add milk"
    assert s("Jarvis", "hey_jarvis") == ""
    assert s("Carvus, Set a timer for 5 minutes for chicken", "hey_jarvis") == "Set a timer for 5 minutes for chicken"   # misheard name
    assert s("Jervis turn off the lights", "hey_jarvis") == "Turn off the lights"
    assert s("Set the table", "hey_jarvis") == "Set the table"
    assert s("Visit grandma Sunday at 2", "hey_jarvis") == "Visit grandma Sunday at 2"    # a real word is kept
    assert wake.pretty("hey_hub_v0.1") == "Hey Hub" and wake.pretty("hey_jarvis") == "Hey Jarvis"

    rng = np.random.default_rng(1)
    quiet = lambda: rng.normal(0, 30, wake.FRAME).astype(np.int16)
    loud = lambda: rng.normal(0, 4000, wake.FRAME).astype(np.int16)
    seq = [quiet() for _ in range(10)] + [loud() for _ in range(25)] + [quiet() for _ in range(200)]
    it = iter(seq)
    frames = wake.record_command(lambda: next(it), floor=0.001)
    assert 35 + 12 <= len(frames) <= 35 + 16              # stops ~1.1 s after the talking ends
    # the wall's chime right after the word, then a pause, then the cook talks: the chime must not end the recording
    seq = [loud() for _ in range(4)] + [quiet() for _ in range(15)] + [loud() for _ in range(25)] + [quiet() for _ in range(200)]
    it = iter(seq)
    frames = wake.record_command(lambda: next(it), floor=0.001)
    assert len(frames) >= 44 + 12
    it = iter([quiet() for _ in range(200)])
    assert wake.record_command(lambda: next(it), floor=0.001) == []     # nobody said anything after the word


def test_wake_word_runs_once_on_one_screen(monkeypatch):
    from app.services import wake
    monkeypatch.setattr(wake, "_claimed", 0)
    wake._publish("heard", "set a timer for 5 minutes")
    n = wake.event()["n"]
    assert wake.event()["stage"] == "heard"
    assert wake.claim(n) is True and wake.claim(n) is False       # a second wall doesn't set a second timer
    assert wake.claim(n - 1) is False


def test_voice_turns_timers_off():
    """"Alexa, cancel the chicken timer" / "stop the timer" / "cancel all timers" / "how much time is left"."""
    from app.services.voice_cmd import interpret as i
    assert i("cancel the chicken timer")["timer"] == {"cancel": True, "all": False, "label": "Chicken"}
    assert i("turn off the timer for the eggs")["timer"]["label"] == "Eggs"
    assert i("stop the timer")["timer"] == {"cancel": True, "all": False, "label": None}
    assert i("cancel all timers")["timer"]["all"] is True
    assert i("how much time is left on the chicken timer")["timer"] == {"query": True, "label": "Chicken"}
    assert i("set a timer for 5 minutes for chicken")["timer"] == {"seconds": 300, "label": "Chicken"}
    assert i("Top the timer")["timer"]["cancel"] is True        # Whisper dropped the "s" of "stop"
    assert "How long" in i("set a timer")["say"]


def test_wake_word_listens_harder_while_a_timer_rings():
    from app.services import wake
    wake.ringing(True)
    assert wake._thr(0.5) == wake.RING_THRESH
    wake.ringing(False)
    assert wake._thr(0.5) == 0.5


def test_village_opens_with_the_holiday_lights_too(monkeypatch):
    """Christmas season: sunset turns on only the holiday plug; the porch lights wait until 11:50 PM."""
    from app.services import village
    monkeypatch.setattr(village, "_settings", lambda: {})
    states = [{"entity_id": "input_text.fh_outdoor_night_lights", "state": "light.front_porch_light,light.driveway_light"},
              {"entity_id": "input_text.fh_outdoor_holiday_lights", "state": "switch.exterior_lights_smart_plug"}]
    assert village.open_lights(states) == ["light.front_porch_light", "light.driveway_light", "switch.exterior_lights_smart_plug"]


def test_outside_power_trip_alert(monkeypatch):
    """GFCI trips: porch light, exterior plug and the Govee on the outdoor outlet go unavailable together -> one push
    after 2 minutes, one "back on" push; an HA restart (everything unavailable) is not called a GFCI."""
    from app.services import outdoor_power as op, village
    monkeypatch.setattr(village, "_settings", lambda: {})
    op._S.update(since=0.0, told=False, names=[], watched=set())
    clock = [1000.0]
    monkeypatch.setattr(op.time, "time", lambda: clock[0])
    lists = [{"entity_id": "input_text.fh_outdoor_night_lights", "state": "light.front_porch_light_2"},
             {"entity_id": "input_text.fh_outdoor_holiday_lights", "state": "light.exterior_lights_smart_plug"}]
    def house(out, inside="on"):
        return lists + [{"entity_id": "light.front_porch_light_2", "state": out, "attributes": {"friendly_name": "Front Porch Light"}},
                        {"entity_id": "light.exterior_lights_smart_plug", "state": out, "attributes": {"friendly_name": "Exterior Lights Smart Plug"}},
                        {"entity_id": "light.back_porch_back_porch_led", "state": out, "attributes": {"friendly_name": "Back Porch LED"}}] + \
               [{"entity_id": f"light.kitchen_{i}", "state": inside} for i in range(6)]
    pushes = []
    push = lambda text, tag: pushes.append(text)
    op.tick({}, house("unavailable"), push)
    clock[0] += 60; op.tick({}, house("unavailable"), push)
    assert pushes == []                                   # not yet: 2 minutes of grace
    clock[0] += 70; op.tick({}, house("unavailable"), push)
    assert len(pushes) == 1 and "Back Porch LED" in pushes[0] and "GFCI" in pushes[0]
    clock[0] += 300; op.tick({}, house("unavailable"), push)
    assert len(pushes) == 1                               # once per outage
    op.tick({}, house("off"), push)
    assert len(pushes) == 2 and "back on" in pushes[1]
    pushes.clear()
    for _ in range(4):                                   # Home Assistant restarting: the kitchen is unavailable too
        clock[0] += 60; op.tick({}, house("unavailable", inside="unavailable"), push)
    assert pushes == []


def test_today_chart_finds_the_washer_and_dryer():
    """GE SmartHQ: each machine's state sensor is picked out (not its time / door / count sensors), and running = a cycle."""
    from app.services import laundry
    states = [{"entity_id": "sensor.d828c1_laundry_machine_state", "state": "Run", "attributes": {"friendly_name": "Dryer Machine State"}},
              {"entity_id": "sensor.d828c1_laundry_time_remaining", "state": "30", "attributes": {"friendly_name": "Dryer Time Remaining"}},
              {"entity_id": "sensor.a11b22_laundry_machine_state", "state": "End of Cycle", "attributes": {"friendly_name": "Washer Machine State"}},
              {"entity_id": "sensor.a11b22_laundry_door", "state": "closed", "attributes": {"friendly_name": "Washer Door"}}]
    assert laundry.state_sensors(states) == {"dryer": "sensor.d828c1_laundry_machine_state", "washer": "sensor.a11b22_laundry_machine_state"}
    assert laundry.is_running("Run") and laundry.is_running("Spin") and not laundry.is_running("End of Cycle")
    assert not laundry.is_running("unavailable") and not laundry.is_running("Off")


def test_week_counts_laundry_loads_and_peak():
    from app.services import timeline
    rows = [{"kind": "laundry", "name": "Washer", "spans": [[400, 450, "on"], [600, 602, "on"], [700, 760, "on"]]},
            {"kind": "laundry", "name": "Dryer", "spans": [[455, 520, "on"]]},
            {"kind": "light", "name": "Porch", "spans": [[0, 120, "on"]]}, {"kind": "tv", "name": "TV", "spans": [[1200, 1290, "on"]]}]
    st = timeline._stats(rows, (360, 540))
    assert st["washer_loads"] == 2 and st["washer_min"] == 112 and st["washer_peak_min"] == 50   # a 2-minute blip isn't a load
    assert st["dryer_loads"] == 1 and st["dryer_peak_min"] == 65
    assert st["light_min"] == 120 and st["tv_min"] == 90


def test_diag_flags_routines_pointing_at_renamed_devices(monkeypatch):
    """Re-adding an integration renamed light.front_porch_light to light.front_porch_light_2: the routine and the
    outdoor list still name the old one, so nothing happens. Diagnostics must say so and suggest the new name."""
    from app.services import diag
    states = [{"entity_id": "automation.kitchen_motion", "state": "on", "attributes": {"friendly_name": "Kitchen motion", "id": "k1", "last_triggered": None}},
              {"entity_id": "automation.outdoor_sunset", "state": "off", "attributes": {"friendly_name": "Outdoor: sunset"}},
              {"entity_id": "light.front_porch_light_2", "state": "on", "attributes": {}},
              {"entity_id": "light.kitchen_uppers", "state": "off", "attributes": {}},
              {"entity_id": "input_text.fh_outdoor_night_lights", "state": "light.front_porch_light", "attributes": {"friendly_name": "Nightly lights"}}]
    monkeypatch.setattr(diag.ha_svc, "_request", lambda path, **k: {"action": [{"action": "light.turn_on", "target": {"entity_id": ["light.kitchen_uppers", "light.kitchen_lowers"]}}]})
    monkeypatch.setattr(diag, "_text", lambda *a, **k: "")
    out = "\n".join(diag.routines(states))
    assert "Kitchen motion: last ran never" in out and "light.kitchen_lowers" in out
    assert "light.turn_on" not in out                    # a service name, not a missing device
    assert "Outdoor: sunset" in out and "<-- OFF" in out
    assert "Nightly lights: HA doesn't have light.front_porch_light" in out
    assert "light.front_porch_light -> light.front_porch_light_2" in out


def test_leaving_keeps_lights_a_routine_turned_on(monkeypatch):
    """Out to dinner at 6:17: Leaving turned off the holiday lights, kitchen uppers and Christmas windows the 5:08
    routines had just turned on. Now it only turns off what someone left on."""
    from app.services import house_modes, ha_live
    st = [{"entity_id": "light.kitchen_uppers", "state": "on", "context": {"id": "a", "parent_id": "auto1", "user_id": None}},
          {"entity_id": "light.bedroom", "state": "on", "context": {"id": "b", "parent_id": None, "user_id": "u1"}},
          {"entity_id": "light.porch", "state": "on", "context": {"id": "c", "parent_id": None, "user_id": None}}]
    monkeypatch.setattr(ha_live, "states", lambda: st)
    assert house_modes._routine_lit(["light.kitchen_uppers", "light.bedroom", "light.porch"]) == {"light.kitchen_uppers"}


def test_leaving_closes_the_village_only_while_out(monkeypatch):
    from app.services import village
    store = {}
    monkeypatch.setattr(village, "_auto", lambda u=None: (store.update(u) if u else None) or dict(store))
    monkeypatch.setattr(village, "_get", lambda *a, **k: "ok")
    monkeypatch.setattr(village, "_evening_now", lambda: True)
    monkeypatch.setattr(village, "_bedtime_now", lambda: False)
    monkeypatch.setattr(village, "_daytime", lambda: False)
    monkeypatch.setattr(village, "_settings", lambda: {})
    store.update({"opened": "17:08"})
    assert village.close_for_night("left the house", night=False)
    assert not store.get("closed") and not store.get("opened")
    assert village.back_home() == "opened the village"          # home from dinner at 9:55: open again
    store.clear(); store.update({"closed": "22:30"})
    assert village.back_home() is None                           # closed by Good night stays closed


def test_leaving_never_touches_lights(monkeypatch):
    from app.services import house_modes
    monkeypatch.setattr(house_modes, "_settings", lambda: {})
    off = [x for x in house_modes.default_steps("away") if x["type"] == "off"]
    assert off and "*lights" not in off[0]["entities"] and "*tvs" in off[0]["entities"]
    calls = []
    monkeypatch.setattr(house_modes.ha_svc, "call_service", lambda d, sv, e, data=None: calls.append((d, sv, e)) or {"ok": True})
    monkeypatch.setattr(house_modes.ha_svc, "peak_now", lambda: False)
    tiles = [{"entity_id": "light.kitchen_uppers", "domain": "light", "name": "Kitchen Uppers", "on": True, "state": "on"},
             {"entity_id": "media_player.living_room_tv", "domain": "media_player", "name": "Living Room TV", "on": True, "state": "on"}]
    done, warn, notes = [], [], []
    house_modes._run_steps("away", [{"type": "off", "entities": ["*lights", "*tvs"]}], tiles, {}, None, False, done, warn, notes)
    assert ("light", "turn_off", "light.kitchen_uppers") not in calls          # even an older saved "lights off" step
    assert ("media_player", "turn_off", "media_player.living_room_tv") in calls


def test_diag_names_who_switched_a_light():
    from app.services.diag import _who
    assert _who({"context_entity_id": "automation.holiday_exterior_regular_lights", "context_entity_id_name": "Holiday Exterior Regular Lights"}) \
        == "by Holiday Exterior Regular Lights (automation.holiday_exterior_regular_lights)"
    assert _who({"context_user_id": "u1", "context_domain": "light", "context_service": "turn_off"}) == "by a person or FamilyHub (light.turn_off)"
    assert _who({}) == "by the device / its own app"


def test_diag_shows_what_a_routine_switches(monkeypatch):
    from app.services import diag
    cfg = {"triggers": [{"trigger": "state", "entity_id": "binary_sensor.kitchen_motion", "to": "on"}],
           "conditions": [{"condition": "time", "after": "21:00"}],
           "actions": [{"action": "light.turn_on", "target": {"entity_id": ["light.kitchen_uppers", "light.front_porch_light_2"]}}]}
    monkeypatch.setattr(diag.ha_svc, "_request", lambda *a, **k: cfg)
    by = {"light.front_porch_light_2": {"attributes": {"friendly_name": "Front Porch Light"}},
          "binary_sensor.kitchen_motion": {"attributes": {"friendly_name": "Kitchen Motion"}}}
    out = "\n".join(diag._routine_detail("fhu_x", by))
    assert "when: state Kitchen Motion (binary_sensor.kitchen_motion)" in out and '"to"' in out
    assert "only if:" in out and "Front Porch Light (light.front_porch_light_2)" in out and "light.turn_on" in out
