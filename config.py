"""
神奇阿标 (God Biao) 配置
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
DB_PATH = BASE_DIR / "godbiao.db"

# LLM API 配置 - 通过环境变量设置（不存储任何 API Key）
# 用户需通过前端设置页面上传自己的 API Key
LLM_CONFIG = {
    "primary": {
        "name": "default",
        "base_url": os.getenv("LLM_BASE_URL", "https://api.openai.com/v1/chat/completions"),
        "api_key": os.getenv("LLM_API_KEY", ""),
        "model": os.getenv("LLM_MODEL", "gpt-4o"),
    },
    "fallback": {
        "name": "fallback",
        "base_url": os.getenv("LLM_FALLBACK_BASE_URL", ""),
        "api_key": os.getenv("LLM_FALLBACK_API_KEY", ""),
        "model": os.getenv("LLM_FALLBACK_MODEL", ""),
    },
}

# 预置模型列表（不含 key，仅 base_url + model）—— 2026年6月最新版本
MODEL_PRESETS = [
    {
        "id": "deepseek",
        "name": "DeepSeek (深度求索)",
        "base_url": "https://api.deepseek.com/v1/chat/completions",
        "model": "deepseek-v4-pro",
        "models": ["deepseek-v4-pro", "deepseek-v4-flash"],
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o",
        "models": ["gpt-4o", "gpt-4o-mini", "o4-mini"],
    },
    {
        "id": "qwen",
        "name": "通义千问 (阿里云)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "model": "qwen3.7-max",
        "models": ["qwen3.7-max", "qwen3.7-plus"],
    },
    {
        "id": "baidu",
        "name": "文心一言 (百度)",
        "base_url": "https://qianfan.baidubce.com/v2/chat/completions",
        "model": "ernie-5.1",
        "models": ["ernie-5.1"],
    },
    {
        "id": "hunyuan",
        "name": "混元 (腾讯)",
        "base_url": "https://api.hunyuan.cloud.tencent.com/v1/chat/completions",
        "model": "hunyuan-hy3",
        "models": ["hunyuan-hy3"],
    },
    {
        "id": "doubao",
        "name": "豆包 (字节跳动)",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "model": "doubao-2.0-pro",
        "models": ["doubao-2.0-pro", "doubao-2.0-flash"],
    },
    {
        "id": "zhipu",
        "name": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "model": "glm-5.1",
        "models": ["glm-5.1", "glm-4.7-flash"],
    },
    {
        "id": "kimi",
        "name": "Kimi (月之暗面)",
        "base_url": "https://api.moonshot.cn/v1/chat/completions",
        "model": "kimi-k2.5",
        "models": ["kimi-k2.5"],
    },
    {
        "id": "minimax",
        "name": "MiniMax",
        "base_url": "https://api.minimax.chat/v1/text/chatcompletion_v2",
        "model": "minimax-m3:free",
        "models": ["minimax-m3:free"],
    },
    {
        "id": "sensenova",
        "name": "商汤 日日新",
        "base_url": "https://api.sensenova.cn/v1/llm/chat/completions",
        "model": "sensenova-6.7-flash-lite",
        "models": ["sensenova-6.7-flash-lite"],
    },
]

MAX_FILE_SIZE_MB = 50
AUTO_DELETE_MINUTES = 30
MAX_TOKENS_PER_RUN = 50000