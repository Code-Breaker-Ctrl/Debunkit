/* =====================================================
   Debunk.IT – main.js
   Dashboard analysis UI
   ===================================================== */

// Character counter
const claimInput = document.getElementById('claimInput');
const charCount  = document.getElementById('charCount');

if (claimInput) {
  claimInput.addEventListener('input', () => {
    charCount.textContent = claimInput.value.length;
  });
}

// Clear input
function clearInput() {
  if (claimInput) {
    claimInput.value = '';
    charCount.textContent = '0';
    document.getElementById('resultCard').classList.add('hidden');
  }
}

// ---------------------------------------------------------------------------
// Run analysis
// ---------------------------------------------------------------------------
async function runAnalysis() {
  const text = claimInput ? claimInput.value.trim() : '';
  if (!text) {
    showToast('Please enter some text to analyze.', 'warning');
    return;
  }
  if (text.length < 20) {
    showToast('Text is too short – please enter at least 20 characters.', 'warning');
    return;
  }

  const analyzeBtn = document.getElementById('analyzeBtn');
  const btnText    = document.getElementById('btnText');
  const btnSpinner = document.getElementById('btnSpinner');

  analyzeBtn.disabled = true;
  btnText.classList.add('hidden');
  btnSpinner.classList.remove('hidden');

  try {
    const response = await fetch('/analyze', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken,
      },
      body: JSON.stringify({ text }),
    });

    const data = await response.json();

    if (!response.ok) {
      showToast(data.error || 'Analysis failed. Please try again.', 'danger');
      return;
    }

    renderResult(data);

  } catch (err) {
    showToast('Network error. Please check your connection.', 'danger');
    console.error(err);
  } finally {
    analyzeBtn.disabled = false;
    btnText.classList.remove('hidden');
    btnSpinner.classList.add('hidden');
  }
}

// ---------------------------------------------------------------------------
// Render result
// ---------------------------------------------------------------------------
function renderResult(data) {
  const resultCard    = document.getElementById('resultCard');
  const verdictBanner = document.getElementById('verdictBanner');
  const verdictIcon   = document.getElementById('verdictIcon');
  const verdictLabel  = document.getElementById('verdictLabel');
  const confidenceBar = document.getElementById('confidenceBar');
  const confidencePct = document.getElementById('confidencePct');
  const resultReason  = document.getElementById('resultReason');
  const resultFactCheck = document.getElementById('resultFactCheck');
  const redFlagsSection = document.getElementById('redFlagsSection');
  const redFlagsList    = document.getElementById('redFlagsList');
  const sourcesSection  = document.getElementById('sourcesSection');
  const sourcesList     = document.getElementById('sourcesList');
  const resultMode      = document.getElementById('resultMode');

  const verdict    = (data.verdict || 'UNCERTAIN').toUpperCase();
  const confidence = parseInt(data.confidence || 50, 10);

  // Verdict banner
  verdictBanner.className = 'verdict-banner ' + verdict.toLowerCase();

  const icons = { REAL: '✅', FAKE: '❌', UNCERTAIN: '⚠️' };
  verdictIcon.textContent  = icons[verdict] || '❔';
  verdictLabel.textContent = verdict;

  // Confidence bar
  confidenceBar.style.setProperty('--pct', confidence + '%');
  confidencePct.textContent = confidence + '%';

  // Text fields
  resultReason.textContent    = data.reason    || '—';
  resultFactCheck.textContent = data.fact_check || '—';

  // Mode badge
  resultMode.textContent = data.mode === 'ai' ? '🤖 AI' : '🔧 Local NLP';

  // Red flags
  const flags = Array.isArray(data.red_flags) ? data.red_flags : [];
  if (flags.length > 0) {
    redFlagsList.innerHTML = flags.map(f => `<li>${escHtml(f)}</li>`).join('');
    redFlagsSection.classList.remove('hidden');
  } else {
    redFlagsSection.classList.add('hidden');
  }

  // Sources
  const sources = Array.isArray(data.sources) ? data.sources : [];
  if (sources.length > 0) {
    sourcesList.innerHTML = sources.map(s => {
      const title   = escHtml(s.title   || s.url || 'Source');
      const url     = escHtml(s.url     || '#');
      const snippet = escHtml(s.snippet || '');
      return `<li><a href="${url}" target="_blank" rel="noopener noreferrer">${title}</a>${snippet ? ' – ' + snippet : ''}</li>`;
    }).join('');
    sourcesSection.classList.remove('hidden');
  } else {
    sourcesSection.classList.add('hidden');
  }

  // Show card
  resultCard.classList.remove('hidden');
  resultCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function showToast(message, category = 'info') {
  const container = document.querySelector('.flash-container') || (() => {
    const c = document.createElement('div');
    c.className = 'flash-container';
    document.body.appendChild(c);
    return c;
  })();

  const flash = document.createElement('div');
  flash.className = `flash flash-${category}`;
  flash.innerHTML = `${escHtml(message)}<button class="flash-close" onclick="this.parentElement.remove()">✕</button>`;
  container.appendChild(flash);

  setTimeout(() => flash.remove(), 5000);
}

// Password visibility toggle (used on auth pages)
function togglePassword(fieldId) {
  const field = document.getElementById(fieldId);
  if (field) {
    field.type = field.type === 'password' ? 'text' : 'password';
  }
}

// Allow Ctrl+Enter / Cmd+Enter to submit
if (claimInput) {
  claimInput.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      runAnalysis();
    }
  });
}
