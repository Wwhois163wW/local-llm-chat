#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# agent.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260204
# Version: 1.0.0

import logging
import time

from chat_module import ChatSession
from parser import parse_stream
from events import FileReadRequest, TextChunk, FileWriteStart, FileContentChunk, FileWriteEnd, StatsUpdate
from tools import read_file

logger = logging.getLogger(__name__)

class Agent:
    def __init__(self, chat_session: ChatSession):
        self.chat_session = chat_session

    def run(self, user_content: str, files: list | None = None):
        """
        Runs the main ReAct loop for one turn of conversation.
        """
        # Initial user request
        self.chat_session.add_user_message(user_content, files)

        max_react_loops = 5
        for i in range(max_react_loops):
            logger.debug(f"Agent ReAct loop iteration {i+1}/{max_react_loops}")

            if i > 0:
                self.chat_session.add_system_message("You have already called a tool. Review the tool's output and provide a final answer to the user.")

            raw_stream, prompt_tokens, start_time = self.chat_session.call_llm()
            event_stream = parse_stream(raw_stream)
            
            full_response_content = ""
            tool_called = False

            for event in event_stream:
                if isinstance(event, FileReadRequest):
                    tool_called = True
                    logger.info(f"Agent received FileReadRequest for: {event.path}")
                    
                    # Add assistant's thought process to history
                    self.chat_session.add_assistant_message(full_response_content + f'<read_file path="{event.path}" />')
                    
                    # Execute tool
                    tool_result = read_file(
                        base_dir=self.chat_session.base_dir,
                        path=event.path,
                        max_file_size_kb=self.chat_session.max_file_size_kb,
                        max_output_tokens=self.chat_session.max_read_file_output_tokens,
                        tokenizer=self.chat_session.tokenizer
                    )
                    
                    # Add tool result to history
                    if tool_result["success"]:
                        self.chat_session.add_system_message(f"Tool <read_file> executed successfully. {tool_result['content']}")
                    else:
                        self.chat_session.add_system_message(f"Tool <read_file> failed. Error: {tool_result['error']}")
                    break # Break event loop to start next ReAct iteration
                
                # For UI-related events, just yield them up
                else:
                    if isinstance(event, (TextChunk, FileContentChunk)):
                        full_response_content += event.content
                    yield event
            
            if tool_called:
                continue

            # If no tool was called, the loop is finished
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

        # If loop finishes due to max_react_loops
        logger.error("Max ReAct loops reached.")
        yield TextChunk(content="\n[Error: Agent reached maximum tool calls.]")
