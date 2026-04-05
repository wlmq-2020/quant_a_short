#!/bin/bash
# A股量化系统 - 每日自动优化任务
# 功能：下载数据 → 全策略优化 → 策略进化（自动更新配置）→ 回测验证

set -e

PROJECT_ROOT="/root/quant_a_short"
LOG_DIR="${PROJECT_ROOT}/logs"
CRON_LOG="${LOG_DIR}/daily_optimization_cron.log"

cd "${PROJECT_ROOT}"

echo "============================================================" | tee -a "${CRON_LOG}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始每日自动优化任务" | tee -a "${CRON_LOG}"
echo "============================================================" | tee -a "${CRON_LOG}"

# 1. 下载最新股票数据
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [1/5] 下载最新股票数据..." | tee -a "${CRON_LOG}"
python3 main.py --fetch-data >> "${CRON_LOG}" 2>&1

# 2. 全策略参数优化
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [2/5] 运行全策略参数优化..." | tee -a "${CRON_LOG}"
python3 main.py --optimize-all >> "${CRON_LOG}" 2>&1

# 3. 策略进化（自动更新config.py）
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [3/5] 运行策略进化（自动更新配置）..." | tee -a "${CRON_LOG}"
python3 main.py --evolve-strategies --auto-update >> "${CRON_LOG}" 2>&1

# 4. 用最优策略回测验证
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [4/5] 回测验证（默认策略）..." | tee -a "${CRON_LOG}"
python3 main.py >> "${CRON_LOG}" 2>&1

echo "============================================================" | tee -a "${CRON_LOG}"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 每日自动优化任务完成！" | tee -a "${CRON_LOG}"
echo "============================================================" | tee -a "${CRON_LOG}"
