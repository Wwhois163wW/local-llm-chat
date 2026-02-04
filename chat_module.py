#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# chat_module.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260204
# Version: 1.9.0

import os
import json
import logging
import configparser
import tiktoken
from openai import OpenAI

from prompts import get_system_prompt

logger = logging.getLogger(__name__)

class ChatSession:
    """
    Manages the conversation history and provides a simple interface to call the LLM.
    It is now a stateful but passive component, orchestrated by the Agent.
    """
    def __init__(self, client: OpenAI, config: configparser.ConfigParser, base_dir: str):
        if not client:
            raise ValueError("OpenAI client must be initialized.")
        self.client = client
        self.model = config['LLM'].get('model', 'local-model')
        self.max_history_length = config['LLM'].getint('max_history_length', 10)
        self.history = [
            {"role": "system", "content": get_system_prompt()}
        ]
        self.base_dir = base_dir # For resolving file paths safely
        
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.warning(f"Failed to initialize tiktoken: {e}")
            self.tokenizer = None
        
        logger.info("ChatSession initialized.")

    def add_user_message(self, content: str):
        self.history.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str):
        self.history.append({"role": "assistant", "content": content})
    
    def add_system_message(self, content: str):
        self.history.append({"role": "system", "content": content})

    def count_tokens(self, text: str) -> int:
        if not self.tokenizer:
            return 0
        return len(self.tokenizer.encode(text))

    def call_llm(self):
        """
        Calls the LLM with the current history and returns the raw stream.
        """
        # Trim history before making the call
        if len(self.history) > self.max_history_length:
            self.history = [self.history[0]] + self.history[-(self.max_history_length-1):]
        
        prompt_tokens = self.count_tokens("\n".join(m['content'] for m in self.history))
        start_time = time.time()
        
        logger.debug(f"Calling LLM with history of length {len(self.history)}")
        
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=self.history,
            stream=True,
        )
        return stream, prompt_tokens, start_time

    def save_history(self, file_path: str):
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
            logger.info(f"Conversation history saved to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def load_history(self, file_path: str):
        if not os.path.exists(file_path):
            return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                loaded_history = json.load(f)
            if isinstance(loaded_history, list) and all(isinstance(i, dict) for i in loaded_history):
                self.history = loaded_history
                logger.info(f"Conversation history loaded from {file_path}")
        except Exception as e:
            logger.error(f"Failed to load history: {e}")