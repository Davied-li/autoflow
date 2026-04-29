# Autoflow: Automated Verification Framework for AXI4-to-APB4 Bridge

## 项目简介
Autoflow 是一个面向 SoC 互联架构的轻量级自动化验证框架，同时包含了基于该框架验证的 AXI4-Full 到 APB4 多节点桥接器 RTL 设计。本项目基于 Python 驱动，结合 cocotb 与 SystemVerilog 断言（SVA），旨在解决传统硬件仿真流程中环境配置复杂、用例管理繁琐以及回归测试效率低下的问题。框架深度集成了 pytest 调度、YAML 配置解析与 Allure 测试报告生成机制，实现了一键式混合验证。

## 核心特性
* **硬件设计 (RTL)**
    * 支持完整的 AXI4-Full 协议，实现 Burst 拆解为单次 APB 访问的状态机逻辑。
    * 支持最大 4 路 APB Slave 路由，采用 One-hot 地址译码机制。
    * 内建 `ERR_SINK` 数据黑洞与排空机制，有效防止多重协议异常（如 Timeout、4KB 越界）导致的总线死锁。
* **自动化验证 (Verification Framework)**
    * **配置驱动**：基于 YAML 文件的数据驱动测试（Data-Driven Testing），实现测试用例与验证逻辑解耦。
    * **混合验证**：结合 cocotb 场景激励与 SVA 协议级断言，提升边界覆盖率。
    * **故障注入**：支持自动化 Fault Injection（如总线反压、非法地址生成、延迟响应），验证状态机鲁棒性。
    * **全链路追踪**：统一管理编译日志、仿真波形，并生成结构化的测试覆盖率报告。

## 目录结构说明
```text
autoflow/
├── analysis/               # 覆盖率数据分析与日志解析脚本
├── configs/                # YAML 测试用例配置与环境参数文件
├── core/                   # Autoflow 框架底层驱动核心 (Python/pytest 插件)
├── report_assets/          # 测试报告依赖的静态资源 (模块架构图等)
├── rtl/                    # AXI4-to-APB4 桥接器及相关外设 Verilog 源码
├── tests/                  # 基于 cocotb 编写的各项测试用例 (Testcases)
├── tools/                  # 辅助工具链 (格式化、环境检查等)
├── waves_svg/              # 波形矢量图导出目录 (支持论文与报告渲染)
├── autoflow_phase2_fault_injection.patch # 故障注入功能增量补丁包
├── clean_all.sh            # 一键清理编译中间产物与缓存脚本
├── .gitignore              # Git 提交忽略配置
└── README.md               # 项目主文档
