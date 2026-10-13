// Copy only native build inputs outside OneDrive when Gradle rejects cloud files.
// Usage: node stage-android.cjs <absolute-staging-directory>
const fs = require('node:fs');
const path = require('node:path');
const upstream = path.join(__dirname, 'upstream');
const destination = process.argv[2];
if (!destination || !path.isAbsolute(destination)) throw Error('An absolute staging directory is required.');
const stage = path.resolve(destination);
if (stage.startsWith(upstream + path.sep) || stage === upstream) throw Error('Staging must be separate from the upstream checkout.');
const copy = (from, to) => fs.cpSync(from, to, { recursive: true, dereference: true, filter: source => !['build', '.gradle', '.git'].includes(path.basename(source)) });
fs.mkdirSync(stage, { recursive: true });
copy(path.join(upstream, 'android'), path.join(stage, 'android'));
const settings = fs.readFileSync(path.join(upstream, 'android/capacitor.settings.gradle'), 'utf8');
for (const match of settings.matchAll(/new File\('([^']+)'\)/g)) {
  const from = path.resolve(upstream, 'android', match[1]);
  const relative = path.relative(upstream, from);
  if (!relative.startsWith('node_modules' + path.sep)) throw Error('Unexpected native module path.');
  copy(from, path.join(stage, relative));
}
console.log(`Native inputs staged at ${stage}`);
