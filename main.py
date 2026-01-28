#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# main.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260127
# Version: 1.2.0

import argparse
import configparser
from api_client import Get_LLM_Client_by_Config
from chat_module import Send_Message_to_LLM

def main():
    parser = argparse.ArgumentParser(description="Interact with a local LLM.")
    parser.add_argument("prompt", type=str, help="The prompt to send to the LLM.")
    
    args = parser.parse_args()

    # Load configuration
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), 'config.ini') # Make sure to find config.ini relative to main.py
    config.read(config_path)

    model_name = config['LLM'].get('model', 'local-model')

    # Initialize LLM client
    llm_client = Get_LLM_Client_by_Config(config_path)

    if llm_client:
        Send_Message_to_LLM(llm_client, args.prompt, model_name)
    else:
        print("Failed to get LLM client, cannot send message.")

if __name__ == '__main__':
    import os
    main()
