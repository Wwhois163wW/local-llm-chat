#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tests/mock_llm.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260210
# Version: 1.0.0

import asyncio
from typing import AsyncIterator, Any

class MockChunk:
    """模拟 ChatCompletionChunk"""
    def __init__(self, content: str):
        self.choices = [type('Choice', (), {
            'delta': type('Delta', (), {'content': content})
        })]

class MockAsyncStream:
    """模拟 AsyncIterator[ChatCompletionChunk]"""
    def __init__(self, chunks: list[str]):
        self.chunks = chunks
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index < len(self.chunks):
            chunk_content = self.chunks[self.index]
            self.index += 1
            await asyncio.sleep(0.01) # 模拟网络延迟
            return MockChunk(chunk_content)
        else:
            raise StopAsyncIteration

class MockLLMClient:
    """模拟 AsyncOpenAI 客户端"""
    def __init__(self):
        self.chat = type('Chat', (), {
            'completions': type('Completions', (), {
                'create': self.create
            })
        })

    async def create(self, **kwargs) -> MockAsyncStream:
        stream_type = kwargs.get("stream", True)
        messages = kwargs.get("messages", [])
        
        # 简单的基于用户输入的 Mock 策略
        user_msg = messages[-1]["content"] if messages else ""
        
        if "write a file" in user_msg.lower():
            chunks = [
                "<thought>I need to write a summary file to document the project.</thought>",
                "<write_file path=\"summary.md\" content_to_write=\"Project Overview: Async system refined.\" />",
                "<echo message=\"Task completed.\" />"
            ]
        elif "list" in user_msg.lower():
            chunks = [
                "<thought>User wants to list files.</thought>",
                "<list_dir path=\".\" />",
                "<echo message=\"Listed.\" />"
            ]
        else:
            chunks = ["<thought>Hello!</thought>", "Hello, how can I help you today?"]
            
        return MockAsyncStream(chunks)

def Get_Mock_LLM_Client():
    return MockLLMClient()
