#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# infra/llm/async_client.py
# Author: ZHU, W. phD
# License: RIKEN
# Version: 1.3.1 (Refactored for DDD)

import configparser
from openai import AsyncOpenAI
import logging

logger = logging.getLogger(__name__)

class AsyncLLMClientFactory:
    """DDD 架构下的异步 LLM 客户端工厂"""
    
    @staticmethod
    def Create_Client_from_Config(config: configparser.ConfigParser) -> AsyncOpenAI:
        try:
            ip = config['LLM']['ip']
            port = config['LLM']['port']
            api_key = config['LLM'].get('api_key', 'lm-studio')
            base_url = f"http://{ip}:{port}/v1"
            
            client = AsyncOpenAI(
                base_url=base_url,
                api_key=api_key,
                timeout=120.0,
            )
            logger.info(f"DDD Async LLM client initialized for {ip}:{port}")
            return client
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            raise ConnectionError(f"LLM Connection failed: {e}")
