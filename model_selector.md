# 智能模型选择工具 (Model Selector)
# Author: ZHU, W. phD | License: RIKEN

## 技术设计要点
1. **API 对标**: 通过 `v1/models` 发现模型，并并发发送请求测量端到端延迟。
2. **交互式持久化**: 支持用户通过索引选择并将结果原子化写入 `config.ini`。
3. **环境兼容**: 使用 `AsyncOpenAI` 与 `Asyncio` 确保网络 I/O 非阻塞，针对 Windows 环境配置了 `SelectorEventLoopPolicy`。

## 变更记录流水
- **2026/02/12**: 初始版本发布。实装模型探测、延迟测试与配置自动同步功能。符合 ReAct 架构下的配置动态化需求。
