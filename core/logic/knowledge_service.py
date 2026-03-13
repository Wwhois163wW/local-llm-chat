#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/logic/knowledge_service.py
# Author: ZHU, W. phD
# License: RIKEN
# Version: 1.0.0

import json
import logging
from typing import Any
from core.interfaces.agent_interfaces import IKnowledgeMatcher

class KnowledgeMatcher(IKnowledgeMatcher):
    """知识检索器：负责根据原始提取出的词条从事实库中匹配专业 NMR 背景。"""
    
    def __init__(self, kb_path: str):
        self.kb_path = kb_path
        self._kb_data: dict[str, str] = {}
        self._Load_KB()
        
    def _Load_KB(self):
        try:
            with open(self.kb_path, 'r', encoding='utf-8-sig') as f:
                self._kb_data = json.load(f)
            logging.info(f"Knowledge Base loaded with {len(self._kb_data)} facts.")
        except Exception as e:
            logging.error(f"Failed to load KB from {self.kb_path}: {e}")
            self._kb_data = {}

    def Match_Facts(self, keywords: list[str]) -> list[str]:
        """寻找与关键词最相关的知识碎片"""
        found_facts = []
        # Normalization and Matching
        for kw in keywords:
            if not kw: continue
            kw_lower = kw.lower().strip()
            
            # 简单的关键词命中逻辑 (后续可升级为 RAG/Embedding)
            for kb_key, fact in self._kb_data.items():
                if kb_key.lower() in kw_lower or kw_lower in kb_key.lower():
                    if fact not in found_facts:
                        found_facts.append(fact)
        
        return found_facts[:5] # 限制数量防止 Prompt 爆炸
