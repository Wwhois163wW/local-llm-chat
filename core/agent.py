#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/agent.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260206
# Version: 0.0.3

import logging
import time

from core.session import ChatSession
from core.parser import parse_stream
# 不再导入业务特定事件，实现纯透明分发
from core.events import Event, StatsUpdate

logger = logging.getLogger(__name__)

class Agent:
    def __init__(
        self, 
        chat_session: ChatSession, 
        debug_mode: bool = False
    ):
        """
        初始化 Agent，连接会话层与解析层。

        Args:
            chat_session (ChatSession): 管理对话历史和 LLM 调用的会话对象。
            debug_mode (bool, optional): 是否开启调试模式。默认为 False。
        """
        # @Antigravity, 20260206, [CLEANUP]: 移除冗余注释并应用极简架构
        self.chat_session: ChatSession = chat_session
        self.debug_mode: bool = debug_mode

    async def run(self):
        """
        启动 Agent 的运行循环。
        执行 LLM 调用，通过解析流生成事件，并维护对话状态。

        Yields:
            Event: 包含 TextChunk, StatsUpdate 或业务动作事件的流。
        """
        # @Antigravity, 20260206, [REF]: 重构为 buffer 以更准确描述其用途
        assistant_message_buffer: str = ""
        
        # @Antigravity, 20260206, [STYLE]: 嵌套调用折行
        stream, prompt_tokens, start_time = (
            await self.chat_session.call_llm()
        )
        # @Antigravity, 20260206, [REF]: 直接遍历解析流
        event_stream = parse_stream(stream)

        async for event in event_stream:
            # @Antigravity, 20260206, [REF]: 极简逻辑
            # 所有记录到历史的事件（文本/标签）现在统一通过 content 属性累加
            assistant_message_buffer += event.content
            yield event

        # 确保 Assistant 的消息被完整记录到内存和磁盘
        # @Antigravity, 20260206, [CLEANUP]: 移除旧注释，保持逻辑。
        self.chat_session.add_conversation_message(
            'assistant', 
            assistant_message_buffer
        )

        end_time = time.time()
        latency: float = end_time - start_time
        completion_tokens: int = self.chat_session.count_tokens(
            assistant_message_buffer
        )
        usage: dict[str, int] = {
            "prompt_tokens": prompt_tokens, 
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens
        }
        yield StatsUpdate(
            latency=latency, 
            usage=usage
        )
