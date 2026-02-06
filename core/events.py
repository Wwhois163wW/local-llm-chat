#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/events.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260206
# Version: 0.0.2

from dataclasses import dataclass

@dataclass
class Event:
    """Base class for all events in the system.
    
    Attributes:
        content (str): The raw text representation of the event to be 
                      recorded in the conversation history.
    """
    content: str = ""

@dataclass
class TextChunk(Event):
    """Represents a chunk of plain text from the LLM's response."""
    # content is inherited

@dataclass
class StatsUpdate(Event):
    """Represents the final statistics of an API call.
    
    Attributes:
        latency (float): Time taken for the LLM request in seconds.
        usage (dict[str, int] | None): Token usage details:
            - prompt_tokens (int)
            - completion_tokens (int)
            - total_tokens (int)
    """
    latency: float = 0.0
    usage: dict[str, int] | None = None
    # content is inherited and remains ""

@dataclass
class FileReadRequest(Event):
    """Signals a request from the LLM to read a file."""
    path: str = ""
    # @Antigravity, 20260206, [NEW]: 添加 EchoRequest 事件用于循环验证
@dataclass
class EchoRequest(Event):
    """Represents a request to echo a message back for loop validation.
    
    Attributes:
        message (str): The message to be echoed.
    """
    message: str = ""
    # content is inherited

