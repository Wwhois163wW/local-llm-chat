#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/session.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260213
# Version: 0.0.6

import time
import json
import logging
import configparser
import tiktoken
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk
from typing import cast, Any
from collections.abc import AsyncIterator
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
        # @Antigravity, 2026/02/10, [ADD]: 物理 Context 上限 (n_ctx)
        self.max_context_tokens: int = config.getint(
            'LLM',
            'max_context_tokens',
            fallback=4096
        )
        
        # @Antigravity, 2026/02/12, [REFINE]: 压缩阈值逻辑重构。
        # 废弃旧的消息数计数逻辑，改为基于 Token 密度的自检。
        # 允许从 config 读取静态阈值，如果不提供，则动态设置为窗口的 60%。
        self.token_compression_threshold: int = config.getint(
            'LLM',
            'token_compression_threshold',
            fallback=int(self.max_context_tokens * 0.6)
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
        
        self._start_time = time.time()
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
        [MIDDLEWARE]: 对话要素拦截器，实现双路（User/Assistant）自动捕获。
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

        # @Antigravity, 20260216, [ELEMENT-CAPTURE]: 只要有内容，就尝试捕获并管理别名
        try:
            detected_rids = self.resource_manager.probe_elements(content)
            if detected_rids:
                descriptions = [
                    self.resource_manager.get_resource_description(rid)
                    for rid in detected_rids
                ]
                # 记录到元数据：当前活跃要素表
                self.Update_Metadata_by_Key(
                    "active_elements_info",
                    "\n".join(descriptions),
                    persistent=False
                )
                logger.info(f"[Middleware] Captured {len(detected_rids)} elements from {role}.")
        except Exception as e:
            logger.error(f"Element capture loop failed: {e}")

        # 维护历史长度
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
        print(f"[DEBUG Session] Updating Meta Key: {key} | Value: {value[:30]}...")
        # @Antigravity, 2026/2/10, [FIX]: 路由至 Pydantic 审计系统
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

    def should_compress(self) -> bool:
        """
        核心判定逻辑：检查当前对话历史（不含 Meta/System）的 Token 密度。
        返回 True 表示需要触发异步压缩（Summarization）。
        """
        history_text = "\n".join([str(m.get('content', '')) for m in self.chat_history])
        current_tokens = self.count_tokens(history_text)
        
        if current_tokens >= self.token_compression_threshold:
            logger.info(
                f"[Session] Token density ({current_tokens}) reached "
                f"threshold ({self.token_compression_threshold}). Requesting summary."
            )
            return True
        return False

    def build_prompt(self) -> list[dict[str, Any]]:
        """
        构建发送给 LLM 的完整消息列表，并执行 Token 级别的滑动窗口保底。
        """
        # 1. 组装系统提示词并预留安全空间
        active_meta = self.get_metadata()
        sys_content = AssembledPrompt.build(active_meta)
        sys_tokens = self.count_tokens(sys_content)
        
        # 保护区：System Prompt 必须存在
        final_prompt: list[dict[str, Any]] = [
            {"role": "system", "content": sys_content}
        ]
        
        # 2. 动态计算可用历史空间 (给 Assistant 留出 1000 Token 生成余量)
        available_history_space = self.max_context_tokens - sys_tokens - 1000
        
        # 如果 System Prompt 太大（异常），强制压缩历史
        if available_history_space < 500:
            logger.warning("System prompt is dangerously large. Truncating history aggressively.")
            available_history_space = 500

        # 3. 反向遍历历史记录，填充滑动窗口
        current_history_tokens = 0
        valid_history: list[dict[str, Any]] = []
        
        for msg in reversed(self.chat_history):
            msg_tokens = self.count_tokens(msg.get('content', ''))
            if current_history_tokens + msg_tokens > available_history_space:
                logger.info(f"[Session] Context limit reached. Truncating older messages.")
                break
            valid_history.insert(0, msg)
            current_history_tokens += msg_tokens
            
        final_prompt.extend(valid_history)
        return final_prompt

    def count_tokens(self, text_or_list: str | list[dict[str, Any]]) -> int:
        """计算文本或消息列表的 Token 总数。"""
        if not self.tokenizer:
            # 降级：估算法
            if isinstance(text_or_list, str):
                return len(text_or_list) // 4
            return sum(len(m.get("content", "")) // 4 for m in text_or_list)
        
        if isinstance(text_or_list, str):
            return len(self.tokenizer.encode(text_or_list))
        
        num_tokens = 0
        for message in text_or_list:
            num_tokens += 3  # 每条消息的固定开销
            for value in message.values():
                num_tokens += len(self.tokenizer.encode(str(value)))
        num_tokens += 3  # 响应起始开销
        return num_tokens

    def get_stats(self) -> dict[str, Any]:
        """获取当前会话的实时统计数据。"""
        return {
            "message_count": len(self.chat_history),
            "max_history_length": self.max_history_length,
            "total_estimated_tokens": self.count_tokens(self.chat_history),
            "token_compression_threshold": self.token_compression_threshold,
            "registered_resources_count": len(self.resource_manager.resources) if hasattr(self, "resource_manager") else 0,
            "uptime_seconds": int(time.time() - getattr(self, "_start_time", time.time()))
        }

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
