#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# agent.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260204
# Version: 1.1.0

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
        self.debug_mode = debug_mode # @zhu, 20260205, [mark] read from config.ini

    async def _handle_event(self, event):
        # @zhu, 20260205, [add] handle event
        event_type_name = type(event).__name__.lower()
        
        # @zhu, 20260205, [note] query handler 
        handler_name = f'_handle_{event_type_name}'
        handler = getattr(self, handler_name, self._handle_default)
        
        if self.debug_mode:
            yield TextChunk(content=f"\n[DEBUG: Event -> {str(event)}]\n")

        # @zhu, 20260205, [note] yield result event
        async for result_event in handler(event):
            yield result_event

    async def _handle_textchunk(self, event):
        """
        Handle text chunk event.
        """
        yield event

    async def _handle_default(self, event):
        # @zhu, 20260205, [add] handle default event
        logger.warning(f"Unhandled event type: {type(event).__name__}")
        yield TextChunk(
            content=f"[Agent: Received an unhandled event: {str(event)}]"
        )

    async def run(self):
        """
        Runs the main ReAct loop for one turn of conversation.
        """
        # @zhu, 20260205, [note] store agent work track
        full_response_content = ""
        
        # @zhu, 20260205, [note] call llm
        stream, prompt_tokens, start_time = await self.chat_session.call_llm()
        event_stream = parse_stream(stream)

        # @zhu, 20260205, [note] handle event
        async for event in event_stream:
            async for processed_event in self._handle_event(event):
                full_response_content += event.content
                yield processed_event

        # @zhu, 20260205, [note] refresh chat history
        self.chat_session.add_conversation_message('assistant', full_response_content)

        # @zhu, 20260205, [note] calculate usage
        end_time = time.time()
        latency = end_time - start_time
        completion_tokens = self.chat_session.count_tokens(full_response_content)
        usage = {
            "prompt_tokens": prompt_tokens, 
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens
        }
        yield StatsUpdate(latency=latency, usage=usage)

        pass