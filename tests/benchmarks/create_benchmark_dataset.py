# local-llm-chat/tests/benchmarks/create_benchmark_dataset.py
import sqlite3
import json
import os

DB_PATH = r'C:\codeSpace\nmr_cataloger\data\catalog.db'
OUTPUT_FILE = r'local-llm-chat\tests\benchmarks\benchmark_dataset.json'

def fetch_gold_from_db(limit=50):
    """Fetches records where at least sample_name and operator are known."""
    if not os.path.exists(DB_PATH): return []
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        # Relaxed filter: only require sample_name
        query = """
            SELECT data_path, title, pulse_program, project_id, solvent, operator, sample_name 
            FROM NMR_Catalog 
            WHERE sample_name IS NOT NULL AND sample_name != ''
            LIMIT ?
        """
        cur.execute(query, (limit,))
        columns = ['data_path', 'title', 'pulse_program', 'project_id', 'solvent', 'operator_name', 'sample_name']
        data = [dict(zip(columns, r)) for r in cur.fetchall()]
        conn.close()
        return data
    except Exception as e:
        print(f"SQL Error: {e}"); return []

def create_manual_scenarios():
    """High-quality synthetic ground truth for 3 major domains."""
    return [
        {
            "data_path": "/data/zhu/2026/01/Polymers/PBS_M001/1",
            "title": "PBS M001 zg30 CDCl3",
            "pulse_program": "zg30",
            "project_id": "P456",
            "solvent": "CDCl3",
            "operator_name": "ZHU",
            "sample_name": "PBS M001",
            "scenario": "Organic/Polymer (Ambiguous PBS)"
        },
        {
            "data_path": "/data/lab/2025/Salmon/Metabolomics/Brain_Ext_A1/10",
            "title": "Salmon Brain Extract hsqc D2O",
            "pulse_program": "hsqc",
            "project_id": "PNAS2020",
            "solvent": "D2O",
            "operator_name": "NXY",
            "sample_name": "Brain_Ext_A1",
            "scenario": "Metabolites (Aqueous)"
        },
        {
            "data_path": "/data/lab/2024/Miyagi/Mixed_Materials/LDPE_PBS_70_30/1",
            "title": "Mixture LDPE/PBS 70/30",
            "pulse_program": "zg",
            "project_id": "TMC_PP",
            "solvent": "DMSO",
            "operator_name": "MIYAGI",
            "sample_name": "LDPE/PBS 70/30",
            "scenario": "Mixtures (Multi-component)"
        }
    ]

def generate_deterministic_cases(all_gold):
    maskable_fields = ['sample_name', 'operator_name', 'project_id', 'pulse_program', 'solvent']
    benchmarks = []
    for i, entry in enumerate(all_gold):
        truth_id = f"TRUTH_{i+1:03d}"
        # M1: Single-field mask (In-depth analysis)
        for field in maskable_fields:
            if entry.get(field): # Only mask if truth exists
                masked = entry.copy()
                masked[field] = None
                benchmarks.append({
                    "case_id": f"{truth_id}_M1_{field}",
                    "difficulty": "Easy",
                    "truth": entry,
                    "masked": masked,
                    "masked_field": field
                })
        # M5: All-field mask (Global synthesis)
        global_masked = entry.copy()
        for f in maskable_fields: global_masked[f] = None
        benchmarks.append({
            "case_id": f"{truth_id}_M5_ALL",
            "difficulty": "Hard",
            "truth": entry,
            "masked": global_masked,
            "masked_fields": maskable_fields
        })
    return benchmarks

if __name__ == "__main__":
    all_gold = fetch_gold_from_db(50) + create_manual_scenarios()
    print(f"Extracted {len(all_gold)} golden base records.")
    benchmark_dataset = generate_deterministic_cases(all_gold)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(benchmark_dataset, f, indent=4, ensure_ascii=False)
    print(f"Generated {len(benchmark_dataset)} stable benchmark cases.")
