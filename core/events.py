#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/events.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260206
# Version: 1.0.1

from dataclasses import dataclass

@dataclass
class TextChunk:
    """Represents a chunk of plain text from the LLM's response."""
    content: str

@dataclass
class StatsUpdate:
    """Represents the final statistics of an API call."""
    latency: float
    usage: dict

@dataclass
class FileWriteStart:
    """Signals the beginning of a file-writing block."""
    path: str

@dataclass
class FileContentChunk:
    """Represents a chunk of content to be written to a file."""
    content: str

@dataclass
class FileWriteEnd:
    """Signals the end of a file-writing block."""
    pass

@dataclass
class FileReadRequest:
    """Signals a request from the LLM to read a file."""
    path: str
