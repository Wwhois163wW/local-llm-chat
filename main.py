#!/usr/bin/env python3
# -*- coding: utf-8 -*- 
# main.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260206
# Version: 1.1.0

import configparser
import logging.config
import logging
import os
import asyncio
import shutil
import argparse

from infra.logging_setup import get_logging_config
from infra.llm_client import Get_LLM_Client_by_Config
from core.session import ChatSession
from core.agent import Agent
from core.consumer import consume_events # Import the main consumer

# @zhu, 20260211, [TODO]: 确认迁移完成后清除此函数
def migrate_directories(base_dir: str):
    """
    自动迁移旧目录至新规范。
    output/ -> persistence/
    logs/ -> monitoring/
    .staging/ -> staging/
    """
    migration_map = {
        'output': 'persistence',
        'logs': 'monitoring',
        '.staging': 'staging'
    }
    for old, new in migration_map.items():
        old_path = os.path.join(base_dir, old)
        new_path = os.path.join(base_dir, new)
        if os.path.exists(old_path) and not os.path.exists(new_path):
            try:
                shutil.move(old_path, new_path)
                # 由于此时日志尚未初始化，使用标准输出通知用户
                print(f"[System] Workspace Migrated: {old}/ -> {new}/")
            except Exception as e:
                print(f"[Error] Failed to migrate {old}: {e}")

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
        'persistence' # @Antigravity, 2026/02/11, [REF]: output -> persistence
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
    # @Antigravity, 2026/02/13, [NEW]: 引入标准参数解析 (Standard CLI Argument Parsing)
    parser = argparse.ArgumentParser(
        description="AI Agent CLI with Async Turn Architecture."
    )
    parser.add_argument(
        "-c", "--config", 
        default="config.ini", 
        help="Path to the configuration file (default: config.ini)"
    )
    parser.add_argument(
        "-d", "--debug", 
        action="store_true", 
        help="Enable debug mode (overrides config.ini)"
    )
    parser.add_argument(
        "-v", "--version", 
        action="version", 
        version="AI Agent 1.2.0"
    )
    
    # 捕获未知参数并记录警告，而非直接奔溃
    args, unknown = parser.parse_known_args()
    if unknown:
        print(f"[Warning] Unknown arguments detected: {unknown}")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 0. 自动迁移旧目录规范
    migrate_directories(base_dir)
    
    # 1. Setup Logging & Config
    log_dir = os.path.join(
        base_dir, 
        'monitoring' # @Antigravity, 2026/02/11, [REF]: logs -> monitoring
    )
    os.makedirs(
        log_dir, 
        exist_ok=True
    )
    log_config = get_logging_config(log_dir=log_dir)
    logging.config.dictConfig(log_config)
    logger = logging.getLogger(__name__)
    
    config = configparser.ConfigParser()
    # 允许通过命令行指定配置文件路径
    config_path = (
        args.config if os.path.isabs(args.config) 
        else os.path.join(base_dir, args.config)
    )
    # @Antigravity, 20260206, [FIX]: 增加对配置读取结果的类型判断与容错
    # @Antigravity, 2026/02/12, [FIX]: 强制使用 UTF-8 编码以支持中文注释，防止 Windows GBK 冲突
    config_result = config.read(config_path, encoding='utf-8')
    if not config_result:
        logger.error(f"Failed to read config file from: {config_path}")
        return
    
    logger.info("Application starting up...")

    # 2. Assemble Dependencies
    try:
        # [FIX]: 切换至统一的异步 LLM 客户端驱动
        llm_client = Get_LLM_Client_by_Config(config)
        if not llm_client:
            return
        history_file = check_history_file(base_dir)
        chat_session = ChatSession(
            client=llm_client, 
            config=config, 
            history_file=history_file
        )
        # @Antigravity, 2026/02/13, [REF]: 参数优先级调试重构
        debug_mode = args.debug or config.getboolean(
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
