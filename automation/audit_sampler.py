# local-llm-chat/automation/audit_sampler.py
import sqlite3
import os
import json
import sys
from openai import OpenAI

sys.path.append(os.path.join(os.getcwd(), 'local-llm-chat'))
from core.processor import LLMProcessor, Get_Batch_NMR_Prompt
from automation.batch_executor import RobustBatchExecutor

DB_PATH = r'C:\codeSpace\nmr_cataloger\data\catalog.db'
API_URL = 'http://192.168.0.200:1234/v1'
MODEL_NAME = 'qwen/qwen3-vl-8b'

def run_full_row_audit():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Fetch 5 records with ALL key columns to test Full Row Reconstruction
    query = """
        SELECT data_path, title, pulse_program, solvent, operator, project_id, acquisition_date, frequency, nucleus_1 
        FROM NMR_Catalog 
        WHERE (sample_name IS NULL OR sample_name = '') 
        LIMIT 5
    """
    cur.execute(query)
    rows = cur.fetchall()
    
    batch_data = []
    columns = ['data_path', 'title', 'pulse_program', 'solvent', 'operator', 'project_id', 'acquisition_date', 'frequency', 'nucleus_1']
    for r in rows:
        record = dict(zip(columns, r))
        batch_data.append({
            "id": record['data_path'],
            "data_path": record['data_path'],
            "title": record['title'],
            "known_metadata": record # Pass EVERYTHING to AI
        })

    client = OpenAI(base_url=API_URL, api_key="lm-studio")
    processor = LLMProcessor(client=client, model=MODEL_NAME)
    executor = RobustBatchExecutor(processor=processor)
    
    print(f"\n[FULL ROW AUDIT #1] Processing {len(batch_data)} real records with Complete Metadata...")
    results = executor.Recursive_Fallback_Extraction(batch_data)
    
    for res in results:
        rid = res.get('id')
        print(f"\n{'='*80}")
        print(f"PATH: {rid}")
        print("-" * 80)
        
        # Display all keys returned by AI
        all_keys = sorted(res.keys())
        for k in all_keys:
            if k != 'id' and k != 'reasoning':
                val = res.get(k)
                print(f"  {k:20}: {val}")
        
        print(f"\n  [REASONING]: {res.get('reasoning')}")
        print("="*80)
    
    conn.close()

if __name__ == "__main__":
    run_full_row_audit()
