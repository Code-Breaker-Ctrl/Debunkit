# DEBUNK.IT Metrics Summary

## Codebase Metrics

- Total counted LOC: **17,244**
- Python LOC: **4,939**
- JavaScript LOC: **2,948**
- CSS LOC: **3,954**
- HTML LOC: **5,072**
- Flask routes detected: **17**
- Security controls detected: **7/7**

## ML Baseline Benchmark

- Dataset: **Local CSV: WELFake_Dataset.csv**
- Total samples used: **5,000**
- Test set size: **1,000 samples**
- Accuracy: **93.0%**
- Weighted Precision: **93.0%**
- Weighted Recall: **93.0%**
- Weighted F1 Score: **93.0%**
- Avg local ML inference: **1.573 ms/query**
- P95 local ML inference: **2.728 ms/query**

> Note: These numbers evaluate only the TF-IDF + Logistic Regression local baseline/fallback, not the full Cohere + RAG fact-checking system.

## Live Deployment Latency

- `home`: **60.0% success**, avg **8522.4 ms**, p95 **20000.0 ms**
- `health`: **100.0% success**, avg **116.0 ms**, p95 **130.7 ms**

## LinkedIn/Resume-Safe Bullets

- Built DEBUNK.IT, a full-stack AI-assisted misinformation detection platform with **17 Flask routes**, **17,244+ counted lines of code**, and **7 detected security controls**.
- Benchmarked a TF-IDF + Logistic Regression fake-news classification baseline on **1,000 held-out samples**, achieving **93.0% accuracy**, **93.0% precision**, and **93.0% weighted F1**.
- Optimized local ML fallback inference to **1.573 ms/query average** with **2.728 ms p95 latency**.
- Deployed live on Render with `/api/health` returning **100.0% successful responses** across **5 benchmark requests**.

## Wording Warning

- Do not claim this ML accuracy is the accuracy of the full AI/RAG fact-checker.
- Correct wording: local ML baseline/fallback benchmark.