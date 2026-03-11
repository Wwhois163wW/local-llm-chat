# local-llm-chat/tests/test_v3_batch.py
import json
import os
import sys
import sqlite3
from openai import OpenAI

# Ensure core and prompts are importable
sys.path.append(os.path.join(os.getcwd(), 'local-llm-chat'))
from core.processor import LLMProcessor, Get_Batch_NMR_Prompt

# Config
DB_PATH = r'C:\codeSpace\nmr_cataloger\data\catalog.db'
API_URL = 'http://192.168.0.200:1234/v1'
MODEL_NAME = 'qwen/qwen3-vl-8b'

def run_v3_batch_test():
    # 1. Fetch 5 records from the SAME DIRECTORY with 'almina' or 'mg'
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Find a directory that has multiple relevant files
    cur.execute("""
        SELECT data_path, title, pulse_program, solvent, operator, sample_name 
        FROM NMR_Catalog 
        WHERE title LIKE '%almina%' OR title LIKE '%mg%'
        LIMIT 5
    """)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print("No matching records found in DB for 'almina/mg'. Using simulated batch.")
        records = [
            {"data_path": "/data/zhu/2026/cmj-177/1", "title": "cmj-177-192-2/58.4mg_almina zg30", "known_metadata": {"solvent": "Plasma"}},
            {"data_path": "/data/zhu/2026/cmj-177/2", "title": "cmj-177-192-2/58.4mg_almina hsqc", "known_metadata": {"solvent": "Plasma"}},
            {"data_path": "/data/zhu/2026/cmj-177/3", "title": "cmj-177-192-2/58.4mg_almina cpd", "known_metadata": {"solvent": "Plasma"}},
            {"data_path": "/data/zhu/2026/cmj-177/4", "title": "cmj-177-192-3/42.1mg_almina zg30", "known_metadata": {"solvent": "Plasma"}},
            {"data_path": "/data/zhu/2026/cmj-177/5", "title": "cmj-177-192-3/42.1mg_almina noesy", "known_metadata": {"solvent": "Plasma"}}
        ]
    else:
        columns = ['data_path', 'title', 'pulse_program', 'solvent', 'operator', 'sample_name']
        records = []
        for r in rows:
            records.append({
                "data_path": r[0],
                "title": r[1],
                "known_metadata": {"pulse_program": r[2], "solvent": r[3], "operator": r[4]}
            })

    # 2. Setup LLM
    client = OpenAI(base_url=API_URL, api_key="lm-studio")
    processor = LLMProcessor(client=client, model=MODEL_NAME)
    
    # 3. Generate v3 Batch Prompt (with KB Injection)
    print(f"\n--- [v3 BATCH INFERENCE] INJECTING NMR KNOWLEDGE FRAGMENTS ---\n")
    messages = Get_Batch_NMR_Prompt(records)
    
    # Debug: See the prompt content
    # print(messages[1]['content']) 
    
    # 4. Infer
    print(f"Processing Batch of {len(records)} records...")
    result_array = processor.Extract_JSON_by_Prompt(messages)
    
    # 5. Show Results
    if result_array:
        for i, res in enumerate(result_array, 1):
            print(f"RECORD #{i} | Raw: '{records[i-1]['title']}'")
            print(f"  > OPERATOR   : {res.get('operator_name')}")
            print(f"  > SAMPLE_BASE: {res.get('sample_base_name')}")
            print(f"  > MASS       : {res.get('sample_mass')}")
            print(f"  > FILLER     : {res.get('filler')}")
            print(f"  > PULSE      : {res.get('pulse_program')}")
            print(f"  > REASONING  : {res.get('reasoning')}")
            print("-" * 50)
    else:
        print("Inference failed or returned invalid JSON.")

if __name__ == "__main__":
    run_v3_batch_test()
