# local-llm-chat/automation/batch_executor.py
import os
import sys
import json
import logging
from collections import defaultdict
from typing import List, Dict, Any

sys.path.append(os.path.join(os.getcwd(), 'local-llm-chat'))
from core.processor import LLMProcessor, Get_Batch_NMR_Prompt

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class RobustBatchExecutor:
    def __init__(self, processor: LLMProcessor, max_batch_size: int = 15):
        self.processor = processor
        self.max_batch_size = max_batch_size

    def Group_By_Directory(self, raw_data: List[Dict]) -> List[List[Dict]]:
        """Groups flat database rows into chunks by their parent directory."""
        groups = defaultdict(list)
        for row in raw_data:
            dir_name = os.path.dirname(row['data_path'])
            groups[dir_name].append(row)
        
        chunks = []
        for d, items in groups.items():
            # Chunking within the same directory if it exceeds max size
            for i in range(0, len(items), self.max_batch_size):
                chunks.append(items[i:i + self.max_batch_size])
        return chunks

    def Recursive_Fallback_Extraction(self, batch_data: List[Dict], attempt: int = 1) -> List[Dict]:
        """
        Attempts to extract JSON. If it fails (parse error or missing IDs), 
        it SPLITS the batch in half and retries recursively.
        """
        if not batch_data: return []
        
        logging.info(f"-> Processing Batch of {len(batch_data)} items (Attempt {attempt})...")
        messages = Get_Batch_NMR_Prompt(records=batch_data)
        
        result_array = self.processor.Extract_JSON_by_Prompt(messages)
        
        # Validation: Did we get a list? Did we get all IDs back?
        is_valid = False
        if isinstance(result_array, list):
            input_ids = {str(item['id']) for item in batch_data}
            output_ids = {str(res.get('id')) for res in result_array if res.get('id')}
            
            if input_ids == output_ids:
                is_valid = True
            else:
                logging.warning(f"ID Mismatch! In: {len(input_ids)}, Out: {len(output_ids)}. Fallback triggered.")
        else:
            logging.warning("JSON Parse Error or Not an Array. Fallback triggered.")

        if is_valid:
            return result_array
            
        # --- THE FALLBACK MECHANISM ---
        if len(batch_data) == 1:
            logging.error(f"Failed on single item {batch_data[0]['id']}. Giving up on this row.")
            return [] # Bottom of recursion, data is unprocessable
            
        logging.info(f"Splitting batch of {len(batch_data)} in half and retrying...")
        mid = len(batch_data) // 2
        left_half = self.Recursive_Fallback_Extraction(batch_data[:mid], attempt + 1)
        right_half = self.Recursive_Fallback_Extraction(batch_data[mid:], attempt + 1)
        
        return left_half + right_half

if __name__ == "__main__":
    from openai import OpenAI
    client = OpenAI(base_url='http://192.168.0.200:1234/v1', api_key="lm-studio")
    processor = LLMProcessor(client=client, model='qwen/qwen3-vl-8b')
    executor = RobustBatchExecutor(processor=processor)
    
    # Simulated Mock Data
    mock_data = [
        {"id": "R1", "data_path": "/data/ELS/1", "title": "els-pe_1-kpi-28mg-zhu", "known_metadata": {}},
        {"id": "R2", "data_path": "/data/ELS/2", "title": "els-pcl_3-kpi-30mg-zhu", "known_metadata": {}},
        {"id": "R3", "data_path": "/data/ELS/3", "title": "els-control-kpi-30mg-zhu", "known_metadata": {}}
    ]
    
    chunks = executor.Group_By_Directory(mock_data)
    
    final_results = []
    for chunk in chunks:
        res = executor.Recursive_Fallback_Extraction(chunk)
        final_results.extend(res)
        
    print("\n=== FINAL ALIGNED RESULTS ===")
    print(json.dumps(final_results, indent=2, ensure_ascii=False))
