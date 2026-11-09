export function formatSeconds(ms: number | undefined): string {
  if (!ms || ms < 0) return "0.0s";
  return `${(ms / 1000).toFixed(1)}s`;
}

export function formatTokens(n: number | undefined): string {
  if (!n) return "-";
  return new Intl.NumberFormat("zh-CN").format(n);
}

export function shortHash(hash: string | undefined): string {
  if (!hash) return "-";
  return hash.length > 14 ? `${hash.slice(0, 14)}…` : hash;
}

export function actionLabel(action: string): string {
  const map: Record<string, string> = {
    isolate_port: "隔离端口",
    restart_service: "重启服务",
    restart_host: "重启主机",
    power_off: "下电",
    config_change: "改配置",
  };
  return map[action] ?? action;
}
