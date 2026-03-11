# local-llm-chat/automation/production_pilot.py
import os
import sys
import sqlite3
import json
from collections import Counter
from openai import OpenAI

sys.path.append(os.path.join(os.getcwd(), 'local-llm-chat'))
from core.processor import LLMProcessor, Get_Batch_NMR_Prompt
from automation.batch_executor import RobustBatchExecutor

DB_PATH = r'C:\codeSpace\nmr_cataloger\data\catalog.db'
API_URL = 'http://192.168.0.200:1234/v1'
MODEL_NAME = 'qwen/qwen3-vl-8b'

def find_target_directory(conn):
    cur = conn.cursor()
    # Find directories where sample_name is empty
    cur.execute("SELECT data_path FROM NMR_Catalog WHERE sample_name IS NULL OR sample_name = '' LIMIT 200")
    paths = [os.path.dirname(r[0]) for r in cur.fetchall()]
    dir_counts = Counter(paths)
    for d, count in dir_counts.most_common():
        if 5 <= count <= 15: # Good size for a contrastive batch
            return d
    return None

def run_pilot():
    if not os.path.exists(DB_PATH):
        print("Database not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    target_dir = find_target_directory(conn)
    
    if not target_dir:
        print("No suitable messy directory found.")
        conn.close()
        return

    print(f"\n[PRODUCTION PILOT] Target Directory: {target_dir}")
    
    cur = conn.cursor()
    cur.execute("SELECT id, data_path, title, pulse_program, solvent, operator FROM NMR_Catalog WHERE data_path LIKE ? AND (sample_name IS NULL OR sample_name = '')", (target_dir + '%',))
    rows = cur.fetchall()
    
    batch_data = []
    for r in rows:
        batch_data.append({
            "id": r[0],
            "data_path": r[1],
            "title": r[2],
            "known_metadata": {"pulse_program": r[3], "solvent": r[4], "operator": r[5]}
        })

    client = OpenAI(base_url=API_URL, api_key="lm-studio")
    processor = LLMProcessor(client=client, model=MODEL_NAME)
    executor = RobustBatchExecutor(processor=processor)
    
    print(f"Running v3 Batch Inference on {len(batch_data)} records...")
    results = executor.Recursive_Fallback_Extraction(batch_data)
    
    print("\n" + "="*80)
    print(f"{'ID':<6} | {'RAW TITLE':<40} | {'AI SAMPLE NAME':<30}")
    print("-"*80)
    
    for res in results:
        rid = res.get('id')
        # Find matching raw title
        raw = next((b['title'] for b in batch_data if str(b['id']) == str(rid)), "Unknown")
        sample = res.get('sample_base_name', 'N/A')
        print(f"{rid:<6} | {raw[:40]:<40} | {sample:<30}")
        if res.get('reasoning'):
            print(f"  [REASONING]: {res['reasoning']}")
        print("-"*80)

    conn.close()

if __name__ == "__main__":
    run_pilot()
