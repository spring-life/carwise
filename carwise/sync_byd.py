"""Create a dated catalog snapshot from selected official BYD product pages."""

import argparse
from datetime import date
import json

import httpx

from .config import Settings
from .models import VehicleVariant


MODELS = (
    (148, "qin-l-dm-i", "DM-i 插电混动"),
    (152, "qin-plus-dm-i", "DM-i 插电混动"),
    (150, "song-l-dm-i", "DM-i 插电混动"),
    (10041, "haishi-06-ev", "纯电"),
    (10051, "haishi-06-dm-i", "DM-i 插电混动"),
    (10050, "haiou", "纯电"),
    (10043, "haibao-06-dm-i-wagon", "DM-i 插电混动"),
    (10038, "haibao-07-dm-i", "DM-i 插电混动"),
    (10044, "haibao-06-gt", "纯电"),
    (151, "xia", "DM-i 插电混动"),
)

FEATURES = (
    "CLTC纯电续驶里程（km）",
    "电池容量（kWh）",
    "电机最大功率（kW）",
    "轮胎规格",
    "高快领航辅助（HNOA）",
    "云辇-C智能阻尼车身控制系统",
    "前排座椅通风加热",
    "15.6英寸中控屏",
)


def fetch_parameter_table(goods_id: int, browser) -> dict[str, dict[str, str]]:
    page = browser.new_page()
    try:
        with page.expect_response(lambda response: "goodsParams" in response.url, timeout=30000) as captured:
            page.goto(
                f"https://www.byd.com/cn/parameter-comparison?goodsId={goods_id}",
                wait_until="domcontentloaded", timeout=30000,
            )
        payload = captured.value.json()
        if not payload.get("success"):
            raise RuntimeError(f"Official parameter table failed for goodsId={goods_id}")
        sections = payload["data"]["configs"]
        trim_row = next(row for row in sections[0]["value"] if row["name"] == "车型")
        trims = trim_row["value"]
        result: dict[str, dict[str, str]] = {trim: {} for trim in trims if trim}
        for section in sections:
            for row in section["value"]:
                if row["name"] not in FEATURES and row["name"] != "NEDC亏电油耗（L/100km）":
                    continue
                for index, trim in enumerate(trims):
                    if trim and index < len(row["value"]):
                        value = str(row["value"][index]).strip()
                        if value:
                            result[trim][row["name"]] = {"●": "有", "—": "无", "○": "可选装"}.get(value, value)
        return result
    finally:
        page.close()


def fetch_catalog(as_of: date, with_features: bool = False) -> list[VehicleVariant]:
    variants: list[VehicleVariant] = []
    browser = None
    playwright = None
    if with_features:
        from playwright.sync_api import sync_playwright

        playwright = sync_playwright().start()
        try:
            browser = playwright.chromium.launch(channel="msedge", headless=True)
        except Exception as exc:
            playwright.stop()
            raise RuntimeError("Microsoft Edge is required to refresh BYD configuration fields") from exc
    try:
        with httpx.Client(timeout=30, headers={"Referer": "https://www.byd.com/"}) as client:
            listing_response = client.get("https://cms-api.byd.com/car/byd/cn/goodsListForSearch")
            listing_response.raise_for_status()
            listings = {int(item["id"]): item for item in listing_response.json()["data"]}
            for goods_id, slug, powertrain in MODELS:
                listing = listings.get(goods_id)
                if not listing or not listing["name"].startswith("2026款"):
                    raise RuntimeError(f"Official 2026 model identity changed for goodsId={goods_id}")
                model_name = listing["name"][5:]
                parameters = fetch_parameter_table(goods_id, browser) if browser else {}
                response = client.get(
                    "https://cms-api.byd.com/car/byd/cn/getGoodsAttrListForCompareByGoodsId",
                    params={"goodsId": goods_id},
                )
                response.raise_for_status()
                payload = response.json()
                if payload.get("code") != 0 or not isinstance(payload.get("data"), list):
                    raise RuntimeError(f"Official variant response changed for goodsId={goods_id}")
                source = {
                    "title": f"比亚迪官网：{listing['name']} 参数对比",
                    "url": f"https://www.byd.com/cn/parameter-comparison?goodsId={goods_id}",
                    "observed_on": as_of.isoformat(),
                }
                model_variants = 0
                for item in payload["data"]:
                    if item.get("type") != "车型" or item.get("price") is None:
                        continue
                    trim = item["name"].strip()
                    features = parameters.get(trim, {}).copy()
                    fuel = features.pop("NEDC亏电油耗（L/100km）", None)
                    variant = VehicleVariant.model_validate({
                        "id": f"byd-2026-{slug}-{item['attrId']}",
                        "market": "中国大陆",
                        "make": "比亚迪",
                        "model": model_name,
                        "year": 2026,
                        "trim": trim,
                        "image_url": listing.get("img"),
                        "powertrain": powertrain,
                        "msrp": round(item["price"]),
                        "currency": "CNY",
                        "fuel_consumption": float(fuel) if fuel else None,
                        "fuel_unit": "L/100km" if fuel else None,
                        "fuel_standard": "NEDC 亏电油耗" if fuel else None,
                        "features": features,
                        "sources": {"specs": source, "price": source, **({"fuel": source} if fuel else {})},
                    })
                    variants.append(variant)
                    model_variants += 1
                if not model_variants:
                    raise RuntimeError(f"No priced variants returned for {listing['name']}")
                print(f"{listing['name']}: {model_variants} variants")
    finally:
        if browser:
            browser.close()
        if playwright:
            playwright.stop()
    return variants


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync verified BYD variants and MSRP snapshot")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--with-features", action="store_true", help="Read the official parameter table through Edge")
    args = parser.parse_args()
    variants = fetch_catalog(args.as_of, args.with_features)
    output = Settings().data_dir / "catalog.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps([variant.model_dump(mode="json") for variant in variants], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Saved {len(variants)} official variants to {output}")


if __name__ == "__main__":
    main()
