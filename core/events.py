#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/events.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260206
# Version: 0.0.2

from typing import Any
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
class Thought(Event):
    """Represents the thinking process (CoT) of the agent."""
    # content is inherited

@dataclass
class FinalAnswer(Event):
    """Represents the final conclusion or summary for the user."""
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
class EchoRequest(Event):
    """Represents a request to echo a message back for loop validation.
    
    Attributes:
        message (str): The message to be echoed.
    """
    message: str = ""
    # content is inherited

@dataclass
class LoadResourceRequest(Event):
    """Requests basic metadata for a resource (file/web)."""
    res_type: str = ""
    source: str = ""

@dataclass
class ReadResourceRequest(Event):
    """Requests content slice of a resource. 
    Source can be a physical path or a Resource ID (RID).
    """
    source: str = ""
    start: int = 1
    end: int = 100

@dataclass
class GetSystemInfoRequest(Event):
    """Requests current system status."""
    pass

@dataclass
class GetSessionStatsRequest(Event):
    """Requests current session token and turn statistics."""
    pass

@dataclass
class ListDirRequest(Event):
    """Requests contents of a directory."""
    path: str = ""

@dataclass
class UpdateMetadataRequest(Event):
    """Requests to update session or persistent metadata."""
    key: str = ""
    value: Any = None
    persistent: bool = False

@dataclass
class GetMetadataRequest(Event):
    """Requests a current snapshot of all session and persistent metadata, 
    optionally filtered by key.
    """
    key: str | None = None

@dataclass
class GetCwdRequest(Event):
    """Requests the current working directory path."""
    pass

@dataclass
class SearchTextRequest(Event):
    """Requests recursive text search."""
    path: str = "."
    query: str = ""

@dataclass
class FindFilesRequest(Event):
    """Requests glob file search."""
    path: str = "."
    pattern: str = "*"

@dataclass
class FileWriteRequest(Event):
    """Requests file writing with content."""
    path: str = ""
    content_to_write: str = ""
@dataclass
class SpecialTokenDetected(Event):
    """Represents the detection of non-standard model tokens (e.g., <|...|>)."""
    token: str = ""
