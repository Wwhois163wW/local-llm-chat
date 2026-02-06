#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/consumer.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260206
# Version: 1.0.2

import asyncio
import logging
from core.agent import Agent
from core.session import ChatSession
from core.events import TextChunk, StatsUpdate

logger = logging.getLogger(__name__)

_SECTION_TITLE = "\n--- Local LLM Chat ---"
_SECTION_WELCOME = "Commands: quit, exit, goodbye" # Removed /add for now
_SECTION_TIMEOUT_WARNING = "\n[Session Timeout] Closing connection..."

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
    
    print(f"\nLLM > ", end="", flush=True)
    try:
        event_stream = agent.run()
        
        async for event in event_stream:
            if isinstance(event, TextChunk):
                print(event.content, end="", flush=True)
            elif isinstance(event, StatsUpdate):
                # For now, we just consume it without printing
                pass
            else:
                logger.info(f"Consumer received unhandled event: {event}")
        print()

    except Exception as e:
        logger.error(f"An error occurred while running agent: {e}", exc_info=True)
        print(f"\n[Error]: {e}")

    return True