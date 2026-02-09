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
        self._counter = 1
        logger.info(f"ResourceManager initialized with base_dir: {base_dir}")

    def register_resource(self, resource_type: str, source: str, metadata: dict[str, Any]) -> str:
        """
        注册一个新资源并生成唯一的 RID。
        """
        rid = f"res_{self._counter}"
        self.resources[rid] = {
            "type": resource_type,
            "source": source,
            "metadata": metadata
        }
        self._counter += 1
        logger.info(f"Registered resource {rid}: {resource_type} -> {source}")
        return rid

    def get_resource(self, rid: str) -> dict[str, Any] | None:
        """
        根据 RID 获取资源详情。
        """
        return self.resources.get(rid)

    def clear(self):
        """清空所有已加载的资源。"""
        self.resources.clear()
        self._counter = 1
        logger.debug("ResourceManager cache cleared.")
