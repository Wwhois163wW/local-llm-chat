#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
# infra/background_api.py
# Author: ZHU, W. phD
# License: https://csrs.riken.go.jp/en/labs/emart/index.html
# Date: 20260216
# Version: 1.5.1

import logging
import os
import shutil
import time
import platform
import sys
import re
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.session import ChatSession

logger = logging.getLogger(__name__)

def _get_base_anchor(session: ChatSession | None) -> str:
    """内部辅助：推导物理根路径。"""
    if not session:
        return "."
    if hasattr(session, "history_file") and session.history_file:
        try:
            return str(Path(session.history_file).resolve().parent.parent)
        except Exception:
            pass
    return getattr(session.resource_manager, "base_dir", ".") if hasattr(session, "resource_manager") else "."

def _resolve_element_alias(source: str, session: ChatSession | None) -> str:
    """
    [FUZZY-RESOLVER]: 解析别名或模糊路径。
    支持 path_n, url_n, block_n 等分类别名。
    """
    if not session or not hasattr(session, "resource_manager"):
        return source
        
    # 1. 尝试直接获取别名
    res_info = session.resource_manager.get_resource(source)
    if res_info:
        logger.info(f"[Resolver] Exact alias match: {source} -> {res_info['content'][:30]}...")
        return str(res_info["content"])
        
    # 2. 尝试纠正 LLM 的幻觉（如将 path_1 写成了 p_1 或简写的 1）
    s_lower = source.lower()
    mapping = {
        'p': 'path_', 'path': 'path_',
        'b': 'block_', 'block': 'block_',
        'u': 'url_', 'url': 'url_'
    }
    
    # 提取数字部分
    numeric_part = re.search(r'\d+', source)
    if not numeric_part: return source
    idx = numeric_part.group()

    # 意图引导匹配
    for prefix, target_cat in mapping.items():
        if s_lower.startswith(f"{prefix}_") or (s_lower.startswith(prefix) and len(s_lower) > len(prefix) and s_lower[len(prefix)].isdigit()):
            fuzzy_rid = f"{target_cat}{idx}"
            fuzzy_res = session.resource_manager.get_resource(fuzzy_rid)
            if fuzzy_res:
                logger.warning(f"[Resolver] Intention-based match: {source} -> {fuzzy_rid}")
                return str(fuzzy_res["content"])

    # 兜底：纯数字或未匹配到明确意图，尝试按默认顺序打捞
    if source.isdigit():
        for cat_prefix in ['path_', 'block_', 'url_']:
            fuzzy_rid = f"{cat_prefix}{idx}"
            fuzzy_res = session.resource_manager.get_resource(fuzzy_rid)
            if fuzzy_res:
                logger.warning(f"[Resolver] Default sequence recovery: {source} -> {fuzzy_rid}")
                return str(fuzzy_res["content"])

    return source

async def probe_and_load_resource(
    source_path: str, 
    session_obj: ChatSession | None,
    category: str = "path"
) -> dict[str, Any]:
    """
    执行资源探测、主动备份与 URM 注册。
    [RESOLVER-AWARE]: 深度支持全量要素别名解析。
    """
    if not session_obj or not hasattr(session_obj, "resource_manager"):
        return {"success": False, "error": "Session instance missing."}
        
    # 优先解析别名
    source_path = _resolve_element_alias(source_path, session_obj)

    # @Antigravity, 2026/02/12, [CACHE]: 检查现有映射...
    if source_path in session_obj.resource_manager.content_to_rid:
        rid = session_obj.resource_manager.content_to_rid[source_path]
        return {
            "success": True, 
            "rid": rid, 
        }

    # @Antigravity, 20260213, [STABLE]: 取消硬编码 ".", 优先基于 history_file 推导绝对锚点
    base_anchor = _get_base_anchor(session_obj)
    logger.info(f"Resolved base_anchor for probe/backup: {base_anchor}")
    
    # 1. 物理探测与权限校验
    from infra.tools import get_file_metadata
    white_list = session_obj.meta_manager.state.read_whitelist if session_obj else None
    res = get_file_metadata(base_anchor, source_path, white_list=white_list)
    
    if not res.get("success") or not res.get("result"):
        return {
            "success": False, 
            "error": res.get("error") or f"Failed to probe metadata for '{source_path}'."
        }
        
    # 2. [Safe Probe]: 探测即备份逻辑
    try:
        backup_dir = os.path.join(base_anchor, "staging", "backups")
        os.makedirs(backup_dir, exist_ok=True)
        ts = int(time.time())
        fname = os.path.basename(source_path)
        backup_path = os.path.join(backup_dir, f"{fname}.{ts}.probe.bak")
        shutil.copy2(os.path.join(base_anchor, source_path), backup_path)
        logger.info(f"Proactive backup created: {backup_path}")
    except Exception as be:
        logger.warning(f"Proactive backup failed for '{source_path}': {be}")

    # 3. 执行资源管理器注册 (使用新参数 category)
    rid = session_obj.resource_manager.register_resource(
        category=category,
        content=source_path,
        metadata=res["result"]
    )
    
    # 4. 认知同步：更新元数据
    meta_val = session_obj.resource_manager.get_resource_description(rid)
    # 我们不再使用 detected_resources_info，而是统一累加到 active_elements_info
    current_elements = session_obj.meta_manager.state.active_elements_info or ""
    if rid not in current_elements:
        new_elements = (current_elements + "\n" + meta_val).strip()
        session_obj.Update_Metadata_by_Key("active_elements_info", new_elements, persistent=False)
    
    return {
        "success": True, 
        "rid": rid, 
        "result": f"Resource loaded as {rid}. Proactive backup created. Metadata updated."
    }

# --- Task Handlers ---

async def _handle_load_resource(params: dict, session: ChatSession | None) -> dict:
    res_type = params.get("res_type", "file")
    source = str(params.get("source", ""))
    if res_type != "file":
        return {"success": False, "error": f"Resource type '{res_type}' not yet supported."}
    return await probe_and_load_resource(source, session)

async def _handle_read_resource(params: dict, session: ChatSession | None) -> dict:
    source = str(params.get("source", ""))
    start = params.get("start", 1)
    end = params.get("end", 100)
    
    if not session or not hasattr(session, "resource_manager"):
        return {"success": False, "error": "Session/URM unavailable."}
        
    res_data = session.resource_manager.get_resource(source)
    resolved_path = str(res_data["source"]) if res_data else ""
    
    if not resolved_path:
        load_res = await probe_and_load_resource(source, session)
        if not load_res.get("success"):
            error_msg = load_res.get("error", "Unknown error")
            return {
                "success": False, 
                "error": f"Auto-load failed for '{source}': {error_msg}. Please check if the path exists or list the directory first."
            }
        resolved_path = source

    from infra.tools import read_file
    base_anchor = _get_base_anchor(session)
    white_list = session.meta_manager.state.read_whitelist if session else None
    return read_file(
        base_dir=base_anchor, 
        path=resolved_path, 
        max_file_size_kb=500, 
        max_output_tokens=2000, 
        tokenizer=getattr(session, "tokenizer", None),
        start_line=start,
        end_line=end,
        white_list=white_list
    )

async def _handle_search_text(params: dict, session: ChatSession | None) -> dict:
    from infra.tools import search_text
    path = str(params.get("path", "."))
    query = str(params.get("query", ""))
    base_anchor = _get_base_anchor(session)
    white_list = session.meta_manager.state.read_whitelist if session else None
    return search_text(base_anchor, path, query, white_list=white_list)

async def _handle_find_files(params: dict, session: ChatSession | None) -> dict:
    from infra.tools import find_files
    path = str(params.get("path", "."))
    pattern = str(params.get("pattern", "*"))
    base_anchor = _get_base_anchor(session)
    white_list = session.meta_manager.state.read_whitelist if session else None
    return find_files(base_anchor, path, pattern, white_list=white_list)

async def _handle_list_dir(params: dict, session: ChatSession | None) -> dict:
    from infra.tools import list_dir
    path = str(params.get("path", "."))
    base_anchor = _get_base_anchor(session)
    white_list = session.meta_manager.state.read_whitelist if session else None
    return list_dir(base_anchor, path, white_list=white_list)

async def _handle_file_write(params: dict, session: ChatSession | None) -> dict:
    from infra.tools import write_file
    path = str(params.get("path", ""))
    content = str(params.get("content_to_write", ""))
    base_anchor = _get_base_anchor(session)
    res = write_file(base_anchor, path, content)
    if not res["success"] and "Access denied" in str(res.get("error")):
        res["error"] = "Access denied: Path out of bounds. Please write files within the project workspace."
    return res

async def _handle_get_session_stats(_params: dict, session: ChatSession | None) -> dict:
    if not session or not hasattr(session, "get_stats"):
        return {"success": False, "error": "Session stats unavailable."}
    stats = session.get_stats()
    return {"success": True, "result": stats}

async def _handle_get_system_info(_params: dict, _session: ChatSession | None) -> dict:
    info = {
        "os": platform.system(),
        "os_release": platform.release(),
        "python_version": sys.version.split()[0],
        "cwd": os.getcwd(),
        "node": platform.node()
    }
    return {"success": True, "result": info}

async def _handle_get_cwd(_params: dict, _session: ChatSession | None) -> dict:
    return {"success": True, "result": os.getcwd()}

async def _handle_echo(params: dict, _session: ChatSession | None) -> dict:
    message = params.get("message", "No message provided")
    return {
        "success": True, 
        "result": f"[Echo]: {message} | Security Word: 3+7=21",
        "metadata_key": "last_echo"
    }

async def _handle_execute_command(params: dict, session: ChatSession | None) -> dict:
    from infra.tools import execute_command
    cmd = str(params.get("command", ""))
    cwd = str(params.get("cwd", "."))
    timeout = int(params.get("timeout", 30))
    base_anchor = _get_base_anchor(session)
    return execute_command(base_anchor, cmd, cwd, timeout)

# --- Dispatcher Mapping ---

TASK_MAPPING = {
    "LoadResourceRequest": _handle_load_resource,
    "ReadResourceRequest": _handle_read_resource,
    "SearchTextRequest": _handle_search_text,
    "FindFilesRequest": _handle_find_files,
    "ListDirRequest": _handle_list_dir,
    "FileWriteRequest": _handle_file_write,
    "GetSystemInfoRequest": _handle_get_system_info,
    "GetSessionStatsRequest": _handle_get_session_stats,
    "GetCwdRequest": _handle_get_cwd,
    "EchoRequest": _handle_echo,
    "ExecuteCommandRequest": _handle_execute_command,
}

async def Execute_Task_by_Name(
    name: str, 
    params: dict[str, Any], 
    context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    负责异步执行指定的后台任务。
    """
    logger.info(f"Background API: Received task '{name}' with params {params}")
    session: ChatSession | None = context.get("session") if context else None
    
    handler = TASK_MAPPING.get(name)
    if not handler:
        return {"success": False, "error": f"Unknown task: {name}"}
    
    try:
        return await handler(params, session)
    except Exception as e:
        logger.error(f"Error executing task '{name}': {e}")
        return {"success": False, "error": str(e)}
