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
