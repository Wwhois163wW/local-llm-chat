#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# chat_module.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260204
# Version: 1.8.0

from openai import OpenAI
import configparser
import logging
import logging.config
import os
import time
import tiktoken

from events import TextChunk, StatsUpdate, FileReadRequest, FileContentChunk, FileWriteEnd
from prompts import get_file_injection_prompt, get_system_prompt
from parser import parse_stream

logger = logging.getLogger(__name__)

class ChatSession:
    """Manages a single, stateful conversation with the LLM, including history."""
    def __init__(self, client: OpenAI, config: configparser.ConfigParser):
        if not client:
            raise ValueError("OpenAI client must be initialized.")
        self.client = client
        self.model = config['LLM'].get('model', 'local-model')
        self.max_history_length = config['LLM'].getint('max_history_length', 10)
        self.max_file_size_kb = config['LLM'].getint('max_file_size_kb', 10240)
        self.history = []
        self.last_errors = []
        self.file_contexts = {}

        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.warning(f"Failed to initialize tiktoken, token counts will be 0: {e}")
            self.tokenizer = None
            
        system_prompt = get_system_prompt()
        self.history.append({"role": "system", "content": system_prompt})
        
        self.max_read_file_output_tokens = config['LLM'].getint('max_read_file_output_tokens', 500)
            
        logger.info(
            f"ChatSession initialized. Max history: {self.max_history_length}, Max file size: {self.max_file_size_kb} KB, Max read output tokens: {self.max_read_file_output_tokens}"
        )
        
    def send_message(self, user_content: str, files: list|None = None):
        self.last_errors.clear()
        
        # Initial context setup from user's /add command
        if files:
            for file_path in files:
                # For /add, we read the file and store it, then inject a confirmation into history
                tool_result_msg = self._execute_read_file(file_path, store_content=True)
                self.history.append({"role": "system", "content": tool_result_msg})

        self.history.append({"role": "user", "content": user_content})

        max_react_loops = 5
        for i in range(max_react_loops):
            logger.debug(f"ReAct loop iteration {i+1}/{max_react_loops}. History length: {len(self.history)}")
            
            # --- API Call ---
            try:
                raw_stream = self.client.chat.completions.create(
                    model=self.model, messages=self.history, stream=True,
                )
            except Exception as e:
                logger.error(f"Error during API call: {e}")
                self.last_errors.append(f"API Error: {e}")
                return

            # --- Event Parsing and Tool Handling ---
            event_stream = parse_stream(raw_stream)
            
            full_response_content = ""
            tool_called = False
            
            for event in event_stream:
                if isinstance(event, TextChunk):
                    full_response_content += event.content
                    yield event # Yield text immediately to UI
                
                elif isinstance(event, FileReadRequest):
                    tool_called = True
                    logger.info(f"LLM requested to read file: {event.path}")
                    # The assistant's thought process (text before the tool call) is part of the response
                    self.history.append({"role": "assistant", "content": full_response_content + f'<read_file path="{event.path}" />'})
                    
                    # Execute the tool, which stores the content in self.file_contexts
                    tool_result_msg = self._execute_read_file(event.path, store_content=True)
                    
                    # Inject a clean confirmation message into history for the next LLM call
                    self.history.append({"role": "system", "content": tool_result_msg})
                    break
                
                # For other events like <write_file>, just pass them on for now
                else:
                    yield event

            if tool_called:
                continue # Go to the next iteration of the ReAct loop

            # --- Final Response Generation (if no tool was called) ---
            logger.debug("Stream parsing finished, no tool call detected.")
            self.history.append({"role": "assistant", "content": full_response_content})

            # Calculate and yield final stats
            end_time = time.time() # This is not accurate, but a placeholder
            prompt_tokens = 0
            completion_tokens = 0
            if self.tokenizer:
                for message in self.history[:-1]: # Exclude the latest assistant response
                    prompt_tokens += len(self.tokenizer.encode(message.get('content', '')))
                completion_tokens = len(self.tokenizer.encode(full_response_content))
            
            latency = time.time() - start_time
            usage = {
                "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
            yield StatsUpdate(latency=latency, usage=usage)
            return

        logger.error("Max ReAct loops reached. Aborting.")
        self.last_errors.append("Error: Too many nested tool calls. The agent may be in a loop.")

    def _execute_read_file(self, path: str, store_content: bool = False) -> str:
        """
        Executes the read_file tool call.
        If store_content is True, reads and stores file content in self.file_contexts.
        Returns a short, clean confirmation or error message for the LLM.
        """
        supported_extensions = ['.txt', '.md', '.py', '.json', '.csv', '.xml', '.html']
        
        try:
            safe_base_dir = os.path.abspath(os.path.dirname(__file__))
            target_path = os.path.abspath(os.path.join(safe_base_dir, path))
            
            # Allow reading from project root and specific subdirectories
            allowed_dirs = [safe_base_dir, os.path.join(safe_base_dir, 'output'), os.path.join(safe_base_dir, 'logs')]
            if not any(target_path.startswith(d) for d in allowed_dirs):
                return f"Tool <read_file> failed: Path traversal attempt detected."

            _, ext = os.path.splitext(target_path)
            if ext not in supported_extensions:
                return f"Tool <read_file> failed: File type '{ext}' is not supported."
            
            if not os.path.exists(target_path):
                return f"Tool <read_file> failed: File not found at path '{path}'."
            
            with open(target_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            file_size_kb = len(content.encode('utf-8')) / 1024
            if file_size_kb > self.max_file_size_kb:
                 return f"Tool <read_file> failed: File '{os.path.basename(path)}' is too large."

            if store_content:
                self.file_contexts[path] = content
                logger.info(f"Content of '{path}' stored in agent's context.")
            
            # Return a clean confirmation, NOT the content
            return f"Tool <read_file> successfully read file '{os.path.basename(path)}'."
        except Exception as e:
            logger.error(f"An unexpected exception occurred in _execute_read_file: {e}")
            return f"Tool <read_file> failed with an internal error: {e}"