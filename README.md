<img width="1428" height="1273" alt="image" src="https://github.com/user-attachments/assets/edee0eaf-1056-4d1b-b9ce-4233cd65fe9a" /># 训记训练数据 Dashboard

基于[训记](https://xunjiapp.cn) Open API 的**自托管**训练数据看板：减脂 / 增肌多维分析、训练日历下钻、动作进步曲线。

每人使用**自己的训记 API Key**，数据只存在你自己的机器上。本项目不做多用户 SaaS。

## 功能

| 页面 | 内容 |
|------|------|
| 总览 | KPI、月度趋势、力量 vs 有氧、部位分布 |
| 减脂分析 | 有氧里程 / 消耗、心率、训练记录 |
| 增肌训练 | 容量增长、部位月度、Top 动作 |
| 训练节奏 | 周频率、星期 / 时段分布 |
| 动作进步 | 动作趋势、PR；下钻看历史组数与重量进步 |
| 训练日历 | 热力图；下钻看当日完整训练 |

图表支持多维下钻（月 / 周 / 部位 / 动作 / 日）。

<img width="1428" height="1273" alt="image" src="https://github.com/user-attachments/assets/dc9d7a37-1ca5-4173-ba6c-50c7b9dd1786" />
<img width="1429" height="1266" alt="image" src="https://github.com/user-attachments/assets/a022a07b-4583-4b61-aff0-7b5316a6277e" />
<img width="1431" height="1265" alt="image" src="https://github.com/user-attachments/assets/15be79e6-4560-419a-8c54-233ec04f03aa" />




## 前置条件

1. 已安装 [Docker](https://docs.docker.com/get-docker/)（推荐）或 Python 3.10+ / Node 20+
2. 训记 App 中申请 **Open API / LLM Key**（形如 `xjllm_...`）

> Key 只属于你的账号；不要提交到 Git，不要发给别人。

## 快速开始（Docker）

```bash
git clone https://github.com/<your-org>/xunji-log.git
cd xunji-log

cp .env.example .env
# 编辑 .env，填写：
#   XUNJI_API_KEY=xjllm_你的密钥

chmod +x scripts/docker-ops.sh
./scripts/docker-ops.sh up
```

浏览器打开：http://localhost:8080

首次启动后在总览页点 **「增量同步训练数据」**，或：

```bash
# 需本机有 Python，且 export XUNJI_API_KEY=...
python3 scripts/sync_training.py --refresh-days 3
./scripts/docker-ops.sh refresh
```

也可让容器内定时任务自动同步（见下方配置）。

## 配置说明（`.env`）

| 变量 | 必填 | 说明 |
|------|------|------|
| `XUNJI_API_KEY` | **是** | 训记 Open API Key |
| `DASHBOARD_PORT` | 否 | 默认 `8080` |
| `SYNC_ENABLED` | 否 | 默认 `true`，定时增量抓取 |
| `SYNC_CRON` | 否 | 默认 `30 6 * * *`（每天 06:30） |
| `SYNC_REFRESH_DAYS` | 否 | 每次强制重抓最近 N 天，默认 `3` |
| `TZ` | 否 | 默认 `Asia/Shanghai` |

## 本地开发（不经 Docker）

```bash
cp .env.example .env
# 填写 XUNJI_API_KEY

export $(grep -v '^#' .env | xargs)   # 或手动 export

# 抓取 + 聚合
python3 scripts/fetch_training.py --incremental --refresh-days 3
python3 scripts/analyze.py

# API
pip3 install -r server/requirements.txt
uvicorn server.main:app --host 0.0.0.0 --port 8080 --reload

# 前端（另开终端）
cd web && npm install && npm run dev
# http://localhost:5173
```

## 运维命令

```bash
./scripts/docker-ops.sh status    # 状态 + 健康检查
./scripts/docker-ops.sh logs      # 日志
./scripts/docker-ops.sh refresh   # 仅重新聚合 analysis.json
./scripts/docker-ops.sh restart
./scripts/docker-ops.sh down
./scripts/docker-ops.sh rebuild   # 代码更新后无缓存重建
```

### API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/analysis` | 完整分析数据 |
| GET | `/api/day/{date}` | 单日训练明细 |
| GET | `/api/drill?type=&key=` | 多维下钻（month / week / category / movement / day / …） |
| GET | `/api/sync/status` | 最近同步结果 |
| POST | `/api/sync` | 增量抓取 + 刷新分析 |
| POST | `/api/refresh` | 仅重新聚合 |

## 数据目录

```
data/
  cache/YYYY-MM-DD.json   # 训记原始按日缓存（勿提交）
  analysis.json           # 聚合结果（勿提交）
  sync_status.json        # 同步状态（勿提交）
```

训练数据属于个人健康信息，请仅在自有设备上保存。`.gitignore` 已排除上述文件。

## 部署到云主机（可选）

与家用 Ubuntu 相同流程：在腾讯云轻量 / CVM 上安装 Docker → clone → 配置 `.env` 中的 `XUNJI_API_KEY` → `./scripts/docker-ops.sh up`。

公网暴露时建议：

- 前面加 Nginx / Caddy，启用 HTTPS
- 安全组只放行 443（或 VPN / Tailscale）
- **不要**把未设访问控制的 Dashboard 直接挂公网（当前无登录，等同公开你的训练数据）

## 安全提示

- 仓库**不包含**任何默认 API Key；未配置 `XUNJI_API_KEY` 时同步会直接失败并提示
- 切勿把 `.env`、真实 Key、`data/cache` 推送到公开仓库
- 若 Key 曾泄露，请在训记 App 中轮换

## 许可证

MIT — 见 [LICENSE](./LICENSE)。

训记 App、Open API 及其商标归各自权利人所有；使用 API 须遵守训记官方条款。
