#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reqable Report Server 接收端。

Reqable 每完成一个会话就把 HAR JSON POST 到这里，本服务抽成
一行一条的精简记录追加写入 data/records.jsonl，供 flow_report.py 聚合。

短视频域名来自 build.py 产出的 shortvideo-domains.json（与屏蔽规则同源），
所以「屏蔽什么」和「统计什么」永远是同一份清单。

配置方式见同目录 README.md。
"""
import gzip
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parent.parent
DOMAINS_FILE = BASE / "shortvideo-domains.json"
OUT = BASE / "data" / "records.jsonl"
PORT = 18080


def load_matchers() -> dict:
    """分组名 -> (精确域名集合, 后缀元组, 关键词元组)。

    只取 DOMAIN / DOMAIN-SUFFIX / DOMAIN-KEYWORD。IP-CIDR 规则无法从 host
    反查归属，统计里用不上，跳过。
    """
    if not DOMAINS_FILE.exists():
        sys.exit(f"缺少 {DOMAINS_FILE.name}，先跑 python3 build.py")

    raw = json.loads(DOMAINS_FILE.read_text(encoding="utf-8"))["groups"]
    out = {}
    for group, rules in raw.items():
        exact, suffix, keyword = set(), [], []
        for rule in rules:
            rtype, _, value = rule.partition(":")
            if rtype == "DOMAIN":
                exact.add(value.lower())
            elif rtype == "DOMAIN-SUFFIX":
                suffix.append(value.lower())
            elif rtype == "DOMAIN-KEYWORD":
                keyword.append(value.lower())
        out[group] = (exact, tuple(suffix), tuple(keyword))
    return out


MATCHERS = load_matchers()


def classify(host: str) -> Optional[str]:
    for group, (exact, suffix, keyword) in MATCHERS.items():
        if host in exact:
            return group
        if any(host.endswith("." + s) or host == s for s in suffix):
            return group
        if any(k in host for k in keyword):
            return group
    return None


def decompress(raw: bytes) -> bytes:
    # Report Server 可配 Gzip/Brotli/Zstd。只解 gzip：其他算法原样返回，
    # 让上层 JSON 解析报错暴露出来，而不是静默写入坏数据。
    if raw[:2] == b"\x1f\x8b":
        return gzip.decompress(raw)
    return raw


def to_record(entry: dict) -> dict:
    """HAR 单条 entry -> 精简记录。"""
    req = entry.get("request") or {}
    resp = entry.get("response") or {}
    url = req.get("url", "")
    host = (urlparse(url).hostname or "").lower()
    # bodySize 是实际传输字节（-1 表示该字段未记录）。流量统计必须用传输量，
    # 不能用 content.size（那是解压后大小，视频流会严重低估）。
    body_size = resp.get("bodySize", -1)
    if not isinstance(body_size, int) or body_size < 0:
        body_size = (resp.get("content") or {}).get("size", 0) or 0
    return {
        "ts": entry.get("startedDateTime"),
        "host": host,
        "group": classify(host),
        "url": url,
        "method": req.get("method"),
        "status": resp.get("status"),
        "bytes_in": body_size,
        "bytes_out": req.get("bodySize", 0) or 0,
        "mime": (resp.get("content") or {}).get("mimeType", ""),
    }


def extract(har: dict) -> list:
    log = har.get("log")
    if isinstance(log, dict):
        return [to_record(e) for e in log.get("entries") or []]
    # Report Server 可能只推一条裸 entry
    if "request" in har:
        return [to_record(har)]
    return []


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        try:
            records = extract(json.loads(decompress(raw)))
        except Exception as exc:
            self.send_error(400, f"bad payload: {exc}")
            return

        with open(OUT, "a", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        # Reqable 不重试，但返回 200 才算推送成功
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def do_GET(self):
        # 用于自检：服务活着吗、攒了多少条
        n = sum(1 for _ in open(OUT, encoding="utf-8")) if OUT.exists() else 0
        body = json.dumps({"ok": True, "records": n}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # 保留默认访问日志到 stderr，方便确认 Reqable 真的推过来了
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    print(f"规则来源 {DOMAINS_FILE.name}：{len(MATCHERS)} 组", flush=True)
    print(f"listening on http://0.0.0.0:{PORT}  ->  {OUT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
