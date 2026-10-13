<template>
  <bookshelf-lazy-bookshelf v-if="isPodcast" page="books" />
  <section v-else class="goblin-library" :style="{ '--goblin-list-font-size': listFontSize + 'px' }">
    <header><h1>Library</h1><p>{{ libraryName }}</p>
      <label class="goblin-search"><span class="material-symbols" aria-hidden="true">search</span><input v-model="search" type="search" placeholder="Books, authors, series" aria-label="Search books, authors and series" /></label>
      <div class="goblin-filters" aria-label="Library filters">
        <button v-for="option in filters" :key="option.id" :aria-pressed="filter === option.id" @click="filter = option.id">{{ option.label }}</button>
        <button class="goblin-group" :aria-label="`Grouped by ${groupBy}. Switch grouping`" @click="toggleGrouping">{{ groupBy === 'author' ? 'Author' : 'Series' }} ⇄</button>
      </div>
    </header>
    <p v-if="loading" role="status">Loading library…</p>
    <div v-if="error" role="alert"><p>{{ error }}</p><button @click="load">Retry</button><nuxt-link to="/downloads">Open downloads</nuxt-link></div>
    <p v-if="!loading && !tree.length">No matching books.</p>
    <details v-for="group in tree" :key="groupBy + group.key" class="goblin-author" :open="!!search">
      <summary><span>{{ group.name }}<span v-if="group.recent" class="goblin-recent">Recent</span></span><small>{{ group.count }} books</small></summary>
      <div class="goblin-branch">
        <component :is="group.flattenAuthor ? 'div' : 'details'" v-for="branch in group.branches" :key="branch.key" :open="!!search">
          <summary v-if="!group.flattenAuthor"><span>{{ branch.name }}<span v-if="branch.recent" class="goblin-recent">Recent</span></span><small>{{ branch.books.length }} books</small></summary>
          <div class="goblin-books">
            <nuxt-link v-for="row in branch.books" :key="row.item.id" :to="bookRoute(row.item)" class="goblin-book">
              <span class="goblin-book-text"><strong>{{ row.sequence != null ? row.sequence + '. ' : '' }}{{ title(row.item) }}</strong><small v-if="!branch.hideBookAuthor">{{ author(row.item) }}</small><small>{{ duration(row.item) }} · {{ status(row.item) }}{{ localFor(row.item) ? ' · Downloaded' : '' }}</small><progress v-if="progressFor(row.item).progress > 0" :value="progressFor(row.item).progress" max="1" aria-label="Listening progress" /></span>
            </nuxt-link>
          </div>
        </component>
      </div>
    </details>
  </section>
</template>
<script>
import { Preferences } from '@capacitor/preferences'
const { buildTree, metadata } = require('@/utils/shelfgoblin-tree')
const { FONT_SIZE_KEY, DEFAULT_FONT_SIZE, normalizeFontSize } = require('@/utils/shelfgoblin-display')
export default {
  data: () => ({ items: [], localItems: [], loading: false, error: '', search: '', filter: 'all', groupBy: 'author', loadVersion: 0, listFontSize: DEFAULT_FONT_SIZE,
    filters: [{ id: 'all', label: 'All books' }, { id: 'downloaded', label: 'Downloaded' }, { id: 'progress', label: 'In progress' }] }),
  computed: {
    libraryId() { return this.$store.state.libraries.currentLibraryId },
    libraryName() { return this.$store.getters['libraries/getCurrentLibraryName'] },
    isPodcast() { return this.$store.getters['libraries/getCurrentLibraryMediaType'] === 'podcast' },
    connectionId() { return this.$store.getters['user/getServerConnectionConfigId'] },
    tree() { const catalog = this.$store.state.libraries.filterData || {}; return buildTree(this.items, { groupBy: this.groupBy, filter: this.filter, search: this.search, progress: this.progressFor, downloaded: item => !!this.localFor(item), authorCatalog: catalog.authors || [], seriesCatalog: catalog.series || [] }) }
  },
  watch: { libraryId() { this.load() }, connectionId() { this.load() } },
  methods: {
    applyFontSize(event) { this.listFontSize = normalizeFontSize(event.detail) },
    async readFontSize() { try { const { value } = await Preferences.get({ key: FONT_SIZE_KEY }); this.listFontSize = normalizeFontSize(value) } catch (_) {} },
    toggleGrouping() { this.groupBy = this.groupBy === 'author' ? 'series' : 'author'; try { localStorage.setItem('shelfgoblin-grouping', this.groupBy) } catch (_) {} },
    localFor(item) { return this.localItems.find(local => local.libraryItemId === item.id && local.serverConnectionConfigId === this.connectionId) },
    progressFor(item) { const local = this.localFor(item); const offline = local && this.$store.getters['globals/getLocalMediaProgressById'](local.id); const remote = this.$store.getters['user/getUserMediaProgress'](item.id); return offline && (!remote || Number(offline.lastUpdate || 0) >= Number(remote.lastUpdate || 0)) ? offline : remote || {} },
    bookRoute(item) { const local = this.localFor(item); return local ? `/localMedia/item/${local.id}` : `/item/${item.id}` },
    title(item) { return metadata(item).title || 'Untitled' },
    author(item) { const m = metadata(item); return m.authors?.map(a => a.name).join(', ') || m.authorName || 'Unknown author' },
    duration(item) { const hours = (item.media?.duration || 0) / 3600; return hours ? `${Math.floor(hours)}h ${Math.floor((hours % 1) * 60)}m` : 'Ebook' },
    status(item) { const p = this.progressFor(item); return p.isFinished ? 'Finished' : p.progress > 0 ? `${Math.round(p.progress * 100)}% listened` : 'Not started' },
    async refreshDownloads() { this.localItems = (await this.$db.getLocalLibraryItems()) || [] },
    async load() {
      const version = ++this.loadVersion;
      this.items = []; this.error = ''; this.loading = true;
      if (!this.libraryId || this.isPodcast) { this.loading = false; return }
      const id = this.libraryId;
      try {
        await this.refreshDownloads();
        const results = []; let page = 0;
        while (true) {
          const data = await this.$nativeHttp.get(`/api/libraries/${id}/items?limit=200&page=${page}`);
          if (version !== this.loadVersion) return;
          if (!Array.isArray(data.results)) throw new Error('Invalid library response');
          results.push(...data.results);
          if (!data.results.length || results.length >= data.total || data.results.length < 200) break;
          page++;
        }
        this.items = results;
      } catch (_) {
        if (version !== this.loadVersion) return;
        // Offline downloads remain accessible through the inherited Downloads screen.
        this.error = 'Could not load this library. Check your connection or sign in again. Downloaded books are available from Downloads.';
      } finally { if (version === this.loadVersion) this.loading = false }
    }
  },
  mounted() { try { if (localStorage.getItem('shelfgoblin-grouping') === 'series') this.groupBy = 'series' } catch (_) {}; window.addEventListener('shelfgoblin-font-size', this.applyFontSize); this.readFontSize(); this.$eventBus.$on('new-local-library-item', this.refreshDownloads); this.load() },
  beforeDestroy() { this.loadVersion++; window.removeEventListener('shelfgoblin-font-size', this.applyFontSize); this.$eventBus.$off('new-local-library-item', this.refreshDownloads) }
}
</script>
<style scoped>
.goblin-library{padding:20px 16px 100px;color:rgb(var(--color-fg));max-width:720px;margin:auto}
h1{font-size:26px;font-weight:500}header>p{opacity:.7;font-size:13px;margin:4px 0 16px}
.goblin-search{display:flex;align-items:center;gap:8px;background:rgba(127,127,127,.15);border-radius:24px;padding:12px 16px}.goblin-search input{background:transparent;flex:1;min-width:0;font-size:16px}
.goblin-filters{display:grid;grid-template-columns:minmax(0,.95fr) minmax(0,1.3fr) minmax(0,1.2fr) minmax(0,1.1fr);gap:6px;margin:16px 0}.goblin-filters button{border:1px solid rgba(127,127,127,.35);border-radius:10px;padding:10px 4px;min-width:0;min-height:44px;font-size:12px;overflow-wrap:anywhere}.goblin-filters button[aria-pressed=true]{background:rgba(110,160,100,.3)}.goblin-group{width:100%}
summary{display:flex;align-items:center;gap:8px;min-height:60px;list-style:none;cursor:pointer}summary::-webkit-details-marker{display:none}summary:before{content:'›';font-size:24px}details[open]>summary:before{content:'⌄'}summary>span{font-weight:500;flex:1}small{font-size:12px;opacity:.75}.goblin-author{border-bottom:1px solid rgba(127,127,127,.25)}.goblin-author>summary>span{font-size:18px}.goblin-branch,.goblin-books{margin-left:10px;padding-left:12px;border-left:1px solid rgba(127,127,127,.3)}.goblin-book{display:flex;gap:10px;align-items:center;padding:12px 0;min-height:64px}.goblin-book-text{display:flex;flex-direction:column;gap:3px;flex:1;min-width:0}.goblin-book strong{font-weight:500}.goblin-book progress{height:4px;width:100%;accent-color:#7ca976}button:focus-visible,input:focus-visible,a:focus-visible,summary:focus-visible{outline:2px solid #7ca976;outline-offset:3px}
.goblin-recent{display:inline-block;margin-left:8px;padding:2px 5px;border-radius:5px;font:11px system-ui;background:rgba(110,160,100,.15);color:inherit;vertical-align:middle;opacity:.8}
</style>
<style scoped>
.goblin-author summary>span,.goblin-book strong{font-size:var(--goblin-list-font-size,16px);overflow-wrap:anywhere;min-width:0}
.goblin-author>summary>span{font-size:calc(var(--goblin-list-font-size,16px) + 2px)}
.goblin-author small{font-size:max(12px,calc(var(--goblin-list-font-size,16px) * .75))}
.goblin-author summary{gap:8px;padding:8px 0}
.goblin-author summary small{flex-shrink:0}
.goblin-book-text{overflow-wrap:anywhere}
</style>
