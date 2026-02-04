#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# chat_module.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260203
# Version: 1.7.9

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
        self.file_contexts = {} # Correctly store file contents outside of history

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
        
        # This is for the /add command, which injects content directly
        if files:
            for file_path in files:
                # For /add, we still want to inject the content for the LLM to see
                tool_response = self._execute_read_file(file_path, inject_content=True)
                self.history.append({"role": "system", "content": tool_response})

        self.history.append({"role": "user", "content": user_content})

        max_react_loops = 5
        for i in range(max_react_loops):
            logger.debug(f"ReAct loop iteration {i+1}/{max_react_loops}. History length: {len(self.history)}")
            
            if i > 0:
                self.history.append({
                    "role": "system",
                    "content": "You have already called a tool. Review the tool's output and provide a final answer to the user. Do not call any more tools unless absolutely necessary."
                })

            if len(self.history) > self.max_history_length:
                self.history = [self.history[0]] + self.history[-(self.max_history_length-1):]
                logger.debug(f"History trimmed to the last {self.max_history_length} messages.")

            prompt_tokens = 0
            if self.tokenizer:
                for message in self.history:
                    prompt_tokens += len(self.tokenizer.encode(message.get('content', '')))
            
            start_time = time.time()
            try:
                raw_stream = self.client.chat.completions.create(
                    model=self.model, messages=self.history, stream=True,
                )
            except Exception as e:
                logger.error(f"Error during API call: {e}")
                self.last_errors.append(f"API Error: {e}")
                return # Stop generation

            event_stream = parse_stream(raw_stream)
            
            full_response_content = ""
            completion_tokens = 0
            tool_called = False

            for event in event_stream:
                if isinstance(event, (TextChunk, FileContentChunk)):
                    full_response_content += event.content
                
                if isinstance(event, FileReadRequest):
                    tool_called = True
                    logger.info(f"LLM requested to read file: {event.path}")
                    # For ReAct, we do NOT inject the content back, only a confirmation.
                    tool_response_content = self._execute_read_file(event.path, store_content=True) # store_content is now correct
                    
                    assistant_response = full_response_content + f'<read_file path="{event.path}" />'
                    self.history.append({"role": "assistant", "content": assistant_response})
                    self.history.append({"role": "system", "content": tool_response_content})
                    break 
                
                yield event

            if tool_called:
                continue 

            logger.debug("Stream parsing finished, no tool call detected.")
            end_time = time.time()
            self.history.append({"role": "assistant", "content": full_response_content})

            if self.tokenizer:
                completion_tokens = len(self.tokenizer.encode(full_response_content))
            latency = end_time - start_time
            usage = {
                "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
            yield StatsUpdate(latency=latency, usage=usage)
            return

        logger.error("Max ReAct loops reached. Aborting.")
        self.last_errors.append("Error: Too many nested tool calls. The agent may be in a loop.")

    def _execute_read_file(self, path: str, store_content: bool = False, inject_content: bool = False) -> str:
        """
        Executes the read_file tool call.
        If store_content is True, reads and stores file content in self.file_contexts.
        If inject_content is True, returns a string with the file content (for /add).
        Otherwise, returns only a success/failure message (for ReAct).
        """
        supported_extensions = ['.txt', '.md', '.py', '.json', '.csv', '.xml', '.html']
        
        try:
            # ... (Path safety checks remain the same)
            safe_base_dir = os.path.abspath(os.path.dirname(__file__))
            target_path = os.path.abspath(os.path.join(safe_base_dir, path))
            
            output_dir = os.path.abspath(os.path.join(safe_base_dir, 'output'))
            logs_dir = os.path.abspath(os.path.join(safe_base_dir, 'logs'))
            
            is_in_safe_dir = target_path.startswith(safe_base_dir) or \
                              target_path.startswith(output_dir) or \
                              target_path.startswith(logs_dir)

            if not is_in_safe_dir:
                return f"Tool <read_file> failed: Path traversal attempt detected. Access is restricted."

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
            
            if inject_content:
                if self.tokenizer and self.max_read_file_output_tokens > 0:
                    encoded_content = self.tokenizer.encode(content)
                    if len(encoded_content) > self.max_read_file_output_tokens:
                        truncated_content = self.tokenizer.decode(encoded_content[:self.max_read_file_output_tokens])
                        return f"File '{os.path.basename(path)}' content (truncated) is now in context."
                return f"File '{os.path.basename(path)}' content is now in context."
            else: # For ReAct loop, just confirm success.
                return f"Tool <read_file> successfully read file '{os.path.basename(path)}'. Its content is now available in your context."
        except Exception as e:
            logger.error(f"An unexpected exception occurred in _execute_read_file: {e}")
            return f"Tool <read_file> failed with an internal error: {e}"
