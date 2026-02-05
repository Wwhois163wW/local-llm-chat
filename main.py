#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# main.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260205
# Version: 2.2.0

import configparser
import logging.config
import logging
import os
import asyncio

from logging_setup import get_logging_config
from api_client import Get_LLM_Client_by_Config
from chat_module import ChatSession
from agent import Agent
from consumer import consume_events # Import the main consumer

def check_history_file(base_dir: str) -> str:
    history_dir = os.path.join(base_dir, 'output')
    os.makedirs(history_dir, exist_ok=True)
    history_file = os.path.join(history_dir, 'chat_history.jsonl')
    return history_file

async def main():
    base_dir = os.path.dirname(__file__)
    
    # 1. Setup Logging & Config
    log_dir = os.path.join(base_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_config = get_logging_config(log_dir=log_dir)
    logging.config.dictConfig(log_config)
    logger = logging.getLogger(__name__)
    
    config = configparser.ConfigParser()
    config_path = os.path.join(base_dir, 'config.ini')
    config.read(config_path)
    
    logger.info("Application starting up...")

    # 2. Assemble Dependencies
    try:
        llm_client = Get_LLM_Client_by_Config(config)
        history_file = check_history_file(base_dir)
        chat_session = ChatSession(
            client=llm_client, 
            config=config, 
            history_file=history_file
        )
        debug_mode = config.getboolean('Agent', 'debug_mode', fallback=False)
        agent = Agent(chat_session, debug_mode)
    except Exception as e:
        logger.critical(f"Failed to initialize core components: {e}", exc_info=True)
        return

    # 3. Launch the UI / Consumer Layer
    await consume_events(agent, chat_session, config)
    
    logger.info("Application shutting down.")

if __name__ == '__main__':
    asyncio.run(main())
