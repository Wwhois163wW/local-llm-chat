import json
import os

AUDIT_FILE = r'local-llm-chat\automation\to_be_audited.json'
BENCHMARK_FILE = r'local-llm-chat\tests\benchmarks\benchmark_dataset.json'

def merge():
    if not os.path.exists(AUDIT_FILE):
        print("Audit file missing.")
        return

    with open(AUDIT_FILE, 'r', encoding='utf-8') as f:
        audited = json.load(f)

    dataset = []
    if os.path.exists(BENCHMARK_FILE):
        with open(BENCHMARK_FILE, 'r', encoding='utf-8') as f:
            dataset = json.load(f)

    for item in audited:
        truth = item['truth']
        # Reconstruct original input state
        masked = truth.copy()
        masked['sample_name'] = None
        masked['sample_mass'] = None
        masked['filler'] = None
        masked['operator_name'] = 'common'
        
        # New standardized entry
        new_case = {
            "case_id": f"GOLD_{item['case_id']}",
            "difficulty": "Real_Production",
            "truth": truth,
            "masked": masked,
            "expert_reasoning": item.get('ai_reasoning')
        }
        dataset.append(new_case)

    with open(BENCHMARK_FILE, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, indent=4, ensure_ascii=False)
    
    print(f"Merge successful. Dataset now has {len(dataset)} cases.")

if __name__ == "__main__":
    merge()
