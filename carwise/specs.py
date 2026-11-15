import re
from collections.abc import Callable

from .models import AskResponse, Citation, VehicleVariant


ENGINE_FIELDS = (
    ("发动机型号", ("型号",)),
    ("发动机型式", ("型式", "形式")),
    ("排量（L）", ("排量",)),
    ("发动机最大功率（kW）", ("功率",)),
    ("发动机最大扭矩（N·m）", ("扭矩",)),
)


def _catalog_answer(
    vehicles: list[VehicleVariant],
    source_key: str,
    rows_for: Callable[[VehicleVariant], list[tuple[str, str]]],
) -> AskResponse | None:
    answers: list[str] = []
    citations: list[Citation] = []
    missing: list[str] = []
    for vehicle in vehicles:
        fields = rows_for(vehicle)
        source = vehicle.sources.get(source_key)
        if not fields or source is None:
            missing.append(vehicle.label)
            continue
        rows = [f"{key}：{value}" for key, value in fields]
        answers.append(f"{vehicle.label}（官网参数记录于 {source.observed_on}）：\n" + "\n".join(rows))
        citations.append(Citation(
            id=f"S{len(citations) + 1}",
            document_id=f"catalog-{vehicle.id}",
            title=source.title,
            url=source.url,
            source_type="official",
            published_on=source.observed_on,
            location=vehicle.trim,
            excerpt="\n".join(rows),
        ))
    if missing:
        answers.append("以下配置的官网快照未收录所问字段：" + "、".join(missing))
    if not citations:
        return None
    return AskResponse(answer="\n\n".join(answers), citations=citations, mode="catalog")


def engine_specs_answer(question: str, vehicles: list[VehicleVariant]) -> AskResponse | None:
    if "发动机" not in question or any(term in question for term in ("故障", "保养", "机油")):
        return None
    if not any(term in question for term in ("规格", "参数", "配置", "型号", "型式", "形式", "排量", "功率", "扭矩", "怎么样")):
        return None
    broad = any(term in question for term in ("规格", "参数", "配置", "怎么样"))
    requested = [key for key, aliases in ENGINE_FIELDS if broad or any(alias in question for alias in aliases)]
    return _catalog_answer(vehicles, "specs", lambda vehicle: [
        (key, str(vehicle.features[key])) for key in requested if vehicle.features.get(key) not in (None, "")
    ])


def catalog_question_answer(question: str, vehicles: list[VehicleVariant]) -> AskResponse | None:
    normalized = re.sub(r"[\s？?。！!]", "", question)
    if normalized in ("这款车怎么样", "这个车怎么样", "该车怎么样", "它怎么样", "这个车整体好不好", "这款车整体好不好", "这款车值得买吗", "这个车值得买吗"):
        return AskResponse(
            answer=f"你想了解 {vehicles[0].model} 的价格配置、动力能耗、保养要求，还是故障处理？请选择一个方向继续问。",
            citations=[], mode="clarification",
        )
    engine = engine_specs_answer(question, vehicles)
    if engine is not None:
        return engine
    if "发动机" in question:
        return None
    if "动力" in question and any(term in question for term in ("参数", "规格", "配置", "数据")):
        keys = [key for key, _ in ENGINE_FIELDS] + ["电机最大功率（kW）", "电池容量（kWh）", "CLTC纯电续驶里程（km）"]
        def power_rows(vehicle: VehicleVariant) -> list[tuple[str, str]]:
            rows = [(key, str(vehicle.features[key])) for key in keys if vehicle.features.get(key) not in (None, "")]
            return ([("动力类型", vehicle.powertrain)] if vehicle.powertrain and rows else []) + rows
        return _catalog_answer(vehicles, "specs", power_rows)
    if any(term in question for term in ("官方指导价", "指导价", "售价", "多少钱", "价格")) and not any(term in question for term in ("实际", "成交", "落地")):
        return _catalog_answer(vehicles, "price", lambda vehicle: [
            ("官方指导价", f"¥{vehicle.msrp:,}")
        ] if vehicle.msrp is not None else [])
    if "轮胎" in question and any(term in question for term in ("规格", "尺寸", "多大", "型号")):
        return _catalog_answer(vehicles, "specs", lambda vehicle: [
            ("轮胎规格", str(vehicle.features["轮胎规格"]))
        ] if vehicle.features.get("轮胎规格") else [])
    if "电池" in question and any(term in question for term in ("容量", "多大", "多少度")):
        return _catalog_answer(vehicles, "specs", lambda vehicle: [
            ("电池容量（kWh）", str(vehicle.features["电池容量（kWh）"]))
        ] if vehicle.features.get("电池容量（kWh）") else [])
    if "油耗" in question and not any(term in question for term in ("真实", "实测", "实际", "车主", "道路")):
        return _catalog_answer(vehicles, "fuel", lambda vehicle: [
            (f"{vehicle.fuel_standard}（{vehicle.fuel_unit}）", str(vehicle.fuel_consumption))
        ] if vehicle.fuel_consumption is not None else [])
    if any(term in question for term in ("纯电续航", "纯电续驶里程")) and not any(term in question for term in ("真实", "实测", "实际", "道路")):
        return _catalog_answer(vehicles, "specs", lambda vehicle: [
            ("CLTC纯电续驶里程（km）", str(vehicle.features["CLTC纯电续驶里程（km）"]))
        ] if vehicle.features.get("CLTC纯电续驶里程（km）") else [])
    if "座椅" in question and any(term in question for term in ("通风", "加热")):
        return _catalog_answer(vehicles, "specs", lambda vehicle: [
            ("前排座椅通风加热", str(vehicle.features["前排座椅通风加热"]))
        ] if "前排座椅通风加热" in vehicle.features else [])
    return None
