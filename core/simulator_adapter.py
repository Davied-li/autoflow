import os
import subprocess
from config_parser import AutoFlowConfigParser # 🧠 把咱们的大脑引进来

class VCSAdapter:
    def __init__(self, config_data):
        self.config = config_data
        self.sim_config = self.config.get('simulation_config', {})
        self.compile_opts = self.sim_config.get('compile_options', '')
        self.top_module = self.sim_config.get('top_module', 'tb_top')
        self.rtl_paths = self.sim_config.get('rtl_paths', [])

    def generate_compile_cmd(self):
        rtl_files = " ".join(self.rtl_paths)
        cmd = f"vcs {self.compile_opts} {rtl_files} -top {self.top_module}"
        return cmd

    def generate_run_cmd(self, testcase_name, seed):
        cmd = f"./simv +ntb_random_seed={seed} +TESTNAME={testcase_name}"
        if self.config.get('global_switches', {}).get('dump_waveform'):
            cmd += " +fsdb+autoflush"
        return cmd

    def execute_command(self, cmd_string, log_name="console.log"):
        """升级版：执行命令并保存日志到 report 目录"""
        print(f"🚀 [AutoFlow 真机执行]: {cmd_string}")
        
        # 确保 report 目录存在
        report_dir = os.path.join(os.path.dirname(__file__), '../report')
        os.makedirs(report_dir, exist_ok=True)
        log_path = os.path.join(report_dir, log_name)

        try:
            result = subprocess.run(
                cmd_string, 
                shell=True, 
                check=True, 
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, 
                universal_newlines=True
            )
            
            # 🚨 核心新增：把输出写进 .log 文件
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(result.stdout)
                
            print(f"✅ 执行成功！日志已保存至 -> report/{log_name}")
            
        except subprocess.CalledProcessError as e:
            print(f"❌ 运行报错了！")
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(e.stderr)

# ================= 终极点火入口 =================
# ================= 终极点火入口 =================
if __name__ == "__main__":
    import sys # 🚨 新增引入 sys 模块用来接收命令行参数
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 🚨 升级逻辑：如果运行时带了参数，就用参数指向的 yaml；否则默认用 regression_test.yaml
    if len(sys.argv) > 1:
        yaml_file = sys.argv[1]
        yaml_path = os.path.join(current_dir, '../', yaml_file)
    else:
        yaml_path = os.path.join(current_dir, '../configs/regression_test.yaml')

    from config_parser import AutoFlowConfigParser
    
    parser = AutoFlowConfigParser(yaml_path)
    adapter = VCSAdapter(parser.config_data)

    print("\n" + "="*40 + "\n🔨 阶段一: 自动编译 RTL\n" + "="*40)
    # 编译日志保存为 compile.log
    adapter.execute_command(adapter.generate_compile_cmd(), "compile.log")

    print("\n" + "="*40 + "\n🏁 阶段二: 自动批量运行回归测试\n" + "="*40)
    cases = parser.get_testcases()
    for case in cases:
        for seed in case['seeds']:
            print(f"\n▶️ 准备出击 -> 用例: [{case['name']}] | 随机种子: [{seed}]")
            run_cmd = adapter.generate_run_cmd(case['name'], seed)
            # 🚨 核心新增：每个用例生成独立的 log 文件
            log_filename = f"sim_{case['name']}_seed{seed}.log"
            adapter.execute_command(run_cmd, log_filename)