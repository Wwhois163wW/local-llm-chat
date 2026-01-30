#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# chat_module.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260130
# Version: 1.5.0

from openai import OpenAI
import configparser
import logging
import logging.config
import os
import time
from dataclasses import dataclass
import re
import tiktoken

from events import TextChunk, StatsUpdate, FileWriteStart, FileContentChunk, FileWriteEnd
from prompts import get_file_injection_prompt

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
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
                stream=True,
            )

            full_response_content = ""
            completion_tokens = 0
            buffer = ""
            in_file_write_block = False
            
            for chunk in stream:
                content = chunk.choices[0].delta.content or ""
                if not content:
                    continue
                buffer += content
                
                while True:
                    if not in_file_write_block:
                        start_tag_match = re.search(r'<write_file path="([^"]+)">', buffer)
                        if start_tag_match:
                            pre_tag_content = buffer[:start_tag_match.start()]
                            if pre_tag_content:
                                yield TextChunk(content=pre_tag_content)
                                full_response_content += pre_tag_content
                                if self.tokenizer:
                                    completion_tokens += len(self.tokenizer.encode(pre_tag_content))
                            file_path = start_tag_match.group(1)
                            yield FileWriteStart(path=file_path)
                            buffer = buffer[start_tag_match.end():]
                            in_file_write_block = True
                        else:
                            # In normal text mode, yield content line by line or if buffer gets large
                            # to ensure responsiveness, but keep a small tail to avoid splitting a tag.
                            yield_boundary = buffer.rfind('\n')
                            if yield_boundary == -1 and len(buffer) > 100: # Force yield if buffer is large
                                yield_boundary = len(buffer) - 20

                            if yield_boundary != -1:
                                content_to_yield = buffer[:yield_boundary]
                                yield TextChunk(content=content_to_yield)
                                full_response_content += content_to_yield
                                if self.tokenizer:
                                    completion_tokens += len(self.tokenizer.encode(content_to_yield))
                                buffer = buffer[yield_boundary:]
                            break # Break inner loop to get more chunks
                    
                    if in_file_write_block:
                        end_tag_match = re.search(r'</write_file>', buffer)
                        if end_tag_match:
                            file_content_chunk = buffer[:end_tag_match.start()]
                            if file_content_chunk:
                                yield FileContentChunk(content=file_content_chunk)
                                full_response_content += file_content_chunk
                                if self.tokenizer:
                                    completion_tokens += len(self.tokenizer.encode(file_content_chunk))
                            yield FileWriteEnd()
                            buffer = buffer[end_tag_match.end():]
                            in_file_write_block = False
                        else:
                            # Not enough data to find the end tag, wait for more
                            break
            
            # After the loop, yield any remaining content
            if buffer:
                if in_file_write_block:
                    logger.warning("Stream ended with an unclosed <write_file> tag.")
                    yield FileContentChunk(content=buffer)
                else:
                    yield TextChunk(content=buffer)
                full_response_content += buffer
                if self.tokenizer:
                    completion_tokens += len(self.tokenizer.encode(buffer))

            logger.debug("OpenAI stream finished.")
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

if __name__ == '__main__':
    from api_client import Get_LLM_Client_by_Config
    from logging_setup import get_logging_config

    logging.config.dictConfig(get_logging_config(log_dir='.', log_level='DEBUG'))
    config = configparser.ConfigParser()
    script_dir = os.path.dirname(__file__)
    config_path = os.path.join(script_dir, 'config.ini')
    if not os.path.exists(config_path):
        logger.error("config.ini not found")
    config.read(config_path)

    if config.has_section('LLM'):
        llm_client = Get_LLM_Client_by_Config(config)
        if llm_client:
            chat_session = ChatSession(llm_client, config)
            logger.info("--- Message 1 ---")
            question1 = "My name is aigniter. What is your name?"
            logger.info(f"> {question1}")
            print("LLM > ", end="", flush=True)
            final_stats1 = None
            for event in chat_session.send_message(question1):
                if isinstance(event, TextChunk):
                    print(event.content, end="", flush=True)
                elif isinstance(event, StatsUpdate):
                    final_stats1 = event
            print(f"\nStats: {final_stats1}\n")

            logger.info("--- Message 2 ---")
            question2 = "Do you remember my name?"
            logger.info(f"> {question2}")
            print("LLM > ", end="", flush=True)
            final_stats2 = None
            for event in chat_session.send_message(question2):
                if isinstance(event, TextChunk):
                    print(event.content, end="", flush=True)
                elif isinstance(event, StatsUpdate):
                    final_stats2 = event
            print(f"\nStats: {final_stats2}\n")
    else:
        logger.error("Config file is missing [LLM] section.")