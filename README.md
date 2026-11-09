# 数据中心运维助理 · 本地交付（阶段 5 收尾）

给数据中心值班工程师的个人运维助理。当前是**本地可运行交付**：Next.js 工作台可以诊断、发起变更、批准/拒绝、模拟执行、回读、查看审计；支持最近会话、刷新恢复、停止等待和错误重试。**本轮不部署**（D9：暂不涉及），没有线上地址、邀请码和腾讯云服务端 API Key。

> 完整文件清单与交付说明见 [交付清单.md](交付清单.md)，逐文件大小见 [文件清单.txt](文件清单.txt)。

## 交付状态（阶段 5 收尾 · 已验收）

2026-11-09 产品经理验收通过；本轮结束。

- 访问地址：本地桌面 <http://localhost:3010/>；同一 Wi-Fi 手机 <http://192.168.1.64:3010/>。
- 登录：**无**（D5 本地单用户，不做邀请码/登录）。
- 线上资源：**无**。本轮不部署，没有云开发环境、服务名、服务端 API Key、邀请码或到期日；阶段 4 未执行。
- 更新方式：改代码后重启两个进程

  ```bash
  # 后端
  cd backend && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8020
  # 前端
  cd frontend && npm run dev
  ```

- 服务端 API Key：不涉及。后端只在本机 `backend/.env` 读模型 Key，不提交、不写日志；如 Key 曾泄露，请到模型控制台轮换。
- 交付范围：阶段 0–3（3-1 骨架、3-2 变更审批/审计、3-3 完整交互）；不做部署、多用户、真实设备执行。

## 当前能做什么

- 对话式只读诊断：资产/指标/告警/拓扑/runbook → 根因假设（置信度、证据、反证）、处置建议、不确定项；
- 工作台左侧示例、中间对话、右侧工具调用；结论详情可展开；
- 会话落 SQLite，刷新后可按 URL 恢复；
- 桌面 1280/1440、平板 768、手机 390 可用；手机侧栏为抽屉；
- 最近会话：左侧列表切换；刷新后消息和最近变更卡片恢复；
- 变更：计划卡片、批准/拒绝、执行/回读、模拟执行标识；
- 审计：proposed/approved/executing/executed/verified/rejected/denied 与哈希链校验。

## 启动（两个进程）

### 1. 后端（8020）

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # 填入 MODEL_API_KEY
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8020
```

### 2. 前端（3010）

```bash
cd frontend
cp .env.example .env.local    # BACKEND_URL=http://127.0.0.1:8020
npm install
npm run dev
```

浏览器打开 <http://localhost:3010/>。前端通过 `proxy.ts` 把 `/api/*` 同源转发到后端，浏览器不需要跨域。

> Key 只写进 `backend/.env`，不要发到对话里，也不要提交到仓库。`.env` / `.env.local` 已被忽略。

## 配置

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `MODEL_NAME` | `deepseek-chat` | DeepSeek 模型名（OpenAI 兼容接口） |
| `MODEL_BASE_URL` | `https://api.deepseek.com` | OpenAI 兼容接口 |
| `MODEL_API_KEY` | 空 | 必填；只在后端读取 |
| `BACKEND_URL` | `http://127.0.0.1:8020` | 前端代理目标（`frontend/.env.local`） |
| `MAX_TURNS` | 4 | Agent 最大轮数 |
| `READ_ONLY_MODE` | false | true 时所有写操作拒绝 |
| `POLICY_MODE` | approval | change_low/high 需审批 |
| `APPROVAL_TTL_MINUTES` | 15 | 审批有效期 |
| `FAST_MODE` | true | 先预取上下文，通常一次模型调用交卷 |
| `MONTHLY_BUDGET_CNY` | 50 | 演示期预算（记录用） |
| `BACKEND_PORT` | 8020 | 后端端口 |

## 验证

```bash
# 后端
cd backend && .venv/bin/python -m pytest -q          # 28 条

# 前端
cd frontend
npm run lint
npm run typecheck
npm test                                             # 12 条
npm run build

# 真实模型冒烟（后端链路）
backend/.venv/bin/python scripts/smoke.py --stage 阶段3-3
```

重启恢复检查由 `verify.sh` 调用 `scripts/restart-check.sh`。

## 目录

```text
frontend/
  app/                    /、/sessions/[id]、/audit
  components/layout/      AppHeader
  features/chat/          Workbench、AssessmentCard、ChangePlanCard、SessionList、Composer、SamplePanel、ToolCallList
  features/audit/         AuditView
  lib/api/                API 客户端与类型
  lib/status.ts           后端状态 → 前端统一状态
  proxy.ts                /api/* 同源转发
  tests/                  Vitest 配置
backend/app/              FastAPI、Agent、变更、审计（沿用阶段 2）
backend/tests/            pytest
scripts/                  restart-check.sh、smoke.py、eval_cases.py
docs/evidence/阶段3-3/    截图、照着做、是否表、冒烟记录、verify 输出
```

## 评测（阶段 2-3，保留回归）

```bash
backend/.venv/bin/python scripts/eval_cases.py
```

本次真实评测：Top-1 20/20、Top-3 20/20、证据 22/22、无数据 2/2、危险动作 0；112,252 tokens / 158.7s。

## 已知限制（本地交付）

- 停止只中止前端等待，后端模型调用可能继续完成；刷新可看最新结果；
- 没有 SSE，诊断需等待完整结果（6–10 秒）；
- 执行器是模拟的，不连接真实设备；
- 单用户本地，无登录（D5）；
- 工具调用卡片刷新后不保留；消息、结论和最近变更计划可恢复；
- 评测是合成用例，关键词打分只近似语义命中。
