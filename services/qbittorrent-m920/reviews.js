'use strict';
async function loadReviews() {
  const response = await fetch('/imports/api/reviews');
  if (response.redirected) throw new Error('Refresh to sign in again.');
  if (!response.ok) throw new Error('Unable to load metadata reviews.');
  const rows = await response.json();
  const list = document.querySelector('#review-list');
  list.replaceChildren();
  if (!rows.length) list.textContent = 'No audiobooks awaiting manual review.';
  for (const row of rows) {
    const article = document.createElement('article'); article.className = 'job';
    const link = document.createElement('a');
    link.href = '/imports/?review=' + encodeURIComponent(row.id);
    link.textContent = row.source;
    const status = document.createElement('p'); status.textContent = row.status.replaceAll('_', ' ');
    article.append(link, status); list.append(article);
  }
}
loadReviews().catch(error => { document.querySelector('#review-error').textContent = error.message; });
