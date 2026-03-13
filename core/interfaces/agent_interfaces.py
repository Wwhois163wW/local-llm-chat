#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/interfaces/agent_interfaces.py
# Author: ZHU, W. phD

from abc import ABC, abstractmethod
from typing import List
from core.models.nmr_models import DataChunk, ContextBundle, NMRRecord

class IPersonaSynthesizer(ABC):
    @abstractmethod
    def Synthesize_Persona(self, operator: str, year: str, refs: List[any]) -> str:
        """根据操作员与年份合成画像"""
        pass

class IKnowledgeMatcher(ABC):
    @abstractmethod
    def Match_Facts(self, keywords: List[str]) -> List[str]:
        """根据关键词匹配专业知识"""
        pass

class INMRExtractor(ABC):
    @abstractmethod
    async def Extract_Batch(self, chunk: DataChunk) -> List[NMRRecord]:
        """执行批量元数据提取"""
        pass
