# EVO-X2 Local LLM Agent CLI

[![Author](https://img.shields.io/badge/Author-ZHU,%20W.%20phD-blue)](https://csrs.riken.jp/en/labs/emart/index.html)
[![License](https://img.shields.io/badge/License-RIKEN-green)](https://csrs.riken.jp/en/labs/emart/index.html)
[![Version](https://img.shields.io/badge/Version-1.2.x-orange)](#)

## 0. 项目愿景
本项目致力于构建一个具备**高度感知力**、**自适应性**以及**资源治理能力**的本地 LLM 代理框架。通过将传统的“对话模式”升级为“任务处理模式”，实现 AI 对本地工程环境的深度掌控。

## 1. 核心特性
- **URM (Unified Resource Management)**: 统一资源管理系统。实现资源的按需加载、自动感知的元数据同步以及分片读取。
- **Metadata-Driven Memory**: 基于元数据的动态上下文注入。AI 始终拥有当前环境（文件状态、系统信息、任务进度）的实时快照。
- **Decoupled Turn Architecture**: 彻底解耦的推理与执行层。通过极简的事件总线实现异步流处理与工具反馈。
- **System Awareness**: 支持物理路径提取、系统负载查询及跨平台环境感知。

## 2. 技术栈
- **Language**: Python 3.10+
- **LLM Kernel**: EVO-X2 (OpenAI Compatible API)
- **Tokenization**: Tiktoken (cl100k_base)
- **Engine**: Asyncio Context

## 3. 快速开始
### 安装依赖
```bash
pip install -r requirements.txt
```
### 配置环境
复制 `config.example.ini` 并重命名为 `config.ini`，填入您的本地 API 终端与模型名称。

### 运行
```bash
python main.py
```

## 4. 架构文档
- [全链路架构描述](docs/architecture.md)
- [工具目录 (Tools Catalog)](docs/tools_catalog.md)
- [核心变更流水](docs/dialog/)

---

*Copyright (c) 2026 ZHU, W. phD. Licensed under RIKEN EmArt Lab.*
