#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/logic/persona_service.py
# Author: ZHU, W. phD
# License: RIKEN
# Version: 1.0.0

from typing import List
from core.interfaces.agent_interfaces import IPersonaSynthesizer
from core.models.nmr_models import Publication

class PersonaSynthesizer(IPersonaSynthesizer):
    """画像师：负责将干巴巴的文献列表转化为鲜活的研究员背景描述"""
    
    def Synthesize_Persona(self, 
                           operator: str, 
                           year: str, 
                           refs: List[Publication]
                          ) -> str:
        if not refs:
            return (
                f"The researcher '{operator}' is conducting NMR experiments in {year}. "
                "No specific historical specialty found in current index."
            )
            
        topics = [r.title for r in refs]
        summary = (
            f"Researcher '{operator}' has a strong historical focus in '{year}' on topics "
            f"including: {', '.join(topics[:3])}. "
            "They are likely an expert in the chemical systems related to these publications."
        )
        return summary
