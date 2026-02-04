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
    def __init__(self, chat_session: ChatSession):
        self.chat_session = chat_session

    def run(self, user_content: str, files: list | None = None):
        """
        Runs the main ReAct loop for one turn of conversation.
        """
        if user_content:
            self.chat_session.add_user_message(user_content)
        if files:
            for file_path in files:
                tool_result = read_file(
                    base_dir=self.chat_session.base_dir, path=file_path,
                    max_file_size_kb=10240, max_output_tokens=500, # Use config values later
                    tokenizer=self.chat_session.tokenizer
                )
                if tool_result["success"]:
                    self.chat_session.add_system_message(f"User uploaded file '{os.path.basename(file_path)}'. Content is now in context.")
                    self.chat_session.file_contexts[file_path] = tool_result["content"]
                else:
                    yield TextChunk(content=f"\n[Error reading file {file_path}: {tool_result['error']}]")

        max_react_loops = 5
        for i in range(max_react_loops):
            logger.debug(f"Agent ReAct loop iteration {i+1}/{max_react_loops}")

            raw_stream, prompt_tokens, start_time = self.chat_session.call_llm()
            event_stream = parse_stream(raw_stream)
            
            full_response_content = ""
            tool_called = False

            for event in event_stream:
                if isinstance(event, FileReadRequest):
                    tool_called = True
                    logger.info(f"Agent received FileReadRequest for: {event.path}")
                    self.chat_session.add_assistant_message(full_response_content + f'<read_file path="{event.path}" />')
                    
                    tool_result = read_file(
                        base_dir=self.chat_session.base_dir, path=event.path,
                        max_file_size_kb=10240, max_output_tokens=500, # Use config values later
                        tokenizer=self.chat_session.tokenizer
                    )
                    
                    if tool_result["success"]:
                        self.chat_session.add_system_message(f"Tool <read_file> executed successfully. You should now use the content to answer the user.")
                        self.chat_session.file_contexts[event.path] = tool_result["content"]
                    else:
                        self.chat_session.add_system_message(f"Tool <read_file> failed. Error: {tool_result['error']}")
                    break
                else:
                    if isinstance(event, TextChunk):
                        full_response_content += event.content
                    yield event
            
            if tool_called:
                continue

            self.chat_session.add_assistant_message(full_response_content)
            
            end_time = time.time()
            latency = end_time - start_time
            completion_tokens = self.chat_session.count_tokens(full_response_content)
            usage = {
                "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
            yield StatsUpdate(latency=latency, usage=usage)
            return

        logger.error("Max ReAct loops reached.")
        yield TextChunk(content="\n[Error: Agent reached maximum tool calls.]")