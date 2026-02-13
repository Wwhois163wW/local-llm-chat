# 全功能集成测试场景指南 (Manual Test Scenarios)

本指南旨在通过一组精心设计的“对话指令”，全面验证重构后的各项核心功能（URM, Tiered Write, act_type, Safety Gate）。

## 测试执行步骤

### 场景 1：URM 认知加载与元数据探测
- **用户指令**: “请帮我检查 `main.py` 的文件状态，包括大小和修改时间。”
- **预期行为**: 
  - AI 应调用 `load_resource` 或 `get_file_metadata`。
  - 系统控制台应显示 `[URM] Probing source: main.py`。
  - 如果文件之前未加载，系统应自动执行一次备份。

### 场景 2：三段式写操作 - 隔离创建 (Create)
- **用户指令**: “在 `tests/` 目录下创建一个名为 `functional_smoke.txt` 的文件，内容为 'Hello World'。”
- **预期行为**:
  - 由于文件不存在，AI 触发 `Create` 意图。
  - 系统应返回结果：“New file created in staging buffer: 'staging/new/tests/functional_smoke.txt'”。
  - **核心点**: 并没有直接写入 `tests/`，而是进行了隔离。

### 场景 3：三段式写操作 - 认知驱动更新 (Update)
- **用户指令**: 
  1. “读取 `main.py` 的前 10 行内容。”
  2. “在 `main.py` 的头部增加一行注释：`# Integration Test Passed`。”
- **预期行为**:
  - 第 1 步使文件进入 URM `Loaded` 状态。
  - 第 2 步 AI 应触发 `Update` 意图（`act_type: Update`）。
  - 系统应执行自动备份并在 `main.py` 原地覆盖。

### 场景 4：连续创建拦截 (Consecutive Create Gate)
- **用户指令**: “帮我连续创建两个文件：`a.txt` 内容 'aaa'，以及 `b.txt` 内容 'bbb'。”
- **预期行为**:
  - 第一个文件创建成功并重定向。
  - 第二个文件创建动作应被 `Consumer` 拦截，提示：“Create blocked. Consecutive creation is prohibited.”。
  - **目的**: 防止 AI 在未观察状态下进行大规模文件破坏/生产。

### 场景 5：系统指令安全确认
- **用户指令**: “使用系统指令查看工作区的目录树 (tree /f)。”
- **预期行为**:
  - AI 调用 `execute_command`。
  - 系统弹出安全性控制交互，询问用户是否允许执行。

---
**提示**: 您可以在对话过程中观察控制台的 `[System] ⚙️ Executing... (Intent: ...)` 日志，它将实时反映 `act_type` 的语义判定。
