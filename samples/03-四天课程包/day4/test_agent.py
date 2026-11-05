"""Day4 测试用例 — pytest 验证 Agent 接口是否符合 Spec

运行: pytest test_agent.py -v
"""
import json
import pytest
import requests

BASE_URL = "http://localhost:8100"


def call_agent(question: str) -> str:
    """调用 Agent 接口，收集完整响应"""
    resp = requests.post(f"{BASE_URL}/agent/single",
        json={"question": question}, stream=True)
    result = ""
    for line in resp.iter_lines(decode_unicode=True):
        if line and line.startswith("data: ") and line != "data: [DONE]":
            result += json.loads(line[6:])["content"]
    return result


# ═══ 对照 Spec 的 10 条验收标准 ═══

@pytest.mark.parametrize("device_id,expected", [
    ("DEV-0001", "诺基亚"),  # Spec #2: 查询设备详情
    ("DEV-0002", "华为"),
])
def test_query_device_returns_vendor(device_id, expected):
    """Spec #2: Agent 能查询设备详情，返回厂商信息"""
    result = call_agent(f"查 {device_id} 的状态")
    assert expected in result, f"期望包含 '{expected}'，实际: {result[:100]}"


def test_no_alarm_device_returns_normal():
    """Spec #4: 无告警设备应报告正常"""
    result = call_agent("查 DEV-0001 的告警")
    assert "无告警" in result or "正常" in result or "running" in result.lower(), \
        f"无告警设备应报告正常，实际: {result[:100]}"


def test_response_format_sse():
    """Spec #7: 接口响应格式为 SSE 流式"""
    resp = requests.post(f"{BASE_URL}/agent/single",
        json={"question": "DEV-0001 状态"}, stream=True)
    first_line = next(resp.iter_lines(decode_unicode=True))
    assert first_line.startswith("data: "), f"首行应为 SSE 格式，实际: {first_line[:50]}"


def test_response_time():
    """Spec #8: Agent 响应时间 < 10 秒"""
    import time
    start = time.time()
    call_agent("查 DEV-0001 的状态")
    elapsed = time.time() - start
    assert elapsed < 10, f"响应时间 {elapsed:.1f}s 超过 10s 限制"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
