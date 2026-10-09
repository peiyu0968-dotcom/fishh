# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas"]
# ///
"""把 work/population_115.csv 整理成網頁可直接用 <script> 載入的 docs/data.js。"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "work" / "population_115.csv"
OUT = ROOT / "docs" / "data.js"
FIELDS = ["year", "month", "district", "households",
          "population_total", "population_male", "population_female"]
NUM = FIELDS[3:]
PREFIX = "window.TAIPEI_POPULATION_DATA="


def load():
    df = pd.read_csv(SRC, encoding="utf-8-sig")
    missing = set(FIELDS) - set(df.columns)
    if missing:
        raise ValueError(f"CSV 缺少欄位：{sorted(missing)}")
    df = df[FIELDS]
    if df.isna().any().any():
        raise ValueError(f"來源有空白值，不補 0：\n{df[df.isna().any(axis=1)]}")
    dup = df[df.duplicated(["year", "month", "district"], keep=False)]
    if not dup.empty:
        raise ValueError(f"年月×行政區重複，需查明原因，不可加總：\n{dup}")
    for c in ["year", "month", *NUM]:
        df[c] = df[c].astype(int)
    return df.sort_values(["year", "month", "district"]).reset_index(drop=True)


def main():
    df = load()
    months = sorted({(int(y), int(m)) for y, m in zip(df.year, df.month)})
    data = {
        "meta": {
            "title": "臺北市各行政區戶籍人口數、戶數統計",
            "yearNote": "民國 115 年 ＝ 西元 2026 年",
            "dataType": "戶籍人口統計，不等同於實際居住人口；各月份為不同時間點的統計，不可相加為全年人口。",
            "months": [{"year": y, "month": m} for y, m in months],
            "fields": {
                "year": "西元年", "month": "月份（1–12）", "district": "行政區",
                "households": "戶數", "population_total": "總人口數",
                "population_male": "男性人口數", "population_female": "女性人口數",
            },
        },
        "rows": df.to_dict("records"),
    }
    text = PREFIX + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"已輸出 {OUT}（{OUT.stat().st_size:,} bytes，{len(df)} 筆）")

    # ---- 核對：重新讀 data.js，與來源 CSV 比對 ----
    raw = OUT.read_text(encoding="utf-8")
    assert raw.startswith(PREFIX) and raw.rstrip().endswith(";")
    js = json.loads(raw[len(PREFIX):].rstrip().rstrip(";"))
    jd = pd.DataFrame(js["rows"])[FIELDS]
    errs = []
    for (y, m), g in jd.groupby(["year", "month"]):
        if len(g) != 12:
            errs.append(f"{y}-{m}: 行政區數 {len(g)} ≠ 12")
    if (jd.population_male + jd.population_female != jd.population_total).any():
        errs.append("有列的男+女≠總人口")
    tot = jd.groupby("month").population_total.sum()
    for m, want in {1: 2437022, 9: 2418872}.items():
        if tot[m] != want:
            errs.append(f"{m} 月全市總人口 {tot[m]} ≠ {want}")
    src = pd.read_csv(SRC, encoding="utf-8-sig")
    a = jd.groupby("month")[NUM].sum()
    b = src.groupby("month")[NUM].sum()
    if not a.equals(b):
        errs.append(f"各月加總與 CSV 不一致：\n{a - b}")
    if [m["month"] for m in js["meta"]["months"]] != sorted(jd.month.unique().tolist()):
        errs.append("meta.months 與資料月份不一致")
    if errs:
        print("核對失敗：\n" + "\n".join(errs))
        sys.exit(1)
    print(f"核對通過：月份 {sorted(jd.month.unique().tolist())}，每月 12 區，男+女=總，"
          f"1 月 {tot[1]:,}、9 月 {tot[9]:,}，各月加總與 CSV 一致")


if __name__ == "__main__":
    main()
