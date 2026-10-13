<template>
  <section class="goblin-font-settings py-3" aria-label="List appearance">
    <div class="flex items-center justify-between gap-3">
      <label for="goblin-list-size">List font size</label>
      <output for="goblin-list-size">{{ fontSize }} px</output>
    </div>
    <input id="goblin-list-size" v-model.number="fontSize" type="range" :min="minimum" :max="maximum" step="1" :disabled="loading" @input="preview" @change="save" />
    <div class="flex items-center justify-between text-xs text-fg-muted"><span>Smaller</span><button type="button" :disabled="loading" @click="reset">Reset to default</button><span>Larger</span></div>
    <div class="goblin-font-preview" :style="{ '--goblin-list-font-size': fontSize + 'px' }" aria-label="List font size preview">
      <p class="goblin-preview-author">Brandon Sanderson</p>
      <p>The Stormlight Archive</p>
      <p>2. Words of Radiance</p>
    </div>
    <p class="text-xs text-fg-muted mt-2">Applies to authors, series, book titles and details in the library tree.</p>
    <p v-if="error" role="alert" class="text-error text-sm mt-2">{{ error }}</p>
  </section>
</template>
<script>
import { Preferences } from '@capacitor/preferences'
const { FONT_SIZE_KEY, DEFAULT_FONT_SIZE, MIN_FONT_SIZE, MAX_FONT_SIZE, normalizeFontSize } = require('@/utils/shelfgoblin-display')
export default {
  data: () => ({ fontSize: DEFAULT_FONT_SIZE, minimum: MIN_FONT_SIZE, maximum: MAX_FONT_SIZE, loading: true, error: '' }),
  methods: {
    preview() { this.fontSize = normalizeFontSize(this.fontSize); window.dispatchEvent(new CustomEvent('shelfgoblin-font-size', { detail: this.fontSize })) },
    async save() {
      this.preview(); this.error = '';
      try { await Preferences.set({ key: FONT_SIZE_KEY, value: String(this.fontSize) }) }
      catch (_) { this.error = 'Could not save the font size. Try again.' }
    },
    reset() { this.fontSize = DEFAULT_FONT_SIZE; this.save() }
  },
  async mounted() {
    try { const { value } = await Preferences.get({ key: FONT_SIZE_KEY }); this.fontSize = normalizeFontSize(value) }
    catch (_) { this.error = 'Could not load the saved font size. You can choose it again.' }
    finally { this.loading = false }
  }
}
</script>
<style scoped>
.goblin-font-settings input[type=range]{display:block;margin:0;width:100%;min-height:44px;accent-color:rgb(var(--color-track-cursor))}
.goblin-font-settings button{min-height:44px;text-decoration:underline}
.goblin-font-preview{margin-top:12px;padding:14px;border:1px solid rgb(var(--color-border));border-radius:10px;background:rgb(var(--color-secondary));font-size:var(--goblin-list-font-size,16px);overflow-wrap:anywhere}
.goblin-preview-author{font-size:calc(var(--goblin-list-font-size,16px) + 2px);font-family:Georgia,serif}
</style>
