#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tests/test_parser_fallback.py

import asyncio
from core.parser import parse_stream
from core.events import TextChunk, EchoRequest

class MockChunk:
    def __init__(self, content):
        class Delta:
            def __init__(self, c):
                self.content = c
        class Choice:
            def __init__(self, d):
                self.delta = d
        self.choices = [Choice(Delta(content))]

async def run_test():
    print("=== Testing Parser Fallback & Greedy Logic ===")
    
    # 场景 1: 正常文本夹杂标签
    stream1 = [
        MockChunk("Hello <echo "),
        MockChunk('message="Success"/> after')
    ]
    print("\nScenario 1: Normal and Tag")
    async for event in parse_stream(stream1):
        print(f"Event: {type(event).__name__} -> {event.content}")

    # 场景 2: 截断标签回退 (由于流结束)
    stream2 = [
        MockChunk("Normal text <read_file pa")
    ]
    print("\nScenario 2: Truncated Tag (Flush)")
    async for event in parse_stream(stream2):
        print(f"Event: {type(event).__name__} -> {event.content}")

    # 场景 3: 误报标签回退 (多个 '<')
    # 贪心逻辑：发现第二个 '<' 时，说明第一个可能不是标签，应回退第一个 '<' 后的内容
    stream3 = [
        MockChunk("Compare: 1 < 5 and 2 < 3")
    ]
    print("\nScenario 3: False Positive Tag (Multiple '<')")
    async for event in parse_stream(stream3):
        print(f"Event: {type(event).__name__} -> {event.content}")

if __name__ == "__main__":
    asyncio.run(run_test())
