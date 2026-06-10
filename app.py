"""
神奇阿标 (God Biao) 主应用
"""
import json
import uuid
import sqlite3
import os
import shutil
import glob
from datetime import datetime, timedelta
from io import BytesIO

from fastapi import FastAPI, File, Form, UploadFile, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from config import BASE_DIR, UPLOAD_DIR, DB_PATH, MODEL_PRESETS
from parser import parse_file
from llm_client import compare_bid, evaluate_format, extract_key_info, test_api_key
from models import init_all_tables, job_create, job_get, job_update, job_trim, job_cleanup_old
from bid_api import router as bid_router

# ── App 初始化 ──

app = FastAPI(title="神奇阿标 - God Biao")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
UPLOAD_DIR.mkdir(exist_ok=True)

# 挂载制标 API
app.include_router(bid_router)

# 初始化所有表
init_all_tables()

# ── 全局状态 ──

_compare_progress: dict = {}  # job_id → {phase, content_done, format_done, started_at, error}
MAX_HISTORY = 3


# ═══════════════════════════════════════════════════
# 页面路由
# ═══════════════════════════════════════════════════

@app.get("/review", response_class=HTMLResponse)
async def review_page(request: Request):
    cleanup_uploads()
    tpl = templates.env.get_template("index.html")
    return HTMLResponse(tpl.render({"request": request}))


@app.get("/")
async def root():
    return RedirectResponse(url="/review")


@app.get("/bidding", response_class=HTMLResponse)
def bidding_page(request: Request):
    tpl = templates.env.get_template("bidding.html")
    return HTMLResponse(tpl.render({"request": request}))


@app.get("/result/{job_id}", response_class=HTMLResponse)
async def result_page(request: Request, job_id: str):
    row = job_get(job_id)
    if not row:
        return HTMLResponse("<h2>任务未找到</h2>", 404)
    tpl = templates.env.get_template("result.html")
    return HTMLResponse(tpl.render({"request": request, "job": dict(row)}))


# ═══════════════════════════════════════════════════
# 评标 API
# ═══════════════════════════════════════════════════

@app.post("/upload")
async def upload(
    request: Request,
    bid_file: UploadFile = File(None),
    tech_file: UploadFile = File(None),
    biz_file: UploadFile = File(None),
    requirements: str = Form(""),
    req_file: UploadFile = File(None),
    eval_mode: str = Form("combined"),
):
    bid_text = ""
    bid_filename = ""

    if eval_mode == "separate":
        tech_text = ""
        biz_text = ""
        if tech_file and tech_file.filename:
            tech_text = await parse_file(tech_file)
        if biz_file and biz_file.filename:
            biz_text = await parse_file(biz_file)
        if not tech_text and not biz_text:
            tpl = templates.env.get_template("index.html")
            return HTMLResponse(tpl.render({"request": request, "error": "请至少上传技术标或商务标文件"}))
        bid_text = ""
        if tech_text:
            bid_text += "=== 技术标 ===\n" + tech_text + "\n\n"
        if biz_text:
            bid_text += "=== 商务标 ===\n" + biz_text
        bid_filename = (tech_file.filename if tech_file else "") + (" + " + biz_file.filename if biz_file else "")
    else:
        if not bid_file or not bid_file.filename:
            tpl = templates.env.get_template("index.html")
            return HTMLResponse(tpl.render({"request": request, "error": "请上传投标文件"}))
        bid_text = await parse_file(bid_file)
        bid_filename = bid_file.filename

    req_text = requirements.strip()
    if req_file:
        req_text += "\n" + (await parse_file(req_file))

    if not bid_text:
        tpl = templates.env.get_template("index.html")
        return HTMLResponse(tpl.render({"request": request, "error": "无法解析投标文件，请检查文件格式（支持 PDF/Word/图片）"}))

    job_id = str(uuid.uuid4())[:8]
    job_create(job_id, req_text, bid_filename, bid_text, eval_mode)
    job_trim(MAX_HISTORY)

    tpl = templates.env.get_template("review.html")
    return HTMLResponse(tpl.render({
        "request": request,
        "job_id": job_id,
        "req_text": req_text,
        "bid_text_preview": bid_text,
        "bid_filename": bid_filename,
        "bid_full_len": len(bid_text),
        "req_full_len": len(req_text),
        "eval_mode": eval_mode,
    }))


@app.get("/api/model-presets")
async def get_model_presets():
    return MODEL_PRESETS


@app.get("/api/jobs")
async def list_jobs():
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT id, created_at, bid_filename, model_used, eval_mode FROM jobs ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))
        conn.commit()
    return {"ok": True}


@app.post("/api/test-key")
async def test_key(data: dict):
    base_url = data.get("base_url", "")
    api_key = data.get("api_key", "")
    model = data.get("model", "")
    if not base_url or not api_key or not model:
        return JSONResponse({"error": "请填写完整信息"}, 400)
    ok, msg = await test_api_key(base_url, api_key, model)
    return {"ok": ok, "message": msg}


@app.post("/compare/{job_id}")
async def compare(job_id: str):
    row = job_get(job_id)
    if not row:
        return JSONResponse({"error": "任务不存在"}, 404)

    _compare_progress[job_id] = {"phase": "content", "content_done": 0, "format_done": 0, "started_at": datetime.now().isoformat(), "error": None}

    try:
        result = await compare_bid(row["req_text"], row["bid_text"], row["eval_mode"], _compare_progress, job_id)
        job_update(job_id, result_json=json.dumps(result, ensure_ascii=False))
        _compare_progress[job_id]["phase"] = "done"
        return {"ok": True, "job_id": job_id}
    except Exception as e:
        _compare_progress[job_id]["phase"] = "error"
        _compare_progress[job_id]["error"] = str(e)
        return JSONResponse({"error": str(e)}, 500)


@app.get("/api/compare-status/{job_id}")
async def compare_status(job_id: str):
    info = _compare_progress.get(job_id, {})
    return {
        "phase": info.get("phase", "unknown"),
        "content_done": info.get("content_done", 0),
        "format_done": info.get("format_done", 0),
        "error": info.get("error"),
    }


# ═══════════════════════════════════════════════════
# 清理函数
# ═══════════════════════════════════════════════════

def cleanup_uploads():
    """清理上传目录 + 旧任务"""
    for f in glob.glob(str(UPLOAD_DIR / "*")):
        try:
            os.remove(f) if os.path.isfile(f) else shutil.rmtree(f)
        except Exception:
            pass
    job_cleanup_old(days=1)
    _compare_progress.clear()


# ═══════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8880)