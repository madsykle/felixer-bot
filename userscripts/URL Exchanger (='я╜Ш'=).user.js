// ==UserScript==
// @name         URL Exchanger (='ｘ'=)
// @namespace    https://yuumari.com/
// @author       yuumari dev
// @copyright    2022+, yuumari dev (https://yuumari.com/)
// @description  the script will allows you to exchange to a next url automatically.
// @grant        GM_xmlhttpRequest
// @icon         https://yuumari.com/images/icon-userscript-64.png
// @include      /^https?:\/\/(baristakesehatan|baristakesehatan|comzom|e-mailku|indobo|jansamparks|lelmak|marketmarathi|sazwe|tamilroars|team2earn)\.com\//
// @include      /^https?:\/\/(suntechu|tech4auto|thetrendverse|tuktukgamer|tyrano-wealth|videolyrics)\.in\//
// @include      /^https?:\/\/(indiaurl)\.info\//
// @include      /^https?:\/\/(aradmag|flyfaucet)\.online\//
// @include      /^https?:\/\/(smartfine)\.site\//
// @include      /^https?:\/\/(101989|bicolink)\.xyz\//
// @include      /^https?:\/\/blog\.(scriptgrowagarden)\.com\//
// @include      /^https?:\/\/finance\.(chartvacancy)\.co\.in\//
// @include      /^https?:\/\/gold\.(tfker)\.com\//
// @include      /^https?:\/\/lnk\.(bloggingos)\.xyz\//
// @include      /^https?:\/\/mtc1\.(9to5equipment)\.com\//
// @include      /^https?:\/\/tech\.(pracagov)\.com\//
// @include      /^https?:\/\/test\.(mukhyamantriyojanadoot)\.com\//
// @include      /^https?:\/\/(anime)\.dutchycorp\.space\//
// @include      /^https?:\/\/(go|www.go)\.cutelink\.in\//
// @include      /^https?:\/\/(go\.)?link4earn\.in\//
// @license      MIT; https://opensource.org/licenses/MIT
// @run-at       document-start
// @version      1.96.1
// ==/UserScript==

+async function() {
  'use strict';
  const u = new Proxy(new URL(location.href), {
          get: (t, p) => {
            switch (p) {
              case 'path': {
                const normalized = Reflect.get(t, 'pathname').replace(/\/+/g, '/');
                const level = normalized.split('/');
                const compare = (h, n) => {
                        if (n instanceof RegExp) {
                          if (!n.test(h)) { return false; }
                        } else {
                          if (h !== n) { return false; }
                        }
                        return true;
                      };
                return {
                         normalized,
                         is: s => compare(normalized, s),
                         level,
                         level1: {
                           is: s => compare(level[1], s),
                           value: level[1] ?? null
                         },
                         root: normalized === '/'
                       };
              }
              case 'querys': return Reflect.get(t, 'search').slice(1);
              case 'hashId': return Reflect.get(t, 'hash').slice(1);
              case 'params': {
                const s = Reflect.get(t, 'searchParams');
                return {
                         ...Object.fromEntries(s),
                         _keys: [...s.keys()],
                         _key0: s.keys().next().value,
                         _vals: [...s.values()],
                         _val0: s.values().next().value
                       };
              }
              case 'request': return Reflect.get(t, 'pathname').slice(1) + Reflect.get(t, 'search') + Reflect.get(t, 'hash');
              default: return Reflect.get(t, p) ?? null;
            }
          }
        });
  const decode = s => {
          try {
            return atob(decodeURIComponent(s));
          } catch {
            return null;
          }
        };
  const where = (h, v) => v.every(x => x) ? v.map((mv, mi) => h[mi] + mv).concat(h.slice(v.length)).join('') : null;
  const go = (h, ...v) => {
          const l = where(h, v);
          if (!l) { return; }
          location.href = l;
        };
  const click = (h, ...v) => {
          const l = where(h, v);
          if (!l) { return; }
          const m = document.createElement('meta');
          m.name = 'referrer';
          m.content = 'origin';
          document.head.appendChild(m);
          const a = document.createElement('a');
          a.href = l;
          a.click();
        };
  const gmfetch = (url, o = {}) => {
          return new Promise(resolve => {
                   GM_xmlhttpRequest({
                     method: o?.method ?? 'GET',
                     url,
                     headers: o?.headers,
                     data: o?.data,
                     onload: res => {
                       resolve({
                         ok: res.status >= 200 && res.status < 300,
                         status: res.status,
                         text: () => res.responseText,
                         json: () => JSON.parse(res.responseText),
                         raw: res
                       });
                     }
                   });
                 });
        };
  const get = url => gmfetch(url);
  const post = (url, data) => {
          return gmfetch(url, {
            method: 'POST',
            data: new URLSearchParams(data),
            headers: {
              'content-type': 'application/x-www-form-urlencoded'
            }
          });
        };
  const sleep = (sec = 0) => {
          return new Promise(resolve => window.setTimeout(resolve, sec * 1000));
        };
  switch (u.hostname) {
    case 'suntechu.in': return u.path.is('/token.php') && click`https://web.urllinkshort.in/${u.params.post}`;
    case 'anime.dutchycorp.space': return u.path.is(/^\/redir[^\/]+\.php$/) && go`${u.params.code}?verif=0`;
    case 'comzom.com': // through
    case 'smartfine.site': return u.path.root && click`${u.params.link}`;
    case 'tech.pracagov.com': return u.path.is('/verify/') && click`${u.params._key0}`;
    case 'finance.chartvacancy.co.in': return u.path.is('/error404_bmOP786ev138.php') && go`https://tfushort.com/${u.params.link}`;
    case 'tamilroars.com': return u.path.root && click`https://userlinks.in/${u.params.adlinkfly}`;
    case 'jansamparks.com': return u.path.is('/verify.php') && click`${u.params.link}`;
    case 'tyrano-wealth.in': return u.path.root && go`https://tyrano-shortener.in/${u.params.adlinkfly}`;
    case 'tech4auto.in': return u.path.is('/folder.php') && click`https://inshorturl.com/${u.params.link}`;
    case 'mtc1.9to5equipment.com': return u.path.root && click`https://shortxlinks.com/${u.params.adlinkfly}`;
    case 'lelmak.com': return u.path.is('/safe.php') && go`https://up4cloud.com/${u.params.link}`;
    case 'team2earn.com': return u.path.root && go`https://link.webshortner.com/${u.params.adlinkfly}`;
    case 'test.mukhyamantriyojanadoot.com': return u.path.root && click`https://youlinks.in/${u.params.open ?? u.params.adlinkfly}`;
    case 'marketmarathi.com': return u.path.root && click`https://linkpays.in/${u.params.link}`;
    case 'go.cutelink.in': return u.path.root && click`https://cutelink.in/${u.params._key0}`;
    case 'indiaurl.info':
      if (u.path.root && u.params.go) {
        return click`https://indiaurl.xyz/${u.params.go}`;
      } else if (u.path.is('/token.php') && u.params.id) {
        return click`${decode(u.params.id)}`;
      }
      return;
    case 'thetrendverse.in': return u.path.root && click`https://e2share.in/${u.params.open}`;
    case 'sazwe.com': return u.path.is('/safe.php') && click`https://go.sazwe.com/${u.params.link}`;
    case 'aradmag.online': return u.path.is('/go.php') && click`https://horrorpay.online/${u.params.dex}`;
    case 'blog.scriptgrowagarden.com': return go`https://golink.bloggerishyt.in/${u.params.token}`;
    case 'indobo.com': return click`https://link.paid4link.com/${u.params.adlinkfly}`;

    // stop 3XX. (use header modifier)
    case 'baristakesehatan.com': return u.path.root && go`https://link.get4links.com/${u.params.adlinkfly}`;
    case 'videolyrics.in': return u.path.is('/lyricalweb/check') && go`https://cb.claimsatoshi.xyz/${u.params.p}`;
    case 'link4earn.in': // through
    case 'go.link4earn.in': return go`https://link4earn.com/${u.request}`;
    case 'gold.tfker.com': return u.path.root && click`https://xdabo.com/${u.params.cdf_plus}`;
    case 'lnk.bloggingos.xyz': return go`https://shrt.shortlinkdk.com/${u.request}`;
    case 'e-mailku.com': // through
    case 'bicolink.xyz': return go`https://go.bicolink.net/${u.request}`;
    case 'tuktukgamer.in': return u.path.is('/token.php') && click`${decode(u.params.id)}`;

    default: return;
  }
}``;
