const { test } = require('node:test');
const assert = require('node:assert/strict');
const { buildTree } = require('./overlay/utils/shelfgoblin-tree');
const book = (id, title, authors, series) => ({ id, media: { metadata: { title, authors, series } } });
const a = { id: 'a', name: 'Author A' }, b = { id: 'b', name: 'Author B' };
const s = sequence => ({ id: 's', name: 'Series', sequence });
test('numeric and fractional sequences sort before unnumbered books', () => {
  const tree = buildTree([book('ten', 'Ten', [a], [s('10')]), book('two', 'Two', [a], [s('2')]), book('half', 'Half', [a], [s('2.5')]), book('none', 'Extra', [a], [s(null)])]);
  assert.deepEqual(tree[0].branches[0].books.map(r => r.item.id), ['two', 'half', 'ten', 'none']);
});
test('coauthors and multi-series memberships remain discoverable without inflating counts', () => {
  const item = book('one', 'Shared', [a, b], [s(1), { id: 't', name: 'Other', sequence: 3 }]);
  const authors = buildTree([item]);
  assert.equal(authors.length, 2); assert.equal(authors[0].count, 1); assert.equal(authors[0].branches.length, 2);
  const series = buildTree([item], { groupBy: 'series' });
  assert.equal(series.length, 2); assert.equal(series[0].count, 1); assert.equal(series[0].branches.length, 2);
});
test('standalone and missing-author metadata produce valid branches', () => {
  const tree = buildTree([book('one', 'Solo', [], [])]);
  assert.equal(tree[0].name, 'Unknown author'); assert.equal(tree[0].branches[0].name, 'Standalone books');
});
test('named series sort alphabetically before the standalone bucket in both views', () => {
  const items = [book('solo', 'Solo', [a], []), book('z', 'Z', [a], [{id:'z',name:'Zodiac',sequence:1}]), book('t', 'T', [a], [{id:'t',name:'The Stormlight Archive',sequence:1}])];
  const expected = ['The Stormlight Archive', 'Zodiac', 'Standalone books'];
  assert.deepEqual(buildTree(items, {groupBy:'series'}).map(g => g.name), expected);
  assert.deepEqual(buildTree(items)[0].branches.map(g => g.name), expected);
  assert.deepEqual(buildTree(items, {groupBy:'series',search:'solo'}).map(g => g.name), ['Standalone books']);
});
test('a named series called Standalone books stays separate from the fallback bucket', () => {
  const tree = buildTree([book('solo','Solo',[a],[]),book('named','Named',[a],['Standalone books'])],{groupBy:'series'});
  assert.equal(tree.length,2);
  assert.equal(tree[0].standalone,false);
  assert.equal(tree[1].standalone,true);
});
test('search matches titles, authors and series; filters remove empty branches', () => {
  const items = [book('one', 'First', [a], [s(1)]), book('two', 'Other', [b], [])];
  for (const search of ['first', 'author a', 'series']) assert.equal(buildTree(items, { search })[0].count, 1);
  assert.equal(buildTree(items, { search: 'missing' }).length, 0);
  assert.equal(buildTree(items, { filter: 'downloaded', downloaded: i => i.id === 'two' })[0].name, 'Author B');
  assert.equal(buildTree(items, { filter: 'progress', progress: i => ({ progress: .4, isFinished: i.id === 'two' }) })[0].name, 'Author A');
});
