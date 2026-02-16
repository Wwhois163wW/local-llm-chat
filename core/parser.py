#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/parser.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260216
# Version: 0.2.1

import re
import logging
from typing import Any, Callable
from collections.abc import AsyncIterator, AsyncGenerator, Iterable
from dataclasses import dataclass
from enum import Enum, auto

from core.events import (
    TextChunk, ReadResourceRequest, EchoRequest, Event,
    LoadResourceRequest, UpdateMetadataRequest,
    GetSystemInfoRequest, GetSessionStatsRequest, ListDirRequest,
    GetMetadataRequest, GetCwdRequest, Thought, FinalAnswer,
    SearchTextRequest, FindFilesRequest, FileWriteRequest,
    SpecialTokenDetected, ExecuteCommandRequest, MalformedAction
)

logger = logging.getLogger(__name__)

class ParserState(Enum):
    """解析器内部状态枚举。"""
    TEXT = auto()       # 普通文本状态，即时输出
    CALLING = auto()    # 捕获到 '<'，进入受控截流状态
    OPAQUE = auto()     # 处理大段内容标签（如 write_file），忽略内部特殊符号直至闭合

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
    opaque_end_tag: str | None

    def __init__(self, rules: list[ParserRule]):
        self.rules = rules
        self.buffer = ""
        self.state = ParserState.TEXT
        # 记录标签起始位置在 buffer 中的相对索引
        self.tag_start_idx = -1
        self.opaque_end_tag = None

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
                    # 全是普通文本，非空则吐
                    if self.buffer:
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
                    yield matched_rule.event_factory(best_match)
                    self.buffer = self.buffer[best_match.end():]
                    self.state = ParserState.TEXT
                    continue
                
                # Check for "opaque" tags entry (e.g., <write_file)
                # ONLY write_file needs isolation to ensure raw writing
                if self.buffer.startswith("<write_file"):
                    self.state = ParserState.OPAQUE
                    self.opaque_end_tag = "</write_file>"
                    break

                # Original safety for short tags: detect double '<'
                all_indices = [i for i, char in enumerate(self.buffer) if char == '<']
                if len(all_indices) > 1:
                    # Heuristic: If it looks like a comparison (e.g. '< ' or '<数字'), 
                    # flush the first '<' as text to avoid silent interception.
                    first_lt_pos = all_indices[0]
                    next_char = self.buffer[first_lt_pos + 1] if first_lt_pos + 1 < len(self.buffer) else ""
                    
                    if next_char.isspace() or next_char.isdigit():
                        yield TextChunk(content=self.buffer[0:first_lt_pos+1])
                        self.buffer = self.buffer[first_lt_pos+1:]
                    else:
                        yield SpecialTokenDetected(
                            token="unexpected_lt_inside_tag", 
                            content=self.buffer[0]
                        )
                        self.buffer = self.buffer[1:]
                    
                    self.state = ParserState.TEXT
                    continue
                
                if len(self.buffer) > 4000:
                    yield TextChunk(content=self.buffer[0])
                    self.buffer = self.buffer[1:]
                    self.state = ParserState.TEXT
                    continue

                break

            elif self.state == ParserState.OPAQUE:
                # In OPAQUE mode, we ONLY scan for the explicit end_tag.
                # Internal '<' are ignored.
                assert self.opaque_end_tag is not None
                match = re.search(re.escape(self.opaque_end_tag), self.buffer)
                if match:
                    # Once end_tag found, the buffer now contains the full tag.
                    full_content = self.buffer[:match.end()]
                    
                    # Pass the full content back to the rules for standard processing
                    # We reuse the existing patterns by applying them to this "sealed" buffer section
                    matched = False
                    for rule in self.rules:
                        m = rule.pattern.fullmatch(full_content)
                        if m:
                            yield rule.event_factory(m)
                            matched = True
                            break
                    
                    if not matched:
                        # Fallback for corrupted opaque tags
                        yield MalformedAction(raw_tag=full_content, content=full_content)

                    self.buffer = self.buffer[match.end():]
                    self.state = ParserState.TEXT
                    self.opaque_end_tag = None
                    continue
                else:
                    # Not found yet, keep buffering.
                    # Safety limit for huge opaque blocks
                    if len(self.buffer) > 200000: # 200k chars ~ 150k tokens safety
                        logger.warning("Opaque buffer exceeded 200k limit. Forcing flush.")
                        yield TextChunk(content=self.buffer)
                        self.buffer = ""
                        self.state = ParserState.TEXT
                    break

    def flush(self) -> Iterable[Event]:
        """流结束时的清理，释放截流 buffer。"""
        if self.buffer:
            yield TextChunk(content=self.buffer)
            self.buffer = ""
        self.state = ParserState.TEXT

# --- 辅助函数：解码与处理 ---

def _strip_markdown_code_delimiters(text: str) -> str:
    """
    剥离文本两端的 markdown 代码块语法 (```lang ... ```).
    """
    text = text.strip()
    # 匹配 ```lang\n内容\n``` 或 ```内容```
    m = re.match(r'^```(?:\w+\n)?(.*?)\n?```$', text, re.DOTALL)
    if m:
        return m.group(1)
    return text

def _create_write_file_event(m: re.Match[str]) -> Any:
    """
    处理 write_file 标签。支持属性模式 (group 2) 与主体模式 (group 3).
    """
    path = m.group(1)
    attr_content = m.group(2)
    body_content = m.group(3)
    
    # 优先取主体内容 (Body-style)
    final_content = ""
    if body_content is not None:
        final_content = _strip_markdown_code_delimiters(body_content)
    elif attr_content is not None:
        final_content = attr_content
        
    return FileWriteRequest(
        path=path, 
        content_to_write=final_content, 
        content=m.group(0)
    )

# --- 规则定义容器 ---
_PARSER_RULES: list[ParserRule] = [
    ParserRule(
        name="load_resource",
        # @Antigravity, 2026/02/13, [STRICT]: 回归严格属性顺序，拒绝容错。
        pattern=re.compile(r'<load_resource\s+type="([^"<]+)"\s+source="([^"<]+)"\s*/>'),
        event_factory=lambda m: LoadResourceRequest(
            res_type=m.group(1), 
            source=m.group(2), 
            content=m.group(0)
        )
    ),
    # --- Special Token Interception ---
    ParserRule(
        name="special_token",
        # @Antigravity, 2026/02/12, [REF]: 细化特殊 Token 匹配，防止对普通文本（如 |>）过度敏感
        # 仅匹配格式严格为 <|TOKEN|> 的结构
        pattern=re.compile(r'<\|(.*?)\|>', re.DOTALL),
        event_factory=lambda m: SpecialTokenDetected(
            token=m.group(1), 
            content=m.group(0)
        )
    ),
    ParserRule(
        name="list_dir",
        pattern=re.compile(r'<list_dir\s+path="([^"<]+)"\s*/>'),
        event_factory=lambda m: ListDirRequest(path=m.group(1), content=m.group(0))
    ),
    ParserRule(
        name="update_metadata",
        pattern=re.compile(r'<update_metadata\s+([^>]*?)/>'),
        event_factory=lambda m: UpdateMetadataRequest(
            key=next((x.group(1) for x in [re.search(r'key="([^"<]+)"', m.group(1))] if x), "unknown"), 
            value=next((x.group(1) for x in [re.search(r'value="([^"<]+)"', m.group(1))] if x), ""), 
            persistent=re.search(r'persistent="true"', m.group(1)) is not None,
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
        pattern=re.compile(r'<echo message="([^"<]+)"\s*/>'),
        event_factory=lambda m: EchoRequest(message=m.group(1), content=m.group(0))
    ),
    ParserRule(
        name="get_metadata",
        pattern=re.compile(r'<get_metadata(?:\s+key="([^"<]+)")?\s*/>'),
        event_factory=lambda m: GetMetadataRequest(
            key=m.group(1) if m.group(1) else None, 
            content=m.group(0)
        )
    ),
    ParserRule(
        name="read_resource",
        pattern=re.compile(r'<read_resource\s+source="([^"<]+)"\s+start="(\d+)"\s+end="(\d+)"\s*/>'),
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
    ),
    # --- ReAct Infrastructure ---
    ParserRule(
        name="thought",
        pattern=re.compile(r'<thought>(.*?)</thought>', re.DOTALL),
        event_factory=lambda m: Thought(content=m.group(1))
    ),
    ParserRule(
        name="final_answer",
        pattern=re.compile(r'<final_answer>(.*?)</final_answer>', re.DOTALL),
        event_factory=lambda m: FinalAnswer(content=m.group(1))
    ),
    # --- Extended Search Tools ---
    ParserRule(
        name="search_text",
        pattern=re.compile(r'<search_text\s+path="([^"]+)"\s+query="([^"]+)"\s*/>'),
        event_factory=lambda m: SearchTextRequest(path=m.group(1), query=m.group(2), content=m.group(0))
    ),
    ParserRule(
        name="find_files",
        pattern=re.compile(r'<find_files\s+path="([^"<]+)"\s+pattern="([^"<]+)"\s*/>'),
        event_factory=lambda m: FindFilesRequest(path=m.group(1), pattern=m.group(2), content=m.group(0))
    ),
    # --- Refined Write File (Supports Attr and Body style) ---
    ParserRule(
        name="write_file",
        # @Antigravity, 2026/02/12, [REF]: 属性模式禁用 < 以触发违规检测逻辑。
        pattern=re.compile(
            r'<write_file\s+path="([^"<]+)"(?:(?:\s+content_to_write="([^"<]+)"\s*/>)|(?:\s*>(.*?)</write_file>))', 
            re.DOTALL
        ),
        event_factory=_create_write_file_event
    ),
    ParserRule(
        name="execute_command",
        pattern=re.compile(r'<execute_command\s+command="([^"<]+)"\s+cwd="([^"<]+)"\s+timeout="(\d+)"\s*/>'),
        event_factory=lambda m: ExecuteCommandRequest(
            command=m.group(1), 
            cwd=m.group(2), 
            timeout=int(m.group(3)), 
            content=m.group(0)
        )
    ),
    # @Antigravity, 2026/02/13, [CATCH-ALL]: 拦截任何 XML 风格的非法构造，将其转化为报错事件。
    # 置于列表最末，确保不干扰合法捕获。
    ParserRule(
        name="unrecognized_tag",
        pattern=re.compile(r'<([a-z_]+)\s+[^>]*?/?>'),
        event_factory=lambda m: MalformedAction(raw_tag=m.group(0), content=m.group(0))
    )
]

def _extract_chunk_content(chunk: Any) -> str:
    """辅助函数：从 LLM 流的 Chunk 中提取内容。"""
    try:
        return chunk.choices[0].delta.content or ""
    except (AttributeError, IndexError):
        return ""

async def parse_stream(raw_stream: AsyncIterator[Any]) -> AsyncGenerator[Event, None]:
    """
    解析来自 LLM 的原始异步流，并产生结构化的事件对象。
    封装了 XmlStreamParser 的贪心状态机。
    """
    parser = XmlStreamParser(_PARSER_RULES)
    
    # [FIX]: 使用 async for 迭代异步流以解决 GeneratorExit 故障
    async for chunk in raw_stream:
        content = _extract_chunk_content(chunk)
        if not content:
            continue
            
        for event in parser.parse_chunk(content):
            yield event
            
    for event in parser.flush():
        yield event
