# -*- coding: utf-8 -*-
"""
优选个股独立页面生成
读取 target_stocks.json → 渲染 stock_pick.html
"""
import os, sys, json

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "backtest_data")

INDUSTRY_MAP = {
    "603261": "航空装备/军机挂弹",
    "600649": "上海国资地产/破净",
    "000922": "特种电机/核电",
}

def get_industry(code):
    code_num = code.split(".")[-1] if "." in code else code
    return INDUSTRY_MAP.get(code_num, "待补充")

def render_stock_card(s, grade):
    strategies = ",".join(s.get("strategies", []))
    profit_hits = s.get("profit_hits", 0)
    color = {"A": "#ff6b6b", "B": "#ffd93d", "C": "#6bcb77"}.get(grade, "#888")
    return """
    <div class="stock-card">
      <div class="stock-header">
        <span class="stock-grade" style="background:%s">%s级</span>
        <span class="stock-name">%s</span>
        <span class="stock-code">%s</span>
      </div>
      <div class="stock-body">
        <div class="stock-metrics">
          <div class="metric"><span class="label">最新价</span><span class="value">%.2f</span></div>
          <div class="metric"><span class="label">涨跌幅</span><span class="value %s">%.2f%%</span></div>
          <div class="metric"><span class="label">共振数</span><span class="value">%d重</span></div>
          <div class="metric"><span class="label">盈利策略</span><span class="value">%d个</span></div>
          <div class="metric"><span class="label">综合分</span><span class="value">%.2f</span></div>
        </div>
        <div class="stock-info">
          <p><b>命中策略：</b>%s</p>
          <p><b>行业题材：</b>%s</p>
          <p><b>交易建议：</b>止损-8%%，止盈+15%%，持有2-4天</p>
        </div>
      </div>
    </div>
    """ % (
        color, grade, s.get("name", ""), s.get("code", ""),
        s.get("close", 0), "up" if s.get("pct_chg", 0) >= 0 else "down", s.get("pct_chg", 0),
        s.get("resonance_count", 0), profit_hits, s.get("final_score", 0),
        strategies, get_industry(s.get("code", ""))
    )

def main():
    target_path = os.path.join(DATA_DIR, "target_stocks.json")
    if not os.path.exists(target_path):
        print("错误: 优选个股数据不存在，请先运行 screen_filter.py")
        sys.exit(1)

    with open(target_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    date = data.get("date", "")
    grade_a = data.get("grade_a", [])
    grade_b = data.get("grade_b", [])
    grade_c = data.get("grade_c", [])

    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>回测优选个股 - %s</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
       background: #0a0e1a; color: #e0e6f0; padding: 20px; }
.container { max-width: 1200px; margin: 0 auto; }
.header { text-align: center; margin-bottom: 30px; }
.header h1 { font-size: 28px; color: #ffd93d; margin-bottom: 8px; }
.header .date { font-size: 14px; color: #8892a6; }
.header .summary { margin-top: 15px; display: flex; justify-content: center; gap: 30px; }
.header .summary .item { text-align: center; }
.header .summary .num { font-size: 24px; font-weight: bold; }
.header .summary .label { font-size: 12px; color: #8892a6; }
.grade-section { margin-bottom: 30px; }
.grade-title { font-size: 20px; font-weight: bold; margin-bottom: 15px; padding-left: 10px; border-left: 4px solid; }
.grade-title.a { border-color: #ff6b6b; color: #ff6b6b; }
.grade-title.b { border-color: #ffd93d; color: #ffd93d; }
.grade-title.c { border-color: #6bcb77; color: #6bcb77; }
.stock-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 15px; }
.stock-card { background: #131829; border: 1px solid #2a3050; border-radius: 12px; padding: 16px; transition: transform 0.2s; }
.stock-card:hover { transform: translateY(-2px); border-color: #4a5080; }
.stock-header { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.stock-grade { padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; color: #fff; }
.stock-name { font-size: 16px; font-weight: bold; flex: 1; }
.stock-code { font-size: 12px; color: #8892a6; font-family: monospace; }
.stock-metrics { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-bottom: 12px; }
.metric { text-align: center; }
.metric .label { display: block; font-size: 11px; color: #8892a6; margin-bottom: 2px; }
.metric .value { font-size: 14px; font-weight: bold; }
.metric .value.up { color: #ff6b6b; }
.metric .value.down { color: #6bcb77; }
.stock-info p { font-size: 12px; color: #a0a8c0; margin-bottom: 4px; line-height: 1.5; }
.stock-info b { color: #c0c8e0; }
.rules { background: #131829; border: 1px solid #2a3050; border-radius: 12px; padding: 20px; margin-top: 20px; }
.rules h3 { color: #ffd93d; margin-bottom: 10px; }
.rules p { font-size: 13px; color: #a0a8c0; line-height: 1.8; }
.source-note { text-align: center; margin-top: 20px; font-size: 11px; color: #556; }
@media (max-width: 640px) {
  .stock-grid { grid-template-columns: 1fr; }
  .stock-metrics { grid-template-columns: repeat(3, 1fr); }
  .header h1 { font-size: 22px; }
}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🎯 回测优选个股</h1>
    <div class="date">数据日期：%s</div>
    <div class="summary">
      <div class="item"><div class="num" style="color:#ff6b6b">%d</div><div class="label">A级首选</div></div>
      <div class="item"><div class="num" style="color:#ffd93d">%d</div><div class="label">B级备选</div></div>
      <div class="item"><div class="num" style="color:#6bcb77">%d</div><div class="label">C级观察</div></div>
    </div>
  </div>
""" % (date, date, len(grade_a), len(grade_b), len(grade_c))

    if grade_a:
        html += '<div class="grade-section"><div class="grade-title a">A级首选（高置信度）</div><div class="stock-grid">'
        for s in grade_a:
            html += render_stock_card(s, "A")
        html += '</div></div>'

    if grade_b:
        html += '<div class="grade-section"><div class="grade-title b">B级备选（中等置信度）</div><div class="stock-grid">'
        for s in grade_b:
            html += render_stock_card(s, "B")
        html += '</div></div>'

    if grade_c:
        html += '<div class="grade-section"><div class="grade-title c">C级观察（低置信度）</div><div class="stock-grid">'
        for s in grade_c:
            html += render_stock_card(s, "C")
        html += '</div></div>'

    html += """
  <div class="rules">
    <h3>📋 统一交易规则</h3>
    <p>1. <b>仓位管理</b>：单只个股仓位不超过总资金20%，同时持仓不超过5只。</p>
    <p>2. <b>止损纪律</b>：买入后亏损达8%立即止损，不补仓、不摊平。</p>
    <p>3. <b>止盈策略</b>：盈利达15%分批止盈，或持有2-4天后根据走势决定。</p>
    <p>4. <b>大盘过滤</b>：上证综指跌破MA20时减少仓位或空仓观望（逆向策略除外）。</p>
    <p>5. <b>买入时机</b>：优选尾盘14:30后买入，避免早盘追高。</p>
    <p>6. <b>风险提示</b>：以上个股基于历史回测策略筛选，不构成投资建议，股市有风险，投资需谨慎。</p>
  </div>
  <div class="source-note">
    数据来源：A股回测系统 | 筛选规则：多策略共振+盈利策略加权+综合评分 | 生成时间：%s
  </div>
</div>
</body>
</html>
""" % date

    out_path = os.path.join(BASE, "stock_pick.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print("优选个股页面已生成: %s" % out_path, flush=True)
    print("  A级: %d 只, B级: %d 只, C级: %d 只" % (len(grade_a), len(grade_b), len(grade_c)), flush=True)

if __name__ == "__main__":
    main()
