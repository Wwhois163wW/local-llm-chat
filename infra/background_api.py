#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
# infra/background_api.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260213
# Version: 1.4.1

import logging
import os
import shutil
import time
import platform
import sys
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

async def probe_and_load_resource(
    source_path: str, 
    session_obj: ChatSession | None
) -> dict[str, Any]:
    """
    # @Antigravity, 20260213, [REF]: 外部化资源加载逻辑，精简 Execute_Task_by_Name 体积并统一调用入口。
    执行资源探测、主动备份与 URM 注册。
    """
    if not session_obj or not hasattr(session_obj, "resource_manager"):
        return {
            "success": False, 
            "error": "Internal Error: Session/URM instance missing."
        }
        
    # @Antigravity, 2026/02/12, [CACHE]: 预检查逻辑。如果物理源已存在于 URM，直接复用。
    if source_path in session_obj.resource_manager.source_to_rid:
        rid = session_obj.resource_manager.source_to_rid[source_path]
        logger.info(f"Source '{source_path}' hit existing RID: {rid}. Skipping re-load.")
        return {
            "success": True, 
            "rid": rid, 
            "result": f"Resource hit existing ID: {rid}. Re-used metadata."
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
        
    # 2. [Safe Probe]: 探测即备份逻辑 (响应用户建议)
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

    # 3. 执行资源管理器注册
    rid = session_obj.resource_manager.register_resource(
        resource_type="file",
        source=source_path,
        metadata=res["result"]
    )
    
    # 4. 认知同步：更新元数据
    meta_key = f"resource:{rid}"
    meta_val = session_obj.resource_manager.get_resource_description(rid)
    session_obj.Update_Metadata_by_Key(meta_key, meta_val, persistent=False)
    
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
            return load_res
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
