#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# chat_module.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260129
# Version: 1.3.0

from openai import OpenAI
import configparser
import logging
import logging.config # @Antigravity, 20260129, [FIX]: Explicitly import logging.config
import os
import time # @Antigravity, 20260129, [ADD]: Import time for latency calculation
from dataclasses import dataclass

# @Antigravity, 20260130, [ADD]: Event classes for streaming architecture
@dataclass
class TextChunk:
    content: str

@dataclass
class StatsUpdate:
    latency: float
    usage: dict

logger = logging.getLogger(__name__)

class ChatSession:
    """
    Manages a single, stateful conversation with the LLM, including history.
    """
    def __init__(self, client: OpenAI, config: configparser.ConfigParser):
        """
        Initializes the chat session.

        Args:
            client (OpenAI): The OpenAI client instance.
            config (configparser.ConfigParser): The loaded configuration object.
        """
        if not client:
            raise ValueError("OpenAI client must be initialized.")
        self.client = client
        self.model = config['LLM'].get('model', 'local-model')
        # Use getint for integer conversion, with a fallback default of 10
        self.max_history_length = config['LLM'].getint('max_history_length', 10)
        self.max_file_size_kb = config['LLM'].getint('max_file_size_kb', 10240) # @Antigravity, 20260130, [ADD]: Load file size limit
        self.history = []
        self.last_errors = [] # @Antigravity, 20260130, [ADD]: List to hold non-critical errors for the UI
        logger.info(
            f"ChatSession initialized. Max history: {self.max_history_length}, Max file size: {self.max_file_size_kb} KB"
        )
        
    def send_message(self, user_content: str, files: list|None = None): # @Antigravity, 20260130, [MOD]: Add 'files' parameter
        """
        Sends a user message to the LLM and yields events for streaming output.

        Args:
            user_content (str): The user's input message.
            files (list, optional): A list of file paths to inject into the context. Defaults to None.
        
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

            start_time = time.time()
            logger.debug("Calling OpenAI API with stream=True...")
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
                stream=True,
            )

            full_response_content = ""
            for chunk in stream:
                content = chunk.choices[0].delta.content or ""
                if content:
                    full_response_content += content
                    yield TextChunk(content=content)
            
            logger.debug("OpenAI stream finished.")
            end_time = time.time()
            
            self.history.append({"role": "assistant", "content": full_response_content})

            latency = end_time - start_time
            # Note: The 'usage' field is typically not available in the final chunk of a stream.
            # We will use placeholder stats for now.
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            logger.warning("Token usage statistics are not available in streaming mode with this implementation.")
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
    # Example Usage
    from api_client import Get_LLM_Client_by_Config
    from logging_setup import get_logging_config

    # --- Setup Logging and Config for test ---
    # # logging.config.dictConfig(get_logging_config(log_level='INFO'))
    # @Antigravity, 20260129, [FIX]: Provide log_dir for logging config
    script_dir = os.path.dirname(__file__)
    log_dir = os.path.join(script_dir, 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    logging.config.dictConfig(get_logging_config(log_dir=log_dir, log_level='INFO'))
    
    config = configparser.ConfigParser()
    # # script_dir = os.path.dirname(__file__)
    config_path = os.path.join(script_dir, 'config.ini')
    config.read(config_path)

    if not config.has_section('LLM'):
        logger.error("Config file is missing [LLM] section.")
    else:
        llm_client = Get_LLM_Client_by_Config(config)
        if llm_client:
            # 1. Create a session
            chat_session = ChatSession(llm_client, config)

            # 2. Send a first message
            logger.info("--- Message 1 ---")
            question1 = "My name is aigniter. What is your name?"
            logger.info(f"> {question1}")
            # # response1 = chat_session.send_message(question1)
            # @Antigravity, 20260129, [FIX]: Handle tuple return
            response1, stats1 = chat_session.send_message(question1)
            logger.info(f"< {response1}")
            logger.info(f"Stats: {stats1}\n")

            # 3. Send a second message to test history
            logger.info("--- Message 2 ---")
            question2 = "Do you remember my name?"
            logger.info(f"> {question2}")
            # # response2 = chat_session.send_message(question2)
            # @Antigravity, 20260129, [FIX]: Handle tuple return
            response2, stats2 = chat_session.send_message(question2)
            logger.info(f"< {response2}")
            logger.info(f"Stats: {stats2}\n")

            # 4. Check history
            logger.info(f"Current history length: {len(chat_session.history)}")
            logger.debug(f"Full history: {chat_session.history}")
