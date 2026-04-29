// rtl/tb_adder.v
module tb_adder;
    reg  [7:0] a, b;
    wire [8:0] sum;
    
    // 接收 AutoFlow 传入的参数
    int seed;
    string testcase;

    // 实例化刚刚写的加法器
    adder uut (
        .a(a), 
        .b(b), 
        .sum(sum)
    );

    initial begin
        $dumpfile("waves/adder_wave.vcd"); 
        $dumpvars(0, tb_adder);
        // 从底层命令行捕获 Python 注入的参数！
        if (!$value$plusargs("ntb_random_seed=%d", seed)) seed = 0;
        if (!$value$plusargs("TESTNAME=%s", testcase)) testcase = "default";

        $display("\n========================================");
        $display("🚀 芯片验证启动 -> 运行用例: %s | 随机种子: %d", testcase, seed);
        
        // 我们利用不同的 TESTNAME 来跑不同的测试分支
        if (testcase == "adder_sanity_pass") begin
            // 正常的测试，绝对能通过
            a = 8'd10; b = 8'd20;
            #10;
            if (sum == 9'd30) 
                $display("[PASS] 基础加法测试完美通过: 10 + 20 = %d", sum);
            else 
                $display("[FAIL] 基础加法测试失败!");
        end
        
        else if (testcase == "adder_corner_fail") begin
            // 🚨 我们故意在这里写个错误的预期值，让它打印 FAIL！
            // 为了测试咱们的 Python Log Parser 是不是真的能抓到报错
            a = 8'd255; b = 8'd1;
            #10;
            $display("[FAIL] 这是一个[故意注入的错误]，用来测试分析器！期望输出 0，实际输出 %d", sum);
        end
        
        $display("========================================\n");
        $finish;
    end
endmodule