# 公开展示页

纯静态页面：HTML + CSS + 原生 JS，本地 Mock 数据。

- 不连接任何 API、模型、数据库或真实设备；
- 不使用任何 Key；
- 交互演示（诊断 / 变更计划 / 批准 / 回读 / 审计）全部在浏览器内完成；
- 截图来自项目验收证据，指标来自本地真实评测。

本地预览：

```bash
python3 -m http.server 4173 -d showcase
# http://127.0.0.1:4173/
```

部署：推送到 `main` 后由 `.github/workflows/pages.yml` 发布到 GitHub Pages。
