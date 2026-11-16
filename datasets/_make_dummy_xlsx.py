"""Build a one-sheet workbook and run it through the upload reader."""

from pathlib import Path

from openpyxl import Workbook

from ingest.reader import _read_xlsx, header_hits

out = Path(__file__).resolve().parent / "dummy_header_hits.xlsx"
wb = Workbook()
ws = wb.active
ws.title = "Shipments"
ws.append(["order_id", "sub_category", "sales"])
ws.append([1001, "Phones", 327782.45])
ws.append([1002, "Fasteners", 3001.96])
ws.append([1003, "Chairs", 322822.73])
wb.save(out)
wb.close()

rows = _read_xlsx(out)
print(f"file: {out}")
print(f"rows: {len(rows)}")
print(f"header: {rows[0][1]}")
print(f"header_hits: {header_hits(rows)}")
