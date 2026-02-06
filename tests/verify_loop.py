#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tests/verify_loop.py
# Author: Antigravity (Simulated)
# Date: 20260206

import asyncio
import sys
import os

# 确保核心路径在 pythonpath 中
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.events import TextChunk, EchoRequest, StatsUpdate
from core.parser import parse_stream
from dataclasses import dataclass

@dataclass
class MockDelta:
    content: str | None

@dataclass
class MockChoice:
    delta: MockDelta

@dataclass
class MockChunk:
    choices: list[MockChoice]

def mock_llm_stream(text: str):
    """模拟 LLM 输出流（同步生成器，对齐 OpenAI Stream）"""
    for char in text:
        yield MockChunk(choices=[MockChoice(delta=MockDelta(content=char))])

async def test_echo_parsing():
    print("--- Testing Echo Parsing ---")
    raw_text = 'Hello, let me echo something: <echo message="Success Loop"/> and some more text.'
    stream = mock_llm_stream(raw_text)
    
    events = []
    async for event in parse_stream(stream):
        events.append(event)
        print(f"Parsed Event: {type(event).__name__} -> {getattr(event, 'content', '') or getattr(event, 'message', '')}")

    assert any(isinstance(e, EchoRequest) for e in events)
    print("Test Passed: EchoRequest detected.\n")

async def main():
    await test_echo_parsing()

if __name__ == "__main__":
    asyncio.run(main())
