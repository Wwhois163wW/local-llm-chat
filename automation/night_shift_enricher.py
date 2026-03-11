# local-llm-chat/automation/night_shift_enricher.py
import sqlite3
import os
import sys
import logging
from datetime import datetime
from openai import OpenAI

sys.path.append(os.path.join(os.getcwd(), 'local-llm-chat'))
from core.processor import LLMProcessor, Get_Batch_NMR_Prompt
from automation.batch_executor import RobustBatchExecutor

from infra.config_loader import load_nmr_config
nmr_cfg = load_nmr_config()
DB_PATH = nmr_cfg['db_path']
API_URL = nmr_cfg['api_url']
MODEL_NAME = nmr_cfg['model_name']

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')

def run_night_shift(limit=500):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # 1. Find targets (sample_name is empty AND ai_sample_name is empty)
    query = """
        SELECT data_path, title, pulse_program, solvent, operator, project_id 
        FROM NMR_Catalog 
        WHERE (sample_name IS NULL OR sample_name = '') 
        AND (ai_sample_name IS NULL OR ai_sample_name = '')
        LIMIT ?
    """
    cur.execute(query, (limit,))
    rows = cur.fetchall()
    
    if not rows:
        logging.info("No records to process. Good night!")
        conn.close()
        return

    batch_data = []
    columns = ['data_path', 'title', 'pulse_program', 'solvent', 'operator', 'project_id']
    for r in rows:
        record = dict(zip(columns, r))
        batch_data.append({
            "id": record['data_path'],
            "data_path": record['data_path'],
            "title": record['title'],
            "known_metadata": record
        })

    # 2. Setup AI Engine
    client = OpenAI(base_url=API_URL, api_key='lm-studio')
    processor = LLMProcessor(client=client, model=MODEL_NAME)
    executor = RobustBatchExecutor(processor=processor, max_batch_size=12)
    
    # 3. Process by chunks
    chunks = executor.Group_By_Directory(batch_data)
    logging.info(f"Starting Night Shift: {len(batch_data)} records in {len(chunks)} folder chunks.")
    
    success_count = 0
    for chunk in chunks:
        results = executor.Recursive_Fallback_Extraction(chunk)
        
        # 4. Database Write-back
        for res in results:
            try:
                cur.execute("""
                    UPDATE NMR_Catalog 
                    SET ai_sample_name = ?, 
                        ai_operator = ?, 
                        ai_sample_mass = ?, 
                        ai_filler = ?, 
                        ai_reasoning = ? 
                    WHERE data_path = ?
                """, (
                    res.get('sample_base_name'),
                    res.get('operator_name'),
                    res.get('sample_mass'),
                    res.get('filler'),
                    res.get('reasoning'),
                    res.get('id')
                ))
                success_count += 1
            except Exception as e:
                logging.error(f"Failed to update record {res.get('id')}: {e}")
        
        conn.commit() # Commit after each chunk for safety
        logging.info(f"Processed chunk. Total updated: {success_count}")

    logging.info(f"Night Shift Complete. {success_count} records enriched.")
    conn.close()

if __name__ == "__main__":
    run_night_shift(limit=100) # Start with 100 for safety, increase for real night run

