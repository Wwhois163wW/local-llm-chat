#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# consumer.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260205
# Version: 1.0.0

import asyncio
import logging
from agent import Agent
from chat_module import ChatSession
from events import TextChunk, StatsUpdate, FileReadRequest, FileWriteStart, FileWriteEnd
from tools import read_file
import os

logger = logging.getLogger(__name__)

_SECTION_TITLE = "\n--- Local LLM Chat ---"
_SECTION_WELCOME = "Commands: /add <file_path> | quit, exit, goodbye"
_SECTION_TIMEOUT_WARNING = "\n[Session Timeout] Closing connection..."

# This function is now the main entry point for the CLI interaction
async def consume_events(agent: Agent, chat_session: ChatSession, config: dict):
    print(_SECTION_TITLE)
    print(_SECTION_WELCOME)
    
    wait_limit = config.getint('Agent', 'timeout_seconds', fallback=300)

    while True:
        try:
            should_continue = await asyncio.wait_for(
                chat_looping(agent, chat_session, config),
                timeout=wait_limit
            )
            if not should_continue:
                break
        except asyncio.TimeoutError:
            logger.warning(f"Chat session timed out after {wait_limit}s.")
            print(_SECTION_TIMEOUT_WARNING)
            break
        except Exception as e:
            logger.error(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
            break

async def chat_looping(agent: Agent, chat_session: ChatSession, config: dict) -> bool:
    try:
        user_input = await asyncio.to_thread(input, "\nYou > ")
    except (KeyboardInterrupt, EOFError):
        return False
    
    if user_input.lower() in ["quit", "exit", "goodbye"]:
        return False

    chat_session.add_conversation_message('user', user_input)
    
    # /add command is handled inside add_conversation_message, so we just run the agent
    if user_input.startswith('/add'):
        # For /add command, we don't need to call the LLM, just print confirmation
        # The confirmation is already added to history as an assistant message
        last_message = chat_session.chat_history[-1]
        print(f"\nLLM > {last_message['content']}")
        return True

    print(f"\nLLM > ", end="", flush=True)
    try:
        event_stream = agent.run()
        
        async for event in event_stream:
            # Simple event consumer logic
            if isinstance(event, TextChunk):
                print(event.content, end="", flush=True)
            elif isinstance(event, StatsUpdate):
                # ... handle stats if needed ...
                pass
            else:
                # In this simplified model, other events are just logged
                logger.info(f"Consumer received event: {event}")
        print() # Final newline after stream

    except Exception as e:
        logger.error(f"An error occurred while running agent: {e}", exc_info=True)
        print(f"\n[Error]: {e}")

    return True
