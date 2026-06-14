"""GodBiao 数据模型 — 统一数据库访问层"""
import sqlite3
import os
import sys
from contextlib import contextmanager

# 从 config 导入统一 DB_PATH，消除重复定义
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import DB_PATH


@contextmanager
def get_db():
    """获取数据库连接，自动提交/关闭，启用外键约束"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ═══════════════════════════════════════════════════
# 表创建
# ═══════════════════════════════════════════════════

def init_all_tables():
    """创建所有表（评标 + 制标）"""
    _init_review_tables()
    _init_bid_tables()


def _init_review_tables():
    """评标系统表"""
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                created_at TEXT,
                req_text TEXT,
                bid_filename TEXT,
                bid_text TEXT,
                result_json TEXT,
                tokens_used INTEGER DEFAULT 0,
                cost_estimate REAL DEFAULT 0,
                model_used TEXT DEFAULT '',
                eval_mode TEXT DEFAULT 'combined'
            )
        """)
        # 兼容旧表列
        try:
            db.execute("ALTER TABLE jobs ADD COLUMN eval_mode TEXT DEFAULT 'combined'")
        except:
            pass


def _init_bid_tables():
    """制标系统表"""
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS bid_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS bid_product_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL REFERENCES bid_categories(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS bid_parameters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                line_id INTEGER NOT NULL REFERENCES bid_product_lines(id) ON DELETE CASCADE,
                param_type TEXT DEFAULT 'software',
                param_name TEXT NOT NULL,
                param_value TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS bid_product_models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                line_id INTEGER NOT NULL REFERENCES bid_product_lines(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        for idx in [
            "CREATE INDEX IF NOT EXISTS idx_bp_line ON bid_parameters(line_id)",
            "CREATE INDEX IF NOT EXISTS idx_bp_type ON bid_parameters(param_type)",
            "CREATE INDEX IF NOT EXISTS idx_bpl_cat ON bid_product_lines(category_id)",
        ]:
            db.execute(idx)


# ═══════════════════════════════════════════════════
# 通用数据访问辅助
# ═══════════════════════════════════════════════════

def _update_fields(db, table: str, row_id: int, data: dict, allowed: list):
    """通用 UPDATE：根据 allowed 字段列表更新"""
    for k in allowed:
        if k in data:
            db.execute(
                f"UPDATE {table} SET {k}=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (data[k], row_id),
            )


def _fetch_or_404(db, table: str, row_id: int):
    """通用 SELECT BY ID，不存在返回 None"""
    return db.execute(f"SELECT * FROM {table} WHERE id=?", (row_id,)).fetchone()


# ═══════════════════════════════════════════════════
# 评标数据操作
# ═══════════════════════════════════════════════════

def job_create(job_id: str, req_text: str, bid_filename: str, bid_text: str, eval_mode: str = "combined"):
    with get_db() as db:
        db.execute(
            "INSERT INTO jobs (id, created_at, req_text, bid_filename, bid_text, eval_mode) VALUES (?,datetime('now'),?,?,?,?)",
            (job_id, req_text, bid_filename, bid_text, eval_mode),
        )


def job_get(job_id: str):
    with get_db() as db:
        return db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()


def job_update(job_id: str, **kwargs):
    with get_db() as db:
        for k, v in kwargs.items():
            db.execute(f"UPDATE jobs SET {k}=? WHERE id=?", (v, job_id))


def job_trim(max_keep: int = 3):
    """保留最近 N 条记录，删除旧的"""
    with get_db() as db:
        db.execute(
            "DELETE FROM jobs WHERE id NOT IN (SELECT id FROM jobs ORDER BY created_at DESC LIMIT ?)",
            (max_keep,),
        )


def job_cleanup_old(days: int = 1):
    """删除超过 N 天的旧任务"""
    with get_db() as db:
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        db.execute("DELETE FROM jobs WHERE created_at < ?", (cutoff,))


# ═══════════════════════════════════════════════════
# 制标数据操作
# ═══════════════════════════════════════════════════

def bid_categories_all():
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT * FROM bid_categories ORDER BY sort_order, id"
        ).fetchall()]


def bid_categories_create(name: str, sort_order: int = 0):
    with get_db() as db:
        c = db.execute("INSERT INTO bid_categories (name, sort_order) VALUES (?,?)", (name, sort_order))
        return dict(db.execute("SELECT * FROM bid_categories WHERE id=?", (c.lastrowid,)).fetchone())


def bid_categories_update(cat_id: int, data: dict):
    with get_db() as db:
        _update_fields(db, "bid_categories", cat_id, data, ["name", "sort_order"])
        return _fetch_or_404(db, "bid_categories", cat_id)


def bid_categories_delete(cat_id: int):
    with get_db() as db:
        db.execute("DELETE FROM bid_categories WHERE id=?", (cat_id,))


def bid_product_lines_all(category_id: int = 0):
    with get_db() as db:
        q = """SELECT bpl.*,
               (SELECT COUNT(*) FROM bid_parameters WHERE line_id=bpl.id) as param_count,
               (SELECT COUNT(*) FROM bid_product_models WHERE line_id=bpl.id) as model_count
               FROM bid_product_lines bpl"""
        if category_id:
            rows = db.execute(q + " WHERE bpl.category_id=? ORDER BY bpl.sort_order, bpl.id", (category_id,)).fetchall()
        else:
            rows = db.execute(q + " ORDER BY bpl.sort_order, bpl.id").fetchall()
        return [dict(r) for r in rows]


def bid_product_lines_create(category_id: int, name: str, sort_order: int = 0):
    with get_db() as db:
        c = db.execute("INSERT INTO bid_product_lines (category_id, name, sort_order) VALUES (?,?,?)",
                       (category_id, name, sort_order))
        return dict(db.execute("SELECT * FROM bid_product_lines WHERE id=?", (c.lastrowid,)).fetchone())


def bid_product_lines_update(line_id: int, data: dict):
    with get_db() as db:
        _update_fields(db, "bid_product_lines", line_id, data, ["name", "sort_order"])
        return _fetch_or_404(db, "bid_product_lines", line_id)


def bid_product_lines_delete(line_id: int):
    with get_db() as db:
        db.execute("DELETE FROM bid_product_lines WHERE id=?", (line_id,))


def bid_parameters_all(line_id: int = 0, param_type: str = ""):
    with get_db() as db:
        q = "SELECT * FROM bid_parameters WHERE 1=1"
        params = []
        if line_id:
            q += " AND line_id=?"
            params.append(line_id)
        if param_type:
            q += " AND param_type=?"
            params.append(param_type)
        q += " ORDER BY param_type DESC, sort_order, id"
        return [dict(r) for r in db.execute(q, params).fetchall()]


def bid_parameters_create(line_id: int, param_name: str, param_type: str = "software",
                           param_value: str = "", sort_order: int = 0):
    with get_db() as db:
        if sort_order == 0:
            max_so = db.execute(
                "SELECT MAX(sort_order) FROM bid_parameters WHERE line_id=?", (line_id,)
            ).fetchone()[0] or 0
            sort_order = max_so + 1
        c = db.execute(
            "INSERT INTO bid_parameters (line_id, param_type, param_name, param_value, sort_order) VALUES (?,?,?,?,?)",
            (line_id, param_type, param_name, param_value, sort_order))
        return dict(db.execute("SELECT * FROM bid_parameters WHERE id=?", (c.lastrowid,)).fetchone())


def bid_parameters_update(param_id: int, data: dict):
    with get_db() as db:
        _update_fields(db, "bid_parameters", param_id, data, ["param_type", "param_name", "param_value", "sort_order"])
        return _fetch_or_404(db, "bid_parameters", param_id)


def bid_parameters_delete(param_id: int):
    with get_db() as db:
        db.execute("DELETE FROM bid_parameters WHERE id=?", (param_id,))


def bid_parameters_batch_create(line_id: int, rows_data: list, param_type: str = "software"):
    """批量导入参数"""
    with get_db() as db:
        max_so = db.execute(
            "SELECT MAX(sort_order) FROM bid_parameters WHERE line_id=?", (line_id,)
        ).fetchone()[0] or 0
        imported = 0
        for name, value in rows_data:
            max_so += 1
            db.execute(
                "INSERT INTO bid_parameters (line_id, param_type, param_name, param_value, sort_order) VALUES (?,?,?,?,?)",
                (line_id, param_type, name, value, max_so))
            imported += 1
        return imported


def bid_product_models_all(line_id: int = 0):
    with get_db() as db:
        q = "SELECT * FROM bid_product_models"
        if line_id:
            rows = db.execute(q + " WHERE line_id=? ORDER BY sort_order, id", (line_id,)).fetchall()
        else:
            rows = db.execute(q + " ORDER BY sort_order, id").fetchall()
        return [dict(r) for r in rows]


def bid_product_models_create(line_id: int, name: str, description: str = "", sort_order: int = 0):
    with get_db() as db:
        c = db.execute("INSERT INTO bid_product_models (line_id, name, description, sort_order) VALUES (?,?,?,?)",
                       (line_id, name, description, sort_order))
        return dict(db.execute("SELECT * FROM bid_product_models WHERE id=?", (c.lastrowid,)).fetchone())


def bid_product_models_update(model_id: int, data: dict):
    with get_db() as db:
        _update_fields(db, "bid_product_models", model_id, data, ["name", "description", "sort_order"])
        return _fetch_or_404(db, "bid_product_models", model_id)


def bid_product_models_delete(model_id: int):
    with get_db() as db:
        db.execute("DELETE FROM bid_product_models WHERE id=?", (model_id,))
