#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# main.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260204
# Version: 1.8.2

import configparser
import logging.config
import logging
import os
import csv
import sys
import time # For ReAct loop timeout
from datetime import datetime

from logging_setup import get_logging_config
from api_client import Get_LLM_Client_by_Config
from chat_module import ChatSession
from events import TextChunk, StatsUpdate, FileWriteStart, FileContentChunk, FileWriteEnd, FileReadRequest

def save_usage_stats(log_dir: str, model_name: str, stats: StatsUpdate):
    if not stats:
        return
    csv_file = os.path.join(log_dir, 'usage_stats.csv')
    file_exists = os.path.isfile(csv_file)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    usage = stats.usage
    row = {
        'timestamp': timestamp, 'model': model_name, 'latency_sec': f"{stats.latency:.4f}",
        'total_tokens': usage.get('total_tokens', 0), 'prompt_tokens': usage.get('prompt_tokens', 0),
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
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    config.read(config_path)

    log_level_override = config.get('logging', 'level', fallback='INFO')
    logging.config.dictConfig(get_logging_config(log_dir=log_dir, log_level=log_level_override))
    logger = logging.getLogger(__name__)
    logger.info("Application starting up...")

    if not config.has_section('LLM'):
        logger.error("Configuration file 'config.ini' is missing [LLM] section.")
        return

    llm_client = Get_LLM_Client_by_Config(config)
    if not llm_client:
        logger.error("Failed to initialize LLM client. Exiting.")
        return

    logger.info("LLM client initialized. Starting interactive chat session.")
    chat_session = ChatSession(llm_client, config)
    
    history_file = os.path.join(os.path.dirname(__file__), 'output', 'chat_history.json')
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
            
            # --- ReAct loop is now here in main.py ---
            max_react_loops = 5
            react_loop_count = 0
            
            # This flag tracks if an LLM call resulted in a tool being called in the current turn
            # and whether we should continue the ReAct loop
            should_continue_react_loop = True 
            
            while should_continue_react_loop and react_loop_count < max_react_loops:
                react_loop_count += 1
                logger.debug(f"Main ReAct loop iteration {react_loop_count}/{max_react_loops}.")

                # The chat_session.send_message now performs ONE LLM call
                # and yields its events
                stream = chat_session.send_message(
                    user_content=final_user_query, # Only sent on the first iteration
                    files=files_to_send if files_to_send else None # Only sent on the first iteration
                )

                final_stats = None
                output_file_path = None
                file_buffer = []
                is_writing_file = False
                has_text_output = False
                file_written_successfully = False
                tool_was_called_in_this_iteration = False # Track if any tool was called
                
                for event in stream:
                    if isinstance(event, TextChunk):
                        has_text_output = True
                        print(event.content, end="", flush=True)
                    elif isinstance(event, FileWriteStart):
                        try:
                            output_dir = os.path.join(os.path.dirname(__file__), 'output')
                            if not os.path.exists(output_dir):
                                os.makedirs(output_dir)
                            safe_filename = os.path.basename(event.path)
                            output_file_path = os.path.join(output_dir, safe_filename)
                            is_writing_file = True
                            file_buffer.clear()
                            print(f"\n[LLM wants to write file: {output_file_path}]")
                        except Exception as e:
                            logger.error(f"Failed to prepare file for writing: {e}")
                            print(f"\n[Error: Could not prepare file {event.path}]")
                    elif isinstance(event, FileContentChunk):
                        if is_writing_file:
                            file_buffer.append(event.content)
                    elif isinstance(event, FileWriteEnd):
                        if is_writing_file:
                            try:
                                with open(output_file_path, "w", encoding="utf-8") as f:
                                    f.write("".join(file_buffer))
                                print(f" -> [Saved successfully.]")
                                file_written_successfully = True
                            except Exception as e:
                                logger.error(f"Failed to save buffered content to file: {e}")
                                print(f" -> [Error saving file: {e}]")
                            finally:
                                is_writing_file = False
                                file_buffer.clear()
                    elif isinstance(event, FileReadRequest):
                        tool_was_called_in_this_iteration = True
                        logger.info(f"LLM requested to read file: {event.path}")
                        
                        # Execute the tool and get its result message
                        tool_result_msg = chat_session._execute_read_file(event.path, store_content=True)
                        
                        # Add tool call and response to chat_session's history
                        chat_session.history.append({"role": "assistant", "content": f'<read_file path="{event.path}" />'})
                        chat_session.history.append({"role": "system", "content": tool_result_msg})
                        
                        # Set user_content and files_to_send to None for next LLM call in ReAct loop
                        # as they've already been processed in the first iteration.
                        final_user_query = None
                        files_to_send = None
                        
                        # Break from current event stream processing to go to next ReAct loop iteration
                        break 
                    elif isinstance(event, StatsUpdate):
                        final_stats = event
                
                # After iterating through all events from the stream
                if is_writing_file: # Handle incomplete write_file tags
                    logger.warning(f"File write op for '{output_file_path}' not completed (missing tag).")
                    print(f" -> [Save failed: Incomplete response.]")
                
                if tool_was_called_in_this_iteration:
                    should_continue_react_loop = True # Continue ReAct loop
                else:
                    should_continue_react_loop = False # No tool called, break ReAct loop
            
            # End of ReAct loop
            if react_loop_count >= max_react_loops and should_continue_react_loop:
                logger.error("Max ReAct loops reached. Agent may be in a loop.")
                print("\n[Warning] Max agent tool calls reached. Please rephrase your request.")
            
            # --- Final output processing ---
            if file_written_successfully and not has_text_output:
                print("OK, the file has been saved.", end="")

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
            print("\nGoodbye!")
            chat_session.save_history(history_file)
            break
        except Exception as e:
            logger.error(f"An unexpected error occurred in the main loop: {e}")
            break

if __name__ == '__main__':
    main()