#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/eval/studio.py
# Author: ZHU, W. phD

import json
import asyncio
import logging
from typing import List, Any
from core.models.nmr_models import NMRRecord
from application.pipeline import EnrichmentPipeline
from core.eval.evaluator import GeneralEvaluator

class PromptStudio:
    """提示词测控套件：支持对端到端流水线的基准测评。"""
    
    def __init__(self, pipeline: EnrichmentPipeline):
        self.pipeline = pipeline

    async def Benchmark_Pipeline(self, dataset_path: str, limit: int = 50):
        """对全链路流水线执行 Benchmark"""
        logging.info(f"Loading benchmark dataset from {dataset_path}")
        with open(dataset_path, 'r', encoding='utf-8') as f:
            dataset = json.load(f)
            
        # 1. Convert dataset to NMRRecord models
        test_records = []
        truth_map = {}
        for case in dataset[:limit]:
            rec = NMRRecord(
                id=case['case_id'],
                data_path=case['truth']['data_path'],
                title=case['truth']['title'],
                known_metadata=case['masked']
            )
            test_records.append(rec)
            truth_map[rec.id] = case['truth']
            
        # 2. Run Pipeline
        results = await self.pipeline.Execute_Full_Enrichment(test_records)
        
        # 3. Score
        all_metrics = []
        for res in results:
            truth = truth_map.get(res.id)
            if not truth: continue
            
            # Map model field names to truth field names for evaluation
            pred_dict = {
                "sample_name": res.ai_sample_name.replace("$ai:", "") if res.ai_sample_name else None,
                "operator_name": res.ai_operator.replace("$ai:", "") if res.ai_operator else None,
                "pulse_program": res.ai_pulse_program.replace("$ai:", "") if res.ai_pulse_program else None,
                "solvent": res.ai_solvent.replace("$ai:", "") if res.ai_solvent else None
            }
            truth_dict = {k: v for k, v in truth.items() if k in pred_dict}
            
            metric = GeneralEvaluator.Calculate_Field_Accuracy(truth_dict, pred_dict)
            metric['case_id'] = res.id
            all_metrics.append(metric)
            
        # 4. Summary
        total_hits = sum(m['hits'] for m in all_metrics)
        total_dims = sum(m['total'] for m in all_metrics)
        final_acc = (total_hits / total_dims) * 100 if total_dims else 0
        
        print(f"\n{'='*20} PIPELINE BENCHMARK RESULT {'='*20}")
        print(f"Total Cases: {len(all_metrics)}")
        print(f"Final Strict Accuracy: {final_acc:.2f}%")
        return final_acc
