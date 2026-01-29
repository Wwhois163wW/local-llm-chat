#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# main.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260129
# Version: 1.3.0

import configparser
import logging.config
import logging
import os
from logging_setup import get_logging_config

from api_client import Get_LLM_Client_by_Config
from chat_module import ChatSession # @Antigravity, 20260129, [MOD]: Import ChatSession

def main():
    # --- Configuration and Logging Setup ---
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    config.read(config_path)

    log_level_override = config.get('logging', 'level', fallback='INFO')
    logging_config = get_logging_config(log_dir=log_dir, log_level=log_level_override)
    logging.config.dictConfig(logging_config)
    logger = logging.getLogger(__name__)

    logger.info("Application starting up...")

    # --- Main Logic ---
    if not config.has_section('LLM'):
        logger.error("Configuration file 'config.ini' is missing [LLM] section.")
        logger.error("Please copy 'config.example.ini' to 'config.ini' and fill in your details.")
        return

    llm_client = Get_LLM_Client_by_Config(config)

    if not llm_client:
        logger.error("Failed to initialize LLM client. Exiting.")
        return

    logger.info("LLM client initialized. Starting interactive chat session.")
    
    # Create a chat session
    chat_session = ChatSession(llm_client, config)
    
    # --- Interactive Loop ---
    print("\n--- Local LLM Chat ---")
    print("Enter 'quit', 'exit', or '再见' to end the session.")

    while True:
        try:
            user_input = input("\nYou > ")

            if user_input.lower() in ["quit", "exit", "再见"]:
                logger.info("Exit command received. Shutting down.")
                print("Goodbye!")
                break
            
            if not user_input.strip():
                continue

            response = chat_session.send_message(user_input)

            if response:
                print(f"\nLLM > {response}")
            else:
                print("\nLLM > Sorry, I encountered an error.")

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received. Shutting down.")
            print("\nGoodbye!")
            break
        except Exception as e:
            logger.error(f"An unexpected error occurred in the main loop: {e}")
            break

if __name__ == '__main__':
    main()
