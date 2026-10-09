# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas", "odfpy"]
# ///
"""把「115年1-12月各區人口數.ods」轉成 work/population_115.csv（UTF-8 with BOM）。"""
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "115年1-12月各區人口數.ods"
OUT = ROOT / "work" / "population_115.csv"
COLUMNS = ["year", "month", "district", "households",
           "population_total", "population_male", "population_female"]
# 欄位位置（0 起算）：0 區別 | 1-2 里數 | 3-4 鄰數 | 5 戶數 | 6-8 人口數(合計,男,女)
COL_HH, COL_TOTAL, COL_M, COL_F = 5, 6, 7, 8
HEADER_ROWS = 3


def clean(s):
    return re.sub(r"\s+", "", str(s)).strip()


def check_header(df, sheet):
    """確認多層欄位標頭的位置沒有跑掉，避免把里數、鄰數當成人口數。"""
    expect = {(1, 0): "區別", (1, 5): "戶數", (1, 6): "人口數",
              (2, 6): "合計", (2, 7): "男", (2, 8): "女"}
    for (r, c), want in expect.items():
        got = clean(df.iat[r, c]) if pd.notna(df.iat[r, c]) else ""
        if got != want:
            raise ValueError(f"{sheet}: 標頭 ({r},{c}) 應為「{want}」，實際為「{got}」")


def to_int(v, sheet, district, name):
    if pd.isna(v):
        raise ValueError(f"{sheet} {district}: 必要欄位「{name}」為空白")
    f = float(v)
    if f != int(f):
        raise ValueError(f"{sheet} {district}: 「{name}」不是整數：{v}")
    return int(f)


def main():
    sheets = pd.read_excel(SRC, engine="odf", sheet_name=None, header=None)
    rows, skipped, totals = [], [], {}
    for sheet, df in sheets.items():
        m = re.fullmatch(r"(\d+)月", sheet.strip())
        if not m:
            continue
        month = int(m.group(1))
        check_header(df, sheet)
        body = df.iloc[HEADER_ROWS:]
        body = body[body[0].notna() & ~body[0].astype(str).str.startswith("說明")]
        vals = body[[COL_HH, COL_TOTAL, COL_M, COL_F]]
        if vals.isna().all().all():
            skipped.append(month)
            continue
        title = clean(df.iat[0, 0]) + clean(df.iat[0, 1])
        tm = re.search(r"(\d+)年(\d+)月", title)
        if not tm or int(tm.group(2)) != month:
            raise ValueError(f"{sheet}: 標題「{title}」與工作表月份不符")
        year = int(tm.group(1)) + 1911
        for _, r in body.iterrows():
            district = clean(r[0])
            rec = [to_int(r[c], sheet, district, n) for c, n in
                   [(COL_HH, "戶數"), (COL_TOTAL, "合計"), (COL_M, "男"), (COL_F, "女")]]
            if district == "總計":
                totals[(year, month)] = rec
                continue
            rows.append([year, month, district, *rec])

    out = pd.DataFrame(rows, columns=COLUMNS)
    dup = out[out.duplicated(["year", "month", "district"], keep=False)]
    if not dup.empty:
        raise ValueError(f"年月×行政區重複：\n{dup}")

    OUT.parent.mkdir(exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"略過沒有數值的月份：{skipped}")
    print(f"已輸出 {len(out)} 列 → {OUT}")

    # ---- 驗證 ----
    errs = []
    for (y, mo), g in out.groupby(["year", "month"]):
        if len(g) != 12:
            errs.append(f"{y}-{mo}: 行政區數 {len(g)} ≠ 12")
        bad = g[g.population_male + g.population_female != g.population_total]
        if not bad.empty:
            errs.append(f"{y}-{mo}: 男+女≠總 {list(bad.district)}")
        s = g[["households", "population_total", "population_male", "population_female"]].sum().tolist()
        if s != totals[(y, mo)]:
            errs.append(f"{y}-{mo}: 加總 {s} ≠ 總計列 {totals[(y, mo)]}")
    back = pd.read_csv(OUT, encoding="utf-8-sig")
    if not back.equals(out):
        errs.append("重新讀取的 CSV 與輸出不一致")
    if not OUT.read_bytes().startswith(b"\xef\xbb\xbf"):
        errs.append("CSV 缺少 UTF-8 BOM")
    if errs:
        print("驗證失敗：\n" + "\n".join(errs))
        sys.exit(1)
    print(f"驗證通過：{out.groupby(['year','month']).ngroups} 個月份 × 12 區，"
          "男女加總、總計列、重複、BOM、重新讀取皆一致")


if __name__ == "__main__":
    main()
