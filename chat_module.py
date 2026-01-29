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
        self.history = []
        logger.info(
            f"ChatSession initialized. Max history length: {self.max_history_length}"
        )

    def send_message(self, user_content: str):
        """
        Sends a user message to the LLM, manages history, and returns the response.

        Args:
            user_content (str): The user's input message.

        Returns:
            tuple: (response_content, stats)
                - response_content (str): The model's response content, or None on error.
                - stats (dict): A dictionary containing 'latency' and 'usage' (token counts).
        """
        # @Antigravity, 20260129, [MOD]: Update return type in docstring above
        try:
            # 1. Add user message to history
            self.history.append({"role": "user", "content": user_content})

            # 2. Trim history if it exceeds the max length (sliding window)
            if len(self.history) > self.max_history_length:
                # Keep the last `max_history_length` items
                self.history = self.history[-self.max_history_length:]
                logger.debug(f"History trimmed to the last {self.max_history_length} messages.")

            # 3. Send the full history to the LLM
            start_time = time.time() # @Antigravity, 20260129, [ADD]: Start timing
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
            )
            end_time = time.time() # @Antigravity, 20260129, [ADD]: End timing

            # # response_content = completion.choices[0].message.content
            # @Antigravity, 20260129, [FIX]: Extract response and stats
            response_content = completion.choices[0].message.content
            latency = end_time - start_time
            
            # Extract usage statistics
            # # usage = {
            # #     "prompt_tokens": completion.usage.prompt_tokens,
            # #     "completion_tokens": completion.usage.completion_tokens,
            # #     "total_tokens": completion.usage.total_tokens
            # # }
            
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

            # 4. Add assistant's response to history
            self.history.append({"role": "assistant", "content": response_content})
            
            # # return response_content
            return response_content, stats # @Antigravity, 20260129, [MOD]: Return content and stats

        except Exception as e:
            logger.error(f"Error during API call: {e}")
            # Optionally remove the user's message if the call failed
            if self.history and self.history[-1]["role"] == "user":
                self.history.pop()
            # # return None
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
