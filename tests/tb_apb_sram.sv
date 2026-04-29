`timescale 1ns/1ps

module tb_apb_sram;
    // 信号定义
    reg         PCLK;
    reg         PRESETn;
    reg         PSEL;
    reg         PENABLE;
    reg         PWRITE;
    reg  [7:0]  PADDR;
    reg  [31:0] PWDATA;
    wire [31:0] PRDATA;
    wire        PREADY;

    // 实例化待测设计 (DUT)
    apb_sram uut (
        .PCLK   (PCLK),
        .PRESETn(PRESETn),
        .PSEL   (PSEL),
        .PENABLE(PENABLE),
        .PWRITE (PWRITE),
        .PADDR  (PADDR),
        .PWDATA (PWDATA),
        .PRDATA (PRDATA),
        .PREADY (PREADY)
    );

    // 1. 生成 100MHz 时钟
    initial PCLK = 0;
    always #5 PCLK = ~PCLK;

    // 2. 自动化测试逻辑
    string testcase;
    initial begin
        // 初始化信号
        PRESETn = 0; PSEL = 0; PENABLE = 0; PWRITE = 0; PADDR = 0; PWDATA = 0;
        $dumpfile("waves/sram_wave.vcd");
        $dumpvars(0, tb_apb_sram);
        
        if (!$value$plusargs("TESTNAME=%s", testcase)) testcase = "default";
        // 监控 0x05 号房间的变化

        // 释放复位
        #15 PRESETn = 1;
        #10;

        if (testcase == "sram_basic_rw") begin
            // 用例 1: 写 0x12345678 到地址 0x05，然后读出来
            apb_write(8'h05, 32'h1234_5678);
            apb_read(8'h05);
            
            if (PRDATA == 32'h1234_5678) 
                $display("[PASS] 基本读写测试通过！数据匹配: %h", PRDATA);
            else 
                $display("[FAIL] 基本读写测试失败！期望 12345678, 实际得到 %h", PRDATA);
        end

        #50;
        $display("测试结束，正在退出...");
        $finish;
    end

    // --- 模拟 APB 写操作的任务 ---
    task apb_write(input [7:0] addr, input [31:0] data);
        begin
            @(posedge PCLK);
            PSEL <= 1; PWRITE <= 1; PADDR <= addr; PWDATA <= data;
            PENABLE <= 0; 
            
            @(posedge PCLK);
            PENABLE <= 1;  // 🚨 使用非阻塞赋值，仿真器会自动处理对齐
            
            wait(PREADY);
            
            @(posedge PCLK);
            PSEL <= 0; PENABLE <= 0;
        end
    endtask

    // --- 模拟 APB 读操作的任务 ---
    task apb_read(input [7:0] addr);
        begin
            @(posedge PCLK);
            PSEL = 1; PWRITE = 0; PADDR = addr;
            @(posedge PCLK);
            PENABLE = 1;
            wait(PREADY);
            @(posedge PCLK);
            PSEL = 0; PENABLE = 0;
        end
    endtask
    always @(uut.mem[8'h05]) begin
            $display("[%0t] 🚨 警报：SRAM 地址 0x05 的内容变更为: %h", $time, uut.mem[8'h05]);
    end
endmodule