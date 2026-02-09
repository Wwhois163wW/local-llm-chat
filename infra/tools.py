#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# infra/tools.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260206
# Version: 1.2.1

import os
import logging
import time
import datetime

logger = logging.getLogger(__name__)

def _is_path_safe(base_dir: str, target_path: str) -> bool:
    """内部辅助：确保 target_path 在 base_dir 范围内。"""
    try:
        abs_base = os.path.abspath(base_dir)
        abs_target = os.path.abspath(target_path)
        # 使用 commonpath 确保 target 是 base 的子路径或同路径
        return os.path.commonpath([abs_base, abs_target]) == abs_base
    except Exception:
        return False

# @Antigravity, 20260209, [FIX]: 强化路径安全校验，使用 commonpath 避免 Windows 边界匹配 Bug
def get_file_metadata(base_dir: str, path: str) -> dict:
    """
    获取文件详细元数据而不读取全量内容。
    """
    result = {"success": False, "error": "", "metadata": {}}
    try:
        target_path = os.path.normpath(os.path.join(base_dir, path))
        
        if not _is_path_safe(base_dir, target_path):
            result["error"] = "Access denied: Path out of bounds."
            return result
            
        if not os.path.exists(target_path):
            result["error"] = "File not found."
            return result
            
        file_stats = os.stat(target_path)
        with open(target_path, 'r', encoding='utf-8', errors='ignore') as f:
            line_count = sum(1 for _ in f)
            
        result["metadata"] = {
            "path": path,
            "size_kb": round(file_stats.st_size / 1024, 2),
            "line_count": line_count,
            "last_modified": time.ctime(file_stats.st_mtime)
        }
        result["success"] = True
        return result
    except Exception as e:
        logger.error(f"Error in get_file_metadata: {e}")
        result["error"] = str(e)
        return result

def read_file(
    base_dir: str, 
    path: str, 
    max_file_size_kb: int, 
    max_output_tokens: int, 
    tokenizer,
    start_line: int | None = None,
    end_line: int | None = None
) -> dict:
    """
    读取文件内容，支持行号切片。
    """
    supported_extensions = ['.txt', '.md', '.py', '.json', '.csv', '.xml', '.html']
    result = {"success": False, "error": "", "content": None}

    try:
        target_path = os.path.normpath(os.path.join(base_dir, path))
        
        if not _is_path_safe(base_dir, target_path):
            result["error"] = "Access denied: Path out of bounds."
            return result

        _, ext = os.path.splitext(target_path)
        # if ext not in supported_extensions:
        #    logger.warning(f"Reading file with unsupported extension: {ext}")
        
        if not os.path.exists(target_path):
            result["error"] = f"File not found: {path}"
            return result
        
        file_size_kb = os.path.getsize(target_path) / 1024
        if file_size_kb > max_file_size_kb:
             result["error"] = f"File too large ({file_size_kb:.2f} KB)."
             return result

        with open(target_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

        total_lines = len(lines)
        s = (start_line - 1) if start_line and start_line > 0 else 0
        e = end_line if end_line and end_line <= total_lines else total_lines
        
        s = max(0, min(s, total_lines))
        e = max(s, min(e, total_lines))
        
        content = "".join(lines[s:e])
        slice_info = f" (Lines {s+1}-{e} of {total_lines})"
        
        display_content = content
        if tokenizer and max_output_tokens > 0:
            encoded_content = tokenizer.encode(content)
            if len(encoded_content) > max_output_tokens:
                display_content = tokenizer.decode(encoded_content[:max_output_tokens]) + "\n... (truncated)"

        result["content"] = f"File content{slice_info}:\n```\n{display_content}\n```"
        result["success"] = True
        return result
    except Exception as e:
        logger.error(f"Error in read_file: {e}")
        result["error"] = str(e)
        return result

def list_dir(base_dir: str, path: str) -> dict:
    """列出目录内容。"""
    try:
        target_path = os.path.normpath(os.path.join(base_dir, path))
        if not _is_path_safe(base_dir, target_path):
            return {"success": False, "error": "Access denied."}
            
        if not os.path.isdir(target_path):
            return {"success": False, "error": "Not a directory."}
            
        items = os.listdir(target_path)
        result_text = f"Directory listing for '{path}':\n" + "\n".join([
            f"- {'[DIR] ' if os.path.isdir(os.path.join(target_path, i)) else '      '}{i}"
            for i in items
        ])
        return {"success": True, "result": result_text}
    except Exception as e:
        return {"success": False, "error": str(e)}

def write_file(base_dir: str, path: str, content: str) -> dict:
    """写入文件内容。"""
    try:
        target_path = os.path.normpath(os.path.join(base_dir, path))
        if not _is_path_safe(base_dir, target_path):
            return {"success": False, "error": "Access denied."}
            
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return {"success": True, "result": f"Successfully wrote to {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_system_info() -> str:
    """获取基础系统信息。"""
    import datetime
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"Current System Time: {now}"
