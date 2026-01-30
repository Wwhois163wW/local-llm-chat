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
import csv # @Antigravity, 20260129, [ADD]: Import for CSV logging
import time # @Antigravity, 20260129, [ADD]: Import for spinner
import threading # @Antigravity, 20260129, [ADD]: Import for non-blocking UI
import sys # @Antigravity, 20260129, [ADD]: Import for stdout flushing
from datetime import datetime # @Antigravity, 20260129, [ADD]: Import for timestamp
from logging_setup import get_logging_config

from api_client import Get_LLM_Client_by_Config
from chat_module import ChatSession # @Antigravity, 20260129, [MOD]: Import ChatSession

# @Antigravity, 20260129, [ADD]: Helper function to save stats to CSV
def save_usage_stats(log_dir, model_name, stats):
    """Appends usage statistics to a CSV file."""
    if not stats:
        return

    csv_file = os.path.join(log_dir, 'usage_stats.csv')
    file_exists = os.path.isfile(csv_file)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    usage = stats.get('usage', {})
    
    row = {
        'timestamp': timestamp,
        'model': model_name,
        'latency_sec': f"{stats.get('latency', 0):.4f}",
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

# @Antigravity, 20260129, [ADD]: Spinner task for threading
def spinner_task(stop_event):
    """Displays a rotating spinner while waiting."""
    spinner_chars = ['|', '/', '-', '\\']
    idx = 0
    while not stop_event.is_set():
        sys.stdout.write(f"\rThinking... {spinner_chars[idx]}")
        sys.stdout.flush()
        idx = (idx + 1) % len(spinner_chars)
        time.sleep(0.1)
    # Clear line on stop
    sys.stdout.write("\r" + " " * 20 + "\r")
    sys.stdout.flush()

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

            # @Antigravity, 20260130, [ADD]: Initialize files_to_send for potential file commands
            files_to_send = []
            final_user_query = user_input # Default to user's direct input

            # @Antigravity, 20260129, [ADD]: Handle commands like /add
            if user_input.startswith('/'):
                parts = user_input.split(maxsplit=1)
                command = parts[0].lower()
                
                if command == '/add':
                    if len(parts) < 2:
                        print("Error: Please provide a file path. Usage: /add <path>")
                        continue # Skip to next loop iteration
                    
                    file_path = parts[1].strip()
                    # @Antigravity, 20260129, [ADD]: Strip surrounding quotes from path (Windows convenience)
                    if (file_path.startswith('"') and file_path.endswith('"')) or \
                       (file_path.startswith("'") and file_path.endswith("'")):
                        file_path = file_path[1:-1]
                    
                    # @Antigravity, 20260130, [DEL]: Removed redundant path check, will be handled by ChatSession
                    # if not os.path.exists(file_path):
                    #     print(f"Error: File not found: {file_path}")
                    #     continue # Skip to next loop iteration
                    
                    # @Antigravity, 20260130, [MOD]: Add file to list, not modify user_input
                    files_to_send.append(file_path)
                    final_user_query = f"I've uploaded the file '{os.path.basename(file_path)}', please review it."
                    print(f"File '{os.path.basename(file_path)}' queued for context...")
                else:
                    print(f"Unknown command: {command}")
                    continue # Skip to next loop iteration

            # # response, stats = chat_session.send_message(user_input)
            
            # @Antigravity, 20260129, [MOD]: Threaded execution with spinner
            result_container = {}
            def api_call_wrapper():
                # @Antigravity, 20260130, [FIX]: Add try/except to ensure container is always populated
                try:
                    # @Antigravity, 20260130, [MOD]: Adapt to new send_message signature
                    result_container['response'], result_container['stats'] = chat_session.send_message(
                        user_content=final_user_query,
                        files=files_to_send if files_to_send else None # Only pass if files were actually added
                    )
                except Exception as e:
                    logger.error(f"Exception occurred in api_call_wrapper thread: {e}")
                    result_container['response'], result_container['stats'] = None, None

            # Start API thread
            api_thread = threading.Thread(target=api_call_wrapper)
            api_thread.start()

            # Start spinner logic
            stop_spinner = threading.Event()
            spinner_thread = threading.Thread(target=spinner_task, args=(stop_spinner,))
            spinner_thread.start()

            # Wait for API call to finish, but in a non-blocking way to catch interrupts
            while api_thread.is_alive():
                api_thread.join(timeout=0.2)
            
            # Stop spinner
            stop_spinner.set()
            spinner_thread.join()

            # @Antigravity, 20260130, [FIX]: Define response and stats from container
            response = result_container.get('response')
            stats = result_container.get('stats')

            # @Antigravity, 20260130, [ADD]: Check for and display any file injection errors
            if chat_session.last_errors:
                for error_msg in chat_session.last_errors:
                    print(f"[Warning] {error_msg}")

            if response:
                print(f"\nLLM > {response}")
                # @Antigravity, 20260129, [ADD]: Display statistics and save to CSV
                if stats:
                    # Save to CSV
                    save_usage_stats(log_dir, chat_session.model, stats)
                    
                    # Print simplified summary
                    usage = stats['usage']
                    print(f"\n[Stats] Latency: {stats['latency']:.2f}s | Tokens: {usage['total_tokens']} "
                          f"(In: {usage['prompt_tokens']}, Out: {usage['completion_tokens']})")
            elif not chat_session.last_errors: # Only print generic error if no specific errors were already shown
                print("\nLLM > Sorry, I encountered an error.")

        except KeyboardInterrupt:
            # @Antigravity, 20260130, [FIX]: Ensure spinner line is cleared on interrupt
            sys.stdout.write("\r" + " " * 20 + "\r")
            sys.stdout.flush()
            logger.info("Keyboard interrupt received. Shutting down.")
            print("\nGoodbye!")
            break
        except Exception as e:
            logger.error(f"An unexpected error occurred in the main loop: {e}")
            break

if __name__ == '__main__':
    main()
