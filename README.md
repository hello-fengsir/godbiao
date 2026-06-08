# 🦸 神奇阿标 (God Biao)

> AI 智能标书比对系统 — 上传投标文件 + 招标要求，自动逐条核查，防止标书出错

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-ready-blue.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## ✨ 功能亮点

- 📄 **多格式解析** — PDF / Word / 图片(OCR) / 纯文本全支持
- 🤖 **多模型对比** — 支持 DeepSeek / OpenAI / 通义千问等 10+ 大模型
- 📊 **逐项核查** — AI 自动提取招标要求，逐条比对投标响应
- 📝 **格式评估** — 检测标书格式问题（字体、排版、缺失章节等）
- 🔑 **关键信息提取** — 自动抓取金额、货期、资质等商务关键项
- 🔒 **零密钥存储** — API Key 仅存浏览器 localStorage，服务器不落盘
- 🐳 **一键部署** — Docker Compose 开箱即用

## 🚀 快速开始

### 前置要求

- Docker & Docker Compose
- 任意兼容 OpenAI API 的大模型 Key（如 DeepSeek / OpenAI / 通义千问）

### 部署

```bash
git clone https://github.com/hello-fengsir/godbiao.git
cd godbiao

# 可选：创建 .env 文件配置默认 API Key
cp .env.example .env
# 编辑 .env 填入你的 Key（也可不填，在前端页面设置）

docker compose up -d
```

打开浏览器访问 `http://localhost:8880`

### 使用流程

1. 首页点击 **⚙️ 模型设置** → 选择提供商 → 粘贴 API Key → 保存
2. 选择评标模式（合并/分离）
3. 上传投标文件 + 填写招标要求
4. 预览确认 → 开始 AI 比对
5. 查看结果：逐项满足度 + 格式评分 + 关键信息提取

📖 详细产品文档请参阅 [docs/PRODUCT.md](docs/PRODUCT.md)

## 📁 项目结构

```
godbiao/
├── app.py              # FastAPI 主服务
├── config.py           # 模型预置列表 & 配置
├── llm_client.py       # LLM 调用封装（比对/格式/关键信息）
├── parser.py           # 文件解析（PDF/Word/OCR/TXT）
├── templates/          # Jinja2 前端模板
│   ├── index.html      # 首页（上传 + 历史记录）
│   ├── review.html     # 预览页
│   └── result.html     # 结果页
├── static/             # 静态资源（favicon 等）
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

## 🎨 截图

*（运行 `docker compose up -d` 后访问 http://localhost:8880 体验）*

## ⚠️ 免责声明

本项目仅供学习交流使用，禁止用于任何商业用途。使用者须自行承担因使用本项目产生的任何法律风险与责任。

## 📄 License

MIT License © [峰Sir](https://github.com/hello-fengsir)
