#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# chat_module.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260127
# Version: 1.2.0

from openai import OpenAI
import configparser
import logging # @Antigravity, 20260128, [ADD]: Add logging import
import os # @Antigravity, 20260128, [ADD]: Add os import for example usage

logger = logging.getLogger(__name__) # @Antigravity, 20260128, [ADD]: Get logger instance

def Send_Message_to_LLM(client: OpenAI, user_content: str, config: configparser.ConfigParser): # @Antigravity, 20260128, [FIX]: Accept config object directly
    """
    向LLM发送消息并获取回复。

    Args:
        client (OpenAI): OpenAI客户端实例。
        user_content (str): 用户输入的内容。
        config (configparser.ConfigParser): 已经加载的配置对象。

    Returns:
        str: 模型的回复内容，或在出错时返回None。
    """
    model = config['LLM'].get('model', 'local-model') # @Antigravity, 20260128, [ADD]: Get model from config

    if not client:
        logger.error("Error: OpenAI client is not initialized.") # @Antigravity, 20260128, [FIX]: Use logger.error instead of print
        return None

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": user_content}
            ],
        )
        logger.info("\n--- Response ---") # @Antigravity, 20260128, [FIX]: Use logger.info instead of print
        response = completion.choices[0].message.content
        logger.info(response) # @Antigravity, 20260128, [FIX]: Use logger.info instead of print
        return response
    except Exception as e:
        logger.error(f"Error during API call: {e}") # @Antigravity, 20260128, [FIX]: Use logger.error instead of print
        return None

if __name__ == '__main__':
    # 示例用法
    from api_client import Get_LLM_Client_by_Config
    
    # @Antigravity, 20260128, [ADD]: Load config for example usage
    config = configparser.ConfigParser()
    script_dir = os.path.dirname(__file__)
    config_path = os.path.join(script_dir, 'config.ini')
    config.read(config_path)

    llm_client = Get_LLM_Client_by_Config(config) # @Antigravity, 20260128, [FIX]: Pass config object
    if llm_client:
        test_question = "Are you gpt-oss-120B? Please indicate how much context you can handle."
        Send_Message_to_LLM(llm_client, test_question, config) # @Antigravity, 20260128, [FIX]: Pass config object
