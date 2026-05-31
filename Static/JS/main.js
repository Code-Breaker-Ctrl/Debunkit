let currentMode = 'title';
let isAnalyzing = false;
let lastAnalysisReport = null;
let cachedHistoryAnalyses = [];

const MAX_RETRIES = 2;
const RETRY_DELAY = 1500;

// ===== SAFE DOM HELPERS =====

function clearElement(element) {
    if (!element) return;

    while (element.firstChild) {
        element.removeChild(element.firstChild);
    }
}

function setStatusMessage(container, message, color = 'var(--text)') {
    if (!container) return;

    clearElement(container);

    const p = document.createElement('p');
    p.textContent = message;
    p.style.color = color;

    container.appendChild(p);
}

function createCell(text, align = 'left') {
    const td = document.createElement('td');
    td.textContent = text;
    td.style.padding = '10px';
    td.style.textAlign = align;
    return td;
}

function createDetailRow(label, value, options = {}) {
    const wrapper = document.createElement('div');
    wrapper.style.marginBottom = '14px';

    const labelEl = document.createElement('div');
    labelEl.textContent = label;
    labelEl.style.color = 'var(--accent)';
    labelEl.style.fontWeight = 'bold';
    labelEl.style.marginBottom = '5px';
    labelEl.style.fontSize = '13px';

    const valueEl = document.createElement('div');
    valueEl.textContent = value || 'N/A';
    valueEl.style.color = options.color || 'var(--text)';
    valueEl.style.whiteSpace = options.preWrap ? 'pre-wrap' : 'normal';
    valueEl.style.wordBreak = 'break-word';
    valueEl.style.lineHeight = '1.5';

    if (options.monospace) {
        valueEl.style.fontFamily = "'Courier New', Courier, monospace";
        valueEl.style.background = 'rgba(255,255,255,0.03)';
        valueEl.style.border = '1px solid var(--border)';
        valueEl.style.borderRadius = '6px';
        valueEl.style.padding = '10px';
        valueEl.style.maxHeight = '180px';
        valueEl.style.overflowY = 'auto';
    }

    wrapper.appendChild(labelEl);
    wrapper.appendChild(valueEl);

    return wrapper;
}

// ===== CSRF HELPERS =====

function getCSRFToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}

function csrfHeaders(headers = {}) {
    return {
        ...headers,
        'X-CSRFToken': getCSRFToken()
    };
}

// ===== VERDICT HELPERS =====

function normalizeVerdict(verdict) {
    const value = String(verdict || '').trim().toUpperCase();

    const aliases = {
        'REAL': 'SUPPORTED',
        'TRUE': 'SUPPORTED',
        'CONFIRMED': 'SUPPORTED',
        'FAKE': 'REFUTED',
        'FALSE': 'REFUTED',
        'DEBUNKED': 'REFUTED',
        'UNCERTAIN': 'INSUFFICIENT EVIDENCE',
        'UNKNOWN': 'INSUFFICIENT EVIDENCE',
        'UNVERIFIED': 'INSUFFICIENT EVIDENCE',
        'SUSPICIOUS': 'LOW CREDIBILITY'
    };

    return aliases[value] || value || 'INSUFFICIENT EVIDENCE';
}

function normalizeVerdictSafe(verdict) {
    return normalizeVerdict(verdict);
}

function verdictClass(verdict) {
    return 'verdict-' + normalizeVerdict(verdict).replace(/\s+/g, '-');
}

function getVerdictColor(verdict) {
    const normalized = normalizeVerdict(verdict);

    if (normalized === 'SUPPORTED') return 'var(--success)';
    if (normalized === 'REFUTED') return 'var(--danger)';
    if (normalized === 'MISLEADING') return 'var(--warn)';
    if (normalized === 'LOW CREDIBILITY') return 'var(--warn)';
    if (normalized === 'INSUFFICIENT EVIDENCE') return 'var(--muted)';

    return 'var(--warn)';
}

function mergeBreakdown(rawBreakdown, normalizer) {
    const merged = {};

    Object.entries(rawBreakdown || {}).forEach(([rawKey, count]) => {
        const normalizedKey = normalizer(rawKey);
        const numericCount = Number(count) || 0;

        merged[normalizedKey] = (merged[normalizedKey] || 0) + numericCount;
    });

    return merged;
}

function normalizeModeLabel(mode) {
    const value = String(mode || 'unknown').trim().toLowerCase();

    if (value === 'ai') return 'AI Analysis';
    if (value === 'local') return 'Local NLP';
    if (value === 'local_fallback') return 'Local NLP';
    if (value === 'ml_model') return 'ML Model';

    return value
        .replace(/_/g, ' ')
        .replace(/\b\w/g, char => char.toUpperCase());
}

// ===== COPY REPORT =====

function buildReportText(report) {
    if (!report) {
        return '';
    }

    const verdict = normalizeVerdict(report.verdict);
    const confidence = report.confidence ?? 'N/A';
    const reason = report.reason || 'N/A';
    const factCheck = report.fact_check || 'N/A';
    const inputType = report.input_type || report.type || 'N/A';
    const textAnalyzed = report.text_analyzed || 'N/A';
    const generatedAt = report.generated_at || new Date().toLocaleString();

    const redFlags = Array.isArray(report.red_flags) && report.red_flags.length > 0
        ? report.red_flags.map(flag => `- ${flag}`).join('\n')
        : 'None detected.';

    const sources = Array.isArray(report.sources) && report.sources.length > 0
        ? report.sources.map((src, index) => {
            const title = src.title || `Source ${index + 1}`;
            const url = src.url || 'No URL';
            return `${index + 1}. ${title}\n   ${url}`;
        }).join('\n')
        : 'No sources available.';

    return `DEBUNK.IT ANALYSIS REPORT

Generated At: ${generatedAt}
Input Type: ${inputType}

Claim / Text Analyzed:
${textAnalyzed}

Verdict: ${verdict}
Confidence: ${confidence}%

Reason:
${reason}

Fact-check:
${factCheck}

Red Flags:
${redFlags}

Sources:
${sources}

Generated by DEBUNK.IT
AI-assisted misinformation analysis system`;
}

async function copyCurrentReport() {
    if (!lastAnalysisReport) {
        showNotification('No report available to copy yet.', 'warning');
        return;
    }

    const reportText = buildReportText(lastAnalysisReport);

    try {
        await navigator.clipboard.writeText(reportText);
        showNotification('Report copied to clipboard.', 'success');
    } catch (error) {
        console.error('[Clipboard Error]', error);
        showNotification('Could not copy report. Browser blocked clipboard access.', 'error');
    }
}
function sanitizeFilenamePart(value) {
    return String(value || 'report')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '')
        .substring(0, 40) || 'report';
}

function downloadCurrentReport() {
    if (!lastAnalysisReport) {
        showNotification('No report available to download yet.', 'warning');
        return;
    }

    const reportText = buildReportText(lastAnalysisReport);
    const verdict = sanitizeFilenamePart(normalizeVerdict(lastAnalysisReport.verdict));
    const timestamp = new Date()
        .toISOString()
        .replace(/[:.]/g, '-')
        .substring(0, 19);

    const filename = `debunkit-${verdict}-${timestamp}.txt`;

    const blob = new Blob([reportText], {
        type: 'text/plain;charset=utf-8'
    });

    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = filename;

    document.body.appendChild(link);
    link.click();
    link.remove();

    URL.revokeObjectURL(url);

    showNotification('Report downloaded successfully.', 'success');
}

// ===== DYNAMIC DASHBOARD HELPERS =====

const MODE_HINTS = {
    title: 'Headline mode is best for quick news claims, viral captions, and short breaking-news titles.',
    url: 'URL mode extracts article text first, then checks the submitted source with live context.',
    text: 'Text mode is best for long articles, forwarded messages, and full claim explanations.'
};

function updateModeHint(mode) {
    const hint = document.getElementById('mode-hint');

    if (hint) {
        hint.textContent = MODE_HINTS[mode] || MODE_HINTS.title;
    }
}

function focusScannerMode(mode) {
    if (isAnalyzing) {
        showNotification('Analysis in progress. Please wait.', 'warning');
        return;
    }

    const tabButtons = document.querySelectorAll('.tab-btn');
    tabButtons.forEach(btn => btn.classList.remove('active'));

    tabButtons.forEach(btn => {
        const label = btn.textContent.trim().toLowerCase();

        if (
            label === mode ||
            (mode === 'title' && label === 'headline')
        ) {
            btn.classList.add('active');
        }
    });

    document.querySelectorAll('.input-section').forEach(section => {
        section.classList.remove('active');
    });

    const selectedInput = document.getElementById('input-' + mode);
    if (selectedInput) {
        selectedInput.classList.add('active');
    }

    currentMode = mode;
    updateModeHint(mode);

    const activeInput = document.getElementById('val-' + mode);
    if (activeInput) {
        activeInput.focus();
    }

    const scannerPanel = document.querySelector('.scanner-panel');
    if (scannerPanel) {
        scannerPanel.scrollIntoView({
            behavior: 'smooth',
            block: 'center'
        });
    }
}

function fillExampleClaim(text) {
    focusScannerMode('title');

    const input = document.getElementById('val-title');

    if (input) {
        input.value = text;
        input.focus();
    }

    showNotification('Example claim loaded. Click Analyze Data to scan it.', 'info');
}

function setDashboardMetric(id, value) {
    const el = document.getElementById(id);

    if (el) {
        el.textContent = value;
    }
}

function updateConfidenceVisual(confidence) {
    const fill = document.getElementById('confidence-fill');

    if (!fill) return;

    const value = Number(confidence);
    const safeValue = Number.isFinite(value)
        ? Math.max(0, Math.min(value, 100))
        : 0;

    fill.style.width = safeValue + '%';

    if (safeValue >= 75) {
        fill.style.background = 'var(--success)';
    } else if (safeValue >= 50) {
        fill.style.background = 'var(--warn)';
    } else {
        fill.style.background = 'var(--danger)';
    }
}

async function loadDashboardOverview() {
    await Promise.allSettled([
        loadDashboardStats(),
        loadRecentAnalyses()
    ]);
}

async function loadDashboardStats() {
    try {
        const response = await fetch('/api/stats');

        if (!response.ok) {
            setDashboardMetric('dash-total-scans', '--');
            setDashboardMetric('dash-supported-count', '--');
            setDashboardMetric('dash-refuted-count', '--');
            return;
        }

        const data = await response.json();
        const verdicts = mergeBreakdown(data.verdict_breakdown || {}, normalizeVerdict);

        setDashboardMetric('dash-total-scans', data.total_analyses || 0);
        setDashboardMetric('dash-supported-count', verdicts.SUPPORTED || 0);
        setDashboardMetric('dash-refuted-count', verdicts.REFUTED || 0);

    } catch (error) {
        console.warn('[Dashboard] Stats unavailable:', error);

        setDashboardMetric('dash-total-scans', '--');
        setDashboardMetric('dash-supported-count', '--');
        setDashboardMetric('dash-refuted-count', '--');
    }
}

async function loadRecentAnalyses() {
    const container = document.getElementById('recent-analyses-content');

    if (!container) return;

    try {
        const response = await fetch('/api/history?limit=3');

        if (!response.ok) {
            setStatusMessage(container, 'Login to see recent scans.', 'var(--muted)');
            return;
        }

        const data = await response.json();

        if (!data.analyses || data.analyses.length === 0) {
            setStatusMessage(container, 'No recent scans yet.', 'var(--muted)');
            return;
        }

        clearElement(container);

        data.analyses.forEach(analysis => {
            const item = document.createElement('div');
            item.className = 'recent-item';
            item.addEventListener('click', () => showAnalysisDetail(analysis.id));

            const title = document.createElement('div');
            title.className = 'recent-item-title';

            const rawText = String(analysis.text_analyzed || '');
            title.textContent = rawText.substring(0, 78) + (rawText.length > 78 ? '...' : '');

            const meta = document.createElement('div');
            meta.className = 'recent-item-meta';

            const verdict = normalizeVerdict(analysis.verdict);

            const verdictSpan = document.createElement('span');
            verdictSpan.className = 'recent-verdict';
            verdictSpan.textContent = verdict;
            verdictSpan.style.color = getVerdictColor(verdict);

            const confSpan = document.createElement('span');
            confSpan.textContent = Number.isFinite(Number(analysis.confidence))
                ? `${analysis.confidence}%`
                : 'N/A';

            meta.appendChild(verdictSpan);
            meta.appendChild(confSpan);

            item.appendChild(title);
            item.appendChild(meta);

            container.appendChild(item);
        });

    } catch (error) {
        console.warn('[Dashboard] Recent analyses unavailable:', error);
        setStatusMessage(container, 'Recent scans unavailable.', 'var(--muted)');
    }
}

// ===== UI SWITCHING =====

function switchTab(e, mode) {
    if (isAnalyzing) {
        showNotification('Analysis in progress. Please wait.', 'warning');
        return;
    }

    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    e.currentTarget.classList.add('active');

    document.querySelectorAll('.input-section').forEach(sec => sec.classList.remove('active'));

    const section = document.getElementById('input-' + mode);
    if (section) {
        section.classList.add('active');
    }

    currentMode = mode;
    updateModeHint(mode);

    console.log(`[UI] Switched to ${mode} input mode`);
}

function switchView(viewId) {
    if (isAnalyzing) {
        showNotification('Analysis in progress. Please wait.', 'warning');
        return;
    }

    document.querySelectorAll('.view-section').forEach(view => view.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));

    const view = document.getElementById('view-' + viewId);
    const nav = document.getElementById('nav-' + viewId);

    if (view) view.classList.add('active');
    if (nav) nav.classList.add('active');

    if (viewId === 'history') {
        loadAnalysisHistory();
    } else if (viewId === 'analytics') {
        loadSystemAnalytics();
    } else if (viewId === 'scanner') {
        loadDashboardOverview();
    }
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;

    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'error' ? 'var(--danger)' : type === 'success' ? 'var(--success)' : type === 'warning' ? 'var(--warn)' : 'var(--accent)'};
        color: white;
        padding: 15px 25px;
        border-radius: 6px;
        z-index: 10000;
        animation: slideInRight 0.3s ease-out;
        font-weight: bold;
        box-shadow: 0 5px 20px rgba(0, 0, 0, 0.3);
        font-family: 'Courier New', Courier, monospace;
    `;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease-out';
        setTimeout(() => notification.remove(), 300);
    }, 4000);
}

// ===== INPUT / RESULTS =====

function getPayload() {
    const inputElement = document.getElementById('val-' + currentMode);
    const val = inputElement ? inputElement.value.trim() : '';

    return {
        type: currentMode,
        text: val
    };
}

function displayError(errorMessage) {
    lastAnalysisReport = null;

    const resPanel = document.getElementById('result-panel');
    const resultEmpty = document.getElementById('result-empty');
    const vSpan = document.getElementById('res-verdict');

    if (resultEmpty) resultEmpty.style.display = 'none';
    if (resPanel) resPanel.style.display = 'block';

    if (vSpan) {
        vSpan.textContent = 'ERROR';
        vSpan.className = 'res-verdict res-error';
    }

    const confidenceEl = document.getElementById('res-confidence');
    const reasonEl = document.getElementById('res-reason');
    const factcheckEl = document.getElementById('res-factcheck');
    const flagsEl = document.getElementById('res-flags');

    if (confidenceEl) confidenceEl.innerText = '';
    if (reasonEl) reasonEl.innerText = errorMessage;
    if (factcheckEl) factcheckEl.innerText = 'N/A';
    if (flagsEl) flagsEl.innerText = 'N/A';

    updateConfidenceVisual(0);

    const sourcesContainer = document.getElementById('res-sources-container');
    if (sourcesContainer) sourcesContainer.style.display = 'none';
}

function renderSources(sources) {
    const sourcesContainer = document.getElementById('res-sources-container');
    const sourcesDiv = document.getElementById('res-sources');

    if (!sourcesContainer || !sourcesDiv) return;

    clearElement(sourcesDiv);

    if (sources && Array.isArray(sources) && sources.length > 0) {
        sourcesContainer.style.display = 'block';

        sources.forEach(src => {
            if (!src.url || !src.title) return;

            if (!src.url.startsWith('http://') && !src.url.startsWith('https://')) {
                console.warn(`[Security] Blocked non-HTTP URL: ${src.url}`);
                return;
            }

            const a = document.createElement('a');
            a.href = src.url;
            a.target = '_blank';
            a.rel = 'noopener noreferrer';
            a.textContent = '[LINK] ' + src.title;

            Object.assign(a.style, {
                color: 'var(--text)',
                textDecoration: 'none',
                fontSize: '13px',
                background: 'rgba(255, 255, 255, 0.05)',
                padding: '8px 12px',
                borderRadius: '4px',
                border: '1px solid var(--border)',
                display: 'block',
                transition: 'border-color 0.2s',
                cursor: 'pointer',
                marginBottom: '5px'
            });

            a.addEventListener('mouseover', () => {
                a.style.borderColor = 'var(--accent)';
            });

            a.addEventListener('mouseout', () => {
                a.style.borderColor = 'var(--border)';
            });

            sourcesDiv.appendChild(a);
        });
    } else {
        sourcesContainer.style.display = 'none';
    }
}

async function startScan(retryCount = 0) {
    if (isAnalyzing) {
        showNotification('Analysis already in progress. Please wait.', 'warning');
        return;
    }

    const payload = getPayload();
    const resPanel = document.getElementById('result-panel');
    const resultEmpty = document.getElementById('result-empty');
    const scanner = document.getElementById('scanner');
    const btn = document.getElementById('analyze-btn');

    if (payload.text.length < 5) {
        displayError('Please provide valid input (at least 5 characters) to analyze.');
        return;
    }

    if (currentMode === 'url') {
        try {
            new URL(payload.text);
        } catch {
            displayError('Please enter a valid URL (e.g., https://example.com/article)');
            return;
        }
    }

    lastAnalysisReport = null;

    if (resultEmpty) resultEmpty.style.display = 'none';
    if (resPanel) resPanel.style.display = 'none';
    if (scanner) scanner.style.display = 'block';

    if (btn) {
        btn.disabled = true;
        btn.innerText = '● SCANNING...';
    }

    isAnalyzing = true;

    console.log(`[API] Starting analysis (attempt ${retryCount + 1}/${MAX_RETRIES + 1})`);

    try {
        const response = await fetch('/analyze', {
            method: 'POST',
            headers: csrfHeaders({
                'Content-Type': 'application/json'
            }),
            body: JSON.stringify(payload),
            signal: AbortSignal.timeout(30000)
        });

        const data = await response.json();

        if (!response.ok) {
            const errorMsg = data.error || `HTTP ${response.status}`;

            if (response.status === 429) {
                displayError(errorMsg);
                showNotification(errorMsg, 'warning');
            } else if (response.status === 400) {
                displayError('Invalid input: ' + errorMsg);
            } else if (response.status >= 500) {
                if (retryCount < MAX_RETRIES) {
                    console.log(`[API] Server error, retrying in ${RETRY_DELAY}ms...`);
                    setTimeout(() => startScan(retryCount + 1), RETRY_DELAY);
                    return;
                }

                displayError('Server error. Please try again later.');
            } else {
                displayError('Error: ' + errorMsg);
            }
        } else {
            if (resPanel) resPanel.style.display = 'block';
            if (resultEmpty) resultEmpty.style.display = 'none';

            const vSpan = document.getElementById('res-verdict');
            const verdict = normalizeVerdict(data.verdict);

            lastAnalysisReport = {
                ...data,
                input_type: currentMode,
                text_analyzed: payload.text,
                generated_at: new Date().toLocaleString()
            };

            if (vSpan) {
                vSpan.innerText = 'VERDICT: ' + verdict;
                vSpan.className = 'res-verdict ' + verdictClass(verdict);
            }

            const confidenceEl = document.getElementById('res-confidence');
            const reasonEl = document.getElementById('res-reason');
            const factcheckEl = document.getElementById('res-factcheck');
            const flagsEl = document.getElementById('res-flags');

            if (confidenceEl) confidenceEl.innerText = 'CONFIDENCE: ' + data.confidence + '%';
            if (reasonEl) reasonEl.textContent = data.reason || 'N/A';
            if (factcheckEl) factcheckEl.textContent = data.fact_check || 'N/A';

            const flagsText = (data.red_flags && data.red_flags.length > 0)
                ? data.red_flags.join(' | ')
                : 'None detected.';

            if (flagsEl) flagsEl.textContent = flagsText;

            updateConfidenceVisual(data.confidence);
            renderSources(data.sources);

            console.log(`[Analysis] Complete: ${verdict} (${data.confidence}%)`);
            showNotification(`Analysis complete: ${verdict} (${data.confidence}% confidence)`, 'success');

            loadDashboardOverview();
        }
    } catch (error) {
        console.error('[Error]', error);

        if (resPanel) resPanel.style.display = 'block';
        if (resultEmpty) resultEmpty.style.display = 'none';

        if (error.name === 'AbortError') {
            if (retryCount < MAX_RETRIES) {
                console.log(`[API] Request timeout, retrying in ${RETRY_DELAY}ms...`);
                setTimeout(() => startScan(retryCount + 1), RETRY_DELAY);
                return;
            }

            displayError('Request timed out. Please check your connection and try again.');
        } else {
            if (retryCount < MAX_RETRIES) {
                console.log(`[API] Network error, retrying in ${RETRY_DELAY}ms...`);
                setTimeout(() => startScan(retryCount + 1), RETRY_DELAY);
                return;
            }

            displayError('Failed to connect to the Core Engine. Please check your connection.');
        }
    } finally {
        if (scanner) scanner.style.display = 'none';

        if (btn) {
            btn.disabled = false;
            btn.innerText = '▶ ANALYZE DATA';
        }

        isAnalyzing = false;
    }
}

async function loadAnalysisHistory() {
    const contentDiv = document.getElementById('history-content');
    setStatusMessage(contentDiv, 'Loading analysis history.');

    try {
        const response = await fetch('/api/history?limit=100');
        const data = await response.json();

        if (!response.ok) {
            setStatusMessage(
                contentDiv,
                'Error loading history: ' + (data.error || 'Unknown error'),
                'var(--danger)'
            );
            return;
        }

        if (!data.analyses || data.analyses.length === 0) {
            cachedHistoryAnalyses = [];
            updateHistoryCountLabel(0, 0);
            setStatusMessage(contentDiv, 'No analyses yet. Start by analyzing some content!');
            return;
        }

        cachedHistoryAnalyses = data.analyses;
        applyHistoryFilters();

    } catch (error) {
        console.error('[Error]', error);
        setStatusMessage(
            contentDiv,
            'Failed to load history: ' + (error.message || 'Unknown error'),
            'var(--danger)'
        );
    }
}

function getHistoryFilters() {
    const searchInput = document.getElementById('history-search');
    const verdictSelect = document.getElementById('history-verdict-filter');
    const modeSelect = document.getElementById('history-mode-filter');
    const sortSelect = document.getElementById('history-sort');

    return {
        search: searchInput ? searchInput.value.trim().toLowerCase() : '',
        verdict: verdictSelect ? verdictSelect.value : 'all',
        mode: modeSelect ? modeSelect.value : 'all',
        sort: sortSelect ? sortSelect.value : 'newest'
    };
}

function applyHistoryFilters() {
    const filters = getHistoryFilters();

    let filtered = [...cachedHistoryAnalyses];

    if (filters.search) {
        filtered = filtered.filter(analysis => {
            const searchableText = [
                analysis.text_analyzed,
                analysis.reason,
                analysis.fact_check,
                analysis.verdict,
                analysis.mode,
                Array.isArray(analysis.red_flags) ? analysis.red_flags.join(' ') : ''
            ]
                .filter(Boolean)
                .join(' ')
                .toLowerCase();

            return searchableText.includes(filters.search);
        });
    }

    if (filters.verdict !== 'all') {
        filtered = filtered.filter(analysis => {
            return normalizeVerdict(analysis.verdict) === filters.verdict;
        });
    }

    if (filters.mode !== 'all') {
        filtered = filtered.filter(analysis => {
            return normalizeModeLabel(analysis.mode) === filters.mode;
        });
    }

    filtered.sort((a, b) => {
        if (filters.sort === 'oldest') {
            return getAnalysisDateValue(a) - getAnalysisDateValue(b);
        }

        if (filters.sort === 'confidence-high') {
            return (Number(b.confidence) || 0) - (Number(a.confidence) || 0);
        }

        if (filters.sort === 'confidence-low') {
            return (Number(a.confidence) || 0) - (Number(b.confidence) || 0);
        }

        return getAnalysisDateValue(b) - getAnalysisDateValue(a);
    });

    renderHistoryTable(filtered);
    updateHistoryCountLabel(filtered.length, cachedHistoryAnalyses.length);
}

function getAnalysisDateValue(analysis) {
    if (!analysis || !analysis.timestamp) return 0;

    const parsedDate = new Date(analysis.timestamp);
    return Number.isNaN(parsedDate.getTime()) ? 0 : parsedDate.getTime();
}

function updateHistoryCountLabel(showing, total) {
    const label = document.getElementById('history-count-label');

    if (!label) return;

    label.textContent = `Showing ${showing} of ${total} analyses`;
}

function resetHistoryFilters() {
    const searchInput = document.getElementById('history-search');
    const verdictSelect = document.getElementById('history-verdict-filter');
    const modeSelect = document.getElementById('history-mode-filter');
    const sortSelect = document.getElementById('history-sort');

    if (searchInput) searchInput.value = '';
    if (verdictSelect) verdictSelect.value = 'all';
    if (modeSelect) modeSelect.value = 'all';
    if (sortSelect) sortSelect.value = 'newest';

    applyHistoryFilters();
}

function renderHistoryTable(analyses) {
    const contentDiv = document.getElementById('history-content');

    if (!contentDiv) return;

    if (!analyses || analyses.length === 0) {
        setStatusMessage(contentDiv, 'No analyses match your filters.', 'var(--muted)');
        return;
    }

    clearElement(contentDiv);

    const tableWrapper = document.createElement('div');
    tableWrapper.className = 'history-table-wrapper';

    const table = document.createElement('table');
    table.className = 'history-table';

    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');

    const headers = [
        { text: 'Text', align: 'left' },
        { text: 'Verdict', align: 'center' },
        { text: 'Confidence', align: 'center' },
        { text: 'Mode', align: 'center' },
        { text: 'Date', align: 'center' }
    ];

    headers.forEach(header => {
        const th = document.createElement('th');
        th.textContent = header.text;
        th.style.textAlign = header.align;
        headerRow.appendChild(th);
    });

    thead.appendChild(headerRow);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');

    analyses.forEach(analysis => {
        const row = document.createElement('tr');
        row.addEventListener('click', () => showAnalysisDetail(analysis.id));

        const rawText = String(analysis.text_analyzed || '');
        const previewText = rawText.substring(0, 65) + (rawText.length > 65 ? '...' : '');

        const textCell = createCell(previewText, 'left');

        const verdict = normalizeVerdict(analysis.verdict);
        const verdictCell = createCell(verdict, 'center');
        verdictCell.style.color = getVerdictColor(verdict);
        verdictCell.style.fontWeight = 'bold';

        const confidenceValue = Number.isFinite(Number(analysis.confidence))
            ? `${analysis.confidence}%`
            : 'N/A';

        const confidenceCell = createCell(confidenceValue, 'center');

        const modeCell = createCell(normalizeModeLabel(analysis.mode), 'center');
        modeCell.style.color = 'var(--muted)';
        modeCell.style.fontSize = '12px';

        let dateText = 'N/A';

        if (analysis.timestamp) {
            const parsedDate = new Date(analysis.timestamp);
            if (!Number.isNaN(parsedDate.getTime())) {
                dateText = parsedDate.toLocaleDateString();
            }
        }

        const dateCell = createCell(dateText, 'center');
        dateCell.style.color = 'var(--muted)';
        dateCell.style.fontSize = '12px';

        row.appendChild(textCell);
        row.appendChild(verdictCell);
        row.appendChild(confidenceCell);
        row.appendChild(modeCell);
        row.appendChild(dateCell);

        tbody.appendChild(row);
    });

    table.appendChild(tbody);
    tableWrapper.appendChild(table);
    contentDiv.appendChild(tableWrapper);
}

// ===== ANALYTICS =====

async function loadSystemAnalytics() {
    const contentDiv = document.getElementById('analytics-content');
    setStatusMessage(contentDiv, 'Loading system analytics.');

    try {
        const response = await fetch('/api/stats');
        const data = await response.json();

        if (!response.ok) {
            setStatusMessage(
                contentDiv,
                'Error loading stats: ' + (data.error || 'Unknown error'),
                'var(--danger)'
            );
            return;
        }

        if (!data.total_analyses || data.total_analyses === 0) {
            setStatusMessage(contentDiv, 'No analyses yet. Run some analyses to see statistics!');
            return;
        }

        clearElement(contentDiv);

        const normalizedVerdictBreakdown = mergeBreakdown(
            data.verdict_breakdown || {},
            normalizeVerdict
        );

        const normalizedModeBreakdown = mergeBreakdown(
            data.mode_breakdown || {},
            normalizeModeLabel
        );

        const grid = document.createElement('div');
        grid.style.display = 'grid';
        grid.style.gridTemplateColumns = '1fr 1fr';
        grid.style.gap = '20px';

        const summaryCard = document.createElement('div');
        summaryCard.style.background = 'rgba(62, 207, 122, 0.1)';
        summaryCard.style.border = '1px solid rgba(62, 207, 122, 0.3)';
        summaryCard.style.padding = '15px';
        summaryCard.style.borderRadius = '6px';

        const summaryTitle = document.createElement('h3');
        summaryTitle.textContent = 'Summary';
        summaryTitle.style.margin = '0 0 10px 0';
        summaryTitle.style.color = 'var(--success)';
        summaryCard.appendChild(summaryTitle);

        const totalP = document.createElement('p');
        totalP.style.margin = '5px 0';
        totalP.style.color = 'var(--text)';
        totalP.textContent = `Total Analyses: ${data.total_analyses}`;
        summaryCard.appendChild(totalP);

        const avgP = document.createElement('p');
        avgP.style.margin = '5px 0';
        avgP.style.color = 'var(--text)';
        avgP.textContent = `Average Confidence: ${data.average_confidence}%`;
        summaryCard.appendChild(avgP);

        grid.appendChild(summaryCard);

        const verdictCard = document.createElement('div');
        verdictCard.style.background = 'rgba(232, 200, 74, 0.1)';
        verdictCard.style.border = '1px solid rgba(232, 200, 74, 0.3)';
        verdictCard.style.padding = '15px';
        verdictCard.style.borderRadius = '6px';

        const verdictTitle = document.createElement('h3');
        verdictTitle.textContent = 'Verdict Breakdown';
        verdictTitle.style.margin = '0 0 10px 0';
        verdictTitle.style.color = 'var(--accent)';
        verdictCard.appendChild(verdictTitle);

        const verdictOrder = [
            'SUPPORTED',
            'REFUTED',
            'MISLEADING',
            'LOW CREDIBILITY',
            'INSUFFICIENT EVIDENCE'
        ];

        Object.entries(normalizedVerdictBreakdown)
            .sort(([a], [b]) => {
                const indexA = verdictOrder.indexOf(a);
                const indexB = verdictOrder.indexOf(b);

                if (indexA === -1 && indexB === -1) return a.localeCompare(b);
                if (indexA === -1) return 1;
                if (indexB === -1) return -1;

                return indexA - indexB;
            })
            .forEach(([verdict, count]) => {
                const p = document.createElement('p');
                p.style.margin = '5px 0';
                p.style.color = getVerdictColor(verdict);

                const strong = document.createElement('strong');
                strong.textContent = verdict;

                p.appendChild(strong);
                p.appendChild(document.createTextNode(`: ${count}`));

                verdictCard.appendChild(p);
            });

        grid.appendChild(verdictCard);

        const modeCard = document.createElement('div');
        modeCard.style.background = 'rgba(100, 100, 200, 0.1)';
        modeCard.style.border = '1px solid rgba(100, 100, 200, 0.3)';
        modeCard.style.padding = '15px';
        modeCard.style.borderRadius = '6px';

        const modeTitle = document.createElement('h3');
        modeTitle.textContent = 'Analysis Mode';
        modeTitle.style.margin = '0 0 10px 0';
        modeTitle.style.color = 'var(--text)';
        modeCard.appendChild(modeTitle);

        Object.entries(normalizedModeBreakdown)
            .sort(([a], [b]) => a.localeCompare(b))
            .forEach(([modeLabel, count]) => {
                const p = document.createElement('p');
                p.style.margin = '5px 0';
                p.style.color = 'var(--text)';

                const strong = document.createElement('strong');
                strong.textContent = modeLabel;

                p.appendChild(strong);
                p.appendChild(document.createTextNode(`: ${count}`));

                modeCard.appendChild(p);
            });

        grid.appendChild(modeCard);
        contentDiv.appendChild(grid);

    } catch (error) {
        console.error('[Error]', error);
        setStatusMessage(
            contentDiv,
            'Failed to load analytics: ' + (error.message || 'Unknown error'),
            'var(--danger)'
        );
    }
}

// ===== MODAL / CLEAR DATABASE =====

let pendingAction = null;

function showClearConfirmation() {
    const modal = document.getElementById('modal-overlay');
    const title = document.getElementById('modal-title');
    const message = document.getElementById('modal-message');
    const footer = document.querySelector('.modal-footer');

    if (!modal || !title || !message || !footer) {
        console.error('Modal overlay not found');
        return;
    }

    title.textContent = 'Clear Database';
    clearElement(message);
    clearElement(footer);

    const warning = document.createElement('p');
    warning.className = 'warning-text';
    warning.textContent = 'WARNING: This will DELETE ALL analyses from the database.';

    const note = document.createElement('p');
    note.textContent = 'This action cannot be undone.';

    const confirmText = document.createElement('p');
    confirmText.textContent = 'Are you absolutely sure?';
    confirmText.style.marginTop = '15px';
    confirmText.style.color = 'var(--danger)';

    message.appendChild(warning);
    message.appendChild(note);
    message.appendChild(confirmText);

    const cancelBtn = document.createElement('button');
    cancelBtn.className = 'modal-btn cancel';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.addEventListener('click', closeModal);

    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'modal-btn confirm';
    deleteBtn.textContent = 'Delete All';
    deleteBtn.style.background = 'var(--danger)';
    deleteBtn.addEventListener('click', confirmAction);

    footer.appendChild(cancelBtn);
    footer.appendChild(deleteBtn);

    pendingAction = 'clearDatabase';
    modal.style.display = 'flex';
}

function closeModal() {
    const modal = document.getElementById('modal-overlay');
    const footer = document.querySelector('.modal-footer');

    if (!modal) return;

    if (footer) {
        clearElement(footer);

        const cancelBtn = document.createElement('button');
        cancelBtn.className = 'modal-btn cancel';
        cancelBtn.textContent = 'Cancel';
        cancelBtn.addEventListener('click', closeModal);

        const confirmBtn = document.createElement('button');
        confirmBtn.className = 'modal-btn confirm';
        confirmBtn.id = 'modal-confirm-btn';
        confirmBtn.textContent = 'Confirm';
        confirmBtn.addEventListener('click', confirmAction);

        footer.appendChild(cancelBtn);
        footer.appendChild(confirmBtn);
    }

    modal.style.display = 'none';
    pendingAction = null;
}

function confirmAction() {
    if (pendingAction === 'clearDatabase') {
        clearAllAnalyses();
    }

    closeModal();
}

async function clearAllAnalyses() {
    try {
        const response = await fetch('/api/clear-database', {
            method: 'POST',
            headers: csrfHeaders({
                'Content-Type': 'application/json'
            })
        });

        const data = await response.json();

        if (response.ok) {
            showNotification(`Database cleared! ${data.deleted} analyses deleted.`, 'success');
            setTimeout(() => {
                loadAnalysisHistory();
                loadDashboardOverview();
            }, 1500);
        } else {
            showNotification(`Error: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error('[Error]', error);
        showNotification(`Failed to clear database: ${error.message}`, 'error');
    }
}

// ===== ANALYSIS DETAIL MODAL =====

async function showAnalysisDetail(analysisId) {
    const modal = document.getElementById('modal-overlay');
    const title = document.getElementById('modal-title');
    const message = document.getElementById('modal-message');
    const footer = document.querySelector('.modal-footer');

    if (!modal || !title || !message || !footer) {
        showNotification('Detail modal not found.', 'error');
        return;
    }

    title.textContent = `Analysis #${analysisId}`;
    clearElement(message);
    clearElement(footer);

    const loading = document.createElement('p');
    loading.textContent = 'Loading analysis details.';
    loading.style.color = 'var(--text)';
    message.appendChild(loading);

    const closeBtn = document.createElement('button');
    closeBtn.className = 'modal-btn cancel';
    closeBtn.textContent = 'Close';
    closeBtn.addEventListener('click', closeModal);
    footer.appendChild(closeBtn);

    pendingAction = null;
    modal.style.display = 'flex';

    try {
        const response = await fetch(`/api/analysis/${analysisId}`);
        const data = await response.json();

        clearElement(message);

        if (!response.ok) {
            const errorBox = document.createElement('p');
            errorBox.textContent = data.error || 'Failed to load analysis details.';
            errorBox.style.color = 'var(--danger)';
            message.appendChild(errorBox);
            return;
        }

        const detailContainer = document.createElement('div');
        detailContainer.style.maxHeight = '65vh';
        detailContainer.style.overflowY = 'auto';
        detailContainer.style.paddingRight = '5px';

        const verdict = normalizeVerdict(data.verdict);
        const verdictColor = getVerdictColor(verdict);

        const summaryBox = document.createElement('div');
        summaryBox.style.display = 'grid';
        summaryBox.style.gridTemplateColumns = '1fr 1fr';
        summaryBox.style.gap = '10px';
        summaryBox.style.marginBottom = '18px';

        const verdictBox = document.createElement('div');
        verdictBox.style.background = 'rgba(255,255,255,0.03)';
        verdictBox.style.border = '1px solid var(--border)';
        verdictBox.style.borderRadius = '6px';
        verdictBox.style.padding = '12px';

        const verdictLabel = document.createElement('div');
        verdictLabel.textContent = 'VERDICT';
        verdictLabel.style.color = 'var(--accent)';
        verdictLabel.style.fontWeight = 'bold';
        verdictLabel.style.marginBottom = '6px';

        const verdictValue = document.createElement('div');
        verdictValue.textContent = verdict;
        verdictValue.style.color = verdictColor;
        verdictValue.style.fontWeight = 'bold';

        verdictBox.appendChild(verdictLabel);
        verdictBox.appendChild(verdictValue);

        const confidenceBox = document.createElement('div');
        confidenceBox.style.background = 'rgba(255,255,255,0.03)';
        confidenceBox.style.border = '1px solid var(--border)';
        confidenceBox.style.borderRadius = '6px';
        confidenceBox.style.padding = '12px';

        const confidenceLabel = document.createElement('div');
        confidenceLabel.textContent = 'CONFIDENCE';
        confidenceLabel.style.color = 'var(--accent)';
        confidenceLabel.style.fontWeight = 'bold';
        confidenceLabel.style.marginBottom = '6px';

        const confidenceValue = document.createElement('div');
        confidenceValue.textContent = Number.isFinite(Number(data.confidence))
            ? `${data.confidence}%`
            : 'N/A';
        confidenceValue.style.color = 'var(--text)';
        confidenceValue.style.fontWeight = 'bold';

        confidenceBox.appendChild(confidenceLabel);
        confidenceBox.appendChild(confidenceValue);

        summaryBox.appendChild(verdictBox);
        summaryBox.appendChild(confidenceBox);
        detailContainer.appendChild(summaryBox);

        let dateText = 'N/A';

        if (data.timestamp) {
            const parsedDate = new Date(data.timestamp);
            if (!Number.isNaN(parsedDate.getTime())) {
                dateText = parsedDate.toLocaleString();
            }
        }

        detailContainer.appendChild(createDetailRow('DATE', dateText));
        detailContainer.appendChild(createDetailRow('MODE', data.mode || 'N/A'));
        detailContainer.appendChild(createDetailRow('TEXT ANALYZED', data.text_analyzed || 'N/A', {
            monospace: true,
            preWrap: true
        }));
        detailContainer.appendChild(createDetailRow('REASON', data.reason || 'N/A', {
            preWrap: true
        }));
        detailContainer.appendChild(createDetailRow('FACT-CHECK', data.fact_check || 'N/A', {
            preWrap: true
        }));

        const redFlags = Array.isArray(data.red_flags) && data.red_flags.length > 0
            ? data.red_flags.join(' | ')
            : 'None detected.';

        detailContainer.appendChild(createDetailRow('RED FLAGS', redFlags, {
            color: redFlags === 'None detected.' ? 'var(--text)' : 'var(--warn)',
            preWrap: true
        }));

        const sourcesSection = document.createElement('div');
        sourcesSection.style.marginTop = '16px';

        const sourcesTitle = document.createElement('div');
        sourcesTitle.textContent = 'SOURCES';
        sourcesTitle.style.color = 'var(--accent)';
        sourcesTitle.style.fontWeight = 'bold';
        sourcesTitle.style.marginBottom = '8px';
        sourcesTitle.style.fontSize = '13px';

        sourcesSection.appendChild(sourcesTitle);

        if (Array.isArray(data.sources) && data.sources.length > 0) {
            data.sources.forEach((src, index) => {
                const sourceLink = document.createElement('a');

                const sourceTitle = src.title || `Source ${index + 1}`;
                const url = src.url || '';

                sourceLink.textContent = `[${index + 1}] ${sourceTitle}`;
                sourceLink.style.display = 'block';
                sourceLink.style.color = 'var(--text)';
                sourceLink.style.textDecoration = 'none';
                sourceLink.style.border = '1px solid var(--border)';
                sourceLink.style.background = 'rgba(255,255,255,0.03)';
                sourceLink.style.borderRadius = '6px';
                sourceLink.style.padding = '8px 10px';
                sourceLink.style.marginBottom = '6px';
                sourceLink.style.wordBreak = 'break-word';

                if (url.startsWith('http://') || url.startsWith('https://')) {
                    sourceLink.href = url;
                    sourceLink.target = '_blank';
                    sourceLink.rel = 'noopener noreferrer';
                } else {
                    sourceLink.href = '#';
                    sourceLink.addEventListener('click', event => event.preventDefault());
                    sourceLink.style.opacity = '0.6';
                }

                sourceLink.addEventListener('mouseover', () => {
                    sourceLink.style.borderColor = 'var(--accent)';
                });

                sourceLink.addEventListener('mouseout', () => {
                    sourceLink.style.borderColor = 'var(--border)';
                });

                sourcesSection.appendChild(sourceLink);
            });
        } else {
            const noSources = document.createElement('p');
            noSources.textContent = 'No sources stored for this analysis.';
            noSources.style.color = 'var(--muted)';
            sourcesSection.appendChild(noSources);
        }

        detailContainer.appendChild(sourcesSection);
        message.appendChild(detailContainer);
    } catch (error) {
        console.error('[Error]', error);
        clearElement(message);

        const errorBox = document.createElement('p');
        errorBox.textContent = 'Failed to load analysis details: ' + (error.message || 'Unknown error');
        errorBox.style.color = 'var(--danger)';
        message.appendChild(errorBox);
    }
}

// ===== CLEAR UI =====

function clearUI() {
    if (isAnalyzing) {
        showNotification('Analysis in progress. Cannot clear.', 'warning');
        return;
    }

    lastAnalysisReport = null;

    const textInput = document.getElementById('val-text');
    const urlInput = document.getElementById('val-url');
    const titleInput = document.getElementById('val-title');
    const resultPanel = document.getElementById('result-panel');
    const resultEmpty = document.getElementById('result-empty');

    if (textInput) textInput.value = '';
    if (urlInput) urlInput.value = '';
    if (titleInput) titleInput.value = '';

    if (resultPanel) resultPanel.style.display = 'none';
    if (resultEmpty) resultEmpty.style.display = 'grid';

    updateConfidenceVisual(0);

    const btn = document.getElementById('analyze-btn');

    if (btn) {
        btn.disabled = false;
        btn.innerText = '▶ ANALYZE DATA';
    }

    console.log('[UI] Cleared');
}

// ===== USER DROPDOWN INFO MODALS =====

function createInfoModal(titleText, bodyBuilder) {
    const modal = document.getElementById('modal-overlay');
    const title = document.getElementById('modal-title');
    const message = document.getElementById('modal-message');
    const footer = document.querySelector('.modal-footer');

    if (!modal || !title || !message || !footer) {
        showNotification('Modal not found.', 'error');
        return;
    }

    title.textContent = titleText;
    clearElement(message);
    clearElement(footer);

    bodyBuilder(message);

    const closeBtn = document.createElement('button');
    closeBtn.className = 'modal-btn cancel';
    closeBtn.textContent = 'Close';
    closeBtn.addEventListener('click', closeModal);

    footer.appendChild(closeBtn);

    pendingAction = null;
    modal.style.display = 'flex';
}

function createModalSection(container, heading, text) {
    const box = document.createElement('div');
    box.style.border = '1px solid var(--border)';
    box.style.background = 'rgba(255,255,255,0.035)';
    box.style.borderRadius = '8px';
    box.style.padding = '12px';
    box.style.marginBottom = '10px';

    const h = document.createElement('h4');
    h.textContent = heading;
    h.style.color = 'var(--accent)';
    h.style.margin = '0 0 8px 0';

    const p = document.createElement('p');
    p.textContent = text;
    p.style.color = 'var(--text)';
    p.style.lineHeight = '1.6';
    p.style.margin = '0';

    box.appendChild(h);
    box.appendChild(p);
    container.appendChild(box);
}

function createModalList(container, heading, items) {
    const box = document.createElement('div');
    box.style.border = '1px solid var(--border)';
    box.style.background = 'rgba(255,255,255,0.035)';
    box.style.borderRadius = '8px';
    box.style.padding = '12px';
    box.style.marginBottom = '10px';

    const h = document.createElement('h4');
    h.textContent = heading;
    h.style.color = 'var(--accent)';
    h.style.margin = '0 0 8px 0';

    const ul = document.createElement('ul');
    ul.style.margin = '0 0 0 18px';
    ul.style.padding = '0';
    ul.style.color = 'var(--text)';
    ul.style.lineHeight = '1.7';

    items.forEach(item => {
        const li = document.createElement('li');
        li.textContent = item;
        ul.appendChild(li);
    });

    box.appendChild(h);
    box.appendChild(ul);
    container.appendChild(box);
}

function showAboutModal() {
    createInfoModal('About DEBUNK.IT', (container) => {
        const wrapper = document.createElement('div');
        wrapper.style.maxHeight = '65vh';
        wrapper.style.overflowY = 'auto';
        wrapper.style.paddingRight = '8px';

        createModalSection(
            wrapper,
            'What is DEBUNK.IT?',
            'DEBUNK.IT is an AI-assisted misinformation analysis system that helps users examine headlines, URLs, and full article text using source-aware reasoning.'
        );

        createModalList(wrapper, 'What it can analyze', [
            'News headlines and short public claims.',
            'Article URLs using webpage scraping.',
            'Full article text pasted by the user.',
            'Claims that may be supported, refuted, misleading, low credibility, or lacking enough evidence.'
        ]);

        createModalList(wrapper, 'Core features', [
            'AI-powered claim analysis.',
            'Live source scanning.',
            'URL article extraction.',
            'Analysis history for logged-in users.',
            'Verdict confidence score.',
            'Reason, fact-check summary, red flags, and sources.'
        ]);

        createModalSection(
            wrapper,
            'Important limitation',
            'DEBUNK.IT is not a final truth authority. Breaking news, old videos, satire, edited media, and conflicting sources may still require manual verification.'
        );

        container.appendChild(wrapper);
    });
}

function showHelpModal() {
    createInfoModal('Get Help', (container) => {
        const wrapper = document.createElement('div');
        wrapper.style.maxHeight = '65vh';
        wrapper.style.overflowY = 'auto';
        wrapper.style.paddingRight = '8px';

        createModalList(wrapper, 'How to use the scanner', [
            'Use HEADLINE mode for quick claims or news titles.',
            'Use URL mode when you have a full article link.',
            'Use TEXT mode when you want to paste a full article or long message.',
            'Click Analyze Data and wait for the verdict, confidence, reason, fact-check, and red flags.'
        ]);

        createModalList(wrapper, 'Verdict meaning', [
            'SUPPORTED: credible evidence supports the central claim.',
            'REFUTED: credible evidence contradicts the central claim.',
            'INSUFFICIENT EVIDENCE: sources do not clearly prove or disprove it.',
            'MISLEADING: partly true but missing context or framed unfairly.',
            'LOW CREDIBILITY: weak sourcing, risky pattern, or suspicious claim.'
        ]);

        createModalList(wrapper, 'Tips for better results', [
            'Paste the exact headline instead of vague summaries.',
            'For URLs, use the direct article link, not a homepage link.',
            'For viral images or videos, describe where and when it claims to be from.',
            'Check the sources section before trusting the result.'
        ]);

        createModalSection(
            wrapper,
            'Need more control?',
            'Go to Settings to change theme, background, language, privacy preferences, password, and account options.'
        );

        container.appendChild(wrapper);
    });
}

function showLanguageModal() {
    createInfoModal('Language', (container) => {
        const wrapper = document.createElement('div');
        wrapper.style.display = 'grid';
        wrapper.style.gap = '12px';

        const info = document.createElement('p');
        info.textContent = 'Choose your preferred language. This currently affects the Settings page and saved language preference.';
        info.style.color = 'var(--text)';
        info.style.lineHeight = '1.6';
        info.style.margin = '0';

        const select = document.createElement('select');
        select.id = 'quick-language-select';
        select.style.width = '100%';
        select.style.padding = '12px';
        select.style.borderRadius = '6px';
        select.style.border = '1px solid var(--border)';
        select.style.background = 'rgba(255,255,255,0.04)';
        select.style.color = 'var(--text)';
        select.style.fontFamily = 'inherit';

        const languages = [
            { value: 'en', label: 'English' },
            { value: 'hi', label: 'हिन्दी' },
            { value: 'ja', label: '日本語' }
        ];

        const savedLanguage = localStorage.getItem('debunkit_language') || 'en';

        languages.forEach(lang => {
            const option = document.createElement('option');
            option.value = lang.value;
            option.textContent = lang.label;

            if (lang.value === savedLanguage) {
                option.selected = true;
            }

            select.appendChild(option);
        });

        const note = document.createElement('p');
        note.textContent = 'For full language controls, open Settings.';
        note.style.color = 'var(--muted)';
        note.style.fontSize = '13px';
        note.style.lineHeight = '1.5';
        note.style.margin = '0';

        const actions = document.createElement('div');
        actions.style.display = 'flex';
        actions.style.gap = '10px';
        actions.style.marginTop = '8px';

        const saveBtn = document.createElement('button');
        saveBtn.className = 'modal-btn confirm';
        saveBtn.textContent = 'Save Language';
        saveBtn.addEventListener('click', () => {
            const selectedLanguage = document.getElementById('quick-language-select').value;
            localStorage.setItem('debunkit_language', selectedLanguage);
            showNotification('Language preference saved.', 'success');
            closeModal();
        });

        const settingsBtn = document.createElement('button');
        settingsBtn.className = 'modal-btn cancel';
        settingsBtn.textContent = 'Open Settings';
        settingsBtn.addEventListener('click', () => {
            window.location.href = '/settings';
        });

        actions.appendChild(saveBtn);
        actions.appendChild(settingsBtn);

        wrapper.appendChild(info);
        wrapper.appendChild(select);
        wrapper.appendChild(note);
        wrapper.appendChild(actions);

        container.appendChild(wrapper);
    });
}

console.log('[Main.js] Loaded successfully');