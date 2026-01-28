#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# api_client.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260127
# Version: 1.2.0

import configparser
from openai import OpenAI
import os
import logging # @Antigravity, 20260128, [ADD]: Add logging import

logger = logging.getLogger(__name__) # @Antigravity, 20260128, [ADD]: Get logger instance

def Get_LLM_Client_by_Config(config): # @Antigravity, 20260128, [FIX]: Accept config object directly
    """
    根据配置文件获取LLM客户端实例。

    Args:
        config (configparser.ConfigParser): 已经加载的配置对象。

    Returns:
        openai.OpenAI: 配置好的OpenAI客户端实例。
    """
    # @Antigravity, 20260128, [DEL]: Removed redundant configparser.ConfigParser
    try:
        ip = config['LLM']['ip']
        port = config['LLM']['port']
        api_key = config['LLM']['api_key']
        
        base_url = f"http://{ip}:{port}/v1"
        
        client = OpenAI(
            base_url=base_url,
            api_key=api_key
        )
        logger.info(f"Querying EVO-X2 ({ip}) via uv...") # @Antigravity, 20260128, [FIX]: Use logger.info instead of print
        return client
    except KeyError as e:
        logger.error(f"Error: Missing LLM configuration item in config file: {e}") # @Antigravity, 20260128, [FIX]: Use logger.error instead of print
        return None
    except Exception as e:
        logger.error(f"Unknown error occurred while initializing LLM client: {e}") # @Antigravity, 20260128, [FIX]: Use logger.error instead of print
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
