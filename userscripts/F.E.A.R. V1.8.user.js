//  ███████╗███████╗    █████╗    ██████╗
//  ██╔════╝██╔════╝   ██╔══██╗   ██╔══██╗
//  █████╗  █████╗     ███████║   ██████╔╝
//  ██╔══╝  ██╔══╝     ██╔══██║   ██╔══██╗
//  ██║██╗  ███████╗██╗██║  ██║██╗██║  ██║
//  ╚═╝╚═╝  ╚══════╝╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═╝
// Forcefully Eliminating Advertising Redirects
// by iWoozy_Real - OPEN SOURCE - V1.8
// Discord Server : https://trw.lat/ds
// "Un tabaco no hace que un sapo que vuelva un capo y un revolver no hace que un muchacho se haga un macho" - Canserbero

// ==UserScript==
// @name         F.E.A.R. V1.8
// @namespace    ⃟⃞⃟⃞  -THE NOTORIUS Ⱳ.Ø.Ẓ̣̣ ✞
// @version      1.8
// @description  Enhanced AdLink bypass
// @author       iWoozy_real
// @license      MIT
// @match        *://linkvertise.com/*
// @match        *://loot-link.com/*
// @match        *://loot-links.com/*
// @match        *://lootdest.com/*
// @match        *://lootdest.org/*
// @match        *://lootlinks.co/*
// @match        *://lootlinks.com/*
// @match        *://daughablelea.com/*
// @match        *://tonordersitye.com/*
// @match        *://cuty.io/*
// @match        *://www.cuty.io/*
// @match        *://cety.app/*
// @match        *://www.cety.app/*
// @match        *://work.ink/*
// @match        *://lockr.so/*
// @match        *://rip.linkvertise.lol/bypass?url=*
// @match        *://rip.linkvertise.lol/workink?url=*
// @match        *://*.*.*/*?iwantreferrer=*
// @match        *://trw.lat/?url=*
// @match        *://*.*.*/riplvlol*
// @exclude      *://tria.ge/*
// @exclude      *://*.google.*/*

// @grant        GM_xmlhttpRequest
// @grant        GM_getResourceText
// @grant        unsafeWindow
// @grant        GM_addStyle
// @require      https://cdnjs.cloudflare.com/ajax/libs/jquery/3.7.1/jquery.min.js
// @resource     NOTYF_CSS https://cdn.jsdelivr.net/npm/notyf@3/notyf.min.css
// @require      https://cdn.jsdelivr.net/npm/notyf@3/notyf.min.js
// @downloadURL  https://trw.lat/install/userscript/u.user.js
// @updateURL    https://trw.lat/install/userscript/u.user.js
// @homepageURL  https://trw.lat
// @supportURL   https://trw.lat/ds
// @run-at       document-body
// ==/UserScript==

(function () {
  'use strict';
  if (window.top !== window.self) {return}
  if (location.hostname.includes("loot-link") || location.hostname.includes("lootdest") || location.hostname.includes("lootlink")){setInterval(()=>{document.querySelector(".fc-monetization-dialog-container")?.remove()},2500)}
  if (location.href.startsWith("https://rip.linkvertise.lol/workink?url=")){
    unsafeWindow.TRW_Running=true;
    return;
  }
  const CONFIG = {
    wait: 1, // Initial delay (in seconds) before starting the bypass process.
    site: 'rip.linkvertise.lol/bypass?url=', // Base URL for the bypass service.
    timeout: 6000000, // Maximum time (in milliseconds) to wait for the bypass completion check on rip.linkvertise.lol.
    interval: 500, // Interval (in milliseconds) between checks for bypass completion on rip.linkvertise.lol.
    SecureMode: true
    //^^ Enables SecureMode, which increases the wait time to 30 seconds and adds a manual click-button prompt to proceed
    //^^ Enhancing stealth and reducing detectability of the bypass by up to 100%.
  };

  // Adjust wait time if SecureMode is true
  if (CONFIG.SecureMode) {
    CONFIG.wait = 25;
  }

  const notyfCss = GM_getResourceText("NOTYF_CSS");
  GM_addStyle(notyfCss);
  const notyf = new Notyf({ duration: 5000 });
  notyf.information = function(message) {
    this.success({
      message: message,
      duration: 4000,
      dismissible: true,
      background: '#17a2b8',
      icon: '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="white" viewBox="0 0 16 16"><path d="M8 16A8 8 0 1 0 8 0a8 8 0 0 0 0 16zm.93-9.412l-1 4.705c-.07.34.029.533.304.533.194 0 .487-.07.686-.246l-.088.416c-.287.346-.92.598-1.465.598-.703 0-1.002-.422-.808-1.319l.738-3.468c.064-.302.156-.506.258-.678l-.803-.303c-.21.105-.402.26-.523.465l-.728 3.424c-.07.34-.029.533-.304.533-.194 0-.487.07-.686.246l.088-.416c.287-.346.92-.598 1.465-.598.703 0 1.002.422.808 1.319l-.738 3.468c-.064.302-.156.506-.258.678l.803.303c.21-.105.402-.26.523-.465l.728-3.424c.07-.34.029-.533.304-.533.194 0 .487.07.686.246l-.088.416c-.287.346-.92.598-1.465.598-.703 0-1.002-.422-.808-1.319l.738-3.468c-.064.302-.156.506-.258-.678l-.803-.303c-.21.105-.402.26-.523.465z"/></svg>'
    });
  };

  const Log = {
    i: (msg) => console.log(`[F.E.A.R.] ${msg}`),
    e: (msg) => console.error(`[F.E.A.R. ERROR] ${msg}`),
    w: (msg) => console.warn(`[F.E.A.R. WARN] ${msg}`),
  };

  async function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  async function findHref() {
    const start = Date.now();
    while (Date.now() - start < CONFIG.timeout) {
      await sleep(CONFIG.interval);
      try {
        if (document.querySelector("#bypass-title")?.textContent === "BYPASS DONE" && unsafeWindow.o1success) {
          return unsafeWindow.o1result;
        } else if (document.querySelector("#bypass-title")?.textContent === "BYPASS FAILED!") {
          return false;
        }
      } catch (err) {
        console.log(`Find href error: ${err}`);
      }
    }
    return false;
  }

  function isBot() {
    const t = document.title;
    return t.includes('Just a moment') || t.includes('Just a second') || document.body.innerHTML.includes('Are you human?');
  }

  async function main() {
    if (isBot()) {
      notyf.information('Complete the bot challenge to proceed');
      return;
    }

    const p = new URLSearchParams(window.location.search);
    const ref = p.get('iwantreferrer');
    if (ref) {
      history.replaceState(null, null, '/' + ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c => (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c/4).toString(16)))
      setInterval(() => history.replaceState(null, null, '/' + ([1e7]+-1e3+-4e3+-8e3+-1e11)
        .replace(/[018]/g, c => (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c/4).toString(16))), 1000);

      if (CONFIG.SecureMode) {
        unsafeWindow.dest = decodeURIComponent(ref);
        document.documentElement.innerHTML = `<!DOCTYPE html><html><head><title>RIP.LINKVERTISE.LOL</title>` +
          `<style>body{font-family:Arial,sans-serif;background:#1a1a1a;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;margin:0;color:#e0e0e0}h2{font-size:2.5em;margin-bottom:10px}p{font-size:1.2em;text-align:center;margin:5px 0}button{font-size:1.5em;padding:15px 30px;background:#333;color:#e0e0e0;border:none;border-radius:8px;cursor:pointer;transition:transform .2s,background .2s}button:hover{transform:scale(1.05);background:#4a4a4a}button:disabled{background:#555;color:#999;cursor:not-allowed}#countdown{font-size:1.3em;margin-bottom:10px}</style>` +
          `</head><body><h2>F.E.A.R - Forcefully Eliminating Advertising Redirects</h2><p>Click the button below to proceed.</p>` +
          `<div id="countdown"></div><button id="nextBtn">Next</button></body></html>`;

        const script = document.createElement('script');
        script.textContent = 'window.ock=true;';
        document.head.appendChild(script);

        (function waitForOck() {
          if (unsafeWindow.ock === true) {
            const dest = unsafeWindow.dest || '';
            const countdownEl = document.getElementById('countdown');
            const btn = document.getElementById('nextBtn');

            function hasHash(url) {
              try {
                return (unsafeWindow.dest.includes("hash="))
              } catch {
                return false;
              }
            }

            if (hasHash(dest)) {
              countdownEl.style.color = 'red';
              countdownEl.style.fontWeight = 'bold';
              let time = 8;
              countdownEl.textContent = `YOU HAVE EXACTLY ${time} SECONDS TO CLICK THE BUTTON BEFORE YOUR HASH EXPIRES`;
              const interval = setInterval(() => {
                time--;
                if (time > 0) {
                  countdownEl.textContent = `YOU HAVE EXACTLY ${time} SECONDS TO CLICK THE BUTTON BEFORE YOUR HASH EXPIRES`;
                } else {
                  countdownEl.textContent = `WELL DONE, NOW THE HASH IS INVALID AND IF YOU CLICK YOU WILL BE DETECTED, STARTING BYPASS AGAIN...`;
                  countdownEl.style.color = '';
                  countdownEl.style.fontWeight = '';
                  btn.disabled = true;
                  clearInterval(interval);
                  setTimeout(() => {
                      location.replace(location.href.split('?')[0]);
                  }, 3500);
                }
              }, 1000);
            } else {
              countdownEl.style.display = 'none';
            }

            btn.addEventListener('click', () => {
              if (!btn.disabled && unsafeWindow.dest) {
                window.location.href = unsafeWindow.dest;
              }
            });
          } else {
            setTimeout(waitForOck, 50);
          }
        })();

      } else {
        document.documentElement.innerHTML = `<h2>F.E.A.R - Forcefully Eliminating Advertising Redirects</h2>`;
        window.location.assign(decodeURIComponent(ref));
      }
      return;
    }

    if (location.hostname === 'rip.linkvertise.lol' && location.pathname === "/bypass") {
      notyf.information("Bypassing...");
      const success = await findHref();
      if (success) {
        notyf.success(`Redirecting...`);
        const redirect = p.get('url');
        const host = new URL(redirect).hostname;
        await sleep(2000);
        const bypassUrl = `https://${host}/cdn-cgi/trace?iwantreferrer=${encodeURIComponent(success)}`;
        window.location.href = bypassUrl;
      } else {
        console.log('Failed to find link');
      }
      return;
    }

    if (location.href.includes('https://trw.lat/?url=')) {
      await sleep(1000);
      const info = document.getElementById('information');
      if (info) info.click();
      notyf.information(`Redirecting in ${CONFIG.wait}s...`);
      let timeLeft = CONFIG.wait;
      const h1 = document.querySelector('body > div:nth-child(3) > h1');
      if (h1) {
        h1.textContent = `Redirecting in ${timeLeft}s...`;
        const countdown = setInterval(() => {
          timeLeft--;
          if (timeLeft <= 0) {
            clearInterval(countdown);
            h1.textContent = `Redirecting now...`;
          } else {
            h1.textContent = `Redirecting in ${timeLeft}s...`;
          }
        }, 1000);
      }
      await sleep(CONFIG.wait * 1000);
      const u = new URLSearchParams(location.search).get('url');
      window.location.href = `https://${CONFIG.site}${encodeURIComponent(u)}`;
      return;
    }
    if (CONFIG.SecureMode) {
        (function(){
          if(document.getElementById('fear-overlay')) return;
          const BYPASS='https://trw.lat/?url='+encodeURIComponent(location.href);
          const MAX_RETRIES=2;
          let retries=0, userChose=false;

          const makeStyle=()=>{
            const s=document.createElement('style');
            s.id='fear-overlay-style';
            s.textContent='#fear-overlay{position:fixed !important;inset:0 !important;z-index:2147483647 !important;display:flex !important;align-items:center !important;justify-content:center !important;pointer-events:auto !important;touch-action:none !important}#fear-overlay *{box-sizing:border-box !important;pointer-events:auto !important;touch-action:manipulation !important}#fear-panel{background:#0b1220 !important;color:#e6eef8 !important;padding:14px !important;border-radius:8px !important;max-width:92% !important;text-align:center !important;font-family:sans-serif !important}#fear-panel button{padding:8px 12px !important;margin:0 6px !important;border-radius:6px !important;border:0 !important;cursor:pointer !important;font-weight:600 !important}#fear-yes{background:#2ea44f;color:#04220d}#fear-no{background:#2d3a57;color:#e6eef8}#fear-status{margin-bottom:6px;font-size:12px;font-weight:600}';
            return s;
          };

          const create=()=>{
            if(document.getElementById('fear-overlay') || userChose) return;
            if(!document.getElementById('fear-overlay-style')) document.head.appendChild(makeStyle());

            const root=document.createElement('div');
            root.id='fear-overlay';
            root.setAttribute('role','dialog');
            root.setAttribute('aria-modal','true');
            Object.assign(root.style,{background:'rgba(0,0,0,.6)'});

            const panel=document.createElement('div');
            panel.id='fear-panel';
            panel.innerHTML='<div id="fear-status">Checking server...</div><h2 style="margin:0 0 8px">F.E.A.R - Forcefully Eliminating Advertising Redirects</h2><p style="margin:0 0 12px">Do you want to bypass this link?</p><div style="display:flex;gap:8px;justify-content:center;align-items:center"><button id="fear-yes" role="button" tabindex="0">Yes — Bypass</button><button id="fear-no" role="button" tabindex="0">No — Close</button></div><div style="font-size:12px;margin-top:8px;color:#9fb7d6">Esc to close</div>';

            root.appendChild(panel);
            document.body.appendChild(root);

            const prev=document.documentElement.style.overflow;
            document.documentElement.style.overflow='hidden';

            const cleanup=()=>{
              userChose=true;
              document.documentElement.style.overflow=prev||'';
              document.getElementById('fear-overlay')?.remove();
              mutation.disconnect();
            };

            const stopAndAct=(ev,fn)=>{try{ev.stopPropagation();}catch(e){}try{ev.preventDefault();}catch(e){}fn();};

            const yes=document.getElementById('fear-yes');
            const no=document.getElementById('fear-no');

            const onYes=ev=>stopAndAct(ev,()=>{cleanup(); location.assign(BYPASS);});
            const onNo=ev=>stopAndAct(ev,cleanup);

            yes.addEventListener('pointerdown',onYes,{capture:true});
            yes.addEventListener('click',onYes,{capture:true});
            yes.addEventListener('touchstart',onYes,{capture:true,passive:false});

            no.addEventListener('pointerdown',onNo,{capture:true});
            no.addEventListener('click',onNo,{capture:true});
            no.addEventListener('touchstart',onNo,{capture:true,passive:false});

            const onKey=e=>{
              if(e.key==='Escape') cleanup();
              if(e.key==='Enter'||e.key===' '){
                const active=document.activeElement;
                if(active===yes) onYes(e);
                if(active===no) onNo(e);
              }
            };
            document.addEventListener('keydown',onKey,{capture:true});

            const observer=new MutationObserver(()=>{
              if(!document.getElementById('fear-overlay')) document.removeEventListener('keydown',onKey,{capture:true}); observer.disconnect();
            });
            observer.observe(document.documentElement,{childList:true,subtree:true});

            const statusEl=document.getElementById('fear-status');
            fetch('https://trw.lat/api/status',{cache:'no-cache',redirect:'manual'})
              .then(r=>r.ok?r.json():Promise.reject(r))
              .then(json=>{
                if(json.status==='OK'){statusEl.textContent='Server OK'; statusEl.style.color='lime';}
                else{statusEl.textContent=`Server status: ${json.status}`; statusEl.style.color='yellow';}
              })
              .catch(()=>{statusEl.textContent='Servers Down'; statusEl.style.color='red';});
          };

          create();

          const mutation=new MutationObserver(()=>{
            if(!userChose && !document.getElementById('fear-overlay') && retries<MAX_RETRIES){
              retries++;
              setTimeout(create,300);
            } else if(retries>=MAX_RETRIES) mutation.disconnect();
          });
          mutation.observe(document.documentElement,{childList:true,subtree:true});
        })();
    } else{
        document.documentElement.innerHTML = `<h2>F.E.A.R - Forcefully Eliminating Advertising Redirects</h2>`;
        const bypassUrl = `https://trw.lat/?url=${encodeURIComponent(location.href)}`;
        window.location.assign(bypassUrl);
    }
  }

  (async () => {
    try {
      await main();
    } catch (e) {
      Log.e(`Init failed: ${e.message}`);
      notyf.error('Error occurred. Contact support.');
    }
  })();
})();
