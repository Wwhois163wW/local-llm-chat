#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# main.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260127
# Version: 1.2.0

import argparse
import configparser
import logging.config # @Antigravity, 20260128, [ADD]: Add logging.config import
import logging # @Antigravity, 20260128, [ADD]: Add logging import

from api_client import Get_LLM_Client_by_Config
from chat_module import Send_Message_to_LLM

def main():
    # @Antigravity, 20260128, [ADD]: Create logs directory if it does not exist
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # @Antigravity, 20260128, [ADD]: Configure logging from config.ini
    config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    logging.config.fileConfig(config_path, disable_existing_loggers=False)
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description="Interact with a local LLM.")
    parser.add_argument("prompt", type=str, help="The prompt to send to the LLM.")
    
    args = parser.parse_args()

    # Load configuration
    config = configparser.ConfigParser()
    # @Antigravity, 20260128, [DEL]: Removed redundant config_path definition
    config.read(config_path)

    model_name = config['LLM'].get('model', 'local-model')

    # Initialize LLM client
    llm_client = Get_LLM_Client_by_Config(config) # @Antigravity, 20260128, [FIX]: Pass config object instead of config_path

    if llm_client:
        logger.info("LLM client initialized successfully.") # @Antigravity, 20260128, [ADD]: Log success
        Send_Message_to_LLM(llm_client, args.prompt, config) # @Antigravity, 20260128, [FIX]: Pass config object instead of model_name
    else:
        logger.error("Failed to get LLM client, cannot send message.") # @Antigravity, 20260128, [FIX]: Use logger.error instead of print

if __name__ == '__main__':
    import os
    main()
