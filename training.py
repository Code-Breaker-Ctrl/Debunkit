import pandas as pd
import numpy as np
import joblib

from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix, roc_auc_score
)

# 1) Load
df = pd.read_csv("news_benchmark_200_clean.csv")

# 2) Cleanup
df = df.dropna(subset=["title", "text", "label"])
df["label"] = df["label"].astype(str).str.strip().str.upper()
df = df[df["label"].isin(["FAKE", "REAL"])].copy()

# 3) Features/target
df["combined_text"] = df["title"].fillna("") + " " + df["text"].fillna("")
X = df["combined_text"].values
y = df["label"].map({"FAKE": 0, "REAL": 1}).values

# 4) Model pipeline
pipe = Pipeline([
    ("tfidf", TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.95
    )),
    ("clf", LogisticRegression(max_iter=3000, class_weight="balanced"))
])

# 5) Cross-validation (stable estimate)
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_acc = cross_val_score(pipe, X, y, cv=cv, scoring="accuracy")
print(f"5-Fold CV Accuracy: {cv_acc.mean():.4f} ± {cv_acc.std():.4f}")

# 6) Train/test split for detailed metrics
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

pipe.fit(X_train, y_train)

# 7) Predict
pred = pipe.predict(X_test)
proba = pipe.predict_proba(X_test)[:, 1]  # probability of REAL

print("\nHoldout Accuracy:", accuracy_score(y_test, pred))
print("\nClassification Report:")
print(classification_report(y_test, pred, target_names=["FAKE", "REAL"]))

cm = confusion_matrix(y_test, pred)
print("\nConfusion Matrix [ [TN, FP], [FN, TP] ]:")
print(cm)

try:
    auc = roc_auc_score(y_test, proba)
    print(f"\nROC-AUC: {auc:.4f}")
except Exception:
    pass

# 8) Save model
joblib.dump(pipe, "fake_news_tfidf_logreg.joblib")
print("\nSaved model: fake_news_tfidf_logreg.joblib")

# 9) Save test predictions for error analysis
out = pd.DataFrame({
    "text": X_test,
    "true_label": np.where(y_test == 1, "REAL", "FAKE"),
    "pred_label": np.where(pred == 1, "REAL", "FAKE"),
    "prob_real": proba
})
out.to_csv("test_predictions.csv", index=False, encoding="utf-8")
print("Saved predictions: test_predictions.csv")