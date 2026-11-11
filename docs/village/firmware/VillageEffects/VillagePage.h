// The main phone control page for village-fx.local.
// Kept in its own tab so the Arduino IDE never tries to read the HTML as code.
#pragma once
#include <Arduino.h>

const char PAGE[] PROGMEM = R"HTML(<!doctype html><html><head><meta name=viewport content="width=device-width,initial-scale=1">
<title>Village Effects</title><style>body{font-family:sans-serif;margin:16px;background:#1b1410;color:#f6ead8}
h1{font-size:22px}button,a.b{display:inline-block;text-align:center;text-decoration:none;font-size:17px;padding:12px 0;margin:4px 1%;border:0;border-radius:10px;background:#7a1414;color:#fff;width:47%}
.g{background:#1f5a32}.s{font-size:14px;color:#cdb;white-space:pre-wrap}</style></head><body>
<h1>North Pole Village</h1><div id=st class=s>...</div>
<p><button onclick="c('wake')">Wake village</button><button onclick="c('sleep')">Sleep</button>
<button onclick="c('tree')">Tree show</button><button onclick="c('rachell')">Rachell's show</button>
<button onclick="c('carol')">Carolers sing</button><button class=g onclick="c('train')">Send train</button>
<button class=g onclick="c('sleigh')">Fly sleigh</button>
<button class=g onclick="c('rinkon')">Rink on</button><button class=g onclick="c('rinkoff')">Rink off</button>
<button class=g onclick="c('mist1')">Chimney mist</button><button class=g onclick="c('mist2')">Station mist</button>
<button class=g onclick="c('lampson')">Lamps on</button><button class=g onclick="c('lampsauto')">Lamps auto</button>
<button onclick="c('manual')" style="background:#555">Manual mode on/off</button><a class="b g" href="/settings">Settings</a></p>
<h3 style="font-size:17px;margin:14px 0 4px">Train</h3><div id=ts class=s>...</div>
<p><button class=g onclick="t('go?laps=1')">1 lap</button><button class=g onclick="t('go?laps=3')">3 laps</button>
<button class=g onclick="t('go?laps=10')">10 laps</button><button style="background:#b00" onclick="t('stop')">STOP train</button>
<div style="margin:4px 1%"><input id=pn type=number min=1 max=255 value=7 style="width:90px;font-size:17px;padding:10px;border-radius:10px;border:1px solid #999"> <button style="width:auto;background:#2b6a3a" onclick="c('play:'+pn.value)">Play sound #</button></div>
<div style="margin:4px 1%"><input id=ln type=number min=1 max=250 value=1 style="width:90px;font-size:17px;padding:10px;border-radius:10px;border:1px solid #999"> <button style="width:auto;background:#7a5a14" onclick="c('light:'+ln.value)">Show light preset #</button></div>
<button style="background:#2b4a7a" onclick="t('bttest')">Bluetooth test</button><button style="background:#555" onclick="t('relaytest')">Relay test (5 s)</button>
<button class=g onclick="t('xing')">Test crossing</button><a class="b" id=tset style="background:#7a5a14" href="http://village-train.local/settings">Train settings</a>
<a class="b" id=lgt style="background:#2b4a7a" href="http://village-lights.local">Lights (WLED)</a><a class="b" id=tpg style="background:#2b4a7a" href="http://village-train.local">Train page</a></p>
<script>function K(){fetch('/links').then(r=>r.text()).then(x=>{var a=x.split('\n');lgt.href='http://'+a[0];tpg.href='http://'+a[1];tset.href='http://'+a[1]+'/settings'})}setInterval(K,10000);K()</script>
<script>function t(x){fetch('/train?do='+encodeURIComponent(x)).then(T)}function T(){fetch('/train?do=status').then(r=>r.text()).then(x=>ts.textContent=x)}setInterval(T,3000);T()</script>
<script>function c(x){fetch('/cmd?do='+x).then(s)}function s(){fetch('/status').then(r=>r.text()).then(t=>st.textContent=t)}setInterval(s,2000);s()</script>
<h3 style="font-size:16px;margin:14px 0 4px">Live log <button onclick="lg.textContent='';fetch('/logclear')" style="width:auto;font-size:13px;padding:4px 10px;background:#555">Clear</button></h3>
<pre id=lg style="background:#000;color:#7CFC7C;font-size:12px;height:260px;overflow-y:auto;padding:8px;border-radius:8px;white-space:pre-wrap;margin:0"></pre>
<script>var ls=-1;function L(){fetch('/log').then(r=>r.text()).then(t=>{var i=t.indexOf('\n'),q=t.slice(0,i);if(q!=ls){ls=q;var b=lg.scrollTop+lg.clientHeight>=lg.scrollHeight-20;lg.textContent=t.slice(i+1);if(b)lg.scrollTop=lg.scrollHeight}})}setInterval(L,700);L()</script></body></html>)HTML";
