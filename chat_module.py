#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# chat_module.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260204
# Version: 2.0.0

import time
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
    """
    def __init__(self, client: OpenAI, config: configparser.ConfigParser, base_dir: str):
        self.client = client
        self.model = config['LLM'].get('model', 'local-model')
        self.max_history_length = config['LLM'].getint('max_history_length', 10)
        self.history = [{"role": "system", "content": get_system_prompt()}]
        self.base_dir = base_dir
        self.file_contexts = {} # To store content of read files
        
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            self.tokenizer = None
            logger.warning(f"Failed to load tokenizer: {e}")
        
        logger.info("ChatSession initialized.")

    def add_user_message(self, content: str):
        self.history.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str):
        self.history.append({"role": "assistant", "content": content})
    
    def add_system_message(self, content: str):
        self.history.append({"role": "system", "content": content})

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text)) if self.tokenizer else 0

    def call_llm(self):
        """
        Calls the LLM with the current history and returns the raw stream, prompt tokens, and start time.
        """
        if len(self.history) > self.max_history_length:
            self.history = [self.history[0]] + self.history[-(self.max_history_length-1):]
        
        prompt_tokens = self.count_tokens("\n".join(m['content'] for m in self.history))
        start_time = time.time()
        
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
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def load_history(self, file_path: str):
        if not os.path.exists(file_path): return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.history = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load history: {e}")
