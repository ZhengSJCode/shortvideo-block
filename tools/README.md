# Reqable 流量统计

## 三个文件

| 文件 | 作用 |
|---|---|
| `receiver.py` | HTTP 接收端，监听 `18080`，把 Reqable 推来的 HAR 抽成一行一条写进 `records.jsonl` |
| `report.py` | 按小时聚合，输出总流量 / 短视频流量 / 占比 / 域名 Top10 |
| `records.jsonl` | 数据，一行一条 JSON |

## 启动

```bash
cd ~/reqable-flow
nohup python3 receiver.py > receiver.log 2>&1 &
```

自检：`curl http://127.0.0.1:18080/` 应返回 `{"ok": true, "records": N}`

## Reqable 侧配置

1. 打开 Reqable → 菜单 `Tools` → `Report Server`
2. 新增一条：
   - **Name**: `local`
   - **URL Rule**: `*`（先全量收，摸清域名后再收窄）
   - **Endpoint**: `http://127.0.0.1:18080/`
   - **Compression**: `None`（receiver 只解 gzip，配 None 最省事）
3. 保存后正常抓包，`receiver.log` 应出现 `POST / 200`

手机抓包时把 Endpoint 换成 Mac 的局域网 IP，如 `http://192.168.x.x:18080/`。

## 看报表

```bash
python3 report.py           # 今天
python3 report.py --days 7  # 最近 7 天
```

## 域名规则

短视频平台域名写在 `receiver.py` 的 `SHORTS_HOSTS` 里。看报表的「流量域名 Top 10」
能发现漏掉的 CDN，补进去即可。新记录才会用新规则，旧记录里 `platform` 是写入时算好的。
