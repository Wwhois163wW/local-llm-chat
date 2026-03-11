# local-llm-chat/tests/benchmarks/evaluate_v3_full.py
import json
import os
import sys
import time
from datetime import datetime
from openai import OpenAI

# Ensure core is importable
sys.path.append(os.path.join(os.getcwd(), 'local-llm-chat'))
from core.processor import LLMProcessor
from automation.batch_executor import RobustBatchExecutor

# Config
from infra.config_loader import load_nmr_config
nmr_cfg = load_nmr_config()
API_URL = nmr_cfg['api_url']
MODEL_NAME = nmr_cfg['model_name']
DATASET_PATH = os.path.join(os.getcwd(), 'local-llm-chat', 'tests', 'benchmarks', 'benchmark_dataset.json')

SCHEMA_MAP = {
    "sample_name": "sample_base_name",
    "operator_name": "operator_name",
    "project_id": "project_id",
    "pulse_program": "pulse_program",
    "solvent": "solvent"
}

def semantic_match(truth, prediction):
    t = str(truth).lower().strip()
    p = str(prediction).lower().strip()
    if t == 'none' or p == 'none': return "STRICT" if t == p else "MISMATCH"
    if t == p: return "STRICT"
    if t in p or p in t: return "PARTIAL"
    return "MISMATCH"

def run_full_benchmark():
    if not os.path.exists(DATASET_PATH): return
    with open(DATASET_PATH, 'r', encoding='utf-8') as f:
        dataset = json.load(f)

    client = OpenAI(base_url=API_URL, api_key="lm-studio")
    processor = LLMProcessor(client=client, model=MODEL_NAME)
    executor = RobustBatchExecutor(processor=processor, max_batch_size=12)
    
    records_to_process = []
    for case in dataset:
        records_to_process.append({
            "id": case['case_id'],
            "data_path": case['truth']['data_path'],
            "title": case['truth']['title'],
            "known_metadata": case['masked'],
            "actual_truth": case['truth']
        })

    chunks = executor.Group_By_Directory(records_to_process)
    
    print(f"\n{'='*20} v3 FULL SYSTEM BENCHMARK (Full-Field Scoring) {'='*20}")
    print(f"Total Cases: {len(dataset)} | Total Chunks: {len(chunks)}\n")
    
    all_results = []
    total_start = time.time()
    
    for i, chunk in enumerate(chunks, 1):
        print(f"Processing Chunk {i}/{len(chunks)} ({len(chunk)} items)...")
        results = executor.Recursive_Fallback_Extraction(chunk)
        truth_data = {str(item['id']): item['actual_truth'] for item in chunk}
        
        for res in results:
            rid = str(res.get('id'))
            if rid in truth_data:
                truth = truth_data[rid]
                
                # Identify ALL fields in Truth that are NOT None
                valid_fields = [f for f in SCHEMA_MAP.keys() if truth.get(f) is not None]
                
                case_score = {
                    "case_id": rid,
                    "valid_fields": valid_fields,
                    "scores": {"strict": 0, "partial": 0, "total": len(valid_fields)}
                }
                
                for f in valid_fields:
                    ai_field = SCHEMA_MAP.get(f, f)
                    m_type = semantic_match(truth.get(f), res.get(ai_field))
                    if m_type == "STRICT": case_score["scores"]["strict"] += 1
                    if m_type != "MISMATCH": case_score["scores"]["partial"] += 1
                
                all_results.append(case_score)

    total_duration = time.time() - total_start
    
    # --- PERSISTENCE & STATS ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = os.path.join(os.getcwd(), 'local-llm-chat', nmr_cfg['test_output_dir'])), "reports")
    os.makedirs(report_dir, exist_ok=True)
    
    # Global aggregates across all valid fields
    total_valid_dims = sum(r['scores']['total'] for r in all_results)
    strict_sum = sum(r['scores']['strict'] for r in all_results)
    partial_sum = sum(r['scores']['partial'] for r in all_results)
    
    summary_data = {
        "timestamp": timestamp,
        "model": MODEL_NAME,
        "total_records": len(all_results),
        "total_fields_evaluated": total_valid_dims,
        "strict_accuracy": (strict_sum/total_valid_dims)*100 if total_valid_dims else 0,
        "partial_accuracy": (partial_sum/total_valid_dims)*100 if total_valid_dims else 0,
        "avg_latency": total_duration/len(all_results) if all_results else 0
    }
    
    with open(os.path.join(report_dir, f"summary_fullfield_{timestamp}.json"), 'w', encoding='utf-8') as f:
        json.dump(summary_data, f, indent=4, ensure_ascii=False)
            
    print(f"\n{'='*20} FINAL COMPREHENSIVE SCORE {'='*20}")
    print(f"Total Fields Evaluated : {total_valid_dims}")
    print(f"STRICT Accuracy        : {summary_data['strict_accuracy']:.1f}%")
    print(f"SEMANTIC Accuracy      : {summary_data['partial_accuracy']:.1f}%")
    print(f"Avg Latency            : {summary_data['avg_latency']:.2f}s/record")

if __name__ == "__main__":
    run_full_benchmark()

