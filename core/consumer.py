#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# core/consumer.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 20260206
# Version: 1.2.0

import asyncio
import logging
import configparser
import json
from typing import Any, cast
from dataclasses import asdict
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
    FileWriteRequest,
    Event,
    ExecuteCommandRequest,
    MalformedAction
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
                
                # [NEW]: 特殊 Token 拦截处理 (降噪处理)
                elif isinstance(event, SpecialTokenDetected):
                    logger.debug(f"Detected special token: {event.token}")
                
                # [轨道 B] 架构动作轨道 (解析流产生的所有非文本、非统计事件)
                elif not isinstance(event, StatsUpdate):
                    action_triggered = True
                    
                    if isinstance(event, MalformedAction):
                        obs_result = (
                            f"[Error]: Detected malformed or unrecognized tool call: {event.raw_tag}. "
                            "Please strictly follow the tool definitions and parameters provided in the prompt."
                        )
                    else:
                        obs_result = await handle_generic_action(
                            event, 
                            session
                        )
                    
                    if obs_result:
                        observations.append(obs_result)
                        # @Antigravity, 2026/02/11, [ADD]: Debug 模式下的实时反馈增强
                        if getattr(agent, "debug_mode", False):
                            print(f"\n[Debug Observation] 👁️ {obs_result}", flush=True)
            
            print() # 视觉换行
            
            # @Antigravity, 2026/02/12, [SMART]: 语义密度管理。如果 Observation 过长，执行主动信息提取
            # 以防止注入 ChatSession 后导致物理 Context 崩溃。
            optimized_observations: list[str] = []
            for obs in observations:
                if len(obs) > 1000: # 粗略字符预估，超过 1000 字符尝试提取
                    logger.info(f"[Consumer] Large observation (len={len(obs)}) detected. Extracting key info...")
                    from core.summarizer import Extract_Key_Info_by_LLM
                    sem_obs = await Extract_Key_Info_by_LLM(
                        session.client,
                        session.summary_model,
                        obs
                    )
                    optimized_observations.append(sem_obs)
                else:
                    optimized_observations.append(obs)

            # 【时序保证】：在 Assistant 消息记录完成后，统一注入观察结果
            for obs in optimized_observations:
                session.Inject_Tool_Observation(obs)
            
            # 只有当触发了动作且有反馈时，才考虑进入下一轮继续思考
            keep_looping = action_triggered
                
        except Exception as e:
            # @Antigravity, 20260210, [NEW]: 引入超时反馈重试机制
            original_error = str(e)
            is_timeout = "timed out" in original_error.lower() or "timeout" in original_error.lower()
            
            if is_timeout and turn_count <= 2: # Compensate for transient timeouts
                logger.warning(f"Turn {turn_count} timed out. Injecting feedback for retry...")
                retry_msg = (
                    "[Observation]: The last inference timed out due to long response time. Suggestions:\n"
                    "1. If the task is too complex, try breaking it into simpler sub-tasks.\n"
                    "2. If the previous CoT was too long, be more concise and call relevant tools directly.\n"
                    "3. Please re-evaluate the current state and perform the next step."
                )
                session.Inject_Tool_Observation(retry_msg)
                turn_count += 1
                continue
            
            logger.error(f"Error during turn {turn_count}: {e}", exc_info=True)
            break

    # @Antigravity, 2026/02/12, [DECOUPLE]: 将阈值计算下沉至 Session 层
    # 判别逻辑现在完全由 session.should_compress() 负责，不再依赖外部 config
    if session.should_compress():
        logger.info("[Consumer] Context density reached threshold. Summarizing...")
        from core.summarizer import Summarize_Conversation_by_LLM
        summary = await Summarize_Conversation_by_LLM(
            session.client,
            session.summary_model,
            session.chat_history
        )
        if summary and not summary.startswith("Summary failed"):
            session.Update_Metadata_by_Key("context_summary", summary, persistent=True)
            # 压缩后清除非持久化的旧历史以释放物理空间
            # 保留最后 2 条消息以维持交互连贯性
            if len(session.chat_history) > 2:
                session.chat_history = session.chat_history[-2:]
                logger.info("[Consumer] Memory flushed. Kept last 2 messages.")

def Is_Command_Safe_for_AutoRun(command: str) -> bool:
    """
    基于用户全局安全规则，识别无需确认即可执行的只读指令。
    """
    safe_prefixes = [
        "ls", "dir", "pwd", "date", "whoami", "hostname",
        "git status", "git branch", "git log", "git rev-parse",
        "netsh wlan show", "python --version", "pip --version",
        "Get-ChildItem", "Get-Item", "Test-Path", "type ", "cat "
    ]
    cmd_clean = command.strip().lower()
    return any(cmd_clean.startswith(p) for p in safe_prefixes)

async def handle_generic_action(
    event: Event, 
    session: ChatSession
) -> str | None:
    """
    语义动作分发器。
    基于 event.act_type 执行安全决策、审计追踪与任务驱动。
    """
    task_name = type(event).__name__
    params = asdict(event)
    act_type = getattr(event, "act_type", "Unknown")
    
    # @Antigravity, 2026/02/13, [UI]: 降噪重构。在终端使用更紧凑的单行输出，弱化审计噪音。
    print(f"[System] ⚙️ {task_name} ({act_type})...", end="\r", flush=True)
    
    # 状态预检：频率限制 (Create vs Create)
    last_type = session.meta_manager.state.last_action_type
    
    # --- 架构短路：Core 层元数据直连 (视为 Update 行为) ---
    if isinstance(event, UpdateMetadataRequest):
        res_msg = session.Update_Metadata_by_Key(
            key=params.get("key", ""),
            value=params.get("value"),
            persistent=params.get("persistent", False)
        )
        session.meta_manager.update_state("last_action_type", "Update", context="Internal Logic")
        return res_msg
        
    if isinstance(event, GetMetadataRequest):
        session.meta_manager.update_state("last_action_type", "Read", context="Internal Logic")
        key_path = params.get("key")
        full_meta = session.get_metadata()
        
        if not key_path:
            return f"Metadata Snapshot:\n{json.dumps(full_meta, indent=2, ensure_ascii=False)}"
            
        parts = key_path.replace(":", ".").split(".")
        current = full_meta
        for p in parts:
            if isinstance(current, dict) and p in current:
                current = current[p]
            else:
                return f"[Observation]: Metadata key '{key_path}' not found (missing at segment '{p}')."
        
        return f"[Observation]: Metadata '{key_path}' value: {current}"
    
    # --- 转发至基础设施层 ---
    # [Pre-check for Command Execution]: 遵循用户全局安全规则，非白名单指令必须手动确认
    if isinstance(event, ExecuteCommandRequest):
        cmd_str = params.get("command", "")
        # @Antigravity, 2026/02/12, [SAFE]: 引入白名单加速
        if not Is_Command_Safe_for_AutoRun(cmd_str):
            print(f"\n[Security Alert] AI is requesting to execute a potentially sensitive command:")
            print(f"Command: {cmd_str}")
            print(f"CWD: {params.get('cwd', '.')}")
            
            user_choice = await asyncio.to_thread(input, "Allow execution? (y/n) > ")
            if user_choice.lower() != 'y':
                logger.info(f"User rejected command: {cmd_str}")
                return f"[Observation]: User rejected the command: {cmd_str}"
        else:
            logger.info(f"Auto-running safe command: {cmd_str}")

    # [Cognitive Write Check]: Intent is based on URM cognition
    if isinstance(event, FileWriteRequest):
        target_path = params.get("path", "")
        # @Antigravity, 2026/02/12, [REF]: Use URM to determine C/U
        resource_record = session.resource_manager.get_resource(target_path)
        # 修正事件意图：未加载的写一律视为 Create
        if resource_record is None:
            event.act_type = "Create"
            act_type = "Create"

        if act_type == "Create" and last_type == "Create":
            logger.warning("Blocked consecutive Create attempt.")
            return (
                "[Observation]: Create blocked. Consecutive creation is prohibited. "
                "Please perform a 'Read' (or Load) to verify state or provide deeper <thought> before creating."
            )
    # @zhu, 20260211, [MARK] 交给后台
    res: dict[str, Any] = await Execute_Task_by_Name(
        task_name, 
        params, 
        context={"session": session}
    )
    
    if not res.get("success") and res.get("error") == "UNCERTAIN_PERMISSION":
        uncertain_path = res.get("uncertain_path", "Unknown Path")
        print(f"\n[Permission Request] AI is requesting access to a path outside the workspace:")
        print(f"Path: {uncertain_path}")
        
        user_choice = await asyncio.to_thread(input, "Allow access and add to whitelist? (y/n) > ")
        if user_choice.lower() == 'y':
            current_list = list(session.meta_manager.state.read_whitelist)
            if uncertain_path not in current_list:
                current_list.append(uncertain_path)
                session.Update_Metadata_by_Key("read_whitelist", current_list, persistent=True)
                logger.info(f"Path whitelisted: {uncertain_path}")
            
            print(f"[System] Permission granted. Retrying {task_name}...")
            res = await Execute_Task_by_Name(task_name, params, context={"session": session})
        else:
            logger.info(f"User denied access to: {uncertain_path}")
            return f"[Observation]: Access denied by user for path: {uncertain_path}"

    if not res.get("success"):
        return f"[Error]: Execution of '{task_name}' failed: {res.get('error')}"
    
    # 动作追踪：同步物理操作的真实意图
    actual_type = res.get("action_type") or act_type
    session.meta_manager.update_state("last_action_type", actual_type, context="Action Tracking")
    
    return cast(str | None, res.get("result"))
