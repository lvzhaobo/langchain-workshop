"""生成 data/objects.json —— 5G 基站参考数据（50 条）

换场景时：改这个脚本或直接让 AI 按同样字段生成你自己场景的数据。
字段约定（通用模板）：
    id        对象唯一标识，如 OBJ-0001
    name      对象名称
    category  类别
    status    normal / warning / fault
    metrics   关键指标（dict，场景自定义）
    events    异常/事件列表 [{event_id, level, type, description, time}]

运行：python scripts/gen_data.py
"""
import json
import random
from pathlib import Path
from typing import Any

random.seed(42)

VENDORS = ["华为", "中兴", "爱立信", "诺基亚"]
MODELS = {
    "华为": ["AAU5613", "AAU5313", "BBU5900"],
    "中兴": ["A9611", "V9200", "IT BBU"],
    "爱立信": ["AIR 3268", "AIR 6449", "Baseband 6630"],
    "诺基亚": ["AirScale 64T64R", "AirFrame 16", "AirScale BBU"],
}
SITES = [
    "北京市朝阳区望京SOHO", "北京市海淀区中关村软件园", "上海市浦东新区张江高科",
    "深圳市南山区科技园", "广州市天河区珠江新城", "杭州市余杭区未来科技城",
    "成都市高新区天府软件园", "武汉市洪山区光谷广场", "南京市江宁区九龙湖",
    "西安市雁塔区高新路",
]
EVENT_TYPES = [
    ("P0", "光模块故障", "收光功率低于 -30dBm，链路中断"),
    ("P1", "光模块功率异常", "收光功率 -28.5dBm，低于告警门限"),
    ("P1", "驻波比告警", "天线驻波比 2.8，超过 2.5 门限"),
    ("P2", "温度过高", "设备温度 52°C，接近上限 55°C"),
    ("P2", "CPU 占用高", "CPU 持续 5 分钟超过 85%"),
    ("P3", "时钟源切换", "GPS 时钟失锁，切换至地面时钟"),
]


def make_object(i: int) -> dict[str, Any]:
    vendor = random.choice(VENDORS)
    # 约 60% 正常 / 25% 告警 / 15% 故障
    status = random.choices(["normal", "warning", "fault"], weights=[60, 25, 15])[0]
    events = []
    if status != "normal":
        n = random.randint(1, 3) if status == "warning" else random.randint(2, 4)
        picked = random.sample(EVENT_TYPES, min(n, len(EVENT_TYPES)))
        if status == "fault" and picked[0][0] != "P0":
            picked[0] = EVENT_TYPES[0]
        for j, (level, etype, desc) in enumerate(picked):
            events.append({
                "event_id": f"EVT-{i:04d}-{j+1}",
                "level": level,
                "type": etype,
                "description": desc,
                "time": f"2026-07-{random.randint(20, 26):02d} {random.randint(0, 23):02d}:{random.randint(0, 59):02d}",
            })
    return {
        "id": f"OBJ-{i:04d}",
        "name": f"{random.choice(SITES)[:9]}-基站{i:02d}",
        "category": "5G基站-射频",
        "vendor": vendor,
        "model": random.choice(MODELS[vendor]),
        "site": random.choice(SITES),
        "status": status,
        "metrics": {
            "rx_power_dbm": round(random.uniform(-30, -18), 1),
            "temperature_c": random.randint(28, 54),
            "cpu_percent": random.randint(15, 92),
            "vswr": round(random.uniform(1.1, 2.9), 1),
        },
        "events": events,
    }


if __name__ == "__main__":
    objects = [make_object(i) for i in range(1, 51)]
    out = Path(__file__).parent.parent / "data" / "objects.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(objects, ensure_ascii=False, indent=2), encoding="utf-8")
    stats = {s: sum(1 for o in objects if o["status"] == s) for s in ["normal", "warning", "fault"]}
    print(f"已生成 {len(objects)} 条 → {out}")
    print(f"状态分布: {stats}")
