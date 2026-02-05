#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# chat_module.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260205
# Version: 2.0.2

import time
import json
import logging
import configparser
import tiktoken
from openai import OpenAI
import os

from prompts import get_system_prompt

logger = logging.getLogger(__name__)

class ChatSession:
    def __init__(
        self,
        client: OpenAI,
        config: configparser.ConfigParser,
        history_file: str,
    ):
        self.client = client
        self.model = config['LLM'].get('model', 'local-model')
        self.max_history_length = config.getint('LLM', 'max_history_length', fallback=10)
        
        self.system_prompt ={
            "role": "system", 
            "content": get_system_prompt()
        }
        self.chat_history = []
        self.history_file = history_file
        
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            self.tokenizer = None
            logger.warning(f"Failed to load tokenizer: {e}")
        
        self._load_conversation_memory_from_file()
        logger.info("ChatSession initialized.")
    
    def add_conversation_message(self, role: str, content: str):
        if role not in ['user', 'assistant']:
            logger.warning(f"Invalid role '{role}' for conversation message.")
            return

        message = { "role": role, "content": content, "timestamp": time.time() }
        self._write_message(message)
        self.chat_history.append(message)
        
        while len(self.chat_history) > self.max_history_length:
            self.chat_history.pop(0)

    def _write_message(self, message: dict):
        try:
            with open(self.history_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(message, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"Failed to write message: {e}")

    def _load_conversation_memory_from_file(self):
        if not os.path.exists(self.history_file): return
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            start_index = max(0, len(lines) - self.max_history_length)
            for line in lines[start_index:]:
                if line.strip():
                    message = json.loads(line)
                    if message.get('role') in ['user', 'assistant']:
                        self.chat_history.append(message)
        except Exception as e:
            logger.error(f"Failed to load history: {e}")

    def build_prompt(self):
        return [self.system_prompt] + self.chat_history

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text)) if self.tokenizer else 0

    async def call_llm(self)-> tuple:
        prompt = self.build_prompt()
        prompt_tokens = self.count_tokens("\n".join(m.get('content', '') for m in prompt))
        start_time = time.time()
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=prompt,
            stream=True,
        )
        return stream, prompt_tokens, start_time
