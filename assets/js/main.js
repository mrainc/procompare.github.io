/**
 * Omnichannel Group / ProCompare Tech - Core Interactive Scripts
 */

document.addEventListener('DOMContentLoaded', () => {
  initThemeToggle();
  initReadingProgress();
  initTableOfContents();
  initResponsiveTables();
  initCodeCopyButtons();
  initLiveSearch();
  initMatrixFilter();
  initShareTools();
});

/* --------------------------------------------------------------------------
   1. Dark / Light Mode Switcher
   -------------------------------------------------------------------------- */
function initThemeToggle() {
  const themeToggleBtn = document.getElementById('theme-toggle');
  if (!themeToggleBtn) return;

  themeToggleBtn.addEventListener('click', () => {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('procompare-theme', newTheme);
  });
}

/* --------------------------------------------------------------------------
   2. Reading Progress Indicator
   -------------------------------------------------------------------------- */
function initReadingProgress() {
  const progressBar = document.getElementById('reading-progress');
  if (!progressBar) return;

  window.addEventListener('scroll', () => {
    const totalHeight = document.documentElement.scrollHeight - window.innerHeight;
    if (totalHeight <= 0) return;
    const progress = (window.scrollY / totalHeight) * 100;
    progressBar.style.width = Math.min(100, Math.max(0, progress)) + '%';
  }, { passive: true });
}

/* --------------------------------------------------------------------------
   3. Table of Contents & ScrollSpy
   -------------------------------------------------------------------------- */
function initTableOfContents() {
  const postBody = document.getElementById('post-body');
  const tocNav = document.getElementById('toc-nav');
  if (!postBody || !tocNav) return;

  const headings = postBody.querySelectorAll('h2, h3');
  if (headings.length === 0) return;

  const ol = document.createElement('ol');
  const headingElements = [];

  headings.forEach((heading, index) => {
    // Ensure heading has an ID
    if (!heading.id) {
      heading.id = heading.textContent
        .toLowerCase()
        .replace(/[^\w\s-]/g, '')
        .trim()
        .replace(/\s+/g, '-');
    }

    const li = document.createElement('li');
    li.className = heading.tagName === 'H3' ? 'toc-sub' : 'toc-item';

    const a = document.createElement('a');
    a.href = '#' + heading.id;
    a.textContent = heading.textContent.replace(/^[0-9]+\.\s*/, ''); // Clean numbered prefix for TOC
    a.setAttribute('data-target', heading.id);

    li.appendChild(a);
    ol.appendChild(li);
    headingElements.push({ heading, link: a });
  });

  tocNav.appendChild(ol);

  // ScrollSpy to highlight active heading
  const observerOptions = {
    root: null,
    rootMargin: '-80px 0px -60% 0px',
    threshold: 0
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const id = entry.target.id;
        tocNav.querySelectorAll('a').forEach(a => a.classList.remove('active'));
        const activeLink = tocNav.querySelector(`a[data-target="${id}"]`);
        if (activeLink) activeLink.classList.add('active');
      }
    });
  }, observerOptions);

  headings.forEach(h => observer.observe(h));
}

/* --------------------------------------------------------------------------
   4. Responsive Article Tables
   -------------------------------------------------------------------------- */
function initResponsiveTables() {
  document.querySelectorAll('.prose table').forEach((table) => {
    if (table.parentElement?.classList.contains('table-responsive')) return;

    const wrapper = document.createElement('div');
    wrapper.className = 'table-responsive';
    wrapper.setAttribute('tabindex', '0');
    wrapper.setAttribute('aria-label', 'Scrollable comparison table');
    table.parentNode.insertBefore(wrapper, table);
    wrapper.appendChild(table);
  });
}

/* --------------------------------------------------------------------------
   5. Code Block Copy Buttons
   -------------------------------------------------------------------------- */
function initCodeCopyButtons() {
  const codeBlocks = document.querySelectorAll('.prose pre');
  codeBlocks.forEach(pre => {
    const btn = document.createElement('button');
    btn.className = 'code-copy-btn';
    btn.textContent = 'Copy';
    btn.setAttribute('aria-label', 'Copy code to clipboard');

    btn.addEventListener('click', async () => {
      const code = pre.querySelector('code') || pre;
      const text = code.innerText;

      try {
        await navigator.clipboard.writeText(text);
        btn.textContent = 'Copied!';
        btn.style.color = '#34d399';
        setTimeout(() => {
          btn.textContent = 'Copy';
          btn.style.color = '';
        }, 2000);
      } catch (err) {
        console.error('Failed to copy', err);
      }
    });

    pre.appendChild(btn);
  });
}

/* --------------------------------------------------------------------------
   5. Live Article Search & Keyboard Shortcut
   -------------------------------------------------------------------------- */
function initLiveSearch() {
  const searchInput = document.getElementById('site-search-input');
  if (!searchInput) return;
  const hasArticleCards = document.querySelectorAll('.article-card').length > 0;
  const query = new URLSearchParams(window.location.search).get('q') || '';

  if (query) {
    searchInput.value = query;
    if (hasArticleCards) filterArticles(query);
  }

  // Keyboard shortcut '/'
  window.addEventListener('keydown', (e) => {
    if (e.key === '/' && document.activeElement !== searchInput) {
      e.preventDefault();
      searchInput.focus();
    } else if (e.key === 'Escape' && document.activeElement === searchInput) {
      searchInput.blur();
    }
  });

  searchInput.addEventListener('input', (e) => {
    if (hasArticleCards) filterArticles(e.target.value);
  });
}

function filterArticles(query) {
  const articleCards = document.querySelectorAll('.article-card');
  const countEl = document.getElementById('articles-count');
  const noResultsEl = document.getElementById('no-articles-found');
  let visibleCount = 0;

  articleCards.forEach(card => {
    const title = card.getAttribute('data-title') || '';
    const category = card.getAttribute('data-category') || '';
    const tags = card.getAttribute('data-tags') || '';
    const text = (title + ' ' + category + ' ' + tags).toLowerCase();

    if (!query || text.includes(query)) {
      card.style.display = 'flex';
      visibleCount++;
    } else {
      card.style.display = 'none';
    }
  });

  if (countEl) {
    countEl.textContent = query
      ? `Found ${visibleCount} result${visibleCount === 1 ? '' : 's'} for "${query}"`
      : 'Showing all articles';
  }

  if (noResultsEl) {
    noResultsEl.style.display = visibleCount === 0 ? 'block' : 'none';
  }
}

/* --------------------------------------------------------------------------
   6. Interactive Matrix Tab Filter
   -------------------------------------------------------------------------- */
function initMatrixFilter() {
  const filterBtns = document.querySelectorAll('.filter-btn');
  const rows = document.querySelectorAll('.interactive-matrix tbody tr');
  if (filterBtns.length === 0 || rows.length === 0) return;

  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const filter = btn.getAttribute('data-filter');

      rows.forEach(row => {
        const cat = row.getAttribute('data-cat');
        if (filter === 'all' || cat === filter) {
          row.style.display = '';
        } else {
          row.style.display = 'none';
        }
      });
    });
  });
}

/* --------------------------------------------------------------------------
   7. Share Tools & Clipboard Toast
   -------------------------------------------------------------------------- */
function initShareTools() {
  const copyButtons = [
    document.getElementById('share-copy-top'),
    document.getElementById('share-copy-bottom')
  ].filter(Boolean);

  const toast = document.getElementById('toast');

  copyButtons.forEach(btn => {
    btn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(window.location.href);
        showToast('Link copied to clipboard!');
      } catch (e) {
        showToast('Failed to copy link.');
      }
    });
  });

  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => {
      toast.classList.remove('show');
    }, 2800);
  }
}
