#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/session.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260206
# Version: 0.0.3

import time
import json
import logging
import configparser
import tiktoken
from openai import OpenAI, Stream
from typing import cast, Any
from collections.abc import Iterable
import os

from core.prompts import get_system_prompt

logger = logging.getLogger(__name__)

class ChatSession:
    def __init__(
        self,
        client: OpenAI,
        config: configparser.ConfigParser,
        history_file: str,
    ):
        """
        管理对话会话，包括历史记录、Token 统计和 LLM 交互。

        Args:
            client (OpenAI): OpenAI 客户端实例。
            config (configparser.ConfigParser): 应用程序配置对象。
            history_file (str): 历史记录文件的绝对路径。
        """
        # @Antigravity, 20260206, [CLEANUP]: 移除冗余注释并优化历史隔离逻辑
        self.client: OpenAI = client
        self.model: str = config['LLM'].get(
            'model', 
            'local-model'
        )
        self.max_history_length: int = config.getint(
            'LLM', 
            'max_history_length', 
            fallback=10
        )
        
        self.system_prompt: dict[str, str] = {
            "role": "system", 
            "content": get_system_prompt()
        }
        self.chat_history: list[dict[str, str | float]] = []
        self.history_file: str = history_file
        
        try:
            self.tokenizer: tiktoken.Encoding | None = (
                tiktoken.get_encoding("cl100k_base")
            )
        except Exception as e:
            self.tokenizer = None
            logger.warning(
                f"Failed to load tokenizer: {e}"
            )
        
        self._load_conversation_memory_from_file()
        logger.info("ChatSession initialized.")

    def add_conversation_message(self, role: str, content: str):
        """
        将消息添加到会话历史并持久化。

        Args:
            role (str): 角色（'user' 或 'assistant'）。
            content (str): 消息内容。
        """
        if role not in ['user', 'assistant']:
            logger.warning(
                f"Invalid role '{role}' for conversation message."
            )
            return

        message: dict[str, str | float] = { 
            "role": role, 
            "content": content, 
            "timestamp": time.time() 
        }
        self._write_message(message)
        self.chat_history.append(message)
        
        while len(self.chat_history) > self.max_history_length:
            _ = self.chat_history.pop(0)

    def _write_message(self, message: dict[str, str | float]):
        """
        将单条消息异步写入磁盘文件。

        Args:
            message (dict[str, Any]): 要写入的消息字典。
        """
        try:
            with open(self.history_file, 'a', encoding='utf-8') as f:
                _ = f.write(
                    json.dumps(message, ensure_ascii=False) + '\n'
                )
        except Exception as e:
            logger.error(
                f"Failed to write message: {e}"
            )

    def Inject_Tool_Observation(self, content: str):
        """
        架构方法：将工具观察结果作为消息注入历史。
        为了增强感知度，修改为以 'user' (环境反馈) 角色注入。

        Args:
            content (str): 观察到的结果文本。
        """
        # @Antigravity, 20260206, [REF]: 将角色从 system 改为 user 以提高感知度
        message: dict[str, str | float] = { 
            "role": "user", 
            "content": f"[Observation]: {content}", 
            "timestamp": time.time() 
        }
        self.chat_history.append(message)
        self._write_message(message)

    def Update_Metadata_by_Key(self, key: str, value: str | int | float | bool | None):
        """
        架构方法：更新会话元数据（如状态灯、面包屑等）。

        Args:
            key (str): 元数据键。
            value (Any): 元数据值。
        """
        # 目前简单记录到日志，实际可对接数据库或 UI 状态机
        logger.info(f"[Metadata Update] {key} = {value}")

    def _load_conversation_memory_from_file(self):
        """从磁盘加载历史记录到内存。"""
        if not os.path.exists(self.history_file):
            return
            
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                lines: list[str] = f.readlines()
            
            start_index = max(0, len(lines) - self.max_history_length)
            loaded_count: int = 0
            
            for line in lines[start_index:]:
                if line.strip():
                    # 显式转换解析结果，减少类型推导压力
                    raw_msg = json.loads(line)
                    message: dict[str, str | float] = {
                        'role': str(raw_msg.get('role', '')),
                        'content': str(raw_msg.get('content', '')),
                        'timestamp': float(raw_msg.get('timestamp', 0))
                    }
                    # @Antigravity, 20260206, [FIX]: 允许加载 system 消息，以保留工具观察结果
                    if message.get('role') in ['user', 'assistant', 'system']:
                        self.chat_history.append(message)
                        loaded_count += 1
            
            if loaded_count > 0:
                # 注入历史隔离提示：引导 LLM 识别新会话窗口
                separator: dict[str, str | float] = {
                    "role": "system",
                    "content": (
                        "[System] 以上为历史聊天记录。接下来的对话将在新窗口中进行。"
                        "请不要先入为主地假设用户要继续旧话题，除非用户在后续输入中明确提到。"
                    ),
                    "timestamp": time.time()
                }
                self.chat_history.append(separator)
                logger.debug("History separator injected.")
                
        except Exception as e:
            logger.error(
                f"Failed to load history: {e}"
            )

    def build_prompt(self) -> list[dict[str, str | float]]:
        """
        构建发送给 LLM 的完整消息列表。

        Returns:
            list[dict[str, str | float]]: 包含系统提示词和历史记录的消息列表。
        """
        # 合并系统提示词
        full_history: list[dict[str, str | float]] = [
            cast(dict[str, str | float], self.system_prompt)
        ] + self.chat_history
        return full_history

    def count_tokens(self, text: str) -> int:
        """
        使用 Tiktoken 计算文本中的 Token 数量。

        Args:
            text (str): 目标文本。

        Returns:
            int: Token 数量。
        """
        if not self.tokenizer:
            return 0
        return len(self.tokenizer.encode(text))

    async def call_llm(self) -> tuple[Stream, int, float]:
        """
        异步调用 LLM API。

        Returns:
            tuple[Stream, int, float]: 包含 (stream, prompt_tokens, start_time) 的元组。
        """
        prompt = self.build_prompt()
        
        prompt_text: str = "\n".join(
            str(m.get('content', '')) 
            for m in prompt
        )
        prompt_tokens: int = self.count_tokens(prompt_text)
        
        start_time: float = time.time()
        
        # 使用 cast 适配 OpenAI 的类型协变检查
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=cast(Any, prompt), 
            stream=True,
        )
        return stream, prompt_tokens, start_time
