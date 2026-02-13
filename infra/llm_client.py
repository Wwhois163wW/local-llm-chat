#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# infra/llm_client.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260210
# Version: 1.3.0

import configparser
from openai import AsyncOpenAI
import os
import logging

logger = logging.getLogger(__name__)

def Get_LLM_Client_by_Config(config: configparser.ConfigParser) -> AsyncOpenAI | None:
    """
    统一获取异步 LLM 客户端实例。
    @zhu, 20260211, [REF]: 全量异步化。强制移除同步客户端以对齐架构。
    """
    try:
        ip = config['LLM']['ip']
        port = config['LLM']['port']
        api_key = config['LLM']['api_key']
        base_url = f"http://{ip}:{port}/v1"
        
        client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=120.0,
        )
        logger.info(f"Unified Async LLM client initialized for {ip}:{port}")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize unified LLM client: {e}")
        return None

if __name__ == '__main__':
    # 示例用法
    config = configparser.ConfigParser()
    script_dir = os.path.dirname(__file__)
    # @Antigravity, 2026/02/12, [REF]: 精简配置路径，禁止向工作区外扩散。
    config_path = os.path.join(script_dir, 'config.ini')
    if os.path.exists(config_path):
        config.read(config_path, encoding='utf-8')

    client = Get_LLM_Client_by_Config(config)
    if client:
        logger.info("LLM client initialized successfully (Async).")
    else:
        logger.error("Failed to initialize LLM client.")
