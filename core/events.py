#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/events.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260206
# Version: 0.1.1

from typing import Any
from dataclasses import dataclass

@dataclass
class Event:
    """Base class for all events in the system.
    
    Attributes:
        content (str): The raw text representation of the event to be 
                      recorded in the conversation history.
        act_type (str): Explicit action category (e.g., 'Read', 'Create', 'Update').
                       Helps decouple consumer logic from fragile inference.
    """
    content: str = ""
    act_type: str = ""

@dataclass
class TextChunk(Event):
    """Represents a chunk of plain text from the LLM's response."""
    act_type: str = "System"
    # content is inherited

@dataclass
class Thought(Event):
    """Represents the thinking process (CoT) of the agent."""
    act_type: str = "System"
    # content is inherited

@dataclass
class FinalAnswer(Event):
    """Represents the final conclusion or summary for the user."""
    act_type: str = "System"
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
    act_type: str = "System"
    # content is inherited and remains ""


@dataclass
class EchoRequest(Event):
    """Represents a request to echo a message back for loop validation.
    
    Attributes:
        message (str): The message to be echoed.
    """
    message: str = ""
    act_type: str = "System"
    # content is inherited

@dataclass
class LoadResourceRequest(Event):
    """Requests basic metadata for a resource (file/web)."""
    res_type: str = ""
    source: str = ""
    act_type: str = "Read"

@dataclass
class ReadResourceRequest(Event):
    """Requests content slice of a resource. 
    Source can be a physical path or a Resource ID (RID).
    """
    source: str = ""
    start: int = 1
    end: int = 100
    act_type: str = "Read"

@dataclass
class GetSystemInfoRequest(Event):
    """Requests current system status."""
    act_type: str = "Read"

@dataclass
class GetSessionStatsRequest(Event):
    """Requests current session token and turn statistics."""
    act_type: str = "Read"

@dataclass
class ListDirRequest(Event):
    """Requests contents of a directory."""
    path: str = ""
    act_type: str = "Read"

@dataclass
class UpdateMetadataRequest(Event):
    """Requests to update session or persistent metadata."""
    key: str = ""
    value: Any = None
    persistent: bool = False
    act_type: str = "Update"

@dataclass
class GetMetadataRequest(Event):
    """Requests a current snapshot of all session and persistent metadata, 
    optionally filtered by key.
    """
    key: str | None = None
    act_type: str = "Read"

@dataclass
class GetCwdRequest(Event):
    """Requests the current working directory path."""
    act_type: str = "Read"

@dataclass
class SearchTextRequest(Event):
    """Requests recursive text search."""
    path: str = "."
    query: str = ""
    act_type: str = "Read"

@dataclass
class FindFilesRequest(Event):
    """Requests glob file search."""
    path: str = "."
    pattern: str = "*"
    act_type: str = "Read"

@dataclass
class FileWriteRequest(Event):
    """Requests file writing with content."""
    path: str = ""
    content_to_write: str = ""
    act_type: str = "Write"
@dataclass
class SpecialTokenDetected(Event):
    """Represents the detection of non-standard model tokens (e.g., <|...|>)."""
    token: str = ""
    act_type: str = "System"

@dataclass
class ExecuteCommandRequest(Event):
    """Requests to execute a system command.
    
    Attributes:
        command (str): The command string to execute.
        cwd (str): Current working directory for the command.
        timeout (int): Timeout in seconds.
    """
    command: str = ""
    cwd: str = "."
    timeout: int = 30
    act_type: str = "Execute"
@dataclass
class MalformedAction(Event):
    """Represents a tag that looks like a tool call but doesn't match any specific rule.
    
    Attributes:
        raw_tag (str): The malformed tag string captured from the stream.
    """
    raw_tag: str = ""
    act_type: str = "System"
