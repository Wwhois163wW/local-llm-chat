#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# application/pipeline.py
# Author: ZHU, W. phD
# License: RIKEN
# Version: 1.0.0

import logging
from typing import List, Dict, Any
from core.models.nmr_models import NMRRecord, DataChunk, ContextBundle, Publication
from core.interfaces.agent_interfaces import IPersonaSynthesizer, IKnowledgeMatcher, INMRExtractor

class EnrichmentPipeline:
    """元数据增强编排器：核心 Pipeline，协调画像驱动的数据提取流。"""
    
    def __init__(self, 
                 persona_agent: IPersonaSynthesizer,
                 kb_agent: IKnowledgeMatcher,
                 extractor_agent: INMRExtractor
                ):
        self.persona_agent = persona_agent
        self.kb_agent = kb_agent
        self.extractor_agent = extractor_agent

    def Chunk_Records(self, records: List[NMRRecord]) -> List[DataChunk]:
        """按目录物理路径对记录进行分块"""
        chunks_map: Dict[str, DataChunk] = {}
        for rec in records:
            dir_path = "/".join(rec.data_path.replace("\\", "/").split("/")[:-1])
            if dir_path not in chunks_map:
                chunks_map[dir_path] = DataChunk(directory_path=dir_path)
            chunks_map[dir_path].records.append(rec)
        return list(chunks_map.values())

    async def Execute_Full_Enrichment(self, raw_records: List[NMRRecord]) -> List[NMRRecord]:
        """执行端到端全链路增强流程"""
        logging.info(f"Starting Pipeline for {len(raw_records)} records.")
        
        # 1. Chunking
        chunks = self.Chunk_Records(raw_records)
        enriched_all = []
        MAX_BATCH_SIZE = 5 # 适配 8k Context 与 Flash Attention，恢复工业级吞吐量
        
        for chunk in chunks:
            # 2. Context Assembly
            mock_pubs = [Publication(title="NMR studies of Alumina", year="2024")]
            sample_rec = chunk.records[0]
            op = sample_rec.known_metadata.get('operator', 'ZHU')
            year = "2024"
            
            persona = self.persona_agent.Synthesize_Persona(op, year, mock_pubs)
            facts = self.kb_agent.Match_Facts([r.title for r in chunk.records[:1]])
            
            chunk.context = ContextBundle(
                persona=persona,
                kb_fragments=facts,
                references=mock_pubs
            )
            
            # 3. LLM Extraction with Sub-batching
            all_records_in_chunk = chunk.records
            for i in range(0, len(all_records_in_chunk), MAX_BATCH_SIZE):
                sub_records = all_records_in_chunk[i:i + MAX_BATCH_SIZE]
                sub_chunk = DataChunk(
                    directory_path=chunk.directory_path,
                    records=sub_records,
                    context=chunk.context
                )
                
                try:
                    processed_sub_records = await self.extractor_agent.Extract_Batch(sub_chunk)
                    enriched_all.extend(processed_sub_records)
                except Exception as e:
                    logging.error(f"Sub-batch extraction failed in {chunk.directory_path}: {e}")
                    enriched_all.extend(sub_records) # Fallback
                
        return enriched_all
