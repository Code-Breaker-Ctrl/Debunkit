import pandas as pd

df = pd.read_csv("news_benchmark_200_clean.csv")

print("Rows:", len(df))
print("Cols:", len(df.columns))
print("Columns:", list(df.columns))
print("Nulls:\n", df.isnull().sum())
print("Unique labels:", df["label"].unique())
print("Label counts:\n", df["label"].value_counts())
print("Duplicate IDs:", df["id"].duplicated().sum())
print("ID min/max:", df["id"].min(), df["id"].max())