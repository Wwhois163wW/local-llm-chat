#!/usr/bin/env python3
# -*- coding: utf-8 -*- 
# local-llm-chat/core/processor.py
# Author: ZHU, W. phD
# License: RIKEN
# Date: 2026-03-10
# Version: 1.1.0

import json
import logging
import time
import os
import re
from typing import Any, Optional, Dict, List
from openai import OpenAI
from jinja2 import Environment, FileSystemLoader

# @Antigravity, 20260310, [REF]: Enhanced Matcher with Provenance Tracking and Keyword Fallback

class LabKnowledgeMatcher:
    """
    Retrieves structured publication evidence from the lab list.
    Supports Author mapping and Keyword-based fallback for "common" operators.
    """
    def __init__(self, index_path: str):
        self.publications = []
        if os.path.exists(index_path):
            with open(index_path, 'r', encoding='utf-8') as f:
                self.publications = json.load(f)
        
        self.operator_map = {
            "NXY": "Ni, X",
            "SHIMA": "Shima, H",
            "OKADA": "Okada, M",
            "ZHU": "Zhu, W",
            "MORIMOTO": "Morimoto, T",
            "MIYAMOTO": "Miyamoto, H",
            "INABU": "Inabu, Y"
        }

    def Get_Relevant_Pubs(self, year: str, operator: str, raw_title: str = "", window: int = 3) -> List[Dict]:
        """
        Retrieves a list of relevant publications as structural evidence.
        """
        if not self.publications: return []
        
        try:
            start_yr = int(year)
            end_yr = start_yr + window
        except: return []

        target_author = self.operator_map.get(operator.upper(), operator).lower()
        
        # 1. Try Author Match
        results = [
            pub for pub in self.publications 
            if start_yr <= int(pub.get('year', 0)) <= end_yr 
            and target_author in pub.get('authors', '').lower()
        ]
        
        # 2. Fallback: Keyword Match (For "common" or missing authors)
        if not results and raw_title:
            # Extract meaningful words (3+ chars, ignore dates/common params)
            keywords = [w.lower() for w in re.findall(r'[A-Za-z]{3,}', raw_title)]
            # Filter out common technical terms
            blacklist = {'mgml', 'pdata', 'zgpr', 'zg30', 'cdcl', 'dmso', 'pdata'}
            clean_keywords = [k for k in keywords if k not in blacklist]
            
            for pub in self.publications:
                if start_yr <= int(pub.get('year', 0)) <= end_yr:
                    pub_title_low = pub['title'].lower()
                    if any(k in pub_title_low for k in clean_keywords):
                        results.append(pub)
        
        return results[:10] # Return top 10 as evidence

class LLMProcessor:
    def __init__(self, client: OpenAI, model: str = "qwen/qwen3-vl-8b"):
        self.client = client
        self.model = model
        self.logger = logging.getLogger(__name__)

    def Extract_JSON_by_Prompt(self, messages: List[Dict[str, str]], temperature: float = 0.0) -> Optional[Dict[str, Any]]:
        try:
            response = self.client.chat.completions.create(model=self.model, messages=messages, temperature=temperature)
            content = response.choices[0].message.content
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            return json.loads(content)
        except Exception as e:
            self.logger.error(f"LLM Extraction failed: {e}")
            return None

    def Summarize_Researcher_Persona(self, operator: str, year: str, pubs: List[Dict]) -> str:
        """Summarizes research focus based on structural publication data."""
        if not pubs: return ""
        titles = [p['title'] for p in pubs]
        prompt = (
            f"Synthesize a scientific persona for researcher '{operator}' around {year} based on these papers:\n"
            f"{chr(10).join(['- ' + t for t in titles[:8]])}\n"
            "Output one dense sentence on their expertise and materials."
        )
        try:
            resp = self.client.chat.completions.create(model=self.model, messages=[{"role": "user", "content": prompt}], temperature=0.3, max_tokens=80)
            return resp.choices[0].message.content.strip()
        except: return f"Focus on {titles[0]}."

    def Handshake_and_Wait(self, wait_seconds: int = 60) -> bool:
        self.logger.info(f"Warming up model '{self.model}'...")
        try:
            _ = self.client.models.list()
            self.client.chat.completions.create(model=self.model, messages=[{"role": "user", "content": "ping"}], max_tokens=5)
            time.sleep(wait_seconds)
            return True
        except Exception as e:
            self.logger.error(f"Handshake failed: {e}")
            return False

# Static N-Shot Library
STATIC_N_SHOT_EXAMPLES = [
    {
        "input_string": "20240801 PBS M001 CDCl3",
        "known_metadata": {"solvent": "CDCl3"},
        "target_fields": ["sample_name", "reasoning", "related_publications"],
        "expected_output": {
            "sample_name": "PBS M001",
            "reasoning": "Detected organic solvent CDCl3; therefore PBS is interpreted as the polymer Polybutylene Succinate.",
            "related_publications": ["Simultaneous multimodal and multitask strategies for diverse biodegradable polymers..."]
        }
    }
]

def Get_NMR_Extraction_Prompt(
    input_string: str, 
    data_path: str = "", # NEW
    known_metadata: dict = None, 
    target_fields: list = None,
    examples: list = None,
    lab_context: str = "",
    references: List[Dict] = None
) -> List[Dict[str, str]]:
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")
    env = Environment(loader=FileSystemLoader(template_dir))
    try:
        template = env.get_template("nmr_dynamic_ner.j2")
        if target_fields is None: 
            target_fields = ["operator_name", "sample_name", "project_id", "pulse_program", "reasoning", "related_publications"]
        
        prompt_text = template.render(
            input_string=input_string,
            data_path=data_path, # Passed to template
            known_metadata=known_metadata,
            target_fields=target_fields,
            examples=examples if examples else STATIC_N_SHOT_EXAMPLES,
            environmental_context=lab_context,
            references=references
        )
        return [
            {"role": "system", "content": "You are a professional NMR data scientist. Output JSON only."},
            {"role": "user", "content": prompt_text}
        ]
    except Exception as e:
        import logging
        logging.error(f"Failed to load NMR extraction template: {e}")
        return [{"role": "user", "content": f"Extract metadata from title: {input_string}"}]
