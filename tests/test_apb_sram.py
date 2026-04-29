import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer, ReadOnly


# ==============================================================================
# APB 写事务
# ==============================================================================
async def apb_write(dut, addr, data):
    """
    标准 APB 写事务

    APB 写时序：
    1. Setup Phase:
       PSEL=1, PENABLE=0, PWRITE=1, 地址和数据有效
    2. Access Phase:
       PSEL=1, PENABLE=1
    3. 等待 PREADY
    4. 撤销 PSEL / PENABLE
    """

    # ------------------------------
    # 1. Setup Phase
    # ------------------------------
    await RisingEdge(dut.PCLK)
    await Timer(1, unit="ns")

    dut.PSEL.value = 1
    dut.PENABLE.value = 0
    dut.PWRITE.value = 1
    dut.PADDR.value = addr
    dut.PWDATA.value = data

    # APB4 字节写使能
    # 0xF 表示 4 个字节全部写入
    if hasattr(dut, "PSTRB"):
        dut.PSTRB.value = 0xF

    # ------------------------------
    # 2. Access Phase
    # ------------------------------
    await RisingEdge(dut.PCLK)
    await Timer(1, unit="ns")

    dut.PENABLE.value = 1

    # ------------------------------
    # 3. 等待 PREADY
    # ------------------------------
    while True:
        await RisingEdge(dut.PCLK)
        await ReadOnly()

        # 如果 RTL 没有 PREADY，默认认为永远 ready
        if not hasattr(dut, "PREADY"):
            break

        if int(dut.PREADY.value) == 1:
            break

    # ------------------------------
    # 4. 撤销请求
    # ------------------------------
    await Timer(1, unit="ns")

    dut.PSEL.value = 0
    dut.PENABLE.value = 0
    dut.PWRITE.value = 0
    dut.PADDR.value = 0
    dut.PWDATA.value = 0

    if hasattr(dut, "PSTRB"):
        dut.PSTRB.value = 0


# ==============================================================================
# APB 读事务
# ==============================================================================
async def apb_read(dut, addr):
    """
    标准 APB 读事务

    APB 读时序：
    1. Setup Phase:
       PSEL=1, PENABLE=0, PWRITE=0, 地址有效
    2. Access Phase:
       PSEL=1, PENABLE=1
    3. 等待 PREADY
    4. 在 PREADY 有效时采样 PRDATA
    5. 撤销 PSEL / PENABLE
    """

    # ------------------------------
    # 1. Setup Phase
    # ------------------------------
    await RisingEdge(dut.PCLK)
    await Timer(1, unit="ns")

    dut.PSEL.value = 1
    dut.PENABLE.value = 0
    dut.PWRITE.value = 0
    dut.PADDR.value = addr
    dut.PWDATA.value = 0

    # 读操作时 PSTRB 无效，清 0
    if hasattr(dut, "PSTRB"):
        dut.PSTRB.value = 0

    # ------------------------------
    # 2. Access Phase
    # ------------------------------
    await RisingEdge(dut.PCLK)
    await Timer(1, unit="ns")

    dut.PENABLE.value = 1

    # ------------------------------
    # 3. 等待 PREADY 并采样 PRDATA
    # ------------------------------
    while True:
        await RisingEdge(dut.PCLK)
        await ReadOnly()

        # 如果 RTL 没有 PREADY，默认认为当前周期 ready
        if not hasattr(dut, "PREADY"):
            prdata_val = dut.PRDATA.value
            break

        if int(dut.PREADY.value) == 1:
            prdata_val = dut.PRDATA.value
            break

    # ------------------------------
    # 4. 检查 PRDATA 是否存在 X/Z
    # ------------------------------
    if not prdata_val.is_resolvable:
        dut._log.error("PRDATA bus contains unknown states X/Z: %s", str(prdata_val))
        data = 0
    else:
        data = int(prdata_val)

    # ------------------------------
    # 5. 撤销请求
    # ------------------------------
    await Timer(1, unit="ns")

    dut.PSEL.value = 0
    dut.PENABLE.value = 0
    dut.PADDR.value = 0

    return data


# ==============================================================================
# 顶层测试用例
# ==============================================================================
@cocotb.test()
async def apb_basic_rw(dut):
    """
    测试 APB SRAM 基础读写功能

    测试流程：
    1. 启动时钟
    2. 初始化所有 APB 输入信号
    3. 执行复位
    4. 向地址 0x05 写入 0x12345678
    5. 从地址 0x05 读回数据
    6. 比较读回值是否等于写入值
    """

    # ------------------------------
    # 1. 启动 PCLK，周期 10ns
    # ------------------------------
    cocotb.start_soon(Clock(dut.PCLK, 10, unit="ns").start())

    # ------------------------------
    # 2. 初始化输入信号
    # ------------------------------
    dut.PRESETn.value = 0

    dut.PSEL.value = 0
    dut.PENABLE.value = 0
    dut.PWRITE.value = 0
    dut.PADDR.value = 0
    dut.PWDATA.value = 0

    if hasattr(dut, "PSTRB"):
        dut.PSTRB.value = 0

    # ------------------------------
    # 3. 系统复位
    # ------------------------------
    for _ in range(2):
        await RisingEdge(dut.PCLK)

    await Timer(2, unit="ns")
    dut.PRESETn.value = 1

    dut._log.info("System reset completed.")

    # 复位释放后再等 1 个周期，保证 RTL 状态稳定
    await RisingEdge(dut.PCLK)

    # ------------------------------
    # 4. 执行写事务
    # ------------------------------
    target_addr = 0x05
    write_data = 0x12345678

    dut._log.info(
        "Initiating APB write transaction: Addr=0x%02X, Data=0x%08X",
        target_addr,
        write_data
    )

    await apb_write(dut, target_addr, write_data)

    # 写完后等待一个周期，保证 SRAM 写入稳定
    await RisingEdge(dut.PCLK)

    # ------------------------------
    # 5. 执行读事务
    # ------------------------------
    dut._log.info(
        "Initiating APB read transaction: Addr=0x%02X",
        target_addr
    )

    read_data = await apb_read(dut, target_addr)

    # ------------------------------
    # 6. 结果检查
    # ------------------------------
    assert read_data == write_data, (
        "Data mismatch. Expected: 0x%08X, Actual: 0x%08X"
        % (write_data, read_data)
    )

    dut._log.info(
        "Verification passed. Read data: 0x%08X",
        read_data
    )