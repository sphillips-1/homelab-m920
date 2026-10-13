const collator = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });
function metadata(item) { return item.media?.metadata || {}; }
function references(values, fallback) {
  return values?.length ? values.map(v => typeof v === 'string' ? { name: v, id: v } : v) : [{ name: fallback, id: `fallback:${fallback}`, fallback: true }];
}
function groupOrder(a, b) { return Number(a.standalone) - Number(b.standalone) || collator.compare(a.name, b.name); }
function catalogNames(catalog) {
  return catalog.map(v => typeof v === 'string' ? {id:v,name:v} : v).filter(v => typeof v?.name === 'string' && v.name).sort((a,b) => b.name.length - a.name.length);
}
// ABS 2.36 library lists flatten relationships to "Name #sequence, Other #sequence".
// Match the library's canonical names first so commas inside a name are preserved.
function compactReferences(text, catalog, isSeries) {
  let remaining = typeof text === 'string' ? text.trim() : '';
  const result = [];
  while (remaining) {
    const known = catalog.find(v => remaining === v.name || remaining.startsWith(v.name + ', ') || (isSeries && remaining.startsWith(v.name + ' #')));
    if (known) {
      remaining = remaining.slice(known.name.length);
      let sequence = null;
      if (isSeries && remaining.startsWith(' #')) {
        remaining = remaining.slice(2);
        const end = remaining.indexOf(', ');
        sequence = end < 0 ? remaining : remaining.slice(0,end);
        remaining = end < 0 ? '' : remaining.slice(end);
      }
      result.push({...known, sequence});
      remaining = remaining.startsWith(', ') ? remaining.slice(2) : remaining;
    } else {
      const end = remaining.indexOf(', ');
      const entry = end < 0 ? remaining : remaining.slice(0,end);
      const split = isSeries ? entry.lastIndexOf(' #') : -1;
      const name = split < 0 ? entry : entry.slice(0,split);
      if (name) result.push({id:name,name,sequence:split < 0 ? null : entry.slice(split + 2)});
      remaining = end < 0 ? '' : remaining.slice(end + 2);
    }
  }
  return result;
}
function structuredReferences(value) { return Array.isArray(value) ? value : value?.name ? [value] : []; }
function buildTree(items, { groupBy = 'author', filter = 'all', search = '', progress = () => null, downloaded = () => false, authorCatalog = [], seriesCatalog = [] } = {}) {
  const groups = new Map();
  const term = search.trim().toLocaleLowerCase();
  const authorNames = catalogNames(authorCatalog), seriesNames = catalogNames(seriesCatalog);
  for (const item of items) {
    const m = metadata(item);
    const expandedAuthors = structuredReferences(m.authors), expandedSeries = structuredReferences(m.series);
    const authors = references(expandedAuthors.length ? expandedAuthors : compactReferences(m.authorName, authorNames, false), 'Unknown author');
    const series = references(expandedSeries.length ? expandedSeries : compactReferences(m.seriesName, seriesNames, true), 'Standalone books');
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
      const numeric = a.sequence != null && b.sequence != null && Number.isFinite(Number(a.sequence)) && Number.isFinite(Number(b.sequence));
      return (numeric ? Number(a.sequence) - Number(b.sequence) : collator.compare(String(a.sequence ?? ''), String(b.sequence ?? ''))) || collator.compare(metadata(a.item).title || '', metadata(b.item).title || '');
    }) })).sort(groupOrder)
  })).sort(groupOrder);
}
module.exports = { buildTree, metadata };
