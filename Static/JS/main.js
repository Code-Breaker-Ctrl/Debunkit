/* ===================================================
   Debunkit – Frontend logic
   HTML structure lives in Template/index.html.
   This file handles data fetching and DOM updates.
   =================================================== */

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const targetId = btn.dataset.view;

        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.view-section').forEach(s => s.classList.remove('active'));

        btn.classList.add('active');
        document.getElementById(targetId).classList.add('active');

        if (targetId === 'view-history')   loadAnalysisHistory();
        if (targetId === 'view-analytics') loadSystemAnalytics();
    });
});

// ---------------------------------------------------------------------------
// Character counter
// ---------------------------------------------------------------------------

const claimInput   = document.getElementById('claim-input');
const charCounter  = document.getElementById('char-counter');

claimInput.addEventListener('input', () => {
    const len = claimInput.value.length;
    charCounter.textContent = `${len} / 5000`;
    charCounter.style.color = len > 4800 ? 'var(--danger)' : 'var(--muted)';
});

// ---------------------------------------------------------------------------
// Analyse claim
// ---------------------------------------------------------------------------

async function runAnalysis() {
    const text       = claimInput.value.trim();
    const useWebSrc  = document.getElementById('use-web-sources').checked;
    const btn        = document.getElementById('analyse-btn');
    const spinner    = document.getElementById('spinner');
    const resultCard = document.getElementById('result-card');
    const errorDiv   = document.getElementById('analyse-error');

    if (!text) {
        showError(errorDiv, 'Please enter a claim to analyse.');
        return;
    }
    if (text.length > 5000) {
        showError(errorDiv, 'Claim is too long (max 5000 characters).');
        return;
    }

    // UI: loading state
    btn.disabled = true;
    spinner.classList.remove('hidden');
    resultCard.classList.add('hidden');
    errorDiv.classList.add('hidden');

    try {
        const response = await fetch('/api/analyse', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ text, use_web_sources: useWebSrc }),
        });

        const data = await response.json();

        if (!response.ok) {
            showError(errorDiv, data.error || 'Analysis failed. Please try again.');
            return;
        }

        renderResult(data);
    } catch (err) {
        console.error('[Debunkit] analyse error:', err);
        showError(errorDiv, 'Network error. Please check your connection.');
    } finally {
        btn.disabled = false;
        spinner.classList.add('hidden');
    }
}

function renderResult(data) {
    const card     = document.getElementById('result-card');
    const badge    = document.getElementById('result-verdict-badge');
    const confEl   = document.getElementById('result-confidence');
    const summaryEl = document.getElementById('result-summary');
    const sourcesEl = document.getElementById('result-sources');
    const flagsEl   = document.getElementById('result-red-flags');
    const domainEl  = document.getElementById('result-domain');
    const flagBlock = document.getElementById('red-flags-block');

    const verdict    = data.verdict    || 'UNCERTAIN';
    const confidence = data.confidence || 0;

    badge.textContent = verdict;
    badge.className   = `verdict-badge verdict-${verdict}`;
    confEl.textContent = `${confidence}% confidence`;

    summaryEl.textContent  = data.summary        || '—';
    sourcesEl.textContent  = data.source_analysis || 'No source analysis available.';
    domainEl.textContent   = (data.domain || 'general').charAt(0).toUpperCase() +
                              (data.domain || 'general').slice(1);

    // Red flags list
    flagsEl.innerHTML = '';
    const flags = Array.isArray(data.red_flags) ? data.red_flags : [];
    if (flags.length > 0) {
        flags.forEach(flag => {
            const li = document.createElement('li');
            li.textContent = flag;
            flagsEl.appendChild(li);
        });
        flagBlock.style.display = 'block';
    } else {
        flagBlock.style.display = 'none';
    }

    card.classList.remove('hidden');
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ---------------------------------------------------------------------------
// Analysis history
// ---------------------------------------------------------------------------

async function loadAnalysisHistory() {
    const contentDiv = document.getElementById('history-content');
    contentDiv.innerHTML = '<p>Loading…</p>';

    try {
        const response = await fetch('/api/history?limit=20');
        const data     = await response.json();

        if (!response.ok) {
            contentDiv.innerHTML = `<p style="color:var(--danger)">Error: ${data.error}</p>`;
            return;
        }

        if (data.analyses.length === 0) {
            contentDiv.innerHTML = '<p style="color:var(--muted)">No analyses yet. Start by analysing some content!</p>';
            return;
        }

        // Build table
        const table = document.createElement('table');
        table.className = 'history-table';

        table.innerHTML = `
            <thead>
              <tr>
                <th>Claim</th>
                <th>Verdict</th>
                <th>Confidence</th>
                <th>Domain</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody id="history-tbody"></tbody>`;

        const tbody = table.querySelector('#history-tbody');

        data.analyses.forEach(analysis => {
            const date    = new Date(analysis.timestamp).toLocaleDateString();
            const snippet = analysis.text_analyzed.length > 55
                ? analysis.text_analyzed.substring(0, 55) + '…'
                : analysis.text_analyzed;

            const tr = document.createElement('tr');
            tr.style.cursor = 'pointer';
            tr.addEventListener('click', () => showAnalysisDetail(analysis));
            tr.innerHTML = `
                <td>${escapeHtml(snippet)}</td>
                <td><span class="verdict-pill pill-${analysis.verdict}">${analysis.verdict}</span></td>
                <td>${analysis.confidence}%</td>
                <td>${analysis.domain || '—'}</td>
                <td style="color:var(--muted);font-size:0.85rem">${date}</td>`;
            tbody.appendChild(tr);
        });

        contentDiv.innerHTML = '';
        contentDiv.appendChild(table);

    } catch (err) {
        console.error('[Debunkit] history error:', err);
        contentDiv.innerHTML = `<p style="color:var(--danger)">Failed to load history: ${escapeHtml(err.message)}</p>`;
    }
}

function showAnalysisDetail(analysis) {
    const flags = Array.isArray(analysis.red_flags) ? analysis.red_flags : [];
    const flagText = flags.length > 0 ? '\n🚩 ' + flags.join('\n🚩 ') : 'None';

    alert(
        `ID: #${analysis.id}\n` +
        `Verdict: ${analysis.verdict} (${analysis.confidence}%)\n` +
        `Domain: ${analysis.domain || '—'}\n\n` +
        `Summary: ${analysis.summary || '—'}\n\n` +
        `Source analysis: ${analysis.source_analysis || '—'}\n\n` +
        `Red flags: ${flagText}`
    );
}

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

async function loadSystemAnalytics() {
    const contentDiv = document.getElementById('analytics-content');
    contentDiv.innerHTML = '<p>Loading…</p>';

    try {
        const response = await fetch('/api/stats');
        const data     = await response.json();

        if (!response.ok) {
            contentDiv.innerHTML = `<p style="color:var(--danger)">Error: ${data.error}</p>`;
            return;
        }

        if (data.total_analyses === 0) {
            contentDiv.innerHTML = '<p style="color:var(--muted)">No analyses yet. Run some analyses to see statistics!</p>';
            return;
        }

        // Verdict breakdown rows
        let verdictRows = '';
        for (const [verdict, count] of Object.entries(data.verdict_breakdown || {})) {
            verdictRows += `<p><span class="verdict-pill pill-${verdict}">${verdict}</span>  ${count}</p>`;
        }

        // Mode breakdown rows
        let modeRows = '';
        for (const [mode, count] of Object.entries(data.mode_breakdown || {})) {
            const label = mode === 'ai' ? '🤖 AI Analysis' : '📊 Local NLP';
            modeRows += `<p>${label}: <strong>${count}</strong></p>`;
        }

        contentDiv.innerHTML = `
            <div class="analytics-grid">
              <div class="stat-card">
                <h3>Total Analyses</h3>
                <div class="stat-value">${data.total_analyses}</div>
              </div>
              <div class="stat-card">
                <h3>Avg Confidence</h3>
                <div class="stat-value">${data.average_confidence}%</div>
              </div>
              <div class="stat-card">
                <h3>Verdict Breakdown</h3>
                ${verdictRows}
              </div>
              <div class="stat-card">
                <h3>Analysis Mode</h3>
                ${modeRows}
              </div>
            </div>`;

    } catch (err) {
        console.error('[Debunkit] analytics error:', err);
        contentDiv.innerHTML = `<p style="color:var(--danger)">Failed to load analytics: ${escapeHtml(err.message)}</p>`;
    }
}

// ---------------------------------------------------------------------------
// Clear database
// ---------------------------------------------------------------------------

async function clearAllAnalyses() {
    if (!confirm('⚠️ This will DELETE ALL analyses from the database. This cannot be undone.\n\nAre you sure?')) {
        return;
    }
    if (!confirm('🚨 FINAL CONFIRMATION: Delete all analysis records permanently?')) {
        return;
    }

    try {
        const response = await fetch('/api/clear-database', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
        });
        const data = await response.json();

        if (response.ok) {
            alert(`✅ Database cleared — ${data.deleted} analyses deleted.`);
            loadAnalysisHistory();
        } else {
            alert(`❌ Error: ${data.error}`);
        }
    } catch (err) {
        console.error('[Debunkit] clear-database error:', err);
        alert(`❌ Failed to clear database: ${err.message}`);
    }
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function showError(el, message) {
    el.textContent = message;
    el.classList.remove('hidden');
}

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Allow pressing Enter (without Shift) in the textarea to submit
claimInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        runAnalysis();
    }
});
