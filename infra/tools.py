#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# infra/tools.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260206
# Version: 1.2.4

import os
import logging
import time

logger = logging.getLogger(__name__)

def _is_path_safe(base_dir: str, target_path: str, level: str = "W") -> bool:
    """
    内部辅助：路径安全决策中心。
    - level="W" (Write): 强制锁死在 base_dir 及其影子目录。
    - level="R" (Read): 开放模式，仅拦截系统敏感黑名单。
    """
    try:
        abs_base = os.path.abspath(base_dir)
        abs_target = os.path.abspath(target_path)
        
        # 定义敏感黑名单 (针对 Read 级别)
        # @Antigravity, 2026/02/10, [RULE]: 遵循最小阻碍原则，仅拦截核心系统路径
        blacklist = [
            'C:\\Windows', 'C:\\System32', '/etc', '/var', '/root', '/bin', 
            '/.ssh', '/.gnupg', os.path.expanduser('~/.ssh')
        ]
        
        # Write 级别维持严苛校验
        if level == "W":
            # 允许工作区或影子路径
            is_in_workspace = os.path.commonpath([abs_base, abs_target]) == abs_base
            is_in_staging = ".staging" in abs_target
            return is_in_workspace or is_in_staging
            
        # Read 级别：防君子不防小人，仅拦截黑名单
        for blocked in blacklist:
            if abs_target.lower().startswith(blocked.lower()):
                return False
        return True # 其他路径均视为可读
    except Exception:
        return False

# @Antigravity, 20260209, [FIX]: 强化路径安全校验，使用 commonpath 避免 Windows 边界匹配 Bug
def get_file_metadata(base_dir: str, path: str) -> dict:
    """
    获取文件详细元数据而不读取全量内容。
    """
    result = {"success": False, "error": "", "result": {}}
    try:
        target_path = os.path.normpath(os.path.join(base_dir, path))
        
        if not _is_path_safe(base_dir, target_path, level="R"):
            result["error"] = "Access denied: Path out of bounds or sensitive."
            return result
            
        if not os.path.exists(target_path):
            result["error"] = "File not found."
            return result
            
        file_stats = os.stat(target_path)
        with open(target_path, 'r', encoding='utf-8', errors='ignore') as f:
            line_count = sum(1 for _ in f)
            
        result["result"] = {
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
    result = {"success": False, "error": "", "result": None}

    try:
        target_path = os.path.normpath(os.path.join(base_dir, path))
        
        if not _is_path_safe(base_dir, target_path, level="R"):
            result["error"] = "Access denied: Path out of bounds or sensitive."
            return result

        pass
        
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
        s_idx = (start_line - 1) if start_line and start_line > 0 else 0
        
        # 处理 -1 语义：实现安全预览 (Start + 100)
        effective_end = end_line
        if effective_end == -1:
            effective_end = (start_line if start_line else 1) + 100
            
        e_idx = effective_end if (effective_end is not None and effective_end <= total_lines) else total_lines
        
        s_idx = max(0, min(s_idx, total_lines))
        e_idx = max(s_idx, min(e_idx, total_lines))
        
        content = "".join(lines[s_idx:e_idx])
        slice_info = f" (Lines {s_idx+1}-{e_idx} of {total_lines})"
        
        display_content = content
        if tokenizer and max_output_tokens > 0:
            encoded_content = tokenizer.encode(content)
            if len(encoded_content) > max_output_tokens:
                display_content = tokenizer.decode(encoded_content[:max_output_tokens]) + "\n... (truncated)"

        result["result"] = f"File content{slice_info}:\n```\n{display_content}\n```"
        result["success"] = True
        return result
    except Exception as e:
        logger.error(f"Error in read_file: {e}")
        result["error"] = str(e)
        return result

def list_dir(base_dir: str, path: str) -> dict:
    """列出目录内容。无权限限制。"""
    try:
        # 直接解析路径，不进行 workspace 校验
        target_path = os.path.normpath(os.path.join(base_dir, path))
        
        if not os.path.exists(target_path):
             return {"success": False, "error": f"Path not found: {path}"}
             
        if not os.path.isdir(target_path):
            return {"success": False, "error": f"Not a directory: {path}"}
            
        items = os.listdir(target_path)
        result_text = f"Directory listing for '{path}':\n" + "\n".join([
            f"- {'[DIR] ' if os.path.isdir(os.path.join(target_path, i)) else '      '}{i}"
            for i in items
        ])
        return {"success": True, "result": result_text}
    except Exception as e:
        logger.error(f"list_dir failed for {path}: {e}")
        return {"success": False, "error": str(e)}

def write_file(base_dir: str, path: str, content: str) -> dict:
    """
    分级写入控制 (Tiered CRUD):
    1. Update (U): 既有文件修改，允许在工作区执行并存底备份。
    2. Create (C): 新文件创建，强制重定向至 .staging/new/ 且禁止重名覆盖。
    """
    try:
        import html
        import shutil
        decoded_content = html.unescape(content)
        
        target_path = os.path.normpath(os.path.join(base_dir, path))
        file_exists = os.path.exists(target_path)
        
        # @Antigravity, 20260210, [FIX]: 路径重定向与创建/更新识别
        is_create = not file_exists
        action_type = "Create" if is_create else "Update"
        final_path = target_path # 初始默认值
        feedback = ""

        if is_create:
            # [RULE]: 新文件强制进入影子目录
            staging_root = os.path.join(base_dir, ".staging", "new")
            os.makedirs(staging_root, exist_ok=True)
            
            # 防止双重嵌套：如果 Agent 已经显式写了 .staging/new/，则提取其实际子路径
            # 统一使用 normpath 处理，增强鲁棒性
            norm_path = os.path.normpath(path)
            if norm_path.startswith(".staging" + os.sep + "new"):
                # 剥离前缀
                relative_sub = os.path.relpath(norm_path, ".staging" + os.sep + "new")
            elif norm_path.startswith(".staging/new"): # 兼容 posix 风格
                relative_sub = os.path.relpath(norm_path, ".staging/new")
            else:
                relative_sub = norm_path
                
            # 安全处理子路径（处理冒号与跨目录尝试）
            safe_subpath = relative_sub.replace(":", "_").replace("..", "__")
            final_path = os.path.normpath(os.path.join(staging_root, safe_subpath))
            
            target_dir = os.path.dirname(final_path)
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)
            
            # [RULE]: 禁止同名覆盖 (C 级别冲突)
            if os.path.exists(final_path):
                return {
                    "success": False, 
                    "error": f"Create conflict: File '{path}' already exists in staging. Overwrite via Create is forbidden."
                }
            feedback = f"New file created in staging buffer: '{os.path.relpath(final_path, base_dir)}'."
            logger.info(f"Create redirected: {path} -> {final_path}")

        else: # Update 逻辑
            final_path = target_path
            feedback = f"Successfully updated '{path}'."
            is_safe = _is_path_safe(base_dir, target_path)
            if not is_safe:
                staging_root = os.path.join(base_dir, ".staging", "external")
                safe_subpath = path.replace(":", "_").replace("..", "__").lstrip("\\/")
                final_path = os.path.join(staging_root, safe_subpath)
                feedback = f"External file update redirected to staging: '.staging/external/{safe_subpath}'."
            else:
                # [RULE]: 工作区内更新需“存底” (Backup)
                backup_dir = os.path.join(base_dir, ".staging", "backups")
                os.makedirs(backup_dir, exist_ok=True)
                timestamp = int(time.time())
                backup_name = f"{os.path.basename(path)}.{timestamp}.bak"
                shutil.copy2(target_path, os.path.join(backup_dir, backup_name))
                feedback = f"File updated in workspace. Backup saved to '.staging/backups/{backup_name}'."

        # 执行写入
        os.makedirs(os.path.dirname(final_path), exist_ok=True)
        with open(final_path, 'w', encoding='utf-8') as f:
            f.write(decoded_content)
            
        return {
            "success": True, 
            "result": feedback or f"Successfully {action_type.lower()}ed {path}",
            "action_type": action_type # 透传给业务层进行频率限制判定
        }
        
    except Exception as e:
        logger.error(f"Write failed: {e}")
        return {"success": False, "error": str(e)}

def search_text(base_dir: str, path: str, query: str) -> dict:
    """在指定目录下递归搜索文本 (Grep)。"""
    try:
        target_path = os.path.normpath(os.path.join(base_dir, path))
        if not _is_path_safe(base_dir, target_path, level="R"):
            return {
                "success": False, 
                "error": f"Access denied: Path '{path}' is sensitive or blocked."
            }

        # 使用 PowerShell 的 Select-String 或简单的 git grep 逻辑 (如果可用)
        # 这里采用 Python 原生实现以保证跨平台稳定性
        matches = []
        for root, _, files in os.walk(target_path):
            for file in files:
                full_path = os.path.join(root, file)
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for i, line in enumerate(f, 1):
                            if query in line:
                                rel_path = os.path.relpath(full_path, base_dir)
                                matches.append(f"{rel_path}:{i}: {line.strip()}")
                except Exception:
                    continue
                if len(matches) > 50:
                    matches.append("... (too many matches, truncated)")
                    break
            if len(matches) > 50:
                break
        
        if not matches:
            return {"success": True, "result": "No matches found."}
        return {"success": True, "result": "\n".join(matches)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def find_files(base_dir: str, path: str, pattern: str) -> dict:
    """根据模式搜索文件 (Glob)。"""
    try:
        import fnmatch
        target_path = os.path.normpath(os.path.join(base_dir, path))
        if not _is_path_safe(base_dir, target_path, level="R"):
            return {
                "success": False, 
                "error": f"Access denied: Path '{path}' is sensitive or blocked."
            }

        matches = []
        for root, _, files in os.walk(target_path):
            for filename in fnmatch.filter(files, pattern):
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, base_dir)
                matches.append(rel_path)
                if len(matches) > 100:
                    matches.append("... (too many files, truncated)")
                    break
            if len(matches) > 100:
                break
        
        if not matches:
            return {"success": True, "result": f"No files matching '{pattern}' found."}
        return {"success": True, "result": "\n".join(matches)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_system_info() -> str:
    """获取基础系统信息。"""
    import datetime
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"Current System Time: {now}"
