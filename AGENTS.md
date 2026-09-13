# AGENTS.md — A股短线交易回测项目

本文件是本项目所有AI代理必须遵守的最高优先级项目指导。

## 0. 最高优先级硬约束

### 0.1 所有数据必须真实，严禁模拟/编造/伪造

- 本项目产出的一切数字、图表、报告、结论，必须源自真实回测运行结果或真实公开数据源。
- 绝对禁止：凭空编造收益率、手写"示例数据"充当结果、用占位数字填充。
- 拿不到真实数据就明确标注"数据缺失/不可得"，而不是造一个数补上。

### 0.2 数据溯源可核查

- 任何引用真实数据的输出，附上来源与更新时间。
- 禁止在未跑通回测的情况下宣称"策略盈利X%"。

## 1. 项目概述

A股短线交易策略统一回测项目：对28套短线策略（S01~S22, S26~S29, S31, S32）做回测，输出各策略收益指标、累计收益曲线、多策略共振选股、优选个股。

- 运行环境：Python 3.12+，pandas/numpy/akshare/flask
- Web控制台：http://127.0.0.1:5000

## 2. 目录结构

```
├── update_data.py           # 行情数据下载（akshare新浪，4进程）
├── backtest_engine_v2.py    # 回测引擎v2（28套策略+大盘趋势过滤+样本外分段）
├── resonance_screen.py      # 多策略共振选股
├── screen_filter.py         # 二次筛选优选个股（A/B/C分级）
├── gen_stock_pick_html.py   # 优选个股页面生成
├── daily_signal.py          # 每日信号一键生成
├── AGENTS.md                 # 本文件
├── backtest_data/
│   ├── daily.pkl            # 全市场日线数据（pickle格式，gitignore）
│   ├── universe.csv         # 股票池
│   ├── sh000001.csv        # 上证综指（趋势过滤用）
│   ├── resonance_result.json # 共振选股结果
│   ├── target_stocks.json   # 优选个股（A/B/C分级）
│   └── results_v2/          # v2回测结果
│       ├── summary_v2.json  # 策略收益汇总
│       └── {strategy}_equity.csv # 各策略权益曲线（gitignore）
└── webapp/
    ├── app.py               # Flask后端
    └── templates/
        └── index.html       # 前端四页签控制台
```

## 3. 核心参数

- 初始资金：100万
- 佣金：万3，印花税：千1（卖出），滑点：千1
- 每日选股Top N=3，最大持仓=5
- 大盘趋势过滤：上证综指站上MA20才开仓（逆向策略S07/S28/S12/S13/S32豁免）
- 样本外验证：按Q1/Q2/Q3分段输出收益

## 4. 策略列表

28套策略，详见 backtest_engine_v2.py 的 STRATEGIES 字典。
盈利策略（2025-09至2026-09回测）：S11, S20, S01, S26, S17, S21, S02, S19, S09, S14, S31, S16, S27
共振选股启用：S11, S20, S01, S26, S17, S21, S02, S19, S09, S14, S31

## 5. 标准操作流程

### 5.1 完整流水线（首次/定期更新）
```
python update_data.py          # 1.下载行情数据（约15分钟）
python backtest_engine_v2.py   # 2.跑回测v2（约30分钟，支持断点续传）
python resonance_screen.py      # 3.多策略共振选股（约5分钟）
python screen_filter.py         # 4.二次筛选优选个股
python gen_stock_pick_html.py   # 5.生成优选个股页面
```

### 5.2 每日信号（收盘后）
```
python daily_signal.py --no-update  # 用已有数据快速生成
python daily_signal.py               # 先更新行情再生成
```

### 5.3 启动Web控制台
```
cd webapp
python app.py
# 访问 http://127.0.0.1:5000
```

## 6. 代码规范

- 统一 `# -*- coding: utf-8 -*-` 头
- 引擎内部用numpy矩阵批量计算，不要逐行循环
- 修改引擎/脚本后必须重跑受影响的下游产物

## 7. 交付与验证

- 交付任何收益数字前，对照 backtest_data/results_v2/summary_v2.json 核验
- 看板、收益图中的口径说明必须与引擎一致
- 新策略加入后：引擎注册→跑回测→结果落盘→更新看板→重新交付

## 8. 手机端预览

- Flask绑定0.0.0.0，手机与电脑同一WiFi时访问 http://电脑局域网IP:5000
- 不在同一网络时需用内网穿透（ngrok/cpolar）
