#!/usr/bin/env python3
# -*- coding: utf-8 -*- 
# model_selector.py
# Author: ZHU, W. phD
# License: https://csrs.riken.jp/en/labs/emart/index.html
# Date: 2026/02/12
# Version: 1.0.0

import asyncio
import time
import configparser
import os
import sys
import requests
from typing import Any
from openai import AsyncOpenAI

# @Antigravity, 2026/02/12, [NEW]: 智能模型选择与性能对标工具

async def Benchmark_Model(
    client: AsyncOpenAI, 
    model_id: str,
    native_meta: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    测量特定模型的响应延迟（对标性能）。
    """
    start_time = time.perf_counter()
    try:
        # 发送最简提示词进行延迟测试
        response = await client.chat.completions.create(
            model=model_id, 
            messages=[{
                "role": "user", 
                "content": "Hi"
            }], 
            max_tokens=5
        )
        end_time = time.perf_counter()
        latency = end_time - start_time
        
        # @Antigravity, 2026/02/12, [SYNC]: 使用注入的 LM Studio 原生元数据
        context_len = 0
        if native_meta:
            # 优先选择已加载实例的配置（最准确），回退至模型物理上限
            loaded = native_meta.get("loaded_instances", [])
            if loaded:
                context_len = loaded[0].get("config", {}).get("context_length", 0)
            
            if not context_len:
                context_len = native_meta.get("max_context_length", 0)

        return {
            "model": model_id, 
            "success": True, 
            "latency": latency, 
            "tokens": response.usage.total_tokens if response.usage else 0,
            "context_length": int(context_len) if context_len else 0
        }
    except Exception as e:
        return {
            "model": model_id, 
            "success": False, 
            "error": str(e)
        }

async def Main_Process() -> None:
    """工具主逻辑。"""
    print("=== Smart Model Switcher for LM Studio ===")
    
    config = configparser.ConfigParser()
    script_dir = os.path.dirname(
        os.path.abspath(__file__)
    )
    config_path = os.path.join(script_dir, "config.ini")
    
    if not os.path.exists(config_path):
        print(f"Error: {config_path} not found.")
        return

    config.read(config_path, encoding='utf-8')
    ip = config.get("LLM", "ip", fallback="127.0.0.1")
    port = config.get("LLM", "port", fallback="1234")
    api_key = config.get("LLM", "api_key", fallback="lm-studio")
    current_model = config.get("LLM", "model", fallback="unknown")
    
    base_url = f"http://{ip}:{port}/v1"
    client = AsyncOpenAI(
        api_key=api_key, 
        base_url=base_url
    )
    
    print(f"Connecting to: {base_url} ...")
    
    try:
        # 0. [NEW] 获取 LM Studio 原生元数据映射
        native_map = {}
        try:
            native_url = f"http://{ip}:{port}/api/v1/models"
            resp = requests.get(native_url, timeout=3)
            if resp.status_code == 200:
                models_data = resp.json().get("models", [])
                native_map = {m["key"]: m for m in models_data}
        except Exception as e:
            print(f"[Warning] Native API probe failed: {e}")

        # 1. 获取模型列表
        models_response = await client.models.list()
        # @Antigravity, 2026/02/12, [RULE]: 遵循列表推导式分行规则
        available_models = [m.id 
                            for m in models_response.data
                           ]
        
        if not available_models:
            print("No models found on LM Studio.")
            return
            
        print(f"Found {len(available_models)} models. Checking load status...")
        
        # 2. 区分已加载与未加载模型，避免自动冷启动 (Prevent Auto-Loading)
        loaded_models = []
        unloaded_results = []
        
        for mid in available_models:
            meta = native_map.get(mid, {})
            if meta.get("loaded_instances"):
                loaded_models.append(mid)
            else:
                # 对未加载模型，记录静态结果而不进行 Benchmark
                unloaded_results.append({
                    "model": mid,
                    "success": True,
                    "latency": 999.0, # 排序至最后
                    "context_length": int(meta.get("max_context_length", 0)),
                    "is_loaded": False
                })

        # 3. 仅对已加载模型并发对标性能
        benchmark_results = []
        if loaded_models:
            print(f"Benchmarking {len(loaded_models)} loaded models...")
            tasks = [
                Benchmark_Model(client, mid, native_map.get(mid)) 
                for mid in loaded_models
            ]
            raw_res = await asyncio.gather(*tasks)
            for r in raw_res:
                r["is_loaded"] = True
                benchmark_results.append(r)
        
        # 合并结果
        results = benchmark_results + unloaded_results
        
        # 按延迟排序（成功的排前面，未加载的排最后）
        sorted_results = sorted(
            results, 
            key=lambda x: (not x.get("is_loaded", False), x.get("latency", 999)) 
        )
        
        # 3. 打印结果表格
        print("\n" + "-" * 88)
        print(
            f"{'ID':<4} | {'Model Name':<35} | {'Latency':<10} | {'Context':<8} | {'Status'}"
        )
        print("-" * 88)
        
        for idx, res in enumerate(sorted_results):
            marker = (
                "<- CURRENT" 
                if res["model"] == current_model 
                else ""
            )
            context_str = (
                f"{res.get('context_length', 0) // 1024}k" 
                if res.get('context_length', 0) > 0 
                else "N/A"
            )
            
            # 状态显示优化
            if not res.get("is_loaded", False):
                status = "Unloaded"
                latency_str = "SKIP"
            elif res["success"]:
                status = "OK"
                latency_str = f"{res.get('latency', 0):.3f}s"
            else:
                status = f"Error: {res['error'][:20]}"
                latency_str = "N/A"
            
            print(
                f"{idx:<4} | {res['model'][:35]:<35} | "
                f"{latency_str:<10} | {context_str:<8} | {status} {marker}"
            )
        print("-" * 88)
        
        # 4. 交互选择
        print("\n(Enter model ID to set as default, or 'q' to quit)")
        choice = await asyncio.to_thread(
            input, "Select ID > "
        )
        
        if choice.lower() == 'q' or not choice:
            return
            
        try:
            target_idx = int(choice)
            if 0 <= target_idx < len(sorted_results):
                chosen_res = sorted_results[target_idx]
                chosen_model = chosen_res["model"]
                context_val = chosen_res.get("context_length", 4096) # 降级为 4k
                
                # 5. 更新配置
                # @Antigravity, 2026/02/12, [REF]: 原子化更新 config.ini
                # 同步更新模型名称与物理 Token 上限
                config.set("LLM", "model", chosen_model)
                if context_val > 0:
                    config.set("LLM", "max_context_tokens", str(context_val))
                    
                with open(config_path, "w", encoding="utf-8") as f:
                    config.write(f)
                
                msg = f"\nSUCCESS: Updated config.ini with model '{chosen_model}'"
                if context_val > 0:
                    msg += f" and context limit {context_val}."
                else:
                    msg += "."
                print(msg)
            else:
                print("Invalid ID.")
        except ValueError:
            print("Invalid input.")
            
    except Exception as e:
        print(f"API Error: {e}")

if __name__ == "__main__":
    if sys.platform == "win32":
        # @Antigravity, 2026/02/12, [FIX]: 修复 Windows 下异步策略
        asyncio.set_event_loop_policy(
            asyncio.WindowsSelectorEventLoopPolicy()
        )
    asyncio.run(Main_Process())
