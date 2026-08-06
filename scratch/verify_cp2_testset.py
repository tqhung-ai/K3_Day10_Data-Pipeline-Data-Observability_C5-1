import sys
import json
from pathlib import Path

project_root = Path(r"d:\AI thực chiến\K3_Day10_Data-Pipeline-Data-Observability_C5-1")
sys.path.insert(0, str(project_root / "src"))

from core.config import load_settings
from core.utils import read_json

def main():
    settings = load_settings(project_root)
    test_set_path = settings.paths.eval_testset
    
    if not test_set_path.exists():
        print(f"❌ Chưa tìm thấy file test set tại: {test_set_path}")
        print("Vui lòng chạy script scratch/run_cp1.py trước để sinh file này.")
        return
        
    print(f"✅ Đã tìm thấy test set cố định tại: {test_set_path}")
    test_set = read_json(test_set_path)
    
    print(f"\nTổng số câu hỏi trong test set: {len(test_set)}")
    
    print("\n--- ĐỌC THỬ 2 HÀNG ĐẦU TIÊN (Kiểm chứng theo yêu cầu CP2) ---")
    for i, row in enumerate(test_set[:2]):
        print(f"\n[Câu hỏi {i+1}] - Type: {row['question_type']}")
        print(f"Q: {row['question']}")
        print(f"A (Ground Truth): {row['ground_truth']}")
        print(f"Doc IDs trỏ đến: {row['ground_truth_doc_ids']}")
        
    print("\n✅ Test set đã hợp lệ! Sẵn sàng cho CP3 (Evaluate).")

if __name__ == "__main__":
    main()
