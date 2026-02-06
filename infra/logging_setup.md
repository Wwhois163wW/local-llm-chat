# infra/logging_setup.md

## 1. 技术设计要点/总结
*   **职责**: 封装标准的 `logging.config.dictConfig` 配置。
*   **配置项**: 
    *   同时输出至控制台（StreamHandler）和物理文件（FileHandler）。
    *   动态创建 `logs/` 目录以确保存储路径有效。
    *   统一的日志格式，包含时间戳、模块名和日志等级。
*   **日志过滤**: 增加了对 `httpx` 和 `openai` 的等级屏蔽（设为 `WARNING`），以确保 CLI 流式渲染的视觉纯净。

## 2. 变更记录流水
*   **20260206, [REFACTOR]: 架构重构迁移**: 物理搬迁至 `infra/` 目录。
*   **20260206, [OPT]: 视觉降噪优化**: 屏蔽了底层网络库的中断式日志，提升打印机效果稳定性。
