// rtl/adder.v
module adder (
    input  wire [7:0] a,
    input  wire [7:0] b,
    output wire [8:0] sum
);
    // 真实的加法逻辑
    assign sum = a + b;
endmodule