#!/usr/bin/env python3
# -*- coding: utf-8 -*- 
# local-llm-chat/core/processor.py
# Author: ZHU, W. phD
# License: RIKEN
# Date: 2026-03-11
# Version: 1.2.0

import json
import logging
import time
import os
import re
from typing import Any, Optional, Dict, List
from openai import OpenAI
from jinja2 import Environment, FileSystemLoader

class LabKnowledgeMatcher:
    def __init__(self, index_path: str):
        self.publications = []
        if os.path.exists(index_path):
            with open(index_path, 'r', encoding='utf-8') as f:
                self.publications = json.load(f)
        self.operator_map = {
            "NXY": "Ni, X", "SHIMA": "Shima, H", "OKADA": "Okada, M",
            "ZHU": "Zhu, W", "MORIMOTO": "Morimoto, T", "MIYAMOTO": "Miyamoto, H", "INABU": "Inabu, Y"
        }

    def Get_Relevant_Pubs(self, year: str, operator: str, raw_title: str = "", window: int = 3) -> List[Dict]:
        if not self.publications: return []
        try:
            start_yr = int(year)
            end_yr = start_yr + window
        except: return []
        target_author = self.operator_map.get(operator.upper(), operator).lower()        
        results = [pub for pub in self.publications if start_yr <= int(pub.get('year', 0)) <= end_yr and target_author in pub.get('authors', '').lower()]
        if not results and raw_title:
            keywords = [w.lower() for w in re.findall(r'[A-Za-z]{3,}', raw_title)]
            blacklist = {'mgml', 'pdata', 'zgpr', 'zg30', 'cdcl', 'dmso'}
            clean_keywords = [k for k in keywords if k not in blacklist]
            for pub in self.publications:
                if start_yr <= int(pub.get('year', 0)) <= end_yr:
                    if any(k in pub['title'].lower() for k in clean_keywords):
                        results.append(pub)
        return results[:10]

class LLMProcessor:
    def __init__(self, client: OpenAI, model: str = "qwen/qwen3-vl-8b"):
        self.client = client
        self.model = model
        self.logger = logging.getLogger(__name__)

    def Extract_JSON_by_Prompt(self, messages: List[Dict[str, str]], temperature: float = 0.0) -> Optional[Dict[str, Any]]:
        try:
            response = self.client.chat.completions.create(model=self.model, messages=messages, temperature=temperature)
            content = response.choices[0].message.content
            if '```json' in content: content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content: content = content.split('```')[1].split('```')[0].strip()
            return json.loads(content)
        except Exception as e:
            self.logger.error(f"LLM Extraction failed: {e}")
            return None

    def Summarize_Researcher_Persona(self, operator: str, year: str, pubs: List[Dict]) -> str:
        if not pubs: return ""
        titles = [p['title'] for p in pubs]
        prompt = f"Synthesize a scientific persona for researcher '{operator}' around {year} based on these papers:\n{chr(10).join(['- ' + t for t in titles[:8]])}\nOutput one dense sentence."
        try:
            resp = self.client.chat.completions.create(model=self.model, messages=[{"role": "user", "content": prompt}], temperature=0.3, max_tokens=80)
            return resp.choices[0].message.content.strip()
        except: return f"Focus on {titles[0]}."

    def Handshake_and_Wait(self, wait_seconds: int = 60) -> bool:
        try:
            _ = self.client.models.list()
            return True
        except: return False

STATIC_N_SHOT_EXAMPLES = [
    {
        "input_string": "20240716_cmj-177-192-2/58.4mg_almina FSLG-PSD-HETCOR",
        "data_path": "\\\\10.64.180.130\\emar-doc\\Work\\Zhu\\database\\02+ssNMR\\data\\nmr\\NXY\\457\\pdata",
        "known_metadata": {"operator": None, "solvent": "Plasma"},
        "expected_output": {
            "id": "CASE_SAMPLE_001",
            "operator_name": "NXY",
            "sample_base_name": "cmj-177-192-2",
            "sample_mass": "58.4mg",
            "filler": "Alumina",
            "pulse_program": "ik_lghetfq_psd",
            "solvent": "Plasma",
            "project_id": None,
            "reasoning": "Spatial Proximity Rule: 'NXY' is closer to experiment folder than 'Zhu'."
        }
    }
]

def Get_NMR_Extraction_Prompt(input_string: str, data_path: str = "", known_metadata: dict = None, target_fields: list = None, lab_context: str = "", references: List[Dict] = None) -> List[Dict[str, str]]:
    template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")
    env = Environment(loader=FileSystemLoader(template_dir))
    try:
        from prompts import nmr_ner; template = env.get_template("nmr_ner/" + nmr_ner.get_active_template_name())
        prompt_text = template.render(input_string=input_string, data_path=data_path, known_metadata=known_metadata, environmental_context=lab_context, references=references, examples=STATIC_N_SHOT_EXAMPLES)
        return [{"role": "system", "content": "You are a professional NMR data scientist. Output JSON only."}, {"role": "user", "content": prompt_text}]
    except: return [{"role": "user", "content": f"Extract: {input_string}"}]

def Get_Batch_NMR_Prompt(records: List[Dict], 
                       knowledge_db_path: str = r"core\knowledge\nmr_kb.json",
                       external_context: str = "") -> List[Dict[str, str]]:
    template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")
    env = Environment(loader=FileSystemLoader(template_dir))
    knowledge_fragments = []
    if os.path.exists(knowledge_db_path):
        with open(knowledge_db_path, 'r', encoding='utf-8-sig') as f:
            kb = json.load(f)
            batch_text = " ".join([r.get('title', '') for r in records]).lower()
            for key, entry in kb.items():
                if any(k in batch_text for k in entry['keywords']): 
                    knowledge_fragments.append({"key": key, "fact": entry['fact']})
    
    # 注入外部灵魂上下文 (Persona 等)
    if external_context:
        knowledge_fragments.append({"key": "Domain_Context", "fact": external_context})
    
    cleaned_records = []
    for r in records:
        cleaned = r.copy()
        if "known_metadata" in cleaned:
            meta = cleaned["known_metadata"].copy()
            op = str(meta.get("operator", "")).lower()
            if "common" in op or not op or op == "none": meta["operator"] = None
            cleaned["known_metadata"] = meta
        cleaned_records.append(cleaned)

    try:
        from prompts import nmr_ner
        template = env.get_template("nmr_ner/" + nmr_ner.get_active_template_name())
        prompt_text = template.render(batch_data=cleaned_records, knowledge_fragments=knowledge_fragments, examples=STATIC_N_SHOT_EXAMPLES)
        return [{"role": "system", "content": "You are a senior NMR data scientist. Output JSON array."}, {"role": "user", "content": prompt_text}]
    except Exception as e: return [{"role": "user", "content": f"Extract batch: {len(records)}"}]
