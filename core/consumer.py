#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/consumer.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260206
# Version: 0.0.2

import asyncio
import logging
import configparser
import json
import os
from typing import Any, cast
from dataclasses import asdict
from openai import AsyncOpenAI

from core.agent import Agent
from core.session import ChatSession
from core.events import (
    TextChunk, 
    StatsUpdate, 
    UpdateMetadataRequest, 
    GetMetadataRequest,
    Thought,
    FinalAnswer,
    SpecialTokenDetected,
    FileWriteRequest
)
from infra.background_api import Execute_Task_by_Name

logger = logging.getLogger(__name__)

_SECTION_TITLE = "\n=== AI Agent CLI (Async Turn Architecture) ==="
_SECTION_WELCOME = "Commands: quit, exit, goodbye"

async def consume_events(
    agent: Agent, 
    chat_session: ChatSession, 
    config: configparser.ConfigParser
) -> None:
    """
    运行 Agent 的主交互循环（CLI 界面）。

    Args:
        agent (Agent): 绑定的 Agent 实例。
        chat_session (ChatSession): 当前对话会话对象。
        config (configparser.ConfigParser): 应用程序配置。
    """
    # @Antigravity, 20260206, [CLEANUP]: 移除冗余标注，应用架构收官标准
    print(_SECTION_TITLE)
    print(_SECTION_WELCOME)
    
    # 获取转数限制，架构层只关心控制参数
    max_turns: int = config.getint('Agent', 'max_turns', fallback=3)

    while True:
        try:
            # 1. 用户输入阶段
            user_input: str = await asyncio.to_thread(input, "\nYou > ")
            if user_input.lower() in ["quit", "exit", "goodbye"]:
                break
            
            # 2. 存入内存与磁盘
            chat_session.add_conversation_message('user', user_input)
            
            # 3. 启动 Turn Loop (多轮思考与执行)
            await process_turns(agent, chat_session, max_turns)
            
        except (KeyboardInterrupt, EOFError):
            break
        except Exception as e:
            logger.error(f"Error in main interaction loop: {e}", exc_info=True)
            break

async def process_turns(
    agent: Agent, 
    session: ChatSession, 
    max_turns: int
) -> None:
    """
    管理多轮 Agent 思考 (Turn Loop) 及其动作的分发与反馈注入。

    Args:
        agent (Agent): 执行推理的 Agent 实例。
        session (ChatSession): 会话状态容器。
        max_turns (int): 允许的最大递归思维深度。
    """
    turn_count: int = 0
    keep_looping: bool = True
    
    while keep_looping and turn_count < max_turns:
        turn_count += 1
        action_triggered: bool = False
        observations: list[str] = [] # 暂存本轮所有的动作反馈
        
        if turn_count > 1:
            print(
                f"\n[System] 🔄 Turn {turn_count}: "
                f"LLM is re-thinking based on observations..."
            )

        print(f"LLM > ", end="", flush=True)
        
        try:
            # 迭代流事件，基于极简 Agent 直接产出的事件流
            async for event in agent.run():
                # [轨道 A.1] 思维链路轨道
                if isinstance(event, Thought):
                    print(f"\n[Thought] 🧠 {event.content}", flush=True)

                # [轨道 A.2] 最终答案轨道
                elif isinstance(event, FinalAnswer):
                    print(f"\n[Final Answer] ✨ {event.content}", flush=True)
                    keep_looping = False # 显式结束 Turn Loop

                # [轨道 A.3] 即时渲染轨迹
                elif isinstance(event, TextChunk):
                    print(event.content, end="", flush=True)
                
                # [NEW]: 特殊 Token 拦截处理
                elif isinstance(event, SpecialTokenDetected):
                    logger.warning(f"Detected special token: {event.token}")
                    warning_msg = (
                        f"[Observation]: 检测到非标准指令格式 '<|{event.token}|>'。 "
                        "请注意：由于系统安全限制，此类指令已被拦截。请仅使用定义的 XML 标签执行操作。"
                    )
                    observations.append(warning_msg)
                    action_triggered = True # 触发下一轮修正
                
                # [轨道 B] 架构动作轨道 (解析流产生的所有非文本、非统计事件)
                elif not isinstance(event, StatsUpdate):
                    action_triggered = True
                    # 动态映射：任务名=类名，参数=asdict
                    task_name: str = type(event).__name__
                    params: dict[str, Any] = asdict(event)
                    
                    obs_result = await handle_generic_action(
                        task_name, 
                        params, 
                        session
                    )
                    if obs_result:
                        observations.append(obs_result)
            
            print() # 视觉换行
            
            # 【时序保证】：在 Assistant 消息记录完成后，统一注入观察结果
            for obs in observations:
                session.Inject_Tool_Observation(obs)
            
            # 只有当触发了动作且有反馈时，才考虑进入下一轮继续思考
            keep_looping = action_triggered
                
        except Exception as e:
            # @Antigravity, 20260210, [NEW]: 引入超时反馈重试机制
            original_error = str(e)
            is_timeout = "timed out" in original_error.lower() or "timeout" in original_error.lower()
            
            if is_timeout and turn_count <= 2: # 仅在起始几轮且未超重试限额时补救
                logger.warning(f"Turn {turn_count} timed out. Injecting feedback for retry...")
                retry_msg = (
                    "[Observation]: 上次推理由于响应时间过长而超时。建议如下：\n"
                    "1. 如果任务过于复杂，请尝试将其拆分为多个简单的子任务执行。\n"
                    "2. 如果之前的思考路径太长，请精简逻辑，直接调用最相关的工具。\n"
                    "3. 请针对当前状态重新进行 <thought> 并执行下一步。"
                )
                session.Inject_Tool_Observation(retry_msg)
                # @Antigravity, 20260210, [FIX]: 确保 continue 前步进计数器，防止死循环
                turn_count += 1
                continue
            
            logger.error(f"Error during turn {turn_count}: {e}", exc_info=True)
            break

    # @Antigravity, 20260210, [NEW]: 对话压缩触发点
    if len(session.chat_history) >= session.compression_threshold * 2:
        logger.info("[Consumer] History reached threshold. Triggering summarization...")
        from core.summarizer import Summarize_Conversation_by_LLM
        # [FIX]: 确保传递的是异步客户端
        summary = await Summarize_Conversation_by_LLM(
            session.client,
            session.summary_model,
            session.chat_history
        )
        if summary and not summary.startswith("Summary failed"):
            session.Update_Metadata_by_Key("context_summary", summary, persistent=True)

async def handle_generic_action(
    task_name: str, 
    params: dict[str, Any], 
    session: ChatSession
) -> str | None:
    """
    通用动作分发器。
    引入 CRUD 频率限制：不允许连续执行 Create 动作。
    """
    print(f"\n[System] ⚙️ Executing {task_name}...")
    
    # 状态预检：频率限制 (Create vs Create)
    last_type = session.meta_manager.state.last_action_type
    
    # --- 架构短路：Core 层元数据直连 (视为 Update 行为) ---
    if task_name == UpdateMetadataRequest.__name__:
        res_msg = session.Update_Metadata_by_Key(
            key=params.get("key", ""),
            value=params.get("value"),
            persistent=params.get("persistent", False)
        )
        session.meta_manager.update_state("last_action_type", "Update", context="Internal Logic")
        return res_msg
        
    if task_name == GetMetadataRequest.__name__:
        session.meta_manager.update_state("last_action_type", "Read", context="Internal Logic")
        # ... (省略 10 行提取逻辑) ...
        key = params.get("key")
        full_meta = session.get_metadata()
        if key:
            val = full_meta.get(key)
            if val is not None: return f"Metadata '{key}' value: {val}"
            return f"Metadata '{key}' not found."
        return f"Metadata Snapshot:\n{json.dumps(full_meta, indent=2, ensure_ascii=False)}"
    
    # --- 转发至基础设施层 ---
    # [Pre-check for Write]: 我们需要先探测是 C 还是 U (基于路径存在性)
    if task_name == FileWriteRequest.__name__:
        target_path = params.get("path", "")
        base_dir = "." # 默认工作区
        full_path = os.path.normpath(os.path.join(base_dir, target_path))
        is_create = not os.path.exists(full_path)
        
        if is_create and last_type == "Create":
            logger.warning("Blocked consecutive Create attempt.")
            return (
                "[Observation]: Create 被拦截。系统禁止连续执行创建动作。 "
                "请先执行一次 Read 操作查看当前状态，或进行一段深入的 <thought> 后再尝试创建。"
            )

    res: dict[str, Any] = await Execute_Task_by_Name(task_name, params, context={"session": session})
    
    if not res.get("success"):
        # 即使失败也记录当前尝试的动作类型（如果是写操作）
        return f"[Error]: Execution of '{task_name}' failed: {res.get('error')}"
    
    # 更新动作追踪
    actual_type = res.get("action_type")
    if not actual_type:
        # 推断映射
        if task_name in ["ReadResourceRequest", "ListDirRequest", "FindFilesRequest", "SearchTextRequest", "GetSystemInfoRequest"]:
            actual_type = "Read"
        elif task_name == "FileWriteRequest":
            actual_type = "Update" # 兜底值
            
    if actual_type:
        session.meta_manager.update_state("last_action_type", actual_type, context="Action Tracking")
    
    return cast(str | None, res.get("result"))
