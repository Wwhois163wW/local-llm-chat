#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# main.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260130
# Version: 1.4.0

import configparser
import logging.config
import logging
import os
import csv
import sys
from datetime import datetime

from logging_setup import get_logging_config
from api_client import Get_LLM_Client_by_Config
from chat_module import ChatSession, TextChunk, StatsUpdate, FileWriteStart, FileContentChunk, FileWriteEnd

def save_usage_stats(log_dir: str, model_name: str, stats: StatsUpdate):
    """Appends usage statistics to a CSV file."""
    if not stats:
        return

    csv_file = os.path.join(log_dir, 'usage_stats.csv')
    file_exists = os.path.isfile(csv_file)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    usage = stats.usage
    
    row = {
        'timestamp': timestamp,
        'model': model_name,
        'latency_sec': f"{stats.latency:.4f}",
        'total_tokens': usage.get('total_tokens', 0),
        'prompt_tokens': usage.get('prompt_tokens', 0),
        'completion_tokens': usage.get('completion_tokens', 0)
    }

    try:
        with open(csv_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to save usage stats to CSV: {e}")

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
    
    chat_session = ChatSession(llm_client, config)
    
    print("\n--- Local LLM Chat ---")
    print("Commands: /add <file_path> | quit, exit, goodbye")

    while True:
        try:
            user_input = input("\nYou > ")

            if user_input.lower() in ["quit", "exit", "goodbye"]:
                logger.info("Exit command received. Shutting down.")
                print("Goodbye!")
                break
            
            if not user_input.strip():
                continue

            files_to_send = []
            final_user_query = user_input

            if user_input.startswith('/'):
                parts = user_input.split(maxsplit=1)
                command = parts[0].lower()
                
                if command == '/add':
                    if len(parts) < 2:
                        print("Error: Please provide a file path. Usage: /add <path>")
                        continue
                    
                    file_path = parts[1].strip()
                    if (file_path.startswith('"') and file_path.endswith('"')) or \
                       (file_path.startswith("'") and file_path.endswith("'")):
                        file_path = file_path[1:-1]
                    
                    files_to_send.append(file_path)
                    final_user_query = f"I've uploaded the file '{os.path.basename(file_path)}', please review it."
                    print(f"File '{os.path.basename(file_path)}' queued for context...")
                else:
                    print(f"Unknown command: {command}")
                    continue

            print(f"\nLLM > ", end="", flush=True)
            
            stream = chat_session.send_message(
                user_content=final_user_query,
                files=files_to_send if files_to_send else None
            )

            final_stats = None
            output_file_handle = None
            output_file_path = None
            
            for event in stream:
                if isinstance(event, TextChunk):
                    print(event.content, end="", flush=True)
                elif isinstance(event, FileWriteStart):
                    try:
                        # Ensure logs directory exists if no other path is specified
                        if not os.path.dirname(event.path):
                             event.path = os.path.join(log_dir, event.path)
                        output_file_path = event.path
                        output_file_handle = open(output_file_path, "w", encoding="utf-8")
                        print(f"\n[Saving to file: {output_file_path}]", end="", flush=True)
                    except Exception as e:
                        logger.error(f"Failed to open file for writing: {e}")
                        print(f"\n[Error: Could not open file {event.path}]", end="", flush=True)
                elif isinstance(event, FileContentChunk):
                    if output_file_handle:
                        try:
                            output_file_handle.write(event.content)
                        except Exception as e:
                             logger.error(f"Failed to write to file: {e}")
                elif isinstance(event, FileWriteEnd):
                    if output_file_handle:
                        output_file_handle.close()
                        print(f"\n[File saved: {output_file_path}]", end="", flush=True)
                        output_file_handle = None
                        output_file_path = None
                elif isinstance(event, StatsUpdate):
                    final_stats = event

            # Ensure file is closed even if stream ends without a FileWriteEnd tag
            if output_file_handle:
                output_file_handle.close()
                logger.warning(f"File stream ended without a closing tag. File '{output_file_path}' was closed.")
                print(f"\n[File saved: {output_file_path}]", end="", flush=True)

            if final_stats:
                save_usage_stats(log_dir, chat_session.model, final_stats)
                usage = final_stats.usage
                print(f"\n\n[Stats] Latency: {final_stats.latency:.2f}s | Tokens: {usage['total_tokens']} "
                      f"(In: {usage['prompt_tokens']}, Out: {usage['completion_tokens']})")
            else:
                print()

            if chat_session.last_errors:
                print()
                for error_msg in chat_session.last_errors:
                    print(f"[Warning] {error_msg}")

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received. Shutting down.")
            print("\nGoodbye!")
            break
        except Exception as e:
            logger.error(f"An unexpected error occurred in the main loop: {e}")
            break

if __name__ == '__main__':
    main()
