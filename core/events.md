# core/events.md

## 1. 技术设计要点/总结
*   **职责**: 定义了系统中流转的所有核心数据协议 (DTOs)。
*   **事件类型**:
    *   `TextChunk`: 纯文本片段。
    *   `FileReadRequest`: 触发读取本地文件的动作。
    *   `FileWriteStart/Chunk/End`: 实现流式文件保存的协议。
    *   `EchoRequest`: 用于回环验证的测试事件。
    *   `StatsUpdate`: 最后的统计数据包。
*   **标准**: 所有事件继承自基础基类（隐含），并支持 `str()` 转换以便于调试。

## 2. 变更记录流水
*   **20260206, [REFACTOR]: 架构重构迁移**: 物理搬迁至 `core/` 目录。
*   **20260206, [NEW]: 添加 EchoRequest**: 为回环验证新增事件定义。
