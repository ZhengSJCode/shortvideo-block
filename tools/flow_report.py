#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按小时聚合 data/records.jsonl，输出短视频流量占比。

用法:
    python3 tools/flow_report.py            # 今天
    python3 tools/flow_report.py 2026-10-31
    python3 tools/flow_report.py --days 3
"""
import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

RECORDS = Path(__file__).resolve().parent.parent / "data" / "records.jsonl"
MB = 1024 * 1024


def parse_ts(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone()
    except ValueError:
        return None


def load(day_filter: Optional[set] = None) -> list:
    if not RECORDS.exists():
        return []
    out = []
    with open(RECORDS, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            dt = parse_ts(r.get("ts"))
            if not dt:
                continue
            if day_filter and dt.strftime("%Y-%m-%d") not in day_filter:
                continue
            r["_dt"] = dt
            out.append(r)
    return out


def fmt_mb(n: int) -> str:
    return f"{n / MB:.1f} MB"


def summarize(rows: list) -> None:
    if not rows:
        print("没有记录。先启动 tools/flow_receiver.py 并在 Reqable 里配好 Report Server。")
        return

    # 每小时：总字节、短视频字节、各分组字节
    hourly = defaultdict(lambda: {"all": 0, "shorts": 0, "by_group": defaultdict(int)})
    by_host = defaultdict(int)
    for r in rows:
        h = r["_dt"].strftime("%m-%d %H:00")
        size = r["bytes_in"] + r["bytes_out"]
        hourly[h]["all"] += size
        by_host[r["host"]] += size
        group = r.get("group")
        if group:
            hourly[h]["shorts"] += size
            hourly[h]["by_group"][group] += size

    print(f"{'时间':<14}{'总流量':>12}{'短视频':>12}{'占比':>9}  主要来源")
    print("-" * 78)
    for h in sorted(hourly):
        d = hourly[h]
        pct = d["shorts"] / d["all"] * 100 if d["all"] else 0
        tops = sorted(d["by_group"].items(), key=lambda x: -x[1])[:3]
        top_s = "  ".join(f"{k} {fmt_mb(v)}" for k, v in tops) or "-"
        print(f"{h:<14}{fmt_mb(d['all']):>12}{fmt_mb(d['shorts']):>12}{pct:>8.1f}%  {top_s}")

    total = sum(d["all"] for d in hourly.values())
    shorts = sum(d["shorts"] for d in hourly.values())
    print("-" * 78)
    pct = shorts / total * 100 if total else 0
    print(f"{'合计':<14}{fmt_mb(total):>12}{fmt_mb(shorts):>12}{pct:>8.1f}%")

    # 域名 Top 10：用来发现「流量大但没被归类」的新 CDN，据此补 build.py 的分组
    group_of = {}
    for r in rows:
        if r.get("group") and r["host"] not in group_of:
            group_of[r["host"]] = r["group"]
    print("\n流量域名 Top 10（未归类的值得看看是不是漏掉的短视频 CDN）：")
    for host, size in sorted(by_host.items(), key=lambda x: -x[1])[:10]:
        tag = f"  <- {group_of[host]}" if host in group_of else ""
        print(f"  {fmt_mb(size):>10}  {host}{tag}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date", nargs="?", help="YYYY-MM-DD，默认今天")
    ap.add_argument("--days", type=int, help="最近 N 天")
    args = ap.parse_args()

    if args.days:
        days = {(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                for i in range(args.days)}
    elif args.date:
        days = {args.date}
    else:
        days = {datetime.now().strftime("%Y-%m-%d")}

    rows = load(days)
    if not rows and not RECORDS.exists():
        sys.exit("没有数据文件，先启动 tools/flow_receiver.py")
    summarize(rows)


if __name__ == "__main__":
    main()
