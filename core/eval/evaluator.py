#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/eval/evaluator.py
# Author: ZHU, W. phD

from typing import Any

class GeneralEvaluator:
    """通用评分器：计算预测结果与金标准之间的字段匹配率。"""
    
    @staticmethod
    def Calculate_Field_Accuracy(truth: dict[str, Any], pred: dict[str, Any]) -> dict[str, float]:
        """计算严格匹配分。"""
        if not pred:
            return {"accuracy": 0.0, "hits": 0, "total": len(truth)}
            
        hits = 0
        valid_fields = list(truth.keys())
        for f in valid_fields:
            t_v = str(truth.get(f)).lower().strip()
            p_v = str(pred.get(f)).lower().strip()
            
            # 严格匹配逻辑
            if t_v == p_v:
                hits += 1
                
        return {
            "accuracy": (hits / len(valid_fields)) * 100 if valid_fields else 0.0,
            "hits": hits,
            "total": len(valid_fields)
        }
