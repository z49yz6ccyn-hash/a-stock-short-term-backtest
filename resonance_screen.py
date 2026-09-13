# -*- coding: utf-8 -*-
"""
多策略共振选股
同一交易日多套策略同时命中同一只个股 = 信号共振，置信度更高
输出：backtest_data/resonance_result.json
"""
import os, sys, json, pickle
import pandas as pd
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "backtest_data")

# 启用共振选股的策略（盈利策略为主）
RESO_KEYS = ["S11", "S20", "S01", "S26", "S17", "S21", "S02", "S19", "S09", "S14", "S31"]

def main():
    pkl_path = os.path.join(DATA_DIR, "daily.pkl")
    if not os.path.exists(pkl_path):
        print("错误: 数据文件不存在，请先运行 update_data.py")
        sys.exit(1)

    print("加载行情数据...", flush=True)
    with open(pkl_path, "rb") as f:
        data = pickle.load(f)
    print("加载完成: %d 只股票" % len(data), flush=True)

    sys.path.insert(0, BASE)
    from backtest_engine_v2 import calc_indicators, select_stocks, STRATEGIES

    latest_date = None
    for code, df in data.items():
        if len(df) > 0:
            d = df["date"].max()
            if latest_date is None or d > latest_date:
                latest_date = d
    print("最新交易日: %s" % latest_date.strftime("%Y-%m-%d"), flush=True)

    print("预计算指标...", flush=True)
    stock_indicators = {}
    for code, df in data.items():
        if len(df) < 60:
            continue
        try:
            ind, c, o, h, l, v, pct = calc_indicators(df)
            stock_indicators[code] = (df, ind, c, o, h, l, v, pct)
        except Exception:
            continue

    print("共振选股中...", flush=True)
    resonance = {}

    for code, (df, ind, c, o, h, l, v, pct) in stock_indicators.items():
        day_idx = df.index[df["date"] == latest_date]
        if len(day_idx) == 0:
            continue
        i = day_idx[0]

        hit_strategies = []
        scores = {}
        for key in RESO_KEYS:
            try:
                cond, score = select_stocks(key, df, ind, c, o, h, l, v, pct, i)
                if cond and score > 0:
                    hit_strategies.append(key)
                    scores[key] = round(score, 2)
            except Exception:
                continue

        if hit_strategies:
            name = code
            uni_path = os.path.join(DATA_DIR, "universe.csv")
            if os.path.exists(uni_path):
                uni = pd.read_csv(uni_path)
                row = uni[uni["code"] == code]
                if len(row) > 0:
                    name = row.iloc[0].get("code_name", code)

            resonance[code] = {
                "code": code,
                "name": name,
                "close": round(float(c[i]), 2),
                "pct_chg": round(float(pct[i]), 2),
                "volume": int(v[i]),
                "resonance_count": len(hit_strategies),
                "strategies": hit_strategies,
                "scores": scores,
                "total_score": round(sum(scores.values()), 2),
            }

    result_list = sorted(resonance.values(), key=lambda x: (x["resonance_count"], x["total_score"]), reverse=True)

    print("\n共振选股结果:", flush=True)
    print("  总命中股票: %d 只" % len(result_list), flush=True)
    for n in range(5, 0, -1):
        count = len([r for r in result_list if r["resonance_count"] >= n])
        if count > 0:
            print("  %d重共振: %d 只" % (n, count), flush=True)

    print("\nTop 20 共振选股:", flush=True)
    for r in result_list[:20]:
        print("  %s %-10s 共振:%d 价格:%.2f 涨幅:%.2f%% 策略:%s" % (
            r["code"], r["name"], r["resonance_count"], r["close"], r["pct_chg"], ",".join(r["strategies"])), flush=True)

    out_path = os.path.join(DATA_DIR, "resonance_result.json")
    output = {
        "date": latest_date.strftime("%Y-%m-%d"),
        "total_stocks": len(result_list),
        "strategies_used": RESO_KEYS,
        "top20": result_list[:20],
        "all": result_list,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("\n结果已保存: %s" % out_path, flush=True)

if __name__ == "__main__":
    main()
