(() => {
  'use strict';
  const ua = navigator.userAgent;
  const android = /Android/i.test(ua);
  const ios = /iPhone|iPad|iPod/i.test(ua) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  if (!android && !ios) return;
  // Never interrupt OAuth callbacks, public shares or embedded app sign-in.
  if (/\/(auth|share|public)(\/|$)/i.test(location.pathname) ||
      /[?&](code|state|error|token)=/i.test(location.search) ||
      /; wv\)|Audiobookshelf|AudioBooth/i.test(ua) ||
      window.self !== window.top) return;
  if (window.matchMedia('(display-mode: standalone)').matches || navigator.standalone) return;
  const key = 'homelab-mobile-app-dismissed';
  try { if (sessionStorage.getItem(key)) return; } catch (_) { /* storage optional */ }

  const name = android ? 'Audiobookshelf' : 'AudioBooth';
  const store = android
    ? 'https://play.google.com/store/apps/details?id=com.audiobookshelf.app'
    : 'https://apps.apple.com/app/id6753017503';
  // Launch only: do not pass browser credentials or pretend both clients
  // support opening arbitrary server/book URLs.
  const launch = android ? 'audiobookshelf://' : 'audiobooth://';
  const host = document.createElement('div');
  const shadow = host.attachShadow({ mode: 'open' });
  shadow.innerHTML = `
    <style>
      dialog { box-sizing:border-box; width:calc(100% - 32px); max-width:390px;
        border:1px solid #58504a; border-radius:18px; padding:24px;
        background:#211e1b; color:#fff; font:16px/1.5 system-ui,sans-serif; }
      dialog::backdrop { background:rgb(0 0 0 / 65%); }
      h2 { font-size:23px; line-height:1.2; margin:0 0 12px; }
      p { color:#ddd6cf; } a,button { box-sizing:border-box; display:block;
        width:100%; margin-top:12px; padding:12px; border-radius:9px;
        text-align:center; font:inherit; cursor:pointer; }
      a { color:#211e1b; background:#f3bd7a; text-decoration:none; }
      .store { background:transparent; color:#f3bd7a; }
      button { background:transparent; color:white; border:1px solid #81766c; }
    </style>
    <dialog aria-labelledby="title" aria-describedby="description">
      <h2 id="title">Open in ${name}?</h2>
      <p id="description">Listen in the app on your ${android ? 'Android device' : 'iPhone or iPad'}. Sign in to your server in the app if you haven’t already.</p>
      <a href="${launch}">Open ${name}</a>
      <a class="store" href="${store}" target="_blank" rel="noopener noreferrer">Get the app</a>
      <button type="button">Continue in browser</button>
    </dialog>`;
  document.body.appendChild(host);
  const dialog = shadow.querySelector('dialog');
  const dismiss = () => {
    try { sessionStorage.setItem(key, '1'); } catch (_) { /* storage optional */ }
    dialog.close();
    host.remove();
  };
  shadow.querySelector('button').addEventListener('click', dismiss);
  dialog.addEventListener('cancel', (event) => { event.preventDefault(); dismiss(); });
  dialog.showModal();
})();
