#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/resource_manager.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260209
# Version: 1.0.0

import logging
from typing import Any

logger = logging.getLogger(__name__)

class ResourceManager:
    """
    统一资源管理器 (URM) 的核心组件。
    负责维护 Resource ID (RID) 与物理资源的映射。
    """
    def __init__(self, base_dir: str = "."):
        self.base_dir = base_dir
        self.resources: dict[str, dict[str, Any]] = {}
        # @Antigravity, 2026/02/12, [ADD]: 路径到 RID 的反向映射，用于去重
        self.source_to_rid: dict[str, str] = {}
        self._counter = 1
        logger.info(f"ResourceManager initialized with base_dir: {base_dir}")

    def register_resource(self, resource_type: str, source: str, metadata: dict[str, Any]) -> str:
        """
        注册一个新资源并生成唯一的 RID。若源已注册，则直接返回已有 RID。
        """
        # @Antigravity, 2026/02/12, [DEDUPE]: 检查是否已存在
        if source in self.source_to_rid:
            rid = self.source_to_rid[source]
            logger.debug(f"Source '{source}' already registered as {rid}. Skipping.")
            return rid

        rid = f"res_{self._counter}"
        self.resources[rid] = {
            "type": resource_type,
            "source": source,
            "metadata": metadata
        }
        self.source_to_rid[source] = rid
        self._counter += 1
        logger.info(f"Registered resource {rid}: {resource_type} -> {source}")
        return rid

    def get_resource(self, rid: str) -> dict[str, Any] | None:
        """
        根据 RID 获取资源详情。
        """
        return self.resources.get(rid)

    def get_resource_description(self, rid: str) -> str:
        """
        获取资源的语义化描述文本，用于注入 AI 观察结果。
        """
        res = self.get_resource(rid)
        if not res:
            return f"Resource {rid} not found."
        
        r_type = res.get("type", "unknown")
        src = res.get("source", "unknown")
        meta = res.get("metadata", {})
        
        if r_type == "file":
            # @Antigravity, 20260210, [FIX]: 增加对 metadata 为空或缺失的防御性处理
            meta = meta or {}
            lines = meta.get("line_count", "?")
            size = meta.get("size_kb", "?")
            return f"[File] {src} ({lines} lines, {size} KB) -> ID: {rid}"
            
        return f"[{r_type.capitalize()}] {src} -> ID: {rid}"

    def clear(self):
        """清空所有已加载的资源。"""
        self.resources.clear()
        self.source_to_rid.clear()
        self._counter = 1
        logger.debug("ResourceManager cache cleared.")
