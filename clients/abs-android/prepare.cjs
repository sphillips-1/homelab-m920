// Apply a reproducible overlay without committing third-party source or build state.
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const root = __dirname;
const checkout = path.join(root, 'upstream');
const revision = '609f9d644c8390fc662869e08ace18ce4a519b00';
const git = (...args) => execFileSync('git', args, { cwd: root, encoding: 'utf8' }).trim();
if (!fs.existsSync(path.join(checkout, '.git'))) {
  git('clone', 'https://github.com/advplyr/audiobookshelf-app.git', checkout);
}
if (git('-C', checkout, 'rev-parse', 'HEAD') !== revision) {
  if (git('-C', checkout, 'status', '--porcelain')) throw Error('Upstream has changes; refusing to change its revision.');
  git('-C', checkout, 'fetch', 'origin', revision);
  git('-C', checkout, 'checkout', '--detach', revision);
}
function transform(file, fn) {
  // Always transform the pinned source, so preparation is idempotent.
  const source = git('-C', checkout, 'show', `${revision}:${file}`);
  fs.writeFileSync(path.join(checkout, file), fn(source) + '\n');
}
const server = 'https://audiobooks.shelfgoblin.dev/audiobookshelf';
transform('components/connection/ServerConnectForm.vue', s => s
  .replaceAll('audiobookshelf://oauth', 'shelfgoblin://oauth')
  .replace("url.startsWith('shelfgoblin://oauth')", "urlObj.protocol === 'shelfgoblin:' && urlObj.hostname === 'oauth' && !urlObj.pathname && !urlObj.username && !urlObj.password && !urlObj.port")
  .replace('this.oauth.state !== state', '!this.oauth.state || this.oauth.state !== state')
  .replace("this.$router.replace('/bookshelf')", "this.$router.replace('/bookshelf/library')")
  .replaceAll('address: null,', `address: '${server}',`)
  .replace("address: '',", `address: '${server}',`)
  .replace('placeholder="http://55.55.55.55:13378"', `placeholder="${server}"`));
transform('capacitor.config.json', s => {
  const config = JSON.parse(s);
  config.appId = 'dev.shelfgoblin.abs'; config.appName = 'ShelfGoblin';
  config.plugins.StatusBar.backgroundColor = '#24140f';
  return JSON.stringify(config, null, 2);
});
// Keep the Java namespace so inherited native classes and resource imports work.
transform('android/app/build.gradle', s => s
  .replace('applicationId "com.audiobookshelf.app"', 'applicationId "dev.shelfgoblin.abs"')
  .replace('versionCode 121', "versionCode = (project.findProperty('shelfgoblinVersionCode') ?: '122').toInteger()")
  .replace('versionName "0.14.2-beta"', "versionName = (project.findProperty('shelfgoblinVersionName') ?: '0.14.2-shelfgoblin.2')")
  .replace('  buildTypes {', `  signingConfigs {
    debug {
      if (project.findProperty('shelfgoblinDebugKeystore')) {
        storeFile file(project.findProperty('shelfgoblinDebugKeystore'))
        storePassword 'android'
        keyAlias 'androiddebugkey'
        keyPassword 'android'
      }
    }
  }
  buildTypes {`));
for (const variant of ['main', 'debug']) transform(`android/app/src/${variant}/res/values/strings.xml`, s => s
  .replace('name="app_name">Audiobookshelf', 'name="app_name">ShelfGoblin')
  .replace('name="title_activity_main">Audiobookshelf', 'name="title_activity_main">ShelfGoblin')
  .replace('name="custom_url_scheme">audiobookshelf', 'name="custom_url_scheme">shelfgoblin'));
transform('pages/bookshelf.vue', s => s.replace('return this.isHome ||', "return (this.$route.name === 'bookshelf-library' && this.$store.getters['libraries/getCurrentLibraryMediaType'] === 'book') || this.isHome ||"));
transform('pages/index.vue', s => s.replace("redirect('/bookshelf')", "redirect('/bookshelf/library')"));
transform('nuxt.config.js', s => s
  .replace("'@/assets/app.css'", "'@/assets/app.css', '@/assets/shelfgoblin-theme.css'"));
transform('plugins/init.client.js', s => s.replace('  // Set theme', "  // Default to ShelfGoblin; restore an explicitly saved theme below.\n  document.documentElement.dataset.theme = 'shelfgoblin'\n  // Set theme"));
transform('pages/settings.vue', s => s
  .replace('    <!-- Playback settings -->', '    <settings-list-font-size />\n\n    <!-- Playback settings -->')
  .replace("theme: 'dark'", "theme: 'shelfgoblin'")
  .replace(/(themeOptionItems\(\)\s*\{\s*return\s*\[)/, "$1\n          { text: 'ShelfGoblin', value: 'shelfgoblin' },")
  .replace("|| 'dark'", "|| 'shelfgoblin'"));
transform('components/app/Appbar.vue', s => s.replace('src="/Logo.png"', 'src="/branding/shelfgoblin-favicon.svg" alt="ShelfGoblin"'));
transform('pages/connect.vue', s => s
  .replace('<div class="w-full h-full">', '<div class="w-full h-full shelfgoblin-connect">')
  .replace('src="/Logo.png" class="h-20 w-20 mb-2"', 'src="/branding/shelfgoblin-logo.svg" alt="ShelfGoblin" class="h-20 w-72 max-w-full mb-2"')
  .replace('<h1 class="text-2xl">audiobookshelf</h1>', '<h1 class="sr-only">ShelfGoblin</h1>')
  .replace('p-2 text-xl">audiobookshelf', 'p-2 text-xl">ShelfGoblin'));
const branding = path.join(root, '../../services/authentik/branding');
const brandOutput = path.join(checkout, 'static/branding');
fs.mkdirSync(brandOutput, { recursive: true });
for (const asset of ['shelfgoblin-logo.svg', 'shelfgoblin-favicon.svg', 'bookshelf-background.svg']) {
  fs.copyFileSync(path.join(branding, asset), path.join(brandOutput, asset));
}
require('./launcher-icon.cjs')(fs.readFileSync(path.join(branding, 'shelfgoblin-favicon.svg'), 'utf8'), checkout);
transform('android/app/src/main/AndroidManifest.xml', s => s
  .replace('@mipmap/ic_launcher_round', '@mipmap/shelfgoblin_launcher')
  .replace('@mipmap/ic_launcher', '@mipmap/shelfgoblin_launcher'));
fs.cpSync(path.join(root, 'overlay'), checkout, { recursive: true });
console.log(`ShelfGoblin prepared from ${revision}. Server: ${server}`);
