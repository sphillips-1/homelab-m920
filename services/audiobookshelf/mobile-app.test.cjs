const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync(`${__dirname}/mobile-app.js`, 'utf8');

function run({ ua = 'Android Chrome', path = '/audiobookshelf/', search = '',
  dismissed = false, platform = '', touch = 0, standalone = false, storageThrows = false } = {}) {
  const events = {};
  const result = { shown: false, html: '', removed: false, saved: false };
  const dialog = { showModal() { result.shown = true; }, close() {},
    addEventListener(name, fn) { events[name] = fn; } };
  const shadow = { set innerHTML(value) { result.html = value; },
    querySelector(selector) { return selector === 'dialog' ? dialog : {
      addEventListener(name, fn) { events[name] = fn; }
    }; } };
  const window = { matchMedia: () => ({ matches: standalone }) };
  window.self = window.top = window;
  vm.runInNewContext(source, { window,
    navigator: { userAgent: ua, platform, maxTouchPoints: touch },
    location: { pathname: path, search },
    sessionStorage: {
      getItem() { if (storageThrows) throw Error(); return dismissed; },
      setItem() { result.saved = true; }
    },
    document: { body: { appendChild() {} }, createElement() { return {
      attachShadow: () => shadow, remove() { result.removed = true; }
    }; } }
  });
  return { result, events };
}
test('offers platform-specific launch and store links', () => {
  for (const [ua, scheme, store] of [['Android Chrome', 'audiobookshelf://', 'play.google.com'],
    ['iPhone Safari', 'audiobooth://', 'apps.apple.com']]) {
    const { result } = run({ ua });
    assert.equal(result.shown, true);
    assert.ok(result.html.includes(scheme));
    assert.ok(result.html.includes(store));
  }
  assert.equal(run({ ua: 'Macintosh Safari', platform: 'MacIntel', touch: 5 }).result.shown, true);
});
test('does not interrupt desktop, auth, shares, webviews or dismissed sessions', () => {
  for (const options of [{ ua: 'Windows Chrome' }, { dismissed: true }, { standalone: true },
    { path: '/audiobookshelf/auth/openid/mobile-redirect' },
    { path: '/audiobookshelf/share/book' }, { search: '?code=secret&state=secret' },
    { ua: 'Android; wv) Chrome' }]) {
    assert.equal(run(options).result.shown, false, JSON.stringify(options));
  }
});
test('continue and Escape dismiss; blocked storage still permits prompt', () => {
  for (const event of ['click', 'cancel']) {
    const { result, events } = run({ storageThrows: true });
    assert.equal(result.shown, true);
    events[event]({ preventDefault() {} });
    assert.equal(result.removed, true);
    assert.equal(result.saved, true);
  }
});
