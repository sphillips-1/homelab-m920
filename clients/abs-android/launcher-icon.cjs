// Convert the repository's simple SVG mark into native Android vector resources.
// Keep the SVG authoritative rather than maintaining a second copy of the art.
const fs = require('node:fs');
const path = require('node:path');
module.exports = (svg, checkout) => {
  const shapes = [...svg.matchAll(/<(path|circle)\b([^>]+)\/>/g)].map(([, tag, attrs]) => {
    const a = Object.fromEntries([...attrs.matchAll(/([\w-]+)="([^"]*)"/g)].map(m => [m[1], m[2]]));
    const { cx, cy, r } = a;
    const d = tag === 'path' ? a.d : `M${+cx - +r},${cy}a${r},${r} 0,1 0 ${2 * r},0a${r},${r} 0,1 0 ${-2 * r},0`;
    const attributes = { pathData: d, fillColor: a.fill || '#00000000', strokeColor: a.stroke, strokeWidth: a['stroke-width'], strokeLineJoin: a['stroke-linejoin'], fillAlpha: a['fill-opacity'] };
    return '    <path ' + Object.entries(attributes).filter(([, v]) => v != null).map(([k, v]) => `android:${k}="${v}"`).join(' ') + ' />';
  }).join('\n');
  if (!shapes) throw Error('ShelfGoblin SVG contains no supported artwork');
  const vector = (body, size) => `<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="${size}dp" android:height="${size}dp" android:viewportWidth="${size}" android:viewportHeight="${size}">\n${body}\n</vector>\n`;
  const write = (relative, content) => { const target = path.join(checkout, 'android/app/src/main/res', relative); fs.mkdirSync(path.dirname(target), { recursive: true }); fs.writeFileSync(target, content); };
  const background = '    <path android:fillColor="#2b1b12" android:pathData="M0,0h64v64H0z" />';
  write('mipmap-anydpi/shelfgoblin_launcher.xml', vector(background + '\n' + shapes, 64));
  // Inset the artwork so ears and book corners fit circular adaptive masks.
  write('drawable/shelfgoblin_foreground.xml', vector('  <group android:scaleX="0.9" android:scaleY="0.9" android:translateX="25.2" android:translateY="25.2">\n' + shapes + '\n  </group>', 108));
  const mono = shapes.replace(/android:(fillColor|strokeColor)="[^"]+"/g, (match, kind) => match.includes('#00000000') ? match : `android:${kind}="#ffffffff"`).replace(/ android:fillAlpha="[^"]+"/g, '');
  write('drawable/shelfgoblin_monochrome.xml', vector('  <group android:scaleX="0.9" android:scaleY="0.9" android:translateX="25.2" android:translateY="25.2">\n' + mono + '\n  </group>', 108));
  write('drawable/shelfgoblin_background.xml', '<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle"><solid android:color="#2b1b12" /></shape>\n');
  write('mipmap-anydpi-v26/shelfgoblin_launcher.xml', '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n  <background android:drawable="@drawable/shelfgoblin_background" />\n  <foreground android:drawable="@drawable/shelfgoblin_foreground" />\n  <monochrome android:drawable="@drawable/shelfgoblin_monochrome" />\n</adaptive-icon>\n');
};
