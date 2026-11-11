/* Live video from Alarm.com cameras (doorbell, backyard) in the wall + phone.
   Ported from the `alarm-webrtc-card.js` shipped with ibasebcast/ha-alarmdotcom
   (Apache-2.0, see static/vendor/ha-alarmdotcom-LICENSE). Changes: plain class
   instead of a Lovelace card; credentials come from FamilyHub's /api/ha/webrtc/<entity>
   (which asks Home Assistant on your behalf) instead of the HA websocket; status
   callback instead of placeholders. The video itself goes browser <-> Alarm.com's
   streaming servers directly — nothing passes through FamilyHub or HA.

   const s = new ADCStream(videoEl, "camera.front_door", {onstatus: st => ...});
   s.start();  ...  s.stop();          status: connecting | live | failed | stopped */
(function(){
  class ADCStream {
    constructor(video, entityId, opts){
      this.video=video; this.entityId=entityId; this.opts=opts||{};
      this.pc=null; this.ws=null; this._gen=0; this._keep=null; this._retry=null; this._retries=0; this._max=this.opts.maxRetries??4;
      this._connected=false; this._stopped=false;
    }
    _status(s, why){ try{ (this.opts.onstatus||(()=>{}))(s, why); }catch(e){} }
    _log(){ if(this.opts.debug) console.debug("[ADCStream "+this.entityId+"]", ...arguments); }

    // Apple decoders choke on some H.264 profiles the cameras advertise; force Constrained Baseline (see fork #38/#112)
    _isApple(){ const ua=navigator.userAgent.toLowerCase(); const ios=/ipad|iphone|ipod/.test(ua)||(navigator.platform==="MacIntel"&&navigator.maxTouchPoints>1);
      const safari=ua.includes("safari")&&!ua.includes("chrome")&&!ua.includes("chromium"); return ios||safari||navigator.platform.toLowerCase().includes("mac"); }
    _patchSdp(sdp){ if(!sdp) return sdp; sdp=sdp.replace(/profile-level-id=[0-9a-fA-F]{6}/g,"profile-level-id=42e01f");
      for(const m of [...sdp.matchAll(/a=rtpmap:(\d+) H264\/90000/gi)]){ const pt=m[1], re=new RegExp(`a=fmtp:${pt} ([^\\r\\n]*)`), f=sdp.match(re);
        if(f){ if(!/profile-level-id/i.test(f[1])) sdp=sdp.replace(re,`a=fmtp:${pt} ${f[1]};profile-level-id=42e01f`); }
        else sdp=sdp.replace(m[0],`${m[0]}\r\na=fmtp:${pt} profile-level-id=42e01f`); }
      return sdp; }

    async start(){
      this._stopped=false; this._gen++; const gen=this._gen; this._status("connecting");
      let cfg=null;
      try{ const r=await fetch(this.opts.configUrl||`/api/ha/webrtc/${encodeURIComponent(this.entityId)}`); if(r.ok) cfg=await r.json(); }catch(e){}
      if(gen!==this._gen) return;
      if(!cfg||!this._valid(cfg)){ this._status("failed","no stream"); return; }
      try{ if(cfg.streamType==="janus"||cfg.janusGatewayUrl) await this._janus(cfg, gen); else await this._legacy(cfg, gen); }
      catch(e){ this._log("start failed", e); this._fail(gen, "start failed"); }
    }
    stop(){ this._stopped=true; this._gen++; this._teardown(); this._status("stopped"); }
    _valid(c){ if(c.streamType==="janus"||c.janusGatewayUrl) return !!(c.janusGatewayUrl&&c.janusToken); return !!(c.signallingServerUrl&&c.signallingServerToken&&c.cameraAuthToken); }
    _teardown(){ clearInterval(this._keep); this._keep=null; clearTimeout(this._retry); this._retry=null; clearInterval(this._watch); this._watch=null;
      try{ if(this.ws) this.ws.close(); }catch(e){} this.ws=null;
      try{ if(this.pc) this.pc.close(); }catch(e){} this.pc=null;
      if(this.video&&this.video.srcObject){ try{ this.video.srcObject.getTracks().forEach(t=>t.stop()); }catch(e){} this.video.srcObject=null; }
      this._connected=false; }
    _fail(gen, why){ if(gen!==this._gen||this._stopped) return; this._gen++; this._teardown();
      if(this._retries++<this._max){ this._status("connecting", why); this._retry=setTimeout(()=>{ if(!this._stopped) this.start(); }, 3000); }
      else this._status("failed", why); }
    _live(){ this._connected=true; this._retries=0; this._status("live"); }
    /* A track can arrive with no pictures (battery doorbells are slow to wake, or Alarm.com's relay stalls).
       Only call it "live" once frames are actually playing; no frames in firstFrameMs, or a picture frozen
       for freezeMs, counts as a failure and reconnects (the snapshot stays up meanwhile). */
    _watchFrames(gen){
      const v=this.video, t0=Date.now(), first=this.opts.firstFrameMs??15000, freeze=this.opts.freezeMs??8000;
      let lastT=-1, lastMove=Date.now();
      clearInterval(this._watch);
      this._watch=setInterval(()=>{ if(gen!==this._gen){ clearInterval(this._watch); return; }
        const moving=v.videoWidth>0&&v.readyState>=2&&v.currentTime>0;
        if(v.currentTime!==lastT){ lastT=v.currentTime; lastMove=Date.now(); }
        if(!this._connected){
          if(moving) this._live();
          else if(Date.now()-t0>first){ clearInterval(this._watch); this._fail(gen,"no video"); }
          else this._play();
        } else if(Date.now()-lastMove>freeze){ clearInterval(this._watch); this._connected=false; this._fail(gen,"frozen"); }
      }, 500);
    }
    _play(){ const v=this.video; if(v&&(v.paused||v.ended)){ v.muted=true; v.playsInline=true; v.play().catch(()=>{}); } }
    _pc(cfg, gen){
      const pc=new RTCPeerConnection({iceServers:cfg.iceServers||[]}); this.pc=pc;
      pc.ontrack=(e)=>{ if(gen!==this._gen) return; if(!this.video.srcObject){ this.video.srcObject=e.streams[0]; this._watchFrames(gen); } this._play(); };
      pc.oniceconnectionstatechange=()=>{ if(gen!==this._gen) return; const s=pc.iceConnectionState; if(s==="disconnected"||s==="failed"||s==="closed") this._fail(gen,"ice "+s); };
      return pc;
    }

    // ---- legacy signalling server ----
    async _legacy(cfg, gen){
      const pc=this._pc(cfg, gen);
      const ws=new WebSocket(`${cfg.signallingServerUrl}/${cfg.signallingServerToken}`); this.ws=ws;
      ws.onopen=()=>{ if(gen===this._gen) ws.send("HELLO 2.0.1"); };
      ws.onmessage=async(m)=>{ if(gen!==this._gen) return;
        if(m.data.startsWith("HELLO")){ ws.send(`START_SESSION ${cfg.cameraAuthToken}`); return; }
        if(m.data.startsWith("SESSION_STARTED")) return;
        let d; try{ d=JSON.parse(m.data); }catch(e){ return; }
        if(d.sdp&&d.sdp.type==="offer"){
          let offer=d.sdp; if(this._isApple()&&offer.sdp) offer={type:offer.type, sdp:this._patchSdp(offer.sdp)};
          await pc.setRemoteDescription(offer); if(gen!==this._gen) return;
          const ans=await pc.createAnswer(); if(gen!==this._gen) return; await pc.setLocalDescription(ans); if(gen!==this._gen) return;
          await new Promise(res=>{ if(pc.iceGatheringState==="complete") return res(); const h=()=>{ if(pc.iceGatheringState==="complete"){ pc.removeEventListener("icegatheringstatechange",h); res(); } }; pc.addEventListener("icegatheringstatechange",h); setTimeout(res,5000); });
          ws.send(JSON.stringify({to:d.from, sdp:pc.localDescription}));
        }
        if(d.ice){ try{ await pc.addIceCandidate(d.ice); }catch(e){} }
      };
      ws.onclose=()=>{ if(gen!==this._gen) return; this._fail(gen, this._connected?"stream ended":"ws closed"); };
    }

    // ---- Janus gateway (current Alarm.com cameras) ----
    async _janus(cfg, gen){
      const pc=this._pc(cfg, gen);
      const ws=await new Promise((res,rej)=>{ let w; try{ w=new WebSocket(cfg.janusGatewayUrl,["janus-protocol"]); }catch(e){ return rej(e); }
        let done=false; w.onopen=()=>{ if(!done){ done=true; res(w); } }; w.onerror=(e)=>{ if(!done){ done=true; rej(e||new Error("ws error")); } };
        w.onclose=()=>{ if(!done){ done=true; rej(new Error("closed before open")); } }; setTimeout(()=>{ if(!done){ done=true; try{w.close();}catch(e){} rej(new Error("open timeout")); } },5000); });
      if(gen!==this._gen){ ws.close(); return; }
      this.ws=ws;
      let sessionId=null, handleId=null, streamId=cfg.janusStreamId??null, created=false; const needsCreate=!!cfg.proxyUrl;
      const send=(msg)=>{ if(!ws||ws.readyState!==WebSocket.OPEN) return; ws.send(JSON.stringify({...msg, token:cfg.janusToken, transaction:Math.random().toString(36).slice(2)})); };
      send({janus:"create"});
      ws.onmessage=async(ev)=>{ if(gen!==this._gen) return; let msg; try{ msg=JSON.parse(ev.data); }catch(e){ return; }
        if(msg.janus==="success"&&!sessionId){ sessionId=msg.data&&msg.data.id;
          this._keep=setInterval(()=>{ if(ws.readyState===WebSocket.OPEN) send({janus:"keepalive", session_id:sessionId}); },25000);
          send({janus:"attach", session_id:sessionId, plugin:"janus.plugin.streaming"}); return; }
        if(msg.janus==="success"&&sessionId&&!handleId){ handleId=msg.data&&msg.data.id;
          if(needsCreate) send({janus:"message", session_id:sessionId, handle_id:handleId, body:{request:"create", type:"rtp", media_uri:cfg.proxyUrl,
              name:`${(cfg.janusToken||"stream").split(",")[0]}_Live`, is_private:true, streaming_type:"Live", video:true, videoport:0, videopt:126, videortpmap:"H264/90000", timeout_seconds:180, max_timeout_seconds:900}});
          else send({janus:"message", session_id:sessionId, handle_id:handleId, body:{request:"watch", id:streamId, token:cfg.janusToken, audio:true, video:true}});
          return; }
        if(msg.janus==="success"&&sessionId&&handleId&&needsCreate&&!created){
          const id=(msg.plugindata&&msg.plugindata.data&&msg.plugindata.data.stream&&msg.plugindata.data.stream.id)??(msg.data&&msg.data.id)??(msg.plugindata&&msg.plugindata.data&&msg.plugindata.data.id);
          if(id){ created=true; streamId=id; send({janus:"message", session_id:sessionId, handle_id:handleId, body:{request:"watch", id:streamId, token:cfg.janusToken, audio:true, video:true}}); return; } }
        if(msg.janus==="ack") return;
        if(msg.janus==="event"){ const pd=msg.plugindata&&msg.plugindata.data; if(pd&&pd.error){ this._fail(gen,"plugin "+pd.error_code); return; } }
        if(msg.jsep){ let j=msg.jsep; if(this._isApple()&&j.sdp) j={type:j.type, sdp:this._patchSdp(j.sdp)};
          await pc.setRemoteDescription(j); if(gen!==this._gen) return; const ans=await pc.createAnswer(); if(gen!==this._gen) return; await pc.setLocalDescription(ans); if(gen!==this._gen) return;
          send({janus:"message", session_id:sessionId, handle_id:handleId, body:{request:"start"}, jsep:pc.localDescription}); return; }
        if(msg.candidate){ try{ await pc.addIceCandidate(msg.candidate); }catch(e){} return; }
        if(msg.janus==="hangup"||msg.janus==="detached"||msg.janus==="error"){ this._fail(gen, msg.janus); }
      };
      pc.onicecandidate=(e)=>{ if(gen!==this._gen) return; if(e.candidate&&sessionId&&handleId) send({janus:"trickle", session_id:sessionId, handle_id:handleId, candidate:e.candidate}); };
      ws.onclose=()=>{ if(gen!==this._gen) return; this._fail(gen, this._connected?"stream ended":"ws closed"); };
    }
  }
  window.ADCStream=ADCStream;
})();
