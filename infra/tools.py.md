# tools.py 技术说明

## 技术设计要点
- **分级权限 (Tiered CRUD)**: 核心决策逻辑位于 `_is_path_safe`，区分为 Read (R) 与 Write (W) 两种级别。
- **路径重定向与剥离**: 恶意或不确定的 Write 操作（如 Create）强制路由至 `.staging/` 影子目录。新增循环剥离算法，自动清除路径中重复出现的 `.staging/new/` 等前缀。
- **命令执行 (Subprocess)**: 引入 `execute_command`，支持在指定 CWD 下执行系统指令并捕获输出。集成超时控制与错误捕获。

## 变更记录流水
- **2026/02/10**: 彻底放开 `list_dir` 权限。重构 `write_file` 路径解析逻辑，根治双重嵌套 Bug。实现 `execute_command` 核心函数。实现异步兼容。
