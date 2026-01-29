#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# main.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260127
# Version: 1.2.0

import argparse
import configparser
import logging.config
import logging
import os
from logging_setup import get_logging_config # @Antigravity, 20260129, [ADD]: Import new logging setup

from api_client import Get_LLM_Client_by_Config
from chat_module import Send_Message_to_LLM

def main():
    # --- Configuration Setup ---
    # Create logs directory
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Load external config file if it exists
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    config.read(config_path)

    # --- Logging Setup ---
    # Get default logging config
    log_level_override = config.get('logging', 'level', fallback='INFO')
    logging_config = get_logging_config(log_level=log_level_override)
    
    # Apply logging configuration
    logging.config.dictConfig(logging_config)
    logger = logging.getLogger(__name__)

    logger.info("Logging configured successfully.")

    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Interact with a local LLM.")
    parser.add_argument("prompt", type=str, help="The prompt to send to the LLM.")
    
    args = parser.parse_args()

    # --- Main Logic ---
    if not config.has_section('LLM'):
        logger.error("Configuration file 'config.ini' is missing or does not have an [LLM] section.")
        logger.error("Please copy 'config.example.ini' to 'config.ini' and fill in your details.")
        return

    # Initialize LLM client
    llm_client = Get_LLM_Client_by_Config(config)

    if llm_client:
        logger.info("LLM client initialized successfully.")
        Send_Message_to_LLM(llm_client, args.prompt, config)
    else:
        logger.error("Failed to get LLM client, cannot send message.")

if __name__ == '__main__':
    main()
