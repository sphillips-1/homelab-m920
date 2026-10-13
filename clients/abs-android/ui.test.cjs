// Browser acceptance checks against the real Vue screen with synthetic ABS data.
// Requires npm ci in upstream and Playwright available through normal resolution.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const root = __dirname;
const screen = fs.readFileSync(path.join(root, 'overlay/pages/bookshelf/library.vue'), 'utf8');
const template = screen.match(/<template>([\s\S]*?)<\/template>/)[1];
const script = screen.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '').replace(/^const \{ buildTree, metadata \}.*$/gm, '').replace('export default', 'return');
const treeScript = fs.readFileSync(path.join(root, 'overlay/utils/shelfgoblin-tree.js'), 'utf8').replace('module.exports = { buildTree, metadata };', '');
const css = screen.match(/<style scoped>([\s\S]*?)<\/style>/)[1];
(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_EXECUTABLE_PATH || undefined });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  try {
    await page.route('**/book_placeholder.jpg', route => route.abort());
    await page.setContent('<div id="app"></div>');
    await page.addStyleTag({ content: 'body{margin:0;background:#181b19;color:#ecf0e9;font:14px system-ui}*{box-sizing:border-box}button,input{font:inherit;color:inherit;background:transparent}a{color:inherit;text-decoration:none}h1,p{margin:0}:root{--color-fg:236 240 233}' + css });
    await page.addStyleTag({ path: path.join(root, 'overlay/assets/shelfgoblin-theme.css') });
    await page.evaluate(() => document.documentElement.dataset.theme = 'shelfgoblin');
    await page.addScriptTag({ path: path.join(root, 'upstream/node_modules/vue/dist/vue.js') });
    await page.evaluate(({ template, script, treeScript }) => {
      const factory = new Function('Capacitor', treeScript + '\n' + script);
      const component = factory({ convertFileSrc: url => url });
      component.template = template;
      const books = [
        { id: 'one', media: { duration: 3600, metadata: { title: 'The Way of Kings', authors: [{id:'a',name:'Brandon Sanderson'}], series:[{id:'s',name:'The Stormlight Archive',sequence:1}] } } },
        { id: 'two', media: { duration: 7200, metadata: { title: 'Words of Radiance', authors: [{id:'a',name:'Brandon Sanderson'}], series:[{id:'s',name:'The Stormlight Archive',sequence:2}] } } }
      ];
      const store = { state: { libraries: { currentLibraryId: 'library' } }, getters: {
        'libraries/getCurrentLibraryName': 'Audiobooks · Homelab', 'libraries/getCurrentLibraryMediaType': 'book',
        'user/getServerConnectionConfigId': 'connection', 'user/getUserMediaProgress': id => id === 'two' ? { progress:.38 } : {},
        'globals/getLocalMediaProgressById': () => null, 'globals/getLibraryItemCoverSrc': () => '/book_placeholder.jpg'
      } };
      Vue.prototype.$store = store;
      Vue.prototype.$db = { getLocalLibraryItems: async () => [{ id:'local_two', libraryItemId:'two', serverConnectionConfigId:'connection' }] };
      Vue.prototype.$nativeHttp = { get: async () => ({ results:books,total:2 }) };
      Vue.prototype.$eventBus = { $on() {}, $off() {} };
      Vue.component('nuxt-link', { props:['to'], template:'<a :href="to"><slot /></a>' });
      window.vm = new Vue(component).$mount('#app');
    }, { template, script, treeScript });
    await page.getByText('Brandon Sanderson', { exact: true }).first().waitFor();
    await page.locator('.goblin-author > summary').click();
    await page.locator('.goblin-branch summary').click();
    assert.equal(await page.locator('.goblin-book').count(), 2);
    await page.getByRole('button', { name: 'Downloaded', exact: true }).click();
    assert.equal(await page.locator('.goblin-book').count(), 1);
    assert.equal(await page.locator('.goblin-book').getAttribute('href'), '/localMedia/item/local_two');
    await page.getByRole('button', { name: 'Grouped by author. Switch grouping' }).click();
    assert.equal(await page.locator('.goblin-author > summary > span').textContent(), 'The Stormlight Archive');
    assert.equal(await page.getByRole('button', { name:'Downloaded',exact:true }).getAttribute('aria-pressed'), 'true');
    await page.getByRole('button', { name:'All books',exact:true }).click();
    await page.getByRole('searchbox').fill('way');
    assert.equal(await page.locator('.goblin-book').count(), 1);
    assert.equal(await page.locator('.goblin-book').getAttribute('href'), '/item/one');
    await page.getByRole('searchbox').fill('');
    await page.getByRole('button', { name:'In progress',exact:true }).click();
    assert.equal(await page.locator('.goblin-book').count(), 1);
    for (const width of [320,390,720]) {
      await page.setViewportSize({width,height:844});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `Overflow at ${width}px`);
    }
    assert.deepEqual(errors, []);
    assert.equal(await page.locator('body').evaluate(el => getComputedStyle(el).backgroundColor), 'rgb(244, 234, 215)');
    assert.equal(await page.locator('.goblin-library').evaluate(el => getComputedStyle(el).color), 'rgb(43, 27, 18)');
    assert.equal(await page.locator('.goblin-group').evaluate(el => getComputedStyle(el).color), 'rgb(255, 250, 240)');
    await page.evaluate(() => document.documentElement.dataset.theme = 'dark');
    assert.equal(await page.locator('body').evaluate(el => getComputedStyle(el).backgroundColor), 'rgb(24, 27, 25)');
    await page.evaluate(() => document.documentElement.dataset.theme = 'shelfgoblin');
    await page.setViewportSize({width:390,height:700});
    await page.getByRole('button', { name:'All books',exact:true }).click();
    await page.getByRole('button', { name:'Grouped by series. Switch grouping' }).click();
    await page.getByRole('searchbox').fill('Sanderson');
    fs.mkdirSync(path.join(root,'artifacts'), {recursive:true});
    await page.screenshot({path:path.join(root,'artifacts/shelfgoblin-theme-preview.png'),fullPage:true});
    console.log('Browser checks passed: expand, grouping, retained filter, download route, search, progress and responsive widths.');
  } finally { await browser.close() }
})().catch(e => { console.error(e); process.exitCode = 1 });
