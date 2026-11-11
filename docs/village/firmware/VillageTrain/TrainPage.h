// The phone page for village-train.local.
// Kept in its own tab so the Arduino IDE never tries to read the HTML as code.
#pragma once
#include <Arduino.h>

const char PAGE[] PROGMEM = R"HTML(<!doctype html><html><head><meta name=viewport content="width=device-width,initial-scale=1">
<title>Village Train</title><style>body{font-family:sans-serif;margin:16px;background:#101820;color:#e8f0f8}
button{font-size:17px;padding:12px;margin:4px 2px;border:0;border-radius:10px;background:#1f5a32;color:#fff;width:48%}
.r{background:#7a1414}.s{font-size:14px;white-space:pre-wrap}</style></head><body><h1>Village Train</h1>
<div id=st class=s>...</div><p><button onclick="c('go?laps=1')">1 lap</button><button onclick="c('go?laps=3')">3 laps</button>
<button onclick="c('go?laps=10')">10 laps</button><button class=r onclick="c('stop')">STOP</button><button onclick="c('xing')">Test crossing</button><button style="background:#555" onclick="c('relaytest')">Relay test (5 s)</button><button style="background:#2b4a7a" onclick="c('bttest')">Bluetooth test</button><button style="background:#7a5a14" onclick="location.href='/settings'">Settings</button><button style="background:#7a1414" onclick="location.href='/fx'">Village page</button></p>
<script>function c(x){fetch('/'+x).then(s)}function s(){fetch('/status').then(r=>r.text()).then(t=>st.textContent=t)}setInterval(s,1000);s()</script>
<h3 style="font-size:16px;margin:14px 0 4px">Live log <button onclick="lg.textContent='';fetch('/logclear')" style="width:auto;font-size:13px;padding:4px 10px;background:#555">Clear</button></h3>
<pre id=lg style="background:#000;color:#7CFC7C;font-size:12px;height:260px;overflow-y:auto;padding:8px;border-radius:8px;white-space:pre-wrap;margin:0"></pre>
<script>var ls=-1;function L(){fetch('/log').then(r=>r.text()).then(t=>{var i=t.indexOf('\n'),q=t.slice(0,i);if(q!=ls){ls=q;var b=lg.scrollTop+lg.clientHeight>=lg.scrollHeight-20;lg.textContent=t.slice(i+1);if(b)lg.scrollTop=lg.scrollHeight}})}setInterval(L,700);L()</script></body></html>)HTML";
