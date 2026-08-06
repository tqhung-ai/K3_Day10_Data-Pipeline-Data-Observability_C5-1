import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

project_root = Path(r"d:\AI thực chiến\K3_Day10_Data-Pipeline-Data-Observability_C5-1")
sys.path.insert(0, str(project_root / "src"))

from core.config import load_settings
from ingestion.crossref import fetch_source_records
from ingestion.cleaning import build_clean_dataframe
from evaluation.testset import build_test_set
from core.utils import write_csv

def main():
    settings = load_settings(project_root)
    print("Fetching raw records (Role 2)...")
    records = fetch_source_records(settings)
    print(f"Fetched {len(records)} raw records.")
    
    print("Building clean dataframe (Role 3)...")
    clean_df = build_clean_dataframe(records, datetime.utcnow())
    print(f"Clean dataframe created with {len(clean_df)} records.")
    write_csv(clean_df, settings.paths.clean_csv)
    print(f"Saved clean CSV to {settings.paths.clean_csv}")
    
    print("Building test set (Role 5)...")
    test_set = build_test_set(clean_df, settings.paths.eval_testset)
    print(f"Generated test set with {len(test_set)} questions.")
    print(f"Saved test set to {settings.paths.eval_testset}")

if __name__ == "__main__":
    main()
