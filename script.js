let allArticles = [];
let currentTag = 'all';
let searchQuery = '';
let currentPage = 1;
const itemsPerPage = 12; // Mobile friendly number of cards per page

document.addEventListener('DOMContentLoaded', () => {
    const grid = document.getElementById('articlesGrid');
    const stats = document.getElementById('statsDisplay');
    
    if (typeof allArticlesData !== 'undefined') {
        allArticles = allArticlesData;
        extractTags();
        renderArticles();
    } else {
        grid.innerHTML = `<div class="loader" style="color: #ef4444;">에러 발생: 데이터를 찾을 수 없습니다.<br>먼저 데이터 수집 스크립트(run_update.bat)를 실행해주세요.</div>`;
        stats.innerText = '';
    }
    setupEventListeners();
});

function extractTags() {
    const tagSet = new Set();
    allArticles.forEach(article => {
        if (article.tags) {
            article.tags.forEach(tag => tagSet.add(tag));
        }
    });
    
    const sortedTags = Array.from(tagSet).sort();
    const filtersContainer = document.getElementById('tagFilters');
    
    filtersContainer.innerHTML = '<button class="filter-btn active" data-tag="all">All</button>';
    
    sortedTags.forEach(tag => {
        const btn = document.createElement('button');
        btn.className = 'filter-btn';
        btn.setAttribute('data-tag', tag.toLowerCase());
        btn.innerText = tag;
        filtersContainer.appendChild(btn);
    });
    
    setupTagListeners();
}

function renderArticles() {
    const grid = document.getElementById('articlesGrid');
    const stats = document.getElementById('statsDisplay');
    
    grid.innerHTML = '';
    
    let filtered = allArticles;
    
    // Filter by tag
    if (currentTag !== 'all') {
        filtered = filtered.filter(article => 
            article.tags && article.tags.some(t => t.toLowerCase() === currentTag)
        );
    }
    
    // Filter by search
    if (searchQuery) {
        const q = searchQuery.toLowerCase();
        filtered = filtered.filter(article => 
            article.title.toLowerCase().includes(q) || 
            (article.summary && article.summary.join(' ').toLowerCase().includes(q)) ||
            article.source.toLowerCase().includes(q)
        );
    }
    
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    const paginated = filtered.slice(startIndex, endIndex);
    const totalPages = Math.ceil(filtered.length / itemsPerPage);
    
    stats.innerText = `총 ${filtered.length}개의 기사 (페이지 ${currentPage}/${totalPages || 1})`;
    
    if (filtered.length === 0) {
        grid.innerHTML = '<div class="loader">검색 결과가 없습니다.</div>';
        renderPagination(0);
        return;
    }
    
    paginated.forEach(article => {
        const card = document.createElement('div');
        card.className = 'card';
        
        let summaryHtml = '';
        if (article.summary && article.summary.length > 0) {
            summaryHtml = '<ul>' + article.summary.map(s => `<li>${s}</li>`).join('') + '</ul>';
        } else {
            summaryHtml = '<p>요약이 없습니다.</p>';
        }
        
        let tagsHtml = '';
        if (article.tags) {
            tagsHtml = '<div class="card-tags">' + article.tags.map(t => `<span class="tag">${t}</span>`).join('') + '</div>';
        }
        
        let displayTitle = article.translated_title || article.title;
        
        card.innerHTML = `
            <div class="card-header">
                <span class="source">${article.source}</span>
                <span class="date">${article.date}</span>
            </div>
            <h3 class="card-title">
                ${displayTitle}
            </h3>
            <div class="card-summary">
                ${summaryHtml}
            </div>
            <div style="margin-top: auto; margin-bottom: 15px; font-size: 0.85rem;">
                <a href="${article.link}" target="_blank" rel="noopener noreferrer" style="color: var(--accent-color); text-decoration: none; font-weight: 500;">🔗 원문 읽기 (Original Link)</a>
            </div>
            ${tagsHtml}
        `;
        
        grid.appendChild(card);
    });
    
    renderPagination(totalPages);
}

function renderPagination(totalPages) {
    const container = document.getElementById('paginationContainer');
    if (!container) return;
    
    container.innerHTML = '';
    
    if (totalPages <= 1) return;
    
    // Add Prev button
    if (currentPage > 1) {
        const prevBtn = document.createElement('button');
        prevBtn.className = 'page-btn';
        prevBtn.innerText = '이전';
        prevBtn.addEventListener('click', () => {
            currentPage--;
            renderArticles();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
        container.appendChild(prevBtn);
    }
    
    // Page Numbers (Show window of 5 pages)
    let startPage = Math.max(1, currentPage - 2);
    let endPage = Math.min(totalPages, startPage + 4);
    
    if (endPage - startPage < 4) {
        startPage = Math.max(1, endPage - 4);
    }
    
    for (let i = startPage; i <= endPage; i++) {
        const btn = document.createElement('button');
        btn.className = `page-btn ${i === currentPage ? 'active' : ''}`;
        btn.innerText = i;
        btn.addEventListener('click', () => {
            currentPage = i;
            renderArticles();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
        container.appendChild(btn);
    }
    
    // Add Next button
    if (currentPage < totalPages) {
        const nextBtn = document.createElement('button');
        nextBtn.className = 'page-btn';
        nextBtn.innerText = '다음';
        nextBtn.addEventListener('click', () => {
            currentPage++;
            renderArticles();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
        container.appendChild(nextBtn);
    }
}

function setupEventListeners() {
    const searchInput = document.getElementById('searchInput');
    searchInput.addEventListener('input', (e) => {
        searchQuery = e.target.value;
        currentPage = 1; // Reset to page 1 on search
        renderArticles();
    });
    
    setupTagListeners();
}

function setupTagListeners() {
    const buttons = document.querySelectorAll('.filter-btn');
    buttons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            buttons.forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            
            currentTag = e.target.getAttribute('data-tag');
            currentPage = 1; // Reset to page 1 on filter
            renderArticles();
        });
    });
}
