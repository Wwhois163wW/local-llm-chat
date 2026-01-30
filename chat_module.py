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
        self.max_file_size_kb = config['LLM'].getint('max_file_size_kb', 1024) # @Antigravity, 20260130, [ADD]: Load file size limit
        self.history = []
        self.last_errors = [] # @Antigravity, 20260130, [ADD]: List to hold non-critical errors for the UI
        logger.info(
            f"ChatSession initialized. Max history: {self.max_history_length}, Max file size: {self.max_file_size_kb} KB"
        )
        
    def send_message(self, user_content: str, files: list|None = None): # @Antigravity, 20260130, [MOD]: Add 'files' parameter
        """
        Sends a user message to the LLM, manages history, and returns the response.
        Optionally, injects file contents into the conversation context before the user message.

        Args:
            user_content (str): The user's input message.
            files (list, optional): A list of file paths to inject into the context. Defaults to None.

        Returns:
            tuple: (response_content, stats)
                - response_content (str): The model's response content, or None on error.
                - stats (dict): A dictionary containing 'latency' and 'usage' (token counts).
        """
        # @Antigravity, 20260129, [MOD]: Update return type in docstring above
        try:
            self.last_errors.clear() # @Antigravity, 20260130, [ADD]: Clear previous errors
            # @Antigravity, 20260130, [ADD]: Process file contents before adding user message
            injected_file_messages = []
            if files:
                for file_path in files:
                    if not os.path.exists(file_path):
                        # logger.warning(f"File not found, skipping: {file_path}")
                        self.last_errors.append(f"File not found, skipped: {file_path}") # @Antigravity, 20260130, [MOD]: Report error to UI
                        continue
                    
                    # @Antigravity, 20260130, [ADD]: Check file size
                    try:
                        file_size_kb = os.path.getsize(file_path) / 1024
                        if file_size_kb > self.max_file_size_kb:
                            self.last_errors.append(f"File '{os.path.basename(file_path)}' is too large ({file_size_kb:.1f} KB > {self.max_file_size_kb} KB), skipped.")
                            continue

                        with open(file_path, 'r', encoding='utf-8') as f:
                            file_content = f.read()
                        
                        file_name = os.path.basename(file_path)
                        # Default prompt template for file injection
                        file_injection_prompt = (
                            f"The following is the content of the file '{file_name}', please read it carefully:\n\n"
                            f"```\n{file_content}\n```\n\n"
                            f"Once read, you can proceed with the user's main query."
                        )
                        injected_file_messages.append({"role": "user", "content": file_injection_prompt})
                        logger.info(f"Injected file '{file_name}' content to history.")
                    except Exception as e:
                        # logger.error(f"Failed to read or inject file {file_path}: {e}")
                        self.last_errors.append(
                            f"Failed to read file '{os.path.basename(file_path)}': {e}"
                        ) # @Antigravity, 20260130, [MOD]: Report error to UI

            # 1. Add injected file messages (if any) to history
            self.history.extend(injected_file_messages)

            # 2. Add user message to history
            self.history.append({"role": "user", "content": user_content})

            # 3. Trim history if it exceeds the max length (sliding window)
            if len(self.history) > self.max_history_length:
                # Keep the last `max_history_length` items
                self.history = self.history[-self.max_history_length:]
                logger.debug(f"History trimmed to the last {self.max_history_length} messages.")

            # 4. Send the full history to the LLM
            start_time = time.time() # @Antigravity, 20260129, [ADD]: Start timing
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
            )
            end_time = time.time() # @Antigravity, 20260129, [ADD]: End timing

            # @Antigravity, 20260129, [FIX]: Extract response and stats
            response_content = completion.choices[0].message.content
            latency = end_time - start_time
            
            # Extract usage statistics
            # @Antigravity, 20260129, [FIX]: Safe usage extraction
            if hasattr(completion, 'usage') and completion.usage:
                usage = {
                    "prompt_tokens": completion.usage.prompt_tokens,
                    "completion_tokens": completion.usage.completion_tokens,
                    "total_tokens": completion.usage.total_tokens
                }
            else:
                logger.warning("API response missing 'usage' field.")
                usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

            stats = {
                "latency": latency,
                "usage": usage
            }
            logger.debug(f"Stats generated: {stats}")

            # 5. Add assistant's response to history
            self.history.append({"role": "assistant", "content": response_content})
            
            return response_content, stats # @Antigravity, 20260129, [MOD]: Return content and stats

        except Exception as e:
            logger.error(f"Error during API call: {e}")
            # Optionally remove the user's message if the call failed
            # @Antigravity, 20260130, [FIX]: Correctly handle removal of multiple messages (injected + user)
            # Remove the user's message and any injected file messages if the API call failed
            if self.history:
                # Assuming injected file messages are always before the user_content
                # Count how many messages were added in this turn
                messages_added_this_turn = 1 + len(injected_file_messages)
                for _ in range(messages_added_this_turn):
                    if self.history and self.history[-1]["role"] == "user":
                        self.history.pop()
                    else: # Should not happen if logic is correct, but for safety
                        break
            return None, None # @Antigravity, 20260129, [MOD]: Return None for both on error

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
