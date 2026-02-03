#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# chat_module.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260203
# Version: 1.6.0

from openai import OpenAI
import configparser
import logging
import logging.config
import os
import time
import tiktoken

from events import TextChunk, StatsUpdate
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
        
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.warning(f"Failed to initialize tiktoken, token counts will be 0: {e}")
            self.tokenizer = None
            
        system_prompt = get_system_prompt()
        self.history.append({"role": "system", "content": system_prompt})
            
        logger.info(
            f"ChatSession initialized. Max history: {self.max_history_length}, Max file size: {self.max_file_size_kb} KB"
        )
        
    def send_message(self, user_content: str, files: list|None = None):
        logger.debug("send_message stream started.")
        try:
            self.last_errors.clear()
            injected_file_messages = []
            if files:
                logger.debug(f"Processing {len(files)} files for injection.")
                for file_path in files:
                    if not os.path.exists(file_path):
                        self.last_errors.append(f"File not found, skipped: {file_path}")
                        continue
                    try:
                        file_size_kb = os.path.getsize(file_path) / 1024
                        if file_size_kb > self.max_file_size_kb:
                            self.last_errors.append(f"File '{os.path.basename(file_path)}' is too large ({file_size_kb:.1f} KB > {self.max_file_size_kb} KB), skipped.")
                            continue
                        with open(file_path, 'r', encoding='utf-8') as f:
                            file_content = f.read()
                        file_name = os.path.basename(file_path)
                        file_injection_prompt = get_file_injection_prompt(file_name, file_content)
                        injected_file_messages.append({"role": "user", "content": file_injection_prompt})
                        logger.info(f"Injected file '{file_name}' content to history.")
                    except Exception as e:
                        self.last_errors.append(f"Failed to read file '{os.path.basename(file_path)}': {e}")

            self.history.extend(injected_file_messages)
            self.history.append({"role": "user", "content": user_content})
            logger.debug(f"History prepared for API call. Length: {len(self.history)}")

            if len(self.history) > self.max_history_length:
                self.history = self.history[-self.max_history_length:]
                logger.debug(f"History trimmed to the last {self.max_history_length} messages.")

            prompt_tokens = 0
            if self.tokenizer:
                for message in self.history:
                    prompt_tokens += len(self.tokenizer.encode(message['content']))

            start_time = time.time()
            logger.debug("Calling OpenAI API with stream=True...")
            raw_stream = self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
                stream=True,
            )

            event_stream = parse_stream(raw_stream)
            
            full_response_content = ""
            completion_tokens = 0

            for event in event_stream:
                if isinstance(event, TextChunk):
                    full_response_content += event.content
                    if self.tokenizer:
                        completion_tokens += len(self.tokenizer.encode(event.content))
                
                yield event
            
            logger.debug("Stream parsing finished.")
            end_time = time.time()
            self.history.append({"role": "assistant", "content": full_response_content})

            latency = end_time - start_time
            usage = {
                "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
            yield StatsUpdate(latency=latency, usage=usage)

        except Exception as e:
            logger.error(f"Error during API stream: {e}")
            if self.history:
                messages_added_this_turn = 1 + len(injected_file_messages)
                for _ in range(messages_added_this_turn):
                    if self.history and self.history[-1]["role"] == "user":
                        self.history.pop()
                    else:
                        break