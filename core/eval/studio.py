#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/eval/studio.py
# Author: ZHU, W. phD

import json
import logging
import time
from typing import Any
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
        import time
        start_bench = time.time()
        results = await self.pipeline.Execute_Full_Enrichment(test_records)
        total_bench_time = time.time() - start_bench
        
        # 3. Score
        all_metrics = []
        total_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "latency": 0.0}
        
        # 定义字段分类
        KEY_FIELDS = ["sample_name", "pulse_program", "solvent"]
        
        for res in results:
            truth = truth_map.get(res.id)
            if not truth: continue
            
            # 提取存放在 known_metadata 中的指标
            if '_metrics' in res.known_metadata:
                m = res.known_metadata['_metrics']
                total_usage['input_tokens'] += m.get('input_tokens', 0)
                total_usage['output_tokens'] += m.get('output_tokens', 0)
                total_usage['total_tokens'] += m.get('total_tokens', 0)
                total_usage['latency'] += m.get('latency', 0)
                del res.known_metadata['_metrics'] # 清理
            
            pred_dict = {
                "sample_name": res.ai_sample_name.replace("$ai:", "") if res.ai_sample_name else None,
                "operator_name": res.ai_operator.replace("$ai:", "") if res.ai_operator else None,
                "pulse_program": res.ai_pulse_program.replace("$ai:", "") if res.ai_pulse_program else None,
                "solvent": res.ai_solvent.replace("$ai:", "") if res.ai_solvent else None,
                "sample_mass": res.ai_sample_mass.replace("$ai:", "") if res.ai_sample_mass else None,
                "filler": res.ai_filler.replace("$ai:", "") if res.ai_filler else None
            }
            truth_dict = {k: v for k, v in truth.items() if k in pred_dict}
            
            # 计算不同密度的精度
            key_truth = {k: v for k, v in truth_dict.items() if k in KEY_FIELDS}
            key_pred = {k: v for k, v in pred_dict.items() if k in KEY_FIELDS}
            
            metric = GeneralEvaluator.Calculate_Field_Accuracy(truth_dict, pred_dict)
            key_metric = GeneralEvaluator.Calculate_Field_Accuracy(key_truth, key_pred)
            
            metric['key_hits'] = key_metric['hits']
            metric['key_total'] = key_metric['total']
            metric['case_id'] = res.id
            all_metrics.append(metric)
            
        # 4. Summary Output
        num_cases = len(all_metrics)
        global_hits = sum(m['hits'] for m in all_metrics)
        global_total = sum(m['total'] for m in all_metrics)
        key_hits = sum(m['key_hits'] for m in all_metrics)
        key_total = sum(m['key_total'] for m in all_metrics)
        
        global_acc = (global_hits / global_total) * 100 if global_total else 0
        key_acc = (key_hits / key_total) * 100 if key_total else 0
        
        avg_latency = total_usage['latency'] / num_cases if num_cases else 0
        throughput = (num_cases / total_bench_time) if total_bench_time else 0
        
        print(f"\n{'='*20} DETAILED PIPELINE BENCHMARK {'='*20}")
        print(f"Total Cases: {num_cases}")
        print(f"Global Accuracy (All Fields): {global_acc:.2f}%")
        print(f"Key Field Accuracy (Sample/Prog/Solvent): {key_acc:.2f}%")
        print(f"-"*50)
        print(f"Performance Metrics:")
        print(f"  Avg Latency per record: {avg_latency:.3f}s")
        print(f"  Throughput: {throughput:.2f} records/s")
        print(f"  Total Token Usage: {total_usage['total_tokens']} (In: {total_usage['input_tokens']}, Out: {total_usage['output_tokens']})")
        print(f"  Est. Time for 100 records: {100 / throughput:.2f}s")
        print(f"{'='*60}\n")
        
        return {
            "global_acc": global_acc,
            "key_acc": key_acc,
            "avg_latency": avg_latency,
            "throughput": throughput,
            "tokens": total_usage,
            "num_cases": num_cases
        }
