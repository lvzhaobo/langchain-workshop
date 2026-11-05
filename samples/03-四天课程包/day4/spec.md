# Spec：5G 基站设备智能检测 Agent

> 版本 v1.0 · SDD（Spec-Driven Development）示范

## 验收标准（10 条）

1. Agent 能通过 `/agent/single` 接口接收用户问题并返回分析结果
2. Agent 能调用 `query_device` 工具查询设备详情，返回厂商/型号/站点/状态
3. Agent 能调用 `query_alarms` 工具查询告警列表
4. 当设备无告警时，Agent 应报告"设备运行正常"
5. 当设备有 P0 告警时，Agent 应建议立即处理
6. Agent 分析结果应包含：设备状态摘要 + 告警分析 + 建议操作
7. 接口响应格式为 SSE 流式：`data: {"content": "..."}` → `data: [DONE]`
8. Agent 响应时间 < 10 秒（包含 LLM 推理 + 工具调用）
9. 输入不存在的设备 ID 时，应返回"设备不存在"而非抛出异常
10. 接口须支持 CORS，可从任意前端页面调用

## 接口契约

```
POST /agent/single
Content-Type: application/json

Request:
{
  "question": "查 DEV-0001 的状态和告警",
  "thread_id": "optional-session-id"
}

Response (SSE):
data: {"content": "设备 DEV-0001..."}
data: {"content": "..."}
data: [DONE]
```

## 工具契约

| 工具 | 参数 | 返回 |
|------|------|------|
| query_device | device_id: str | "{vendor} {model}，站点{site}，状态{status}" |
| query_alarms | device_id: str | "{device_id}: 告警列表" 或 "当前无告警" |
