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

    job = dict(row)
    result_data = {}
    if job.get("result_json"):
        try:
            result_data = json.loads(job["result_json"])
        except:
            pass

    # 提取内容比对结果
    results = result_data.get("items", result_data.get("results", []))
    total = len(results)
    full_pass = sum(1 for r in results if r.get("status") == "满足")
    partial = sum(1 for r in results if r.get("status") == "部分满足")
    failed = sum(1 for r in results if r.get("status") in ("不满足", "缺失"))
    full_pass_pct = round(full_pass / total * 100) if total else 0
    partial_pct = round(partial / total * 100) if total else 0
    failed_pct = round(failed / total * 100) if total else 0

    # 提取格式评估结果
    fmt_eval = result_data.get("format_eval", {})
    fmt_score = fmt_eval.get("score", 0)
    fmt_overall = fmt_eval.get("overall", "")
    fmt_items = fmt_eval.get("items", [])

    # 提取关键信息
    key_info = result_data.get("key_info", {})

    tpl = templates.env.get_template("result.html")
    return HTMLResponse(tpl.render({
        "request": request,
        "job": job,
        "bid_filename": job.get("bid_filename", ""),
        "model": job.get("model_used", result_data.get("model", "")),
        "tokens": job.get("tokens_used", result_data.get("tokens_used", 0)),
        "eval_mode": job.get("eval_mode", "combined"),
        "overall": result_data.get("overall", ""),
        "results": results,
        "total": total,
        "full_pass": full_pass,
        "full_pass_pct": full_pass_pct,
        "partial": partial,
        "partial_pct": partial_pct,
        "failed": failed,
        "failed_pct": failed_pct,
        "fmt_score": fmt_score,
        "fmt_overall": fmt_overall,
        "fmt_items": fmt_items,
        "key_info": key_info,
    }))


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
    result = await test_api_key(base_url, api_key, model)
    ok = result.get("ok", False)
    msg = result.get("model", result.get("detail", ""))
    return {"ok": ok, "message": msg}


@app.post("/compare/{job_id}")
async def compare(job_id: str, request: Request):
    row = job_get(job_id)
    if not row:
        return JSONResponse({"error": "任务不存在"}, 404)

    # 从前端 headers 读取 API Key 配置
    provider = None
    api_key = request.headers.get("X-API-Key", "")
    api_base_url = request.headers.get("X-API-Base-Url", "")
    api_model = request.headers.get("X-API-Model", "")
    api_provider_name = request.headers.get("X-API-Provider-Name", "")
    if api_provider_name:
        try:
            from urllib.parse import unquote
            api_provider_name = unquote(api_provider_name)
        except:
            pass
    if api_key and api_base_url and api_model:
        provider = {
            "name": api_provider_name or "Custom",
            "base_url": api_base_url,
            "api_key": api_key,
            "model": api_model,
        }

    _compare_progress[job_id] = {
        "phase": "content", "content_done": 0, "format_done": 0,
        "started_at": datetime.now().isoformat(), "error": None,
        "step": "正在逐条比对招标要求与投标响应..."
    }

    total_tokens = 0

    try:
        # 步骤1: 内容逐条比对
        _compare_progress[job_id]["step"] = "📋 正在逐条比对内容..."
        content_result = await compare_bid(row["req_text"], row["bid_text"], provider, row["eval_mode"])
        total_tokens += content_result.get("tokens_used", 0)
        _compare_progress[job_id]["content_done"] = 1
        _compare_progress[job_id]["phase"] = "format"
        _compare_progress[job_id]["step"] = "📐 正在评估格式与排版..."

        # 步骤2: 格式评估
        format_result = await evaluate_format(row["bid_text"], provider)
        total_tokens += format_result.get("tokens_used", 0)
        _compare_progress[job_id]["format_done"] = 1
        _compare_progress[job_id]["step"] = "📊 正在提取关键信息..."

        # 步骤3: 提取关键信息
        key_info_result = await extract_key_info(row["bid_text"], provider)
        total_tokens += key_info_result.get("tokens_used", 0)
        _compare_progress[job_id]["step"] = "✅ 正在生成报告..."

        # 合并结果
        model_name = content_result.get("model", "") or (provider["model"] if provider else "")
        combined = {
            "overall": content_result.get("overall", ""),
            "items": content_result.get("items", []),
            "format_eval": {
                "overall": format_result.get("overall", ""),
                "score": format_result.get("score", 0),
                "items": format_result.get("items", []),
            },
            "key_info": key_info_result,
            "tokens_used": total_tokens,
            "model": model_name,
        }

        job_update(job_id, result_json=json.dumps(combined, ensure_ascii=False))
        job_update(job_id, model_used=model_name)
        job_update(job_id, tokens_used=total_tokens)
        _compare_progress[job_id]["phase"] = "done"
        _compare_progress[job_id]["step"] = "✅ 分析完成"
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
        "step": info.get("step", ""),
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