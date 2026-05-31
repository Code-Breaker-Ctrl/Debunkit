
<div align="center">

<img src="Static/Images/debunkit-logo.png" alt="DEBUNK.IT Logo" width="80"/>

# DEBUNK.IT

**AI-powered misinformation detection platform**

[![Python](https://img.shields.io/badge/Python-3.10+-e8c84a?style=for-the-badge&logo=python&logoColor=black)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.x-e8c84a?style=for-the-badge&logo=flask&logoColor=black)](https://flask.palletsprojects.com)
[![Cohere](https://img.shields.io/badge/Cohere_AI-command--r-3ecf7a?style=for-the-badge)](https://cohere.com)
[![License](https://img.shields.io/badge/License-MIT-6f7890?style=for-the-badge)](LICENSE)
[![Version](https://img.shields.io/badge/Version-3.0-e05252?style=for-the-badge)](#)

*Analyze claims before they spread.*

</div>

---

## 📸 Overview

![DEBUNK.IT Dashboard](docs/screenshots/ss1_dashboard.png)

**DEBUNK.IT** is a full-stack, AI-assisted fact-checking web platform that analyzes **headlines**, **article URLs**, and **full text** for misinformation. It combines:

- 🤖 **Cohere LLM** for source-aware AI reasoning
- 🌐 **Live web search (RAG)** via DuckDuckGo for real-time context
- 📊 **TF-IDF + Logistic Regression** as a trained local ML fallback
- 🔍 **Custom NLP engine** for pattern-based offline analysis
- 🔒 **Security-first architecture** — CSRF, SSRF, XSS, rate limiting

Built for the modern misinformation landscape — sports claims, political statements, health news, viral videos, and general news across Indian and international sources.

---

## ✨ Features

| Feature | Description |
|--------|-------------|
| 🔍 **Hybrid AI Pipeline** | Cohere LLM + ML model + NLP fallback — always returns a verdict |
| 🌐 **Live RAG Search** | Multi-query DuckDuckGo search with fact-check source detection |
| 🔗 **URL Article Scraper** | Extracts article content and uses it as primary evidence |
| 🛡️ **Security-First** | CSRF tokens, SSRF blocking, XSS sanitization, rate limiting, hashed passwords |
| 📚 **Analysis History** | Full searchable/filterable history with verdict statistics per user |
| 📊 **Engine Telemetry** | Verdict breakdown, confidence averages, mode usage analytics |
| 📋 **Report Export** | Copy or download full analysis reports as `.txt` files |
| 🎨 **Polished Dark UI** | Animated Matrix-style background, dark/light theme, monospace terminal aesthetic |
| 💾 **Smart Caching** | Results cached per user (6h for URLs, 24h for text) |
| 👤 **User Accounts** | Register, login, profile management, settings, account deletion |

---

## 📸 Screenshots

<table>
  <tr>
    <td align="center">
      <img src="docs/screenshots/ss5_scanner.png" alt="Live Scanner with REFUTED verdict" width="100%"/>
      <br><sub><b>Live Scanner — REFUTED verdict at 85% confidence</b></sub>
    </td>
    <td align="center">
      <img src="docs/screenshots/ss2_login.png" alt="Login page with animated background" width="100%"/>
      <br><sub><b>Login page — animated canvas background</b></sub>
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="docs/screenshots/ss3_history.png" alt="Analysis History Database Ledger" width="100%"/>
      <br><sub><b>Database Ledger — full analysis history with filters</b></sub>
    </td>
    <td align="center">
      <img src="docs/screenshots/ss4_analytics.png" alt="Engine Telemetry Analytics" width="100%"/>
      <br><sub><b>Engine Telemetry — verdict breakdown & stats</b></sub>
    </td>
  </tr>
</table>

---

## 🧠 How It Works

```
User submits Headline / URL / Text
           │
           ▼
   Input Validation & Sanitization
   (length, null bytes, SSRF, XSS)
           │
           ▼ (URL mode only)
   Article Scraper
   (BeautifulSoup, redirect validation)
           │
           ▼
   RAG — Live Web Search
   (DuckDuckGo: entity + direct + fact-check queries)
           │
           ▼
   ┌─────────────────────────┐
   │   Cohere AI Analysis    │  ← Domain-aware prompts
   │  (command-r-08-2024)    │    (sports / health /
   │                         │     political / general)
   └───────────┬─────────────┘
               │ fails?
               ▼
   Local NLP Fallback
   (pattern scoring + public figure claim detection)
           │
           ▼
   Verdict + Confidence Score
   Cached to DB (if logged in)
```

### Verdict System

| Verdict | Meaning |
|---------|---------|
| ✅ `SUPPORTED` | Credible evidence confirms the central claim |
| ❌ `REFUTED` | Credible sources contradict the claim |
| ⚠️ `MISLEADING` | Partly true but missing context, old media, or misrepresented |
| 🔍 `INSUFFICIENT EVIDENCE` | Sources don't clearly confirm or deny |
| 🚩 `LOW CREDIBILITY` | Suspicious language/weak sourcing, can't be directly refuted |

---

## 🗂️ Project Structure

```
Debunkit/
├── debunkit_app.py          # Flask app — all routes & API endpoints
├── config.py                # Config classes (Dev / Prod / Test)
├── requirements.txt         # Python dependencies
├── training.py              # ML model training (TF-IDF + LogReg)
├── dataset.py               # Dataset inspection utility
│
├── Core/
│   ├── ai_engine.py         # Cohere AI + hybrid analysis logic
│   ├── rag_engine.py        # DuckDuckGo live search + article scraper
│   ├── nlp_engine.py        # Local NLP pattern engine (offline fallback)
│   ├── database.py          # SQLAlchemy models + DB helpers
│   └── user_model.py        # User auth model (Flask-Login)
│
├── utils/
│   ├── validators.py        # Input validation + SSRF protection
│   └── sanitizer.py         # XSS / URL injection prevention
│
├── Template/                # Jinja2 HTML templates
│   ├── index.html           # Main dashboard (scanner, history, analytics)
│   ├── login.html
│   ├── register.html
│   ├── profile.html
│   └── settings.html
│
└── Static/
    ├── CSS/                 # style.css, auth.css, profile.css
    ├── Images/              # Logo and assets
    └── JS/
        ├── canvas.js        # Animated falling-words background
        └── main.js          # Full frontend logic (~900 lines)
```

---

## ⚙️ Tech Stack

**Backend**
- [Flask](https://flask.palletsprojects.com/) — web framework
- [Flask-Login](https://flask-login.readthedocs.io/) — user session management
- [Flask-Limiter](https://flask-limiter.readthedocs.io/) — rate limiting
- [Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/) — ORM (SQLite / PostgreSQL)
- [Flask-CORS](https://flask-cors.readthedocs.io/) — cross-origin resource sharing

**AI / ML**
- [Cohere API](https://cohere.com/) (`command-r-08-2024`) — primary AI fact-checker
- [scikit-learn](https://scikit-learn.org/) — TF-IDF + Logistic Regression local model
- [DuckDuckGo Search](https://pypi.org/project/duckduckgo-search/) (`ddgs`) — RAG live web context
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) — article scraping

**Frontend**
- Jinja2 templates + vanilla JS (~900 lines)
- CSS custom properties — dark/light theme
- HTML5 Canvas — animated background

---

## 🚀 Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/Code-Breaker-Ctrl/Debunkit.git
cd Debunkit
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up environment variables

Create a `.env` file in the project root:

```env
COHERE_API_KEY=your_cohere_api_key_here
SECRET_KEY=your_flask_secret_key_here
DATABASE_URL=sqlite:///debunkit.db
FLASK_ENV=development
```

> Get a free Cohere API key at [cohere.com](https://cohere.com)

### 4. (Optional) Train the local ML model

```bash
python training.py
```

> Requires `news_benchmark_200_clean.csv` in the project root.  
> Skip this step to run with AI-only mode (Cohere).

### 5. Run the app

```bash
python debunkit_app.py
```

Open **http://127.0.0.1:5000** in your browser.

---

## 🔐 Security Architecture

DEBUNK.IT is built with a layered security approach:

| Layer | Protection |
|-------|-----------|
| `validators.py` | Input length limits, null byte stripping, URL scheme enforcement, **SSRF blocking** via DNS resolution |
| `sanitizer.py` | **XSS prevention** — HTML escaping, script tag removal, dangerous protocol blocking (`javascript:`, `data:`) |
| `debunkit_app.py` | **CSRF token** validation on every `POST / PUT / PATCH / DELETE` request |
| `main.js` | Sends CSRF token in `X-CSRFToken` header; blocks non-HTTP source URLs in the DOM |
| `config.py` | Rate limiting (10/day guests, 20/min users), password complexity regex, secure session cookies |

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/analyze` | Main analysis endpoint |
| `GET` | `/api/history` | Get user's analysis history |
| `GET` | `/api/analysis/<id>` | Get specific analysis details |
| `GET` | `/api/search?q=` | Search past analyses |
| `GET` | `/api/stats` | Get verdict statistics |
| `POST` | `/api/clear-database` | Delete all user analyses |
| `GET/PUT` | `/api/user/profile` | View or update profile |
| `PUT` | `/api/user/settings` | Update theme, password, preferences |
| `DELETE` | `/api/user/delete` | Delete account and all data |
| `GET` | `/api/health` | Health check |

---

## 🌍 Deployment

### Environment Variables (Production)

```env
FLASK_ENV=production
SECRET_KEY=<strong-random-secret>
COHERE_API_KEY=<your-key>
DATABASE_URL=postgresql://user:pass@host/dbname
SESSION_COOKIE_SECURE=True
RATELIMIT_ENABLED=True
```

### Run with Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 debunkit_app:app
```

### Docker (coming soon)

```dockerfile
# Dockerfile support planned for v3.1
```

---

## ⚠️ Limitations

- **Not a final truth authority.** DEBUNK.IT is an AI-assisted tool, not a replacement for human judgment.
- Breaking news, satire, AI-generated images, and conflicting sources may still require manual verification.
- The local ML model (`training.py`) is a style classifier — it detects writing patterns, not factual truth.
- AI analysis requires a valid **Cohere API key**. Without it, the system falls back to local NLP only.
- Search results depend on DuckDuckGo availability — analysis quality may vary for very recent events.

---

## 🗺️ Roadmap

- [ ] Docker support
- [ ] Hindi language UI
- [ ] Image/video claim analysis
- [ ] Browser extension
- [ ] Public API with authentication
- [ ] Multilingual fact-checking support

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add: your feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

Built by **[Code-Breaker-Ctrl](https://github.com/Code-Breaker-Ctrl)**

*DEBUNK.IT v3.0 — AI-powered misinformation detection*

⭐ Star this repo if you found it useful!

</div>
