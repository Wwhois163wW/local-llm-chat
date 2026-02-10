# core/resource_manager.md

## 1. 技术设计要点/总结
*   **职责**: 统一管理会话期间加载的所有资源（文件、元数据等），通过 RID 实现物理源解耦。
*   **语义化描述**: `get_resource_description` 方法负责将复杂的资源元数据转化为 AI 友好的文本摘要。
*   **分片注入配合**: 作为 `InjectResourceRequest` 的底层数据源，支持按行精准读取。

## 2. 变更记录流水
*   **2026-02-09**: @Antigravity 初始定义资源管理核心。
*   **2026-02-10 [v1.1.0]**: @Antigravity 新增 `get_resource_description` 接口，正式接入全链路探测反馈。
