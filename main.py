#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# main.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260204
# Version: 2.0.0

import configparser
import logging.config
import logging
import os
import csv
from datetime import datetime

from logging_setup import get_logging_config
from api_client import Get_LLM_Client_by_Config
from chat_module import ChatSession
from agent import Agent
from events import TextChunk, StatsUpdate, FileWriteStart, FileContentChunk, FileWriteEnd

def save_usage_stats(log_dir: str, model_name: str, stats: StatsUpdate):
    # This function is correct
    pass

def main():
    base_dir = os.path.dirname(__file__)
    log_dir = os.path.join(base_dir, 'logs')
    # ... (Config and logger setup)
    config = configparser.ConfigParser()
    config_path = os.path.join(base_dir, 'config.ini')
    config.read(config_path)

    llm_client = Get_LLM_Client_by_Config(config)
    # ...
    
    chat_session = ChatSession(llm_client, config, base_dir)
    agent = Agent(chat_session)
    
    history_file = os.path.join(base_dir, 'output', 'chat_history.json')
    chat_session.load_history(history_file)
    
    print("\n--- Local LLM Chat ---")
    print("Commands: /add <file_path> | quit, exit, goodbye")

    while True:
        try:
            user_input = input("\nYou > ")
            if user_input.lower() in ["quit", "exit", "goodbye"]:
                chat_session.save_history(history_file)
                print("Goodbye!")
                break
            
            files_to_send = []
            final_user_query = user_input

            if user_input.startswith('/add'):
                # ... (/add parsing)
                pass

            print(f"\nLLM > ", end="", flush=True)
            
            # Main now correctly calls agent.run()
            event_stream = agent.run(
                user_content=final_user_query,
                files=files_to_send or None
            )

            # --- Event consumer loop ---
            # ... (event handling logic for UI is correct)

        except KeyboardInterrupt:
            chat_session.save_history(history_file)
            print("\nGoodbye!")
            break
        except Exception as e:
            logger.error(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
            break

if __name__ == '__main__':
    main()