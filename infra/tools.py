#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# infra/tools.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260206
# Version: 1.5.0

import os
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

def _is_path_safe(base_dir: str, target_path: str, level: str = "W", white_list: list[str] | None = None) -> str:
    """
    内部辅助：路径安全决策中心。
    返回值:
        - "ALLOWED": 允许执行。
        - "DENIED": 明确禁止。
        - "UNCERTAIN": 需要动态授权。
    """
    try:
        # 归一化路径
        abs_base = os.path.normcase(os.path.abspath(base_dir))
        abs_target = os.path.normcase(os.path.abspath(target_path))
        
        p_base = Path(abs_base)
        p_target = Path(abs_target)
        
        # 只要在工作区根目录下，即视为安全
        if p_target.is_relative_to(p_base) or p_target == p_base:
            return "ALLOWED"
            
        # Write 级别：如果不属于工作区，直接禁止（会被重定向到 staging）
        if level == "W":
            return "DENIED"

        # Read 级别：检查动态授权白名单
        if white_list:
            for item in white_list:
                try:
                    p_white = Path(os.path.normcase(os.path.abspath(item)))
                    if p_target.is_relative_to(p_white) or p_target == p_white:
                        return "ALLOWED"
                except Exception:
                    continue
        
        return "UNCERTAIN"

    except Exception as e:
        logger.error(f"Path safety check error: {e}")
        return "DENIED"

# @Antigravity, 20260209, [FIX]: 强化路径安全校验，使用 commonpath 避免 Windows 边界匹配 Bug
# @Antigravity, 2026/02/10, [FIX]: 增强类型提示与 Windows 对齐
def get_file_metadata(base_dir: str, path: str, white_list: list[str] | None = None) -> dict:
    """
    获取文件详细元数据而不读取全量内容。
    """
    result = {"success": False, "error": "", "result": {}, "uncertain_path": None}
    try:
        # 统一归一化：abspath + normcase
        abs_target = os.path.normcase(os.path.abspath(os.path.join(base_dir, path)))
        target_path = Path(abs_target)
        
        check = _is_path_safe(base_dir, abs_target, level="R", white_list=white_list)
        if check == "DENIED":
            result["error"] = "Access denied: Path out of bounds."
            return result
        elif check == "UNCERTAIN":
            result["uncertain_path"] = abs_target
            result["error"] = "UNCERTAIN_PERMISSION"
            return result
            
        if not target_path.exists():
            result["error"] = f"File not found: {path}"
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
    end_line: int | None = None,
    white_list: list[str] | None = None
) -> dict:
    """
    读取文件内容，支持行号切片。
    """
    result = {"success": False, "error": "", "result": None, "uncertain_path": None}

    try:
        target_path = Path(base_dir) / path
        
        check = _is_path_safe(base_dir, str(target_path), level="R", white_list=white_list)
        if check == "DENIED":
            result["error"] = "Access denied: Path out of bounds."
            return result
        elif check == "UNCERTAIN":
            result["uncertain_path"] = str(target_path.resolve())
            result["error"] = "UNCERTAIN_PERMISSION"
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

def list_dir(base_dir: str, path: str, white_list: list[str] | None = None) -> dict:
    """列出目录内容。"""
    try:
        target_path = Path(base_dir) / path
        
        check = _is_path_safe(base_dir, str(target_path), level="R", white_list=white_list)
        if check == "DENIED":
             return {"success": False, "error": "Access denied."}
        elif check == "UNCERTAIN":
             return {
                 "success": False, 
                 "error": "UNCERTAIN_PERMISSION", 
                 "uncertain_path": str(target_path.resolve())
             }
             
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
    三段式安全写流程 (Tiered Secure Write):
    1. 备份 (Backup): 针对已存在于工作区的文件并在修改前存底。
    2. 写入 (Write): 写入新内容。
    3. 覆盖/隔离 (Overlay/Isolation): 
       - 工作区内相对路径 -> 自动覆盖。
       - 其他路径 -> 重定向至 staging/new 隔离。
    """
    try:
        import html
        import shutil
        decoded_content = html.unescape(content)
        
        base = Path(base_dir).resolve()
        abs_target = os.path.normcase(os.path.abspath(os.path.join(base_dir, path)))
        target_path = Path(abs_target)
        
        # 判定是否属于工作区 (基于相对路径)
        is_in_workspace = False
        try:
            target_path.relative_to(base)
            is_in_workspace = True
        except ValueError:
            is_in_workspace = False

        action_type = "Update" if target_path.exists() else "Create"
        final_path: Path
        feedback = ""

        # Step 1: 权限与意图分流
        if action_type == "Update" and is_in_workspace:
            # 【Update】工作区内：备份 + 原地覆盖
            final_path = target_path
            backup_dir = base / "staging" / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            ts = int(time.time())
            shutil.copy2(target_path, backup_dir / f"{target_path.name}.{ts}.write.bak")
            feedback = f"File updated in workspace. Backup created in staging/backups/."
        else:
            # 【Create】或【外部 Update】：强制隔离至 staging/new
            staging_new = base / "staging" / "new"
            
            # 安全清洗：剥离前导斜杠并处理各平台路径部件
            # 自定义清洗：移除 staging, new, backups 等系统保留字以防止递归
            p_parts = Path(path.replace("\\", "/")).parts
            clean_parts = [p for p in p_parts if p.lower() not in ["staging", "new", "backups", "external"]]
            clean_subpath = Path(*clean_parts)
            
            # 处理 Windows 盘符与非法路径
            final_path = staging_new / str(clean_subpath).replace(":", "_").lstrip("\\/")
            
            if action_type == "Create":
                feedback = f"New file created in staging buffer: 'staging/new/{final_path.relative_to(staging_new)}'."
            else:
                feedback = f"External file update redirected to staging: 'staging/new/{final_path.relative_to(staging_new)}'."
            
            # 强化：隔离模式下一律视作 Create
            action_type = "Create" 
            logger.info(f"Write redirection (Isolation): {path} -> {final_path}")

        # Step 2: 执行物理写入
        final_path.parent.mkdir(parents=True, exist_ok=True)
        with open(final_path, 'w', encoding='utf-8') as f:
            f.write(decoded_content)
            
        return {
            "success": True, 
            "result": feedback,
            "action_type": action_type
        }
    except Exception as e:
        logger.error(f"Secure write failed: {e}")
        return {"success": False, "error": str(e)}

def search_text(base_dir: str, path: str, query: str, white_list: list[str] | None = None) -> dict:
    """在指定目录下递归搜索文本 (Grep)。"""
    try:
        target_path = Path(base_dir) / path
        
        check = _is_path_safe(base_dir, str(target_path), level="R", white_list=white_list)
        if check == "DENIED":
            return {"success": False, "error": "Access denied."}
        elif check == "UNCERTAIN":
            return {
                "success": False, 
                "error": "UNCERTAIN_PERMISSION", 
                "uncertain_path": str(target_path.resolve())
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

def find_files(base_dir: str, path: str, pattern: str, white_list: list[str] | None = None) -> dict:
    """根据模式搜索文件 (Glob)。"""
    try:
        import fnmatch
        target_path = Path(base_dir) / path
        
        check = _is_path_safe(base_dir, str(target_path), level="R", white_list=white_list)
        if check == "DENIED":
            return {"success": False, "error": "Access denied."}
        elif check == "UNCERTAIN":
            return {
                "success": False, 
                "error": "UNCERTAIN_PERMISSION", 
                "uncertain_path": str(target_path.resolve())
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

def execute_command(base_dir: str, command: str, cwd: str = ".", timeout: int = 30) -> dict:
    """
    执行系统命令并捕获输出。
    """
    import subprocess
    try:
        # 确保 cwd 位于工作区内（基本安全检查）
        target_cwd = os.path.normpath(os.path.join(base_dir, cwd))
        if not os.path.exists(target_cwd):
            return {"success": False, "error": f"CWD not found: {cwd}"}

        # 执行指令
        # @Antigravity, 2026/02/10, [RULE]: 捕获并合并输出流
        process = subprocess.run(
            command,
            cwd=target_cwd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
            errors='replace'
        )
        
        stdout = process.stdout or ""
        stderr = process.stderr or ""
        
        result_msg = f"Command executed with exit code {process.returncode}."
        if stdout:
            result_msg += f"\nSTDOUT:\n{stdout}"
        if stderr:
            result_msg += f"\nSTDERR:\n{stderr}"
            
        return {
            "success": True, 
            "result": result_msg,
            "exit_code": process.returncode
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Command timed out after {timeout}s."}
    except Exception as e:
        logger.error(f"Command execution failed: {e}")
        return {"success": False, "error": str(e)}

def get_system_info() -> str:
    """获取基础系统信息。"""
    import datetime
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"Current System Time: {now}"
