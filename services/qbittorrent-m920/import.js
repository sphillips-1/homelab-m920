'use strict';
const source = document.querySelector('#source');
const title = document.querySelector('#title');
const button = document.querySelector('#submit');
const message = document.querySelector('#message');
let downloads = [];
let busy = false;
async function api(path, options) {
  const response = await fetch('/imports/api/' + path, options);
  if (response.redirected) throw new Error('Your session expired. Refresh to sign in again.');
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'The request failed.');
  return data;
}
async function loadDownloads() {
  downloads = await api('downloads');
  source.replaceChildren(new Option(downloads.length ? 'Choose an audiobook…' : 'No completed audiobooks yet', ''));
  for (const item of downloads) source.add(new Option(item.source, item.source));
  document.querySelector('#details').textContent = downloads.length ? 'MP3, M4B and other audio files. Extract ZIP or RAR archives before importing.' : 'Completed audiobook downloads will appear here. Refresh after a download finishes.';
}
source.addEventListener('change', () => {
  const item = downloads.find(item => item.source === source.value);
  if (item) {
    title.value = item.title;
    document.querySelector('#details').textContent = (item.bytes / 1024 ** 3).toFixed(2) + ' GB · The original files stay on the USB.';
  }
  button.disabled = !item || busy;
});
async function loadJobs() {
  const jobs = await api('jobs');
  busy = jobs.some(job => job.status === 'copying');
  button.disabled = !source.value || busy;
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
document.querySelector('#import-form').addEventListener('submit', async event => {
  event.preventDefault(); button.disabled = true;
  try {
    await api('import', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({source:source.value,author:document.querySelector('#author').value,title:title.value})});
    message.textContent = 'Import started. You can leave this page; the copy continues on the server.';
    await loadJobs();
  } catch (error) { message.textContent = error.message; button.disabled = busy || !source.value; }
});
Promise.all([loadDownloads(),loadJobs()]).catch(error => { message.textContent = error.message; });
setInterval(() => loadJobs().catch(error => { message.textContent = error.message; }), 5000);
