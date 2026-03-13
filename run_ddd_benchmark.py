#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# run_ddd_benchmark.py
# Main entry to verify the new DDD-soul-pipeline.

import asyncio
import logging
import configparser
from infra.config_loader import load_nmr_config
from core.logic.persona_service import PersonaSynthesizer
from core.logic.knowledge_service import KnowledgeMatcher
from infra.llm.async_client import AsyncLLMClientFactory
from infra.llm.nmr_extractor_adapter import NMRExtractorAdapter
from application.pipeline import EnrichmentPipeline
from core.eval.studio import PromptStudio

async def main():
    logging.basicConfig(level=logging.INFO)
    
    # 1. Load Config
    nmr_cfg = load_nmr_config()
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    
    # 2. Setup Infrastructure
    client = AsyncLLMClientFactory.Create_Client_from_Config(config)
    extractor = NMRExtractorAdapter(client, nmr_cfg['model_name'])
    
    # 3. Setup Domain Services
    persona = PersonaSynthesizer()
    kb = KnowledgeMatcher(kb_path=r'core\knowledge\nmr_kb.json') # Fixed path
    
    # 4. Setup Pipeline
    pipeline = EnrichmentPipeline(persona, kb, extractor)
    
    # 5. Handshake (Pre-heat Model for LMStudio)
    logging.info("Waking up LLM (LMStudio Handshake)...")
    try:
        # 简单尝试获取模型列表作为握手
        _ = await client.models.list()
        logging.info("Handshake successful. Waiting 3s for resource allocation...")
        await asyncio.sleep(3)
    except Exception as e:
        logging.warning(f"Handshake failed or timed out: {e}. Model might still be cold.")
    
    # 6. Run Studio
    studio = PromptStudio(pipeline)
    await studio.Benchmark_Pipeline(r'tests\benchmarks\static\benchmark_dataset.json', limit=20)

if __name__ == "__main__":
    asyncio.run(main())
