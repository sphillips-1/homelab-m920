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
  if (!source.value || !author.value.trim() || !title.value.trim()) return;
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
  source.replaceChildren(new Option(downloads.length ? 'Choose an audiobook…' : 'No audiobooks awaiting import', ''));
  for (const item of downloads) source.add(new Option(item.source, item.source));
  if (downloads.some(item => item.source === selected)) source.value = selected;
  else if (selected) invalidateReview();
  updateButton();
  document.querySelector('#details').textContent = downloads.length ? 'MP3, M4B and other audio files. Extract ZIP or RAR archives before importing.' : 'Successfully imported downloads are hidden. New completed audiobooks will appear here after refreshing.';
}
source.addEventListener('change', () => {
  if (approvalId) {
    message.textContent = 'This page is linked to a review. Open Import audiobooks to choose a different download.';
    return;
  }
  const item = downloads.find(item => item.source === source.value);
  if (item) {
    title.value = item.title;
    document.querySelector('#details').textContent = (item.bytes / 1024 ** 3).toFixed(2) + ' GB · The original files stay on the USB.';
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
    row.append(heading, detail); container.append(row);
  }
}
async function searchMetadata() {
  if (!author.reportValidity() || !title.reportValidity()) return;
  invalidateReview();
  const requestRevision = revision;
  searchController = new AbortController();
  const signal = searchController.signal;
  reviewStatus.textContent = 'Searching Audiobookshelf metadata…';
  try {
    const matches = await api('metadata', {signal,method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({author:author.value,title:title.value,provider:document.querySelector('#provider').value})});
    if (revision !== requestRevision) return;
    reviewStatus.textContent = matches.length ? 'Choose the edition that matches your audio.' : 'No matches found. Try another provider or explicitly confirm manual metadata.';
    const container = document.querySelector('#matches'); container.replaceChildren();
    for (const match of matches) {
      const card = document.createElement('article'); card.className = 'match';
      const heading = document.createElement('h3'); heading.textContent = match.metadata.title + (match.metadata.subtitle ? ' — ' + match.metadata.subtitle : '');
      const detail = document.createElement('p');
      detail.textContent = ['Author: ' + match.metadata.authors.join(', '), 'Narrator: ' + (match.metadata.narrators?.join(', ') || 'Not supplied'), 'Series: ' + (match.metadata.series?.join(', ') || 'Not supplied'), 'Edition: ' + [match.metadata.publishedYear,match.metadata.publisher,match.metadata.language].filter(Boolean).join(' · '), match.metadata.asin ? 'ASIN: ' + match.metadata.asin : '', match.metadata.abridged === true ? 'Abridged' : match.metadata.abridged === false ? 'Unabridged' : ''].filter(Boolean).join(' | ');
      const description = document.createElement('p'); description.textContent = (match.metadata.description || '').slice(0,700);
      const choose = document.createElement('button'); choose.type = 'button'; choose.textContent = 'Use this metadata';
      choose.addEventListener('click', () => {
        review = match.id; manual.checked = false; author.value = match.author; title.value = match.title;
        reviewStatus.textContent = 'Reviewed: ' + match.metadata.title + ' — ' + match.metadata.authors.join(', ') + '. This metadata will be saved with the imported copy.';
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
  event.preventDefault(); button.disabled = true;
  try {
    await api('import', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({source:source.value,author:author.value,title:title.value,review,manual:manual.checked,approval_id:approvalId})});
    message.textContent = 'Import started. You can leave this page; the copy continues on the server.';
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
  author.value = item.matches[0]?.author || '';
  title.value = item.matches[0]?.title || item.source;
  prepareReview();
}
Promise.all([loadDownloads(),loadJobs()]).then(openReview).catch(error => { message.textContent = error.message; });
setInterval(() => loadJobs().catch(error => { message.textContent = error.message; }), 5000);
