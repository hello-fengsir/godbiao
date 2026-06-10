"""
LLM 客户端 - 调用大模型 API 进行标书比对
"""
import json
import httpx
from config import LLM_CONFIG

COMPARE_PROMPT = """你是一位专业的投标审核专家。请严格逐条比对「招标要求」和「投标文件」内容，输出 JSON 格式结果。

## 比对规则
1. 逐条检查招标要求中的每一项是否在投标文件中得到响应
2. 商务要求（价格、货期、资质等）和技术要求（规格、参数、配置等）分别比对
3. 状态判断：
   - "满足"：投标文件中明确响应且内容匹配
   - "部分满足"：有响应但不完全匹配
   - "不满足"：有响应但内容不符合要求
   - "缺失"：投标文件中完全未提及该项要求
4. 每条结果必须包含：要求原文引用、投标文件对应片段、判断理由

## 输出格式（严格 JSON）
```json
{
  "overall": "2-3句话整体评价，包括：总体响应率、主要风险点、是否建议投标",
  "items": [
    {
      "id": 1,
      "category": "商务要求",
      "requirement": "招标要求原文",
      "response": "投标文件对应内容",
      "status": "满足|部分满足|不满足|缺失",
      "reason": "判断理由",
      "suggestion": "修改建议（如需要）"
    }
  ]
}
```

## 招标要求
{requirements}

## 投标文件正文
{bid_content}
{mode_hint}

请严格按照上述 JSON 格式输出比对结果。"""


async def compare_bid(requirements: str, bid_content: str, provider: dict = None, eval_mode: str = "combined") -> dict:
    """调用 LLM 进行标书比对，返回结构化结果。
    
    provider: 运行时传入的配置 {'name', 'base_url', 'api_key', 'model'}
    若为 None，回退到 config.py 中的 LLM_CONFIG（环境变量方式）
    eval_mode: 'combined'（合并评标）或 'separate'（分离评标）
    """
    prompt = COMPARE_PROMPT.replace('{requirements}', requirements[:100000]).replace('{bid_content}', bid_content[:200000])
    # 注入评标模式提示
    if eval_mode == "separate":
        prompt = prompt.replace('{mode_hint}', '\n注意：本次为分离评标模式。投标文件分为「技术标」和「商务标」两部分，请分别针对技术要求和商务要求进行比对。')
    else:
        prompt = prompt.replace('{mode_hint}', '')

    # 优先使用运行时传入的 provider
    if provider and provider.get("api_key"):
        cfg = {
            "name": provider.get("name", "Custom"),
            "base_url": provider["base_url"],
            "api_key": provider["api_key"],
            "model": provider["model"],
        }
        return await call_llm(cfg, prompt)

    # 回退到 config.py 的环境变量方式
    for cfg_key in ["primary", "fallback"]:
        cfg = LLM_CONFIG[cfg_key]
        if not cfg["api_key"] and cfg_key == "fallback":
            continue

        try:
            result = await call_llm(cfg, prompt)
            return result
        except Exception as e:
            if cfg_key == "primary":
                print(f"[LLM] {cfg['name']} 失败: {e}, 尝试 fallback...")
                continue
            raise Exception(f"{cfg['name']} 也失败: {e}")

    raise Exception("所有 LLM 后端均不可用")


async def call_llm(cfg: dict, prompt: str) -> dict:
    """调用单个 LLM API"""
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    if cfg.get("extra_headers"):
        headers.update(cfg["extra_headers"])

    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": "你是一位专业投标审核专家。严格按 JSON 格式输出，不要添加任何解释性文字。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 16384,
    }

    timeout = httpx.Timeout(120.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(cfg["base_url"], headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    usage = data.get("usage", {})
    tokens = usage.get("total_tokens", 0)
    content = data["choices"][0]["message"]["content"]

    # 解析 JSON 响应
    parsed = parse_llm_json(content)
    parsed["tokens_used"] = tokens
    parsed["model"] = cfg["model"]
    return parsed


FORMAT_PROMPT = """你是一位专业的标书格式审核专家。请对以下投标文件进行「结构、格式与排版」评估，输出 JSON 格式结果。

## 评估维度
1. **结构完整性**：是否有封面、目录、章节划分、页码等基本要素
   - 目录识别要点：查找以下文本特征——
     * 连续的短行，每行末尾有数字（页码），如"第一章 xxx ...... 1"
     * 行首有层级编号（一、1. 1.1 (1) 等），行尾有"..."或空格+数字
     * 出现"目录"/"目次"/"Contents"/"Table of Contents"标题
     * 即使PDF文本提取后格式变乱，只要有编号+标题+页码的连续段落模式即可判定为目录
2. **章节逻辑**：章节安排是否合理，标题层级是否清晰，编号是否连续一致
3. **排版规范**：段落分隔是否清晰，列表/表格结构是否规范，内容是否易于阅读
4. **专业度**：用语是否正式规范，是否有错别字或语病，整体呈现是否专业
5. **合规性**：是否包含招标通常要求的必要章节（如公司简介、技术方案、报价单、资质证明等）

## 输出格式（严格 JSON）
```json
{
  "overall": "2-3句话整体格式评价：主要亮点、突出问题、改进建议",
  "score": 85,
  "items": [
    {
      "id": 1,
      "dimension": "结构完整性|章节逻辑|排版规范|专业度|合规性",
      "finding": "发现的具体问题或亮点",
      "severity": "严重|一般|建议|良好",
      "suggestion": "改进建议（如为良好则为肯定描述）"
    }
  ]
}
```

## 投标文件正文
{bid_content}

请严格按照上述 JSON 格式输出格式评估结果。"""


async def evaluate_format(bid_content: str, provider: dict = None) -> dict:
    """评估投标文件的格式与排版"""
    # 预检测目录结构并注入标记
    from parser import detect_toc
    toc_hint = detect_toc(bid_content)

    prompt = FORMAT_PROMPT.replace('{bid_content}', toc_hint + bid_content[:50000])

    if provider and provider.get("api_key"):
        cfg = {
            "name": provider.get("name", "Custom"),
            "base_url": provider["base_url"],
            "api_key": provider["api_key"],
            "model": provider["model"],
        }
    else:
        # 回退环境变量方式
        from config import LLM_CONFIG
        cfg = LLM_CONFIG["primary"]
        if not cfg["api_key"]:
            cfg = LLM_CONFIG["fallback"]

    return await call_llm(cfg, prompt)


KEY_INFO_PROMPT = """你是一位标书信息提取专家。请从以下投标文件中提取关键商务和技术信息，输出 JSON。

## 提取规则
1. **招标方信息**（从招标要求或文件头提取，找不到填"未提及"）：
   - 招标单位名称
   - 联系人/联系电话（如有）
2. **投标方信息**（从投标文件封面/公司简介提取，找不到填"未提及"）：
   - 投标单位名称
   - 联系人/联系电话（如有）
3. **商务关键项**（尽量找到具体数值/描述，找不到填"未提及"）：
   - 项目总金额/报价
   - 货期/交货期/工期
   - 付款方式
   - 报价明细（如有多项分项报价，简要列出）
4. **清单表格**（提取供货范围/设备清单/项目清单，找不到填"未提及"）：
   - 简要列出主要设备/服务的名称、型号、数量（不超过10行）
5. **技术关键项**：
   - 技术方案概述（一句话总结）
   - 技术方案完整度评估（完整/部分/缺失）
   - 实施方案概述（一句话总结）
   - 实施方案完整度评估（完整/部分/缺失）

## 输出格式（严格 JSON，不要任何额外文字）
```json
{
  "tenderer": {
    "name": "招标单位名称或未提及",
    "contact": "联系人信息或未提及"
  },
  "bidder": {
    "name": "投标单位名称或未提及",
    "contact": "联系人信息或未提及"
  },
  "business": {
    "total_amount": "金额或未提及",
    "delivery": "货期或未提及",
    "payment": "付款方式或未提及",
    "scope": "项目清单/供货范围摘要",
    "quotation_detail": "报价明细或未提及"
  },
  "item_table": "设备清单简要描述，每行格式：名称 | 型号 | 数量。如未提及填'未提及'",
  "technical": {
    "tech_summary": "技术方案一句话概述",
    "tech_completeness": "完整|部分|缺失",
    "impl_summary": "实施方案一句话概述",
    "impl_completeness": "完整|部分|缺失"
  }
}
```

## 投标文件正文
{bid_content}

请严格按照上述 JSON 格式输出提取结果。"""


async def extract_key_info(bid_content: str, provider: dict = None) -> dict:
    """提取投标文件中的关键商务/技术信息"""
    prompt = KEY_INFO_PROMPT.replace('{bid_content}', bid_content[:50000])

    if provider and provider.get("api_key"):
        cfg = {
            "name": provider.get("name", "Custom"),
            "base_url": provider["base_url"],
            "api_key": provider["api_key"],
            "model": provider["model"],
        }
    else:
        from config import LLM_CONFIG
        cfg = LLM_CONFIG["primary"]
        if not cfg["api_key"]:
            cfg = LLM_CONFIG["fallback"]

    return await call_llm(cfg, prompt)


async def test_api_key(base_url: str, api_key: str, model: str) -> dict:
    """测试 API Key 是否可用。发送最小请求验证连通性。"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 5,
    }
    timeout = httpx.Timeout(15.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(base_url, headers=headers, json=payload)
        if resp.status_code == 200:
            data = resp.json()
            return {"ok": True, "model": data.get("model", model)}
        else:
            detail = ""
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text[:200]
            return {"ok": False, "status": resp.status_code, "detail": str(detail)}


def parse_llm_json(content: str) -> dict:
    """从 LLM 响应中提取 JSON，多级容错 + 自动修复"""
    import re

    def is_valid_result(d: dict) -> bool:
        """判断是否有效结果：至少含 items 或其他业务字段"""
        if not isinstance(d, dict) or not d:
            return False
        valid_keys = {"items", "overall", "score", "tenderer", "bidder", "business", "technical", "tokens_used", "model"}
        return bool(set(d.keys()) & valid_keys)

    def try_parse(s: str) -> dict | None:
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return None

    # 1. 直接解析整段
    r = try_parse(content)
    if is_valid_result(r):
        return r

    # 2. 提取 ```json ... ``` 块
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
    if m:
        r = try_parse(m.group(1))
        if is_valid_result(r):
            return r

    # 3. 找第一个 { 到最后一个 } 之间的内容
    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        r = try_parse(content[start:end+1])
        if is_valid_result(r):
            return r

        # 4. JSON 修复：补全截断的 JSON
        truncated = content[start:end+1]
        r = try_repair_json(truncated)
        if is_valid_result(r):
            return r

    # 5. 尝试用正则提取 items 数组（仅用于内容比对结果）
    items_match = re.search(r'"items"\s*:\s*\[([\s\S]*?)\](?=\s*[,}])', content)
    if items_match:
        partial_items = _extract_partial_items(items_match.group(1))
        if partial_items:
            return {"items": partial_items, "tokens_used": 0, "model": "partial"}

    # 完全失败
    print(f"[parse_llm_json] 解析失败，原始响应前500字: {content[:500]}")
    return {
        "items": [{
            "id": 0, "category": "错误", "requirement": "解析失败",
            "response": content[:500], "status": "错误",
            "reason": "LLM 返回格式异常（可能被截断），请缩小标书或减少要求条目后重试",
            "suggestion": "建议：1) 拆分标书为更小段落 2) 只粘贴核心要求条目"
        }],
        "tokens_used": 0, "model": "unknown"
    }


def try_repair_json(s: str) -> dict | None:
    """尝试修复常见 JSON 问题：补全未闭合的括号、移除尾部逗号"""
    import re

    # 移除尾部多余逗号（在 ] 或 } 前的逗号）
    s = re.sub(r',\s*([}\]])', r'\1', s)

    # 补全未闭合的字符串（最后一项被截断）
    # 如果最后一个 " 后没有闭合，尝试补全
    if s.count('"') % 2 != 0:
        s += '"'

    # 计算未闭合的括号
    open_braces = s.count('{') - s.count('}')
    open_brackets = s.count('[') - s.count(']')

    # 补全括号
    s += ']' * open_brackets
    s += '}' * open_braces

    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    # 再尝试：截断到最后一个完整的 items 元素
    last_complete = _find_last_complete_item(s)
    if last_complete:
        try:
            return json.loads(last_complete)
        except json.JSONDecodeError:
            pass

    return None


def _find_last_complete_item(s: str) -> str | None:
    """截断 JSON 到最后一个完整的 items 元素"""
    import re
    # 找到 "items": [ 的位置
    m = re.search(r'"items"\s*:\s*\[', s)
    if not m:
        return None
    prefix = s[:m.end()]
    rest = s[m.end():]

    # 从后往前找 },{ 分隔符，每找到一个就尝试补全
    parts = re.split(r'\},\s*\{', rest)
    if len(parts) <= 1:
        return None

    # 取前 N-1 个完整元素 + 最后一个尽可能修复
    complete = parts[:-1]
    last = parts[-1]
    # 找最后一个完整的 }
    brace_idx = last.rfind('}')
    if brace_idx >= 0:
        complete.append(last[:brace_idx+1])
        return prefix + '},{'.join(complete) + ']}'

    return None


def _extract_partial_items(items_str: str) -> list:
    """从截断的 items 数组中尽可能提取完整的条目"""
    import re
    items = []
    # 按 },{ 分割
    parts = re.split(r'\},\s*\{', items_str)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if not part.startswith('{'):
            part = '{' + part
        if not part.endswith('}'):
            # 尝试补全
            part += '}' * (part.count('{') - part.count('}'))
        try:
            item = json.loads(part)
            if isinstance(item, dict):
                items.append(item)
        except json.JSONDecodeError:
            continue
    return items