// 全局变量
let currentPage = 1;
let pageSize = 10;
let totalArticles = 0;
let currentFilters = {};

// DOM加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 初始化页面
    initializeTheme();
    initializePage();
    
    // 绑定事件
    bindEvents();
});

function escapeHTML(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[m]));
}

function isSafeHttpUrl(u) {
    try { return /^https?:\/\//i.test(u || ''); } catch { return false; }
}

// 初始化页面
async function initializePage() {
    // 加载统计数据
    await loadStats();
    
    // 加载筛选选项
    await loadFilterOptions();
    
    // 加载文章列表
    await loadArticles();
}

// 绑定事件
function bindEvents() {
    // 筛选表单提交事件
    document.getElementById('filter-form').addEventListener('submit', function(e) {
        e.preventDefault();
        applyFilters();
    });
    
    // 重置筛选按钮
    document.getElementById('reset-filter').addEventListener('click', function() {
        resetFilters();
    });
    
    // 导航链接
    document.getElementById('home-link').addEventListener('click', function(e) {
        e.preventDefault();
        // 可以在这里添加导航逻辑
    });
    
    document.getElementById('stats-link').addEventListener('click', function(e) {
        e.preventDefault();
        // 可以在这里添加统计页面逻辑
    });

    // 处理未AI文章按钮
    const processBtn = document.getElementById('process-unprocessed-btn');
    if (processBtn) {
        processBtn.addEventListener('click', handleProcessUnprocessed);
    }

    // 即时抓取按钮
    const fetchBtn = document.getElementById('fetch-latest-btn');
    if (fetchBtn) {
        fetchBtn.addEventListener('click', handleFetchLatestProgress);
    }

    // 主题切换按钮
    const themeBtn = document.getElementById('theme-toggle');
    if (themeBtn) {
        themeBtn.addEventListener('click', toggleTheme);
    }
}

// 初始化主题（支持暗色/亮色切换）
function initializeTheme() {
    try {
        const saved = localStorage.getItem('theme');
        const theme = saved === 'light' || saved === 'dark' ? saved : 'dark';
        applyTheme(theme);
    } catch (e) {
        applyTheme('dark');
    }
}

// 应用主题到根元素并更新切换按钮文案
function applyTheme(theme) {
    const root = document.documentElement;
    root.setAttribute('data-theme', theme);
    const icon = document.getElementById('theme-toggle-icon');
    const text = document.getElementById('theme-toggle-text');
    if (icon) {
        icon.className = theme === 'dark' ? 'bi bi-moon' : 'bi bi-sun';
    }
    if (text) {
        text.textContent = theme === 'dark' ? '暗色' : '亮色';
    }
}

// 切换主题并持久化
function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    try { localStorage.setItem('theme', next); } catch {}
}

// 加载统计数据
async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        const stats = await response.json();
        
        // 更新统计卡片
        document.getElementById('total-articles').textContent = stats.total_articles || 0;
        document.getElementById('positive-sentiment').textContent = stats.sentiment_stats.positive || 0;
        document.getElementById('negative-sentiment').textContent = stats.sentiment_stats.negative || 0;
        document.getElementById('neutral-sentiment').textContent = stats.sentiment_stats.neutral || 0;
    } catch (error) {
        console.error('加载统计数据失败:', error);
    }
}

// 触发服务端处理未经过AI的文章（带进度）
async function handleProcessUnprocessed() {
    const btn = document.getElementById('process-unprocessed-btn');
    const modalEl = document.getElementById('taskModal');
    if (!btn || !modalEl || typeof bootstrap === 'undefined') return;
    const originalHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> 处理中…';

    const bar = document.getElementById('task-progress-bar');
    const status = document.getElementById('task-status');
    const modal = new bootstrap.Modal(modalEl);
    bar.className = 'progress-bar progress-bar-striped progress-bar-animated';
    bar.style.width = '0%';
    bar.textContent = '0%';
    status.textContent = '正在计算未处理文章总数…';
    modal.show();

    try {
        const statsResp = await fetch('/api/stats');
        const stats = await statsResp.json();
        const totalUnprocessed = stats.unprocessed_articles || 0;
        if (totalUnprocessed <= 0) {
            status.textContent = '没有未处理文章';
            bar.className = 'progress-bar';
            bar.style.width = '100%';
            bar.textContent = '100%';
            return;
        }
        status.textContent = `待处理 ${totalUnprocessed} 篇文章…`;

        let processedSum = 0;
        const batchSize = 10;
        const maxLoops = Math.ceil(totalUnprocessed / batchSize) + 5;
        for (let i = 0; i < maxLoops; i++) {
            const resp = await fetch('/api/process-unprocessed', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ batch_size: batchSize, delay: 0 })
            });
            if (!resp.ok) throw new Error(`HTTP错误: ${resp.status} ${resp.statusText}`);
            const data = await resp.json();
            const processed = Number(data.processed || 0);
            processedSum += processed;
            const pct = Math.min(100, Math.round((processedSum / totalUnprocessed) * 100));
            bar.className = 'progress-bar';
            bar.style.width = pct + '%';
            bar.textContent = pct + '%';
            status.textContent = `已处理 ${processedSum}/${totalUnprocessed} 篇…`;
            if (processed === 0 || processedSum >= totalUnprocessed) break;
        }
        status.textContent = '处理完成，刷新数据…';
        await loadStats();
        await loadArticles();
    } catch (error) {
        console.error('处理未AI文章失败:', error);
        status.textContent = '处理失败：' + error.message;
        bar.className = 'progress-bar bg-danger';
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalHTML;
        setTimeout(() => { try { const m = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl); m.hide(); } catch {} }, 1200);
    }
}

// 即时抓取（带进度）
async function handleFetchLatestProgress() {
    const btn = document.getElementById('fetch-latest-btn');
    const modalEl = document.getElementById('taskModal');
    if (!btn || !modalEl || typeof bootstrap === 'undefined') return;
    const originalHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> 抓取中…';

    const bar = document.getElementById('task-progress-bar');
    const status = document.getElementById('task-status');
    const modal = new bootstrap.Modal(modalEl);
    bar.className = 'progress-bar progress-bar-striped progress-bar-animated';
    bar.style.width = '25%';
    bar.textContent = '';
    status.textContent = '正在抓取最新新闻…';
    modal.show();

    try {
        const resp = await fetch('/api/fetch-latest', { method: 'POST' });
        if (!resp.ok) throw new Error(`HTTP错误: ${resp.status} ${resp.statusText}`);
        const data = await resp.json();
        bar.className = 'progress-bar';
        bar.style.width = '100%';
        bar.textContent = '100%';
        status.textContent = `抓取完成：文章总数 ${data.total_articles}，未处理 ${data.unprocessed_articles}`;
        await loadStats();
        await loadArticles();
    } catch (error) {
        console.error('即时抓取失败:', error);
        status.textContent = '抓取失败：' + error.message;
        bar.className = 'progress-bar bg-danger';
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalHTML;
        setTimeout(() => { try { const m = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl); m.hide(); } catch {} }, 1200);
    }
}

// 加载筛选选项
async function loadFilterOptions() {
    try {
        // 加载新闻来源选项
        const sourcesResponse = await fetch('/api/sources');
        const sources = await sourcesResponse.json();
        const sourceSelect = document.getElementById('source-filter');
        
        sources.forEach(source => {
            const option = document.createElement('option');
            option.value = source;
            option.textContent = source;
            sourceSelect.appendChild(option);
        });
        
        // 加载情感类型选项
        const sentimentsResponse = await fetch('/api/sentiments');
        const sentiments = await sentimentsResponse.json();
        const sentimentSelect = document.getElementById('sentiment-filter');
        
        sentiments.forEach(sentiment => {
            const option = document.createElement('option');
            option.value = sentiment;
            option.textContent = getSentimentText(sentiment);
            sentimentSelect.appendChild(option);
        });
    } catch (error) {
        console.error('加载筛选选项失败:', error);
    }
}

// 应用筛选条件
function applyFilters() {
    // 获取筛选条件
    currentFilters = {
        source: document.getElementById('source-filter').value,
        sentiment: document.getElementById('sentiment-filter').value,
        start_date: document.getElementById('start-date').value,
        end_date: document.getElementById('end-date').value,
        ai_processed: document.getElementById('ai-processed-filter').value
    };
    
    // 重置页码
    currentPage = 1;
    
    // 重新加载文章
    loadArticles();
}

// 重置筛选条件
function resetFilters() {
    // 清空筛选表单
    document.getElementById('source-filter').value = '';
    document.getElementById('sentiment-filter').value = '';
    document.getElementById('start-date').value = '';
    document.getElementById('end-date').value = '';
    document.getElementById('ai-processed-filter').value = '';
    
    // 清空筛选条件
    currentFilters = {};
    
    // 重置页码
    currentPage = 1;
    
    // 重新加载文章
    loadArticles();
}

// 加载文章列表
async function loadArticles() {
    // 显示加载中
    document.getElementById('loading').classList.remove('d-none');
    document.getElementById('articles-container').classList.add('d-none');
    
    try {
        // 构建API URL
        let url = `/api/articles?page=${currentPage}&page_size=${pageSize}`;
        
        // 添加筛选参数
        if (currentFilters.source) {
            url += `&source=${encodeURIComponent(currentFilters.source)}`;
        }
        if (currentFilters.sentiment) {
            url += `&sentiment=${encodeURIComponent(currentFilters.sentiment)}`;
        }
        if (currentFilters.start_date) {
            url += `&start_date=${encodeURIComponent(currentFilters.start_date)}`;
        }
        if (currentFilters.end_date) {
            url += `&end_date=${encodeURIComponent(currentFilters.end_date)}`;
        }
        if (currentFilters.ai_processed !== '') {
            url += `&ai_processed=${encodeURIComponent(currentFilters.ai_processed)}`;
        }
        
        // 发送请求
        const response = await fetch(url);
        const data = await response.json();
        
        // 更新总文章数
        totalArticles = data.total;
        document.getElementById('article-count').textContent = `${totalArticles} 篇文章`;
        
        // 确保articles数组存在
        const articles = data.articles || [];
        
        // 渲染文章列表
        renderArticles(articles);
        
        // 渲染分页
        renderPagination();
        
        // 隐藏加载中，显示文章列表
        document.getElementById('loading').classList.add('d-none');
        document.getElementById('articles-container').classList.remove('d-none');
    } catch (error) {
        console.error('加载文章失败:', error);
        document.getElementById('loading').classList.add('d-none');
        document.getElementById('articles-container').innerHTML = `
            <div class="alert alert-danger">
                加载文章失败: ${error.message}
            </div>
        `;
        document.getElementById('articles-container').classList.remove('d-none');
    }
}

// 渲染文章列表
function renderArticles(articles) {
    const container = document.getElementById('articles-container');
    
    // 确保articles是一个数组
    if (!articles || !Array.isArray(articles)) {
        console.error('articles不是一个有效的数组:', articles);
        articles = [];
    }
    
    if (articles.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="bi bi-inbox"></i>
                <h5>没有找到文章</h5>
                <p>请尝试调整筛选条件</p>
            </div>
        `;
        return;
    }
    
    // 创建文章HTML
    let articlesHTML = '';
    articles.forEach(article => {
        articlesHTML += createArticleCard(article);
    });
    
    container.innerHTML = articlesHTML;
    
    // 绑定文章卡片点击事件
    document.querySelectorAll('.article-card').forEach(card => {
        card.addEventListener('click', function() {
            const articleId = this.getAttribute('data-article-id');
            console.log('点击文章卡片, ID:', articleId);
            showArticleDetails(articleId);
        });
    });
}

// 创建文章卡片HTML
function createArticleCard(article) {
    console.log('创建文章卡片, 文章ID:', article.id);
    const sentimentClass = getSentimentClass(article.sentiment);
    const sentimentText = getSentimentText(article.sentiment);
    const aiProcessedClass = article.ai_processed ? 'ai-processed-true' : 'ai-processed-false';
    const aiProcessedText = article.ai_processed ? '已处理' : '未处理';
    
    // 格式化发布日期
    const publishedDate = formatDate(article.published);
    
    // 创建情感分数条
    let sentimentScoreBar = '';
    if (article.sentiment_score !== null && article.sentiment_score !== undefined) {
        const score = parseFloat(article.sentiment_score);
        const percentage = (score + 1) * 50; // 将-1到1的范围转换为0-100的百分比
        const color = score > 0 ? '#28a745' : score < 0 ? '#dc3545' : '#ffc107';
        
        sentimentScoreBar = `
            <div class="sentiment-score-bar">
                <div class="sentiment-score-fill" style="width: ${percentage}%; background-color: ${color};"></div>
            </div>
        `;
    }
    
    return `
        <div class="article-card card" data-article-id="${article.id}">
            <div class="card-body">
                <div class="article-header">
                    <div>
                        <div class="article-title">${article.title}</div>
                        <div class="article-meta">
                            <span class="source-badge">${article.source}</span>
                            <span class="ms-2">${publishedDate}</span>
                            ${article.author ? `<span class="ms-2">作者: ${article.author}</span>` : ''}
                        </div>
                    </div>
                    <div>
                        <span class="ai-processed-badge ${aiProcessedClass}">${aiProcessedText}</span>
                    </div>
                </div>
                
                <div class="article-summary">
                    ${escapeHTML(article.summary || '无摘要')}
                </div>
                
                ${article.chinese_summary ? `
                    <div class="article-chinese-summary">
                        <strong>中文摘要:</strong> ${escapeHTML(article.chinese_summary)}
                    </div>
                ` : ''}
                
                ${article.sentiment ? `
                    <div class="article-sentiment">
                        <span class="sentiment-badge ${sentimentClass}">${sentimentText}</span>
                        ${article.sentiment_score !== null && article.sentiment_score !== undefined ? 
                            `<span class="ms-2">情感分数: ${article.sentiment_score.toFixed(2)}</span>` : ''}
                        ${sentimentScoreBar}
                    </div>
                ` : ''}
                
                <div class="article-footer">
                    <div>
                        ${article.keywords ? 
                            article.keywords.split(',').map(keyword => 
                                `<span class="keyword-tag">${keyword.trim()}</span>`
                            ).join('') : ''}
                    </div>
                    <div>
                        <button class="btn btn-sm btn-outline-primary">
                            <i class="bi bi-eye"></i> 查看详情
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// 渲染分页
function renderPagination() {
    const totalPages = Math.ceil(totalArticles / pageSize);
    const paginationContainer = document.querySelector('#pagination-container ul');
    
    if (totalPages <= 1) {
        paginationContainer.innerHTML = '';
        return;
    }
    
    let paginationHTML = '';
    
    // 上一页
    paginationHTML += `
        <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
            <a class="page-link" href="#" data-page="${currentPage - 1}">上一页</a>
        </li>
    `;
    
    // 页码
    for (let i = 1; i <= totalPages; i++) {
        // 显示当前页前后各2页
        if (i === 1 || i === totalPages || (i >= currentPage - 2 && i <= currentPage + 2)) {
            paginationHTML += `
                <li class="page-item ${i === currentPage ? 'active' : ''}">
                    <a class="page-link" href="#" data-page="${i}">${i}</a>
                </li>
            `;
        } else if (i === currentPage - 3 || i === currentPage + 3) {
            paginationHTML += `
                <li class="page-item disabled">
                    <a class="page-link" href="#">...</a>
                </li>
            `;
        }
    }
    
    // 下一页
    paginationHTML += `
        <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
            <a class="page-link" href="#" data-page="${currentPage + 1}">下一页</a>
        </li>
    `;
    
    paginationContainer.innerHTML = paginationHTML;
    
    // 绑定分页点击事件
    document.querySelectorAll('#pagination-container .page-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const page = parseInt(this.getAttribute('data-page'));
            if (page && page !== currentPage) {
                currentPage = page;
                loadArticles();
            }
        });
    });
}

// 显示文章详情
async function showArticleDetails(articleId) {
    console.log('显示文章详情, ID:', articleId);
    
    // 检查Bootstrap是否已加载
    if (typeof bootstrap === 'undefined') {
        console.error('Bootstrap未加载');
        alert('页面组件未完全加载，请刷新页面后重试');
        return;
    }
    
    // 检查Modal组件是否可用
    if (typeof bootstrap.Modal === 'undefined') {
        console.error('Bootstrap Modal组件不可用');
        alert('模态框组件不可用，请刷新页面后重试');
        return;
    }
    
    try {
        // 使用查询参数方式获取文章详情，避免路径参数解析问题
        const response = await fetch(`/api/articles/by-id?article_id=${encodeURIComponent(articleId)}`);
        console.log('API响应状态:', response.status);
        
        // 检查响应状态
        if (!response.ok) {
            throw new Error(`HTTP错误: ${response.status} ${response.statusText}`);
        }
        
        const article = await response.json();
        console.log('文章数据:', article);
        
        // 确保article对象存在
        if (!article) {
            throw new Error('文章数据为空');
        }
        
        // 检查关键字段
        console.log('标题:', article.title);
        console.log('来源:', article.source);
        console.log('发布时间:', article.published);
        console.log('摘要:', article.summary);
        
        // 填充模态框内容
        const modalBody = document.getElementById('article-modal-body');
        const detailHTML = createArticleDetailHTML(article);
        console.log('生成的HTML:', detailHTML);
        modalBody.innerHTML = detailHTML;
        
        const linkEl = document.getElementById('article-link');
        if (isSafeHttpUrl(article.link)) {
            linkEl.href = article.link;
            linkEl.style.display = 'inline-block';
        } else {
            linkEl.removeAttribute('href');
            linkEl.style.display = 'none';
        }
        
        // 显示模态框
        const modalElement = document.getElementById('articleModal');
        console.log('模态框元素:', modalElement);
        
        if (!modalElement) {
            console.error('找不到模态框元素');
            alert('找不到文章详情模态框');
            return;
        }
        
        const modal = new bootstrap.Modal(modalElement);
        console.log('创建的模态框对象:', modal);
        
        // 尝试显示模态框
        try {
            modal.show();
            console.log('模态框显示命令已执行');
        } catch (modalError) {
            console.error('显示模态框时出错:', modalError);
            alert('显示文章详情失败: ' + modalError.message);
        }
    } catch (error) {
        console.error('加载文章详情失败:', error);
        alert('加载文章详情失败: ' + error.message);
    }
}

// 创建文章详情HTML
function createArticleDetailHTML(article) {
    // 确保article对象存在
    if (!article) {
        return '<div class="alert alert-danger">文章数据不存在</div>';
    }
    
    // 添加调试日志
    console.log('创建文章详情HTML, 文章数据:', article);
    
    const sentimentClass = getSentimentClass(article.sentiment);
    const sentimentText = getSentimentText(article.sentiment);
    const aiProcessedClass = article.ai_processed ? 'ai-processed-true' : 'ai-processed-false';
    const aiProcessedText = article.ai_processed ? '已处理' : '未处理';
    
    // 格式化日期
    const publishedDate = formatDate(article.published);
    const createdDate = formatDate(article.created_at);
    const updatedDate = formatDate(article.updated_at);
    
    // 处理标题和来源，确保它们不为null或undefined
    const title = article.title !== null && article.title !== undefined ? article.title : '无标题';
    const source = article.source !== null && article.source !== undefined ? article.source : '未知来源';
    
    // 处理摘要，区分null和空字符串
    const summary = article.summary === null ? '无摘要' : (article.summary || '无摘要');
    
    console.log('处理后的标题:', title);
    console.log('处理后的来源:', source);
    console.log('处理后的摘要:', summary);
    
    return `
        <div class="article-detail-section">
            <div class="article-detail-title">标题</div>
            <div>${escapeHTML(title)}</div>
        </div>
        
        <div class="article-detail-section">
            <div class="article-detail-title">来源</div>
            <div>
                <span class="source-badge">${escapeHTML(source)}</span>
                ${article.author ? `<span class="ms-2">作者: ${article.author}</span>` : ''}
            </div>
        </div>
        
        <div class="article-detail-section">
            <div class="article-detail-title">发布时间</div>
            <div>${publishedDate}</div>
        </div>
        
        <div class="article-detail-section">
            <div class="article-detail-title">摘要</div>
            <div>${escapeHTML(summary)}</div>
        </div>
        
        ${article.chinese_summary !== null && article.chinese_summary !== undefined && article.chinese_summary.trim() !== '' ? `
            <div class="article-detail-section">
                <div class="article-detail-title">中文摘要</div>
                <div>${escapeHTML(article.chinese_summary)}</div>
            </div>
        ` : ''}
        
        ${article.content !== null && article.content !== undefined && article.content.trim() !== '' ? `
            <div class="article-detail-section">
                <div class="article-detail-title">内容</div>
                <div>${escapeHTML(article.content)}</div>
            </div>
        ` : `
            <div class="article-detail-section">
                <div class="article-detail-title">内容</div>
                <div class="text-muted">文章内容暂不可用</div>
            </div>
        `}
        
        <div class="article-detail-section">
            <div class="article-detail-title">情感分析</div>
            <div>
                ${article.sentiment !== null && article.sentiment !== undefined ? 
                    `<span class="sentiment-badge ${sentimentClass}">${sentimentText}</span>` : 
                    '<span class="text-muted">暂无情感分析</span>'}
                ${article.sentiment_score !== null && article.sentiment_score !== undefined ? 
                    `<span class="ms-2">情感分数: ${article.sentiment_score.toFixed(2)}</span>` : ''}
            </div>
        </div>
        
        ${article.keywords ? `
            <div class="article-detail-section">
                <div class="article-detail-title">关键词</div>
                <div>
                    ${article.keywords.split(',').map(keyword => 
                        `<span class="keyword-tag">${keyword.trim()}</span>`
                    ).join('')}
                </div>
            </div>
        ` : ''}
        
        <div class="article-detail-section">
            <div class="article-detail-title">处理状态</div>
            <div>
                <span class="ai-processed-badge ${aiProcessedClass}">${aiProcessedText}</span>
            </div>
        </div>
        
        <div class="article-detail-section">
            <div class="article-detail-title">记录时间</div>
            <div>
                创建时间: ${createdDate}<br>
                更新时间: ${updatedDate}
            </div>
        </div>
    `;
}

// 获取情感类型对应的CSS类
function getSentimentClass(sentiment) {
    switch (sentiment) {
        case 'positive':
            return 'sentiment-positive';
        case 'negative':
            return 'sentiment-negative';
        case 'neutral':
            return 'sentiment-neutral';
        default:
            return '';
    }
}

// 获取情感类型对应的文本
function getSentimentText(sentiment) {
    switch (sentiment) {
        case 'positive':
            return '积极';
        case 'negative':
            return '消极';
        case 'neutral':
            return '中性';
        default:
            return '未知';
    }
}

// 格式化日期
function formatDate(dateString) {
    if (!dateString) return '未知';
    
    try {
        const date = new Date(dateString);
        // 检查日期是否有效
        if (isNaN(date.getTime())) {
            console.warn('无效日期:', dateString);
            return '无效日期';
        }
        
        return date.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (error) {
        console.error('日期格式化错误:', error, '日期字符串:', dateString);
        return '日期格式错误';
    }
}