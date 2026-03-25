"""
Data Ingestion Script
Reads SAP O2C JSONL dataset, cleans it, and outputs a data quality report.
Cleaned data is saved to /data/cleaned/ as CSV for graph loading.
"""

import os
import sys
import json
import glob
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "sap-o2c-data"
CLEANED_DIR = DATA_DIR / "cleaned"


def load_jsonl_folder(folder_path):
    """Read all .jsonl files in a folder into a single DataFrame."""
    records = []
    for jsonl_file in sorted(glob.glob(str(folder_path / "*.jsonl"))):
        with open(jsonl_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)


def clean_dataframe(df, name):
    """Clean a single DataFrame: normalize IDs, handle nulls, flatten nested, standardize dates."""
    # Flatten nested dict columns (e.g., creationTime: {hours, minutes, seconds})
    for col in df.columns:
        if df[col].apply(lambda x: isinstance(x, dict)).any():
            # Convert time dicts to HH:MM:SS strings
            df[col] = df[col].apply(
                lambda x: f"{x['hours']:02d}:{x['minutes']:02d}:{x['seconds']:02d}"
                if isinstance(x, dict) and "hours" in x else x
            )

    # Strip whitespace from string columns
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace({"nan": None, "None": None, "": None, "NaT": None, "none": None})

    # Parse date columns
    date_keywords = ["date", "DateTime"]
    for col in df.columns:
        if any(kw.lower() in col.lower() for kw in date_keywords) and "time" not in col.lower().replace("datetime", ""):
            try:
                df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
                df[col] = df[col].dt.strftime("%Y-%m-%d")
                df[col] = df[col].replace({"NaT": None})
            except Exception:
                pass

    return df


def generate_report(datasets):
    """Print a data quality report for all datasets."""
    print("\n" + "=" * 80)
    print("  DATA QUALITY REPORT")
    print("=" * 80)

    total_rows = 0
    for name, df in sorted(datasets.items()):
        total_rows += len(df)
        print(f"\n{'─' * 60}")
        print(f"  TABLE: {name}")
        print(f"{'─' * 60}")
        print(f"  Rows:    {len(df):,}")
        print(f"  Columns: {len(df.columns)}")
        print(f"  Columns: {list(df.columns)}")

        # Null percentages
        null_pct = (df.isnull().sum() / max(len(df), 1) * 100).round(2)
        non_zero_nulls = null_pct[null_pct > 0]
        if len(non_zero_nulls) > 0:
            print(f"  Null % (non-zero):")
            for col, pct in non_zero_nulls.items():
                print(f"    {col}: {pct}%")
        else:
            print(f"  Null %: None")

        # Unique key counts for likely primary keys (first 1-2 columns)
        for col in df.columns[:3]:
            unique_count = df[col].nunique()
            print(f"  Unique [{col}]: {unique_count:,}")

    print(f"\n{'─' * 60}")
    print(f"  TOTAL RECORDS: {total_rows:,}")
    print(f"{'=' * 80}")
    print("  END OF REPORT")
    print(f"{'=' * 80}\n")


def main():
    print("🔍 Looking for SAP O2C dataset...")

    if not RAW_DIR.exists():
        print(f"❌ Dataset folder not found at {RAW_DIR}")
        print("   Please extract the dataset zip into /data/sap-o2c-data/")
        sys.exit(1)

    # Discover entity folders
    entity_folders = sorted([
        d for d in RAW_DIR.iterdir()
        if d.is_dir() and any(d.glob("*.jsonl"))
    ])

    print(f"📂 Found {len(entity_folders)} entity tables:")
    for f in entity_folders:
        print(f"   - {f.name}")

    datasets = {}

    for folder in entity_folders:
        name = folder.name
        print(f"\n📖 Loading: {name}...")
        df = load_jsonl_folder(folder)
        if df.empty:
            print(f"   ⚠️ Empty - skipping")
            continue
        print(f"   → {len(df):,} rows, {len(df.columns)} columns")
        df = clean_dataframe(df, name)
        datasets[name] = df

    # Save cleaned data as CSV
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in datasets.items():
        output_path = CLEANED_DIR / f"{name}.csv"
        df.to_csv(output_path, index=False)
        print(f"💾 Saved: {output_path.name}")

    # Generate report
    generate_report(datasets)

    print(f"✅ Ingestion complete! {len(datasets)} table(s) cleaned and saved to /data/cleaned/")
    return datasets


if __name__ == "__main__":
    main()
