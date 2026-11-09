---
id: rb-server-disk-latency
title: 服务器磁盘读延迟高 / RAID 降级
applies_to: [server]
symptoms: ["磁盘延迟高", "RAID 降级", "数据库慢查询", "IO wait 高"]
risk: high
requires_change: true
owner: dba-team
version: 2
reviewed_at: 2026-10-10
---

## 现象

数据盘读延迟显著升高，RAID 状态 degraded，数据库出现慢查询或连接堆积。

## 排查步骤

1. 查 RAID 控制器状态与物理盘健康（SMART、离线盘位置）。
2. 查磁盘延迟、IOPS、队列深度与 IO wait。
3. 查数据库慢查询与连接数，确认是否由 IO 引起。
4. 确认是否有备份/重建任务在跑。

## 处置

1. RAID 降级时优先更换离线盘，避免二次故障。
2. 若延迟影响业务，先把读流量切到备库或只读副本。
3. 重建期间限制高 IO 任务，观察重建进度。
4. 变更/换盘需审批，执行后回读 RAID 状态与延迟。

## 回滚

- 换盘失败：保留旧盘，按厂商流程回装；回装前确认数据一致性。
- 切备库：确认主库恢复后切回，切回前校验复制延迟。

## 风险与注意事项

- 禁止在 RAID 重建中拔第二块盘。
- 数据库主库重启/下电属于 forbidden，必须人工升级审批。
