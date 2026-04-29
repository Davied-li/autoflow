# -*- coding: utf-8 -*-

import os
import allure


@allure.feature("AutoFlow Project Overview")
@allure.story("AXI-APB Bridge Verification Framework")
@allure.title("Project Overview - AutoFlow AXI-APB Bridge Verification")
def test_project_overview():
    """
    项目总览页：
    用于在 Allure 报告中展示 AutoFlow 框架说明、验证范围和模块结构图。
    """

    tests_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(tests_dir)

    module_diagram_file = os.path.join(
        project_root,
        "report_assets",
        "module_diagrams",
        "axi_apb_bridge.svg"
    )

    overview_text = """
AutoFlow Verification Framework

Project:
AutoFlow is a Python-based RTL verification automation framework built with Pytest, Cocotb, Synopsys VCS, and Allure.

DUT:
AXI-APB Bridge with Multi-Slave APB subsystem.

Main Capabilities:
1. Pytest-based regression scheduling
2. Cocotb-based AXI transaction driver
3. Synopsys VCS simulation backend
4. AXI single transfer and INCR burst verification
5. Multi-Slave APB address decode verification
6. Invalid address handling
7. APB PSLVERR fault injection
8. APB PREADY timeout verification
9. Random burst stress test with fixed seed
10. VCD waveform archive
11. SVG waveform visualization
12. Allure report generation

Formal Regression Testcases:
1. test_single_transfer
2. test_incr_burst
3. test_multislave_decode
4. test_invalid_address_error
5. test_apb_pslverr_injection
6. test_apb_pready_timeout
7. test_random_burst_stress
"""

    allure.attach(
        overview_text,
        name="AutoFlow Project Summary",
        attachment_type=allure.attachment_type.TEXT
    )

    if os.path.exists(module_diagram_file):
        allure.attach.file(
            module_diagram_file,
            name="Module Diagram - AXI-APB Bridge",
            attachment_type=allure.attachment_type.SVG,
            extension="svg",
        )

    assert os.path.exists(module_diagram_file), (
        "Module diagram file not found: %s" % module_diagram_file
    )