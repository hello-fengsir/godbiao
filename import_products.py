"""导入深信服产品参数到数据库"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import openpyxl
except ImportError:
    print("需要安装 openpyxl: pip install openpyxl")
    sys.exit(1)

from models import get_db, init_product_tables

EXCEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "product_data.xlsx")

def import_products():
    # 先确保表存在
    init_product_tables()

    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
    with get_db() as db:
        db.execute("DELETE FROM products")
        count = 0
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = list(ws.iter_rows(min_row=2, values_only=True))
            for row in rows:
                if not row:
                    continue
                # 兼容两种格式：产品名/型号/参数/备注 或 产品名称/产品参数
                vals = [str(c).strip() if c else "" for c in row]
                if len(vals) >= 3 and vals[1]:
                    name, model, specs = vals[0], vals[1], vals[2]
                    notes = vals[3] if len(vals) > 3 else ""
                elif len(vals) >= 2 and vals[0]:
                    name, model, specs = vals[0], "", vals[1]
                    notes = vals[2] if len(vals) > 2 else ""
                else:
                    continue
                if model or name:
                    db.execute(
                        "INSERT INTO products (category, name, model, specs, notes) VALUES (?,?,?,?,?)",
                        (sheet_name, name, model, specs, notes)
                    )
                    count += 1
        print(f"导入完成：{count} 条产品记录")

if __name__ == "__main__":
    import_products()
