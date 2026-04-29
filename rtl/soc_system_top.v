// SoC 顶层：实例化 AXI-APB Bridge，并挂载 4 块独立 APB SRAM
module soc_system_top (
    input  wire        clk,
    input  wire        rst_n,

    // 暴露 AXI 接口用于 cocotb 测试驱动
    input  wire [31:0] s_axi_awaddr,
    input  wire [2:0]  s_axi_awprot,
    input  wire [7:0]  s_axi_awlen,
    input  wire [2:0]  s_axi_awsize,
    input  wire [1:0]  s_axi_awburst,
    input  wire        s_axi_awvalid,
    output wire        s_axi_awready,

    input  wire [31:0] s_axi_wdata,
    input  wire [3:0]  s_axi_wstrb,
    input  wire        s_axi_wlast,
    input  wire        s_axi_wvalid,
    output wire        s_axi_wready,

    output wire [1:0]  s_axi_bresp,
    output wire        s_axi_bvalid,
    input  wire        s_axi_bready,

    input  wire [31:0] s_axi_araddr,
    input  wire [2:0]  s_axi_arprot,
    input  wire [7:0]  s_axi_arlen,
    input  wire [2:0]  s_axi_arsize,
    input  wire [1:0]  s_axi_arburst,
    input  wire        s_axi_arvalid,
    output wire        s_axi_arready,

    output wire [31:0] s_axi_rdata,
    output wire [1:0]  s_axi_rresp,
    output wire        s_axi_rlast,
    output wire        s_axi_rvalid,
    input  wire        s_axi_rready
);
    // VCD 波形导出：
    // test_runner.py 通过 +AUTOFLOW_WAVE=<path> 传入每个 testcase 的波形文件名。
    // 这样每个 testcase 都会生成独立的 VCD 文件，后续挂到 Allure 报告中。
    reg [1023:0] autoflow_wave_file;

    initial begin
        if ($value$plusargs("AUTOFLOW_WAVE=%s", autoflow_wave_file)) begin
            $dumpfile(autoflow_wave_file);
        end else begin
            $dumpfile("autoflow_wave.vcd");
        end

        $dumpvars(0, soc_system_top);
    end

    // 内部 APB 总线声明
    wire [31:0] paddr;
    wire [2:0]  pprot;
    wire [3:0]  psel;
    wire        penable;
    wire        pwrite;
    wire [31:0] pwdata;
    wire [3:0]  pstrb;

    wire [31:0] prdata_0, prdata_1, prdata_2, prdata_3;
    wire        pready_0, pready_1, pready_2, pready_3;
    wire        pslverr_0, pslverr_1, pslverr_2, pslverr_3;

    // APB 读数据与响应多路复用
    wire [31:0] prdata  = psel[0] ? prdata_0  :
                           psel[1] ? prdata_1  :
                           psel[2] ? prdata_2  :
                           psel[3] ? prdata_3  : 32'd0;

    wire        pready  = psel[0] ? pready_0  :
                           psel[1] ? pready_1  :
                           psel[2] ? pready_2  :
                           psel[3] ? pready_3  : 1'b1;

    wire        pslverr = psel[0] ? pslverr_0 :
                           psel[1] ? pslverr_1 :
                           psel[2] ? pslverr_2 :
                           psel[3] ? pslverr_3 : 1'b0;

    // AXI-APB Bridge 核心
    axi_lite_to_apb_bridge u_bridge (
        .clk(clk),
        .rst_n(rst_n),

        .s_axi_awaddr(s_axi_awaddr),
        .s_axi_awprot(s_axi_awprot),
        .s_axi_awlen(s_axi_awlen),
        .s_axi_awsize(s_axi_awsize),
        .s_axi_awburst(s_axi_awburst),
        .s_axi_awvalid(s_axi_awvalid),
        .s_axi_awready(s_axi_awready),

        .s_axi_wdata(s_axi_wdata),
        .s_axi_wstrb(s_axi_wstrb),
        .s_axi_wlast(s_axi_wlast),
        .s_axi_wvalid(s_axi_wvalid),
        .s_axi_wready(s_axi_wready),

        .s_axi_bresp(s_axi_bresp),
        .s_axi_bvalid(s_axi_bvalid),
        .s_axi_bready(s_axi_bready),

        .s_axi_araddr(s_axi_araddr),
        .s_axi_arprot(s_axi_arprot),
        .s_axi_arlen(s_axi_arlen),
        .s_axi_arsize(s_axi_arsize),
        .s_axi_arburst(s_axi_arburst),
        .s_axi_arvalid(s_axi_arvalid),
        .s_axi_arready(s_axi_arready),

        .s_axi_rdata(s_axi_rdata),
        .s_axi_rresp(s_axi_rresp),
        .s_axi_rlast(s_axi_rlast),
        .s_axi_rvalid(s_axi_rvalid),
        .s_axi_rready(s_axi_rready),

        .paddr(paddr),
        .pprot(pprot),
        .psel(psel),
        .penable(penable),
        .pwrite(pwrite),
        .pwdata(pwdata),
        .pstrb(pstrb),
        .prdata(prdata),
        .pready(pready),
        .pslverr(pslverr)
    );

    // slave0: 0x0000 ~ 0x0FFF
    apb_sram #(.ADDR_WIDTH(12), .DATA_WIDTH(32)) u_sram_0 (
        .PCLK(clk), .PRESETn(rst_n),
        .PSEL(psel[0]), .PENABLE(penable), .PWRITE(pwrite),
        .PADDR(paddr[11:0]), .PWDATA(pwdata), .PRDATA(prdata_0),
        .PREADY(pready_0), .PSLVERR(pslverr_0)
    );

    // slave1: 0x1000 ~ 0x1FFF
    apb_sram #(.ADDR_WIDTH(12), .DATA_WIDTH(32)) u_sram_1 (
        .PCLK(clk), .PRESETn(rst_n),
        .PSEL(psel[1]), .PENABLE(penable), .PWRITE(pwrite),
        .PADDR(paddr[11:0]), .PWDATA(pwdata), .PRDATA(prdata_1),
        .PREADY(pready_1), .PSLVERR(pslverr_1)
    );

    // slave2: 0x2000 ~ 0x2FFF
    apb_sram #(.ADDR_WIDTH(12), .DATA_WIDTH(32)) u_sram_2 (
        .PCLK(clk), .PRESETn(rst_n),
        .PSEL(psel[2]), .PENABLE(penable), .PWRITE(pwrite),
        .PADDR(paddr[11:0]), .PWDATA(pwdata), .PRDATA(prdata_2),
        .PREADY(pready_2), .PSLVERR(pslverr_2)
    );

    // slave3: 0x3000 ~ 0x3FFF
    // 额外打开故障注入：
    //   0x3F00 -> APB PSLVERR 注入
    //   0x3F04 -> APB PREADY timeout 注入
    apb_sram #(
        .ADDR_WIDTH(12),
        .DATA_WIDTH(32),
        .ENABLE_PSLVERR(1),
        .ENABLE_TIMEOUT(1),
        .PSLVERR_ADDR(12'hF00),
        .TIMEOUT_ADDR(12'hF04)
    ) u_sram_3 (
        .PCLK(clk), .PRESETn(rst_n),
        .PSEL(psel[3]), .PENABLE(penable), .PWRITE(pwrite),
        .PADDR(paddr[11:0]), .PWDATA(pwdata), .PRDATA(prdata_3),
        .PREADY(pready_3), .PSLVERR(pslverr_3)
    );

endmodule
