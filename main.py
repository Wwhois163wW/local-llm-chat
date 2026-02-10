#!/usr/bin/env python3
# -*- coding: utf-8 -*- 
# main.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260206
# Version: 0.0.1

import configparser
import logging.config
import logging
import os
import asyncio

from infra.logging_setup import get_logging_config
from infra.llm_client import Get_Async_LLM_Client_by_Config
from core.session import ChatSession
from core.agent import Agent
from core.consumer import consume_events # Import the main consumer

# @Antigravity, 20260206, [CLEANUP]: 清理冗余注释并添加标准 Docstring
def check_history_file(base_dir: str) -> str:
    """
    确保历史记录目录存在并返回聊天历史文件的完整路径。

    Args:
        base_dir (str): 项目根目录。

    Returns:
        str: 聊天历史文件的绝对路径 (chat_history.jsonl)。
    """
    history_dir = os.path.join(
        base_dir, 
        'output'
    )
    os.makedirs(
        history_dir, 
        exist_ok=True
    )
    history_file = os.path.join(
        history_dir, 
        'chat_history.jsonl'
    )
    return history_file

async def main():
    """
    应用程序的主入口点。
    负责初始化日志、加载配置、组装核心组件并启动事件消费者。
    """
    base_dir = os.path.dirname(__file__)
    
    # 1. Setup Logging & Config
    log_dir = os.path.join(
        base_dir, 
        'logs'
    )
    os.makedirs(
        log_dir, 
        exist_ok=True
    )
    log_config = get_logging_config(log_dir=log_dir)
    logging.config.dictConfig(log_config)
    logger = logging.getLogger(__name__)
    
    config = configparser.ConfigParser()
    config_path = os.path.join(
        base_dir, 
        'config.ini'
    )
    # @Antigravity, 20260206, [FIX]: 增加对配置读取结果的类型判断与容错
    config_result = config.read(config_path)
    if not config_result:
        logger.error(f"Failed to read config file from: {config_path}")
        return
    
    logger.info("Application starting up...")

    # 2. Assemble Dependencies
    try:
        # [FIX]: 切换至异步 LLM 客户端驱动
        llm_client = Get_Async_LLM_Client_by_Config(config)
        if not llm_client:
            return
        history_file = check_history_file(base_dir)
        chat_session = ChatSession(
            client=llm_client, 
            config=config, 
            history_file=history_file
        )
        debug_mode = config.getboolean(
            'Agent', 
            'debug_mode', 
            fallback=False
        )
        agent = Agent(
            chat_session, 
            debug_mode
        )
    except Exception as e:
        logger.critical(
            f"Failed to initialize core components: {e}", 
            exc_info=True
        )
        return

    # 3. Launch the UI / Consumer Layer
    await consume_events(
        agent, 
        chat_session, 
        config
    )
    
    logger.info("Application shutting down.")

if __name__ == '__main__':
    asyncio.run(
        main()
    )
