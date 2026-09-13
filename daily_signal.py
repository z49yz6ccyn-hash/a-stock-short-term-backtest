# -*- coding: utf-8 -*-
"""
每日收盘信号一键生成
流程：更新行情（--no-update跳过）→ 多策略共振选股 → 生成信号报告
输出：backtest_data/daily_signal.md
"""
import os, sys, json, subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "backtest_data")

def main():
    no_update = "--no-update" in sys.argv

    if not no_update:
        print("=" * 50, flush=True)
        print("  步骤1/3: 更新行情数据", flush=True)
        print("=" * 50, flush=True)
        subprocess.run([sys.executable, "-X", "utf8", "update_data.py"], cwd=BASE)

    print("=" * 50, flush=True)
    print("  步骤2/3: 多策略共振选股", flush=True)
    print("=" * 50, flush=True)
    subprocess.run([sys.executable, "-X", "utf8", "resonance_screen.py"], cwd=BASE)

    print("=" * 50, flush=True)
    print("  步骤3/3: 生成信号报告", flush=True)
    print("=" * 50, flush=True)

    res_path = os.path.join(DATA_DIR, "resonance_result.json")
    if not os.path.exists(res_path):
        print("错误: 共振选股结果不存在")
        sys.exit(1)

    with open(res_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    date = data.get("date", "")
    top20 = data.get("top20", [])
    total = data.get("total_stocks", 0)

    md = "# A股每日短线策略信号报告\n\n"
    md += "**日期：** %s\n\n" % date
    md += "**选股策略：** 多策略共振（11套策略同时命中）\n\n"
    md += "---\n\n"
    md += "## 📊 信号概览\n\n"
    md += "- **总命中股票：** %d 只\n" % total
    for n in range(5, 0, -1):
        count = len([r for r in data.get("all", []) if r["resonance_count"] >= n])
        if count > 0:
            md += "- **%d重共振：** %d 只\n" % (n, count)
    md += "\n---\n\n"
    md += "## 🎯 Top 20 共振选股\n\n"
    md += "| 排名 | 代码 | 名称 | 最新价 | 涨跌幅 | 共振数 | 命中策略 | 综合分 |\n"
    md += "|------|------|------|--------|--------|--------|----------|--------|\n"
    for i, s in enumerate(top20):
        md += "| %d | %s | %s | %.2f | %.2f%% | %d重 | %s | %.2f |\n" % (
            i+1, s["code"], s["name"], s["close"], s["pct_chg"],
            s["resonance_count"], ",".join(s["strategies"]), s.get("total_score", 0))
    md += "\n---\n\n"
    md += "## 📋 交易纪律\n\n"
    md += "1. **仓位管理：** 单只个股仓位不超过总资金20%，同时持仓不超过5只\n"
    md += "2. **止损纪律：** 买入后亏损达8%立即止损，不补仓、不摊平\n"
    md += "3. **止盈策略：** 盈利达15%分批止盈，或持有2-4天后根据走势决定\n"
    md += "4. **大盘过滤：** 上证综指跌破MA20时减少仓位或空仓观望\n"
    md += "5. **买入时机：** 优选尾盘14:30后买入，避免早盘追高\n\n"
    md += "---\n\n"
    md += "> ⚠️ **风险提示：** 以上个股基于历史回测策略筛选，不构成投资建议，股市有风险，投资需谨慎。\n"

    out_path = os.path.join(DATA_DIR, "daily_signal.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)

    print("信号报告已生成: %s" % out_path, flush=True)
    print("Top 20 股票:", flush=True)
    for i, s in enumerate(top20[:10]):
        print("  %d. %s %s 共振:%d 价格:%.2f 涨幅:%.2f%%" % (
            i+1, s["code"], s["name"], s["resonance_count"], s["close"], s["pct_chg"]), flush=True)

if __name__ == "__main__":
    main()
