'use strict';
const source = document.querySelector('#source');
const title = document.querySelector('#title');
const button = document.querySelector('#submit');
const message = document.querySelector('#message');
let downloads = [];
let busy = false;
let review = null;
let revision = 0;
let searchTimer;
let searchController;
let completedImports = '';
const author = document.querySelector('#author');
const manual = document.querySelector('#manual');
const reviewStatus = document.querySelector('#review-status');
const kind = document.querySelector('#kind');
const year = document.querySelector('#year');
function applyKind(value) {
  kind.value = value || 'audiobook';
  const video = kind.value !== 'audiobook';
  document.querySelector('#author-field').hidden = video;
  document.querySelector('#year-field').hidden = !video;
  const provider = document.querySelector('#provider');
  provider.replaceChildren(...(video ? [new Option('Jellyfin', 'jellyfin')] : [new Option('Audible', 'audible'), new Option('Google Books', 'google'), new Option('Open Library', 'openlibrary')]));
  document.querySelector('#transfer-policy').textContent = video ? 'Approval moves video/subtitles to Jellyfin, stops seeding and removes verified source files after publication. Rejection leaves the download untouched.' : 'Approval copies the audiobook to Audiobookshelf; the USB original stays available for seeding.';
  document.querySelector('#lookup-hint').textContent = video ? 'Search by title and optional release year, select the matching movie or series, then approve the move.' : 'Search by title, optionally narrow by author, and select the matching narrator and edition. A manual import requires an author.';
  document.querySelector('#manual-label').textContent = video ? 'I reviewed the title, year and episode naming; move without a provider match.' : 'I reviewed the entered author and title; import without a provider match.';
  button.textContent = video ? 'Approve and move to Jellyfin' : 'Approve and import';
}
year.addEventListener('input', prepareReview);
const approvalId = new URLSearchParams(location.search).get('review');
function updateButton() { button.disabled = !source.value || busy || (!review && !manual.checked); }
function invalidateReview() {
  clearTimeout(searchTimer);
  searchController?.abort();
  revision++; review = null; manual.checked = false;
  reviewStatus.textContent = 'Review metadata before importing.';
  document.querySelector('#matches').replaceChildren(); updateButton();
}
function prepareReview() {
  invalidateReview();
  if (!source.value || !title.value.trim()) return;
  reviewStatus.textContent = 'Preparing metadata suggestions…';
  searchTimer = setTimeout(searchMetadata, 700);
}
author.addEventListener('input', prepareReview);
title.addEventListener('input', prepareReview);
document.querySelector('#provider').addEventListener('change', prepareReview);
manual.addEventListener('change', () => {
  if (manual.checked) {
    invalidateReview(); manual.checked = true;
    reviewStatus.textContent = 'Manual metadata selected. Approve the import to continue.';
  }
  updateButton();
});
async function api(path, options) {
  const response = await fetch('/imports/api/' + path, options);
  if (response.redirected) throw new Error('Your session expired. Refresh to sign in again.');
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'The request failed.');
  return data;
}
async function loadDownloads() {
  const selected = source.value;
  downloads = await api('downloads');
  source.replaceChildren(new Option(downloads.length ? 'Choose media…' : 'No media awaiting import', ''));
  for (const item of downloads) source.add(new Option(item.source, item.source));
  if (downloads.some(item => item.source === selected)) source.value = selected;
  else if (selected) invalidateReview();
  updateButton();
  document.querySelector('#details').textContent = downloads.length ? 'Audio, movies and TV episodes. Extract archives and split movie packs first.' : 'Successfully imported downloads are hidden. New completed audiobooks will appear here after refreshing.';
}
source.addEventListener('change', () => {
  if (approvalId) {
    message.textContent = 'This page is linked to a review. Open Import audiobooks to choose a different download.';
    return;
  }
  const item = downloads.find(item => item.source === source.value);
  if (item) {
    applyKind(item.kind);
    year.value = item.year || '';
    title.value = item.title;
    document.querySelector('#details').textContent = (item.bytes / 1024 ** 3).toFixed(2) + ' GB · ' + (kind.value === 'audiobook' ? 'Original stays on USB.' : 'Original video/subtitles are removed after the approved move.');
  }
  prepareReview();
});
async function loadJobs() {
  const jobs = await api('jobs');
  busy = jobs.some(job => job.status === 'copying');
  const completed = jobs.filter(job => job.status === 'done').map(job => job.id).join(',');
  if (completed !== completedImports) {
    await loadDownloads();
    completedImports = completed;
  }
  updateButton();
  const container = document.querySelector('#jobs');
  container.replaceChildren();
  if (!jobs.length) { const p = document.createElement('p'); p.className = 'hint'; p.textContent = 'No imports yet.'; container.append(p); }
  for (const job of jobs) {
    const row = document.createElement('div'); row.className = 'job';
    const heading = document.createElement('strong'); heading.textContent = job.author + ' — ' + job.title;
    const detail = document.createElement('p'); detail.textContent = job.message;
    row.append(heading, detail);
    if (job.status === 'cleanup_required') {
      const finish = document.createElement('button'); finish.type = 'button'; finish.textContent = 'Finish move';
      finish.addEventListener('click', async () => {
        finish.disabled = true;
        try { await api('finish-move', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({job:job.id})}); await loadJobs(); }
        catch (error) { message.textContent = error.message; finish.disabled = false; }
      });
      row.append(finish);
    }
    container.append(row);
  }
}
async function searchMetadata() {
  if ((kind.value === 'audiobook' && !author.reportValidity()) || !title.reportValidity() || !year.reportValidity()) return;
  invalidateReview();
  const requestRevision = revision;
  searchController = new AbortController();
  const signal = searchController.signal;
  reviewStatus.textContent = kind.value === 'audiobook' ? 'Searching Audiobookshelf metadata…' : 'Searching Jellyfin metadata…';
  try {
    const matches = await api('metadata', {signal,method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:kind.value,year:year.value,author:author.value.trim(),title:title.value,provider:document.querySelector('#provider').value})});
    if (revision !== requestRevision) return;
    reviewStatus.textContent = matches.length ? 'Choose the metadata that matches this download.' : 'No matches found. Try another provider or explicitly confirm manual metadata.';
    const container = document.querySelector('#matches'); container.replaceChildren();
    for (const match of matches) {
      const card = document.createElement('article'); card.className = 'match';
      const heading = document.createElement('h3'); heading.textContent = match.metadata.title + (match.metadata.subtitle ? ' — ' + match.metadata.subtitle : '');
      const detail = document.createElement('p');
      detail.textContent = match.metadata.kind ? 'Year: ' + (match.metadata.year || 'Unknown') + ' | Provider IDs: ' + JSON.stringify(match.metadata.provider_ids) : ['Author: ' + match.metadata.authors.join(', '), 'Narrator: ' + (match.metadata.narrators?.join(', ') || 'Not supplied'), 'Series: ' + (match.metadata.series?.join(', ') || 'Not supplied'), 'Edition: ' + [match.metadata.publishedYear,match.metadata.publisher,match.metadata.language].filter(Boolean).join(' · '), match.metadata.asin ? 'ASIN: ' + match.metadata.asin : '', match.metadata.abridged === true ? 'Abridged' : match.metadata.abridged === false ? 'Unabridged' : ''].filter(Boolean).join(' | ');
      const description = document.createElement('p'); description.textContent = (match.metadata.description || '').slice(0,700);
      const choose = document.createElement('button'); choose.type = 'button'; choose.textContent = 'Use this metadata';
      choose.addEventListener('click', () => {
        review = match.id; manual.checked = false; author.value = match.author; title.value = match.title;
        if (match.metadata.kind) year.value = match.metadata.year || '';
        reviewStatus.textContent = 'Reviewed: ' + match.metadata.title + ' — ' + (match.metadata.kind ? 'Jellyfin ' + kind.value : match.metadata.authors.join(', ')) + '. This metadata will be saved with the imported copy.';
        container.replaceChildren(); updateButton();
      });
      card.append(heading,detail,description,choose); container.append(card);
    }
  } catch (error) {
    if (revision === requestRevision && error.name !== 'AbortError') reviewStatus.textContent = error.message;
  }
}
document.querySelector('#lookup').addEventListener('click', searchMetadata);
document.querySelector('#import-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (kind.value === 'audiobook' && !author.value.trim()) {
    message.textContent = 'Choose a metadata match or enter an author before importing.';
    return;
  }
  button.disabled = true;
  try {
    await api('import', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({source:source.value,kind:kind.value,year:year.value,author:author.value,title:title.value,review,manual:manual.checked,approval_id:approvalId})});
    message.textContent = 'Transfer started. You can leave this page; it continues on the server.';
    await loadJobs();
  } catch (error) { message.textContent = error.message; updateButton(); }
});
async function openReview() {
  if (!approvalId) return;
  const item = await api('reviews/' + encodeURIComponent(approvalId));
  document.querySelector('#review-evidence').hidden = false;
  document.querySelector('#review-context').textContent = item.source + ' · ' + item.status.replaceAll('_', ' ');
  document.querySelector('#review-data').textContent = JSON.stringify({files:item.files,existingMetadata:item.sidecar,proposedMatches:item.matches}, null, 2);
  if (!downloads.some(download => download.source === item.source)) {
    throw new Error('This download is no longer available for import. Check recent imports and source storage.');
  }
  source.value = item.source; source.disabled = true;
  applyKind(item.media_kind);
  year.value = item.matches[0]?.metadata?.year || '';
  author.value = item.matches[0]?.author || '';
  title.value = item.matches[0]?.title || item.source;
  prepareReview();
}
applyKind('audiobook');
Promise.all([loadDownloads(),loadJobs()]).then(openReview).catch(error => { message.textContent = error.message; });
setInterval(() => loadJobs().catch(error => { message.textContent = error.message; }), 5000);
