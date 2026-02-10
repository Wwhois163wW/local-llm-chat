#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/parser.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260206
# Version: 0.1.1

import re
import logging
from collections.abc import Iterable, AsyncGenerator
from typing import Any, Callable
from dataclasses import dataclass
from enum import Enum, auto

from core.events import (
    TextChunk, ReadResourceRequest, EchoRequest, Event,
    LoadResourceRequest, UpdateMetadataRequest,
    GetSystemInfoRequest, GetSessionStatsRequest, ListDirRequest,
    GetMetadataRequest, GetCwdRequest
)

logger = logging.getLogger(__name__)

class ParserState(Enum):
    """解析器内部状态枚举。"""
    TEXT = auto()       # 普通文本状态，即时输出
    CALLING = auto()    # 捕获到 '<'，进入受控截流状态

@dataclass
class ParserRule:
    """定义一个解析规则。"""
    name: str
    pattern: re.Pattern[str]
    event_factory: Callable[[re.Match[str]], Event]

class XmlStreamParser:
    """
    贪心状态机解析类。
    负责流式处理 LLM 输出，通过状态切换实现标签截流与回退逻辑。
    """
    rules: list[ParserRule]
    buffer: str
    state: ParserState
    tag_start_idx: int

    def __init__(self, rules: list[ParserRule]):
        self.rules = rules
        self.buffer = ""
        self.state = ParserState.TEXT
        # 记录标签起始位置在 buffer 中的相对索引
        self.tag_start_idx = -1

    def parse_chunk(self, content: str) -> Iterable[Event]:
        """
        处理一小段文本块，依据当前状态返回产生的事件。
        """
        self.buffer += content
        
        while True:
            if self.state == ParserState.TEXT:
                # 寻找可能的标签起点
                start_match = re.search(r'<', self.buffer)
                if start_match:
                    # 吐出标签前的普通文本
                    pre_text = self.buffer[:start_match.start()]
                    if pre_text:
                        yield TextChunk(content=pre_text)
                    
                    # 切换状态，保留标签及其之后的内容在 buffer
                    self.buffer = self.buffer[start_match.start():]
                    self.state = ParserState.CALLING
                    continue # 立即按新状态处理
                else:
                    # 全是普通文本，全吐
                    yield TextChunk(content=self.buffer)
                    self.buffer = ""
                    break
            
            elif self.state == ParserState.CALLING:
                # 尝试匹配所有规则
                matched_rule: ParserRule | None = None
                best_match: re.Match[str] | None = None
                
                for rule in self.rules:
                    m = rule.pattern.search(self.buffer)
                    if m:
                        if best_match is None or m.start() < best_match.start():
                            best_match = m
                            matched_rule = rule
                
                if matched_rule and best_match:
                    # 命中标签！
                    # 1. 产生事件
                    yield matched_rule.event_factory(best_match)
                    
                    # 2. 消耗已匹配内容，切回 TEXT 状态
                    self.buffer = self.buffer[best_match.end():]
                    self.state = ParserState.TEXT
                    continue
                
                # 安全检查：如果截流 buffer 过长，或者明显不再可能是合法标签，则回退方案
                # 这里的“贪心”体现为：只要还没看到自闭合或结束符，就先 hold 住
                # 但如果 buffer 中出现了第二个 '<' 且第一个没被吃掉，说明第一个 '<' 可能是误报
                if self.buffer.count('<') > 1:
                    # 将第一个 '<' 之后的内容重新作为一个 chunk 处理，回退当前截流
                    yield TextChunk(content=self.buffer[0])
                    self.buffer = self.buffer[1:]
                    self.state = ParserState.TEXT # 尝试重新查找
                    continue
                
                # 如果 buffer 中含有明显非法字符（针对 XML 标签），也可以提前回退
                # 暂时保持简单：等待更多内容直到匹配或结束
                break

    def flush(self) -> Iterable[Event]:
        """流结束时的清理，释放截流 buffer。"""
        if self.buffer:
            yield TextChunk(content=self.buffer)
            self.buffer = ""
        self.state = ParserState.TEXT

# --- 规则定义容器 ---
_PARSER_RULES: list[ParserRule] = [
    ParserRule(
        name="load_resource",
        pattern=re.compile(r'<load_resource\s+type="([^"]+)"\s+source="([^"]+)"\s*/>'),
        event_factory=lambda m: LoadResourceRequest(
            res_type=m.group(1), 
            source=m.group(2), 
            content=m.group(0)
        )
    ),
    ParserRule(
        name="list_dir",
        pattern=re.compile(r'<list_dir\s+path="([^"]+)"\s*/>'),
        event_factory=lambda m: ListDirRequest(path=m.group(1), content=m.group(0))
    ),
    ParserRule(
        name="update_metadata",
        pattern=re.compile(r'<update_metadata\s+key="([^"]+)"\s+value="([^"]+)"(?:\s+persistent="(true|false)")?\s*/>'),
        event_factory=lambda m: UpdateMetadataRequest(
            key=m.group(1), 
            value=m.group(2), 
            persistent=m.group(3) == "true",
            content=m.group(0)
        )
    ),
    ParserRule(
        name="get_system_info",
        pattern=re.compile(r'<get_system_info\s*/>'),
        event_factory=lambda m: GetSystemInfoRequest(content=m.group(0))
    ),
    ParserRule(
        name="get_session_stats",
        pattern=re.compile(r'<get_session_stats\s*/>'),
        event_factory=lambda m: GetSessionStatsRequest(content=m.group(0))
    ),
    ParserRule(
        name="echo",
        pattern=re.compile(r'<echo message="([^"]+)"\s*/>'),
        event_factory=lambda m: EchoRequest(message=m.group(1), content=m.group(0))
    ),
    ParserRule(
        name="get_metadata",
        pattern=re.compile(r'<get_metadata(?:\s+key="([^"]+)")?\s*/>'),
        event_factory=lambda m: GetMetadataRequest(
            key=m.group(1) if m.group(1) else None, 
            content=m.group(0)
        )
    ),
    ParserRule(
        name="read_resource",
        pattern=re.compile(r'<read_resource\s+source="([^"]+)"\s+start="(-?\d+)"\s+end="(-?\d+)"\s*/>'),
        event_factory=lambda m: ReadResourceRequest(
            source=m.group(1), 
            start=int(m.group(2)), 
            end=int(m.group(3)), 
            content=m.group(0)
        )
    ),
    ParserRule(
        name="get_cwd",
        pattern=re.compile(r'<get_cwd\s*/>'),
        event_factory=lambda m: GetCwdRequest(content=m.group(0))
    )
]

def _extract_chunk_content(chunk: Any) -> str:
    """辅助函数：从 LLM 流的 Chunk 中提取内容。"""
    try:
        return chunk.choices[0].delta.content or ""
    except (AttributeError, IndexError):
        return ""

async def parse_stream(raw_stream: Iterable[Any]) -> AsyncGenerator[Event, None]:
    """
    解析来自 LLM 的原始流，并产生结构化的事件对象。
    封装了 XmlStreamParser 的贪心状态机。
    """
    parser = XmlStreamParser(_PARSER_RULES)
    
    for chunk in raw_stream:
        content = _extract_chunk_content(chunk)
        if not content:
            continue
            
        for event in parser.parse_chunk(content):
            yield event
            
    for event in parser.flush():
        yield event
