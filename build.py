#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从上游分类规则生成 Shadowrocket 短视频屏蔽配置。

规则来源：blackmatrix7/ios_rule_script（每日自动更新的分类规则库）
产物策略统一改为 REJECT，未命中的流量走 FINAL,DIRECT（无节点模式）。

为什么不手写域名：上游维护者持续跟进各 App 新增的 CDN 域名，
手写清单几天就过期。
"""

import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
OUTPUT = BASE / "shortvideo.conf"

UPSTREAM = "https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Shadowrocket"

# 分组 -> 上游规则名。增删这里即可调整屏蔽范围。
GROUPS = {
    "抖音": "DouYin",
    "快手": "KuaiShou",
    "TikTok": "TikTok",
    "B站": "BiliBili",
    "小红书": "XiaoHongShu",
}

HEADER = """# 短视频屏蔽配置 · Shadowrocket
# 生成时间: {ts}
# 规则来源: blackmatrix7/ios_rule_script（上游每日更新）
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

# 上游使用的规则类型，保留这几种；其余（PROCESS-NAME 等）SR 配置里不通用
KEPT_TYPES = ("DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "IP-CIDR", "IP-CIDR6")


def fetch(name):
    url = f"{UPSTREAM}/{name}/{name}.list"
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read().decode("utf-8")


def parse(rule_text):
    """提取规则并统一改写为 REJECT；返回 [(类型, 值), ...]。"""
    out = []
    for raw in rule_text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2 or parts[0] not in KEPT_TYPES:
            continue
        out.append((parts[0], parts[1]))
    return out


def main():
    sections = []
    total = 0

    for label, name in GROUPS.items():
        try:
            rules = parse(fetch(name))
        except Exception as e:
            # 单个源失败不应让整份配置失效，但必须让失败可见
            print(f"[警告] {label} 拉取失败: {e}", file=sys.stderr)
            continue

        if not rules:
            print(f"[警告] {label} 解析结果为空", file=sys.stderr)
            continue

        seen = set()
        lines = [f"\n# === {label}（{len(rules)} 条）==="]
        for rtype, value in rules:
            key = (rtype, value)
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"{rtype},{value},REJECT")

        sections.append("\n".join(lines))
        total += len(seen)

    if not sections:
        sys.exit("所有上游源都失败，未生成配置")

    content = HEADER.format(ts=time.strftime("%Y-%m-%d %H:%M:%S"))
    content += "\n".join(sections) + FOOTER

    OUTPUT.write_text(content, encoding="utf-8")
    print(f"已生成 {OUTPUT.name}: {total} 条规则")


if __name__ == "__main__":
    main()
