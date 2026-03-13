#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/eval/compiler.py
# Author: ZHU, W. phD
# Version: 1.0.0

import random

from core.models.nmr_models import NMRRecord

class DatasetCompiler:
    """数据集编译器：负责将原始 Record 转换为具备“难度等级”的测试用例。"""
    
    @staticmethod
    def Compile_Case(record: NMRRecord, mask_level: int = 1) -> dict:
        """
        根据遮蔽等级生成测试用例。
        mask_level 1: 仅保留 title
        mask_level 2: 保持 title, 掩码 operator
        mask_level 3: 掩码所有 known_metadata
        """
        masked_meta = record.known_metadata.copy()
        
        if mask_level >= 1:
            # Level 1 至少隐藏关键推理线索
            if "operator" in masked_meta: masked_meta["operator"] = "Unknown"
            
        if mask_level >= 2:
            if "solvent" in masked_meta: masked_meta["solvent"] = None
            
        if mask_level >= 3:
            masked_meta = {} # 裸跑，全靠推理
            
        # 难度等级计算 (基于遮蔽比例)
        difficulty_score = mask_level * 0.3 + (random.random() * 0.1) 
        
        return {
            "case_id": record.id,
            "masked_input": {
                "title": record.title,
                "data_path": record.data_path,
                "masked": masked_meta
            },
            "truth": {
                "sample_base_name": record.ai_sample_name,
                "operator_name": record.ai_operator,
                "solvent": record.ai_solvent
            },
            "meta": {
                "difficulty": round(difficulty_score, 2),
                "mask_level": mask_level,
                "type": "evolved"
            }
        }

    def Build_Batch_Test_Set(self, records: list[NMRRecord], batch_size: int = 5) -> list[dict]:
        """将记录组装为带有难度权重的测试集。"""
        # 计算异质性权重：根据批次大小反向定标难度。
        # 认为小批量（单兵作战）比大批量（规律互证）更难。
        hetero_weight = 2.0 / (len(records) if records else 1)
        
        cases = []
        for r in records:
            level = random.choice([1, 2, 3])
            case = self.Compile_Case(r, mask_level=level)
            # 最终难度 = 基础遮蔽难度 + 批次异质性权重
            case["meta"]["difficulty"] = round(case["meta"]["difficulty"] + hetero_weight, 2)
            cases.append(case)
        return cases
