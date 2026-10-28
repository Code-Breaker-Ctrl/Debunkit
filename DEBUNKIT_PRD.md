# Product Requirements Document (PRD): DEBUNK.IT

## 1. Overview
**Product Name:** DEBUNK.IT  
**Tagline:** AI-powered misinformation detection and fact-checking intelligence platform.  
**Live Application URL:** https://debunkit-production.up.railway.app  
**Target Audience:** Researchers, journalists, students, and general internet users seeking to verify claims, news headlines, and online articles.

---

## 2. Core Value Proposition
DEBUNK.IT is an end-to-end fact-checking platform that combines live web search (RAG via DuckDuckGo), Cohere Large Language Models (Command-R series), and local machine learning fallbacks (TF-IDF + Logistic Regression) to deliver transparent, evidence-based verdicts on news headlines, URLs, and long-form text.

---

## 3. Key User Workflows & Testing Requirements

### 3.1 Scanner Modes
The home page features a multi-mode analysis engine:
1. **Headline Check:**
   - **User Action:** Selects the "HEADLINE" tab. Enters a short claim (e.g., "NASA discovers water on the moon").
   - **Execution:** User clicks `ANALYZE DATA`.
   - **Expected Outcome:** Engine triggers RAG web search, calls the AI reasoning engine, and renders an Analysis Report card containing:
     - Verdict tag (`SUPPORTED`, `REFUTED`, or `INSUFFICIENT EVIDENCE`).
     - Confidence percentage score bar (0–100%).
     - Detailed explanation reasoning with cited sources.
2. **URL Article Scan:**
   - **User Action:** Selects the "URL" tab. Enters an article link (e.g., `https://en.wikipedia.org/wiki/Artificial_intelligence`).
   - **Validation:** Must reject invalid URLs or malicious schemes (SSRF protection).
   - **Expected Outcome:** Scrapes text and evaluates truthfulness against web facts.
3. **Full Text Analysis:**
   - **User Action:** Selects the "TEXT" tab. Pastes a multi-sentence paragraph.
   - **Expected Outcome:** Full claim decomposition and verification report.

### 3.2 Report Actions
- **Copy Report:** Clicking `COPY REPORT` copies the markdown summary to the clipboard and shows a toast notification.
- **Download Report:** Clicking `DOWNLOAD REPORT` downloads a `.txt` file containing the analysis breakdown.
- **Clear Input:** Clicking `CLEAR` clears the active input box and resets the result panel.

### 3.3 Example Prompts
- Quick-example pills (e.g., "Old video claim", "Prediction claim", "Misleading sports claim") populate the input field with one click.

### 3.4 Navigation & Guest Access
- **Guest Mode:** Non-logged-in visitors receive 10 free scans per day.
- **Header Status:** Displays system status indicator (`SYS.STATE: OPTIMAL`).
- **Sidebar Links:**
  - `Live Scanner` (Home page)
  - `Analysis History` (Requires sign-in)
  - `System Analytics` (Engine telemetry and aggregate statistics)
- **Authentication Pages:**
  - `LOGIN` modal/page (`/login`)
  - `SIGN UP` registration page (`/register`)

---

## 4. UI & Visual Requirements
- Monospace terminal aesthetic with dark theme by default.
- Interactive animated Matrix canvas background.
- Responsive mobile & desktop layout.
- Proper error toast notifications when input is less than 5 characters or empty.
