#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# infra/llm/nmr_extractor_adapter.py
# Author: ZHU, W. phD
# Version: 1.0.0

import json
import logging
import time
from typing import List, Dict, Any
from typing_extensions import override
from openai import AsyncOpenAI
from core.interfaces.agent_interfaces import INMRExtractor
from core.models.nmr_models import DataChunk, NMRRecord
from core.processor import Get_Batch_NMR_Prompt

class NMRExtractorAdapter(INMRExtractor):
    """适配器：将领域层的推理请求转发给后端的 LLM 服务。"""
    
    def __init__(self, client: AsyncOpenAI, model: str):
        self.client = client
        self.model = model

    async def Extract_Batch(self, chunk: DataChunk) -> List[NMRRecord]:
        # 1. Prepare records for prompt
        records_to_process = []
        for r in chunk.records:
            records_to_process.append({
                "id": r.id,
                "data_path": r.data_path,
                "title": r.title,
                "known_metadata": r.known_metadata
            })
            
        # 2. Assemble Prompt (Use legacy Get_Batch_NMR_Prompt but with DDD context)
        # Note: We pass persona and facts into Get_Batch_NMR_Prompt if needed, 
        # or we could refactor Get_Batch_NMR_Prompt to be even more DDD-friendly.
        persona_str = chunk.context.persona if chunk.context else ""
        kb_str = "\n".join(chunk.context.kb_fragments) if chunk.context else ""
        full_context = f"{persona_str}\n{kb_str}".strip()
        
        # We manually inject soul context into the prompt via official parameter
        messages = Get_Batch_NMR_Prompt(
            records_to_process, 
            external_context=full_context
        )

        # 3. Request LLM
        logging.info(f"Extracting batch of {len(chunk.records)} via LLM...")
        
        start_time = time.time()
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.0
            )
            latency = time.time() - start_time
            content = resp.choices[0].message.content or ""
            usage = resp.usage
            
            # 记录指标到日志
            metrics = {
                "latency": latency,
                "input_tokens": usage.prompt_tokens if usage else 0,
                "output_tokens": usage.completion_tokens if usage else 0,
                "total_tokens": usage.total_tokens if usage else 0
            }
            logging.info(f"LLM Metrics: {metrics}")
            
            # 4. Parse JSON Array
            if '```json' in content: 
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content: 
                content = content.split('```')[1].split('```')[0].strip()
            
            results = json.loads(content)
            
            # 5. Map back to domain models
            for res in results:
                rec_id = res.get('id')
                record = chunk.get_record_by_id(rec_id)
                if record:
                    record.ai_sample_name = res.get('sample_base_name')
                    record.ai_operator = res.get('operator_name')
                    record.ai_sample_mass = res.get('sample_mass')
                    record.ai_solvent = res.get('solvent')
                    record.ai_pulse_program = res.get('pulse_program')
                    record.ai_filler = res.get('filler')
                    record.ai_reasoning = res.get('reasoning')
                    # 临时存储性能指标在第一个记录中，或者扩展接口
                    record.known_metadata['_metrics'] = metrics
                    
            return chunk.records
            
        except Exception as e:
            logging.error(f"LLM Extraction failed: {e}")
            raise e
