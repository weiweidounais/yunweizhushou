/* 公开展示版：全部为本地 Mock 数据，不发起任何网络请求。 */
const CASES = {
  packet: {
    question: "core-sw-01 昨晚 22:00 开始丢包，什么原因？",
    summary: "Gi1/0/24 光模块 RX 功率劣化，导致端口抖动与 CRC 错包，进而丢包；设备 CPU 正常，排除整体过载。",
    impact: "下游 access-sw-02 方向业务可能出现丢包/瞬断；core-sw-01 本体未失联。",
    hypotheses: [
      { cause: "Gi1/0/24 光模块 RX 功率劣化", confidence: "high", evidence: ["ALM-1003：RX -12.8 dBm，低于 -8 dBm", "CRC 错包 2 小时 3→220", "22:00–23:00 端口 up/down 18 次"], falsification: "若更换光模块后 RX 回到 -8~-3 dBm 且 CRC 停止增长，则成立。" },
      { cause: "对端设备或跳线问题（推测）", confidence: "low", evidence: ["runbook rb-net-port-flap 要求排查对端端口状态与光模块", "当前无对端端口数据"], falsification: "查询对端 RX/TX 与错包计数即可排除。" },
      { cause: "设备整体资源过载导致端口异常（已排除）", confidence: "low", evidence: ["CPU 01:00–03:00 为 36/34/32%，低于 80% 正常上限"], falsification: "若 CPU/内存出现尖峰则需重新评估。" }
    ],
    recommendations: [
      { step: "批准并执行隔离 core-sw-01 Gi1/0/24（shutdown）", risk: "high", requires_change: true, rollback: "对 Gi1/0/24 执行 no shutdown 恢复" },
      { step: "更换 Gi1/0/24 光模块与跳线，清洁端面并核对 RX 回到 -8~-3 dBm", risk: "medium", requires_change: true, rollback: "换回原模块/跳线" },
      { step: "恢复端口后观察 30 分钟，确认 up/down 与 CRC 不再增长", risk: "medium" },
      { step: "补充查询对端（access-sw-02/storage-01）端口光功率与错包", risk: "low" }
    ],
    unknowns: ["Gi1/0/24 具体对端与承载业务未确认", "对端端口光功率与错包计数未采集", "该端口是否为堆叠/聚合成员，隔离是否触发链路切换未知"]
  },
  disk: {
    question: "db-prod-01 磁盘读延迟 240ms，数据库很慢，什么原因？",
    summary: "db-prod-01 数据盘出现读延迟升高与队列积压，指向磁盘坏块或 RAID 重建；连接数接近上限会放大影响，但更像结果而非根因。",
    impact: "订单库读写变慢；若继续恶化可能触发连接池耗尽。",
    hypotheses: [
      { cause: "数据盘坏块/RAID 重建导致读延迟", confidence: "high", evidence: ["ALM-2001：磁盘读延迟 240ms（阈值 50ms）", "iostat await 持续 >200ms，队列深度升高", "RAID 状态 degraded/rebuild"], falsification: "若更换磁盘并完成重建后延迟恢复，则成立。" },
      { cause: "连接数接近上限导致排队（推测）", confidence: "medium", evidence: ["连接数 92%，等待队列升高"], falsification: "若磁盘延迟恢复后连接数回落，则不是主因。" },
      { cause: "慢查询/批量任务放大 IO（已排除）", confidence: "low", evidence: ["慢查询日志无新增 Top SQL"], falsification: "对比业务高峰与 IO 峰值即可排除。" }
    ],
    recommendations: [
      { step: "确认 RAID 状态与坏盘位置，按预案更换故障盘", risk: "high", requires_change: true, rollback: "保留原盘，按厂商流程回插" },
      { step: "把只读流量切到备库，降低主库压力", risk: "medium", requires_change: true, rollback: "切回主库读流量" },
      { step: "扩容连接池前先确认磁盘恢复，避免掩盖 IO 问题", risk: "medium" },
      { step: "回读 await、队列深度、连接数三项指标", risk: "low" }
    ],
    unknowns: ["RAID 卡型号与当前重建进度", "备库延迟是否满足切读条件", "业务高峰剩余时间"]
  },
  hvac: {
    question: "hvac-01 回风温度 31°C，机房有风险吗？",
    summary: "hvac-01 回风温度 31°C 且压缩机高压告警，A 机房局部热风险升高；先切备用空调并确认冷通道温度，再决定是否降载。",
    impact: "A 机房部分机柜进风温度可能超过 27°C；持续升高会触发设备降频/保护。",
    hypotheses: [
      { cause: "压缩机高压/制冷能力下降导致回风温度升高", confidence: "high", evidence: ["ALM-3001：回风温度 31°C（阈值 27°C）", "压缩机高压告警持续 12 分钟", "A 机房冷通道温度 26.8°C"], falsification: "若切备用空调后回风降到 27°C 以下，则成立。" },
      { cause: "滤网堵塞导致风量不足（推测）", confidence: "medium", evidence: ["滤网压差高于基线", "未做现场检查"], falsification: "现场检查滤网/风机后排除。" },
      { cause: "机房负载突增（已排除）", confidence: "low", evidence: ["IT 负载 62%，较昨日无突增"], falsification: "对比负载曲线即可排除。" }
    ],
    recommendations: [
      { step: "切换备用空调，确认 A 机房冷通道温度回落", risk: "medium", requires_change: true, rollback: "切回原空调并保持备用机运行" },
      { step: "现场检查滤网、风机与压缩机高压保护", risk: "medium" },
      { step: "持续回读回风温度、冷通道温度和压缩机状态 30 分钟", risk: "low" },
      { step: "若温度继续上升，按预案对非关键负载降载", risk: "high", requires_change: true, rollback: "温度恢复后逐台恢复" }
    ],
    unknowns: ["备用空调当前是否可用", "A 机房机柜进风温度分布", "压缩机高压的具体故障码"]
  }
};

const CHANGE = {
  plan_id: "chg-demo-e1907ecb",
  asset_id: "core-sw-01",
  action: "isolate_port",
  params: { port: "Gi1/0/24", mode: "shutdown" },
  reason: "Gi1/0/24 光模块 RX 功率 -12.8 dBm，CRC 错包 2 小时 3→220，端口 up/down 18 次；隔离端口止损并更换光模块。",
  impact: "Gi1/0/24 承载业务中断；core-sw-01 为 P0 核心交换机，需确认下游冗余。",
  rollback: "对 Gi1/0/24 执行 no shutdown，核对端口 up 与 CRC 计数停止增长。",
  plan_hash: "e1907ecb1a83e82926d4e88413c62e4ecc802fc9f152a165c20d6955a7fe288e",
  audit: [
    ["22:01:02", "change.proposed", "core-sw-01", "ok", "—", "—"],
    ["22:02:10", "change.approved", "chg-demo-e1907ecb", "ok", "apr-demo-7a1", "—"],
    ["22:02:11", "change.executing", "chg-demo-e1907ecb", "ok", "apr-demo-7a1", "—"],
    ["22:02:12", "change.executed", "chg-demo-e1907ecb", "ok", "apr-demo-7a1", "—"],
    ["22:02:13", "change.verified", "chg-demo-e1907ecb", "verified", "apr-demo-7a1", "—"]
  ]
};

const $ = (selector) => document.querySelector(selector);
const messages = $("#messages");
const statusEl = $("#wb-status");
const toolsEl = $("#tools");
let activeCase = "";

function setStatus(text, cls = "") {
  statusEl.textContent = text;
  statusEl.className = `status ${cls}`.trim();
}

function clearMessages() {
  messages.innerHTML = "";
}

function addUser(text) {
  const el = document.createElement("div");
  el.className = "msg user";
  el.innerHTML = `<div class="bubble">${text}</div><span class="avatar">我</span>`;
  messages.appendChild(el);
}

function addAssistant(html) {
  const el = document.createElement("div");
  el.className = "msg assistant";
  el.innerHTML = `<span class="avatar">AI</span><div>${html}</div>`;
  messages.appendChild(el);
  messages.scrollTop = messages.scrollHeight;
  return el;
}

function addTyping() {
  return addAssistant(`<p class="lead-text muted">正在查指标、告警、拓扑和 runbook…</p>`);
}

function renderAssessment(c) {
  const hyps = c.hypotheses.map((h, i) => `
    <div class="hyp">
      <b>${i + 1}. ${h.cause}</b><span class="chip ${h.confidence}">${h.confidence === "high" ? "高" : h.confidence === "low" ? "低" : "中"}</span>
      <ul class="evidence">${h.evidence.map(e => `<li>${e}</li>`).join("")}</ul>
      <div class="evidence">反证/排除：${h.falsification}</div>
    </div>`).join("");
  const recs = c.recommendations.map((r, i) => `
    <div class="rec">
      <b>${i + 1}. ${r.step}</b><span class="chip">风险 ${r.risk === "high" ? "高" : r.risk === "medium" ? "中" : "低"}</span>
      ${r.requires_change ? '<span class="req">需审批后执行</span>' : ""}
      ${r.rollback ? `<div class="evidence">回滚：${r.rollback}</div>` : ""}
    </div>`).join("");
  return `
    <div class="assessment">
      <div class="block">
        <h4>结论</h4>
        <p>${c.summary}</p>
        <p class="muted">影响面：${c.impact}</p>
      </div>
      <details class="block">
        <summary>展开根因、证据与处置建议（${c.hypotheses.length} 条假设 / ${c.recommendations.length} 条建议）</summary>
        <h4>根因假设</h4>${hyps}
        <h4 style="margin-top:8px">处置建议</h4>${recs}
        <h4 style="margin-top:8px">不确定项 / 还需要的数据</h4>
        <ul class="evidence">${c.unknowns.map(u => `<li>${u}</li>`).join("")}</ul>
      </details>
    </div>`;
}

function renderPlan() {
  return `
    <div class="block plan">
      <div class="plan-head"><b>变更计划</b><span class="plan-status">待审批 · 模拟执行</span></div>
      <div class="plan-grid">
        <span>资产</span><b>${CHANGE.asset_id}</b>
        <span>动作</span><b>隔离端口 Gi1/0/24</b>
        <span>参数</span><b>${JSON.stringify(CHANGE.params)}</b>
        <span>plan_hash</span><b>${CHANGE.plan_hash.slice(0, 16)}…</b>
      </div>
      <p style="margin-top:6px"><b>理由：</b>${CHANGE.reason}</p>
      <p><b>影响：</b>${CHANGE.impact}</p>
      <p><b>回滚：</b>${CHANGE.rollback}</p>
      <div class="plan-actions">
        <button type="button" class="approve" id="approve-btn">批准</button>
        <button type="button" class="reject" id="reject-btn">拒绝</button>
      </div>
      <button type="button" class="audit-link" id="audit-link">查看审计记录</button>
    </div>`;
}

function setTools(items) {
  toolsEl.innerHTML = items.map(item => `<div class="tool"><code>${item}</code><span class="ok">ok</span></div>`).join("");
}

function runDiagnosis(key) {
  const c = CASES[key];
  if (!c) return;
  activeCase = key;
  document.querySelectorAll(".sample").forEach(b => b.classList.toggle("active", b.dataset.case === key));
  clearMessages();
  setStatus("诊断中", "busy");
  addUser(c.question);
  const typing = addTyping();
  setTools(["get_incident_context"]);
  setTimeout(() => {
    typing.remove();
    addAssistant(renderAssessment(c));
    setTools(["get_incident_context", "submit_assessment"]);
    setStatus("已完成", "done");
  }, 700);
}

function runChange() {
  activeCase = "change";
  document.querySelectorAll(".sample").forEach(b => b.classList.toggle("active", b.dataset.case === "change"));
  clearMessages();
  setStatus("待审批", "busy");
  addUser("帮我隔离 core-sw-01 的 Gi1/0/24 端口，理由：光模块劣化导致端口抖动");
  const typing = addTyping();
  setTools(["get_incident_context", "propose_change"]);
  setTimeout(() => {
    typing.remove();
    addAssistant(`<p class="lead-text">已生成变更计划，状态 <b>待审批</b>。批准后由确定性代码执行，不交给模型；参数与 plan_hash 绑定。</p>${renderPlan()}`);
    $("#approve-btn").addEventListener("click", approve);
    $("#reject-btn").addEventListener("click", reject);
    $("#audit-link").addEventListener("click", showAudit);
  }, 650);
}

function approve() {
  const plan = $(".plan");
  if (!plan) return;
  const btn = $("#approve-btn");
  if (btn) btn.disabled = true;
  const status = $(".plan-status");
  if (status) { status.textContent = "已批准 · 执行中"; status.className = "plan-status"; }
  setStatus("执行中", "busy");
  setTools(["execute_change", "verify_change"]);
  setTimeout(() => {
    if (status) { status.textContent = "已回读验证"; status.className = "plan-status ok"; }
    const actions = $(".plan-actions");
    if (actions) actions.remove();
    addAssistant(`
      <div class="result">
        <b>已执行并回读验证（模拟）</b>
        <p>执行：已隔离 core-sw-01 Gi1/0/24，业务按预案切至备用链路。</p>
        <p>回读：Gi1/0/24 down；备用链路正常；ALM-1001/1002/1003 转 cleared。</p>
        <ul><li>端口状态 down</li><li>备用链路流量正常</li><li>告警转 cleared</li></ul>
      </div>
      <p class="lead-text muted" style="margin-top:6px">审计记录已写入；点击变更卡片里的「查看审计记录」。</p>`);
    setStatus("已回读验证", "done");
    showAudit();
  }, 700);
}

function reject() {
  const status = $(".plan-status");
  if (status) { status.textContent = "已拒绝"; status.className = "plan-status"; }
  const actions = $(".plan-actions");
  if (actions) actions.innerHTML = '<span class="lead-text muted">已拒绝，不会执行。</span>';
  setStatus("已拒绝");
}

function showAudit() {
  const panel = $("#audit");
  panel.hidden = false;
  const body = $("#audit-body");
  body.innerHTML = CHANGE.audit.map(row => `
    <tr><td>${row[0]}</td><td>${row[1]}</td><td>${row[2]}</td><td>${row[3]}</td>
    <td>${CHANGE.plan_hash.slice(0, 12)}…</td><td>${row[4]}</td></tr>`).join("");
  panel.scrollIntoView({ behavior: "smooth", block: "start" });
}

document.querySelectorAll(".sample").forEach(btn => {
  btn.addEventListener("click", () => {
    const key = btn.dataset.case;
    if (key === "change") runChange();
    else runDiagnosis(key);
    $("#audit").hidden = true;
  });
});

window.addEventListener("load", () => {
  setTimeout(() => runDiagnosis("packet"), 650);
});
