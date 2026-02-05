#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# agent.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260205
# Version: 1.1.1

import logging
import time
import os

from chat_module import ChatSession
from parser import parse_stream
from events import FileReadRequest, TextChunk, FileContentChunk, StatsUpdate
from tools import read_file

logger = logging.getLogger(__name__)

class Agent:
    def __init__(self, chat_session: ChatSession,  debug_mode: bool = False):
        self.chat_session = chat_session
        self.debug_mode = debug_mode

    async def _handle_event(self, event):
        event_type_name = type(event).__name__.lower()
        handler_name = f'_handle_{event_type_name}'
        handler = getattr(self, handler_name, self._handle_default)
        
        if self.debug_mode:
            yield TextChunk(content=f"\n[DEBUG: Event -> {str(event)}]\n")

        async for result_event in handler(event):
            yield result_event

    async def _handle_textchunk(self, event):
        yield event

    async def _handle_default(self, event):
        logger.warning(f"Unhandled event type: {type(event).__name__}")
        yield TextChunk(
            content=f"[Agent: Received an unhandled event: {str(event)}]"
        )

    async def run(self):
        full_response_content = ""
        
        stream, prompt_tokens, start_time = await self.chat_session.call_llm()
        event_stream = parse_stream(stream)

        async for event in event_stream:
            async for processed_event in self._handle_event(event):
                # Correctly accumulate content from the processed TextChunk
                if isinstance(processed_event, TextChunk):
                    full_response_content += processed_event.content
                yield processed_event

        self.chat_session.add_conversation_message('assistant', full_response_content)

        end_time = time.time()
        latency = end_time - start_time
        completion_tokens = self.chat_session.count_tokens(full_response_content)
        usage = {
            "prompt_tokens": prompt_tokens, 
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens
        }
        yield StatsUpdate(latency=latency, usage=usage)

