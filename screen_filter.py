# -*- coding: utf-8 -*-
"""
二次筛选优选个股
基于共振选股结果，按综合评分分A/B/C三级
输出：backtest_data/target_stocks.json
"""
import os, sys, json

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "backtest_data")

# 盈利策略（回测收益为正的策略）
PROFIT_STRATEGIES = {"S01", "S06", "S10", "S21"}

def main():
    res_path = os.path.join(DATA_DIR, "resonance_result.json")
    if not os.path.exists(res_path):
        print("错误: 共振选股结果不存在，请先运行 resonance_screen.py")
        sys.exit(1)

    with open(res_path, "r", encoding="utf-8") as f:
        res_data = json.load(f)

    all_stocks = res_data.get("all", [])
    print("共振选股总数: %d 只" % len(all_stocks), flush=True)

    scored = []
    for s in all_stocks:
        resonance_count = s["resonance_count"]
        strategies = s.get("strategies", [])
        profit_hits = len([k for k in strategies if k in PROFIT_STRATEGIES])
        total_score = s.get("total_score", 0)
        pct = s.get("pct_chg", 0)

        pct_penalty = max(0, pct - 5) * 0.5

        final_score = (resonance_count * 1.2 + profit_hits * 2.0 +
                       total_score / 100 - pct_penalty)

        s["profit_hits"] = profit_hits
        s["final_score"] = round(final_score, 2)
        scored.append(s)

    scored.sort(key=lambda x: x["final_score"], reverse=True)

    grade_a = []
    grade_b = []
    grade_c = []

    for s in scored:
        if s["resonance_count"] >= 5 and s["profit_hits"] >= 2:
            grade_a.append(s)
        elif s["resonance_count"] >= 3 or s["final_score"] >= 5:
            grade_b.append(s)
        else:
            grade_c.append(s)

    grade_a = grade_a[:5]
    grade_b = grade_b[:10]
    grade_c = grade_c[:10]

    print("\n分级结果:", flush=True)
    print("  A级首选: %d 只" % len(grade_a), flush=True)
    print("  B级备选: %d 只" % len(grade_b), flush=True)
    print("  C级观察: %d 只" % len(grade_c), flush=True)

    print("\nA级首选:", flush=True)
    for s in grade_a:
        print("  %s %-10s 共振:%d 盈利策略:%d 价格:%.2f 涨幅:%.2f%% 综合分:%.2f" % (
            s["code"], s["name"], s["resonance_count"], s["profit_hits"],
            s["close"], s["pct_chg"], s["final_score"]), flush=True)

    output = {
        "date": res_data.get("date", ""),
        "grade_a": grade_a,
        "grade_b": grade_b,
        "grade_c": grade_c,
        "profit_strategies": list(PROFIT_STRATEGIES),
        "scoring_rule": "共振数×1.2 + 盈利策略命中×2.0 + 综合分/100 - 涨幅惩罚",
    }

    out_path = os.path.join(DATA_DIR, "target_stocks.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("\n结果已保存: %s" % out_path, flush=True)

if __name__ == "__main__":
    main()
