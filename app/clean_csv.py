import os
import pandas as pd

INPUT_FOLDER = "app/data"
OUTPUT_FOLDER = "app/cleaned_data"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

REMOVE_WORDS = [
    "href",
    "src",
    "image",
    "img",
    "lazy",
    "tablescraper",
    "unnamed"
]


def should_remove(col):
    col = str(col).lower()

    for word in REMOVE_WORDS:
        if word in col:
            return True
    return False


def read_csv_safely(path):
    encodings = ["utf-8", "latin1", "cp1252"]

    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except:
            continue

    print(f"❌ Could not read: {path}")
    return None


for file in os.listdir(INPUT_FOLDER):
    if file.endswith(".csv"):
        try:
            print(f"Cleaning {file}")

            path = os.path.join(INPUT_FOLDER, file)

            df = read_csv_safely(path)

            if df is None:
                continue

            keep_cols = []

            for col in df.columns:
                if not should_remove(col):
                    keep_cols.append(col)

            cleaned_df = df[keep_cols]

            cleaned_df = cleaned_df.dropna(
                axis=1,
                how="all"
            )

            output_path = os.path.join(
                OUTPUT_FOLDER,
                file
            )

            cleaned_df.to_csv(
                output_path,
                index=False,
                encoding="utf-8"
            )

            print(f"✅ Saved {file}")

        except Exception as e:
            print(f"Error in {file}: {e}")

print("All files cleaned successfully")