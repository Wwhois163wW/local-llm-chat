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
            final_stats = None
            output_file_path = None
            file_buffer = []
            is_writing_file = False
            has_text_output = False
            file_written_successfully = False
            
            for event in event_stream:
                if isinstance(event, TextChunk):
                    has_text_output = True
                    print(event.content, end="", flush=True)
                elif isinstance(event, FileWriteStart):
                    try:
                        output_dir = os.path.join(base_dir, 'output')
                        if not os.path.exists(output_dir):
                            os.makedirs(output_dir)
                        safe_filename = os.path.basename(event.path)
                        output_file_path = os.path.join(output_dir, safe_filename)
                        is_writing_file = True
                        file_buffer.clear()
                        print(f"\n[LLM wants to write file: {output_file_path}]", end="", flush=True)
                    except Exception as e:
                        logger.error(f"Failed to prepare file for writing: {e}")
                        print(f"\n[Error: Could not prepare file {event.path}]", end="", flush=True)
                elif isinstance(event, FileContentChunk):
                    if is_writing_file:
                        file_buffer.append(event.content)
                elif isinstance(event, FileWriteEnd):
                    if is_writing_file:
                        try:
                            if output_file_path:
                                with open(output_file_path, "w", encoding="utf-8") as f:
                                    f.write("".join(file_buffer))
                                print(f" -> [Saved successfully.]", end="", flush=True)
                                file_written_successfully = True
                        except Exception as e:
                            logger.error(f"Failed to save buffered content to file: {e}")
                            print(f" -> [Error saving file: {e}]", end="", flush=True)
                        finally:
                            is_writing_file = False
                            file_buffer.clear()
                elif isinstance(event, StatsUpdate):
                    final_stats = event

            if is_writing_file:
                logger.warning(f"File write op for '{output_file_path}' not completed (missing tag).")
                print(f" -> [Save failed: Incomplete response.]", end="", flush=True)
            
            if file_written_successfully and not has_text_output:
                print("OK, the file has been saved.", end="")

            if final_stats:
                save_usage_stats(log_dir, chat_session.model, final_stats)
                usage = final_stats.usage
                print(f"\n\n[Stats] Latency: {final_stats.latency:.2f}s | Tokens: {usage['total_tokens']} "
                      f"(In: {usage['prompt_tokens']}, Out: {usage['completion_tokens']})")
            else:
                print()

        except KeyboardInterrupt:
            chat_session.save_history(history_file)
            print("\nGoodbye!")
            break
        except Exception as e:
            logger.error(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
            break

if __name__ == '__main__':
    main()