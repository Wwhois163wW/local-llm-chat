#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/models/nmr_models.py
# Author: ZHU, W. phD
# License: RIKEN
# Date: 2026-03-13
# Version: 1.0.0

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

@dataclass
class NMRRecord:
    """代表单条 NMR 原始记录及其预测结果的领域模型"""
    id: str
    data_path: str
    title: str
    known_metadata: Dict[str, Any] = field(default_factory=dict)
    
    # 预测结果 (由流水线填充)
    ai_sample_name: Optional[str] = None
    ai_operator: Optional[str] = None
    ai_sample_mass: Optional[str] = None
    ai_filler: Optional[str] = None
    ai_pulse_program: Optional[str] = None
    ai_solvent: Optional[str] = None
    ai_reasoning: Optional[str] = None

@dataclass
class Publication:
    """研究员历史文献背景"""
    title: str
    year: str
    authors: Optional[str] = None
    journal: Optional[str] = None

@dataclass
class ContextBundle:
    """包装全链路“灵魂”上下文的集合"""
    persona: str = ""                         # 合成的研究员画像
    kb_fragments: List[str] = field(default_factory=list) # 匹配的知识库事实块
    references: List[Publication] = field(default_factory=list) # 文献证据链

@dataclass
class DataChunk:
    """同文件夹下的记录分块，共享上下文环境"""
    directory_path: str
    records: List[NMRRecord] = field(default_factory=list)
    context: Optional[ContextBundle] = None
    
    def get_record_by_id(self, record_id: str) -> Optional[NMRRecord]:
        for r in self.records:
            if r.id == record_id:
                return r
        return None
