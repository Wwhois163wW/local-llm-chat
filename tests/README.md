# 自动化测试脚本说明 (Tests)

## 包含文件
- **mock_llm.py**: 模拟异步 OpenAI 响应流，支持 ReAct 动作注入模拟。
- **test_tools.py**: 覆盖基础设施工具的权限与路径安全单元测试。
- **test_framework_flow.py**: 全链路冒烟测试，模拟从用户输入到 Action 执行再到反馈注入的完整闭环。

## 变更记录流水
- **2026/02/10**: 初始化自动化测试套件，支撑后续 Subprocess 等高危功能的迭代验证。
