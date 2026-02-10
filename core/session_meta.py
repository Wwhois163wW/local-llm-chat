#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/session_meta.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260210
# Version: 1.0.0

import time
import json
import logging
import os
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class AuditEntry(BaseModel):
    """审计日志条目模型。"""
    timestamp: float = Field(default_factory=time.time)
    iso_time: str = Field(default_factory=lambda: datetime.now().isoformat())
    key: str
    old_value: Any
    new_value: Any
    context: str | None = None

class SessionState(BaseModel):
    """会话核心状态模型。"""
    current_mode: str = "Flush"
    current_task: str = "General"
    context_summary: str | None = None # @Antigravity, 20260210, [ADD]: 存储对话摘要
    last_action_type: str | None = None # 用于 CRUD 频率限制 (C/U/R)
    custom: dict[str, Any] = Field(default_factory=dict)

class SessionMetaManager:
    """
    基于 Pydantic 的会话元数据管理器。
    负责状态管理与变更审计。
    """
    def __init__(self, history_file: str):
        self.state_file = history_file.replace('.jsonl', '.meta.json')
        self.audit_file = history_file.replace('.jsonl', '.meta_history.jsonl')
        self.state = self._load_state()
        self._initialize_audit_file()

    def _initialize_audit_file(self):
        """确保审计文件存在。"""
        # @zhu, 20260210, [MARK] jsnol文件似乎不需要预创建,但需要确保目录存在
        os.makedirs(os.path.dirname(self.audit_file), exist_ok=True)
        if not os.path.exists(self.audit_file):
            with open(self.audit_file, 'w', encoding='utf-8') as f:
                pass

    def _load_state(self) -> SessionState:
        """从磁盘加载持久化状态快照。"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return SessionState(**data)
            except Exception as e:
                logger.error(f"Failed to load session state: {e}")
        return SessionState()

    def _save_state(self):
        """将当前状态快照写入磁盘。"""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                f.write(self.state.model_dump_json(indent=2))
        except Exception as e:
            logger.error(f"Failed to save session state: {e}")

    def update_state(
        self, 
        key: str, 
        value: Any, 
        context: str | None = None,
        persistent: bool = False
    ):
        """
        原子化更新状态并记录审计。
        """
        old_value = None
        if hasattr(self.state, key):
            old_value = getattr(self.state, key)
            setattr(self.state, key, value)
        else:
            old_value = self.state.custom.get(key)
            self.state.custom[key] = value

        # 记录审计
        entry = AuditEntry(
            key=key,
            old_value=old_value,
            new_value=value,
            context=context
        )
        self._write_audit(entry)
        
        # @Antigravity, 20260210, [FIX]: 恢复快照持久化功能
        if persistent:
            self._save_state()
            logger.info(f"[Meta Persistent] State snapshot saved to {self.state_file}")
            
        logger.info(f"[Meta Audit] {key}: {old_value} -> {value}")

    def _write_audit(self, entry: AuditEntry):
        """将审计条目写入 JSONL。"""
        try:
            with open(self.audit_file, 'a', encoding='utf-8') as f:
                f.write(entry.model_dump_json() + '\n')
        except Exception as e:
            logger.error(f"Failed to write meta audit: {e}")

    def get_snapshot(self) -> dict[str, Any]:
        """获取当前状态的完整快照。"""
        return self.state.model_dump()
