#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# chat_module.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260204
# Version: 2.0.0

import time
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
    def __init__(
        self, 
        client: OpenAI, 
        config: configparser.ConfigParser,
        history_file: str, # @zhu, 20260205, [mark] history_file exist should be comfirm by above layer
    ):
        # @zhu, 20260205, [refactor] inject config
        self.client = client
        self.model = config['LLM'].get('model', 'local-model')
        self.max_history_length = config['LLM'].getint('max_history_length', 10)
        # @zhu, 20260205, [note] init content
        self.system_prompt ={
            "role": "system", 
            "content": get_system_prompt()
        }
        self.chat_history = []
        self.history_file = history_file
        # @zhu, 20260205, [note] mark other status value
        self.file_contexts = {} # To store content of read files
        
        # @zhu, 20260205, [note] init tokenizer
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            self.tokenizer = None
            logger.warning(f"Failed to load tokenizer: {e}")
        
        # @zhu, 20260205, [note] log success message
        logger.info("ChatSession initialized.")
    
    def add_conversation_message(
        self,
        role: str,
        content: str
    ):
        """
        Get content from user or assistant.
        """
        if role not in ['user', 'assistant']:
            return
        # @zhu, 20260205,[add] add content to chat history
        message = {
            "role": role,
            "content": content,
            "timestamp": time.time()
            # @zhu, 20260205, [mark] more content for further
        }
        self.write_message(message)
        self.chat_history.append(message)
        while len(self.chat_history) > self.max_history_length:
            old_message = self.chat_history.pop(0)
            logger.debug(f"Removed message: {old_message}")
        return message

    def write_message(self, message: dict):
        """
        Write message to file.
        """
        try:
            with open(self.history_file, 'a', encoding='utf-8') as f:
                json.dump(message, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to write message: {e}")

    def build_prompt(self):
        """Build full prompt for llm"""
        return [self.system_prompt] + self.chat_history

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text)) if self.tokenizer else 0

    def call_llm(self)-> tuple:
        """
        Calls the LLM with the current history and returns the raw stream, prompt tokens, and start time.
        ---
        
        return:
            `(stream, prompt_tokens, start_time)`
        """
        prompt = self.build_prompt()

        prompt_tokens = self.count_tokens(
            "\n"
            .join(m['content'] for m in prompt)
        )

        start_time = time.time()
        
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=prompt,
            stream=True,
        )
        return stream, prompt_tokens, start_time
