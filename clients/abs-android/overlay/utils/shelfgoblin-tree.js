const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });
function metadata(item) { return item.media?.metadata || {}; }
function references(values, fallback) {
  return values?.length ? values.map(v => typeof v === 'string' ? { name: v, id: v } : v) : [{ name: fallback, id: `fallback:${fallback}`, fallback: true }];
}
function groupOrder(a, b) { return Number(a.standalone) - Number(b.standalone) || collator.compare(a.name, b.name); }
function buildTree(items, { groupBy = 'author', filter = 'all', search = '', progress = () => null, downloaded = () => false } = {}) {
  const groups = new Map();
  const term = search.trim().toLocaleLowerCase();
  for (const item of items) {
    const m = metadata(item);
    const authors = references(m.authors, m.authorName || 'Unknown author');
    const series = references(m.series, 'Standalone books');
    const p = progress(item) || {};
    if (filter === 'downloaded' && !downloaded(item)) continue;
    if (filter === 'progress' && (p.isFinished || !(p.progress > 0))) continue;
    if (term && ![m.title, ...authors.map(a => a.name), ...series.map(s => s.name)].join(' ').toLocaleLowerCase().includes(term)) continue;
    for (const outer of groupBy === 'author' ? authors : series) {
      const key = String(outer.id || outer.name);
      if (!groups.has(key)) groups.set(key, { key, name: outer.name, standalone: groupBy === 'series' && !!outer.fallback, branches: new Map(), ids: new Set() });
      const group = groups.get(key);
      group.ids.add(item.id);
      for (const inner of groupBy === 'author' ? series : authors) {
        const branchKey = String(inner.id || inner.name);
        if (!group.branches.has(branchKey)) group.branches.set(branchKey, { key: branchKey, name: inner.name, standalone: groupBy === 'author' && !!inner.fallback, books: [] });
        const sequence = groupBy === 'author' ? inner.sequence : outer.sequence;
        group.branches.get(branchKey).books.push({ item, sequence });
      }
    }
  }
  return [...groups.values()].map(g => ({ key: g.key, name: g.name, standalone: g.standalone, count: g.ids.size,
    branches: [...g.branches.values()].map(b => ({ ...b, books: b.books.sort((a, b) => {
      if (a.sequence == null && b.sequence != null) return 1;
      if (b.sequence == null && a.sequence != null) return -1;
      return collator.compare(String(a.sequence ?? ''), String(b.sequence ?? '')) || collator.compare(metadata(a.item).title || '', metadata(b.item).title || '');
    }) })).sort(groupOrder)
  })).sort(groupOrder);
}
module.exports = { buildTree, metadata };
