# -*- coding: utf-8 -*-
"""
xlsx_reader —— 极简、零依赖(仅标准库)、健壮的 .xlsx 读取器。

为什么不用 openpyxl？
  赛狐/Temu 等系统导出的 xlsx 常写入一个错误的 <dimension ref="A1"/>，
  openpyxl 的 read_only 模式据此判断维度，导致只读到 1 行 1 列。
  这里直接流式解析 sheetN.xml，忽略维度声明，按真实 <row>/<c> 还原数据，
  因此对"带 505 张内嵌图片的 50MB 导出"也能只读表格、秒级完成。
"""
import zipfile
import re
import io
import xml.etree.ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _col_to_idx(ref):
    """'C7' -> 2 (0-based column index)."""
    m = re.match(r"([A-Z]+)", ref or "")
    if not m:
        return 0
    n = 0
    for ch in m.group(1):
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _read_shared_strings(z):
    try:
        data = z.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(data)
    out = []
    for si in root:
        # 一个 <si> 可能由多个 <r><t> 片段组成，需拼接
        out.append("".join(t.text or "" for t in si.iter(NS + "t")))
    return out


def _sheet_path_map(z):
    """返回 {显示名: worksheet xml 路径}，按 workbook 中的顺序。"""
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    rid_to_target = {}
    for r in rels:
        rid_to_target[r.get("Id")] = r.get("Target")
    result = []
    for sh in wb.iter(NS + "sheet"):
        name = sh.get("name")
        rid = sh.get(RNS + "id")
        target = rid_to_target.get(rid, "")
        if target and not target.startswith("xl/"):
            target = "xl/" + target.lstrip("/")
        result.append((name, target))
    return result


def read_rows(path, sheet=None, max_rows=None):
    """
    读取某个 sheet 的全部行。
      sheet: None=第一个sheet；int=按索引；str=按显示名。
    返回 list[list[str]]，第 0 行通常是表头。
    """
    z = zipfile.ZipFile(path)
    shared = _read_shared_strings(z)
    sheets = _sheet_path_map(z)

    if sheet is None:
        target = sheets[0][1]
    elif isinstance(sheet, int):
        target = sheets[sheet][1]
    else:
        target = next((t for n, t in sheets if n == sheet), None)
        if target is None:
            raise KeyError("sheet not found: %s (have %s)" % (sheet, [n for n, _ in sheets]))

    data = z.read(target)
    rows = []
    for _ev, el in ET.iterparse(io.BytesIO(data), events=("end",)):
        if el.tag == NS + "row":
            cells = {}
            maxi = -1
            for c in el.findall(NS + "c"):
                ci = _col_to_idx(c.get("r"))
                t = c.get("t")
                v = c.find(NS + "v")
                isel = c.find(NS + "is")
                if t == "s" and v is not None:
                    ix = int(v.text) if v.text else -1
                    val = shared[ix] if 0 <= ix < len(shared) else ""
                elif t == "inlineStr" and isel is not None:
                    val = "".join(tt.text or "" for tt in isel.iter(NS + "t"))
                elif v is not None:
                    val = v.text
                else:
                    val = ""
                cells[ci] = val
                maxi = max(maxi, ci)
            rows.append([cells.get(i, "") for i in range(maxi + 1)])
            el.clear()
            if max_rows and len(rows) >= max_rows:
                break
    return rows


def sheet_names(path):
    return [n for n, _ in _sheet_path_map(zipfile.ZipFile(path))]


def read_records(path, sheet=None, header_row=0):
    """把某 sheet 读成 list[dict]，用 header_row 那一行做表头。"""
    rows = read_rows(path, sheet=sheet)
    if not rows:
        return [], []
    header = [str(h).strip() for h in rows[header_row]]
    records = []
    for r in rows[header_row + 1:]:
        rec = {}
        for i, h in enumerate(header):
            if not h:
                continue
            rec[h] = r[i] if i < len(r) else ""
        records.append(rec)
    return header, records


if __name__ == "__main__":
    import sys
    p = sys.argv[1]
    print("sheets:", sheet_names(p))
    h, recs = read_records(p)
    print("header:", h)
    print("rows:", len(recs))
    for rec in recs[:2]:
        print(rec)
