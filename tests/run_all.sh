#!/bin/bash

set -e

export PATH=$PATH:/home/jjt/allure-2.13.8/bin

echo "--- [1/4] Cleaning old data ---"
mkdir -p allure-results
rm -rf allure-results/*
rm -rf sim_build/

mkdir -p ../waves
mkdir -p ../waves_svg
rm -f ../waves/*.vcd
rm -f ../waves_svg/*.svg

echo "--- [2/4] Running AXI-APB Regression ---"

# 关键：这里临时关闭 set -e
# 这样即使 pytest 有 failed，后面也会继续生成 Allure 报告。
set +e
AUTOFLOW_SEED=${AUTOFLOW_SEED:-20260428} pytest test_project_overview.py test_runner.py --alluredir=./allure-results
PYTEST_EXIT_CODE=$?
set -e

echo "--- [3/4] Injecting Environment Info ---"

cat <<EOF > allure-results/environment.properties
OS=$(uname -s)
Python=$(python3 -V 2>&1)
Simulator=Synopsys_VCS
Project=AutoFlow_Verification
EOF

echo "--- [4/4] Generating Allure Report ---"

allure generate ./allure-results -o ./allure-report --clean

echo "======================================="
echo "Allure report generated."
echo "pytest exit code = ${PYTEST_EXIT_CODE}"
echo "======================================="

exit ${PYTEST_EXIT_CODE}