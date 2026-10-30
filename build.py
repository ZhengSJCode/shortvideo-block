#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 sources.txt 生成 Shadowrocket 配置。

不依赖任何代理节点：被屏蔽的域名走 REDIRECT/REJECT，其余流量全部 DIRECT。
后续有了节点，把文件末尾 FINAL,DIRECT 改成 FINAL,PROXY 即可。
"""

import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
SOURCES = BASE / "sources.txt"
OUTPUT = BASE / "shortvideo.conf"

HEADER = """# 短视频屏蔽配置 · Shadowrocket
# 生成时间: {ts}
# 规则来源: 本项目 sources.txt
#
# 当前模式: 无节点（FINAL 直连）
# 需要代理时，把文件末尾 FINAL,DIRECT 改为 FINAL,PROXY 并配置节点

[General]
ipv6 = false
bypass-system = true
skip-proxy = 192.168.0.0/16, 10.0.0.0/8, 172.16.0.0/12, localhost, *.local, *.lan, captive.apple.com
dns-server = https://dns.alidns.com/dns-query, https://doh.pub/dns-query
[Rule]
"""

FOOTER = """
# 兜底：未匹配的流量全部直连（无节点模式）
FINAL,DIRECT
"""


def parse_sources(path):
    """把 sources.txt 解析成 [(section, domain), ...]，保持文件顺序。"""
    section = None
    entries = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().upper()
            if section not in ("REDIRECT", "REJECT"):
                raise ValueError(f"未知段落: {line}")
            continue
        if section is None:
            raise ValueError(f"域名出现在任何段落之前: {line}")
        entries.append((section, line))
    return entries


def render_rules(entries):
    """REDIRECT 必须排在 REJECT 之前，否则同域名会被 REJECT 抢先匹配。"""
    order = {"REDIRECT": 0, "REJECT": 1}
    lines = []
    current = None
    for section, domain in sorted(entries, key=lambda e: order[e[0]]):
        if section != current:
            current = section
            lines.append(f"\n# === {section} ===")
        lines.append(f"DOMAIN-SUFFIX,{domain},{section}")
    return "\n".join(lines)


def main():
    entries = parse_sources(SOURCES)
    if not entries:
        sys.exit("sources.txt 里没有任何域名")

    content = HEADER.format(ts=time.strftime("%Y-%m-%d %H:%M:%S"))
    content += render_rules(entries) + FOOTER

    OUTPUT.write_text(content, encoding="utf-8")
    print(f"已生成 {OUTPUT.name}: {len(entries)} 条规则")


if __name__ == "__main__":
    main()
