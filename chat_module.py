#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# chat_module.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260130
# Version: 1.4.0

from openai import OpenAI
import configparser
import logging
import logging.config
import os
import time
from dataclasses import dataclass
import re # @Antigravity, 20260130, [ADD]: Import for tag parsing
import tiktoken

@dataclass
class TextChunk:
    content: str

@dataclass
class StatsUpdate:
    latency: float
    usage: dict

@dataclass
class FileWriteStart:
    path: str

@dataclass
class FileContentChunk:
    content: str

@dataclass
class FileWriteEnd:
    pass

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
        """
        Sends a user message to the LLM and yields events for streaming output.
        
        Args:
            user_content (str): The user's input message.
            files (list, optional): A list of file paths to inject into the context.
        
        Yields:
            Event objects (e.g., TextChunk, StatsUpdate) representing the stream.
        """
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
                        file_injection_prompt = (
                            f"The following is the content of the file '{file_name}', please read it carefully:\n\n"
                            f"```\n{file_content}\n```\n\n"
                            f"Once read, you can proceed with the user's main query."
                        )
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
            
            # @Antigravity, 20260130, [ADD]: State machine for parsing tagged language
            buffer = ""
            in_file_write_block = False
            
            for chunk in stream:
                content = chunk.choices[0].delta.content or ""
                if not content:
                    continue

                buffer += content
                
                # Process buffer line by line or by tag boundaries
                while True:
                    if not in_file_write_block:
                        start_tag_match = re.search(r'<write_file path="([^"]+)">', buffer)
                        if start_tag_match:
                            # Content before the tag is a normal text chunk
                            pre_tag_content = buffer[:start_tag_match.start()]
                            if pre_tag_content:
                                yield TextChunk(content=pre_tag_content)
                                full_response_content += pre_tag_content
                                if self.tokenizer:
                                    completion_tokens += len(self.tokenizer.encode(pre_tag_content))

                            # Yield the start of file writing
                            file_path = start_tag_match.group(1)
                            yield FileWriteStart(path=file_path)
                            
                            # Update state and buffer
                            buffer = buffer[start_tag_match.end():]
                            in_file_write_block = True
                        else:
                            # No start tag found, yield all but the last part of the buffer
                            # to avoid splitting a tag in the middle
                            last_newline = buffer.rfind('\n')
                            if last_newline != -1:
                                content_to_yield = buffer[:last_newline+1]
                                yield TextChunk(content=content_to_yield)
                                full_response_content += content_to_yield
                                if self.tokenizer:
                                    completion_tokens += len(self.tokenizer.encode(content_to_yield))
                                buffer = buffer[last_newline+1:]
                            break # Wait for more content
                    
                    if in_file_write_block:
                        end_tag_match = re.search(r'</write_file>', buffer)
                        if end_tag_match:
                            # Content before the end tag is file content
                            file_content_chunk = buffer[:end_tag_match.start()]
                            if file_content_chunk:
                                yield FileContentChunk(content=file_content_chunk)
                                full_response_content += file_content_chunk # Also add to history
                                if self.tokenizer:
                                    completion_tokens += len(self.tokenizer.encode(file_content_chunk))
                            
                            # Yield the end of file writing
                            yield FileWriteEnd()
                            
                            # Update state and buffer
                            buffer = buffer[end_tag_match.end():]
                            in_file_write_block = False
                        else:
                            # No end tag yet, yield the buffer as file content chunk
                            if buffer:
                                yield FileContentChunk(content=buffer)
                                full_response_content += buffer
                                if self.tokenizer:
                                    completion_tokens += len(self.tokenizer.encode(buffer))
                                buffer = ""
                            break # Wait for more content

            # After the loop, yield any remaining content in the buffer
            if buffer:
                if in_file_write_block: # Should not happen if LLM is well-behaved
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
                "prompt_tokens": prompt_tokens, 
                "completion_tokens": completion_tokens, 
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
        logger.error("config.ini not found, please create it from config.example.ini")
    config.read(config_path)

    if not config.has_section('LLM'):
        logger.error("Config file is missing [LLM] section.")
    else:
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

            logger.info(f"Current history length: {len(chat_session.history)}")
            logger.debug(f"Full history: {chat_session.history}")
