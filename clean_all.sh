#!/bin/bash
# 只清理仿真中间产物，不碰报告数据
echo "Cleaning simulation artifacts..."

rm -rf tests/sim_build/
rm -rf tests/.pytest_cache/
rm -rf tests/__pycache__/
rm -f tests/ucli.key
rm -f tests/results.xml
rm -f tests/*.log

echo "Cleanup done. Allure reports remain safe."