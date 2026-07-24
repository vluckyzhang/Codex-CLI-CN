from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".cache" / "chatgpt_aqli_pm25"
OUT = ROOT / "output_aqli"
CACHE.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

SOURCE_URL = (
    "https://github.com/aqli-epic/aqli-update/raw/main/"
    "AQLI%20Annual%20Update%202026%20data/gadm1.zip"
)
YEARS = list(range(2012, 2025))

PROVINCES = [
    ("11", "北京", "Beijing", ["Beijing"]),
    ("12", "天津", "Tianjin", ["Tianjin"]),
    ("13", "河北", "Hebei", ["Hebei"]),
    ("14", "山西", "Shanxi", ["Shanxi"]),
    ("15", "内蒙古", "Inner Mongolia", ["Inner Mongolia", "Nei Mongol"]),
    ("21", "辽宁", "Liaoning", ["Liaoning"]),
    ("22", "吉林", "Jilin", ["Jilin"]),
    ("23", "黑龙江", "Heilongjiang", ["Heilongjiang"]),
    ("31", "上海", "Shanghai", ["Shanghai"]),
    ("32", "江苏", "Jiangsu", ["Jiangsu"]),
    ("33", "浙江", "Zhejiang", ["Zhejiang"]),
    ("34", "安徽", "Anhui", ["Anhui"]),
    ("35", "福建", "Fujian", ["Fujian"]),
    ("36", "江西", "Jiangxi", ["Jiangxi"]),
    ("37", "山东", "Shandong", ["Shandong"]),
    ("41", "河南", "Henan", ["Henan"]),
    ("42", "湖北", "Hubei", ["Hubei"]),
    ("43", "湖南", "Hunan", ["Hunan"]),
    ("44", "广东", "Guangdong", ["Guangdong"]),
    ("45", "广西", "Guangxi", ["Guangxi", "Guangxi Zhuang"]),
    ("46", "海南", "Hainan", ["Hainan"]),
    ("50", "重庆", "Chongqing", ["Chongqing"]),
    ("51", "四川", "Sichuan", ["Sichuan"]),
    ("52", "贵州", "Guizhou", ["Guizhou"]),
    ("53", "云南", "Yunnan", ["Yunnan"]),
    ("61", "陕西", "Shaanxi", ["Shaanxi"]),
    ("62", "甘肃", "Gansu", ["Gansu"]),
    ("63", "青海", "Qinghai", ["Qinghai"]),
    ("64", "宁夏", "Ningxia", ["Ningxia", "Ningxia Hui"]),
    ("65", "新疆", "Xinjiang", ["Xinjiang", "Xinjiang Uygur"]),
]


def normalize(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    if destination.exists() and destination.stat().st_size > 1000:
        print(f"Using cached {destination.name}")
        return
    destination.unlink(missing_ok=True)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 AQLI-provincial-panel-reproduction/1.0"},
    )
    last_error: Exception | None = None
    for attempt in range(1, 6):
        try:
            print(f"Downloading AQLI GADM1 archive (attempt {attempt})")
            with urllib.request.urlopen(request, timeout=300) as response, destination.open("wb") as output:
                shutil.copyfileobj(response, output, length=1024 * 1024)
            if destination.stat().st_size < 1000:
                raise RuntimeError(f"Downloaded file is unexpectedly small: {destination.stat().st_size}")
            if not zipfile.is_zipfile(destination):
                first = destination.read_bytes()[:200]
                raise RuntimeError(f"Downloaded content is not ZIP: {first!r}")
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            destination.unlink(missing_ok=True)
            time.sleep(min(30, 2**attempt))
    raise RuntimeError(f"Failed to download AQLI archive: {last_error}")


def find_column(fieldnames: list[str], candidates: list[str]) -> str | None:
    normalized = {normalize(name): name for name in fieldnames}
    for candidate in candidates:
        if normalize(candidate) in normalized:
            return normalized[normalize(candidate)]
    return None


def inspect_csv(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
    pm_columns: dict[int, str] = {}
    for column in header:
        match = re.fullmatch(r"pm[_. -]?(\d{4})", column.strip(), flags=re.I)
        if match:
            pm_columns[int(match.group(1))] = column
    return {
        "path": str(path),
        "header": header,
        "pm_columns": pm_columns,
        "country_column": find_column(header, ["name0", "country", "country_name"]),
        "province_column": find_column(header, ["name1", "name_1", "province", "state"]),
        "type_column": find_column(header, ["type", "measure"]),
        "year_column": find_column(header, ["year"]),
        "value_column": find_column(header, ["value", "pm", "pm25"]),
    }


def select_source_csv(extract_dir: Path) -> tuple[Path, dict[str, Any], list[dict[str, Any]]]:
    candidates = sorted(extract_dir.rglob("*.csv"))
    if not candidates:
        raise RuntimeError(f"No CSV files found in archive. Files: {[str(p) for p in extract_dir.rglob('*') if p.is_file()]}")
    inspections = [inspect_csv(path) for path in candidates]
    wide = [
        item
        for item in inspections
        if item["country_column"] and item["province_column"] and all(year in item["pm_columns"] for year in YEARS)
    ]
    if wide:
        wide.sort(key=lambda item: ("wide" not in Path(item["path"]).name.casefold(), len(item["header"])))
        selected = wide[0]
        return Path(selected["path"]), selected, inspections
    long = [
        item
        for item in inspections
        if item["country_column"]
        and item["province_column"]
        and item["type_column"]
        and item["year_column"]
        and item["value_column"]
    ]
    if long:
        long.sort(key=lambda item: "narrow" not in Path(item["path"]).name.casefold())
        selected = long[0]
        return Path(selected["path"]), selected, inspections
    raise RuntimeError(
        "Could not identify a suitable GADM1 CSV. "
        + json.dumps(inspections, ensure_ascii=False, indent=2)
    )


def parse_float(value: Any) -> float | None:
    text = str(value).strip()
    if not text or text.casefold() in {"na", "nan", "null", "none", "-"}:
        return None
    return float(text)


def load_wide(path: Path, info: dict[str, Any]) -> tuple[dict[str, dict[int, float]], dict[str, dict[str, Any]]]:
    country_col = str(info["country_column"])
    province_col = str(info["province_column"])
    pm_cols: dict[int, str] = info["pm_columns"]
    population_col = find_column(info["header"], ["population"])
    national_standard_col = find_column(info["header"], ["natstandard", "national_standard"])
    rows_by_name: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if normalize(row.get(country_col, "")) != "china":
                continue
            rows_by_name[normalize(row.get(province_col, ""))] = row

    values: dict[str, dict[int, float]] = {}
    trace: dict[str, dict[str, Any]] = {}
    unmatched: list[str] = []
    for code, cn, en, aliases in PROVINCES:
        source_row = None
        source_name = None
        for alias in aliases:
            source_row = rows_by_name.get(normalize(alias))
            if source_row is not None:
                source_name = source_row.get(province_col, alias)
                break
        if source_row is None:
            unmatched.append(en)
            continue
        annual: dict[int, float] = {}
        for year in YEARS:
            value = parse_float(source_row.get(pm_cols[year]))
            if value is None:
                raise RuntimeError(f"Missing PM2.5: {en}, {year}, column {pm_cols[year]}")
            annual[year] = value
        values[code] = annual
        trace[code] = {
            "source_province_name": source_name,
            "population": parse_float(source_row.get(population_col)) if population_col else None,
            "national_standard": parse_float(source_row.get(national_standard_col)) if national_standard_col else None,
        }
    if unmatched:
        available = sorted(row.get(province_col, "") for row in rows_by_name.values())
        raise RuntimeError(f"Unmatched provinces: {unmatched}; China GADM1 names: {available}")
    return values, trace


def load_long(path: Path, info: dict[str, Any]) -> tuple[dict[str, dict[int, float]], dict[str, dict[str, Any]]]:
    country_col = str(info["country_column"])
    province_col = str(info["province_column"])
    type_col = str(info["type_column"])
    year_col = str(info["year_column"])
    value_col = str(info["value_column"])
    population_col = find_column(info["header"], ["population"])
    national_standard_col = find_column(info["header"], ["natstandard", "national_standard"])
    raw: dict[str, dict[int, float]] = {}
    raw_trace: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if normalize(row.get(country_col, "")) != "china":
                continue
            if normalize(row.get(type_col, "")) not in {"pm", "pm25", "pm25concentration"}:
                continue
            try:
                year = int(float(str(row.get(year_col, "")).strip()))
            except ValueError:
                continue
            if year not in YEARS:
                continue
            value = parse_float(row.get(value_col))
            if value is None:
                continue
            province_key = normalize(row.get(province_col, ""))
            raw.setdefault(province_key, {})[year] = value
            raw_trace[province_key] = {
                "source_province_name": row.get(province_col),
                "population": parse_float(row.get(population_col)) if population_col else None,
                "national_standard": parse_float(row.get(national_standard_col)) if national_standard_col else None,
            }

    values: dict[str, dict[int, float]] = {}
    trace: dict[str, dict[str, Any]] = {}
    unmatched: list[str] = []
    for code, cn, en, aliases in PROVINCES:
        source_key = next((normalize(alias) for alias in aliases if normalize(alias) in raw), None)
        if source_key is None:
            unmatched.append(en)
            continue
        if sorted(raw[source_key]) != YEARS:
            raise RuntimeError(f"Incomplete years for {en}: {sorted(raw[source_key])}")
        values[code] = raw[source_key]
        trace[code] = raw_trace[source_key]
    if unmatched:
        available = sorted(item["source_province_name"] for item in raw_trace.values())
        raise RuntimeError(f"Unmatched provinces: {unmatched}; China GADM1 names: {available}")
    return values, trace


def write_outputs(
    values: dict[str, dict[int, float]],
    trace: dict[str, dict[str, Any]],
    archive_path: Path,
    source_csv: Path,
    source_info: dict[str, Any],
    inspections: list[dict[str, Any]],
) -> None:
    aggregation = "population-weighted annual mean as published by EPIC/AQLI at GADM1 level"
    long_rows: list[dict[str, Any]] = []
    for code, cn, en, _aliases in PROVINCES:
        for year in YEARS:
            long_rows.append(
                {
                    "province_code": code,
                    "province_cn": cn,
                    "province_en": en,
                    "year": year,
                    "pm25_ug_m3": f"{values[code][year]:.2f}",
                    "source_province_name": trace[code].get("source_province_name"),
                    "aggregation": aggregation,
                    "source_dataset": "Air Quality Life Index (AQLI)",
                    "source_release": "AQLI Annual Update 2026",
                }
            )
    if len(long_rows) != 390:
        raise RuntimeError(f"Expected 390 records, found {len(long_rows)}")

    long_fields = [
        "province_code",
        "province_cn",
        "province_en",
        "year",
        "pm25_ug_m3",
        "source_province_name",
        "aggregation",
        "source_dataset",
        "source_release",
    ]
    with (OUT / "PM25_Long_Panel.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=long_fields)
        writer.writeheader()
        writer.writerows(long_rows)

    with (OUT / "PM25_Wide.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["province_code", "province_cn", "province_en", *YEARS])
        for code, cn, en, _aliases in PROVINCES:
            writer.writerow([code, cn, en, *[f"{values[code][year]:.2f}" for year in YEARS]])

    all_values = [values[code][year] for code, *_ in PROVINCES for year in YEARS]
    metadata = {
        "source_dataset": "Air Quality Life Index (AQLI)",
        "producer": "Energy Policy Institute at the University of Chicago (EPIC)",
        "source_release": "AQLI Annual Update 2026",
        "source_url": SOURCE_URL,
        "source_repository": "https://github.com/aqli-epic/aqli-update",
        "methodology_url": "https://aqli.epic.uchicago.edu/about/methodology/",
        "underlying_pm25_source": "Atmospheric Composition Analysis Group (ACAG), satellite-derived PM2.5",
        "underlying_source_url": "https://sites.wustl.edu/acag/datasets/surface-pm2-5/",
        "unit": "micrograms per cubic metre (ug/m3)",
        "years": YEARS,
        "province_count": 30,
        "record_count": len(long_rows),
        "excluded_units": ["Xizang/Tibet", "Hong Kong", "Macao", "Taiwan"],
        "aggregation": aggregation,
        "scope_note": "AQLI PM2.5 series excludes mineral dust and sea salt and focuses on human-caused particulate pollution.",
        "archive": {
            "filename": archive_path.name,
            "size_bytes": archive_path.stat().st_size,
            "sha256": sha256sum(archive_path),
        },
        "selected_csv": {
            "archive_member": str(source_csv.relative_to(CACHE / "extracted")),
            "columns": source_info["header"],
        },
        "archive_csv_inspection": [
            {
                "archive_member": str(Path(item["path"]).relative_to(CACHE / "extracted")),
                "columns": item["header"],
                "pm_years": sorted(item["pm_columns"]),
            }
            for item in inspections
        ],
        "province_trace": trace,
        "quality_checks": {
            "expected_records": 390,
            "actual_records": len(long_rows),
            "unique_province_year_keys": len({(row["province_code"], row["year"]) for row in long_rows}),
            "missing_values": sum(1 for value in all_values if value is None),
            "minimum_pm25_ug_m3": min(all_values),
            "maximum_pm25_ug_m3": max(all_values),
        },
    }
    with (OUT / "metadata.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)


def main() -> None:
    archive_path = CACHE / "gadm1.zip"
    download(SOURCE_URL, archive_path)
    extract_dir = CACHE / "extracted"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(extract_dir)
        print("Archive members:")
        for member in archive.namelist():
            print(f"  {member}")

    source_csv, source_info, inspections = select_source_csv(extract_dir)
    print(f"Selected source CSV: {source_csv}")
    if source_info["pm_columns"]:
        values, trace = load_wide(source_csv, source_info)
    else:
        values, trace = load_long(source_csv, source_info)
    write_outputs(values, trace, archive_path, source_csv, source_info, inspections)

    metadata = json.loads((OUT / "metadata.json").read_text(encoding="utf-8"))
    qc = metadata["quality_checks"]
    assert qc["actual_records"] == 390
    assert qc["unique_province_year_keys"] == 390
    assert qc["missing_values"] == 0
    assert 0 < qc["minimum_pm25_ug_m3"] < qc["maximum_pm25_ug_m3"] < 200
    print(json.dumps(qc, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
