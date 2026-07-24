from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import requests
import rasterio
import xarray as xr
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.geometry import mapping

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".cache" / "chatgpt_chap_pm25"
OUT = ROOT / "output"
CACHE.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

YEARS = list(range(2012, 2025))
RECORD_BY_YEAR = {**{year: 6398971 for year in range(2012, 2022)}, **{year: 15208529 for year in range(2022, 2025)}}
MD5_BY_YEAR = {
    2012: "fee023f9ef76dbb7c4e1c3dc804abeac",
    2013: "076811cf62dc70aee8b5b3b57ffce2e6",
    2014: "e8b2a8567b3e7112b108cda6fcdfd7f4",
    2015: "ba03a02bb4e4082aa993ff8387e28eaa",
    2016: "5b93a3cba04c910f32420b5069eff06b",
    2017: "cf570537f85d45ef3501305354ef997e",
    2018: "e5ad8460e2b3933a6082eab2dfceced6",
    2019: "b2bbb5e17724504b6b86bab5d2b8d982",
    2020: "5ff0cdf7630f4d359e24047e4cec6e28",
    2021: "6e4bec8415f28f69950b19dbc91b3b7a",
    2022: "f484925215022c1c8e415375a5c98f0a",
    2023: "0e0c2b4479535e29efb6af5a27b43c2a",
    2024: "cb330b15ad3b93887f27e879d52704a9",
}

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

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 CHAP-PM25-research-reproduction/1.0"})


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def md5sum(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path, expected_md5: str | None = None) -> None:
    if destination.exists() and (expected_md5 is None or md5sum(destination) == expected_md5):
        print(f"Using cached file: {destination.name}")
        return
    destination.unlink(missing_ok=True)
    last_error: Exception | None = None
    for attempt in range(1, 6):
        try:
            print(f"Downloading {url} (attempt {attempt})")
            with SESSION.get(url, stream=True, timeout=(30, 300), allow_redirects=True) as response:
                response.raise_for_status()
                with destination.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            handle.write(chunk)
            if expected_md5 is not None:
                actual = md5sum(destination)
                if actual != expected_md5:
                    raise RuntimeError(f"MD5 mismatch for {destination.name}: {actual} != {expected_md5}")
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            destination.unlink(missing_ok=True)
            time.sleep(min(30, 2**attempt))
    raise RuntimeError(f"Failed to download {url}: {last_error}")


def get_year_file(year: int) -> Path:
    filename = f"CHAP_PM2.5_Y1K_{year}_V4.nc"
    path = CACHE / filename
    record = RECORD_BY_YEAR[year]
    url = f"https://zenodo.org/api/records/{record}/files/{filename}/content"
    download(url, path, MD5_BY_YEAR[year])
    return path


def get_boundaries() -> gpd.GeoDataFrame:
    zip_path = CACHE / "gadm41_CHN_shp.zip"
    url = "https://geodata.ucdavis.edu/gadm/gadm4.1/shp/gadm41_CHN_shp.zip"
    download(url, zip_path)
    extract_dir = CACHE / "gadm41_CHN_shp"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(extract_dir)
    shp = extract_dir / "gadm41_CHN_1.shp"
    if not shp.exists():
        candidates = list(extract_dir.glob("*_1.shp"))
        if len(candidates) != 1:
            raise RuntimeError(f"Could not identify GADM ADM1 shapefile: {candidates}")
        shp = candidates[0]
    gdf = gpd.read_file(shp).to_crs("EPSG:4326")
    name_column = "NAME_1" if "NAME_1" in gdf.columns else "name_1"
    available = {normalize_name(str(row[name_column])): row for _, row in gdf.iterrows()}
    selected_rows: list[dict[str, Any]] = []
    unmatched: list[str] = []
    for label, (code, cn, en, aliases) in enumerate(PROVINCES, start=1):
        match = None
        for alias in aliases:
            match = available.get(normalize_name(alias))
            if match is not None:
                break
        if match is None:
            unmatched.append(en)
            continue
        selected_rows.append({
            "label": label,
            "province_code": code,
            "province_cn": cn,
            "province_en": en,
            "geometry": match.geometry,
        })
    if unmatched:
        actual_names = sorted(str(v[name_column]) for v in available.values())
        raise RuntimeError(f"Unmatched provinces: {unmatched}; GADM names: {actual_names}")
    result = gpd.GeoDataFrame(selected_rows, crs="EPSG:4326")
    if len(result) != 30 or result.geometry.is_empty.any():
        raise RuntimeError("Province boundary selection failed")
    return result


def identify_coordinate(ds: xr.Dataset, kind: str) -> str:
    candidates = []
    for name in list(ds.coords) + list(ds.dims):
        low = str(name).casefold()
        if kind == "lat" and (low in {"lat", "latitude", "y"} or "lat" in low):
            candidates.append(str(name))
        if kind == "lon" and (low in {"lon", "longitude", "x"} or "lon" in low):
            candidates.append(str(name))
    for name in candidates:
        if name in ds and np.asarray(ds[name]).ndim == 1:
            return name
    raise RuntimeError(f"Could not identify {kind} coordinate; coords={list(ds.coords)}, dims={list(ds.dims)}")


def identify_variable(ds: xr.Dataset, lat_name: str, lon_name: str) -> str:
    preferred = []
    fallback = []
    for name, da in ds.data_vars.items():
        squeezed = da.squeeze(drop=True)
        if squeezed.ndim != 2:
            continue
        dims = set(squeezed.dims)
        if lat_name not in dims or lon_name not in dims:
            continue
        if re.search(r"pm\s*2[._]?5|pm25", str(name), re.I):
            preferred.append(str(name))
        else:
            fallback.append(str(name))
    choices = preferred or fallback
    if not choices:
        raise RuntimeError(f"Could not identify a 2-D PM2.5 variable; variables={list(ds.data_vars)}")
    return choices[0]


def read_raster(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, str, dict[str, Any]]:
    with xr.open_dataset(path, mask_and_scale=True, decode_cf=True) as ds:
        lat_name = identify_coordinate(ds, "lat")
        lon_name = identify_coordinate(ds, "lon")
        var_name = identify_variable(ds, lat_name, lon_name)
        da = ds[var_name].squeeze(drop=True).transpose(lat_name, lon_name)
        lat = np.asarray(ds[lat_name].values, dtype=np.float64)
        lon = np.asarray(ds[lon_name].values, dtype=np.float64)
        values = np.asarray(da.values, dtype=np.float64)
        attrs = dict(da.attrs)
    if lat.ndim != 1 or lon.ndim != 1 or values.shape != (lat.size, lon.size):
        raise RuntimeError(f"Unexpected raster shape: {values.shape}, lat={lat.shape}, lon={lon.shape}")
    if lon[0] > lon[-1]:
        lon = lon[::-1]
        values = values[:, ::-1]
    if lat[0] < lat[-1]:
        lat = lat[::-1]
        values = values[::-1, :]
    values[~np.isfinite(values)] = np.nan
    values[(values < 0) | (values > 1000)] = np.nan
    metadata = {
        "variable": var_name,
        "latitude_coordinate": lat_name,
        "longitude_coordinate": lon_name,
        "shape": [int(values.shape[0]), int(values.shape[1])],
        "variable_attributes": {str(k): str(v) for k, v in attrs.items()},
    }
    return values, lat, lon, var_name, metadata


def build_labels(provinces: gpd.GeoDataFrame, lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, Any]:
    if lat.size < 2 or lon.size < 2:
        raise RuntimeError("Raster coordinates are too short")
    dy = float(np.median(np.abs(np.diff(lat))))
    dx = float(np.median(np.abs(np.diff(lon))))
    transform = from_origin(float(lon.min() - dx / 2), float(lat.max() + dy / 2), dx, dy)
    shapes = [(mapping(row.geometry), int(row.label)) for row in provinces.itertuples()]
    labels = rasterize(
        shapes=shapes,
        out_shape=(lat.size, lon.size),
        fill=0,
        transform=transform,
        all_touched=False,
        dtype=np.uint8,
    )
    missing_labels = [label for label in range(1, 31) if not np.any(labels == label)]
    if missing_labels:
        raise RuntimeError(f"Province labels absent from raster: {missing_labels}")
    return labels, transform


def weighted_means(values: np.ndarray, labels: np.ndarray, lat: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    weights_1d = np.cos(np.deg2rad(lat)).astype(np.float64)
    weights_2d = np.broadcast_to(weights_1d[:, None], values.shape)
    valid = (labels > 0) & np.isfinite(values) & np.isfinite(weights_2d) & (weights_2d > 0)
    label_values = labels[valid]
    numerator = np.bincount(label_values, weights=(values[valid] * weights_2d[valid]), minlength=31)
    denominator = np.bincount(label_values, weights=weights_2d[valid], minlength=31)
    means = np.full(31, np.nan, dtype=np.float64)
    good = denominator > 0
    means[good] = numerator[good] / denominator[good]
    return means, denominator


def write_outputs(records: list[dict[str, Any]], metadata: dict[str, Any]) -> None:
    long_path = OUT / "PM25_Long_Panel.csv"
    fields = [
        "province_code", "province_cn", "province_en", "year", "pm25_ug_m3",
        "aggregation", "source_dataset", "source_version",
    ]
    with long_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)

    by_province: dict[str, dict[int, float]] = {}
    labels: dict[str, tuple[str, str]] = {}
    for row in records:
        code = str(row["province_code"])
        labels[code] = (str(row["province_cn"]), str(row["province_en"]))
        by_province.setdefault(code, {})[int(row["year"])] = float(row["pm25_ug_m3"])
    wide_path = OUT / "PM25_Wide.csv"
    with wide_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["province_code", "province_cn", "province_en", *YEARS])
        for code, _, _, _ in PROVINCES:
            cn, en = labels[code]
            writer.writerow([code, cn, en, *[f"{by_province[code][year]:.6f}" for year in YEARS]])

    with (OUT / "metadata.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)


def main() -> None:
    print("Downloading and validating CHAP annual files...")
    year_files = {year: get_year_file(year) for year in YEARS}
    print("Loading GADM 4.1 province boundaries...")
    provinces = get_boundaries()

    first_values, first_lat, first_lon, first_var, first_meta = read_raster(year_files[YEARS[0]])
    labels, transform = build_labels(provinces, first_lat, first_lon)

    records: list[dict[str, Any]] = []
    yearly_metadata: dict[str, Any] = {}
    aggregation = "area-weighted mean using cos(latitude) cell-area weights; GADM 4.1 ADM1 cell-center mask"

    for year in YEARS:
        print(f"Processing {year}")
        values, lat, lon, var_name, raster_meta = read_raster(year_files[year])
        if values.shape != labels.shape or not np.allclose(lat, first_lat) or not np.allclose(lon, first_lon):
            raise RuntimeError(f"Grid mismatch in {year}")
        means, denominators = weighted_means(values, labels, lat)
        if np.any(~np.isfinite(means[1:])):
            raise RuntimeError(f"Missing province means in {year}: {means}")
        for row in provinces.itertuples():
            mean_value = float(means[int(row.label)])
            if not (0 < mean_value < 200):
                raise RuntimeError(f"Implausible PM2.5 mean: {row.province_en} {year} = {mean_value}")
            records.append({
                "province_code": row.province_code,
                "province_cn": row.province_cn,
                "province_en": row.province_en,
                "year": year,
                "pm25_ug_m3": f"{mean_value:.6f}",
                "aggregation": aggregation,
                "source_dataset": "CHAP ChinaHighPM2.5",
                "source_version": "V4 Y1K",
            })
        yearly_metadata[str(year)] = {
            **raster_meta,
            "filename": year_files[year].name,
            "record_id": RECORD_BY_YEAR[year],
            "md5": md5sum(year_files[year]),
            "valid_province_weight_denominators": [float(x) for x in denominators[1:]],
        }

    if len(records) != 390:
        raise RuntimeError(f"Expected 390 records, got {len(records)}")
    key_count = len({(row["province_code"], row["year"]) for row in records})
    if key_count != 390:
        raise RuntimeError(f"Duplicate province-year keys: {key_count}")

    metadata = {
        "generated_by": "Temporary reproducible GitHub Actions workflow",
        "source_dataset": "ChinaHighPM2.5 (CHAP)",
        "source_version": "V4, yearly 1 km (Y1K)",
        "source_records": {
            "2012-2021": "Zenodo record 6398971",
            "2022-2024": "Zenodo record 15208529",
        },
        "unit": "micrograms per cubic metre (ug/m3)",
        "years": YEARS,
        "province_count": 30,
        "record_count": len(records),
        "excluded_units": ["Xizang/Tibet", "Hong Kong", "Macao", "Taiwan"],
        "boundary_source": "GADM 4.1, China ADM1",
        "aggregation": aggregation,
        "grid_transform": [float(x) for x in tuple(transform)],
        "first_variable": first_var,
        "first_raster": first_meta,
        "annual_files": yearly_metadata,
        "quality_checks": {
            "expected_records": 390,
            "actual_records": len(records),
            "unique_keys": key_count,
            "missing_values": 0,
            "plausibility_range_ug_m3": [0, 200],
        },
    }
    write_outputs(records, metadata)
    print(json.dumps(metadata["quality_checks"], indent=2))


if __name__ == "__main__":
    main()
