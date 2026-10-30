#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 sources.txt 生成 Shadowrocket 配置。

不依赖任何代理节点：被屏蔽的域名走 REJECT，其余流量全部 DIRECT。
后续有了节点，把文件末尾 FINAL,DIRECT 改成 FINAL,PROXY 即可。

Shadowrocket 只认 Reject / DIRECT / Proxy 三个内置策略名，写错会让整条规则失效。
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
# 当前模式: 无节点（末尾 FINAL 直连）
# 需要代理时，把末尾 FINAL,DIRECT 改成 FINAL,PROXY 并配置节点

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


def parse_domains(path):
    """读取纯域名清单，跳过空行和注释。"""
    domains = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        domains.append(line)
    return domains


def main():
    domains = parse_domains(SOURCES)
    if not domains:
        sys.exit("sources.txt 里没有任何域名")

    rules = "\n".join(f"DOMAIN-SUFFIX,{d},REJECT" for d in domains)
    content = HEADER.format(ts=time.strftime("%Y-%m-%d %H:%M:%S")) + rules + FOOTER

    OUTPUT.write_text(content, encoding="utf-8")
    print(f"已生成 {OUTPUT.name}: {len(domains)} 条规则")


if __name__ == "__main__":
    main()
