import yaml
import os

class AutoFlowConfigParser:
    def __init__(self, config_path):
        """初始化解析器并加载 YAML 文件"""
        self.config_path = config_path
        self.config_data = self._load_yaml()

    def _load_yaml(self):
        """内部方法：安全读取 YAML 文件"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"❌ 找不到配置文件: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            # 使用 safe_load 防止执行恶意的 YAML 注入
            return yaml.safe_load(f)

    def get_simulator_type(self):
        """获取选用的仿真器"""
        return self.config_data.get('global_switches', {}).get('simulator', 'icarus')

    def get_testcases(self):
        """获取所有测试用例配置"""
        return self.config_data.get('test_configuration', {}).get('testcases', [])

# ================= 测试入口 =================
if __name__ == "__main__":
    # 动态获取当前脚本所在目录，拼接出 yaml 文件的绝对路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    yaml_path = os.path.join(current_dir, '../configs/regression_test.yaml')

    # 实例化解析器
    parser = AutoFlowConfigParser(yaml_path)
    
    # 提取并打印数据
    simulator = parser.get_simulator_type()
    cases = parser.get_testcases()

    print(f"✅ 成功加载 AutoFlow 配置！")
    print(f"🔧 当前底层仿真器引擎: {simulator.upper()}")
    print(f"📦 共解析到 {len(cases)} 个测试用例任务:")
    
    for case in cases:
        print(f"  -> 任务名: {case['name']} | 脚本: {case['module']}.py | 种子队列: {case['seeds']}")