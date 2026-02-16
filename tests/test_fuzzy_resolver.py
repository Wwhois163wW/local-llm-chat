#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tests/test_fuzzy_resolver.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260216

import unittest
from unittest.mock import MagicMock
import os
import asyncio
from infra.background_api import _resolve_element_alias, probe_and_load_resource

class TestFuzzyResolver(unittest.TestCase):
    def setUp(self):
        # 1. 模拟 Session 和 ResourceManager
        self.mock_session = MagicMock()
        self.mock_rm = MagicMock()
        self.mock_session.resource_manager = self.mock_rm
        
        # 2. 模拟已注册的资源
        self.mock_rm.get_resource.side_effect = self._mock_get_resource

    def _mock_get_resource(self, rid):
        if rid == "path_1":
            return {"category": "path", "content": "core/session.py"}
        if rid == "block_1":
            return {"category": "block", "content": "print('hello world')"}
        return None

    def test_exact_alias(self):
        """测试精确别名解析。"""
        res = _resolve_element_alias("path_1", self.mock_session)
        self.assertEqual(res, "core/session.py")

    def test_fuzzy_alias_correction(self):
        """测试模糊别名纠偏 (p_1 -> path_1)。"""
        # 模拟 LLM 笔误写成 p_1
        res = _resolve_element_alias("p_1", self.mock_session)
        print(f"[Test] p_1 -> {repr(res)}")
        self.assertEqual(res, "core/session.py", f"Fuzzy recovery for p_1 failed: got {repr(res)}")
        
        # 模拟 LLM 缩写成 b_1
        res = _resolve_element_alias("b_1", self.mock_session)
        print(f"[Test] b_1 -> {repr(res)}")
        self.assertEqual(res, "print('hello world')", f"Fuzzy recovery for b_1 failed: got {repr(res)}")

    def test_numeric_only_alias(self):
        """测试纯数字别名纠偏 (1 -> path_1)。"""
        # 如果只传了一个 1，解析器应尝试打捞 path_1 (优先级：path > block > url)
        res = _resolve_element_alias("1", self.mock_session)
        self.assertEqual(res, "core/session.py")

if __name__ == "__main__":
    unittest.main()
