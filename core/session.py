#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/session.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260206
# Version: 0.0.4

import time
import json
import logging
import configparser
import tiktoken
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk
from typing import cast, Any, AsyncIterator
import os

from core.prompts import AssembledPrompt
from core.resource_manager import ResourceManager
from core.session_meta import SessionMetaManager

logger = logging.getLogger(__name__)

class ChatSession:
    def __init__(
        self,
        client: AsyncOpenAI,
        config: configparser.ConfigParser,
        history_file: str,
    ):
        """
        管理对话会话，包括历史记录、Token 统计和 LLM 交互。

        Args:
            client (AsyncOpenAI): 异步 OpenAI 客户端实例。
            config (configparser.ConfigParser): 应用程序配置对象。
            history_file (str): 历史记录文件的绝对路径。
        """
        # @Antigravity, 20260206, [CLEANUP]: 移除冗余注释并优化历史隔离逻辑
        self.client: AsyncOpenAI = client
        self.model: str = config['LLM'].get(
            'model', 
            'local-model'
        )
        self.summary_model: str = config['LLM'].get(
            'summary_model',
            self.model
        )
        self.max_history_length: int = config.getint(
            'LLM', 
            'max_history_length', 
            fallback=10
        )
        # @Antigravity, 20260210, [ADD]: 压缩阈值配置
        self.compression_threshold: int = config.getint(
            'LLM',
            'compression_threshold',
            fallback=8
        )
        
        self.chat_history: list[dict[str, Any]] = []
        self.history_file: str = history_file
        
        # --- 核心元数据系统 (Pydantic Meta Manager) ---
        self.meta_manager = SessionMetaManager(history_file)

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
        
        # --- 统一资源管理器 (URM) 初始化 ---
        self.resource_manager = ResourceManager(base_dir=".")
        
        logger.info("ChatSession initialized with Metadata and URM support.")

    def _load_conversation_memory_from_file(self):
        """从磁盘加载历史记录到内存。"""
        if not os.path.exists(self.history_file):
            return
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            # 保证加载时不破坏当前会话的物理容量限制
            start_index = max(0, len(lines) - self.max_history_length)
            for line in lines[start_index:]:
                if line.strip():
                    msg = json.loads(line)
                    if msg.get('role') in ['user', 'assistant', 'system']:
                        self.chat_history.append(msg)
        except Exception as e:
            logger.error(f"Failed to load history: {e}")


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
        
        # @Antigravity, 20260210, [PLAN]: 触发压缩逻辑。由于 process_turns 是异步的，
        # 这里仅作长度维护，实际摘要触发建议在 Consumer 结束一轮任务后异步执行。
        while len(self.chat_history) > self.max_history_length:
            _ = self.chat_history.pop(0)

    def _write_message(self, message: dict[str, Any]):
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

    def Update_Metadata_by_Key(
        self, 
        key: str, 
        value: Any, 
        persistent: bool = False
    ) -> str:
        """更新会话元数据并记录审计记录。"""
        # @Antigravity, 2026/2/10, [FIX]: 路由至 Pydantic 审计系统，并透传 persistent
        self.meta_manager.update_state(
            key, 
            value, 
            context="Interaction", 
            persistent=persistent
        )
        return f"Metadata '{key}' updated and audited (persistent={persistent})."

    def get_metadata(self) -> dict[str, Any]:
        """获取元数据模型快照。"""
        return self.meta_manager.get_snapshot()

    def build_prompt(self) -> list[dict[str, Any]]:
        """构建发送给 LLM 的完整消息列表。"""
        # @Antigravity, 20260210, [NEW]: 动态组装思维链路与元数据
        active_meta = self.get_metadata()
        sys_content = AssembledPrompt.build(active_meta)
        
        full_history: list[dict[str, Any]] = [
            {"role": "system", "content": sys_content}
        ] + self.chat_history
        
        return full_history

    def count_tokens(self, text: str) -> int:
        """计算文本 Token。"""
        if not self.tokenizer:
            return 0
        return len(self.tokenizer.encode(text))

    async def call_llm(self) -> tuple[AsyncIterator[ChatCompletionChunk], int, float]:
        """异步调用 LLM API，返回异步流。"""
        prompt = self.build_prompt()
        prompt_text = "\n".join(str(m.get('content', '')) for m in prompt)
        prompt_tokens = self.count_tokens(prompt_text)
        
        start_time = time.time()
        # [FIX]: 使用 await 调用异步客户端的 completions.create
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=cast(Any, prompt), 
            stream=True,
        )
        return stream, prompt_tokens, start_time
