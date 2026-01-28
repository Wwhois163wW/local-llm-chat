#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# chat_module.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260127
# Version: 1.2.0

from openai import OpenAI
import configparser

def Send_Message_to_LLM(client: OpenAI, user_content: str, model: str):
    """
    向LLM发送消息并获取回复。

    Args:
        client (OpenAI): OpenAI客户端实例。
        user_content (str): 用户输入的内容。
        model (str): 使用的模型名称。

    Returns:
        str: 模型的回复内容，或在出错时返回None。
    """
    if not client:
        print("Error: OpenAI client is not initialized.")
        return None

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": user_content}
            ],
        )
        print("\n--- Response ---")
        response = completion.choices[0].message.content
        print(response)
        return response
    except Exception as e:
        print(f"Error during API call: {e}")
        return None

if __name__ == '__main__':
    # 示例用法
    from api_client import Get_LLM_Client_by_Config
    
    config = configparser.ConfigParser()
    config.read('config.ini')
    model_name = config['LLM'].get('model', 'local-model') # 从配置加载模型，如果不存在则使用默认值

    llm_client = Get_LLM_Client_by_Config()
    if llm_client:
        test_question = "Are you gpt-oss-120B? Please indicate how much context you can handle."
        Send_Message_to_LLM(llm_client, test_question, model_name)
