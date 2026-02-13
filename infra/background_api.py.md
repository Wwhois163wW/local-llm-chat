# infra/background_api.py.md

## 1. 技术设计要点/总结
*   **职责**: 系统总调度中心，负责将 `Consumer` 识别出的 `Event` 动作映射到具体的后台任务实现。
*   **资源加载解耦**: 将 `probe_and_load_resource` 外部化至模块级别，精简了 `Execute_Task_by_Name` 的逻辑深度。
*   **语义化自适应**: 对于 `ReadResourceRequest`，支持自适应探测路径并自动挂载至 URM，实现逻辑透明化。
*   **异步执行**: 采用 `async/await` 协程模式，防止 IO 操作阻塞主线程或 UI。
*   **任务映射**:
    *   `ReadResourceRequest`: 统一分片读取入口。
    *   `LoadResourceRequest`: 纯粹的元数据探测与挂载工具。
    *   `EchoRequest`: 处理回显逻辑并注入 Security Word (3+7=21)。
*   **处理流**:
    1. 判定 `source` 类型 (RID or Path)。
    2. (可选) 自动探测挂载资源。
    3. 同步元数据至会话记忆。
    4. 调用内核工具 (`tools.py`) 执行物理任务。

## 2. 变更记录流水
*   **20260206**: @Antigravity 架构重构，实现异步分发模型。
*   **20260209 [v1.0.5]**: @Antigravity 清理冗余元数据逻辑，强化 URM register/get 接口规范。
*   **2026-02-10 [v1.2.0]**: @Antigravity 实装自适应读取闭环：`ReadResource` 实现路径自动挂载与 RID 寻址的语义大统一，AI 决策成本降为零。
*   **2026/02/13 [v1.3.1]**: @Antigravity 架构优化：将 `probe_and_load_resource` 外部化至模块级别。移除内嵌函数以精简 `Execute_Task_by_Name`，统一资源探测与挂载的入口逻辑。