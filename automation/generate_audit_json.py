import sqlite3
import os
import json
import sys
from openai import OpenAI

sys.path.append(os.path.join(os.getcwd(), 'local-llm-chat'))
from core.processor import LLMProcessor, Get_Batch_NMR_Prompt

DB_PATH = r'C:\codeSpace\nmr_cataloger\data\catalog.db'
API_URL = 'http://192.168.0.200:1234/v1'
MODEL_NAME = 'qwen/qwen3-vl-8b'
OUTPUT_FILE = r'local-llm-chat\automation\to_be_audited.json'

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    query = "SELECT data_path, title, pulse_program, solvent, operator, project_id, acquisition_date, frequency, nucleus_1 FROM NMR_Catalog WHERE (sample_name IS NULL OR sample_name = '') LIMIT 5"
    cur.execute(query)
    rows = cur.fetchall()
    columns = ['data_path', 'title', 'pulse_program', 'solvent', 'operator', 'project_id', 'acquisition_date', 'frequency', 'nucleus_1']
    batch_data = [dict(zip(columns, r)) for r in rows]

    client = OpenAI(base_url=API_URL, api_key='lm-studio')
    processor = LLMProcessor(client=client, model=MODEL_NAME)
    
    # Prep records for AI
    records_for_ai = [{'id': b['data_path'], 'data_path': b['data_path'], 'title': b['title'], 'known_metadata': b} for b in batch_data]
    messages = Get_Batch_NMR_Prompt(records_for_ai)
    ai_results = processor.Extract_JSON_by_Prompt(messages)

    proposed_gold = []
    for db_row in batch_data:
        ai_res = next((r for r in ai_results if str(r.get('id')) == db_row['data_path']), {})
        unified = {
            "case_id": f"REAL_AUDIT_{os.path.basename(os.path.dirname(db_row['data_path']))}",
            "truth": {
                "data_path": db_row['data_path'],
                "title": db_row['title'],
                "operator_name": ai_res.get('operator_name', db_row['operator']),
                "sample_name": ai_res.get('sample_base_name', 'MISSING'),
                "sample_mass": ai_res.get('sample_mass', None),
                "filler": ai_res.get('filler', None),
                "project_id": ai_res.get('project_id', db_row['project_id']),
                "pulse_program": ai_res.get('pulse_program', db_row['pulse_program']),
                "solvent": ai_res.get('solvent', db_row['solvent']),
                "acquisition_date": db_row['acquisition_date'],
                "frequency": db_row['frequency'],
                "nucleus_1": db_row['nucleus_1']
            },
            "ai_reasoning": ai_res.get('reasoning', '')
        }
        proposed_gold.append(unified)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(proposed_gold, f, indent=4, ensure_ascii=False)
    
    print(f"Generated {len(proposed_gold)} audit items in {OUTPUT_FILE}")
    conn.close()

if __name__ == "__main__":
    main()
