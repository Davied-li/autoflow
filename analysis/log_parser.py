import os
import sys    # 🚨 新增：用来接收命令行参数
import re
import glob

class AutoFlowLogParser:
    def __init__(self, report_dir):
        self.report_dir = report_dir
        self.pass_pattern = re.compile(r'\[PASS\]')
        self.fail_pattern = re.compile(r'\[FAIL\]|Error-|Fatal')

    def analyze_all_logs(self, module_filter=""):
        """遍历 report 目录，并支持通过模块名过滤日志"""
        
        # 🚨 核心逻辑：如果有过滤词，就搜索包含该词的日志；否则搜索全部
        search_pattern = f'sim_*{module_filter}*.log'
        log_files = glob.glob(os.path.join(self.report_dir, search_pattern))
        
        if not log_files:
            print(f"⚠️ 报告库中没有找到包含关键字 '{module_filter}' 的仿真日志！")
            return

        print("\n" + "="*50)
        if module_filter:
            print(f"📊 AutoFlow 战报 (仅展示模块: {module_filter})")
        else:
            print("📊 AutoFlow 自动化测试回归战报 (全量)")
        print("="*50)
        
        total_tests = len(log_files)
        passed = 0
        failed = 0
        unknown = 0

        for log_path in log_files:
            filename = os.path.basename(log_path)
            status = "UNKNOWN"
            
            with open(log_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if self.fail_pattern.search(content):
                    status = "❌ FAIL"
                    failed += 1
                elif self.pass_pattern.search(content):
                    status = "✅ PASS"
                    passed += 1
                else:
                    status = "❓ UNKNOWN"
                    unknown += 1
            
            print(f"[{status}] -> {filename}")

        print("-" * 50)
        print(f"总计用例: {total_tests} | 成功: {passed} | 失败: {failed} | 未知: {unknown}")
        pass_rate = (passed / total_tests) * 100 if total_tests > 0 else 0
        print(f"🏆 总体通过率: {pass_rate:.1f}%")
        print("="*50 + "\n")

# ================= 测试入口 =================
if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    report_folder = os.path.join(current_dir, '../report')
    
    # 🚨 接收终端传进来的关键字，如果没有传，默认为空（抓取全部）
    filter_word = ""
    if len(sys.argv) > 1:
        filter_word = sys.argv[1]
    
    analyzer = AutoFlowLogParser(report_folder)
    # 把关键字喂给分析器
    analyzer.analyze_all_logs(filter_word)