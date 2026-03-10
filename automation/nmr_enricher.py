#!/usr/bin/env python3
# -*- coding: utf-8 -*- 
# local-llm-chat/automation/nmr_enricher.py
# Author: ZHU, W. phD
# License: RIKEN
# Date: 2026-03-10
# Version: 1.4.0

import sqlite3
import logging
import time
import os
import sys
import json

# Ensure core is importable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.processor import LLMProcessor, Get_NMR_Extraction_Prompt, LabKnowledgeMatcher

# @Antigravity, 20260310, [FEAT]: Provenance-enabled enrichment loop with Evidence Chain and Keyword Fallback

# Configuration
DB_PATH = r'C:\codeSpace\nmr_cataloger\data\catalog.db'
LAB_INDEX = r'desk\literature\publications_index.json'
API_URL = 'http://192.168.0.200:1234/v1'
MODEL_NAME = 'qwen/qwen3-vl-8b'
OUTPUT_PREVIEW = 'enrichment_preview.json'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NMREnricher:
    def __init__(self, db_path: str, api_url: str, model: str):
        from openai import OpenAI
        self.db_path = db_path
        client = OpenAI(base_url=api_url, api_key="lm-studio")
        self.processor = LLMProcessor(client=client, model=model)
        self.matcher = LabKnowledgeMatcher(LAB_INDEX)
        self.batch_cache = {} # Cache for (operator, year) -> (Persona, Pubs)

    def Get_Batch_Evidence(self, operator: str, year: str, raw_title: str) -> tuple:
        """
        Retrieves both synthesized persona and raw publication evidence.
        """
        key = (operator.upper(), str(year))
        if key not in self.batch_cache:
            logger.info(f"Searching Evidence for {operator} in {year}...")
            # Use Enhanced Matcher with title fallback
            pubs = self.matcher.Get_Relevant_Pubs(year, operator, raw_title=raw_title)
            persona = self.processor.Summarize_Researcher_Persona(operator, year, pubs)
            self.batch_cache[key] = (persona, pubs)
            
        return self.batch_cache[key]

    def Process_Pilot(self, batch_size: int = 5):
        if not os.path.exists(self.db_path):
            logger.error(f"Database not found: {self.db_path}")
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            
            cur.execute(
                "SELECT data_path, title, pulse_program, project_id, solvent, operator, acquisition_date "
                "FROM NMR_Catalog WHERE (sample_name IS NULL OR sample_name = '') "
                "AND (title IS NOT NULL AND title != '') LIMIT ?", (batch_size,)
            )
            rows = cur.fetchall()

            if not rows:
                logger.info("No records found.")
                return

            preview_data = []
            for i, (path, title, p_prog, p_id, solvent, operator, acq_date) in enumerate(rows, 1):
                year = acq_date[:4] if acq_date and len(acq_date) >= 4 else "2024"
                
                # Get both Persona and Raw Evidence
                persona, pubs = self.Get_Batch_Evidence(operator, year, title)
                
                known_meta = {"solvent": solvent, "pulse_program": p_prog, "project_id": p_id}
                
                # Construct Prompt with Evidence Chain and Path
                messages = Get_NMR_Extraction_Prompt(
                    input_string=title, 
                    data_path=path, # Pass the full path!
                    known_metadata=known_meta, 
                    lab_context=persona,
                    references=pubs
                )
                
                result = self.processor.Extract_JSON_by_Prompt(messages)
                
                preview_data.append({
                    "case_no": i,
                    "db_path": path,
                    "original_operator": operator, # Track the common status
                    "input_title": title,
                    "output_parsed": result
                })
                logger.info(f"[{i}/{len(rows)}] Inferred with {len(pubs)} evidence links.")

            with open(OUTPUT_PREVIEW, 'w', encoding='utf-8') as f:
                json.dump(preview_data, f, indent=4, ensure_ascii=False)
            
            conn.close()
            logger.info(f"Pilot Finished. Results in {OUTPUT_PREVIEW}")
            
        except Exception as e:
            logger.error(f"Pilot Error: {e}")

if __name__ == '__main__':
    enricher = NMREnricher(db_path=DB_PATH, api_url=API_URL, model=MODEL_NAME)
    if enricher.processor.Handshake_and_Wait(wait_seconds=5):
        enricher.Process_Pilot(batch_size=5)
