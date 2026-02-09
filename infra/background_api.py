#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# infra/background_api.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260206
# Version: 1.0.2

import logging
import asyncio
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
        if name == "UpdateMetadataRequest":
            if not session:
                return {"success": False, "error": "Session context missing for metadata update"}
            
            key = params.get("key")
            value = params.get("value")
            persistent = params.get("persistent", False)
            
            if not key:
                return {"success": False, "error": "Missing metadata key"}
                
            res_msg = session.Update_Metadata_by_Key(key, value, persistent)
            return {"success": True, "result": res_msg}



        if name == "LoadResourceRequest":
            from infra.tools import get_file_metadata
            res_type = params.get("res_type", "file")
            source = params.get("source")
            
            if res_type == "file":
                res = get_file_metadata(".", source)
                if res["success"]:
                    if session and hasattr(session, "resource_manager"):
                        # 核心：在 URM 注册并分配 RID
                        rid = session.resource_manager.Register_Resource(
                            res_type="file",
                            source=source,
                            metadata=res["metadata"]
                        )
                        # 自动更新元数据上下文
                        meta_key = f"resource:{rid}"
                        session.Update_Metadata_by_Key(
                            meta_key, 
                            session.resource_manager.Get_Resource_Context_Description(rid),
                            persistent=False
                        )
                        return {"success": True, "result": f"Resource loaded as {rid}. Metadata updated in memory."}
                return {"success": False, "error": res.get("error", "Failed to load resource.")}

            return {"success": False, "error": f"Resource type '{res_type}' not yet implemented."}

        if name == "InjectResourceRequest":
            rid = params.get("rid")
            if not session or not hasattr(session, "resource_manager"):
                return {"success": False, "error": "Session/URM unavailable."}
                
            res_data = session.resource_manager.Get_Resource_by_RID(rid)
            if not res_data:
                return {"success": False, "error": f"Resource {rid} not found in registry."}
            
            if res_data["type"] == "file":
                from infra.tools import read_file
                p = res_data["source"]
                s_range = params.get("slice_range", {})
                
                res = read_file(
                    base_dir=".", 
                    path=p, 
                    max_file_size_kb=500, 
                    max_output_tokens=2000, 
                    tokenizer=getattr(session, "tokenizer", None),
                    start_line=s_range.get("start"),
                    end_line=s_range.get("end")
                )
                if res["success"]:
                    return {"success": True, "result": res["content"]}
                return {"success": False, "error": res["error"]}





        if name == "ListDirRequest":
            from infra.tools import list_dir
            path = params.get("path", ".")
            res = list_dir(".", path)
            return res



        if name == "FileWriteRequest":
            from infra.tools import write_file
            path = params.get("path")
            content_to_save = params.get("content_to_write", "")
            res = write_file(".", path, content_to_save)
            return res

        if name == "SystemInfoRequest":
            from infra.tools import get_system_info
            res = get_system_info()
            return {"success": True, "result": res}
            
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
