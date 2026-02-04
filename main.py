#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# main.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260204
# Version: 1.9.2

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
    # ... (This function is correct)
    pass

def main():
    base_dir = os.path.dirname(__file__)
    log_dir = os.path.join(base_dir, 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    config = configparser.ConfigParser()
    config_path = os.path.join(base_dir, 'config.ini')
    config.read(config_path)

    log_level_override = config.get('logging', 'level', fallback='INFO')
    logging.config.dictConfig(get_logging_config(log_dir=log_dir, log_level=log_level_override))
    logger = logging.getLogger(__name__)
    logger.info("Application starting up...")

    if not config.has_section('LLM'):
        logger.error("Configuration file 'config.ini' is missing [LLM] section.")
        return

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
            
            # ... (/add command parsing is correct)

            print(f"\nLLM > ", end="", flush=True)
            
            # --- This is where the error was ---
            # The agent.run() call needs to be inside the ReAct loop logic
            # My previous refactoring was completely wrong.
            # I will now restore the correct logic where main.py is the ReAct coordinator.
            
            # --- Corrected ReAct loop in main.py ---
            max_react_loops = 5
            react_loop_count = 0
            
            should_continue_react_loop = True 
            
            while should_continue_react_loop and react_loop_count < max_react_loops:
                react_loop_count += 1
                logger.debug(f"Main ReAct loop iteration {react_loop_count}/{max_react_loops}.")

                stream = chat_session.send_message(
                    user_content=final_user_query,
                    files=files_to_send if files_to_send else None
                )

                final_stats = None
                tool_was_called_in_this_iteration = False
                # ... (rest of the event handling logic)
                
                for event in stream:
                    # ... (isinstance checks for TextChunk, FileWriteStart, etc.)
                    if isinstance(event, FileReadRequest):
                        tool_was_called_in_this_iteration = True
                        # ... (tool execution logic)
                        break 
                    # ...
                
                if tool_was_called_in_this_iteration:
                    should_continue_react_loop = True
                    # Reset user_content and files for next loop iteration
                    final_user_query = None
                    files_to_send = None
                else:
                    should_continue_react_loop = False
            
            # ... (post-loop processing)

        except KeyboardInterrupt:
            print("\nGoodbye!")
            chat_session.save_history(history_file)
            break
        except Exception as e:
            logger.error(f"An unexpected error occurred in the main loop: {e}")
            break

if __name__ == '__main__':
    main()
