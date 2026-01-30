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
import re
import tiktoken

from events import TextChunk, StatsUpdate, FileWriteStart, FileContentChunk, FileWriteEnd
from prompts import get_file_injection_prompt

logger = logging.getLogger(__name__)

# ... (rest of the class is the same)

# In send_message method:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            file_content = f.read()
                        
                        file_name = os.path.basename(file_path)
                        # Default prompt template for file injection
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
                
                while True: # Loop to process buffer continuously
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
                            # No start tag found, nothing more to process in the buffer for now
                            break
                    
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
                            # No end tag found yet in the buffer
                            break
                
            # After the stream, process any text left in the buffer that wasn't part of a tag
            if buffer and not in_file_write_block:
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
