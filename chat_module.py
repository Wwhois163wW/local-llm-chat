#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# chat_module.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260204
# Version: 1.8.3

from openai import OpenAI
import configparser
import logging
import logging.config
import os
import time
import json
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
        
        # This is for the /add command, which injects content directly
        if files:
            for file_path in files:
                # For /add, we read the file and store it, then inject a confirmation into history
                tool_result_msg = self._execute_read_file(file_path, store_content=True)
                self.history.append({"role": "system", "content": tool_result_msg})

        self.history.append({"role": "user", "content": user_content})

        react_loop_count = 0
        final_assistant_response_content = ""
        final_prompt_tokens = 0
        final_completion_tokens = 0
        total_latency = 0
        
        # --- Start ReAct loop ---
        while react_loop_count < 5: # Max 5 ReAct iterations
            react_loop_count += 1
            logger.debug(f"ReAct loop iteration {react_loop_count}/5. Base history length: {len(self.history)}")

            # Build messages for current LLM call, including only relevant tool calls and responses
            current_messages = []
            
            # 1. System Prompt (always first)
            current_messages.append(self.history[0])
            
            # 2. Add core dialogue history (trimmed)
            dialogue_history = self.history[1:] # Exclude the fixed system prompt
            if len(dialogue_history) > self.max_history_length:
                dialogue_history = dialogue_history[-(self.max_history_length):]
            current_messages.extend(dialogue_history)

            # 3. If it's a subsequent tool call attempt, inject a forceful instruction
            if react_loop_count > 1:
                current_messages.append({
                    "role": "system",
                    "content": "You have already attempted a tool call. Review the tool's output provided in the history and provide a final answer to the user. Do not call any more tools unless absolutely necessary. Focus on replying to the user."
                })
            
            # Calculate prompt tokens for current call
            current_prompt_tokens = 0
            if self.tokenizer:
                for message in current_messages:
                    current_prompt_tokens += len(self.tokenizer.encode(message.get('content', '')))
            
            start_time = time.time()
            try:
                raw_stream = self.client.chat.completions.create(
                    model=self.model, messages=current_messages, stream=True,
                )
            except Exception as e:
                logger.error(f"Error during API call: {e}")
                self.last_errors.append(f"API Error: {e}")
                break # Exit ReAct loop due to API error

            # --- Parse events from LLM response ---
            event_stream = parse_stream(raw_stream)
            
            loop_full_response_content = ""
            tool_called_in_this_loop = False
            
            for event in event_stream:
                if isinstance(event, (TextChunk, FileWriteStart, FileContentChunk, FileWriteEnd)):
                    # These are direct outputs to the user or file writes
                    yield event
                    if isinstance(event, (TextChunk, FileContentChunk)):
                        loop_full_response_content += event.content
                
                elif isinstance(event, FileReadRequest):
                    tool_called_in_this_loop = True
                    logger.info(f"LLM requested to read file: {event.path}")
                    
                    # Execute the tool, which stores content in self.file_contexts
                    tool_result_msg = self._execute_read_file(event.path, store_content=True)
                    
                    # Add LLM's full response (including tool call) and tool's result to history for next iteration
                    self.history.append({"role": "assistant", "content": loop_full_response_content + f'<read_file path="{event.path}" />'})
                    self.history.append({"role": "system", "content": tool_result_msg})
                    break # Break from event loop to start next ReAct iteration
            
            # If no tool was called, the conversation is finished for this turn
            if not tool_called_in_this_loop:
                final_assistant_response_content = loop_full_response_content
                self.history.append({"role": "assistant", "content": final_assistant_response_content})
                break # Exit ReAct loop

            end_time = time.time()
            total_latency += (end_time - start_time)
            # Accumulate tokens only for successful API calls
            final_prompt_tokens += current_prompt_tokens
            final_completion_tokens += (len(self.tokenizer.encode(loop_full_response_content)) if self.tokenizer else 0)

        # --- ReAct loop finished or max loops reached ---
        if react_loop_count >= 5 and tool_called_in_this_loop: # Check if loop was cut short due to max_react_loops
            logger.error("Max ReAct loops reached. Agent may be in a loop.")
            self.last_errors.append("Error: Too many nested tool calls. The agent may be in a loop.")
            # Inject a final message to history so LLM knows it was cut off
            self.history.append({"role": "system", "content": "The agent attempted too many tool calls and was cut off. Provide a summary of the situation."})
            final_assistant_response_content = "I'm sorry, I've reached the maximum number of tool calls for this turn. I couldn't complete your request."
        
        # Yield final stats
        if final_assistant_response_content: # Only yield stats if we have a final response to user
            usage = {
                "prompt_tokens": final_prompt_tokens, "completion_tokens": final_completion_tokens,
                "total_tokens": final_prompt_tokens + final_completion_tokens
            }
            yield StatsUpdate(latency=total_latency, usage=usage)
        
    def save_history(self, file_path: str):
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
            logger.info(f"Conversation history saved to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save history to {file_path}: {e}")

    def load_history(self, file_path: str):
        if not os.path.exists(file_path):
            logger.info("No history file found to load.")
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                loaded_history = json.load(f)
            
            if isinstance(loaded_history, list) and all(isinstance(i, dict) for i in loaded_history):
                # Keep the initial system prompt, append the rest
                self.history = [self.history[0]] + loaded_history[1:] if loaded_history else [self.history[0]]
                logger.info(f"Conversation history loaded from {file_path}")
            else:
                logger.warning(f"History file {file_path} has invalid format. Skipping load.")
        except Exception as e:
            logger.error(f"Failed to load history from {file_path}: {e}")

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
            
            allowed_dirs = [safe_base_dir, os.path.join(safe_base_dir, 'output'), os.path.join(safe_base_dir, 'logs')]
            if not any(target_path.startswith(d) for d in allowed_dirs):
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
            
            return f"Tool <read_file> successfully read file '{os.path.basename(path)}'. Its content is now available in your context."
        except Exception as e:
            logger.error(f"An unexpected exception occurred in _execute_read_file: {e}")
            return f"Tool <read_file> failed with an internal error: {e}"