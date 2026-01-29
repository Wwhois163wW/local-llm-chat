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
import os

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
            str: The model's response content, or None on error.
        """
        try:
            # 1. Add user message to history
            self.history.append({"role": "user", "content": user_content})

            # 2. Trim history if it exceeds the max length (sliding window)
            if len(self.history) > self.max_history_length:
                # Keep the last `max_history_length` items
                self.history = self.history[-self.max_history_length:]
                logger.debug(f"History trimmed to the last {self.max_history_length} messages.")

            # 3. Send the full history to the LLM
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
            )
            response_content = completion.choices[0].message.content

            # 4. Add assistant's response to history
            self.history.append({"role": "assistant", "content": response_content})
            
            return response_content

        except Exception as e:
            logger.error(f"Error during API call: {e}")
            # Optionally remove the user's message if the call failed
            if self.history and self.history[-1]["role"] == "user":
                self.history.pop()
            return None

if __name__ == '__main__':
    # Example Usage
    from api_client import Get_LLM_Client_by_Config
    from logging_setup import get_logging_config

    # --- Setup Logging and Config for test ---
    logging.config.dictConfig(get_logging_config(log_level='INFO'))
    
    config = configparser.ConfigParser()
    script_dir = os.path.dirname(__file__)
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
            response1 = chat_session.send_message(question1)
            logger.info(f"< {response1}\n")

            # 3. Send a second message to test history
            logger.info("--- Message 2 ---")
            question2 = "Do you remember my name?"
            logger.info(f"> {question2}")
            response2 = chat_session.send_message(question2)
            logger.info(f"< {response2}\n")

            # 4. Check history
            logger.info(f"Current history length: {len(chat_session.history)}")
            logger.debug(f"Full history: {chat_session.history}")
