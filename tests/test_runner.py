import os
import shutil
import subprocess

import pytest
import allure
from cocotb_test.simulator import run


# 正式回归 testcase 列表
# 注意：这里不要放 test_intentional_fail_wave_debug
TESTCASES = [
    ("test_single_transfer", 20260428),
    ("test_incr_burst", 20260428),
    ("test_multislave_decode", 20260428),
    ("test_invalid_address_error", 20260428),
    ("test_apb_pslverr_injection", 20260428),
    ("test_apb_pready_timeout", 20260428),
    ("test_random_burst_stress", 20260428),
]


@pytest.mark.parametrize(
    "test_name,seed",
    TESTCASES,
    ids=[case[0] for case in TESTCASES],
)
def test_soc_bridge(test_name, seed):
    """
    AutoFlow AXI-APB Bridge 自动化回归入口。

    功能：
    1. pytest 参数化调度 testcase；
    2. cocotb-test 调用 VCS 仿真；
    3. 每个 testcase 使用独立 sim_build；
    4. 自动归档 VCD 波形；
    5. 自动生成 SVG 波形图；
    6. 自动挂载模块结构图到 Allure 报告。
    """

    os.environ["SIM"] = "vcs"
    os.environ["WAVES"] = "1"
    os.environ["AUTOFLOW_SEED"] = str(seed)

    tests_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(tests_dir)

    verilog_sources = [
        os.path.join(project_root, "rtl", "axi_lite_to_apb_bridge.v"),
        os.path.join(project_root, "rtl", "apb_sram.v"),
        os.path.join(project_root, "rtl", "soc_system_top.v"),
    ]

    sim_build_dir = os.path.join(tests_dir, "sim_build", test_name)

    # VCD 波形输出目录
    waves_dir = os.path.join(project_root, "waves")
    if not os.path.isdir(waves_dir):
        os.makedirs(waves_dir)

    final_wave_file = os.path.join(waves_dir, "%s.vcd" % test_name)
    vcs_wave_file = os.path.join(sim_build_dir, "wave.vcd")

    # SVG 波形输出目录
    waves_svg_dir = os.path.join(project_root, "waves_svg")
    if not os.path.isdir(waves_svg_dir):
        os.makedirs(waves_svg_dir)

    final_wave_svg = os.path.join(waves_svg_dir, "%s.svg" % test_name)

    # 模块结构图
    module_diagram_file = os.path.join(
        project_root,
        "report_assets",
        "module_diagrams",
        "axi_apb_bridge.svg"
    )

    # 每次运行前清理旧文件，避免挂到历史附件
    if os.path.exists(final_wave_file):
        os.remove(final_wave_file)

    if os.path.exists(final_wave_svg):
        os.remove(final_wave_svg)

    try:
        run(
            verilog_sources=verilog_sources,
            toplevel="soc_system_top",
            module="test_soc_system",
            testcase=test_name,
            simulator="vcs",
            timescale="1ns/1ps",
            sim_build=sim_build_dir,
            compile_args=["-timescale=1ns/1ps", "-debug_access+all"],
        )

    finally:
        # 1. 复制 VCS 默认生成的 wave.vcd 到项目级 waves 目录
        if os.path.exists(vcs_wave_file):
            shutil.copyfile(vcs_wave_file, final_wave_file)

        # 2. 挂载 VCD 原始波形
        if os.path.exists(final_wave_file):
            allure.attach.file(
                final_wave_file,
                name="VCD Waveform - %s" % test_name,
                attachment_type=allure.attachment_type.TEXT,
                extension="vcd",
            )

        # 3. 将 VCD 转换成 SVG 可视化波形图
        converter_script = os.path.join(
            project_root,
            "tools",
            "vcd_to_wave_svg.py"
        )

        if os.path.exists(final_wave_file) and os.path.exists(converter_script):
            try:
                subprocess.check_call([
                    "python3",
                    converter_script,
                    "--vcd", final_wave_file,
                    "--svg", final_wave_svg,
                    "--title", test_name
                ])
            except Exception as e:
                print("[WARN] Failed to generate waveform SVG for {}: {}".format(test_name, e))

        # 4. 挂载 SVG 波形图
        if os.path.exists(final_wave_svg):
            allure.attach.file(
                final_wave_svg,
                name="Waveform SVG - %s" % test_name,
                attachment_type=allure.attachment_type.SVG,
                extension="svg",
            )

        # 5. 挂载 AXI-APB Bridge 模块结构图
        if os.path.exists(module_diagram_file):
            allure.attach.file(
                module_diagram_file,
                name="Module Diagram - AXI-APB Bridge",
                attachment_type=allure.attachment_type.SVG,
                extension="svg",
            )