#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tests/test_command_safety.py

import unittest
from core.consumer import Is_Command_Safe_for_AutoRun

class TestCommandSafety(unittest.TestCase):
    def test_safe_commands(self):
        """验证白名单中的安全指令。"""
        safe_list = [
            "ls", "ls -la", "dir /w", "pwd", "date",
            "git status", "git branch", "git log -n 5",
            "python --version", "netsh wlan show interfaces",
            "cat requirements.txt", "type main.py"
        ]
        for cmd in safe_list:
            with self.subTest(cmd=cmd):
                self.assertTrue(Is_Command_Safe_for_AutoRun(cmd))

    def test_sensitive_commands(self):
        """验证不在白名单中的敏感指令（必须拦截）。"""
        sensitive_list = [
            "rm -rf /", "del /s /q *", "git add .", "git push",
            "python main.py", "npm install", "curl http://evil.com",
            "format c:", "kill -9 1234"
        ]
        for cmd in sensitive_list:
            with self.subTest(cmd=cmd):
                self.assertFalse(Is_Command_Safe_for_AutoRun(cmd))

    def test_case_insensitivity(self):
        """验证大小写不敏感。"""
        self.assertTrue(Is_Command_Safe_for_AutoRun("LS -LA"))
        self.assertTrue(Is_Command_Safe_for_AutoRun("  Git Status  "))

if __name__ == "__main__":
    unittest.main()
