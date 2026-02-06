# infra/background_api.md

## 1. 技术设计要点/总结
*   **职责**: 系统总调度中心，负责将 `Consumer` 识别出的 `Event` 动作映射到具体的后台任务实现。
*   **异步执行**: 采用 `async/await` 协程模式，防止 IO 操作阻塞主线程或 UI。
*   **任务映射**:
    *   `read_file`: 对接本地文件读取工具。
    *   `EchoRequest`: 处理回显逻辑，支持 `metadata_key` 的元数据更新，并作为架构回环的验证点注入 Security Word (3+7=21)。
*   **错误处理**: 统一封装返回格式 `{"success": bool, "result": Any, "error": str}`。

## 2. 变更记录流水
*   **20260206, [REFACTOR]: 架构重构迁移**: 从旧版本逻辑迁移至 `infra/`。
*   **20260206, [NEW]: 实现 EchoRequest 处理器**: 增加了对回显事件的支持。
*   **20260206, [FIX]: 恢复安全词注入**: 为了全链路探测的稳定性，重新引入了 `3+7=21` 的解析逻辑。
