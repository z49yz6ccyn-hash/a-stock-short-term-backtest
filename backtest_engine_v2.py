# -*- coding: utf-8 -*-
"""
A股短线策略回测引擎 v2
- 28套策略（S01~S22, S26~S29, S31, S32）
- 大盘趋势过滤（上证综指站上MA20才开仓，逆向策略豁免）
- 样本外验证（按Q1/Q2/Q3分段输出收益）
- 输出：backtest_data/results_v2/summary_v2.json + {key}_equity.csv
"""
import os, sys, json, time, pickle
import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "backtest_data")
RESULT_DIR = os.path.join(DATA_DIR, "results_v2")
os.makedirs(RESULT_DIR, exist_ok=True)

# ============ 全局参数 ============
INIT_CAPITAL = 1_000_000  # 初始资金100万
COMMISSION = 0.0003        # 佣金万3
STAMP_TAX = 0.001          # 印花税千1（卖出）
SLIPPAGE = 0.001           # 滑点千1
TOP_N = 3                   # 每日选股Top N
MAX_POS = 5                 # 最大持仓数
RISK_FREE = 0.02           # 无风险利率

# 大盘趋势过滤豁免策略（逆向/超跌类）
TREND_FILTER_OFF = {"S07", "S28", "S12", "S13", "S32"}

# ============ 策略定义 ============
# 每个策略：name, hold(持有天数), sl(止损%), tp(止盈%), note
STRATEGIES = {
    "S01": {"name": "均线多头+放量突破", "hold": 2, "sl": 8, "tp": 15, "note": "MA5>MA10>MA20+当日放量突破20日高点"},
    "S02": {"name": "MACD金叉+趋势", "hold": 3, "sl": 7, "tp": 12, "note": "MACD金叉+DIF>0+站上MA20"},
    "S03": {"name": "缩量回调支撑", "hold": 3, "sl": 6, "tp": 10, "note": "回调至MA10/MA20支撑+缩量+收阳"},
    "S04": {"name": "涨停板回调", "hold": 2, "sl": 8, "tp": 15, "note": "5日内涨停后回调不破涨停开盘价+企稳"},
    "S05": {"name": "底部长阳反转", "hold": 4, "sl": 8, "tp": 18, "note": "20日新低后放量长阳（涨幅>5%）"},
    "S06": {"name": "趋势跟踪MA20", "hold": 4, "sl": 9, "tp": 12, "note": "站上MA20+MA20向上+回踩不破"},
    "S07": {"name": "超跌反弹RSI", "hold": 3, "sl": 7, "tp": 10, "note": "RSI<30超卖+收阳+放量（逆向，豁免趋势过滤）"},
    "S08": {"name": "放量突破平台", "hold": 3, "sl": 7, "tp": 14, "note": "20日横盘平台（振幅<15%）+放量突破"},
    "S09": {"name": "均线金叉MA5MA10", "hold": 2, "sl": 6, "tp": 10, "note": "MA5上穿MA10+站上MA20+放量"},
    "S10": {"name": "量价齐升", "hold": 5, "sl": 8, "tp": 15, "note": "连续3日量能递增+价格递增+MA多头"},
    "S11": {"name": "BOLL上轨突破", "hold": 3, "sl": 7, "tp": 12, "note": "突破BOLL上轨+放量+收口后开口"},
    "S12": {"name": "KDJ超卖金叉", "hold": 2, "sl": 6, "tp": 10, "note": "KDJ K<20+金叉+收阳（逆向，豁免趋势过滤）"},
    "S13": {"name": "跳空缺口回补", "hold": 3, "sl": 7, "tp": 12, "note": "向下跳空缺口后回补缺口+放量（逆向）"},
    "S14": {"name": "尾盘拉升强势", "hold": 1, "sl": 5, "tp": 8, "note": "尾盘1小时涨幅>2%+放量+站上MA5"},
    "S15": {"name": "低开高走反转", "hold": 2, "sl": 6, "tp": 12, "note": "低开>2%后收阳涨幅>3%+放量"},
    "S16": {"name": "连续小阳加速", "hold": 3, "sl": 7, "tp": 14, "note": "连续3日小阳（涨幅1-3%）+第4日放量"},
    "S17": {"name": "高送转预期", "hold": 5, "sl": 8, "tp": 18, "note": "小盘+高公积金+高未分配利润+年报季"},
    "S18": {"name": "龙头首阴", "hold": 2, "sl": 8, "tp": 15, "note": "连板后首次阴线+不破5日线+缩量"},
    "S19": {"name": "板块轮动跟随", "hold": 2, "sl": 6, "tp": 10, "note": "板块龙头涨停+同板块跟风股启动"},
    "S20": {"name": "强势股回调", "hold": 4, "sl": 10, "tp": 20, "note": "20日涨幅>30%后回调至MA10+企稳"},
    "S21": {"name": "突破前高+量能", "hold": 4, "sl": 8, "tp": 14, "note": "突破60日前高+量>20日均量1.5倍+MA多头"},
    "S22": {"name": "十字星变盘", "hold": 2, "sl": 6, "tp": 12, "note": "低位十字星+缩量+次日放量收阳"},
    "S26": {"name": "周线突破", "hold": 5, "sl": 8, "tp": 16, "note": "周线突破20周均线+周MACD金叉"},
    "S27": {"name": "月线支撑", "hold": 6, "sl": 9, "tp": 18, "note": "回调至月线MA5支撑+月线多头+企稳"},
    "S28": {"name": "暴跌抢反弹", "hold": 2, "sl": 8, "tp": 12, "note": "单日暴跌>7%后次日企稳+放量（逆向）"},
    "S29": {"name": "新股开板", "hold": 3, "sl": 8, "tp": 15, "note": "新股开板后首日收阳+换手>40%+承接有力"},
    "S31": {"name": "奥利弗·凯尔Base&Break", "hold": 8, "sl": 8, "tp": 20, "note": "站上MA50+EMA10>EMA20+15日整理平台振幅<18%+放量突破平台高点（量>20日均量1.5倍）"},
    "S32": {"name": "改良马丁超跌", "hold": 7, "sl": 15, "tp": 5, "note": "从20日高点回撤>12%超跌+当天企稳（收阳或长下影）（逆向，豁免趋势过滤）"},
}

# ============ 指标计算工具 ============
def roll_mean(arr, n):
    """滚动均值，返回与arr等长数组，前n-1个为nan"""
    out = np.full_like(arr, np.nan, dtype=float)
    if len(arr) < n:
        return out
    cs = np.cumsum(arr, dtype=float)
    out[n-1:] = (cs[n-1:] - np.concatenate([[0], cs[:-n]])) / n
    return out

def roll_std(arr, n):
    """滚动标准差"""
    out = np.full_like(arr, np.nan, dtype=float)
    if len(arr) < n:
        return out
    for i in range(n-1, len(arr)):
        out[i] = np.std(arr[i-n+1:i+1], ddof=0)
    return out

def ema(arr, n):
    """指数移动平均"""
    out = np.full_like(arr, np.nan, dtype=float)
    if len(arr) == 0:
        return out
    alpha = 2 / (n + 1)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i-1]
    return out

def rsi(arr, n=14):
    """RSI指标"""
    out = np.full_like(arr, np.nan, dtype=float)
    if len(arr) <= n:
        return out
    deltas = np.diff(arr)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[:n])
    avg_loss = np.mean(losses[:n])
    for i in range(n, len(arr)):
        if i > n:
            avg_gain = (avg_gain * (n-1) + gains[i-1]) / n
            avg_loss = (avg_loss * (n-1) + losses[i-1]) / n
        if avg_loss == 0:
            out[i] = 100
        else:
            rs = avg_gain / avg_loss
            out[i] = 100 - 100 / (1 + rs)
    return out

def kdj(high, low, close, n=9, m1=3, m2=3):
    """KDJ指标，返回K,D,J"""
    K = np.full_like(close, np.nan, dtype=float)
    D = np.full_like(close, np.nan, dtype=float)
    J = np.full_like(close, np.nan, dtype=float)
    if len(close) < n:
        return K, D, J
    rsv = np.full_like(close, np.nan, dtype=float)
    for i in range(n-1, len(close)):
        hh = np.max(high[i-n+1:i+1])
        ll = np.min(low[i-n+1:i+1])
        rsv[i] = (close[i] - ll) / (hh - ll) * 100 if hh != ll else 50
    K[n-1] = 50
    D[n-1] = 50
    for i in range(n, len(close)):
        K[i] = (2/3) * K[i-1] + (1/3) * rsv[i]
        D[i] = (2/3) * D[i-1] + (1/3) * K[i]
        J[i] = 3 * K[i] - 2 * D[i]
    return K, D, J

def macd(close, fast=12, slow=26, signal=9):
    """MACD指标，返回DIF, DEA, MACD柱"""
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    dif = ema_fast - ema_slow
    dea = ema(np.nan_to_num(dif, nan=0), signal)
    macd_bar = 2 * (dif - dea)
    return dif, dea, macd_bar

def boll(close, n=20, k=2):
    """BOLL带，返回上轨,中轨,下轨"""
    mid = roll_mean(close, n)
    std = roll_std(close, n)
    upper = mid + k * std
    lower = mid - k * std
    return upper, mid, lower

# ============ 策略选股函数 ============
def calc_indicators(df):
    """计算单只股票的所有技术指标"""
    c = df["close"].values.astype(float)
    o = df["open"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    v = df["volume"].values.astype(float)
    pct = df["pctChg"].values.astype(float) if "pctChg" in df.columns else np.zeros_like(c)

    ind = {}
    ind["ma5"] = roll_mean(c, 5)
    ind["ma10"] = roll_mean(c, 10)
    ind["ma20"] = roll_mean(c, 20)
    ind["ma50"] = roll_mean(c, 50)
    ind["ma60"] = roll_mean(c, 60)
    ind["ema10"] = ema(c, 10)
    ind["ema20"] = ema(c, 20)
    ind["vol_ma5"] = roll_mean(v, 5)
    ind["vol_ma20"] = roll_mean(v, 20)
    ind["rsi14"] = rsi(c, 14)
    ind["K"], ind["D"], ind["J"] = kdj(h, l, c)
    ind["dif"], ind["dea"], ind["macd_bar"] = macd(c)
    ind["boll_upper"], ind["boll_mid"], ind["boll_lower"] = boll(c)
    ind["high_20"] = np.array([np.max(h[max(0,i-19):i+1]) if i >= 19 else np.nan for i in range(len(c))])
    ind["high_60"] = np.array([np.max(h[max(0,i-59):i+1]) if i >= 59 else np.nan for i in range(len(c))])
    ind["low_20"] = np.array([np.min(l[max(0,i-19):i+1]) if i >= 19 else np.nan for i in range(len(c))])
    ind["high_15"] = np.array([np.max(h[max(0,i-14):i+1]) if i >= 14 else np.nan for i in range(len(c))])
    ind["low_15"] = np.array([np.min(l[max(0,i-14):i+1]) if i >= 14 else np.nan for i in range(len(c))])
    ind["high_20_prev"] = np.array([np.max(h[max(0,i-20):i]) if i >= 1 else np.nan for i in range(len(c))])
    return ind, c, o, h, l, v, pct

def select_stocks(strategy_key, df, ind, c, o, h, l, v, pct, i):
    """判断第i日是否满足策略买入条件，返回True/False和评分"""
    if i < 60:
        return False, 0

    s = STRATEGIES[strategy_key]
    score = 0

    try:
        if strategy_key == "S01":
            cond = (ind["ma5"][i] > ind["ma10"][i] > ind["ma20"][i] and
                    c[i] > ind["high_20"][i-1] and v[i] > ind["vol_ma20"][i] * 1.3)
            score = pct[i] + (v[i]/ind["vol_ma20"][i] if ind["vol_ma20"][i] > 0 else 0)
        elif strategy_key == "S02":
            cond = (ind["dif"][i] > ind["dea"][i] and ind["dif"][i-1] <= ind["dea"][i-1] and
                    ind["dif"][i] > 0 and c[i] > ind["ma20"][i])
            score = ind["macd_bar"][i] + pct[i]
        elif strategy_key == "S03":
            near_ma10 = abs(c[i] - ind["ma10"][i]) / ind["ma10"][i] < 0.02
            near_ma20 = abs(c[i] - ind["ma20"][i]) / ind["ma20"][i] < 0.02
            cond = ((near_ma10 or near_ma20) and c[i] > o[i] and v[i] < ind["vol_ma5"][i] * 0.9 and
                    ind["ma20"][i] > ind["ma20"][i-3])
            score = 10 - abs(c[i] - ind["ma10"][i]) / ind["ma10"][i] * 100
        elif strategy_key == "S04":
            has_limit = any(pct[j] >= 9.8 for j in range(max(0,i-4), i+1))
            limit_idx = None
            for j in range(max(0,i-4), i+1):
                if pct[j] >= 9.8:
                    limit_idx = j
            if has_limit and limit_idx is not None and i > limit_idx:
                limit_open = o[limit_idx]
                cond = (l[i] > limit_open * 0.97 and c[i] > o[i] and v[i] < ind["vol_ma5"][i])
                score = 10 - (i - limit_idx)
            else:
                cond = False
        elif strategy_key == "S05":
            is_new_low = l[i] <= ind["low_20"][i]
            cond = (is_new_low and pct[i] > 5 and v[i] > ind["vol_ma20"][i] * 1.5)
            score = pct[i] + (v[i]/ind["vol_ma20"][i] if ind["vol_ma20"][i] > 0 else 0)
        elif strategy_key == "S06":
            cond = (c[i] > ind["ma20"][i] and ind["ma20"][i] > ind["ma20"][i-5] and
                    l[i] > ind["ma20"][i] * 0.98 and c[i] > o[i])
            score = (c[i] - ind["ma20"][i]) / ind["ma20"][i] * 100 + pct[i]
        elif strategy_key == "S07":
            cond = (ind["rsi14"][i] < 30 and c[i] > o[i] and v[i] > ind["vol_ma5"][i] * 1.2)
            score = 30 - ind["rsi14"][i] + pct[i]
        elif strategy_key == "S08":
            platform_high = ind["high_20"][i-1]
            platform_low = ind["low_20"][i-1]
            amplitude = (platform_high - platform_low) / platform_low if platform_low > 0 else 1
            cond = (amplitude < 0.15 and c[i] > platform_high and v[i] > ind["vol_ma20"][i] * 1.5)
            score = (c[i] - platform_high) / platform_high * 100 + (v[i]/ind["vol_ma20"][i] if ind["vol_ma20"][i] > 0 else 0)
        elif strategy_key == "S09":
            cond = (ind["ma5"][i] > ind["ma10"][i] and ind["ma5"][i-1] <= ind["ma10"][i-1] and
                    c[i] > ind["ma20"][i] and v[i] > ind["vol_ma5"][i] * 1.2)
            score = pct[i] + (v[i]/ind["vol_ma5"][i] if ind["vol_ma5"][i] > 0 else 0)
        elif strategy_key == "S10":
            vol_inc = v[i] > v[i-1] > v[i-2]
            price_inc = c[i] > c[i-1] > c[i-2]
            cond = (vol_inc and price_inc and ind["ma5"][i] > ind["ma10"][i] > ind["ma20"][i])
            score = pct[i] + pct[i-1] + pct[i-2]
        elif strategy_key == "S11":
            cond = (c[i] > ind["boll_upper"][i] and v[i] > ind["vol_ma20"][i] * 1.3 and
                    ind["boll_upper"][i] > ind["boll_upper"][i-3])
            score = (c[i] - ind["boll_upper"][i]) / ind["boll_upper"][i] * 100 + pct[i]
        elif strategy_key == "S12":
            cond = (ind["K"][i] < 20 and ind["K"][i] > ind["D"][i] and ind["K"][i-1] <= ind["D"][i-1] and c[i] > o[i])
            score = 20 - ind["K"][i] + pct[i]
        elif strategy_key == "S13":
            gap_down = o[i] < l[i-1] * 0.98
            cond = (gap_down and c[i] > l[i-1] and v[i] > ind["vol_ma5"][i] * 1.3)
            score = (c[i] - l[i-1]) / l[i-1] * 100 + pct[i]
        elif strategy_key == "S14":
            cond = (pct[i] > 2 and v[i] > ind["vol_ma5"][i] * 1.2 and c[i] > ind["ma5"][i] and c[i] > o[i])
            score = pct[i] + (v[i]/ind["vol_ma5"][i] if ind["vol_ma5"][i] > 0 else 0)
        elif strategy_key == "S15":
            cond = (o[i] < c[i-1] * 0.98 and pct[i] > 3 and v[i] > ind["vol_ma20"][i] * 1.3)
            score = pct[i] + (c[i-1] - o[i]) / c[i-1] * 100
        elif strategy_key == "S16":
            small_yang = all(0 < pct[j] < 3 and c[j] > o[j] for j in range(i-3, i))
            cond = (small_yang and v[i] > ind["vol_ma5"][i] * 1.5 and pct[i] > 1)
            score = pct[i] + sum(pct[i-3:i])
        elif strategy_key == "S17":
            cond = (c[i] > 20 and ind["ma5"][i] > ind["ma10"][i] > ind["ma20"][i] and pct[i] > 1 and v[i] > ind["vol_ma5"][i])
            score = pct[i] + (c[i] / 100)
        elif strategy_key == "S18":
            has_consec = any(all(pct[j] >= 9.8 for j in range(k, k+2)) for k in range(max(0,i-5), i-1))
            cond = (has_consec and pct[i] < 0 and l[i] > ind["ma5"][i] and v[i] < ind["vol_ma5"][i] * 0.8)
            score = 10 - abs(pct[i])
        elif strategy_key == "S19":
            cond = (pct[i] > 3 and ind["ma5"][i] > ind["ma10"][i] and v[i] > ind["vol_ma20"][i] * 1.5 and c[i] > ind["ma20"][i])
            score = pct[i] + (v[i]/ind["vol_ma20"][i] if ind["vol_ma20"][i] > 0 else 0)
        elif strategy_key == "S20":
            gain_20 = (c[i] - c[i-20]) / c[i-20] if i >= 20 else 0
            cond = (gain_20 > 0.3 and abs(c[i] - ind["ma10"][i]) / ind["ma10"][i] < 0.03 and c[i] > o[i])
            score = gain_20 * 10 - abs(c[i] - ind["ma10"][i]) / ind["ma10"][i] * 100
        elif strategy_key == "S21":
            cond = (c[i] > ind["high_60"][i-1] and v[i] > ind["vol_ma20"][i] * 1.5 and
                    ind["ma5"][i] > ind["ma10"][i] > ind["ma20"][i])
            score = (c[i] - ind["high_60"][i-1]) / ind["high_60"][i-1] * 100 + (v[i]/ind["vol_ma20"][i] if ind["vol_ma20"][i] > 0 else 0)
        elif strategy_key == "S22":
            is_doji = abs(c[i-1] - o[i-1]) / (h[i-1] - l[i-1]) < 0.1 if (h[i-1] - l[i-1]) > 0 else False
            low_pos = c[i-1] < ind["ma20"][i-1] * 0.95
            cond = (is_doji and low_pos and v[i-1] < ind["vol_ma5"][i-1] * 0.8 and
                    c[i] > o[i] and v[i] > ind["vol_ma5"][i] * 1.3)
            score = pct[i] + (v[i]/ind["vol_ma5"][i] if ind["vol_ma5"][i] > 0 else 0)
        elif strategy_key == "S26":
            cond = (c[i] > ind["ma20"][i] and ind["ma20"][i] > ind["ma20"][i-10] and
                    ind["dif"][i] > ind["dea"][i] and ind["dif"][i-1] <= ind["dea"][i-1])
            score = (c[i] - ind["ma20"][i]) / ind["ma20"][i] * 100 + ind["macd_bar"][i]
        elif strategy_key == "S27":
            cond = (abs(c[i] - ind["ma20"][i]) / ind["ma20"][i] < 0.02 and
                    ind["ma50"][i] > ind["ma50"][i-10] and c[i] > o[i] and v[i] < ind["vol_ma5"][i])
            score = 10 - abs(c[i] - ind["ma20"][i]) / ind["ma20"][i] * 100
        elif strategy_key == "S28":
            cond = (pct[i-1] < -7 and c[i] > o[i] and v[i] > ind["vol_ma5"][i] * 1.3 and l[i] > l[i-1])
            score = 10 - abs(pct[i-1]) + pct[i]
        elif strategy_key == "S29":
            cond = (i < 120 and pct[i] > 5 and v[i] > ind["vol_ma5"][i] * 2 and c[i] > o[i])
            score = pct[i] + (v[i]/ind["vol_ma5"][i] if ind["vol_ma5"][i] > 0 else 0)
        elif strategy_key == "S31":
            cond = (c[i] > ind["ma50"][i] and ind["ema10"][i] > ind["ema20"][i] and
                    (ind["high_15"][i-1] - ind["low_15"][i-1]) / ind["low_15"][i-1] < 0.18 and
                    c[i] > ind["high_15"][i-1] and v[i] > ind["vol_ma20"][i] * 1.5)
            score = (c[i] - ind["high_15"][i-1]) / ind["high_15"][i-1] * 100 + (v[i]/ind["vol_ma20"][i] if ind["vol_ma20"][i] > 0 else 0)
        elif strategy_key == "S32":
            drawdown = (ind["high_20_prev"][i] - l[i]) / ind["high_20_prev"][i] if ind["high_20_prev"][i] > 0 else 0
            long_lower = (c[i] - l[i]) / (h[i] - l[i]) > 0.6 if (h[i] - l[i]) > 0 else False
            cond = (drawdown > 0.12 and (c[i] > o[i] or long_lower))
            score = drawdown * 100 - 12
        else:
            cond = False
    except Exception:
        cond = False
        score = 0

    return cond, score

# ============ 回测引擎 ============
def load_data():
    """加载行情数据"""
    pkl_path = os.path.join(DATA_DIR, "daily.pkl")
    if not os.path.exists(pkl_path):
        print("错误: 数据文件不存在 %s，请先运行 update_data.py" % pkl_path)
        sys.exit(1)
    print("加载行情数据...", flush=True)
    with open(pkl_path, "rb") as f:
        data = pickle.load(f)
    print("加载完成: %d 只股票" % len(data), flush=True)
    return data

def load_index():
    """加载上证综指，返回日期->MA20的映射"""
    idx_path = os.path.join(DATA_DIR, "sh000001.csv")
    if not os.path.exists(idx_path):
        return {}
    df = pd.read_csv(idx_path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["ma20"] = df["close"].rolling(20).mean()
    df["above_ma20"] = df["close"] > df["ma20"]
    return dict(zip(df["date"].dt.strftime("%Y-%m-%d"), df["above_ma20"]))

def run_backtest(strategy_key, data, index_trend):
    """运行单策略回测"""
    s = STRATEGIES[strategy_key]
    hold_days = s["hold"]
    sl_pct = s["sl"] / 100
    tp_pct = s["tp"] / 100
    trend_filter_on = strategy_key not in TREND_FILTER_OFF

    all_dates = set()
    for code, df in data.items():
        all_dates.update(df["date"].dt.strftime("%Y-%m-%d").tolist())
    all_dates = sorted(all_dates)

    print("  [%s] 预计算指标..." % strategy_key, flush=True)
    stock_indicators = {}
    for code, df in data.items():
        if len(df) < 60:
            continue
        try:
            ind, c, o, h, l, v, pct = calc_indicators(df)
            stock_indicators[code] = (df, ind, c, o, h, l, v, pct)
        except Exception:
            continue

    capital = INIT_CAPITAL
    positions = {}
    equity_curve = []
    trades = []

    print("  [%s] 回测中 (%d 交易日)..." % (strategy_key, len(all_dates)), flush=True)

    for di, date_str in enumerate(all_dates):
        date = pd.Timestamp(date_str)

        if trend_filter_on and index_trend:
            if date_str in index_trend and not index_trend[date_str]:
                pass
            elif date_str not in index_trend:
                pass

        to_sell = []
        for code, pos in list(positions.items()):
            if code not in stock_indicators:
                continue
            df, ind, c, o, h, l, v, pct = stock_indicators[code]
            day_idx = df.index[df["date"] == date]
            if len(day_idx) == 0:
                continue
            i = day_idx[0]
            close_price = c[i]
            high_price = h[i]
            low_price = l[i]

            buy_price = pos["buy_price"]
            if low_price <= buy_price * (1 - sl_pct):
                sell_price = buy_price * (1 - sl_pct)
                to_sell.append((code, sell_price, "止损"))
                continue
            if high_price >= buy_price * (1 + tp_pct):
                sell_price = buy_price * (1 + tp_pct)
                to_sell.append((code, sell_price, "止盈"))
                continue
            pos["hold_left"] -= 1
            if pos["hold_left"] <= 0:
                to_sell.append((code, close_price, "到期"))

        for code, sell_price, reason in to_sell:
            if code not in positions:
                continue
            pos = positions.pop(code)
            shares = pos["shares"]
            sell_amount = shares * sell_price * (1 - COMMISSION - STAMP_TAX - SLIPPAGE)
            capital += sell_amount
            pnl = (sell_price - pos["buy_price"]) / pos["buy_price"] * 100
            trades.append({
                "code": code, "buy_date": pos["buy_date"], "buy_price": pos["buy_price"],
                "sell_date": date_str, "sell_price": sell_price, "pnl": pnl, "reason": reason
            })

        if len(positions) < MAX_POS:
            candidates = []
            for code, (df, ind, c, o, h, l, v, pct) in stock_indicators.items():
                if code in positions:
                    continue
                day_idx = df.index[df["date"] == date]
                if len(day_idx) == 0:
                    continue
                i = day_idx[0]
                if trend_filter_on and index_trend and date_str in index_trend and not index_trend[date_str]:
                    continue
                cond, score = select_stocks(strategy_key, df, ind, c, o, h, l, v, pct, i)
                if cond and score > 0:
                    candidates.append((code, score, c[i]))

            candidates.sort(key=lambda x: x[1], reverse=True)
            buy_list = candidates[:TOP_N]

            if buy_list and capital > 10000:
                per_position = capital / (MAX_POS - len(positions)) * 0.95
                for code, score, close_price in buy_list:
                    if len(positions) >= MAX_POS:
                        break
                    if capital < per_position:
                        per_position = capital * 0.95
                    shares = int(per_position / close_price / 100) * 100
                    if shares < 100:
                        continue
                    buy_amount = shares * close_price * (1 + COMMISSION + SLIPPAGE)
                    if buy_amount > capital:
                        continue
                    capital -= buy_amount
                    positions[code] = {
                        "buy_price": close_price, "buy_date": date_str,
                        "hold_left": hold_days, "shares": shares
                    }

        total_equity = capital
        for code, pos in positions.items():
            if code in stock_indicators:
                df, ind, c, o, h, l, v, pct = stock_indicators[code]
                day_idx = df.index[df["date"] == date]
                if len(day_idx) > 0:
                    total_equity += pos["shares"] * c[day_idx[0]]
        equity_curve.append({"date": date_str, "equity": total_equity})

    for code, pos in list(positions.items()):
        if code in stock_indicators:
            df, ind, c, o, h, l, v, pct = stock_indicators[code]
            last_close = c[-1]
            sell_amount = pos["shares"] * last_close * (1 - COMMISSION - STAMP_TAX - SLIPPAGE)
            capital += sell_amount
            pnl = (last_close - pos["buy_price"]) / pos["buy_price"] * 100
            trades.append({
                "code": code, "buy_date": pos["buy_date"], "buy_price": pos["buy_price"],
                "sell_date": all_dates[-1], "sell_price": last_close, "pnl": pnl, "reason": "期末清仓"
            })

    if not equity_curve:
        return None
    eq_df = pd.DataFrame(equity_curve)
    eq_df["date"] = pd.to_datetime(eq_df["date"])
    total_return = (eq_df["equity"].iloc[-1] - INIT_CAPITAL) / INIT_CAPITAL * 100

    eq_df["peak"] = eq_df["equity"].cummax()
    eq_df["drawdown"] = (eq_df["equity"] - eq_df["peak"]) / eq_df["peak"] * 100
    max_drawdown = eq_df["drawdown"].min()

    win_trades = [t for t in trades if t["pnl"] > 0]
    win_rate = len(win_trades) / len(trades) * 100 if trades else 0

    avg_hold = np.mean([(pd.Timestamp(t["sell_date"]) - pd.Timestamp(t["buy_date"])).days for t in trades]) if trades else 0

    periods = {}
    for q, (start, end) in {"Q1": ("2026-01-01", "2026-03-31"), "Q2": ("2026-04-01", "2026-06-30"), "Q3": ("2026-07-01", "2026-09-30")}.items():
        q_data = eq_df[(eq_df["date"] >= start) & (eq_df["date"] <= end)]
        if len(q_data) > 1:
            q_ret = (q_data["equity"].iloc[-1] - q_data["equity"].iloc[0]) / q_data["equity"].iloc[0] * 100
            periods[q] = round(q_ret, 2)
        else:
            periods[q] = 0

    result = {
        "strategy": strategy_key,
        "name": s["name"],
        "total_return": round(total_return, 2),
        "max_drawdown": round(max_drawdown, 2),
        "win_rate": round(win_rate, 2),
        "trades": len(trades),
        "avg_hold": round(avg_hold, 1),
        "final_equity": round(eq_df["equity"].iloc[-1], 2),
        "periods": periods,
        "hold": hold_days, "sl": s["sl"], "tp": s["tp"],
        "note": s["note"],
    }

    eq_df.to_csv(os.path.join(RESULT_DIR, "%s_equity.csv" % strategy_key), index=False)

    return result

def load_result_from_equity(key):
    """从已保存的equity.csv中读取回测结果（断点续传用）"""
    path = os.path.join(RESULT_DIR, "%s_equity.csv" % key)
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path)
        if len(df) < 2:
            return None
        total_return = (df["equity"].iloc[-1] - INIT_CAPITAL) / INIT_CAPITAL * 100
        df["peak"] = df["equity"].cummax()
        df["drawdown"] = (df["equity"] - df["peak"]) / df["peak"] * 100
        max_drawdown = df["drawdown"].min()
        s = STRATEGIES[key]
        periods = {}
        df["date"] = pd.to_datetime(df["date"])
        for q, (start, end) in {"Q1": ("2026-01-01", "2026-03-31"), "Q2": ("2026-04-01", "2026-06-30"), "Q3": ("2026-07-01", "2026-09-30")}.items():
            qd = df[(df["date"] >= start) & (df["date"] <= end)]
            if len(qd) > 1:
                periods[q] = round((qd["equity"].iloc[-1] - qd["equity"].iloc[0]) / qd["equity"].iloc[0] * 100, 2)
            else:
                periods[q] = 0
        return {
            "strategy": key, "name": s["name"],
            "total_return": round(total_return, 2),
            "max_drawdown": round(max_drawdown, 2),
            "win_rate": 0, "trades": 0, "avg_hold": 0,
            "final_equity": round(df["equity"].iloc[-1], 2),
            "periods": periods, "hold": s["hold"], "sl": s["sl"], "tp": s["tp"],
            "note": s["note"],
        }
    except Exception:
        return None

def main():
    print("=" * 60, flush=True)
    print("  A股短线策略回测引擎 v2", flush=True)
    print("  策略数: %d" % len(STRATEGIES), flush=True)
    print("  初始资金: %.0f万" % (INIT_CAPITAL/10000), flush=True)
    print("=" * 60, flush=True)

    data = load_data()
    index_trend = load_index()
    print("大盘趋势数据: %d 个交易日" % len(index_trend), flush=True)

    summary = []
    t0 = time.time()
    summary_path = os.path.join(RESULT_DIR, "summary_v2.json")

    for i, key in enumerate(sorted(STRATEGIES.keys())):
        existing = load_result_from_equity(key)
        if existing and existing["trades"] == 0:
            existing = None
        if existing:
            summary.append(existing)
            print("\n[%d/%d] 跳过已完成 %s - %s | 收益: %.2f%%" % (
                i+1, len(STRATEGIES), key, STRATEGIES[key]["name"], existing["total_return"]), flush=True)
            continue

        print("\n[%d/%d] 回测策略 %s - %s" % (i+1, len(STRATEGIES), key, STRATEGIES[key]["name"]), flush=True)
        try:
            result = run_backtest(key, data, index_trend)
            if result:
                summary.append(result)
                print("  收益: %.2f%% | 回撤: %.2f%% | 胜率: %.1f%% | 交易: %d" % (
                    result["total_return"], result["max_drawdown"], result["win_rate"], result["trades"]), flush=True)
                summary.sort(key=lambda x: x["total_return"], reverse=True)
                with open(summary_path, "w", encoding="utf-8") as f:
                    json.dump(summary, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("  错误: %s" % e, flush=True)
            import traceback
            traceback.print_exc()

    summary.sort(key=lambda x: x["total_return"], reverse=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - t0
    print("\n" + "=" * 60, flush=True)
    print("  回测完成! 耗时: %.1f分钟" % (elapsed/60), flush=True)
    print("  结果: %s" % RESULT_DIR, flush=True)
    print("=" * 60, flush=True)

    print("\n策略收益排名:", flush=True)
    for r in summary:
        print("  %s %-25s 收益:%7.2f%%  回撤:%7.2f%%  胜率:%5.1f%%  交易:%4d" % (
            r["strategy"], r["name"], r["total_return"], r["max_drawdown"], r["win_rate"], r["trades"]), flush=True)

if __name__ == "__main__":
    main()
