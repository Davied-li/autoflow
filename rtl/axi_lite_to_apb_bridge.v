module axi_lite_to_apb_bridge #(
    parameter ADDR_WIDTH     = 32,
    parameter DATA_WIDTH     = 32,
    parameter STRB_WIDTH     = DATA_WIDTH / 8,
    parameter TIMEOUT_CYCLES = 16
) (
    input  wire                     clk,
    input  wire                     rst_n,

    // AXI4 Write Address Channel
    input  wire [ADDR_WIDTH-1:0]    s_axi_awaddr,
    input  wire [2:0]               s_axi_awprot,
    input  wire [7:0]               s_axi_awlen,   
    input  wire [2:0]               s_axi_awsize,  
    input  wire [1:0]               s_axi_awburst, 
    input  wire                     s_axi_awvalid,
    output reg                      s_axi_awready,

    // AXI4 Write Data Channel
    input  wire [DATA_WIDTH-1:0]    s_axi_wdata,
    input  wire [STRB_WIDTH-1:0]    s_axi_wstrb,
    input  wire                     s_axi_wlast,   
    input  wire                     s_axi_wvalid,
    output reg                      s_axi_wready,

    // AXI4 Write Response Channel
    output reg  [1:0]               s_axi_bresp,
    output reg                      s_axi_bvalid,
    input  wire                     s_axi_bready,

    // AXI4 Read Address Channel
    input  wire [ADDR_WIDTH-1:0]    s_axi_araddr,
    input  wire [2:0]               s_axi_arprot,
    input  wire [7:0]               s_axi_arlen,   
    input  wire [2:0]               s_axi_arsize,  
    input  wire [1:0]               s_axi_arburst, 
    input  wire                     s_axi_arvalid,
    output reg                      s_axi_arready,

    // AXI4 Read Data Channel
    output reg  [DATA_WIDTH-1:0]    s_axi_rdata,
    output reg  [1:0]               s_axi_rresp,
    output reg                      s_axi_rlast,   
    output reg                      s_axi_rvalid,
    input  wire                     s_axi_rready,

    // APB4 Master side
    output reg  [ADDR_WIDTH-1:0]    paddr,
    output reg  [2:0]               pprot,
    output reg  [3:0]               psel,      
    output reg                      penable,
    output reg                      pwrite,
    output reg  [DATA_WIDTH-1:0]    pwdata,
    output reg  [STRB_WIDTH-1:0]    pstrb,

    input  wire [DATA_WIDTH-1:0]    prdata,
    input  wire                     pready,
    input  wire                     pslverr
);

    localparam [1:0] RESP_OKAY   = 2'b00;
    localparam [1:0] RESP_SLVERR = 2'b10;

    localparam [3:0] ST_IDLE         = 4'd0;
    localparam [3:0] ST_WR_SETUP     = 4'd1;
    localparam [3:0] ST_WR_ACCESS    = 4'd2;
    localparam [3:0] ST_WR_NEXT_DATA = 4'd3; 
    localparam [3:0] ST_WR_RESP      = 4'd4;
    localparam [3:0] ST_RD_SETUP     = 4'd5;
    localparam [3:0] ST_RD_ACCESS    = 4'd6;
    localparam [3:0] ST_RD_RESP      = 4'd7; 
    localparam [3:0] ST_ERR_SINK_W   = 4'd8; 

    reg [3:0]                state;
    reg [4:0]                timeout_cnt;

    reg [7:0]                burst_len_reg;
    reg [2:0]                burst_size_reg;
    reg [1:0]                burst_type_reg;
    reg [7:0]                burst_cnt;      
    reg                      err_latch;      
    reg [3:0]                target_psel_reg;

    wire awaddr_in_range = (s_axi_awaddr[31:14] == 18'h00000);
    wire araddr_in_range = (s_axi_araddr[31:14] == 18'h00000);
    
    wire [3:0] aw_device_sel = 4'b0001 << s_axi_awaddr[13:12];
    wire [3:0] ar_device_sel = 4'b0001 << s_axi_araddr[13:12];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state          <= ST_IDLE;
            s_axi_awready  <= 1'b0;
            s_axi_wready   <= 1'b0;
            s_axi_bresp    <= RESP_OKAY;
            s_axi_bvalid   <= 1'b0;
            s_axi_arready  <= 1'b0;
            s_axi_rdata    <= {DATA_WIDTH{1'b0}};
            s_axi_rresp    <= RESP_OKAY;
            s_axi_rlast    <= 1'b0;
            s_axi_rvalid   <= 1'b0;
            paddr          <= {ADDR_WIDTH{1'b0}};
            pprot          <= 3'b000;
            psel           <= 4'b0000;
            penable        <= 1'b0;
            pwrite         <= 1'b0;
            pwdata         <= {DATA_WIDTH{1'b0}};
            pstrb          <= {STRB_WIDTH{1'b0}};
            timeout_cnt    <= 5'd0;
            burst_len_reg  <= 8'd0;
            burst_size_reg <= 3'd0;
            burst_type_reg <= 2'd0;
            burst_cnt      <= 8'd0;
            err_latch      <= 1'b0;
            target_psel_reg<= 4'b0000;
        end else begin
            s_axi_awready <= 1'b0;
            s_axi_wready  <= 1'b0;
            s_axi_arready <= 1'b0;

            case (state)
                ST_IDLE: begin
                    penable     <= 1'b0;
                    timeout_cnt <= 5'd0;

                    if (s_axi_awvalid && s_axi_wvalid) begin
                        s_axi_awready  <= 1'b1;
                        s_axi_wready   <= 1'b1;
                        burst_len_reg  <= s_axi_awlen;
                        burst_size_reg <= s_axi_awsize;
                        burst_type_reg <= s_axi_awburst;
                        burst_cnt      <= 8'd0;
                        err_latch      <= 1'b0;

                        if (!awaddr_in_range) begin
                            err_latch <= 1'b1;
                            psel <= 4'b0000;
                            if (s_axi_awlen == 0) state <= ST_WR_RESP;
                            else begin burst_cnt <= 8'd1; state <= ST_ERR_SINK_W; end
                        end else begin
                            target_psel_reg <= aw_device_sel;
                            psel     <= aw_device_sel; // [修正点]: 在进入 Setup 前提前拉高 PSEL
                            paddr    <= s_axi_awaddr;
                            pprot    <= s_axi_awprot;
                            pwrite   <= 1'b1;
                            pwdata   <= s_axi_wdata;
                            pstrb    <= s_axi_wstrb;
                            state    <= ST_WR_SETUP;
                        end
                    end
                    else if (s_axi_arvalid) begin
                        s_axi_arready  <= 1'b1;
                        burst_len_reg  <= s_axi_arlen;
                        burst_size_reg <= s_axi_arsize;
                        burst_type_reg <= s_axi_arburst;
                        burst_cnt      <= 8'd0;
                        err_latch      <= 1'b0;

                        if (!araddr_in_range) begin
                            err_latch    <= 1'b1;
                            psel         <= 4'b0000;
                            s_axi_rdata  <= {DATA_WIDTH{1'b0}};
                            s_axi_rresp  <= RESP_SLVERR;
                            s_axi_rlast  <= (s_axi_arlen == 0);
                            s_axi_rvalid <= 1'b1;
                            state        <= ST_RD_RESP;
                        end else begin
                            target_psel_reg <= ar_device_sel;
                            psel     <= ar_device_sel; // [修正点]: 在进入 Setup 前提前拉高 PSEL
                            paddr    <= s_axi_araddr;
                            pprot    <= s_axi_arprot;
                            pwrite   <= 1'b0;
                            pwdata   <= {DATA_WIDTH{1'b0}};
                            pstrb    <= {STRB_WIDTH{1'b0}};
                            state    <= ST_RD_SETUP;
                        end
                    end else begin
                        psel <= 4'b0000;
                    end
                end

                ST_ERR_SINK_W: begin
                    if (s_axi_wvalid) begin
                        s_axi_wready <= 1'b1;
                        if (burst_cnt == burst_len_reg) state <= ST_WR_RESP;
                        else burst_cnt <= burst_cnt + 1'b1;
                    end
                end

                ST_WR_SETUP: begin
                    penable     <= 1'b1; 
                    state       <= ST_WR_ACCESS;
                end

                ST_WR_ACCESS: begin
                    if (pready) begin
                        penable     <= 1'b0;
                        timeout_cnt <= 5'd0;
                        if (pslverr) err_latch <= 1'b1;

                        if (burst_cnt < burst_len_reg) begin
                            burst_cnt <= burst_cnt + 1'b1;
                            if (burst_type_reg == 2'b01) paddr <= paddr + (1 << burst_size_reg);
                            psel <= 4'b0000; // 等待下一拍数据时拉低 PSEL
                            state <= ST_WR_NEXT_DATA;
                        end else begin
                            psel <= 4'b0000;
                            state <= ST_WR_RESP;
                        end
                    end else if (timeout_cnt == TIMEOUT_CYCLES - 1) begin
                        psel        <= 4'b0000;
                        penable     <= 1'b0;
                        timeout_cnt <= 5'd0;
                        err_latch   <= 1'b1;
                        if (burst_cnt < burst_len_reg) begin
                            burst_cnt <= burst_cnt + 1'b1;
                            state <= ST_ERR_SINK_W;
                        end else begin
                            state <= ST_WR_RESP;
                        end
                    end else begin
                        timeout_cnt <= timeout_cnt + 1'b1;
                    end
                end

                ST_WR_NEXT_DATA: begin
                    if (s_axi_wvalid) begin
                        s_axi_wready <= 1'b1;
                        pwdata       <= s_axi_wdata;
                        pstrb        <= s_axi_wstrb;
                        psel         <= target_psel_reg; // 重新发起 Setup
                        state        <= ST_WR_SETUP;
                    end
                end

                ST_WR_RESP: begin
                    if (s_axi_bvalid && s_axi_bready) begin
                        s_axi_bvalid <= 1'b0;
                        state        <= ST_IDLE;
                    end else begin
                        s_axi_bresp  <= err_latch ? RESP_SLVERR : RESP_OKAY;
                        s_axi_bvalid <= 1'b1;
                    end
                end

                ST_RD_SETUP: begin
                    penable     <= 1'b1;
                    state       <= ST_RD_ACCESS;
                end

                ST_RD_ACCESS: begin
                    if (pready) begin
                        penable     <= 1'b0;
                        psel        <= 4'b0000;
                        timeout_cnt <= 5'd0;
                        if (pslverr) err_latch <= 1'b1;

                        s_axi_rdata  <= prdata;
                        s_axi_rresp  <= (pslverr || err_latch) ? RESP_SLVERR : RESP_OKAY;
                        s_axi_rlast  <= (burst_cnt == burst_len_reg);
                        s_axi_rvalid <= 1'b1;
                        state        <= ST_RD_RESP;

                    end else if (timeout_cnt == TIMEOUT_CYCLES - 1) begin
                        psel        <= 4'b0000;
                        penable     <= 1'b0;
                        timeout_cnt <= 5'd0;
                        err_latch   <= 1'b1;

                        s_axi_rdata  <= {DATA_WIDTH{1'b0}};
                        s_axi_rresp  <= RESP_SLVERR;
                        s_axi_rlast  <= (burst_cnt == burst_len_reg);
                        s_axi_rvalid <= 1'b1;
                        state        <= ST_RD_RESP;
                    end else begin
                        timeout_cnt <= timeout_cnt + 1'b1;
                    end
                end

                ST_RD_RESP: begin
                    if (s_axi_rvalid && s_axi_rready) begin
                        if (burst_cnt < burst_len_reg) begin
                            burst_cnt <= burst_cnt + 1'b1;
                            if (err_latch && !araddr_in_range) begin
                                s_axi_rdata  <= {DATA_WIDTH{1'b0}};
                                s_axi_rresp  <= RESP_SLVERR;
                                s_axi_rlast  <= (burst_cnt + 1'b1 == burst_len_reg);
                                s_axi_rvalid <= 1'b1;
                            end else begin
                                s_axi_rvalid <= 1'b0;
                                s_axi_rlast  <= 1'b0;
                                if (burst_type_reg == 2'b01) paddr <= paddr + (1 << burst_size_reg);
                                psel         <= target_psel_reg; // 重新发起 Setup
                                state        <= ST_RD_SETUP;
                            end
                        end else begin
                            s_axi_rvalid <= 1'b0;
                            s_axi_rlast  <= 1'b0;
                            state        <= ST_IDLE;
                        end
                    end
                end

                default: state <= ST_IDLE;
            endcase
        end
    end

    `ifndef SYNTHESIS
    `ifndef __ICARUS__ 
    assert property (@(posedge clk) disable iff (!rst_n)
        (psel != 4'b0000 && !penable) |=> (psel != 4'b0000 && penable))
        else $error("SVA: Setup 之后未能进入 Access！");

    assert property (@(posedge clk) disable iff (!rst_n)
        (psel != 4'b0000 && penable && !pready) |=> (psel != 4'b0000 && penable && $stable(paddr) && $stable(pwrite)))
        else $error("SVA: APB 握手未完成，主设备中途撤销！");

    assert property (@(posedge clk) disable iff (!rst_n)
        (s_axi_bvalid && !s_axi_bready) |=> s_axi_bvalid);

    assert property (@(posedge clk) disable iff (!rst_n)
        (s_axi_rvalid && !s_axi_rready) |=> s_axi_rvalid);

    assert property (@(posedge clk) disable iff (!rst_n)
        (psel != 4'b0000 && !penable) |=> $stable(paddr));
    `endif
    `endif
// ==========================================
    // 开启仿真波形记录
    // ==========================================
    `ifdef COCOTB_SIM
    initial begin
        $dumpfile("wave.vcd");
        $dumpvars(0, soc_system_top);
    end
    `endif
endmodule