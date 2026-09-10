#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prepushVerify.py — Claude Code PreToolUse フック（Bash / PowerShell）

nightlyPipeline.yml の出力（見どころ highlights・predictions・出走表・モーター）を含む
コミットを、検算を通さずに push させないためのゲート。
nightlyPipeline は検算（nightly_decide）を持つが commit が `if: always()` で、
検算の成否に関係なく同じパスを push する。同じパスへ Claude Code から push するときに、
ここで同じ穴を開けない。GitHub Actions 上の push はこのフックの対象外（Claude Code の
ツール呼び出しだけに効く）。

検算の内容（対象は push されるコミットが触ったファイルのうち SCOPE 内のもの）:
  1. predictions/YYYYMMDD.json は write-once。追加(A)以外（変更・削除・改名）は FAIL。
     追加でも remote 側に既に同名があれば FAIL（マージ時の上書きになる）。
     中身は JSON・「予測」非空・「開催日」がファイル名と一致（monitorPredictions.valid_pred と同じ基準＋日付）。
  2. docs/highlights/*.json は JSON として開けること。公開物なので予測専用キー
     （build_highlights.py の pred_entry にだけある 判定・主役艇 等）が1つでもあれば FAIL。
     highlights.json はレースが空でないこと（build_highlights.py の自己検査と同じ基準）。
  3. SCOPE 内のテキストに衝突マーカー（<<<<<<< / >>>>>>>）が残っていれば FAIL。
  4. SCOPE 内の削除は FAIL。検算方法を定義していない拡張子も FAIL。

終了コード: 0 = push ではない、または検算 PASS を確認できた / 2 = FAIL（ブロック）。
**検算が走らなかった・完走しなかった場合も 2。** 0 を返すのは PASS を確認できたときだけ。
"""
import json
import os
import re
import shlex
import subprocess
import sys

TAG = "[prepushVerify]"

SCOPE = (
    "docs/highlights/",
    "predictions/",
    "docs/racers/",
    "docs/motor/",
    "docs/data/venueMeta.json",
    "docs/data/motorHistory.json",
)
PRED_RE = re.compile(r"^predictions/(\d{8})\.json$")
# build_highlights.py の pred_entry（:1159-1168）にだけ入り、公開 highlights には入れないキー（:1384）。
PRED_ONLY_KEYS = {"判定", "主役艇", "スコア", "スコア内訳", "対抗艇", "死角艇",
                  "見出しID", "死角ID", "波及ID", "締めID"}
TEXT_EXT = {".csv", ".html", ".js", ".css", ".txt", ".md", ".svg"}
MARKER_RE = re.compile(r"^(<{7}|>{7})( |$)", re.M)
SEP_RE = re.compile(r"&&|\|\||[;|\n]")
GIT_TIMEOUT = 20


class Unverifiable(Exception):
    """検算を完走できなかった。PASS 扱いにしない。"""


def log(msg):
    print(f"{TAG} {msg}", file=sys.stderr)


def git(args, cwd, check=True, binary=False):
    try:
        p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, timeout=GIT_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Unverifiable(f"git {' '.join(args)} を実行できない: {e}")
    if check and p.returncode != 0:
        raise Unverifiable(f"git {' '.join(args)} が rc={p.returncode}: "
                           f"{p.stderr.decode('utf-8', 'replace').strip()}")
    if binary:
        return p
    return p.returncode, p.stdout.decode("utf-8", "replace")


# ---------------------------------------------------------------- コマンド解析

def to_local_path(p, base):
    p = os.path.expanduser(p)
    m = re.match(r"^/([a-zA-Z])(/.*)?$", p)
    if os.name == "nt" and m:
        p = f"{m.group(1).upper()}:{m.group(2) or '/'}"
    return os.path.normpath(os.path.join(base, p))


def find_pushes(command, cwd):
    """command 内の git push を [(repo_dir, push_args)] で返す。解析できなければ Unverifiable。"""
    pushes = []
    for seg in (s.strip() for s in SEP_RE.split(command)):
        if not seg:
            continue
        try:
            toks = shlex.split(seg.replace("\\", "/"), posix=True)
        except ValueError as e:
            if re.search(r"\bgit\b.*\bpush\b", seg):
                raise Unverifiable(f"push を含みうる部分を解析できない（{e}）: {seg}")
            continue
        while toks and (re.match(r"^\w+=", toks[0]) or toks[0] in ("&", "command", "exec", "time", "sudo")):
            toks = toks[1:]
        if not toks:
            continue
        head = toks[0].lower()
        if head in ("cd", "set-location", "sl", "pushd", "chdir"):
            rest = [t for t in toks[1:] if t.lower() not in ("-path", "-literalpath")]
            cwd = to_local_path(rest[0], cwd) if rest else os.path.expanduser("~")
            continue
        if os.path.basename(head) not in ("git", "git.exe"):
            continue
        repo, i = cwd, 1
        while i < len(toks) and toks[i].startswith("-"):
            if toks[i] == "-C" and i + 1 < len(toks):
                repo = to_local_path(toks[i + 1], repo)
                i += 2
            elif toks[i] in ("-c", "--git-dir", "--work-tree", "--namespace") and i + 1 < len(toks):
                i += 2
            else:
                i += 1
        if i < len(toks) and toks[i] == "push":
            pushes.append((repo, toks[i + 1:]))
    return pushes


def parse_push_args(args):
    """(remote, [src...], delete) を返す。src は rev-list に渡せる形。"""
    positional, delete, mode = [], False, None
    takes_value = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}
    i = 0
    while i < len(args):
        a = args[i]
        if a in takes_value:
            i += 2
            continue
        if a in ("--all", "--branches", "--mirror"):
            mode = "--branches"
        elif a == "--tags":
            mode = mode or "--tags"
        elif a in ("-d", "--delete"):
            delete = True
        elif a.startswith("--repo="):
            positional.insert(0, a.split("=", 1)[1])
        elif not a.startswith("-"):
            positional.append(a)
        i += 1
    remote = positional[0] if positional else None
    refspecs = positional[1:]
    if delete:
        return remote, [], True
    if mode:
        return remote, [mode], False
    srcs = []
    for r in refspecs:
        src = r.lstrip("+").split(":", 1)[0]
        if src:  # ":dst" は削除
            srcs.append(src)
    if not refspecs:
        srcs = ["HEAD"]
    return remote, srcs, False


# ---------------------------------------------------------------- 検算

def in_scope(path):
    return any(path == s or path.startswith(s) for s in SCOPE)


def find_keys(obj, keys, found):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in keys:
                found.add(k)
            find_keys(v, keys, found)
    elif isinstance(obj, list):
        for v in obj:
            find_keys(v, keys, found)
    return found


def tips_of(srcs, repo):
    tips = []
    for s in srcs:
        if s in ("--branches", "--tags"):
            ref = "refs/heads" if s == "--branches" else "refs/tags"
            _, out = git(["for-each-ref", "--format=%(objectname)", ref], repo)
            for oid in out.split():
                _, c = git(["rev-parse", "--verify", f"{oid}^{{commit}}"], repo)
                tips.append(c.strip())
        else:
            _, c = git(["rev-parse", "--verify", f"{s}^{{commit}}"], repo)
            tips.append(c.strip())
    return tips


def read_blob(repo, tip, path):
    p = git(["cat-file", "blob", f"{tip}:{path}"], repo, check=False, binary=True)
    if p.returncode != 0:
        return None
    return p.stdout


def check_file(path, data, fails):
    ext = os.path.splitext(path)[1].lower()
    if ext != ".json" and ext not in TEXT_EXT:
        fails.append(f"{path}: 検算方法を定義していない形式（{ext or '拡張子なし'}）")
        return
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        fails.append(f"{path}: UTF-8 として読めない（{e}）")
        return
    if MARKER_RE.search(text):
        fails.append(f"{path}: 衝突マーカーが残っている")
    if ext != ".json":
        return
    try:
        doc = json.loads(text)
    except ValueError as e:
        fails.append(f"{path}: JSON として開けない（{e}）")
        return
    m = PRED_RE.match(path)
    if m:
        if not (isinstance(doc, dict) and doc.get("予測")):
            fails.append(f"{path}: 「予測」が空または無い")
        elif str(doc.get("開催日")) != m.group(1):
            fails.append(f"{path}: 開催日 {doc.get('開催日')} がファイル名と一致しない")
    if path.startswith("docs/highlights/"):
        leaked = find_keys(doc, PRED_ONLY_KEYS, set())
        if leaked:
            fails.append(f"{path}: 公開物に予測専用キーがある {sorted(leaked)}")
        if path == "docs/highlights/highlights.json":
            if not (isinstance(doc, dict) and doc.get("レース数", 0) > 0 and doc.get("レース")):
                fails.append(f"{path}: レースが空")


def verify_push(repo, args):
    """1回の git push を検算。FAIL 理由のリストを返す（空＝PASS）。"""
    if not os.path.isdir(repo):
        raise Unverifiable(f"push 先の作業ディレクトリが存在しない: {repo}")
    _, top = git(["rev-parse", "--show-toplevel"], repo)
    repo = top.strip()
    remote, srcs, delete = parse_push_args(args)
    if delete or not srcs:
        log(f"PASS: {repo} — 送る内容なし（リモート参照の削除のみ）")
        return []
    _, remotes = git(["remote"], repo)
    remotes = remotes.split()
    remote_ref = remote if remote in remotes else ("origin" if "origin" in remotes else None)
    if not remote_ref:
        raise Unverifiable(f"比較基準の remote を特定できない（push 先: {remote}）")
    # 基準は <remote>/main だけ。「どこかの remote ref に載っている」は検算済みの証明にならない
    # （フックの無い経路で別ブランチへ出したコミットを、main への push で素通りさせない）。
    base_ref = f"refs/remotes/{remote_ref}/main"
    if git(["rev-parse", "--verify", "--quiet", base_ref], repo, check=False)[0] != 0:
        raise Unverifiable(f"比較基準 {base_ref} が無い")
    exclude = [base_ref]
    tips = tips_of(srcs, repo)

    _, out = git(["log", "--no-renames", "--diff-merges=first-parent", "--name-status",
                  "--format=", *tips, "--not", *exclude], repo)
    changes = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        st, path = parts[0][:1], parts[-1]
        if in_scope(path):
            changes.setdefault(path, set()).add(st)
    if not changes:
        log(f"PASS: {repo} — push 対象コミットは検算対象パスに触れていない（対象外）")
        return []

    fails = []
    preds_added = []
    for path, sts in sorted(changes.items()):
        if PRED_RE.match(path):
            if sts - {"A"}:
                fails.append(f"{path}: write-once 違反（{''.join(sorted(sts))}）。predictions は追加のみ")
            else:
                preds_added.append(path)
        if "D" in sts:
            fails.append(f"{path}: 検算対象パスの削除")

    if preds_added:
        r = remote_ref or ("origin" if "origin" in remotes else None)
        if not r:
            raise Unverifiable("predictions 追加の上書き判定に使う remote が特定できない")
        rc, _ = git(["fetch", "--quiet", r, "main"], repo, check=False)
        if rc != 0:
            raise Unverifiable(f"{r} main を fetch できず、既存 predictions との突合ができない")
        base = f"refs/remotes/{r}/main"
        for path in preds_added:
            if git(["cat-file", "-e", f"{base}:{path}"], repo, check=False)[0] == 0:
                fails.append(f"{path}: {r}/main に既に存在する（マージで上書きになる）")

    checked = 0
    for tip in tips:
        for path in sorted(changes):
            data = read_blob(repo, tip, path)
            if data is None:
                continue
            check_file(path, data, fails)
            checked += 1
    if checked == 0 and not fails:
        raise Unverifiable("対象ファイルを1つも検算できなかった")

    if fails:
        return fails
    log(f"PASS: {repo} — 検算対象 {len(changes)} ファイル / 検査 {checked} 件すべて合格")
    return []


def run():
    raw = sys.stdin.buffer.read().decode("utf-8")
    payload = json.loads(raw)
    cmd = (payload.get("tool_input") or {}).get("command")
    if not isinstance(cmd, str):
        raise Unverifiable(f"tool_input.command を取得できない（tool={payload.get('tool_name')}）")
    cwd = payload.get("cwd") or os.getcwd()
    pushes = find_pushes(cmd, cwd)
    if not pushes:
        return 0
    all_fails = []
    for repo, args in pushes:
        all_fails += verify_push(repo, args)
    if all_fails:
        log("BLOCK: 検算 FAIL。push を止めた。")
        for f in all_fails:
            log(f"  FAIL {f}")
        return 2
    return 0


def main():
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        rc = run()
    except Unverifiable as e:
        log(f"BLOCK: 検算が完走しなかった — {e}。未検証は合格にしない。")
        sys.exit(2)
    except BaseException as e:  # 想定外の例外も「検算が走らなかった」扱い
        log(f"BLOCK: 検算が異常終了した（{type(e).__name__}: {e}）。未検証は合格にしない。")
        sys.exit(2)
    sys.exit(0 if rc == 0 else 2)


if __name__ == "__main__":
    main()
