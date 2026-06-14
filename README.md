# 🦸 神奇阿标 (God Biao)

> AI 智能招投标工具 — 评标：上传标书自动逐条核查 · 制标：参数化管理一键导出

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-ready-blue.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-v2.1-3b82f6.svg)](https://github.com/hello-fengsir/godbiao/releases/tag/v2.1)

---

## 🆕 v2.1 更新内容

| 模块 | 优化 |
|---|---|
| 📊 **评标结果增强** | 结果页完整展示三路 AI 分析：内容逐项比对（满足/部分满足/不满足百分比统计）+ 格式评估打分 + 关键信息提取（双方信息对比卡片） |
| 🟢 **模型状态检测** | 首页 header 新增模型有效性指示器：无 Key → 待检测 → 🟢已验证 三种状态自动切换，绿色徽章显示当前模型名 |
| 📱 **移动端适配** | 全站响应式：768px 断点，汉堡菜单 + 抽屉侧边栏 + 自适应布局，手机端可正常使用 |
| ⏳ **评标进度优化** | 三步串行（内容比对 → 格式评估 → 关键信息）替代并行，步骤描述实时更新，ETA 估算更准确 |
| 🔑 **前端 Key 透传** | 评标 API Key 从前端请求 header 读取，服务器零密钥存储，多用户互不干扰 |
| 🔒 **安全脱敏** | 全面清理仓库：移除 docstring/placeholder 中厂商名，数据文件型号脱敏处理 |
| 🏗️ **代码健壮性** | 结果页渲染容错（JSON 解析失败不崩溃）、model-presets API 兼容数组/对象两种返回格式 |

---

## ✨ v2.0 新增功能

| 模块 | 功能 |
|---|---|
| 🏗️ **制标工具** | 技术参数管理系统 — 类别 → 产品线 → 参数 三级联动，支持 79+ 条参数快速录入 |
| 📊 **Excel 批量导入** | 支持 `.xlsx` 拖拽上传，按产品线批量导入技术参数 |
| 📥 **Word 一键导出** | 按 [分类] 自动分组，生成规范技术参数表（2 列：序号 / 名称） |
| 🏷️ **型号管理** | 每个产品线支持多型号管理（名称 + 规格描述） |
| 🗂️ **分类管理** | 自定义类别，级联管理产品线与参数 |
| 🔧 **代码重构** | 三文件架构拆分（`app.py` 评标 + `bid_api.py` 制标 + `models.py` 数据层），零硬编码 |

---

## ✨ 原有功能 (v1.x)

- 📄 **多格式解析** — PDF / Word / 图片(OCR) / 纯文本全支持
- 🤖 **多模型对比** — 支持 DeepSeek / OpenAI / 通义千问等 10+ 大模型
- 📊 **逐项核查** — AI 自动提取招标要求，逐条比对投标响应（三路并行分析）
- 📝 **格式评估** — 检测标书格式问题（字体、排版、缺失章节等）
- 🔑 **关键信息提取** — 自动抓取金额、货期、资质等商务关键项
- 🔒 **零密钥存储** — API Key 仅存浏览器 localStorage，服务器不落盘
- 🐳 **一键部署** — Docker Compose 开箱即用

---

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

### 两大工具

| 工具 | 路径 | 用途 |
|---|---|---|
| 📋 **评标** | `/review` | 上传投标文件 + 招标要求 → AI 逐项核查 |
| 🏗️ **制标** | `/bidding` | 产品线 → 参数管理 → 一键导出 Word 技术参数表 |

### 评标流程

1. 首页点击 **⚙️ 模型设置** → 选择提供商 → 粘贴 API Key → 保存
2. 首页点击 **🔍 检测模型** 验证连接（通过后 header 显示 🟢 模型名）
3. 选择评标模式（合并/分离）
4. 上传投标文件 + 填写招标要求
5. 预览确认 → 开始 AI 比对
6. 查看结果：逐项满足度统计 + 格式评分 + 关键信息提取

### 制标流程

1. 切换到 **📋 制标** 页面
2. 选择 / 新建类别和产品线
3. 📥 导入参数（Excel 批量导入）或 + 逐条添加
4. 编辑参数名称和竞争分析备注（仅页面可见）
5. 👁 预览 → 📥 导出 Word

📖 详细产品文档请参阅 [docs/PRODUCT.md](docs/PRODUCT.md)

---

## 📁 项目结构

```
godbiao/
├── app.py              # 主入口 + 评标路由（FastAPI）
├── bid_api.py          # 制标路由（APIRouter, /api/bid/*）
├── models.py           # 统一数据层（评标 + 制标共 5 张表）
├── config.py           # 模型预置列表 & 配置
├── llm_client.py       # LLM 调用封装（三步串行：比对/格式/关键信息）
├── parser.py           # 文件解析（PDF/Word/OCR/TXT）
├── import_products.py  # Excel → SQLite 批量导入工具
├── templates/
│   ├── index.html      # 评标首页（上传 + 模型检测 + 历史记录 + 移动端适配）
│   ├── bidding.html    # 制标页面（类别→产品线→参数管理）
│   ├── review.html     # 预览页（进度条 + ETA）
│   └── result.html     # 结果页（逐项核查 + 格式评分 + 关键信息）
├── static/
├── docker-compose.yml
├── Dockerfile
└── .env.example
```

## 🗃️ 数据模型

```
bid_categories (类别)
  └── bid_product_lines (产品线)
        ├── bid_parameters (技术参数, hardware/software)
        └── bid_product_models (型号)
```

所有 CRUD 通过 RESTful API 暴露，前端完全数据驱动。

---

## 🎨 截图

### 评标首页 — 模型状态检测 + 上传投标文件

<p align="center">
  <img src="screenshots/homepage.png" width="800" alt="评标首页">
</p>

### 制标工具 — 类别→产品线→参数管理 + 一键导出 Word

<p align="center">
  <img src="screenshots/bidding.png" width="800" alt="制标工具">
</p>

### 模型设置 — 支持 10+ 大模型

<p align="center">
  <img src="screenshots/model-settings.png" width="800" alt="模型设置">
</p>

---

## ☕ 赞赏

如果这个项目对你有帮助，欢迎请作者喝杯咖啡~

<p align="center">
  <img src="static/zanshang.jpg" width="300" alt="赞赏码">
</p>

## ⚠️ 免责声明

本项目仅供学习交流使用，禁止用于任何商业用途。使用者须自行承担因使用本项目产生的任何法律风险与责任。

## 📄 License

MIT License © [峰Sir](https://github.com/hello-fengsir)
