#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# infra/llm_client.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260206
# Version: 1.2.1

import configparser
from openai import OpenAI, AsyncOpenAI
import os
import logging

logger = logging.getLogger(__name__)

def Get_LLM_Client_by_Config(config):
    """同步客户端 (Legacy)"""
    try:
        ip = config['LLM']['ip']
        port = config['LLM']['port']
        api_key = config['LLM']['api_key']
        base_url = f"http://{ip}:{port}/v1"
        return OpenAI(base_url=base_url, api_key=api_key, timeout=120.0)
    except Exception as e:
        logger.error(f"Failed to init sync client: {e}")
        return None

def Get_Async_LLM_Client_by_Config(config):
    """
    获取异步 LLM 客户端实例。
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
        logger.info(f"Async LLM client initialized for {ip}:{port}")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize async LLM client: {e}")
        return None

if __name__ == '__main__':
    # 示例用法
    # @Antigravity, 20260128, [ADD]: Load config for example usage
    config = configparser.ConfigParser()
    script_dir = os.path.dirname(__file__)
    config_path = os.path.join(script_dir, 'config.ini')
    config.read(config_path)

    client = Get_LLM_Client_by_Config(config) # @Antigravity, 20260128, [FIX]: Pass config object
    if client:
        logger.info("LLM client initialized successfully.") # @Antigravity, 20260128, [FIX]: Use logger.info instead of print
    else:
        logger.error("Failed to initialize LLM client.") # @Antigravity, 20260128, [FIX]: Use logger.error instead of print
