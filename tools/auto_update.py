#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""定期跑 build.py，上游域名有增删就自动提交并开 PR。

只比较 shortvideo-domains.json 里的 groups（域名集合），不比较时间戳——
build.py 每次跑都会刷新生成时间，直接 git diff 会永远显示「有变化」。

跑完最终回到 main，改动只存在于 auto/rules-update 分支的 PR 里，
所以下一轮的基线永远是 main 上的版本。
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DOMAINS = BASE / "shortvideo-domains.json"
BRANCH = "auto/rules-update"
PR_TITLE = "同步上游短视频域名"


def sh(*args, check=True):
    return subprocess.run(args, cwd=BASE, capture_output=True, text=True, check=check)


def load_groups() -> dict:
    if not DOMAINS.exists():
        return {}
    return json.loads(DOMAINS.read_text(encoding="utf-8")).get("groups", {})


def diff_groups(old: dict, new: dict) -> list:
    """返回 [(分组, 新增列表, 删除列表)]，只含有变化的组。"""
    out = []
    for group in sorted(set(old) | set(new)):
        o, n = set(old.get(group, [])), set(new.get(group, []))
        if o != n:
            out.append((group, sorted(n - o), sorted(o - n)))
    return out


def commit_message(changes: list) -> str:
    lines = ["[chore][rules] 同步上游短视频域名", ""]
    for group, added, removed in changes:
        parts = []
        if added:
            parts.append(f"新增 {len(added)} 条")
        if removed:
            parts.append(f"移除 {len(removed)} 条")
        lines.append(f"- {group}：{'、'.join(parts)}")
    lines.append("- 由 tools/auto_update.py 从 blackmatrix7 上游规则自动同步")
    lines.append("")
    lines.append("Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
    return "\n".join(lines)


def build() -> bool:
    r = sh(sys.executable, "build.py", check=False)
    if r.returncode != 0:
        print(f"build.py 失败：{r.stderr.strip()[:500]}", file=sys.stderr)
        return False
    return True


def has_open_pr() -> bool:
    r = sh("gh", "pr", "list", "--head", BRANCH, "--state", "open",
           "--json", "number", check=False)
    if r.returncode != 0:
        return False
    try:
        return len(json.loads(r.stdout or "[]")) > 0
    except json.JSONDecodeError:
        return False


def publish(changes: list) -> None:
    sh("git", "add", "shortvideo-domains.json", "shortvideo.conf")
    sh("git", "commit", "-m", commit_message(changes))
    sh("git", "push", "-f", "-u", "origin", BRANCH)

    if has_open_pr():
        print(f"已更新现有 PR（分支 {BRANCH}）")
        return

    body = "## 变更\n\n" + "\n".join(
        f"- **{g}**：新增 {len(a)} 条，移除 {len(r)} 条" for g, a, r in changes
    ) + "\n\n由 `tools/auto_update.py` 自动生成，上游为 blackmatrix7/ios_rule_script。"
    sh("gh", "pr", "create", "--base", "main", "--head", BRANCH,
       "--title", PR_TITLE, "--body", body)
    print(f"已创建 PR（分支 {BRANCH}）")


def main():
    old = load_groups()

    # 基于最新 main 建工作分支。已跟踪文件的本地改动会随 checkout 带过来，
    # 下一句 build() 会重新覆盖它们，所以这里不丢信息。
    sh("git", "fetch", "origin", "main")
    sh("git", "checkout", "-B", BRANCH, "origin/main")

    if not build():
        sh("git", "checkout", "main", check=False)
        sys.exit("上游拉取失败，跳过本次同步")

    changes = diff_groups(old, load_groups())
    if not changes:
        # 没有变化就别留下一个空分支
        sh("git", "checkout", "main", check=False)
        sh("git", "checkout", "--", "shortvideo.conf", check=False)
        print(f"{datetime.now():%Y-%m-%d %H:%M} 无变化")
        return

    added = sum(len(a) for _, a, _ in changes)
    removed = sum(len(r) for _, _, r in changes)
    print(f"检测到变化：新增 {added} 条，移除 {removed} 条")
    publish(changes)
    sh("git", "checkout", "main", check=False)


if __name__ == "__main__":
    main()
