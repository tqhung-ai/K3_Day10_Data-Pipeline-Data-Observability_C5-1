from __future__ import annotations

from typing import Any

import pandas as pd


import uuid
import logging
from core.utils import write_json

def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    if df.empty:
        logging.warning("Dataframe is empty. Cannot build test set.")
        return []
        
    # Chon mot so paper dai dien (vd 2-4 papers)
    sample_size = min(4, len(df))
    sample_df = df.sample(n=sample_size, random_state=42)
    
    test_set = []
    
    for _, row in sample_df.iterrows():
        paper_id = str(row['paper_id'])
        
        # 1. Summary question
        test_set.append({
            "id": str(uuid.uuid4()),
            "question_type": "summary",
            "question": f"Tóm tắt nội dung chính của bài báo '{row['title']}'?",
            "ground_truth": str(row['summary']),
            "ground_truth_doc_ids": [paper_id]
        })
        
        # 2. Authors question
        test_set.append({
            "id": str(uuid.uuid4()),
            "question_type": "authors",
            "question": f"Ai là tác giả của bài báo '{row['title']}'?",
            "ground_truth": str(row['authors']),
            "ground_truth_doc_ids": [paper_id]
        })
        
        # 3. Date question
        test_set.append({
            "id": str(uuid.uuid4()),
            "question_type": "date",
            "question": f"Bài báo '{row['title']}' được xuất bản vào ngày nào?",
            "ground_truth": str(row['published']),
            "ground_truth_doc_ids": [paper_id]
        })
        
        # 4. Categories question
        test_set.append({
            "id": str(uuid.uuid4()),
            "question_type": "categories",
            "question": f"Bài báo '{row['title']}' thuộc chuyên mục chính nào?",
            "ground_truth": str(row['primary_category']),
            "ground_truth_doc_ids": [paper_id]
        })
        
    write_json(output_path, test_set)
    return test_set
