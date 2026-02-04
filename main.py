#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# main.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260204
# Version: 1.9.0

import configparser
import logging.config
import logging
import os
import csv
import sys
from datetime import datetime

from logging_setup import get_logging_config
from api_client import Get_LLM_Client_by_Config
from chat_module import ChatSession
from agent import Agent
from events import TextChunk, StatsUpdate, FileWriteStart, FileContentChunk, FileWriteEnd

def save_usage_stats(log_dir: str, model_name: str, stats: StatsUpdate):
    # ... (This function remains the same)
    pass

def main():
    base_dir = os.path.dirname(__file__)
    log_dir = os.path.join(base_dir, 'logs')
    # ... (Config and logger setup remains the same)

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
                logger.info("Exit command received. Shutting down.")
                chat_session.save_history(history_file)
                print("Goodbye!")
                break
            
            # ... (/add command parsing remains the same)

            print(f"\nLLM > ", end="", flush=True)
            
            # The agent's run method now orchestrates the entire ReAct loop
            event_stream = agent.run(
                user_content=final_user_query,
                files=files_to_send if files_to_send else None
            )

            # The consumer loop remains largely the same
            final_stats = None
            # ... (event handling logic for UI) 
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            chat_session.save_history(history_file)
            break
        except Exception as e:
            logger.error(f"An unexpected error occurred in the main loop: {e}")
            break

if __name__ == '__main__':
    main()
