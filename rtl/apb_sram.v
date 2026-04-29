module apb_sram #(
    parameter ADDR_WIDTH = 8,
    parameter DATA_WIDTH = 32,
    // 故障注入开关：默认关闭，避免影响普通 SRAM 行为
    parameter ENABLE_PSLVERR = 0,
    parameter ENABLE_TIMEOUT = 0,
    // APB 局部地址触发点。全局地址由 soc_system_top 的 slave base 决定
    parameter [ADDR_WIDTH-1:0] PSLVERR_ADDR = 12'hF00,
    parameter [ADDR_WIDTH-1:0] TIMEOUT_ADDR = 12'hF04
)(
    input  wire                  PCLK,
    input  wire                  PRESETn,
    input  wire                  PSEL,
    input  wire                  PENABLE,
    input  wire                  PWRITE,
    input  wire [ADDR_WIDTH-1:0] PADDR,
    input  wire [DATA_WIDTH-1:0] PWDATA,
    output reg  [DATA_WIDTH-1:0] PRDATA,
    output wire                  PREADY,
    output wire                  PSLVERR
);

    // 定义 SRAM 存储阵列
    localparam DEPTH = 1 << ADDR_WIDTH;
    reg [DATA_WIDTH-1:0] mem [0:DEPTH-1];

    // ------------------------------------------------------------------
    // 故障注入逻辑
    // ------------------------------------------------------------------
    // 在 APB Access 阶段触发，避免 Setup 阶段误报。
    wire apb_access = PSEL && PENABLE;

    // 访问 PSLVERR_ADDR：从机立即返回 PSLVERR=1，模拟从设备内部错误。
    wire hit_pslverr_addr = ENABLE_PSLVERR && apb_access && (PADDR == PSLVERR_ADDR);

    // 访问 TIMEOUT_ADDR：从机持续不拉高 PREADY，模拟外设无响应。
    // Bridge 内部 TIMEOUT_CYCLES 到达后应强制结束并返回 AXI SLVERR。
    wire hit_timeout_addr = ENABLE_TIMEOUT && apb_access && (PADDR == TIMEOUT_ADDR);

    assign PREADY  = hit_timeout_addr ? 1'b0 : 1'b1;
    assign PSLVERR = hit_pslverr_addr;

    // 写逻辑：只在 Access 阶段且 PREADY=1、无错误时真正写入阵列
    always @(posedge PCLK) begin
        if (PSEL && PENABLE && PREADY && PWRITE && !PSLVERR) begin
            mem[PADDR] <= PWDATA;
        end
    end

    // 读逻辑：在 Setup 阶段锁存地址并预取数据，确保 Access 阶段数据稳定
    always @(posedge PCLK or negedge PRESETn) begin
        if (!PRESETn) begin
            PRDATA <= {DATA_WIDTH{1'b0}};
        end else if (PSEL && !PWRITE) begin
            if (ENABLE_PSLVERR && (PADDR == PSLVERR_ADDR)) begin
                PRDATA <= {DATA_WIDTH{1'b0}};
            end else if (ENABLE_TIMEOUT && (PADDR == TIMEOUT_ADDR)) begin
                PRDATA <= {DATA_WIDTH{1'b0}};
            end else begin
                PRDATA <= mem[PADDR];
            end
        end
    end

endmodule
