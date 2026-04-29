"""
AutoFlow AXI-APB Bridge cocotb tests.

重点能力：
1. AXI 写/读 Burst Driver
2. ready/valid 等待 timeout，避免仿真卡死
3. bresp/rresp/rlast 协议检查
4. 随机测试 seed 固定，失败可复现
5. Multi-Slave 地址空间覆盖
6. 非法地址异常响应验证
7. APB PSLVERR 错误注入验证
8. APB PREADY timeout 超时验证
"""

import os
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


RESP_OKAY = 0
RESP_SLVERR = 2
DEFAULT_TIMEOUT_CYCLES = 200
SLAVE_BASE_ADDRS = [0x0000, 0x1000, 0x2000, 0x3000]


def _sig_is_high(signal):
    """把 cocotb 信号安全转换成 0/1。"""
    return int(signal.value) == 1


async def wait_signal_high(dut, signal, signal_name, timeout_cycles=DEFAULT_TIMEOUT_CYCLES):
    """
    等待某个 ready/valid 信号拉高。

    为什么要加 timeout：
    - 没有 timeout 时，如果 DUT 出现死锁，仿真会一直挂住；
    - 加 timeout 后，pytest/Allure 能直接报告失败点。
    """
    for cycle in range(timeout_cycles):
        await RisingEdge(dut.clk)
        if _sig_is_high(signal):
            return cycle + 1

    raise RuntimeError("Timeout waiting for %s after %d cycles" % (signal_name, timeout_cycles))


def init_axi_master_if(dut):
    """初始化 AXI Master 侧输入信号，避免 X 态影响仿真。"""
    dut.s_axi_awaddr.value = 0
    dut.s_axi_awprot.value = 0
    dut.s_axi_awlen.value = 0
    dut.s_axi_awsize.value = 2
    dut.s_axi_awburst.value = 1
    dut.s_axi_awvalid.value = 0

    dut.s_axi_wdata.value = 0
    dut.s_axi_wstrb.value = 0
    dut.s_axi_wlast.value = 0
    dut.s_axi_wvalid.value = 0
    dut.s_axi_bready.value = 0

    dut.s_axi_araddr.value = 0
    dut.s_axi_arprot.value = 0
    dut.s_axi_arlen.value = 0
    dut.s_axi_arsize.value = 2
    dut.s_axi_arburst.value = 1
    dut.s_axi_arvalid.value = 0
    dut.s_axi_rready.value = 0


async def reset_dut(dut):
    """统一复位流程：每个 testcase 都调用，保证用例之间互不污染。"""
    init_axi_master_if(dut)
    dut.rst_n.value = 0
    await Timer(25, units="ns")
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)


async def axi_write_burst(
    dut,
    start_addr,
    data_list,
    burst_type=1,
    expected_resp=RESP_OKAY,
    timeout_cycles=DEFAULT_TIMEOUT_CYCLES,
):
    """
    AXI 写 Burst Driver。

    data_list 的长度 = Burst 拍数。
    例如 4 个数据表示 AWLEN = 3，即 4-beat burst。
    """
    if len(data_list) == 0:
        raise ValueError("data_list must not be empty")

    burst_last_index = len(data_list) - 1

    await RisingEdge(dut.clk)

    # 1. 同时发起 AW 和第一拍 W。
    # 当前 RTL 的写通道设计要求 AWVALID 和 WVALID 同时有效后才启动桥接。
    dut.s_axi_awaddr.value = start_addr
    dut.s_axi_awprot.value = 0
    dut.s_axi_awlen.value = burst_last_index
    dut.s_axi_awsize.value = 2       # 4 Bytes per beat
    dut.s_axi_awburst.value = burst_type
    dut.s_axi_awvalid.value = 1

    dut.s_axi_wdata.value = data_list[0]
    dut.s_axi_wstrb.value = 0xF
    dut.s_axi_wlast.value = 1 if burst_last_index == 0 else 0
    dut.s_axi_wvalid.value = 1

    aw_done = False
    w_beat_index = 0

    # 2. 完成 AW 握手和所有 W beat 握手。
    for _ in range(timeout_cycles):
        await RisingEdge(dut.clk)

        if (not aw_done) and _sig_is_high(dut.s_axi_awready):
            dut.s_axi_awvalid.value = 0
            aw_done = True

        if _sig_is_high(dut.s_axi_wvalid) and _sig_is_high(dut.s_axi_wready):
            # 当前 W beat 已被 DUT 接收，检查 wlast 是否符合预期。
            expected_wlast = 1 if w_beat_index == burst_last_index else 0
            actual_wlast = int(dut.s_axi_wlast.value)
            assert actual_wlast == expected_wlast, (
                "WLAST mismatch at write beat %d. Exp=%d, Act=%d"
                % (w_beat_index, expected_wlast, actual_wlast)
            )

            w_beat_index += 1

            if w_beat_index < len(data_list):
                # 预先装载下一拍数据，等待 DUT 下一次拉高 WREADY。
                dut.s_axi_wdata.value = data_list[w_beat_index]
                dut.s_axi_wstrb.value = 0xF
                dut.s_axi_wlast.value = 1 if w_beat_index == burst_last_index else 0
                dut.s_axi_wvalid.value = 1
            else:
                dut.s_axi_wvalid.value = 0
                dut.s_axi_wlast.value = 0

        if aw_done and w_beat_index == len(data_list):
            break
    else:
        raise RuntimeError(
            "Timeout during AXI write address/data handshake. Addr=0x%08X, beats=%d"
            % (start_addr, len(data_list))
        )

    # 3. 接收 B 响应。
    dut.s_axi_bready.value = 1
    await wait_signal_high(dut, dut.s_axi_bvalid, "s_axi_bvalid", timeout_cycles)
    bresp = int(dut.s_axi_bresp.value)
    dut.s_axi_bready.value = 0

    if expected_resp is not None:
        assert bresp == expected_resp, (
            "BRESP mismatch. Addr=0x%08X, Exp=%d, Act=%d"
            % (start_addr, expected_resp, bresp)
        )

    return bresp


async def axi_read_burst(
    dut,
    start_addr,
    beat_count,
    burst_type=1,
    expected_resp=RESP_OKAY,
    timeout_cycles=DEFAULT_TIMEOUT_CYCLES,
):
    """
    AXI 读 Burst Driver。

    beat_count 是读数据拍数，不是 ARLEN。
    例如 beat_count=4 时，ARLEN=3。
    """
    if beat_count <= 0:
        raise ValueError("beat_count must be positive")

    await RisingEdge(dut.clk)

    # 1. 发送 AR 请求。
    dut.s_axi_araddr.value = start_addr
    dut.s_axi_arprot.value = 0
    dut.s_axi_arlen.value = beat_count - 1
    dut.s_axi_arsize.value = 2       # 4 Bytes per beat
    dut.s_axi_arburst.value = burst_type
    dut.s_axi_arvalid.value = 1

    await wait_signal_high(dut, dut.s_axi_arready, "s_axi_arready", timeout_cycles)
    dut.s_axi_arvalid.value = 0

    # 2. 接收 R 数据，并严格检查 RRESP/RLAST。
    read_data_list = []
    dut.s_axi_rready.value = 1

    for beat_index in range(beat_count):
        await wait_signal_high(dut, dut.s_axi_rvalid, "s_axi_rvalid", timeout_cycles)

        rdata = int(dut.s_axi_rdata.value)
        rresp = int(dut.s_axi_rresp.value)
        rlast = int(dut.s_axi_rlast.value)

        expected_rlast = 1 if beat_index == beat_count - 1 else 0
        assert rlast == expected_rlast, (
            "RLAST mismatch at read beat %d. Exp=%d, Act=%d"
            % (beat_index, expected_rlast, rlast)
        )

        if expected_resp is not None:
            assert rresp == expected_resp, (
                "RRESP mismatch at read beat %d. Addr=0x%08X, Exp=%d, Act=%d"
                % (beat_index, start_addr, expected_resp, rresp)
            )

        read_data_list.append(rdata)

    dut.s_axi_rready.value = 0
    return read_data_list


# ==============================================================================
# 测试用例 1：基础单拍写读
# ==============================================================================
@cocotb.test()
async def test_single_transfer(dut):
    """验证基本单拍写读。"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset_dut(dut)

    target_addr = 0x0000
    write_data = [0xAABBCCDD]

    await axi_write_burst(dut, target_addr, write_data, expected_resp=RESP_OKAY)
    read_data = await axi_read_burst(dut, target_addr, len(write_data), expected_resp=RESP_OKAY)

    assert read_data == write_data, "Single mismatch. Exp=%s, Act=%s" % (write_data, read_data)


# ==============================================================================
# 测试用例 2：INCR Burst 写读
# ==============================================================================
@cocotb.test()
async def test_incr_burst(dut):
    """验证 AXI INCR Burst 拆解与地址递增逻辑。"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset_dut(dut)

    start_addr = 0x1008
    write_data_burst = [0x11111111, 0x22222222, 0x33333333, 0x44444444]

    dut._log.info("Initiating INCR Burst Write of length 4 at Addr=0x%08X" % start_addr)
    await axi_write_burst(dut, start_addr, write_data_burst, burst_type=1, expected_resp=RESP_OKAY)

    dut._log.info("Initiating INCR Burst Read")
    read_data_burst = await axi_read_burst(
        dut, start_addr, len(write_data_burst), burst_type=1, expected_resp=RESP_OKAY
    )

    assert read_data_burst == write_data_burst, (
        "Burst mismatch. Exp=%s, Act=%s" % (write_data_burst, read_data_burst)
    )

    dut._log.info("INCR Burst verification passed completely")


# ==============================================================================
# 测试用例 3：Multi-Slave 地址覆盖
# ==============================================================================
@cocotb.test()
async def test_multislave_decode(dut):
    """
    覆盖 4 个 APB Slave 地址窗口：
    slave0: 0x0000 ~ 0x0FFF
    slave1: 0x1000 ~ 0x1FFF
    slave2: 0x2000 ~ 0x2FFF
    slave3: 0x3000 ~ 0x3FFF
    """
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset_dut(dut)

    for slave_index, base_addr in enumerate(SLAVE_BASE_ADDRS):
        target_addr = base_addr + 0x20
        write_data = [0x10000000 + slave_index]

        dut._log.info(
            "Testing APB slave%d decode: addr=0x%08X, data=0x%08X"
            % (slave_index, target_addr, write_data[0])
        )

        await axi_write_burst(dut, target_addr, write_data, expected_resp=RESP_OKAY)
        read_data = await axi_read_burst(dut, target_addr, 1, expected_resp=RESP_OKAY)

        assert read_data == write_data, (
            "Slave%d decode mismatch. Exp=%s, Act=%s" % (slave_index, write_data, read_data)
        )


# ==============================================================================
# 测试用例 4：非法地址异常响应
# ==============================================================================
@cocotb.test()
async def test_invalid_address_error(dut):
    """访问 0x4000 以外非法地址，期望 AXI 返回 SLVERR。"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset_dut(dut)

    invalid_addr = 0x4000

    dut._log.info("Testing invalid write address: 0x%08X" % invalid_addr)
    await axi_write_burst(
        dut,
        invalid_addr,
        [0xDEADBEEF],
        burst_type=1,
        expected_resp=RESP_SLVERR,
    )

    dut._log.info("Testing invalid read address: 0x%08X" % invalid_addr)
    read_data = await axi_read_burst(
        dut,
        invalid_addr,
        1,
        burst_type=1,
        expected_resp=RESP_SLVERR,
    )

    assert read_data == [0], "Invalid read data should be 0. Act=%s" % read_data


# ==============================================================================
# 测试用例 5：APB PSLVERR 错误注入
# ==============================================================================
@cocotb.test()
async def test_apb_pslverr_injection(dut):
    """
    访问 slave3 内部保留故障地址 0x3F00。

    预期行为：
    - APB SRAM 在 Access 阶段返回 PSLVERR=1；
    - Bridge 捕获 PSLVERR；
    - AXI 写返回 BRESP=SLVERR；
    - AXI 读返回 RRESP=SLVERR。
    """
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset_dut(dut)

    fault_addr = 0x3F00

    dut._log.info("Testing APB PSLVERR injection at addr=0x%08X" % fault_addr)

    bresp = await axi_write_burst(
        dut,
        fault_addr,
        [0x12345678],
        burst_type=1,
        expected_resp=RESP_SLVERR,
    )
    assert bresp == RESP_SLVERR, "PSLVERR write should return AXI SLVERR"

    read_data = await axi_read_burst(
        dut,
        fault_addr,
        1,
        burst_type=1,
        expected_resp=RESP_SLVERR,
    )
    assert read_data == [0], "PSLVERR read data should be 0. Act=%s" % read_data


# ==============================================================================
# 测试用例 6：APB PREADY timeout 超时注入
# ==============================================================================
@cocotb.test()
async def test_apb_pready_timeout(dut):
    """
    访问 slave3 内部保留故障地址 0x3F04。

    预期行为：
    - APB SRAM 持续 PREADY=0；
    - Bridge 等待 TIMEOUT_CYCLES 后强制结束 APB 访问；
    - AXI 写返回 BRESP=SLVERR；
    - AXI 读返回 RRESP=SLVERR。
    """
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset_dut(dut)

    timeout_addr = 0x3F04

    dut._log.info("Testing APB PREADY timeout injection at addr=0x%08X" % timeout_addr)

    bresp = await axi_write_burst(
        dut,
        timeout_addr,
        [0xCAFEBABE],
        burst_type=1,
        expected_resp=RESP_SLVERR,
        timeout_cycles=DEFAULT_TIMEOUT_CYCLES,
    )
    assert bresp == RESP_SLVERR, "Timeout write should return AXI SLVERR"

    read_data = await axi_read_burst(
        dut,
        timeout_addr,
        1,
        burst_type=1,
        expected_resp=RESP_SLVERR,
        timeout_cycles=DEFAULT_TIMEOUT_CYCLES,
    )
    assert read_data == [0], "Timeout read data should be 0. Act=%s" % read_data


# ==============================================================================
# 测试用例 7：受限随机压力测试
# ==============================================================================
@cocotb.test()
async def test_random_burst_stress(dut):
    """受限随机压力测试：随机 slave、随机 offset、随机 burst 长度、随机数据。"""
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset_dut(dut)

    seed = int(os.getenv("AUTOFLOW_SEED", "20260428"))
    random.seed(seed)
    dut._log.info("Random stress seed = %d" % seed)

    test_iterations = int(os.getenv("AUTOFLOW_ITERATIONS", "100"))

    for iteration in range(test_iterations):
        burst_len = random.randint(1, 4)
        slave_base = random.choice(SLAVE_BASE_ADDRS)

        # 防止 burst 跨出当前 4KB slave 窗口。
        max_offset = 0x1000 - burst_len * 4
        offset = random.randrange(0, max_offset + 1, 4)
        target_addr = slave_base + offset

        write_data_list = [random.randint(0, 0xFFFFFFFF) for _ in range(burst_len)]

        dut._log.info(
            "[Iter %03d] Addr=0x%08X, Len=%d, Data=%s"
            % (iteration, target_addr, burst_len, [hex(x) for x in write_data_list])
        )

        await axi_write_burst(dut, target_addr, write_data_list, expected_resp=RESP_OKAY)
        read_data_list = await axi_read_burst(dut, target_addr, burst_len, expected_resp=RESP_OKAY)

        assert read_data_list == write_data_list, (
            "Random mismatch at iter %d. Addr=0x%08X, Exp=%s, Act=%s"
            % (iteration, target_addr, write_data_list, read_data_list)
        )

    dut._log.info("Stress test completed. %d iterations passed." % test_iterations)
    # ==============================================================================
# 临时测试：故意失败，用于验证失败用例是否仍能保留 VCD/SVG 波形
# ==============================================================================
@cocotb.test()
async def test_intentional_fail_wave_debug(dut):
    """
    这个 testcase 是临时调试用例。

    目的：
    1. 先正常完成一次 AXI 写读；
    2. 然后故意给出错误期望值；
    3. 让 pytest/Allure 标记为 failed；
    4. 检查失败用例是否仍然保留 VCD/SVG 波形附件。

    注意：
    验证完失败波形归档能力后，需要从 test_runner.py 里移除这个 testcase。
    """
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    await reset_dut(dut)

    target_addr = 0x0000
    write_data = [0x12345678]

    await axi_write_burst(dut, target_addr, write_data, expected_resp=RESP_OKAY)
    read_data = await axi_read_burst(dut, target_addr, len(write_data), expected_resp=RESP_OKAY)

    # 前面读写实际应该是正确的。
    # 这里故意写错期望值，用来制造 failed testcase。
    wrong_expected_data = [0xDEADBEEF]

    assert read_data == wrong_expected_data, (
        "Intentional failure for waveform debug. Real read_data=%s, Wrong expected=%s"
        % (read_data, wrong_expected_data)
    )
