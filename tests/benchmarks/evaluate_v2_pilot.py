# local-llm-chat/tests/benchmarks/evaluate_v2_pilot.py
import json
import os
import sys
import time
from openai import OpenAI

# Ensure core is importable
current_dir = os.getcwd()
sys.path.append(os.path.join(current_dir, 'local-llm-chat'))

try:
    from core.processor import LLMProcessor, Get_NMR_Extraction_Prompt
except ImportError as e:
    print(f"Import Error: {e}. Check if local-llm-chat directory structure is correct.")
    sys.exit(1)

# Config
API_URL = 'http://192.168.0.200:1234/v1'
MODEL_NAME = 'qwen/qwen3-vl-8b'
DATASET_PATH = r'local-llm-chat\tests\benchmarks\benchmark_dataset.json'

def run_pilot(limit=10):
    if not os.path.exists(DATASET_PATH):
        print(f"Dataset not found at {DATASET_PATH}")
        return
        
    with open(DATASET_PATH, 'r', encoding='utf-8') as f:
        dataset = json.load(f)

    # Filter for Easy cases (M1_*)
    easy_cases = [c for c in dataset if c.get('difficulty') == 'Easy'][:limit]
    
    if not easy_cases:
        print("No Easy cases found in dataset.")
        return

    client = OpenAI(base_url=API_URL, api_key="lm-studio")
    processor = LLMProcessor(client=client, model=MODEL_NAME)
    
    print(f"\n{'='*20} PERFORMANCE BENCHMARK (Difficulty: Easy) {'='*20}")
    print(f"Model: {MODEL_NAME} | Sample Size: {len(easy_cases)}\n")
    
    total_start = time.time()
    results_log = []

    for i, case in enumerate(easy_cases, 1):
        truth = case['truth']
        masked = case['masked']
        masked_field = case.get('masked_field', 'unknown')
        
        print(f"CASE #{i:02d} | ID: {case['case_id']} | MASKED: [{masked_field}]")
        
        start_time = time.time()
        
        # In Easy mode, we pass the masked metadata (only 1 field is None)
        messages = Get_NMR_Extraction_Prompt(
            input_string=truth['title'],
            data_path=truth['data_path'],
            known_metadata=masked 
        )
        
        result = processor.Extract_JSON_by_Prompt(messages)
        latency = time.time() - start_time
        
        # Validation
        t_val = str(truth.get(masked_field)).lower() if truth.get(masked_field) else "none"
        p_val = str(result.get(masked_field)).lower() if result and result.get(masked_field) else "none"
        match = "✅" if t_val == p_val else "❌"
        
        print(f"TARGET: {masked_field:15} | Truth: {t_val:12} | AI: {p_val:12} | {match}")
        print(f"LATENCY: {latency:.2f}s")
        
        if result and 'reasoning' in result:
            print(f"REASONING: {result['reasoning']}")
        
        print("-" * 60)
        results_log.append({"match": t_val == p_val, "latency": latency})

    total_duration = time.time() - total_start
    avg_latency = total_duration / len(easy_cases)
    success_rate = (sum(1 for r in results_log if r['match']) / len(easy_cases)) * 100
    
    print(f"\n{'='*20} SUMMARY {'='*20}")
    print(f"Total Time: {total_duration:.2f}s")
    print(f"Avg Latency: {avg_latency:.2f}s/case")
    print(f"Success Rate: {success_rate:.1f}%")

if __name__ == "__main__":
    run_pilot()
