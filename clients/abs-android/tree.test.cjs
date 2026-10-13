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
test('ABS 2.36 compact list metadata creates real series with numeric sequence', () => {
  const compact = (id,seriesName) => ({id,media:{metadata:{title:id,authorName:'Author A',seriesName}}});
  const items = [compact('later','Stormlight #2.5'),compact('earlier','Stormlight #2.05'),compact('solo','')];
  const tree = buildTree(items,{groupBy:'series',seriesCatalog:[{id:'s',name:'Stormlight'}],authorCatalog:[a]});
  assert.deepEqual(tree.map(g=>g.name),['Stormlight','Standalone books']);
  assert.equal(tree[0].key,'s');
  assert.deepEqual(tree[0].branches[0].books.map(r=>[r.item.id,r.sequence]),[['earlier','2.05'],['later','2.5']]);
  assert.deepEqual(buildTree(items,{groupBy:'series',search:'Stormlight'}).map(g=>g.name),['Stormlight']);
});
test('canonical names preserve commas and multiple relationships in compact metadata', () => {
  const seriesCatalog = [{id:'c',name:'A Series, With Commas'},{id:'x',name:'Other Series'}];
  const authorCatalog = [{id:'comma',name:'An Author, Jr.'},b];
  const item = {id:'book',media:{metadata:{title:'Book',authorName:'An Author, Jr., Author B',seriesName:'A Series, With Commas #1, Other Series #4'}}};
  const tree = buildTree([item],{groupBy:'series',seriesCatalog,authorCatalog});
  assert.deepEqual(tree.map(g=>g.name),['A Series, With Commas','Other Series']);
  assert.equal(tree[0].branches.length,2);
  assert.equal(tree[1].branches[0].books[0].sequence,'4');
});
test('search matches titles, authors and series; filters remove empty branches', () => {
  const items = [book('one', 'First', [a], [s(1)]), book('two', 'Other', [b], [])];
  for (const search of ['first', 'author a', 'series']) assert.equal(buildTree(items, { search })[0].count, 1);
  assert.equal(buildTree(items, { search: 'missing' }).length, 0);
  assert.equal(buildTree(items, { filter: 'downloaded', downloaded: i => i.id === 'two' })[0].name, 'Author B');
  assert.equal(buildTree(items, { filter: 'progress', progress: i => ({ progress: .4, isFinished: i.id === 'two' }) })[0].name, 'Author A');
});

test('recent author and series lead while other groups and book sequence stay sorted', () => {
  const items = [book('old','Old',[a],[s(1)]), book('recent','Recent',[b],[{id:'z',name:'Zebra',sequence:2}]), book('first','First',[b],[{id:'z',name:'Zebra',sequence:1}]), book('solo','Solo',[a],[])];
  const progress = item => item.id === 'recent' ? {progress:.3,lastUpdate:200} : item.id === 'old' ? {progress:.5,lastUpdate:100} : {};
  for (const groupBy of ['author','series']) {
    const tree = buildTree(items,{groupBy,progress});
    assert.equal(tree[0].name,groupBy === 'author' ? 'Author B' : 'Zebra');
    assert.equal(tree[0].recent,true); assert.equal(tree[0].branches[0].recent,true);
    assert.deepEqual(tree[0].branches[0].books.map(r=>r.item.id),['first','recent']);
    assert.equal(tree.slice(1).some(g=>g.recent),false);
    assert.equal(buildTree(items,{groupBy,progress,search:'Old'}).some(g=>g.recent),false);
  }
});
test('reset or invalid progress cannot become recent and finished books can', () => {
  const items=[book('a','A',[a],[]),book('b','B',[b],[])];
  assert.equal(buildTree(items,{progress:item=>item.id==='b'?{progress:0,lastUpdate:900}:{progress:.2,lastUpdate:100}})[0].name,'Author A');
  assert.equal(buildTree(items,{progress:()=>({progress:.2,lastUpdate:'bad'})}).some(g=>g.recent),false);
  assert.equal(buildTree(items,{progress:item=>item.id==='b'?{isFinished:true,lastUpdate:900}:{}})[0].name,'Author B');
});

test('single-author series hides redundant authors but mixed series stays branched after filtering', () => {
  const items=[book('one','One',[a],[s(1)]),book('two','Two',[a],[s(2)])];
  assert.equal(buildTree(items,{groupBy:'series'})[0].flattenBranch,true);
  assert.equal(buildTree(items)[0].branches[0].hideBookAuthor,true);
  items.push(book('three','Three',[b],[s(3)]));
  const filtered=buildTree(items,{groupBy:'series',search:'One'});
  assert.equal(filtered[0].flattenBranch,false);
  assert.equal(filtered[0].branches[0].hideBookAuthor,false);
  assert.equal(buildTree([book('solo','Solo',[a],[])],{groupBy:'series'})[0].flattenBranch,false);
  assert.equal(buildTree([book('unknown','Unknown',[],[s(1)])],{groupBy:'series'})[0].flattenBranch,false);
});

test('standalone-only authors open directly to books but mixed authors retain standalone branch', () => {
  const items=[book('solo','Solo',[a],[]),book('other','Other',[a],[])];
  assert.equal(buildTree(items)[0].flattenBranch,true);
  items.push(book('series','Series book',[a],[s(1)]));
  assert.equal(buildTree(items)[0].flattenBranch,false);
  assert.equal(buildTree(items,{search:'Solo'})[0].flattenBranch,false);
  assert.equal(buildTree([book('named','Named',[a],[{id:'named',name:'Standalone books'}])])[0].flattenBranch,false);
});
