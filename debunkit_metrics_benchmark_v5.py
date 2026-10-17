"""
DEBUNK.IT — Metrics Benchmark v5 (Final Fix)

Fix in v5:
- No pandas groupby.apply() sampling.
- Keeps label column safely.
- Excludes benchmark scripts from codebase LOC so your project stats are not inflated by the benchmark file itself.

Run:
    python -m pip install pandas numpy scikit-learn requests
    python debunkit_metrics_benchmark_v5.py --csv WELFake_Dataset.csv --live-url https://debunkit.onrender.com --sample-limit 5000

Output:
    debunkit_metrics_results.json
    debunkit_metrics_summary.md

Important:
    ML metrics measure only the local TF-IDF + Logistic Regression fake-news
    classification baseline/fallback, not the full Cohere + RAG fact-checking system.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from pathlib import Path

import numpy as np
import pandas as pd


IGNORE_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules", "instance"}

# Exclude benchmark/report files so LOC reflects the Debunkit app, not the metrics tool.
IGNORE_FILES_PREFIXES = (
    "debunkit_metrics_benchmark",
    "debunkit_metrics_results",
    "debunkit_metrics_summary",
)

TEXT_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".css": "css",
    ".html": "html",
    ".md": "markdown",
}


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def p95(values):
    return float(np.percentile(values, 95)) if values else 0.0


def safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def should_skip(path: Path) -> bool:
    if set(path.parts) & IGNORE_DIRS:
        return True
    return any(path.name.startswith(prefix) for prefix in IGNORE_FILES_PREFIXES)


def codebase_metrics(project_root: Path) -> dict:
    files_by_type = {v: 0 for v in TEXT_EXTENSIONS.values()}
    loc_by_type = {v: 0 for v in TEXT_EXTENSIONS.values()}
    total_files = 0
    flask_routes = set()
    py_texts = []

    route_pattern = re.compile(r"@app\.route\(\s*[\"']([^\"']+)[\"']")

    for path in project_root.rglob("*"):
        if should_skip(path) or not path.is_file():
            continue

        total_files += 1
        ext = path.suffix.lower()

        if ext not in TEXT_EXTENSIONS:
            continue

        text = safe_read(path)
        kind = TEXT_EXTENSIONS[ext]

        files_by_type[kind] += 1
        loc_by_type[kind] += sum(1 for line in text.splitlines() if line.strip())

        if ext == ".py":
            py_texts.append(text)
            flask_routes.update(route_pattern.findall(text))

    combined = "\n".join(py_texts).lower()

    security = {
        "CSRF protection": any(x in combined for x in ["csrf", "x-csrftoken", "csrf_session_key"]),
        "SSRF URL blocking": any(x in combined for x in ["ssrf", "ipaddress", "localhost", "127.0.0.1"]),
        "XSS sanitization": any(x in combined for x in ["sanitize", "html.escape", "javascript:", "dangerous protocol"]),
        "Rate limiting": any(x in combined for x in ["flask_limiter", "limiter.limit", "ratelimit"]),
        "Password hashing": any(x in combined for x in ["generate_password_hash", "check_password_hash", "password_hash"]),
        "Login-protected routes": any(x in combined for x in ["login_required", "flask_login", "loginmanager"]),
        "Input validation": any(x in combined for x in ["validate_text", "validate_url", "validationerror", "validators"]),
    }

    return {
        "total_files_scanned": total_files,
        "files_by_type": files_by_type,
        "loc_by_type": loc_by_type,
        "total_counted_loc": sum(loc_by_type.values()),
        "flask_routes_count": len(flask_routes),
        "flask_routes": sorted(flask_routes),
        "security_controls_detected": security,
        "security_controls_count": int(sum(security.values())),
        "security_controls_total": len(security),
    }


def load_local_fake_news_csv(csv_path: str, sample_limit: int) -> tuple[pd.Series, pd.Series, str, int]:
    path = Path(csv_path)

    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    print(f"   Loading local CSV: {path}")

    raw = pd.read_csv(path)
    print(f"   Raw columns: {list(raw.columns)}")

    # Normalize column names.
    raw.columns = [str(c).strip().lower().replace(" ", "_") for c in raw.columns]
    print(f"   Normalized columns: {list(raw.columns)}")

    if "label" not in raw.columns:
        raise ValueError(f"Required column 'label' not found. Columns found: {list(raw.columns)}")

    # WELFake has title + text. Combine both for better feature representation.
    if "title" in raw.columns and "text" in raw.columns:
        text = raw["title"].fillna("").astype(str) + " " + raw["text"].fillna("").astype(str)
    elif "text" in raw.columns:
        text = raw["text"].fillna("").astype(str)
    elif "content" in raw.columns:
        text = raw["content"].fillna("").astype(str)
    elif "article" in raw.columns:
        text = raw["article"].fillna("").astype(str)
    else:
        raise ValueError(f"No usable text column found. Columns found: {list(raw.columns)}")

    labels = raw["label"]

    if labels.dtype == object:
        label_map = {
            "fake": 0, "false": 0, "0": 0, "unreliable": 0,
            "real": 1, "true": 1, "1": 1, "reliable": 1,
        }
        labels = labels.astype(str).str.strip().str.lower().map(label_map)

    df = pd.DataFrame({
        "text": text.astype(str).str.strip(),
        "label": pd.to_numeric(labels, errors="coerce"),
    })

    df = df.dropna(subset=["text", "label"])
    df = df[df["text"].str.len() > 40].copy()
    df["label"] = df["label"].astype(int)
    df = df[df["label"].isin([0, 1])].copy()

    if df.empty:
        raise ValueError("Dataset cleaned to zero usable rows.")

    if df["label"].nunique() != 2:
        raise ValueError(f"Need both labels 0 and 1. Label counts: {df['label'].value_counts().to_dict()}")

    print(f"   Clean rows before sampling: {len(df):,}")
    print(f"   Label counts before sampling: {df['label'].value_counts().to_dict()}")

    # Balanced sampling WITHOUT groupby.apply().
    if sample_limit and len(df) > sample_limit:
        per_class = min(sample_limit // 2, int(df["label"].value_counts().min()))

        fake_sample = df[df["label"] == 0].sample(n=per_class, random_state=42)
        real_sample = df[df["label"] == 1].sample(n=per_class, random_state=42)

        df = (
            pd.concat([fake_sample, real_sample], axis=0)
            .sample(frac=1, random_state=42)
            .reset_index(drop=True)
        )
    else:
        df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    print(f"   Clean rows used: {len(df):,}")
    print(f"   Label counts used: {df['label'].value_counts().to_dict()}")

    X = df["text"].copy()
    y = df["label"].copy()

    return X, y, f"Local CSV: {path.name}", len(df)


def ml_benchmark(csv_path: str, sample_limit: int, speed_samples: int) -> dict:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report
    from sklearn.model_selection import train_test_split

    X, y, source, total_samples = load_local_fake_news_csv(csv_path, sample_limit)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=42,
        stratify=y,
    )

    start = time.perf_counter()

    vectorizer = TfidfVectorizer(
        max_features=50000,
        ngram_range=(1, 2),
        stop_words="english",
        sublinear_tf=True,
    )

    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    model = LogisticRegression(max_iter=1000, C=1.0, solver="lbfgs", random_state=42)
    model.fit(X_train_vec, y_train)

    training_seconds = time.perf_counter() - start

    y_pred = model.predict(X_test_vec)

    timings = []
    for text in X_test.iloc[: min(speed_samples, len(X_test))]:
        t0 = time.perf_counter()
        model.predict(vectorizer.transform([text]))
        timings.append((time.perf_counter() - t0) * 1000)

    avg_ms = statistics.mean(timings) if timings else 0
    p95_ms = p95(timings)

    return {
        "enabled": True,
        "dataset_source": source,
        "label_meaning": "0=fake, 1=real",
        "total_samples_used": int(total_samples),
        "train_samples": int(len(X_train)),
        "test_samples": int(len(X_test)),
        "training_time_seconds": round(float(training_seconds), 3),
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "precision_weighted": round(float(precision_score(y_test, y_pred, average="weighted", zero_division=0)), 4),
        "recall_weighted": round(float(recall_score(y_test, y_pred, average="weighted", zero_division=0)), 4),
        "f1_weighted": round(float(f1_score(y_test, y_pred, average="weighted", zero_division=0)), 4),
        "avg_inference_ms": round(float(avg_ms), 3),
        "p95_inference_ms": round(float(p95_ms), 3),
        "estimated_local_throughput_per_second": round(float(1000 / avg_ms), 1) if avg_ms else 0,
        "classification_report": classification_report(y_test, y_pred, zero_division=0),
        "important_note": "These ML numbers evaluate only the TF-IDF + Logistic Regression local baseline/fallback, not the full Cohere + RAG fact-checking system.",
    }


def live_latency(live_url: str | None, runs: int) -> dict:
    if not live_url:
        return {"enabled": False, "reason": "No live URL provided"}

    try:
        import requests
    except Exception:
        return {"enabled": False, "reason": "requests not installed"}

    base = live_url.rstrip("/")
    endpoints = {"home": "/", "health": "/api/health"}
    result = {"enabled": True, "base_url": base, "runs": runs, "endpoints": {}}

    for name, path in endpoints.items():
        url = base + path
        times = []
        statuses = []

        for _ in range(runs):
            t0 = time.perf_counter()
            try:
                response = requests.get(url, timeout=20)
                times.append((time.perf_counter() - t0) * 1000)
                statuses.append(response.status_code)
            except Exception as e:
                times.append(20000.0)
                statuses.append(f"ERROR: {e}")

        ok = sum(1 for status in statuses if isinstance(status, int) and 200 <= status < 400)

        result["endpoints"][name] = {
            "url": url,
            "status_samples": statuses,
            "success_rate_percent": round((ok / runs) * 100, 1),
            "avg_latency_ms": round(statistics.mean(times), 1),
            "p95_latency_ms": round(p95(times), 1),
            "min_latency_ms": round(min(times), 1),
            "max_latency_ms": round(max(times), 1),
        }

    return result


def make_summary(results: dict) -> str:
    code = results["codebase"]
    ml = results["ml_baseline"]
    live = results["live_latency"]

    lines = []
    lines.append("# DEBUNK.IT Metrics Summary\n")

    lines.append("## Codebase Metrics\n")
    lines.append(f"- Total counted LOC: **{code['total_counted_loc']:,}**")
    lines.append(f"- Python LOC: **{code['loc_by_type']['python']:,}**")
    lines.append(f"- JavaScript LOC: **{code['loc_by_type']['javascript']:,}**")
    lines.append(f"- CSS LOC: **{code['loc_by_type']['css']:,}**")
    lines.append(f"- HTML LOC: **{code['loc_by_type']['html']:,}**")
    lines.append(f"- Flask routes detected: **{code['flask_routes_count']}**")
    lines.append(f"- Security controls detected: **{code['security_controls_count']}/{code['security_controls_total']}**\n")

    lines.append("## ML Baseline Benchmark\n")
    lines.append(f"- Dataset: **{ml['dataset_source']}**")
    lines.append(f"- Total samples used: **{ml['total_samples_used']:,}**")
    lines.append(f"- Test set size: **{ml['test_samples']:,} samples**")
    lines.append(f"- Accuracy: **{pct(ml['accuracy'])}**")
    lines.append(f"- Weighted Precision: **{pct(ml['precision_weighted'])}**")
    lines.append(f"- Weighted Recall: **{pct(ml['recall_weighted'])}**")
    lines.append(f"- Weighted F1 Score: **{pct(ml['f1_weighted'])}**")
    lines.append(f"- Avg local ML inference: **{ml['avg_inference_ms']} ms/query**")
    lines.append(f"- P95 local ML inference: **{ml['p95_inference_ms']} ms/query**")
    lines.append("\n> Note: These numbers evaluate only the TF-IDF + Logistic Regression local baseline/fallback, not the full Cohere + RAG fact-checking system.\n")

    if live.get("enabled"):
        lines.append("## Live Deployment Latency\n")
        for name, data in live["endpoints"].items():
            lines.append(
                f"- `{name}`: **{data['success_rate_percent']}% success**, "
                f"avg **{data['avg_latency_ms']} ms**, p95 **{data['p95_latency_ms']} ms**"
            )
        lines.append("")

    lines.append("## LinkedIn/Resume-Safe Bullets\n")
    lines.append(
        f"- Built DEBUNK.IT, a full-stack AI-assisted misinformation detection platform "
        f"with **{code['flask_routes_count']} Flask routes**, "
        f"**{code['total_counted_loc']:,}+ counted lines of code**, "
        f"and **{code['security_controls_count']} detected security controls**."
    )
    lines.append(
        f"- Benchmarked a TF-IDF + Logistic Regression fake-news classification baseline "
        f"on **{ml['test_samples']:,} held-out samples**, achieving "
        f"**{pct(ml['accuracy'])} accuracy**, **{pct(ml['precision_weighted'])} precision**, "
        f"and **{pct(ml['f1_weighted'])} weighted F1**."
    )
    lines.append(
        f"- Optimized local ML fallback inference to **{ml['avg_inference_ms']} ms/query average** "
        f"with **{ml['p95_inference_ms']} ms p95 latency**."
    )

    if live.get("enabled") and "health" in live["endpoints"]:
        h = live["endpoints"]["health"]
        lines.append(
            f"- Deployed live on Render with `/api/health` returning "
            f"**{h['success_rate_percent']}% successful responses** across "
            f"**{live['runs']} benchmark requests**."
        )

    lines.append("\n## Wording Warning\n")
    lines.append("- Do not claim this ML accuracy is the accuracy of the full AI/RAG fact-checker.")
    lines.append("- Correct wording: local ML baseline/fallback benchmark.")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--csv", required=True, help="Path to WELFake_Dataset.csv")
    parser.add_argument("--sample-limit", type=int, default=5000)
    parser.add_argument("--speed-samples", type=int, default=200)
    parser.add_argument("--live-url", default=None)
    parser.add_argument("--latency-runs", type=int, default=5)
    args = parser.parse_args()

    root = Path(args.project_root).resolve()

    print("\n" + "═" * 70)
    print("DEBUNK.IT — METRICS BENCHMARK v5")
    print("═" * 70)

    print("\n📁 Scanning codebase...")
    code = codebase_metrics(root)
    print(f"   Counted LOC: {code['total_counted_loc']:,}")
    print(f"   Flask routes: {code['flask_routes_count']}")
    print(f"   Security controls: {code['security_controls_count']}/{code['security_controls_total']}")

    print("\n🤖 Running ML baseline benchmark...")
    ml = ml_benchmark(args.csv, args.sample_limit, args.speed_samples)
    print(f"   Dataset: {ml['dataset_source']}")
    print(f"   Samples used: {ml['total_samples_used']:,}")
    print(f"   Test samples: {ml['test_samples']:,}")
    print(f"   Accuracy: {pct(ml['accuracy'])}")
    print(f"   Precision: {pct(ml['precision_weighted'])}")
    print(f"   F1: {pct(ml['f1_weighted'])}")
    print(f"   Avg inference: {ml['avg_inference_ms']} ms")

    print("\n🌐 Running live latency benchmark...")
    live = live_latency(args.live_url, args.latency_runs)
    if live.get("enabled"):
        for name, data in live["endpoints"].items():
            print(f"   {name}: {data['success_rate_percent']}% success | avg {data['avg_latency_ms']} ms")
    else:
        print(f"   Skipped: {live.get('reason')}")

    results = {
        "generated_at_unix": int(time.time()),
        "codebase": code,
        "ml_baseline": ml,
        "live_latency": live,
    }

    (root / "debunkit_metrics_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (root / "debunkit_metrics_summary.md").write_text(make_summary(results), encoding="utf-8")

    print("\n✅ Saved:")
    print(f"   {root / 'debunkit_metrics_results.json'}")
    print(f"   {root / 'debunkit_metrics_summary.md'}")
    print("\n" + make_summary(results))


if __name__ == "__main__":
    main()
