#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""health/status.json を書き出す（ローカルPCの監視タスクから1日3回実行）。

目的:
  Actions が詰まると Actions 側の警報も一緒に詰まる（2026-08-07 に実測: cron 07:37 の
  警報が 10:37 に起票された）。監視は監視対象と別の場所で動かす必要があるため、
  この点検は PC ローカルのタスクスケジューラから実行する。

出力:
  health/status.json  ... docs/ の外に置く。Pages のデプロイを起動させないため。

方針:
  - 判定はせず事実だけを書く。しきい値の解釈は読む側に任せる。
  - GitHub API が取れなくても、git の情報だけで成立させる（api は任意）。
  - 例外で落とさない。取れなかった項目は null と理由を書く。
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
REPO = "abeken1026395/pallas-mercato-7k9"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "health", "status.json")

# 監視するデータの最終更新（表示名 -> リポジトリ内パス）
WATCH = {
    "liveWeather": "docs/data/liveWeather.json",
    "weather": "docs/data/weather.json",
    "tideToday": "docs/data/tideToday.json",
    "arare": "docs/data/arare.json",
    "racers": "docs/racers/racers_today.csv",
    "highlights": "docs/highlights/highlights.json",
    "motorParts": "docs/data/motorParts.json",
    "results": "results",
    "preview": "preview",
}

# ローカルタスク（タスクスケジューラ）の結果（表示名 -> タスク名）。WATCH と並べて監視する。
# WATCH はリポジトリ内パスの最終更新しか見ないため、タスクが「起動しなかった日」は
# 出力の更新停止としてしか現れない（2026-09-10: Windows Update の再起動でログオフ中になり、
# Interactive のタスクが起動しなかった）。タスクの記録そのものを見て、状態を分ける:
#   成功   : 直近の予定時刻以降に起動し、終了コード 0
#   失敗   : 直近の予定時刻以降に起動し、終了コード 0 以外
#   未実行 : 直近の予定時刻以降に起動記録が無い（記録が無い＝未検証。正常ではない）
#   実行中 : 終了コード 267009（SCHED_S_TASK_RUNNING）
#   未検証 : 照会できない・予定時刻を計算できない
LOCAL_TASKS = {
    "writeKansenkiLocal": "boatrace-writeKansenkiLocal",
    "dailyMotorUsage": "boatrace-dailyMotorUsage",
    "dailyPartsBackfill": "boatrace-dailyPartsBackfill",
}
# 予定時刻から START_GRACE_MIN 分を過ぎたものだけを「直近の予定」として数える（猶予内はまだ判定しない）。
# 根拠（2026-08-12〜09-11 の scripts/logs 実測）: 予定からの起動遅れは通常 0.1 分以内
# （writeKansenki 31回・dailyMotorUsage 29回・dailyPartsBackfill 60回。例外は 08-12 の手動再実行と、
# 起動しなかった 09-10）。所要は最長 26 分（writeKansenki）。60 分あれば起動と完了を待てる。
START_GRACE_MIN = 60
TASK_RUNNING = 267009


def now():
    return datetime.now(JST)


def git(*args):
    r = subprocess.run(["git"] + list(args), cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout.strip() if r.returncode == 0 else ""


def last_commit(path):
    """path を最後に変更したコミットの時刻(JST)とSHA。無ければ None。"""
    out = git("log", "-1", "--format=%cI|%h|%s", "origin/main", "--", path)
    if not out or "|" not in out:
        return None
    iso, sha, subj = out.split("|", 2)
    try:
        t = datetime.fromisoformat(iso).astimezone(JST)
    except ValueError:
        return None
    d = now() - t
    return {
        "時刻": t.strftime("%Y-%m-%d %H:%M"),
        "経過分": int(d.total_seconds() // 60),
        "sha": sha,
        "件名": subj[:60],
    }


def kansenki():
    """当日掲載分の観戦記が、素材の場数ぶんそろっているか。"""
    day = now().strftime("%Y%m%d")
    src = os.path.join(ROOT, "docs", "data", "kansenki", "source", day + ".json")
    art = os.path.join(ROOT, "docs", "data", "kansenki", "articles")
    o = {"掲載日": day, "素材": False, "期待場数": None, "記事数": 0}
    if os.path.exists(src):
        o["素材"] = True
        try:
            with open(src, encoding="utf-8") as f:
                o["期待場数"] = len(json.load(f).get("venues", []))
        except (ValueError, OSError):
            o["期待場数"] = None
    if os.path.isdir(art):
        o["記事数"] = len([n for n in os.listdir(art) if n.startswith(day + "-")])
    return o


def local_logs():
    """scripts/logs/ の各ログの最終行と更新時刻。ローカル実行時のみ中身が入る。"""
    d = os.path.join(ROOT, "scripts", "logs")
    if not os.path.isdir(d):
        return {}
    o = {}
    for name in sorted(os.listdir(d)):
        if not name.endswith(".log"):
            continue
        p = os.path.join(d, name)
        try:
            mt = datetime.fromtimestamp(os.path.getmtime(p), JST)
            with open(p, encoding="utf-8", errors="replace") as f:
                lines = [x.rstrip("\n") for x in f if x.strip()]
            tail = lines[-1][:160] if lines else ""
        except OSError:
            continue
        key = re.sub(r"_\d{8}\.log$|\.log$", "", name)
        prev = o.get(key)
        if prev and prev["更新"] >= mt.strftime("%Y-%m-%d %H:%M"):
            continue
        o[key] = {"更新": mt.strftime("%Y-%m-%d %H:%M"), "最終行": tail}
    return o


def actions_failures():
    """直近24hの失敗run。未認証APIのため取れないことがある（その場合は理由を返す）。

    ★全runを取ってから絞ってはいけない。このリポジトリは1日およそ300run 動くため、
      per_page=100 では6時間ぶんしか見えず、24時間の窓を埋められない。
      2026-08-07 にこの作りで、深夜の失敗25本を全て取りこぼしたうえ
      「取得=true / 失敗=0」と正常に見えてしまった。無言の欠測より危険。
      よって status=failure で失敗だけを、created>= で日付を絞って取り、
      さらにページを送る。取り切れなかった場合は 打切=true を立てる。
    """
    since = (now() - timedelta(days=2)).strftime("%Y-%m-%d")
    base = ("https://api.github.com/repos/" + REPO +
            "/actions/runs?status=failure&per_page=100&created=%3E%3D" + since)
    lim = now() - timedelta(hours=24)
    bad = []
    truncated = False
    for page in (1, 2, 3):
        req = urllib.request.Request(base + "&page=" + str(page), headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "healthStatus",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception as e:  # ネットワーク・レート制限・JSON崩れ すべてここ
            if page == 1:
                return {"取得": False, "理由": str(e)[:120],
                        "失敗": None, "打切": False, "一覧": []}
            truncated = True
            break
        runs = data.get("workflow_runs", [])
        for run in runs:
            if run.get("conclusion") != "failure":
                continue
            try:
                t = datetime.fromisoformat(
                    run["created_at"].replace("Z", "+00:00")).astimezone(JST)
            except (ValueError, KeyError):
                continue
            if t < lim:
                continue
            bad.append({
                "時刻": t.strftime("%m-%d %H:%M"),
                "名前": run.get("name", "")[:40],
                "url": run.get("html_url", ""),
            })
        if len(runs) < 100:
            break
        if page == 3:
            truncated = True
    bad.sort(key=lambda x: x["時刻"])
    return {"取得": True, "理由": None, "失敗": len(bad),
            "打切": truncated, "一覧": bad[:40]}


def _pages_workflow_id():
    """Pages デプロイWFの数値IDを、ワークフロー一覧から名前で引く。

    ★このWFは .github/workflows/ に実体を持たない動的WFで、
      path が dynamic/pages/pages-build-deployment のため、
      endpoint にファイル名を渡すと 404 になる（URLエンコードしても同じ）。
      数値IDでしか引けない。ただしIDをハードコードするとリポジトリの
      作り直しで壊れるので、毎回名前から解決する。
    """
    url = ("https://api.github.com/repos/" + REPO +
           "/actions/workflows?per_page=100")
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "healthStatus",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    for w in data.get("workflows", []):
        if w.get("name") == "pages-build-deployment":
            return w.get("id")
    return None


def deploys():
    """直近24hの Pages デプロイ。

    ★cancelled は failure に数えられないため、Actions失敗の集計では見えない。
      2026-08-06 にサイトが3時間止まった原因はキャンセルの連鎖だった
      （デプロイは同時1本しか処理できず、前が終わる前に次が来ると
        後続に追い越されて cancelled になる）。
      よってデプロイだけを別に数える。

    ★per_page=100 だけでは足りない。実測で先頭100件は約16.7時間ぶんしかなく、
      24時間の窓を埋められないまま「取得=true」と報告してしまう。
      created>= で日付を絞り、ページを送り、取り切れなければ 打切=true を立てる。

    最短間隔が短いほど詰まりやすい。デプロイ1本の所要は実測1〜2分なので、
    間隔がそれを下回る組が多いときは起動頻度が過剰。
    """
    try:
        wid = _pages_workflow_id()
    except Exception as e:
        return {"取得": False, "理由": "ID解決に失敗: " + str(e)[:100]}
    if not wid:
        return {"取得": False, "理由": "pages-build-deployment が一覧に無い"}

    since = (now() - timedelta(days=2)).strftime("%Y-%m-%d")
    base = ("https://api.github.com/repos/" + REPO +
            "/actions/workflows/" + str(wid) +
            "/runs?per_page=100&created=%3E%3D" + since)
    lim = now() - timedelta(hours=24)
    ts = []
    cnt = {"成功": 0, "キャンセル": 0, "失敗": 0, "実行中": 0, "その他": 0}
    truncated = False
    for page in (1, 2, 3, 4):
        req = urllib.request.Request(base + "&page=" + str(page), headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "healthStatus",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if page == 1:
                return {"取得": False, "理由": str(e)[:120]}
            truncated = True
            break
        runs = data.get("workflow_runs", [])
        for run in runs:
            try:
                t = datetime.fromisoformat(
                    run["created_at"].replace("Z", "+00:00")).astimezone(JST)
            except (ValueError, KeyError):
                continue
            if t < lim:
                continue
            ts.append(t)
            c = run.get("conclusion")
            if c == "success":
                cnt["成功"] += 1
            elif c == "cancelled":
                cnt["キャンセル"] += 1
            elif c == "failure":
                cnt["失敗"] += 1
            elif c is None:
                cnt["実行中"] += 1
            else:
                cnt["その他"] += 1
        if len(runs) < 100:
            break
        if page == 4:
            truncated = True
    ts.sort()
    gaps = [int((ts[i + 1] - ts[i]).total_seconds() // 60)
            for i in range(len(ts) - 1)]
    return {
        "取得": True,
        "理由": None,
        "打切": truncated,
        "総数": len(ts),
        "内訳": cnt,
        "最短間隔分": min(gaps) if gaps else None,
        "5分以内の連続": sum(1 for g in gaps if g <= 5),
        "先頭": ts[0].strftime("%m-%d %H:%M") if ts else None,
        "末尾": ts[-1].strftime("%m-%d %H:%M") if ts else None,
    }


_PS_TASKS = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
$o = [ordered]@{}
foreach ($n in @(%s)) {
  try {
    $t = Get-ScheduledTask -TaskName $n
    $i = $t | Get-ScheduledTaskInfo
    $o[$n] = [ordered]@{
      lastRun  = $i.LastRunTime.ToString('yyyy-MM-ddTHH:mm:ss')
      result   = [int64]$i.LastTaskResult
      state    = "$($t.State)"
      triggers = @($t.Triggers | ForEach-Object { [ordered]@{ kind = $_.CimClass.CimClassName; enabled = [bool]$_.Enabled; start = "$($_.StartBoundary)" } })
    }
  } catch { $o[$n] = [ordered]@{ error = $_.Exception.Message } }
}
$o | ConvertTo-Json -Depth 5 -Compress
"""


def query_tasks(names):
    """タスクスケジューラの記録を {タスク名: {...}} で返す。照会できなければ例外。"""
    script = _PS_TASKS % ",".join("'%s'" % n for n in names)
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    return json.loads(r.stdout)


def _latest_due(times, n):
    """times（["05:30", ...]・毎日）のうち、猶予を過ぎた直近の予定時刻。"""
    cands = []
    for back in (0, 1, 2):
        d = (n - timedelta(days=back)).date()
        for hm in times:
            h, m = map(int, hm.split(":"))
            dt = datetime(d.year, d.month, d.day, h, m, tzinfo=JST)
            if dt + timedelta(minutes=START_GRACE_MIN) <= n:
                cands.append(dt)
    return max(cands) if cands else None


def local_tasks(prev):
    """ローカルタスク3本の状態・最終起動・最終終了コード・最終成功。
    「最終成功」はタスクスケジューラが持たないため、前回の status.json から引き継ぐ。"""
    pv = (((prev or {}).get("ローカルタスク") or {}).get("タスク")) or {}
    res = {"取得": False, "理由": None, "開始猶予分": START_GRACE_MIN, "タスク": {}}

    def unverified(reason):
        res["理由"] = reason
        res["タスク"] = {k: {"状態": "未検証", "理由": reason,
                            "最終成功": (pv.get(k) or {}).get("最終成功")} for k in LOCAL_TASKS}
        return res

    if os.name != "nt":
        return unverified("ローカルPC（Windows）以外で実行された")
    try:
        info = query_tasks(list(LOCAL_TASKS.values()))
    except Exception as e:  # PowerShell 不在・タイムアウト・JSON崩れ
        return unverified("タスクスケジューラを照会できない: " + str(e)[:100])
    n = now()
    out = {}
    for key, tname in LOCAL_TASKS.items():
        t = info.get(tname) or {}
        prev_ok = (pv.get(key) or {}).get("最終成功")
        if not t or "error" in t:
            out[key] = {"状態": "未検証", "理由": "照会失敗: " + str(t.get("error"))[:100], "最終成功": prev_ok}
            continue
        trig = t.get("triggers") or []
        if isinstance(trig, dict):  # ConvertTo-Json は要素1つだと配列にしない
            trig = [trig]
        times, other = [], []
        for g in trig:
            if not g.get("enabled"):
                continue
            m = re.search(r"T(\d\d):(\d\d)", g.get("start") or "")
            if g.get("kind") == "MSFT_TaskDailyTrigger" and m:
                times.append("%s:%s" % m.groups())
            else:
                other.append(g.get("kind"))
        code = t.get("result")
        try:
            last = datetime.fromisoformat(t.get("lastRun") or "").replace(tzinfo=JST)
            if last.year < 2000:  # 一度も起動していないと 1999-11-30 が入る
                last = None
        except ValueError:
            last = None
        due = _latest_due(times, n) if times and not other else None
        fmt = lambda x: x.strftime("%Y-%m-%d %H:%M") if x else None
        e = {"予定": " ".join(sorted(times)), "直近の予定": fmt(due), "最終起動": fmt(last),
             "最終終了コード": code,
             "最終終了コード16進": ("0x%08X" % (code & 0xFFFFFFFF)) if isinstance(code, int) else None,
             "最終成功": fmt(last) if (code == 0 and last) else prev_ok,
             "タスク状態": t.get("state")}
        if other or not times:
            e["状態"], e["理由"] = "未検証", "予定時刻を計算できない（日次以外のトリガ: %s）" % other
        elif code == TASK_RUNNING:
            e["状態"] = "実行中"
        elif due is None:
            e["状態"], e["理由"] = "未検証", "直近の予定を計算できない"
        elif last is None or last < due:
            e["状態"], e["理由"] = "未実行", "直近の予定 %s 以降に起動記録が無い（記録なし＝未検証）" % fmt(due)
        elif code == 0:
            e["状態"] = "成功"
        else:
            e["状態"] = "失敗"
        out[key] = e
    res.update({"取得": True, "理由": None, "タスク": out})
    return res


def main():
    try:
        with open(OUT, encoding="utf-8") as f:
            prev = json.load(f)   # ローカルタスクの「最終成功」を引き継ぐため、上書き前に読む
    except (OSError, ValueError):
        prev = None
    git("fetch", "origin", "main")
    head = git("log", "-1", "--format=%cI|%h", "origin/main")
    head_t, head_sha = (head.split("|") + ["", ""])[:2] if "|" in head else ("", "")
    try:
        ht = datetime.fromisoformat(head_t).astimezone(JST)
        head_info = {"時刻": ht.strftime("%Y-%m-%d %H:%M"),
                     "経過分": int((now() - ht).total_seconds() // 60), "sha": head_sha}
    except ValueError:
        head_info = None

    doc = {
        "生成時刻": now().strftime("%Y-%m-%d %H:%M"),
        "生成元": "PCローカル（タスクスケジューラ）",
        "注記": "事実のみ。判定はしない。生成時刻が古い場合は監視自体が止まっている。",
        "最終コミット": head_info,
        "データ更新": {k: last_commit(v) for k, v in WATCH.items()},
        "観戦記": kansenki(),
        "ローカルログ": local_logs(),
        "ローカルタスク": local_tasks(prev),
        "Actions失敗": actions_failures(),
        "デプロイ": deploys(),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("wrote " + OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
