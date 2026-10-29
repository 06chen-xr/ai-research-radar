const PAGE_SIZE = 12;
const CATEGORY_LABELS = {
  all: 'All updates',
  'ai-researcher': 'AI research & thinking',
  'ai-engineering': 'AI engineering & agents',
  'ai-company': 'AI labs & companies',
  'ai-academic': 'Academic research',
  'quant-firm': 'Quant firms',
  interviews: 'Interviews & talks',
  'ai-community': 'Research communities'
};
const QUALITY_LABELS = { core: 'Core source', selected: 'Selected source', watchlist: 'Watchlist' };
const QUALITY_RANK = { core: 0, selected: 1, watchlist: 2 };
const TYPE_LABELS = {
  'personal-blog': 'Personal blog', 'personal-site': 'Personal site', newsletter: 'Newsletter',
  'official-blog': 'Official blog', 'official-site': 'Official site', 'research-blog': 'Research blog',
  'research-index': 'Research index', 'research-publication': 'Research publication', community: 'Community', podcast: 'Podcast'
};
const state = { articles: [], sources: [], statuses: {}, view: 'articles', category: 'all', page: 1, query: '', tier: 'all', sort: 'newest', sourceQuery: '', sourceCategory: 'all', sourceTier: 'all', includeInactiveSources: false };
const $ = (id) => document.getElementById(id);

function escapeHTML(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function safeUrl(value) {
  try { const u = new URL(value, window.location.href); return ['http:', 'https:'].includes(u.protocol) ? u.href : '#'; } catch { return '#'; }
}
function formatDate(value) {
  if (!value) return 'Publication date unknown';
  const d = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return 'Publication date unknown';
  return new Intl.DateTimeFormat('en', { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC' }).format(d);
}
function formatRunDate(value) {
  if (!value) return 'Not collected yet';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return 'Not collected yet';
  return new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }).format(d) + ' UTC';
}
function displayCategory(category) { return CATEGORY_LABELS[category] || 'Other sources'; }
function hasNonEnglishScript(value) { return /[\u3400-\u4DBF\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF\u0400-\u052F\u0590-\u05FF\u0600-\u06FF\u0E00-\u0E7F\u0900-\u097F]/u.test(String(value || '')); }
function isEnglishArticle(article) { return (article.language || 'en') === 'en' && !hasNonEnglishScript(article.title || ''); }
function isActiveEnglishSource(source) { return source.language === 'en' && source.enabled !== false && !hasNonEnglishScript(source.name || ''); }
function updateView(view) {
  state.view = view;
  document.querySelectorAll('.view').forEach(el => el.classList.toggle('active-view', el.id === `view-${view}`));
  document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.view === view));
  $('breadcrumb-current').textContent = ({ articles: 'Daily radar', sources: 'Source directory', about: 'About this project' })[view] || 'Daily radar';
  if (view === 'sources') renderSources();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
function updateCategory(category) {
  state.category = category;
  state.page = 1;
  document.querySelectorAll('.topic-item').forEach(el => el.classList.toggle('active', el.dataset.category === category));
  renderArticles();
}
function articleMatches(article) {
  if (state.category !== 'all' && article.category !== state.category) return false;
  if (state.tier !== 'all' && article.tier !== state.tier) return false;
  const query = state.query.trim().toLowerCase();
  if (query) {
    const haystack = [article.title, article.source_name, article.source_type, ...(article.topics || [])].join(' ').toLowerCase();
    if (!haystack.includes(query)) return false;
  }
  return true;
}
function getFilteredArticles() {
  const articles = state.articles.filter(articleMatches);
  articles.sort((a, b) => {
    if (state.sort === 'source') return String(a.source_name || '').localeCompare(String(b.source_name || ''));
    return String(b.published_at || b.discovered_at || '').localeCompare(String(a.published_at || a.discovered_at || ''));
  });
  return articles;
}
function renderArticles() {
  const filtered = getFilteredArticles();
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  state.page = Math.min(state.page, pages);
  const start = (state.page - 1) * PAGE_SIZE;
  const items = filtered.slice(start, start + PAGE_SIZE);
  $('feed-heading').textContent = state.category === 'all' ? 'Latest articles' : displayCategory(state.category);
  $('result-count').textContent = `${filtered.length} ${filtered.length === 1 ? 'item' : 'items'}`;
  $('active-filter-row').querySelector('.filter-context').textContent = state.category === 'all' ? 'Showing all tracked topics' : `Filtered by ${displayCategory(state.category)}`;
  $('clear-filters').classList.toggle('hidden', state.category === 'all' && !state.query && state.tier === 'all');
  const list = $('article-list');
  if (!state.articles.length) {
    list.innerHTML = `<div class="empty-state"><strong>The article index is waiting for its first collection.</strong><p>The source directory is ready. Once you push the project and run the GitHub Actions workflow, collected titles and original links will appear here. No AI API is required.</p></div>`;
  } else if (!items.length) {
    list.innerHTML = `<div class="empty-state"><strong>No articles match these filters.</strong><p>Try another topic, remove the company tier filter, or search for a different term.</p><button class="page-button" id="empty-clear">Clear filters</button></div>`;
    $('empty-clear')?.addEventListener('click', clearFilters);
  } else {
    list.innerHTML = items.map(article => {
      const category = article.category || 'other';
      const topics = (article.topics || []).slice(0, 4).map(topic => `<span class="article-tag">${escapeHTML(topic.replaceAll('-', ' '))}</span>`).join('');
      const pubDate = article.published_at ? formatDate(article.published_at) : `Date unknown · indexed ${formatDate(article.discovered_at)}`;
      const tier = article.tier ? `<span class="tier-pill">${escapeHTML(article.tier)}</span>` : '';
      const quality = article.source_quality ? `<span class="quality-pill quality-${escapeHTML(article.source_quality)}">${escapeHTML(QUALITY_LABELS[article.source_quality] || article.source_quality)}</span>` : '';
      const type = TYPE_LABELS[article.source_type] || article.source_type || 'Source';
      return `<article class="article-card">
        <div class="article-main">
          <div class="article-meta"><span class="category-pill category-${escapeHTML(category)}">${escapeHTML(displayCategory(category))}</span>${quality}${tier}<span class="type-pill">${escapeHTML(type)}</span><span class="article-date">${escapeHTML(pubDate)}</span></div>
          <a class="article-title" href="${escapeHTML(safeUrl(article.url))}" target="_blank" rel="noopener noreferrer">${escapeHTML(article.title)}</a>
          <div class="article-subline"><span>From <strong>${escapeHTML(article.source_name || 'Unknown source')}</strong></span><span>·</span><a href="${escapeHTML(safeUrl(article.source_url || article.url))}" target="_blank" rel="noopener noreferrer">Source home ↗</a></div>
          ${topics ? `<div class="article-tags">${topics}</div>` : ''}
        </div>
        <a class="article-open" href="${escapeHTML(safeUrl(article.url))}" target="_blank" rel="noopener noreferrer" aria-label="Open original article">↗</a>
      </article>`;
    }).join('');
  }
  const pagination = $('pagination');
  pagination.classList.toggle('hidden', filtered.length <= PAGE_SIZE);
  $('pagination-label').textContent = `Page ${state.page} of ${pages}`;
  $('prev-page').disabled = state.page <= 1;
  $('next-page').disabled = state.page >= pages;
}
function clearFilters() {
  state.category = 'all'; state.query = ''; state.tier = 'all'; state.page = 1;
  $('search-input').value = ''; $('tier-filter').value = 'all';
  document.querySelectorAll('.topic-item').forEach(el => el.classList.toggle('active', el.dataset.category === 'all'));
  renderArticles();
}
function sourceStatus(source) { return state.statuses[source.id] || null; }
function sourceMatches(source) {
  // The default directory is English-only. Non-English sources never appear,
  // even when the user chooses to inspect paused/pending English candidates.
  if ((source.language || 'en') !== 'en' || hasNonEnglishScript(source.name || '')) return false;
  if (!state.includeInactiveSources && !isActiveEnglishSource(source)) return false;
  if (state.sourceCategory !== 'all' && source.category !== state.sourceCategory) return false;
  if (state.sourceTier !== 'all' && source.tier !== state.sourceTier) return false;
  const query = state.sourceQuery.trim().toLowerCase();
  if (!query) return true;
  return [source.name, source.description, source.url, source.tier, ...(source.topics || [])].join(' ').toLowerCase().includes(query);
}
function renderSources() {
  const filtered = state.sources.filter(sourceMatches).sort((a, b) => {
    const tierA = Number((a.tier || '').replace('Tier ', '')) || 99;
    const tierB = Number((b.tier || '').replace('Tier ', '')) || 99;
    if (state.sourceCategory === 'all' && state.sourceTier === 'all') return (QUALITY_RANK[a.source_quality] ?? 9) - (QUALITY_RANK[b.source_quality] ?? 9) || tierA - tierB || a.name.localeCompare(b.name);
    return a.name.localeCompare(b.name);
  });
  const englishSources = state.sources.filter(source => (source.language || 'en') === 'en' && !hasNonEnglishScript(source.name || ''));
  const activeCount = englishSources.filter(isActiveEnglishSource).length;
  const inactiveCount = englishSources.length - activeCount;
  $('source-summary').textContent = state.includeInactiveSources ? `${filtered.length} shown · ${activeCount} curated English sources · ${inactiveCount} paused/pending English sources included.` : `${filtered.length} curated English sources shown · ${inactiveCount} unapproved English sources hidden.`;
  $('source-list').innerHTML = filtered.map(source => {
    const status = sourceStatus(source);
    let statusLabel = source.enabled === false ? (source.review_status === 'pending' ? 'Pending review' : 'Paused') : 'Not checked yet'; let statusClass = '';
    if (source.enabled !== false && status?.status === 'ok') { statusLabel = `${status.articles_found} found`; statusClass = 'ok'; }
    else if (source.enabled !== false && status?.status === 'error') statusLabel = 'Fetch error';
    else if (source.enabled !== false && status?.status === 'directory-only') statusLabel = 'Directory only';
    else if (source.enabled !== false && status?.status === 'robots-disallowed') statusLabel = 'Robots disallow';
    else if (source.enabled !== false && status?.status === 'no-content') statusLabel = 'No new items';
    const topics = (source.topics || []).slice(0, 3).map(topic => `<span class="source-topic">${escapeHTML(topic.replaceAll('-', ' '))}</span>`).join('');
    const tier = source.tier ? `<span class="tier-pill">${escapeHTML(source.tier)}</span>` : '';
    const sourceType = TYPE_LABELS[source.source_type] || source.source_type || 'Source';
    const quality = QUALITY_LABELS[source.source_quality] || 'Watchlist';
    const qualityClass = `quality-${source.source_quality || 'watchlist'}`;
    const monogram = escapeHTML((source.name || 'RR').split(/\s+/).slice(0, 2).map(x => x[0] || '').join('').toUpperCase());
    return `<article class="source-card"><div class="source-card-head"><div class="source-monogram">${monogram}</div><div class="source-name-wrap"><a class="source-name" href="${escapeHTML(safeUrl(source.url))}" target="_blank" rel="noopener noreferrer">${escapeHTML(source.name)}</a><span class="source-url">${escapeHTML(source.url)}</span></div><span class="source-status ${statusClass}">${escapeHTML(statusLabel)}</span></div><p class="source-description">${escapeHTML(source.description || '')}</p><div class="source-topics">${topics}</div><div class="source-card-bottom"><span class="source-bottom-meta">${escapeHTML(sourceType)} ${tier ? '· ' + escapeHTML(source.tier) : ''}</span><span class="quality-pill ${qualityClass}">${escapeHTML(quality)}</span><a class="source-link" href="${escapeHTML(safeUrl(source.url))}" target="_blank" rel="noopener noreferrer">Visit source ↗</a></div></article>`;
  }).join('') || `<div class="empty-state"><strong>No sources match.</strong><p>Try another search term or remove a filter.</p></div>`;
}
async function loadData() {
  $('article-list').innerHTML = '<div class="loading-state"><span class="spinner"></span>Loading article index…</div>';
  try {
    const [articlesResponse, sourcesResponse, statusResponse] = await Promise.all([
      fetch('data/articles.json', { cache: 'no-store' }),
      fetch('data/sources.json', { cache: 'no-store' }),
      fetch('data/collector_status.json', { cache: 'no-store' })
    ]);
    if (!articlesResponse.ok || !sourcesResponse.ok) throw new Error('Data files are unavailable');
    const articlesPayload = await articlesResponse.json();
    const sourcesPayload = await sourcesResponse.json();
    const statusPayload = statusResponse.ok ? await statusResponse.json() : {};
    state.sources = sourcesPayload.sources || [];
    const activeSourceIds = new Set(state.sources.filter(isActiveEnglishSource).map(source => source.id));
    state.articles = (articlesPayload.articles || []).filter(article => activeSourceIds.has(article.source_id) && isEnglishArticle(article));
    state.statuses = Object.fromEntries((statusPayload.sources || []).map(item => [item.source_id, item]));
    $('nav-article-count').textContent = state.articles.length > 99 ? '99+' : String(state.articles.length);
    $('stat-articles').textContent = state.articles.length.toLocaleString('en');
    $('stat-sources').textContent = state.sources.filter(isActiveEnglishSource).length.toLocaleString('en');
    $('stat-active').textContent = `${statusPayload.sources_with_articles ?? 0}/${statusPayload.checked_count ?? 0}`;
    $('last-checked').textContent = statusPayload.last_checked_at ? `Checked ${formatRunDate(statusPayload.last_checked_at)}` : 'Collection not run yet';
    $('footer-updated').textContent = articlesPayload.last_updated_at ? `INDEX UPDATED ${formatRunDate(articlesPayload.last_updated_at)}` : 'WAITING FOR FIRST COLLECTION';
    $('today-date').textContent = new Intl.DateTimeFormat('en', { weekday: 'short', month: 'short', day: 'numeric', timeZone: 'UTC' }).format(new Date());
    renderArticles();
    if (state.view === 'sources') renderSources();
  } catch (error) {
    $('article-list').innerHTML = `<div class="empty-state"><strong>Could not load the local index.</strong><p>${escapeHTML(error.message)}. Make sure the site is served from its repository root and that the data JSON files are present.</p></div>`;
    $('source-list').innerHTML = '<div class="empty-state"><strong>Source data unavailable.</strong><p>Check that data/sources.json is included in the repository.</p></div>';
  }
}

document.querySelectorAll('.nav-item').forEach(el => el.addEventListener('click', () => updateView(el.dataset.view)));
document.querySelectorAll('.topic-item').forEach(el => el.addEventListener('click', () => { updateView('articles'); updateCategory(el.dataset.category); }));
$('search-input').addEventListener('input', e => { state.query = e.target.value; state.page = 1; renderArticles(); });
$('tier-filter').addEventListener('change', e => { state.tier = e.target.value; state.page = 1; renderArticles(); });
$('sort-filter').addEventListener('change', e => { state.sort = e.target.value; renderArticles(); });
$('clear-filters').addEventListener('click', clearFilters);
$('prev-page').addEventListener('click', () => { state.page = Math.max(1, state.page - 1); renderArticles(); });
$('next-page').addEventListener('click', () => { state.page += 1; renderArticles(); });
$('source-search').addEventListener('input', e => { state.sourceQuery = e.target.value; renderSources(); });
$('source-category-filter').addEventListener('change', e => { state.sourceCategory = e.target.value; renderSources(); });
$('source-tier-filter').addEventListener('change', e => { state.sourceTier = e.target.value; renderSources(); });
$('show-inactive-sources').addEventListener('change', e => { state.includeInactiveSources = e.target.checked; renderSources(); });
$('refresh-button').addEventListener('click', loadData);
document.addEventListener('keydown', e => {
  if (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) { e.preventDefault(); $('search-input').focus(); }
  if (e.key === 'Escape' && document.activeElement === $('search-input')) { $('search-input').value = ''; state.query = ''; renderArticles(); $('search-input').blur(); }
});
loadData();
