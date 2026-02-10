#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# infra/background_api.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260206
# Version: 1.2.3

import logging
import os
import platform
import sys
from typing import Any

logger = logging.getLogger(__name__)

async def Execute_Task_by_Name(
    name: str, 
    params: dict[str, Any], 
    context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    负责异步执行指定的后台任务。
    
    Args:
        name (str): 任务/工具名称。
        params (dict[str, Any]): 任务参数。
        context (dict[str, Any], optional): 执行上下文（如包含 session 对象）。
        
    Returns:
        dict[str, Any]: 执行结果。
    """
    logger.info(f"Background API: Received task '{name}' with params {params}")
    session = context.get("session") if context else None
    
    try:
        if name == "LoadResourceRequest":
            from infra.tools import get_file_metadata
            res_type = params.get("res_type", "file")
            source = str(params.get("source", ""))
            
            if res_type == "file":
                res = get_file_metadata(".", source)
                if res["success"]:
                    if session and hasattr(session, "resource_manager"):
                        # 核心：使用小写方法名对齐 URM 接口
                        rid = session.resource_manager.register_resource(
                            resource_type="file",
                            source=source,
                            metadata=res["result"]
                        )
                        # 注入元数据：这里是 URM 对 Metadata 系统的一个应用案例
                        meta_key = f"resource:{rid}"
                        # 构造描述文本块（使用 URM 语义描述接口）
                        meta_val = session.resource_manager.get_resource_description(rid)
                        session.Update_Metadata_by_Key(meta_key, meta_val, persistent=False)
                        
                        return {"success": True, "result": f"Resource loaded as {rid}. Metadata updated in memory."}
                    else:
                        return {"success": False, "error": "Internal Error: Session/URM instance missing during load."}
                return {"success": False, "error": res.get("error") or "Failed to probe file metadata."}

            return {"success": False, "error": f"Resource type '{res_type}' not yet implemented."}

        if name == "ReadResourceRequest":
            source = str(params.get("source", ""))
            if not session or not hasattr(session, "resource_manager"):
                return {"success": False, "error": "Session/URM unavailable."}
                
            # 1. 检查是否为 RID 模式
            res_data = session.resource_manager.get_resource(source)
            resolved_path = ""
            
            if res_data:
                # 命中 RID
                resolved_path = str(res_data["source"])
            else:
                # 视为路径模式，尝试自动加载（挂载）
                from infra.tools import get_file_metadata
                probe_res = get_file_metadata(".", source)
                if not probe_res["success"]:
                    return {"success": False, "error": f"Failed to auto-load path '{source}': {probe_res.get('error')}"}
                
                # 注册新资源
                rid = session.resource_manager.register_resource(
                    resource_type="file",
                    source=source,
                    metadata=probe_res["result"]
                )
                # 自动同步元数据记忆
                meta_key = f"resource:{rid}"
                meta_val = session.resource_manager.get_resource_description(rid)
                session.Update_Metadata_by_Key(meta_key, meta_val, persistent=False)
                resolved_path = source
                logger.info(f"Auto-loaded path '{source}' as {rid} before reading.")

            # 2. 调用内核读取工具执行分片读取
            from infra.tools import read_file
            res = read_file(
                base_dir=".", 
                path=resolved_path, 
                max_file_size_kb=500, 
                max_output_tokens=2000, 
                tokenizer=getattr(session, "tokenizer", None),
                start_line=params.get("start"),
                end_line=params.get("end")
            )
            return res

        if name == "ListDirRequest":
            from infra.tools import list_dir
            path = str(params.get("path", "."))
            res = list_dir(".", path)
            return res

        if name == "FileWriteRequest":
            from infra.tools import write_file
            path = str(params.get("path", ""))
            content_to_save = str(params.get("content_to_write", ""))
            res = write_file(".", path, content_to_save)
            return res

        if name == "GetSystemInfoRequest":
            info = {
                "os": platform.system(),
                "os_release": platform.release(),
                "python_version": sys.version.split()[0],
                "cwd": os.getcwd(),
                "node": platform.node()
            }
            return {"success": True, "result": info}
            
        if name == "GetCwdRequest":
            return {"success": True, "result": os.getcwd()}

        if name == "EchoRequest":
            message = params.get("message", "No message provided")
            # @Antigravity, 20260206, [FIX]: 恢复安全词注入，作为架构回环的固定验证点
            secret_word = "3+7=21"
            return {
                "success": True, 
                "result": f"[Echo]: {message} | Security Word: {secret_word}",
                "metadata_key": "last_echo"
            }

        return {"success": False, "error": f"Unknown task: {name}"}
    except Exception as e:
        logger.error(f"Error executing background task '{name}': {e}")
        return {"success": False, "error": str(e)}
