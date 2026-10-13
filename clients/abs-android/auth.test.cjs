const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, 'upstream/components/connection/ServerConnectForm.vue'), 'utf8');
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace('export default', 'return');
const component = new Function('Browser', 'CapacitorHttp', 'Dialog', script)({}, {}, {});
test('SSO accepts only the custom callback with matching pending state', async () => {
  for (const [url, pending, expected] of [
    ['shelfgoblin://oauth?code=example&state=pending', 'pending', true],
    ['audiobookshelf://oauth?code=example&state=pending', 'pending', false],
    ['shelfgoblin://oauth.evil?code=example&state=pending', 'pending', false],
    ['shelfgoblin://oauth/extra?code=example&state=pending', 'pending', false],
    ['shelfgoblin://oauth?code=example&state=wrong', 'pending', false],
    ['shelfgoblin://oauth?code=example', null, false]
  ]) {
    const calls = [];
    const vm = { oauth: { state: pending }, $toast: { error() {} }, oauthExchangeCodeForToken: async (...args) => calls.push(args) };
    await component.methods.appUrlOpen.call(vm, url);
    assert.equal(calls.length, expected ? 1 : 0, url);
  }
});
test('M920 defaults preserve base path and native Android registrations match', () => {
  assert.equal(component.data().serverConfig.address, 'https://audiobooks.shelfgoblin.dev/audiobookshelf');
  assert.ok(source.includes("encodeURIComponent('shelfgoblin://oauth')"));
  assert.ok(source.includes('code_challenge_method=S256'));
  for (const variant of ['main', 'debug']) {
    const strings = fs.readFileSync(path.join(__dirname, `upstream/android/app/src/${variant}/res/values/strings.xml`), 'utf8');
    assert.ok(strings.includes('name="custom_url_scheme">shelfgoblin'));
    assert.ok(strings.includes('name="app_name">ShelfGoblin'));
  }
  const config = JSON.parse(fs.readFileSync(path.join(__dirname, 'upstream/capacitor.config.json'), 'utf8'));
  assert.equal(config.appId, 'dev.shelfgoblin.abs');
});
