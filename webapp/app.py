# -*- coding: utf-8 -*-
"""
A股30策略回测 Web 控制台
Flask后端，提供四页签：收益看板/后端控制台/文件与产物/优选个股
"""
import os, sys, json, subprocess, time, uuid
from flask import Flask, render_template, jsonify, request, send_file, Response

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, "backtest_data")
RESULT_DIR = os.path.join(DATA_DIR, "results_v2")

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False

_tasks = {}

_SCRIPTS = {
    "update_data": {"name": "更新行情数据", "cmd": ["python", "-X", "utf8", "update_data.py"], "eta": 2400},
    "backtest_v2": {"name": "跑回测v2", "cmd": ["python", "-X", "utf8", "backtest_engine_v2.py"], "eta": 900},
    "resonance": {"name": "多策略共振选股", "cmd": ["python", "-X", "utf8", "resonance_screen.py"], "eta": 300},
    "screen_filter": {"name": "二次筛选优选个股", "cmd": ["python", "-X", "utf8", "screen_filter.py"], "eta": 60},
    "gen_stock_pick": {"name": "刷新优选个股页面", "cmd": ["python", "-X", "utf8", "gen_stock_pick_html.py"], "eta": 30},
    "daily_signal": {"name": "生成每日信号", "cmd": ["python", "-X", "utf8", "daily_signal.py", "--no-update"], "eta": 120},
}

def run_script(name):
    if name not in _SCRIPTS:
        return None
    task_id = str(uuid.uuid4())[:8]
    script = _SCRIPTS[name]
    log_file = os.path.join(DATA_DIR, "logs", "%s_%s.log" % (name, task_id))
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    with open(log_file, "w", encoding="utf-8") as f:
        proc = subprocess.Popen(
            script["cmd"], cwd=BASE, stdout=f, stderr=subprocess.STDOUT,
            creationflags=0 if sys.platform != "win32" else 0
        )

    _tasks[task_id] = {
        "id": task_id, "script": name, "name": script["name"],
        "status": "running", "pid": proc.pid, "start": time.strftime("%Y-%m-%d %H:%M:%S"),
        "log_file": log_file, "eta": script.get("eta", 0),
    }
    return task_id

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/stock_pick")
def stock_pick():
    path = os.path.join(BASE, "stock_pick.html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return Response(f.read(), mimetype="text/html")
    return "优选个股页面尚未生成，请先运行二次筛选和页面生成脚本", 404

@app.route("/api/run/<name>", methods=["POST"])
def api_run(name):
    task_id = run_script(name)
    if task_id:
        return jsonify({"ok": True, "task_id": task_id})
    return jsonify({"ok": False, "msg": "未知脚本: %s" % name})

@app.route("/api/tasks")
def api_tasks():
    out = []
    for tid, t in _tasks.items():
        try:
            import psutil
            if not psutil.pid_exists(t["pid"]):
                t["status"] = "done"
        except Exception:
            pass
        item = {k: v for k, v in t.items() if k != "log_file"}
        out.append(item)
    return jsonify({"ok": True, "tasks": list(reversed(out))})

@app.route("/api/task/<tid>")
def api_task(tid):
    if tid not in _tasks:
        return jsonify({"ok": False, "msg": "任务不存在"})
    t = _tasks[tid]
    try:
        import psutil
        if not psutil.pid_exists(t["pid"]):
            t["status"] = "done"
    except Exception:
        pass
    log = ""
    if os.path.exists(t["log_file"]):
        with open(t["log_file"], "r", encoding="utf-8", errors="ignore") as f:
            log = f.read()[-5000:]
    return jsonify({"ok": True, "task": {k: v for k, v in t.items() if k != "log_file"}, "log": log})

@app.route("/api/summary")
def api_summary():
    path = os.path.join(RESULT_DIR, "summary_v2.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify({"ok": True, "data": data})
    return jsonify({"ok": False, "msg": "回测结果不存在，请先运行回测"})

@app.route("/api/resonance")
def api_resonance():
    path = os.path.join(DATA_DIR, "resonance_result.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify({"ok": True, "data": data})
    return jsonify({"ok": False, "msg": "共振选股结果不存在"})

@app.route("/api/target_stocks")
def api_target_stocks():
    path = os.path.join(DATA_DIR, "target_stocks.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify({"ok": True, "data": data})
    return jsonify({"ok": False, "msg": "优选个股数据不存在"})

@app.route("/api/files")
def api_files():
    files = []
    if os.path.exists(RESULT_DIR):
        for f in sorted(os.listdir(RESULT_DIR)):
            fp = os.path.join(RESULT_DIR, f)
            if os.path.isfile(fp):
                files.append({"name": f, "path": "results_v2/%s" % f, "size": os.path.getsize(fp), "dir": "results_v2"})
    for f in sorted(os.listdir(DATA_DIR)):
        fp = os.path.join(DATA_DIR, f)
        if os.path.isfile(fp) and f.endswith((".csv", ".json", ".md", ".pkl")):
            files.append({"name": f, "path": f, "size": os.path.getsize(fp), "dir": "backtest_data"})
    for f in sorted(os.listdir(BASE)):
        fp = os.path.join(BASE, f)
        if os.path.isfile(fp) and f.endswith(".html"):
            files.append({"name": f, "path": f, "size": os.path.getsize(fp), "dir": "root"})
    return jsonify({"ok": True, "files": files})

if __name__ == "__main__":
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
    except Exception:
        lan_ip = "127.0.0.1"
    print("=" * 60)
    print("  A股30策略回测 Web 控制台")
    print("  项目目录: %s" % BASE)
    print("  本机访问: http://127.0.0.1:5000")
    print("  手机访问: http://%s:5000  (手机与电脑需同一WiFi)" % lan_ip)
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
