# -*- coding: utf-8 -*-
"""
行情数据下载脚本（akshare新浪接口）
使用 akshare stock_zh_a_daily 下载 A 股全市场日线数据（前复权）
输出：backtest_data/daily.pkl（键=baostock格式 sh.600000/sz.000001）
      backtest_data/universe.csv（股票池）
      backtest_data/sh000001.csv（上证综指，v2趋势过滤用）
"""
import os, sys, time, pickle, multiprocessing as mp
import pandas as pd
import numpy as np

# 禁用代理（云端环境代理无法访问金融数据网站）
os.environ['no_proxy'] = '*'
os.environ['NO_PROXY'] = '*'
os.environ['http_proxy'] = ''
os.environ['https_proxy'] = ''
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''

import akshare as ak

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "backtest_data")
os.makedirs(DATA_DIR, exist_ok=True)

START = "20250901"
END = "20260912"
NUM_WORKERS = 4

def log(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)

def code_to_sina(code):
    """baostock格式 sh.600000 -> 新浪格式 sh600000"""
    return code.replace('.', '')

def download_index():
    """下载上证综指"""
    log("下载上证综指 %s ~ %s" % (START, END))
    try:
        df = ak.stock_zh_index_daily(symbol="sh000001")
        df["date"] = pd.to_datetime(df["date"])
        df = df[(df["date"] >= START) & (df["date"] <= END)]
        df = df.sort_values("date").reset_index(drop=True)
        out = os.path.join(DATA_DIR, "sh000001.csv")
        df.to_csv(out, index=False, encoding="utf-8-sig")
        log("上证综指保存完成: %d 行" % len(df))
    except Exception as e:
        log("上证综指下载失败: %s" % e)

def get_universe():
    """获取A股股票池（新浪接口）"""
    log("获取A股股票池...")
    try:
        df = ak.stock_info_a_code_name()
        # 只保留沪深A股（6开头沪市，0/3开头深市），跳过北交所8/4开头
        df = df[df["code"].str.match(r"^(6|0|3)")]
        # 转换为baostock格式
        df["code"] = df["code"].apply(lambda x: ("sh." if x.startswith("6") else "sz.") + x)
        df["code_name"] = df["name"]
        uni = df[["code", "code_name"]].reset_index(drop=True)
        out = os.path.join(DATA_DIR, "universe.csv")
        uni.to_csv(out, index=False, encoding="utf-8-sig")
        log("股票池: %d 只" % len(uni))
        return uni
    except Exception as e:
        log("获取股票池失败: %s" % e)
        return None

def download_stock_worker(args):
    """单进程下载工作函数"""
    codes, start, end, result_queue = args
    os.environ['no_proxy'] = '*'
    os.environ['NO_PROXY'] = '*'
    os.environ['http_proxy'] = ''
    os.environ['https_proxy'] = ''
    import akshare as ak
    import pandas as pd
    import numpy as np

    results = {}
    for code in codes:
        try:
            sina_code = code.replace('.', '')
            df = ak.stock_zh_a_daily(symbol=sina_code, start_date=start, end_date=end, adjust="qfq")
            if df is None or len(df) == 0:
                continue
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
            df["pctChg"] = df["close"].pct_change() * 100
            df["pctChg"] = df["pctChg"].fillna(0)
            df = df.rename(columns={"turnover": "turn"})
            cols = ["date", "open", "high", "low", "close", "volume", "amount", "turn", "pctChg"]
            cols = [c for c in cols if c in df.columns]
            df = df[cols]
            results[code] = df
        except Exception:
            continue
    result_queue.put(results)

def main():
    download_index()
    uni = get_universe()
    if uni is None or len(uni) == 0:
        log("错误: 无法获取股票池")
        sys.exit(1)

    codes = uni["code"].tolist()
    total = len(codes)

    pkl_path = os.path.join(DATA_DIR, "daily.pkl")
    if os.path.exists(pkl_path):
        try:
            with open(pkl_path, "rb") as f:
                data = pickle.load(f)
            log("已有数据: %d 只，继续下载" % len(data))
            codes = [c for c in codes if c not in data or len(data[c]) == 0]
            log("剩余待下载: %d 只" % len(codes))
        except Exception:
            data = {}
    else:
        data = {}

    if not codes:
        log("所有股票已下载完成")
        return

    chunk_size = (len(codes) + NUM_WORKERS - 1) // NUM_WORKERS
    chunks = [codes[i:i+chunk_size] for i in range(0, len(codes), chunk_size)]

    log("开始下载: %d 只股票，%d 进程" % (len(codes), len(chunks)))
    t0 = time.time()

    result_queue = mp.Queue()
    processes = []
    for chunk in chunks:
        p = mp.Process(target=download_stock_worker, args=((chunk, START, END, result_queue),))
        p.start()
        processes.append(p)

    done_count = len(data)
    for _ in processes:
        try:
            results = result_queue.get(timeout=3600)
            data.update(results)
            done_count += len(results)
            elapsed = time.time() - t0
            rate = (done_count - len(data) + len(results)) / elapsed if elapsed > 0 else 0
            eta = (total - done_count) / rate if rate > 0 else 0
            log("进度: %d/%d (%.1f%%) 预计剩余:%.0f分钟" % (
                done_count, total, done_count/total*100, eta/60))
        except Exception as e:
            log("收集结果超时或失败: %s" % e)

    for p in processes:
        p.join(timeout=60)

    with open(pkl_path, "wb") as f:
        pickle.dump(data, f)

    elapsed = time.time() - t0
    log("=" * 50)
    log("下载完成! 成功:%d 总耗时:%.1f分钟" % (len(data), elapsed/60))
    log("数据文件: %s (%.1f MB)" % (pkl_path, os.path.getsize(pkl_path)/1024/1024))

if __name__ == "__main__":
    mp.set_start_method('spawn', force=True)
    main()
