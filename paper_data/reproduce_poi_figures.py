"""Reproduce the POI data cleaning and paper figures from one file.

This script is intentionally standalone. It does not import the old ``scripts/``
pipeline, so a reviewer can run only this file plus the uploaded CSV/data.

Typical use:

    python paper_data/reproduce_poi_figures.py --use-existing
    python paper_data/reproduce_poi_figures.py --collect

Outputs:

    paper_data/data/amap_poi_raw.csv              (when --collect is used)
    paper_data/data/poi_classification_audit.csv
    paper_data/data/poi_spatial.csv
    figures/poi_distance_distribution.png
    figures/poi_distance_distribution_polycentric.png
    figures/category_distance_comparison.png
    figures/poi_scatter_map.png
    figures/category_by_zone.png
    figures/category_by_nearest_center_zone.png
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
THIS_FILE = Path(__file__).resolve()
PAPER_DATA = THIS_FILE.parent
ROOT = PAPER_DATA.parent
DATA_DIR = PAPER_DATA / "data"
FIGURES_DIR = ROOT / "figures"


# ---------------------------------------------------------------------------
# AMAP collection settings
# ---------------------------------------------------------------------------
AMAP_TEXT_URL = "https://restapi.amap.com/v3/place/text"
DEFAULT_PAGE_SIZE = 25
DEFAULT_MAX_PAGES = 100
DEFAULT_SLEEP_S = 0.3
DEFAULT_TIMEOUT_S = 20

KEYWORDS = [
    "工厂", "制造", "加工", "机械厂", "电子厂", "印刷厂", "包装厂",
    "样衣", "打版", "服装设计", "研发中心", "实验室", "试制", "3D打印",
    "中央厨房", "烘焙工厂", "食品加工",
    "产业园", "工业园", "科技园", "创意园", "孵化器",
]

DISTRICTS = [
    "黄浦区", "徐汇区", "长宁区", "静安区", "普陀区", "虹口区", "杨浦区",
    "浦东新区", "闵行区", "宝山区", "嘉定区", "松江区", "青浦区",
    "奉贤区", "金山区", "崇明区",
]

RAW_COLUMNS = [
    "query_keyword", "query_city", "id", "name", "type", "typecode",
    "address", "location", "pname", "cityname", "adname", "adcode",
    "gridcode", "tel",
]


# ---------------------------------------------------------------------------
# Spatial definitions
# ---------------------------------------------------------------------------
PEOPLE_SQUARE_LON = 121.4737
PEOPLE_SQUARE_LAT = 31.2304
SHANGHAI_BBOX = (120.85, 30.67, 122.25, 31.90)
LON_RANGE = (119.0, 123.0)
LAT_RANGE = (30.0, 32.5)

INNER_MAX_KM = 8.0
MIDDLE_MAX_KM = 18.0
ZONE_ORDER = ["inner_center", "middle", "outer"]
ZONE_LABELS_ZH = {
    "inner_center": "近距组 (0-8km)",
    "middle": "中距组 (8-18km)",
    "outer": "远距组 (>18km)",
}

POLYCENTRIC_CENTERS = {
    "central_core": (121.4878, 31.2364),
    "xujiahui": (121.4368, 31.1885),
    "wujiaochang": (121.5147, 31.3039),
    "zhangjiang": (121.5876, 31.2034),
    "hongqiao": (121.3205, 31.1949),
    "qiantan": (121.4732, 31.1524),
}
CENTER_LABELS_ZH = {
    "central_core": "人民广场-外滩-陆家嘴核心区",
    "xujiahui": "徐家汇",
    "wujiaochang": "五角场",
    "zhangjiang": "张江",
    "hongqiao": "虹桥",
    "qiantan": "前滩",
}
NEAREST_CENTER_INNER_MAX_KM = 3.0
NEAREST_CENTER_MIDDLE_MAX_KM = 8.0
NEAREST_CENTER_ZONE_ORDER = ["near_center", "center_influence", "far_from_centers"]
NEAREST_CENTER_ZONE_LABELS_ZH = {
    "near_center": "近距组 (0-3km)",
    "center_influence": "中距组 (3-8km)",
    "far_from_centers": "远距组 (>8km)",
}
POLYCENTRIC_DECAY_KM = 6.0


# ---------------------------------------------------------------------------
# Classification rules
# ---------------------------------------------------------------------------
CATEGORIES = [
    "traditional_factory",
    "urban_production",
    "food_city_production",
    "industrial_space",
    "ambiguous",
]
CATEGORY_LABELS_ZH = {
    "traditional_factory": "传统制造",
    "urban_production": "城市型生产",
    "food_city_production": "城市食品生产",
    "industrial_space": "产业/园区空间",
    "ambiguous": "难以分类",
}
CATEGORY_COLORS = {
    "traditional_factory": "#9e2a2b",
    "urban_production": "#2a6f97",
    "food_city_production": "#e09f3e",
    "industrial_space": "#52796f",
    "ambiguous": "#8d99ae",
}

FALSE_POSITIVE_KEYWORDS = [
    "工厂店", "工厂直销店", "工厂风", "工厂主题",
    "折扣店", "奥特莱斯", "outlets", "专卖店", "体验店", "旗舰店",
    "餐厅", "餐饮", "咖啡", "酒吧", "奶茶", "火锅", "烧烤", "小吃",
    "面馆", "甜品", "酒店", "宾馆", "KTV", "网咖", "美发", "理发",
    "健身", "超市", "便利店", "菜场", "菜市场",
]
PRODUCTION_OVERRIDE_KEYWORDS = [
    "中央厨房", "烘焙工厂", "食品加工", "食品厂", "净菜", "预制菜", "中央工厂",
]
FOOD_KEYWORDS = [
    "中央厨房", "烘焙工厂", "食品加工", "食品厂", "净菜", "预制菜",
    "中央工厂", "冷链", "糕点厂", "乳品", "肉类加工", "水产加工", "饮料厂",
]
URBAN_PRODUCTION_KEYWORDS = [
    "样衣", "打版", "打样", "服装设计", "设计打样", "设计制造",
    "3d打印", "3D打印", "增材制造", "快速成型", "原型", "手板",
    "研发试制", "试制", "中试", "小批量", "定制生产", "研发中心",
    "研发实验室", "试制实验室", "工程实验室", "设计中心",
]
INDUSTRIAL_SPACE_KEYWORDS = [
    "产业园", "工业园", "科技园", "创意园", "孵化器", "软件园",
    "文创园", "众创空间", "加速器", "科技城", "产业基地", "创业园",
    "园区",
]
TRADITIONAL_FACTORY_KEYWORDS = [
    "机械厂", "化工厂", "化工", "金属制品", "金属", "印刷厂", "印刷",
    "包装厂", "包装", "电子厂", "电子装配", "装配厂", "铸造", "锻造",
    "纺织厂", "钢铁", "水泥", "塑料厂", "橡胶", "五金", "机床",
    "制造厂", "加工厂", "制造", "加工", "工厂",
]
AMBIGUOUS_OVERRIDE_KEYWORDS = ["创意工厂", "梦工厂", "梦想工厂"]
LAB_KEYWORD = "实验室"


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
def banner(title: str) -> None:
    line = "=" * 72
    print(f"\n{line}\n{title}\n{line}")


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            out[key.strip()] = val.strip().strip('"').strip("'")
    return out


def get_amap_key(env_path: Path, explicit_key: str | None = None) -> str | None:
    key = explicit_key or os.environ.get("AMAP_KEY") or load_env(env_path).get("AMAP_KEY")
    if not key:
        return None
    key = key.strip()
    if key.lower().startswith("replace_with") or key.lower() in {"your_key_here", "your_amap_web_service_key"}:
        return None
    return key


def in_shanghai_bbox(lon: float, lat: float) -> bool:
    lon_min, lat_min, lon_max, lat_max = SHANGHAI_BBOX
    return lon_min <= lon <= lon_max and lat_min <= lat <= lat_max


def haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def classify_zone(distance_km: float) -> str:
    if pd.isna(distance_km):
        return "unknown"
    if distance_km <= INNER_MAX_KM:
        return "inner_center"
    if distance_km <= MIDDLE_MAX_KM:
        return "middle"
    return "outer"


def classify_nearest_center_zone(distance_km: float) -> str:
    if pd.isna(distance_km):
        return "unknown"
    if distance_km <= NEAREST_CENTER_INNER_MAX_KM:
        return "near_center"
    if distance_km <= NEAREST_CENTER_MIDDLE_MAX_KM:
        return "center_influence"
    return "far_from_centers"


def setup_matplotlib():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    preferred = [
        "Microsoft YaHei", "SimHei", "DengXian", "Microsoft JhengHei",
        "SimSun", "Noto Sans CJK SC", "Source Han Sans SC", "Arial Unicode MS",
    ]
    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = [name for name in preferred if name in available] or ["DejaVu Sans"]
    plt.rcParams.update({
        "font.sans-serif": chosen + plt.rcParams.get("font.sans-serif", []),
        "font.family": "sans-serif",
        "axes.unicode_minus": False,
        "figure.dpi": 120,
        "savefig.dpi": 160,
        "savefig.bbox": "tight",
        "axes.grid": True,
        "grid.alpha": 0.3,
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
    })
    return plt


# ---------------------------------------------------------------------------
# AMAP collection
# ---------------------------------------------------------------------------
def http_get_json(url: str, params: dict, timeout: int) -> dict:
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{query}", headers={"User-Agent": "poi-paper-review/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        charset = resp.headers.get_content_charset() or "utf-8"
        return json.loads(resp.read().decode(charset, errors="replace"))


def fetch_page(key: str, keyword: str, city: str, page: int, page_size: int,
               citylimit: bool, timeout: int) -> list[dict]:
    params = {
        "key": key,
        "keywords": keyword,
        "city": city,
        "citylimit": "true" if citylimit else "false",
        "offset": page_size,
        "page": page,
        "output": "JSON",
    }
    data = http_get_json(AMAP_TEXT_URL, params, timeout)
    if str(data.get("status", "0")) != "1":
        info = data.get("info", "unknown")
        infocode = data.get("infocode", "")
        raise RuntimeError(f"AMAP error infocode={infocode}: {info}")
    pois = data.get("pois", []) or []
    return pois if isinstance(pois, list) else []


def poi_uid(poi: dict) -> str:
    pid = str(poi.get("id", "")).strip()
    if pid:
        return f"id:{pid}"
    return f"nl:{poi.get('name', '')}|{poi.get('location', '')}"


def collect_amap(key: str, city: str, keywords: list[str], districts: list[str],
                 max_pages: int, sleep_s: float, page_size: int, timeout: int,
                 limit_total: int | None, citylimit: bool) -> pd.DataFrame:
    search_cities = districts or [city]
    seen: set[str] = set()
    rows: list[dict] = []

    for q_city in search_cities:
        for kw in keywords:
            added = 0
            for page in range(1, max_pages + 1):
                pois = fetch_page(key, kw, q_city, page, page_size, citylimit, timeout)
                if not pois:
                    break
                new_this_page = 0
                for poi in pois:
                    uid = poi_uid(poi)
                    if uid in seen:
                        continue
                    seen.add(uid)
                    new_this_page += 1
                    added += 1
                    row = {col: "" for col in RAW_COLUMNS}
                    row.update({
                        "query_keyword": kw,
                        "query_city": q_city,
                        "id": poi.get("id", ""),
                        "name": poi.get("name", ""),
                        "type": poi.get("type", ""),
                        "typecode": poi.get("typecode", ""),
                        "address": poi.get("address", "") if isinstance(poi.get("address"), str) else "",
                        "location": poi.get("location", "") if isinstance(poi.get("location"), str) else "",
                        "pname": poi.get("pname", ""),
                        "cityname": poi.get("cityname", ""),
                        "adname": poi.get("adname", ""),
                        "adcode": poi.get("adcode", ""),
                        "gridcode": poi.get("gridcode", ""),
                        "tel": poi.get("tel", "") if isinstance(poi.get("tel"), str) else "",
                    })
                    rows.append(row)
                    if limit_total and len(rows) >= limit_total:
                        print(f"达到 --limit-total={limit_total}，停止采集。")
                        return pd.DataFrame(rows, columns=RAW_COLUMNS)
                if len(pois) < page_size or new_this_page == 0:
                    break
                time.sleep(max(sleep_s, 0.2))
            prefix = f"[{q_city}] " if districts else ""
            print(f"  {prefix}{kw}: 新增 {added} 条")
            time.sleep(max(sleep_s, 0.2))
    return pd.DataFrame(rows, columns=RAW_COLUMNS)


# ---------------------------------------------------------------------------
# Cleaning and classification
# ---------------------------------------------------------------------------
def normalize_raw(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=["name", "address", "lon", "lat", "raw_keyword", "raw_type", "source"])
    raw = raw.copy()
    for col in RAW_COLUMNS:
        if col not in raw.columns:
            raw[col] = ""
    loc = raw["location"].astype(str).str.split(",", n=1, expand=True)
    lon = pd.to_numeric(loc[0], errors="coerce")
    lat = pd.to_numeric(loc[1] if loc.shape[1] > 1 else None, errors="coerce")
    out = pd.DataFrame({
        "name": raw["name"].astype(str).str.strip(),
        "address": raw["address"].astype(str).where(
            raw["address"].astype(str).str.strip() != "", raw["adname"].astype(str)
        ).str.strip(),
        "lon": lon,
        "lat": lat,
        "raw_keyword": raw["query_keyword"].astype(str).str.strip(),
        "raw_type": raw["type"].astype(str).str.strip(),
        "source": "amap",
    })
    out = out.dropna(subset=["lon", "lat"])
    out = out[out.apply(lambda r: in_shanghai_bbox(float(r["lon"]), float(r["lat"])), axis=1)]
    return out.reset_index(drop=True)


def first_hit(text: str, keywords: list[str]) -> str | None:
    low = text.lower()
    for kw in keywords:
        if kw.lower() in low:
            return kw
    return None


def is_false_positive(text: str) -> tuple[bool, str]:
    if first_hit(text, PRODUCTION_OVERRIDE_KEYWORDS):
        return False, ""
    hit = first_hit(text, FALSE_POSITIVE_KEYWORDS)
    if hit:
        return True, f"命中误判关键词「{hit}」(疑似消费/零售场所，非生产活动)"
    return False, ""


def classify_poi(name: str, raw_keyword: str, raw_type: str, address: str) -> tuple[str, str]:
    text = " ".join(str(x) for x in [name, raw_keyword, raw_type, address] if str(x) and str(x) != "nan")

    hit = first_hit(text, AMBIGUOUS_OVERRIDE_KEYWORDS)
    if hit:
        return "ambiguous", f"命中模糊命名「{hit}」(可能为园区或商业命名，需人工核验)"

    hit = first_hit(text, FOOD_KEYWORDS)
    if hit:
        return "food_city_production", f"命中食品生产关键词「{hit}」"

    hit = first_hit(text, URBAN_PRODUCTION_KEYWORDS)
    if hit:
        return "urban_production", f"命中城市型生产关键词「{hit}」"

    if LAB_KEYWORD in text:
        anchor = first_hit(text, ["研发", "试制", "中试", "工程", "材料", "生物医药"])
        if anchor:
            return "urban_production", f"命中「实验室」且含生产/研发线索「{anchor}」"
        return "ambiguous", "命中「实验室」但无生产线索 (可能为学校/检测/医疗，需人工核验)"

    hit = first_hit(text, INDUSTRIAL_SPACE_KEYWORDS)
    if hit:
        return "industrial_space", f"命中产业/园区关键词「{hit}」"

    hit = first_hit(text, TRADITIONAL_FACTORY_KEYWORDS)
    if hit:
        return "traditional_factory", f"命中传统制造关键词「{hit}」"

    return "ambiguous", "未命中任何分类关键词"


def valid_coord(lon: float, lat: float) -> bool:
    return pd.notna(lon) and pd.notna(lat) and LON_RANGE[0] <= lon <= LON_RANGE[1] and LAT_RANGE[0] <= lat <= LAT_RANGE[1]


def clean_classify(interim: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = interim.reset_index(drop=True).copy()
    df["poi_id"] = [f"P{ix:05d}" for ix in range(1, len(df) + 1)]
    df["status"] = "kept"
    df["category"] = ""
    df["classification_reason"] = ""

    bad = ~df.apply(lambda r: valid_coord(r["lon"], r["lat"]), axis=1)
    df.loc[bad, "status"] = "dropped_invalid_coord"
    df.loc[bad, "classification_reason"] = "坐标缺失或超出上海合理范围"

    ok = df["status"] == "kept"
    sub = df[ok].copy()
    dup_mask = sub.duplicated(subset=["name", "address"], keep="first")
    dup_mask = dup_mask | sub.assign(_lon=sub["lon"].round(4), _lat=sub["lat"].round(4)).duplicated(
        subset=["name", "_lon", "_lat"], keep="first"
    )
    dup_ids = sub.loc[dup_mask, "poi_id"]
    df.loc[df["poi_id"].isin(dup_ids), "status"] = "duplicate"
    df.loc[df["poi_id"].isin(dup_ids), "classification_reason"] = "与已有记录重复(name+address 或近似坐标)"

    for ix, row in df[df["status"] == "kept"].iterrows():
        text = " ".join(str(row[k]) for k in ("name", "raw_keyword", "raw_type", "address"))
        fp, reason = is_false_positive(text)
        if fp:
            df.at[ix, "status"] = "filtered_false_positive"
            df.at[ix, "category"] = "filtered"
            df.at[ix, "classification_reason"] = reason
            continue
        cat, reason = classify_poi(row["name"], row["raw_keyword"], row["raw_type"], row["address"])
        df.at[ix, "category"] = cat
        df.at[ix, "classification_reason"] = reason

    audit_cols = [
        "poi_id", "name", "address", "lon", "lat", "raw_keyword", "raw_type",
        "source", "status", "category", "classification_reason",
    ]
    audit = df[audit_cols].copy()
    clean = df[df["status"] == "kept"].copy()
    clean["is_urban_production"] = (clean["category"] == "urban_production").astype(int)
    clean["is_traditional_factory"] = (clean["category"] == "traditional_factory").astype(int)
    clean["is_industrial_space"] = (clean["category"] == "industrial_space").astype(int)
    clean_cols = [
        "name", "address", "lon", "lat", "raw_keyword", "raw_type", "source",
        "poi_id", "category", "classification_reason",
        "is_urban_production", "is_traditional_factory", "is_industrial_space",
    ]
    return clean[clean_cols].reset_index(drop=True), audit


def add_spatial_features(clean: pd.DataFrame) -> pd.DataFrame:
    df = clean.copy()
    df["distance_to_people_square_km"] = df.apply(
        lambda r: round(haversine_km(r["lon"], r["lat"], PEOPLE_SQUARE_LON, PEOPLE_SQUARE_LAT), 4),
        axis=1,
    )
    df["center_zone"] = df["distance_to_people_square_km"].apply(classify_zone)
    df["is_inner_center"] = (df["center_zone"] == "inner_center").astype(int)

    for name, (lon, lat) in POLYCENTRIC_CENTERS.items():
        df[f"distance_to_{name}_km"] = df.apply(
            lambda r, lon=lon, lat=lat: round(haversine_km(r["lon"], r["lat"], lon, lat), 4),
            axis=1,
        )

    def nearest(row: pd.Series) -> tuple[str, float, float]:
        distances = {
            name: haversine_km(row["lon"], row["lat"], lon, lat)
            for name, (lon, lat) in POLYCENTRIC_CENTERS.items()
        }
        center = min(distances, key=distances.get)
        dist = distances[center]
        score = sum(math.exp(-d / POLYCENTRIC_DECAY_KM) for d in distances.values())
        return center, dist, score

    nearest_values = df.apply(nearest, axis=1)
    df["nearest_center"] = nearest_values.apply(lambda x: x[0])
    df["nearest_center_label_zh"] = df["nearest_center"].map(CENTER_LABELS_ZH)
    df["distance_to_nearest_center_km"] = nearest_values.apply(lambda x: round(x[1], 4))
    df["nearest_center_zone"] = df["distance_to_nearest_center_km"].apply(classify_nearest_center_zone)
    df["polycentric_centrality_score"] = nearest_values.apply(lambda x: round(x[2], 4))
    return df


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
DIST_SINGLE = "distance_to_people_square_km"
DIST_MULTI = "distance_to_nearest_center_km"


def present_categories(df: pd.DataFrame) -> list[str]:
    return [cat for cat in CATEGORIES if cat in set(df["category"])]


def overlay_hist_urban_traditional(ax, df: pd.DataFrame, dist_col: str, bins: np.ndarray) -> None:
    groups = [
        ("城市型生产", df.loc[df["is_urban_production"] == 1, dist_col].dropna().to_numpy(), "#2a6f97"),
        ("传统制造", df.loc[df["is_traditional_factory"] == 1, dist_col].dropna().to_numpy(), "#9e2a2b"),
    ]
    for label, vals, color in groups:
        if len(vals):
            ax.hist(vals, bins=bins, color=color, alpha=0.50,
                    label=f"{label} (n={len(vals)})", edgecolor="white")
            ax.axvline(vals.mean(), color=color, linestyle="--", linewidth=1.7,
                       label=f"{label}均值 {vals.mean():.1f}km")


def fig_distance_distribution(df: pd.DataFrame, plt, out: Path, dist_col: str,
                              xlabel: str, title: str, thresholds: list[tuple[float, str]],
                              note: str) -> None:
    fig, ax = plt.subplots(figsize=(9, 5.5))
    max_dist = float(np.nanmax(df[dist_col])) if len(df) else 1.0
    bins = np.linspace(0, max_dist + 1, 16)
    overlay_hist_urban_traditional(ax, df, dist_col, bins)
    for x, label in thresholds:
        ax.axvline(x, color="#666666", linestyle=":", linewidth=1.2)
        ax.text(x, ax.get_ylim()[1] * 0.95, f"  {label}", color="#555555",
                va="top", ha="left", fontsize=9)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("POI 数量")
    ax.set_title(title)
    ax.legend(title="组别/均值", loc="upper right", framealpha=0.9, fontsize=8)
    fig.text(0.5, -0.02, note, ha="center", fontsize=8, color="#666666")
    fig.savefig(out)
    plt.close(fig)


def fig_category_distance_comparison(df: pd.DataFrame, plt, out: Path) -> None:
    cats = present_categories(df)
    labels = [CATEGORY_LABELS_ZH[cat] for cat in cats]
    fig, axes = plt.subplots(2, 1, figsize=(9.5, 10.2), sharex=False, sharey=False)
    specs = [
        (axes[0], DIST_SINGLE, "单中心：距人民广场距离", "距离 (km)",
         [(INNER_MAX_KM, "8km"), (MIDDLE_MAX_KM, "18km")]),
        (axes[1], DIST_MULTI, "多中心：距最近中心/副中心距离", "距离 (km)",
         [(NEAREST_CENTER_INNER_MAX_KM, "3km"), (NEAREST_CENTER_MIDDLE_MAX_KM, "8km")]),
    ]
    for ax, col, title, ylabel, thresholds in specs:
        data = [df.loc[df["category"] == cat, col].to_numpy() for cat in cats]
        bp = ax.boxplot(data, vert=True, patch_artist=True,
                        medianprops=dict(color="#222222", linewidth=1.4),
                        flierprops=dict(marker="o", markersize=3, alpha=0.45))
        ax.set_xticks(range(1, len(labels) + 1))
        ax.set_xticklabels(labels, rotation=20, ha="right")
        for patch, cat in zip(bp["boxes"], cats):
            patch.set_facecolor(CATEGORY_COLORS.get(cat, "#888888"))
            patch.set_alpha(0.85)
        for y, label in thresholds:
            ax.axhline(y, color="#9e2a2b", linestyle="--", linewidth=1.0, alpha=0.65)
            ax.text(0.5, y, f" {label}", color="#9e2a2b", va="bottom", ha="left", fontsize=8)
        ax.set_title(title)
        ax.set_ylabel(ylabel)
    fig.suptitle("不同生产活动类型在两种中心性口径下的距离对比", y=0.995)
    fig.text(0.5, -0.02,
             "注：上图对应单中心口径；下图把上海视为多中心城市。箱体展示组内距离分布，红色虚线为本文设定的距离参考线。",
             ha="center", fontsize=8, color="#666666")
    fig.tight_layout(rect=[0, 0.02, 1, 0.97])
    fig.savefig(out)
    plt.close(fig)


def fig_category_by_zone(df: pd.DataFrame, plt, out: Path, zone_col: str,
                         zone_order: list[str], zone_labels: dict[str, str],
                         title: str, note: str) -> None:
    cats = present_categories(df)
    zones = [z for z in zone_order if z in set(df[zone_col])]
    ct = pd.crosstab(df[zone_col], df["category"]).reindex(index=zones, columns=cats).fillna(0)
    fig, ax = plt.subplots(figsize=(9, 6))
    x = np.arange(len(zones))
    bottom = np.zeros(len(zones))
    for cat in cats:
        vals = ct[cat].to_numpy()
        ax.bar(x, vals, bottom=bottom, color=CATEGORY_COLORS.get(cat, "#888888"),
               label=CATEGORY_LABELS_ZH[cat], edgecolor="white", linewidth=0.6)
        bottom += vals
    ax.set_xticks(x)
    ax.set_xticklabels([zone_labels.get(z, z) for z in zones])
    ax.set_ylabel("POI 数量")
    ax.set_title(title)
    ax.legend(title="类别", loc="upper left", bbox_to_anchor=(1.01, 1.0), framealpha=0.9)
    fig.text(0.5, -0.02, note, ha="center", fontsize=8, color="#666666")
    fig.savefig(out)
    plt.close(fig)


def dest_point(lon: float, lat: float, bearing_deg: float, dist_km: float) -> tuple[float, float]:
    br = math.radians(bearing_deg)
    ang = dist_km / 6371.0088
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    lat2 = math.asin(math.sin(lat1) * math.cos(ang) +
                     math.cos(lat1) * math.sin(ang) * math.cos(br))
    lon2 = lon1 + math.atan2(math.sin(br) * math.sin(ang) * math.cos(lat1),
                             math.cos(ang) - math.sin(lat1) * math.sin(lat2))
    return math.degrees(lon2), math.degrees(lat2)


def ring(lon: float, lat: float, dist_km: float, n: int = 180) -> tuple[list[float], list[float]]:
    pts = [dest_point(lon, lat, b, dist_km) for b in np.linspace(0, 360, n)]
    return [p[0] for p in pts], [p[1] for p in pts]


def fig_poi_scatter_map(df: pd.DataFrame, plt, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 9))
    for cat in present_categories(df):
        sub = df[df["category"] == cat]
        ax.scatter(sub["lon"], sub["lat"], s=4,
                   color=CATEGORY_COLORS.get(cat, "#888888"),
                   label=f"{CATEGORY_LABELS_ZH[cat]} (n={len(sub)})",
                   edgecolor="none", alpha=0.42, zorder=4)
    ax.scatter([PEOPLE_SQUARE_LON], [PEOPLE_SQUARE_LAT], marker="*",
               s=180, color="#111111", edgecolor="white", linewidth=0.8,
               zorder=6, label="人民广场（中心点）")
    other_centers = {k: v for k, v in POLYCENTRIC_CENTERS.items() if k != "central_core"}
    ax.scatter([v[0] for v in other_centers.values()], [v[1] for v in other_centers.values()],
               marker="D", s=34, color="#f4a261", edgecolor="#333333",
               linewidth=0.5, alpha=0.95, zorder=6, label="副中心")
    for name, (lon, lat) in other_centers.items():
        ax.text(lon, lat, " " + CENTER_LABELS_ZH.get(name, name), fontsize=7,
                color="#333333", va="center", ha="left", zorder=7)
    for dist, style in [(INNER_MAX_KM, "--"), (MIDDLE_MAX_KM, ":")]:
        xs, ys = ring(PEOPLE_SQUARE_LON, PEOPLE_SQUARE_LAT, dist)
        ax.plot(xs, ys, color="#9e2a2b", linestyle=style, linewidth=1.4,
                alpha=0.8, zorder=3, label=f"{dist:.0f}km 距离圈（近似）")
    ax.set_aspect(1.0 / math.cos(math.radians(PEOPLE_SQUARE_LAT)))
    ax.set_xlabel("经度 lon")
    ax.set_ylabel("纬度 lat")
    ax.set_title("上海生产活动 POI 空间分布（按类型着色）")
    ax.legend(loc="upper left", framealpha=0.9, fontsize=8)
    fig.text(0.5, 0.04,
             "注：圆环为本文设定的 8/18km 距离参考圈，非真实内环/中环/外环；菱形标记为多中心口径使用的其他副中心；坐标未做 GCJ-02/WGS-84 转换。",
             ha="center", fontsize=8, color="#666666")
    fig.savefig(out)
    plt.close(fig)


def make_figures(df: pd.DataFrame, figures_dir: Path) -> None:
    figures_dir.mkdir(parents=True, exist_ok=True)
    plt = setup_matplotlib()
    fig_distance_distribution(
        df, plt, figures_dir / "poi_distance_distribution.png",
        DIST_SINGLE, "距人民广场距离 (km)",
        "城市型生产与传统制造到人民广场的距离分布（单中心口径）",
        [(INNER_MAX_KM, "8km"), (MIDDLE_MAX_KM, "18km")],
        "注：仅比较城市型生产与传统制造；彩色虚线为组内均值；灰色点线为本文设定的距离参考线，非真实环线。",
    )
    fig_distance_distribution(
        df, plt, figures_dir / "poi_distance_distribution_polycentric.png",
        DIST_MULTI, "距最近中心/副中心距离 (km)",
        "城市型生产与传统制造到最近中心/副中心的距离分布（多中心口径）",
        [(NEAREST_CENTER_INNER_MAX_KM, "3km"), (NEAREST_CENTER_MIDDLE_MAX_KM, "8km")],
        "注：仅比较城市型生产与传统制造；多中心口径将人民广场/外滩/陆家嘴合为中心核心区；彩色虚线为组内均值。",
    )
    fig_category_distance_comparison(df, plt, figures_dir / "category_distance_comparison.png")
    fig_poi_scatter_map(df, plt, figures_dir / "poi_scatter_map.png")
    fig_category_by_zone(
        df, plt, figures_dir / "category_by_zone.png",
        "center_zone", ZONE_ORDER, ZONE_LABELS_ZH,
        "各人民广场距离分组内生产活动类型构成（单中心口径）",
        "注：距离分组为本文操作性划分，非真实内环/中环/外环。",
    )
    fig_category_by_zone(
        df, plt, figures_dir / "category_by_nearest_center_zone.png",
        "nearest_center_zone", NEAREST_CENTER_ZONE_ORDER, NEAREST_CENTER_ZONE_LABELS_ZH,
        "各最近中心距离分组内生产活动类型构成（多中心口径）",
        "注：距离分组按距最近中心/副中心距离划分，用于和单中心口径对比。",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    figures_dir = Path(args.figures_dir)
    raw_path = data_dir / "amap_poi_raw.csv"
    audit_path = data_dir / "poi_classification_audit.csv"
    spatial_path = data_dir / "poi_spatial.csv"
    data_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    if args.collect:
        banner("1. 获取高德 POI 原始数据")
        key = get_amap_key(Path(args.env), args.amap_key)
        if not key:
            raise RuntimeError("未找到 AMAP_KEY。请在 .env 中写入 AMAP_KEY=你的高德Web服务Key，或用 --amap-key 传入。")
        districts = DISTRICTS if args.by_district else []
        raw = collect_amap(
            key=key,
            city=args.city,
            keywords=KEYWORDS,
            districts=districts,
            max_pages=args.max_pages,
            sleep_s=args.sleep,
            page_size=args.page_size,
            timeout=args.timeout,
            limit_total=args.limit_total,
            citylimit=not args.no_citylimit,
        )
        write_csv(raw, raw_path)
        print(f"已保存原始数据: {raw_path} ({len(raw)} 行)")
    else:
        banner("1. 使用已上传的原始 POI 数据")
        if not raw_path.exists():
            raise FileNotFoundError(f"未找到 {raw_path}。请先上传原始数据，或运行 --collect。")
        raw = read_csv(raw_path)
        print(f"读取原始数据: {raw_path} ({len(raw)} 行)")

    banner("2. 自动清洗、分类与空间变量")
    interim = normalize_raw(raw)
    clean, audit = clean_classify(interim)
    spatial = add_spatial_features(clean)
    write_csv(audit, audit_path)
    write_csv(spatial, spatial_path)
    print(f"清洗后保留: {len(spatial)} 条")
    print(f"已保存审计表: {audit_path}")
    print(f"已保存空间数据: {spatial_path}")
    counts = spatial["category"].value_counts()
    for cat in CATEGORIES:
        if cat in counts.index:
            print(f"  - {CATEGORY_LABELS_ZH[cat]}: {counts[cat]}")

    banner("3. 生成论文 POI 图")
    make_figures(spatial, figures_dir)
    print(f"已保存图到: {figures_dir}")

    urban = spatial.loc[spatial["is_urban_production"] == 1, DIST_SINGLE]
    trad = spatial.loc[spatial["is_traditional_factory"] == 1, DIST_SINGLE]
    if len(urban) and len(trad):
        print("\n论文中使用的核心描述性数值:")
        print(f"  城市型生产到人民广场均值: {urban.mean():.2f} km，中位数: {urban.median():.2f} km")
        print(f"  传统制造到人民广场均值  : {trad.mean():.2f} km，中位数: {trad.median():.2f} km")
    print("\n完成。注意：POI 是地图平台描述性样本，不是企业普查，也不构成因果识别。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="获取/清洗上海生产活动 POI 并复现论文图 4/5/7/8")
    parser.add_argument("--collect", action="store_true", help="调用高德 Web 服务重新获取原始 POI")
    parser.add_argument("--use-existing", action="store_true", help="使用 paper_data/data/amap_poi_raw.csv 复现清洗与图")
    parser.add_argument("--amap-key", default=None, help="高德 Web 服务 Key；更推荐写入 .env")
    parser.add_argument("--env", default=str(ROOT / ".env"), help=".env 路径，默认仓库根目录 .env")
    parser.add_argument("--city", default="上海")
    parser.add_argument("--by-district", action="store_true", help="按内置 16 个行政区逐区检索；默认全市关键词检索")
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES)
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP_S)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--limit-total", type=int, default=None, help="调试用：限制本次最多采集多少条")
    parser.add_argument("--no-citylimit", action="store_true", help="关闭高德 citylimit；通常不建议")
    parser.add_argument("--data-dir", default=str(DATA_DIR))
    parser.add_argument("--figures-dir", default=str(FIGURES_DIR))
    args = parser.parse_args()

    if args.collect and args.use_existing:
        parser.error("--collect 和 --use-existing 只能选一个")
    if not args.collect:
        args.use_existing = True
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
