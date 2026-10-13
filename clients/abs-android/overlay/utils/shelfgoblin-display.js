const FONT_SIZE_KEY = 'shelfgoblin-list-font-size';
const DEFAULT_FONT_SIZE = 16;
const MIN_FONT_SIZE = 14;
const MAX_FONT_SIZE = 24;
function normalizeFontSize(value) {
  const size = Number(value);
  return Number.isFinite(size) && size >= MIN_FONT_SIZE && size <= MAX_FONT_SIZE ? Math.round(size) : DEFAULT_FONT_SIZE;
}
module.exports = { FONT_SIZE_KEY, DEFAULT_FONT_SIZE, MIN_FONT_SIZE, MAX_FONT_SIZE, normalizeFontSize };
