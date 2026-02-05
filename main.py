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
import asyncio
import time

from logging_setup import get_logging_config
from api_client import Get_LLM_Client_by_Config
from chat_module import ChatSession
from agent import Agent
from events import (
    TextChunk, 
    StatsUpdate, 
    FileWriteStart, 
    FileContentChunk, 
    FileWriteEnd,
    FileReadRequest
)

_SECTION_TITLE = "\n--- Local LLM Chat ---"
_SECTION_WELCOME = "Commands: /add <file_path> | quit, exit, goodbye"
_SECTION_TIMEOUT_WARNING = "\n[Session Timeout] Closing connection..."

def save_usage_stats(
    log_dir: str, 
    model_name: str, 
    stats: StatsUpdate
):
    """
    Save LLM usage statistics to CSV file.

    Args:
        log_dir (str): Directory to save the CSV file.
        model_name (str): Name of the LLM model.
        stats (StatsUpdate): Statistics to save.
    """
    # @zhu, 20260204,[add] add init coding
    logger = logging.getLogger(__name__)

    if not stats:
        return

    csv_file = os.path.join(log_dir, 'usage_stats.csv')
    
    # Check if file exists to determine if we need to write header
    file_exists = os.path.exists(csv_file)

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    usage:dict = stats.usage
    # stats: StatsUpdate ={
    #   usage:{
    #       prompt_tokens,
    #       completion_tokens,
    #       total_tokens
    #   },
    #   latency:float
    # }
    
    row = {
        'timestamp': timestamp,
        'model': model_name,
        'latency_sec': f'{stats.latency: .4f}',
        'total_tokens': usage.get('total_tokens', 0),
        'prompt_tokens': usage.get('prompt_tokens', 0),
        'completion_tokens': usage.get('completion_tokens', 0)
    }

    try:
        with open(csv_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            
            # Write header if file is new
            if not file_exists:
                writer.writeheader()
            
            # Write stats row
            writer.writerow(row)
        
        logger.debug(f"Usage stats saved to {csv_file}")        
    except Exception as e:
        logger.error(f"Failed to save usage stats to CSV: {e}")

def check_history_file(base_dir: str) -> str:
    history_dir = os.path.join(base_dir, 'output')
    os.makedirs(history_dir, exist_ok=True)
    history_file = os.path.join(history_dir, 'chat_history.jsonl')
    return history_file

async def main():
    base_dir = os.path.dirname(__file__)
    log_dir = os.path.join(base_dir, 'logs')
    # @zhu, 20260204,[add] add logger
    log_config = get_logging_config()
    logging.config.dictConfig(log_config)
    logger = logging.getLogger(__name__)
    # @zhu, 20260204,[add] get config
    config = configparser.ConfigParser()
    config_path = os.path.join(base_dir, 'config.ini')
    config.read(config_path)
    # @zhu, 20260204,[add] get llm client
    llm_client = Get_LLM_Client_by_Config(config)
    
    # @zhu, 20260204,[add] load history
    history_file = check_history_file(base_dir)
    # @zhu, 20260204,[add] init chat session and agent
    chat_session = ChatSession(
        llm_client, 
        config, 
        history_file=history_file
    )
    agent = Agent(chat_session)
    
    # @zhu, 20260204,[add] print section title and welcome
    print(_SECTION_TITLE)
    print(_SECTION_WELCOME)

    # @zhu, 20260204,[add] main loop, use asyncio.wait_for to limit timeout
    chat_limit = 1024
    wait_limit = 300
    chat_stats = True
    loop_count = 0
    while (
        chat_stats 
        and loop_count < chat_limit
    ):
        try:
            chat_stats = await asyncio.wait_for(
                chat_looping(
                    chat_session,
                    agent,
                    logger,
                    log_dir,
                    chat_session.model
                ),
            timeout = wait_limit
            )
            loop_count += 1

        except asyncio.TimeoutError:
            logger.warning(
                f"Chat session timed out after {wait_limit} seconds of inactivity."
            )
            print(_SECTION_TIMEOUT_WARNING)
            break
        except Exception as e:
            logger.error(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
            break
    logger.info("Application shutting down.")

async def chat_looping(
    chat_session: ChatSession,
    agent: Agent,
    logger: logging.Logger,
    log_dir: str,
    model_name: str
)-> bool:
    # @zhu, 20260204,[mark] user's turn
    try:
        user_input = await asyncio.to_thread(input, "\nYou > ") # @zhu, 20260204, [comment] we can use a customized user name if we store user info and inject it into the system prompt  
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye!")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
        return False
    
    # @zhu, 20260204,[mark] check if user want to quit first
    if user_input.lower() in ["quit", "exit", "goodbye"]:
        print("\nGoodbye!")
        return False

    # @zhu, 20260204,[mark] build final user query from user input, also user attend could be deal here
    chat_session.add_conversation_message('user', user_input)
        
    # @zhu, 20260204,[mark] llm's turn
    print(f"\nLLM > ", end="", flush=True)
    try:
        # @zhu, 20260204,[mark] llm could return a success flag to control the chat loop
        event_stream = agent.run()
        final_stats = None
        has_text_output = False

        async for event in event_stream:
            if isinstance(event, TextChunk):
                has_text_output = True
                print(event.content, end="", flush=True)

            elif isinstance(event, FileReadRequest):
                logger.info(f"Received FileReadRequest, creating background task.")
                asyncio.create_task(handle_tool_call(agent, event))

            elif isinstance(event, FileWriteStart):
                print(f"\n[Agent is writing to {event.path}...] ", end="", flush=True)
            elif isinstance(event, FileWriteEnd):
                print(f"[Done.]", end="", flush=True)
            elif isinstance(event, StatsUpdate):
                final_stats = event
            
        if final_stats:
            save_usage_stats(log_dir, model_name, final_stats)
            usage = final_stats.usage
            print(
                f"\n\n[Stats] Latency: {final_stats.latency:.2f}s | Tokens:{usage['total_tokens']} "
                f"(In: {usage['prompt_tokens']}, Out: {usage['completion_tokens']})"
            )
        else:
            print()

    except Exception as e:
        logger.error(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
        print("\nGoodbye!")
        return False
    
    return True

async def handle_tool_call(agent: Agent, event):
    """
    Event handler in backend
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Handling tool call in background: {event}")

    if isinstance(event, FileReadRequest):
        logger.info(f"Background task: executing read_file for {event.path}")
        await asyncio.sleep(2) # 模拟工具执行的耗时
        print("\n[Background Task: File read completed]")

if __name__ == '__main__':
    asyncio.run(main())