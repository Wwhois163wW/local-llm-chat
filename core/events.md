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
# events.md - 事件系统技术设计与变更记录

## (1) 技术设计要点/总结
- **事件分层**: 元数据操作被定义为 `UpdateMetadataRequest` 和 `GetMetadataRequest`，属于核心交互事件。
- **语义增强**: `GetMetadataRequest` 引入了可选的 `key` 属性，支持从全量快照到单点探测的语义平滑升级。
- **基类对齐**: 确保所有请求类继承自 `Event` 并能正确序列化 `content` 以供历史记录回溯。

## (2) 变更记录流水
- **2026-02-09 [v0.0.3]**: @Antigravity 初始定义元数据读写事件。
- **2026-02-09 [v0.0.4]**: @Antigravity 增强 `GetMetadataRequest` 语义，增加 `key` 过滤参数；修复因编辑导致的文档字符串丢失问题。
- **2026-02-10 [v0.0.5]**: @Antigravity 新增 `GetCwdRequest` 用于获取当前工作路径。
- **2026-02-10 [v0.1.0]**: @Antigravity 统一读取事件：移除 `FileReadRequest`, `InjectResourceRequest`，引入多态 `ReadResourceRequest`。
