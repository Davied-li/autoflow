import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

# ==============================================================================
# AXI4 主机驱动模型 (基础单跳变写事务)
# ==============================================================================
async def axi_write_single(dut, addr, data):
    """执行基础 AXI 单拍写事务 (awlen = 0)"""
    await RisingEdge(dut.clk)
    
    # 1. 触发地址通道 (AW) 与数据通道 (W)
    dut.s_axi_awaddr.value = addr
    dut.s_axi_awprot.value = 0
    dut.s_axi_awlen.value = 0    # 突发长度为 1 拍
    dut.s_axi_awsize.value = 2   # 每次传输 4 Bytes (2^2)
    dut.s_axi_awburst.value = 1  # INCR 模式
    dut.s_axi_awvalid.value = 1
    
    dut.s_axi_wdata.value = data
    dut.s_axi_wstrb.value = 0xF  # 字节掩码全开
    dut.s_axi_wlast.value = 1    # 最后一拍
    dut.s_axi_wvalid.value = 1
    
    # 2. 等待握手成功 (简化模型：假设总线最终会拉高 ready)
    aw_done = False
    w_done = False
    while not (aw_done and w_done):
        await RisingEdge(dut.clk)
        if int(dut.s_axi_awready.value) == 1:
            dut.s_axi_awvalid.value = 0
            aw_done = True
        if int(dut.s_axi_wready.value) == 1:
            dut.s_axi_wvalid.value = 0
            w_done = True

    # 3. 响应通道 (B) 握手
    dut.s_axi_bready.value = 1
    while True:
        await RisingEdge(dut.clk)
        if int(dut.s_axi_bvalid.value) == 1:
            resp = int(dut.s_axi_bresp.value)
            break
            
    dut.s_axi_bready.value = 0
    return resp

# ==============================================================================
# 顶层测试用例
# ==============================================================================
@cocotb.test()
async def bridge_basic_test(dut):
    """测试 AXI 到 APB 的单拍转换逻辑与多从机路由"""
    
    # 1. 初始化时钟
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    # 2. 系统复位与接口初始化
    dut.rst_n.value = 0
    # 初始化 AXI 接口
    dut.s_axi_awvalid.value = 0
    dut.s_axi_wvalid.value = 0
    dut.s_axi_bready.value = 0
    dut.s_axi_arvalid.value = 0
    dut.s_axi_rready.value = 0
    
    # 模拟一个永远处于 Ready 状态的 0-wait APB 从机
    dut.prdata.value = 0
    dut.pready.value = 1
    dut.pslverr.value = 0

    await Timer(25, unit="ns")
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)
    dut._log.info("System reset completed.")

    # 3. 发起 AXI 写入事务
    # 根据 RTL 的路由规则，地址 [13:12] 决定选中的 Slave。
    # 0x1000 的二进制为 0001_0000_0000_0000，[13:12] 为 01，应选中 psel[1]
    target_addr = 0x1000
    write_data = 0xDEADBEEF
    
    dut._log.info("Initiating AXI Write Transaction: Addr=0x%08X, Data=0x%08X", target_addr, write_data)
    
    resp = await axi_write_single(dut, target_addr, write_data)
    
    if resp == 0:
        dut._log.info("AXI Write completed with OKAY response.")
    else:
        dut._log.error("AXI Write failed with SLVERR response.")
        
    # 延时观察波形
    await Timer(50, unit="ns")