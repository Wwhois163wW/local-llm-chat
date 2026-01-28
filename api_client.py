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

def Get_LLM_Client_by_Config(config_file='config.ini'):
    """
    根据配置文件获取LLM客户端实例。

    Args:
        config_file (str): 配置文件的路径。

    Returns:
        openai.OpenAI: 配置好的OpenAI客户端实例。
    """
    config = configparser.ConfigParser()
    config.read(config_file)

    try:
        ip = config['LLM']['ip']
        port = config['LLM']['port']
        api_key = config['LLM']['api_key']
        
        base_url = f"http://{ip}:{port}/v1"
        
        client = OpenAI(
            base_url=base_url,
            api_key=api_key
        )
        print(f"Querying EVO-X2 ({ip}) via uv...") 
        return client
    except KeyError as e:
        print(f"Error: Missing LLM configuration item in config file: {e}") # 修改为英文错误提示
        return None
    except Exception as e:
        print(f"Unknown error occurred while initializing LLM client: {e}") # 修改为英文错误提示
        return None

if __name__ == '__main__':
    # 示例用法
    client = Get_LLM_Client_by_Config()
    if client:
        print("LLM client initialized successfully.")
    else:
        print("Failed to initialize LLM client.")
