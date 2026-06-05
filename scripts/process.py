#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import argparse
from uuid import uuid4

try:
    from coze_workload_identity import requests
except ImportError:
    import requests

import pdfplumber


# =========================
# Ark config
# =========================
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
ARK_MODEL = "ep-20250228191006-w8qdh"


# =========================
# Utils
# =========================
def log(msg: str):
    print(msg, flush=True)


def ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)
    return p


def safe_write(path: str, content: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content or "")


def load_dotenv(path: str):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def get_ark_api_key():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    load_dotenv(os.path.join(base_dir, ".env"))

    for key in ("ARK_API_KEY", "VOLC_ARK_API_KEY"):
        value = os.getenv(key)
        if value:
            return value

    raise ValueError(
        "Missing ARK API key. Set ARK_API_KEY or VOLC_ARK_API_KEY, "
        "or run: python scripts/configure_secrets.py 'ARK_API_KEY=your-api-key'"
    )


def split_text(text: str, max_bytes: int = 65000):
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        cand = (cur + "\n\n" + p).strip() if cur else p
        if len(cand.encode("utf-8")) <= max_bytes:
            cur = cand
        else:
            if cur:
                chunks.append(cur)
            cur = p
    if cur:
        chunks.append(cur)
    return chunks


def extract_json_array_loose(text: str):
    """
    从可能夹杂杂质的输出中尽量提取 JSON 数组
    """
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"```(?:json|javascript|js|html|txt)?", "", t, flags=re.I).replace("```", "").strip()

    l = t.find("[")
    r = t.rfind("]")
    if l >= 0 and r > l:
        candidate = t[l : r + 1].strip()
        try:
            return json.loads(candidate)
        except Exception:
            # remove trailing commas
            candidate2 = re.sub(r",\s*([\]\}])", r"\1", candidate)
            try:
                return json.loads(candidate2)
            except Exception:
                return None
    return None


# =========================
# PDF -> text
# =========================
def pdf_to_text_pages(pdf_path: str):
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            txt = page.extract_text() or ""
            pages.append((i, txt.strip()))
    return pages


def build_full_text(pages):
    out = []
    for i, txt in pages:
        if txt:
            out.append(f"--- Page {i} ---\n{txt}")
        else:
            out.append(f"--- Page {i} ---\n[NO TEXT EXTRACTED]")
    return "\n\n".join(out)


# =========================
# Filter financial pages
# =========================
def filter_financial_pages_from_pages(pages):
    number_pattern = re.compile(r"\d[\d,]*\.?\d*")
    keywords = [
        "元", "万元", "亿元", "%", "每股收益", "EPS",
        "净利润", "利润", "收入", "营收", "营业收入",
        "资产", "负债", "现金流", "毛利率", "ROE", "EBIT", "EBITDA"
    ]

    filtered = []
    for i, txt in pages:
        if not txt:
            continue
        nums = number_pattern.findall(txt)
        hit_kw = any(k in txt for k in keywords)
        if len(nums) >= 6 or (len(nums) >= 3 and hit_kw):
            filtered.append((i, txt))
    return filtered


def build_filtered_text(filtered_pages):
    out = []
    for i, txt in filtered_pages:
        out.append(f"--- Page {i} ---\n{txt}")
    return "\n\n".join(out)


# =========================
# ARK API helpers (using requests)
# =========================
def ark_api_call(api_key: str, messages: list, stream: bool = True, max_tokens: int = None):
    """调用火山引擎 ARK API"""
    base_url = os.getenv("ARK_BASE_URL", ARK_BASE_URL).rstrip("/")
    model = os.getenv("ARK_LLM_MODEL", ARK_MODEL)
    url = f"{base_url}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    data = {
        "model": model,
        "messages": messages,
        "stream": stream
    }
    
    if max_tokens is not None:
        data["max_tokens"] = max_tokens

    if stream:
        response = requests.post(url, headers=headers, json=data, stream=True)
        response.raise_for_status()
        
        buf = []
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    line = line[6:]
                if line == '[DONE]':
                    break
                try:
                    chunk = json.loads(line)
                    if 'choices' in chunk and len(chunk['choices']) > 0:
                        delta = chunk['choices'][0].get('delta', {})
                        content = delta.get('content', '')
                        if content:
                            buf.append(content)
                except Exception:
                    pass
        return "".join(buf).strip()
    else:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content'].strip()


def validate_chart_item(item: dict) -> bool:
    """
    验证图表组件是否有效
    返回 True 表示有效，False 表示应该过滤掉
    """
    if not item or not isinstance(item, dict):
        return False
    
    # 检查必需字段
    if 'type' not in item or not item['type']:
        return False
    
    if 'content' not in item:
        return False
    
    content = item['content']
    
    # 检查 content 是否为空或全是空白
    if isinstance(content, str):
        if not content.strip():
            return False
    elif isinstance(content, dict):
        # 检查字典中是否有实际内容
        has_content = any(
            bool(v) if isinstance(v, str) else v is not None
            for v in content.values()
        )
        if not has_content:
            return False
    
    # 检查 visualization_slot
    if 'visualization_slot' in item:
        vis_slot = item['visualization_slot']
        if isinstance(vis_slot, dict) and 'chart_code' in vis_slot:
            chart_code = vis_slot['chart_code']
            if isinstance(chart_code, str) and not chart_code.strip():
                return False
    
    # 检查 interpretation
    if 'interpretation' in item:
        interp = item['interpretation']
        if isinstance(interp, dict) and 'content' in interp:
            interp_content = interp['content']
            if isinstance(interp_content, str) and not interp_content.strip():
                return False
    
    return True


def filter_valid_charts(charts: list) -> list:
    """
    过滤掉无效的图表组件
    """
    valid_charts = []
    filtered_count = 0
    
    for item in charts:
        if validate_chart_item(item):
            valid_charts.append(item)
        else:
            filtered_count += 1
            log(f"  [Filter] Removed empty/invalid chart component")
    
    if filtered_count > 0:
        log(f"  [Filter] Removed {filtered_count} invalid chart(s), kept {len(valid_charts)} valid chart(s)")
    
    return valid_charts


def extract_data_with_ark(filtered_text: str, api_key: str):
    if not filtered_text.strip():
        return []

    prompt_data = """
你是一名资深的财务分析师。
从文档中提取结构化数据和关键观点，并严格按照 JSON 数组格式输出。

输出格式（必须是有效的 JSON）：
[
  {
    "type": "structured_data",
    "content": {
      "field1": "value1",
      "field2": "value2",
      "field3": "value3",
      "field4": "value4",
      "field5": "value5"
    }
  },
  {
    "type": "opinion_data",
    "content": {
      "analyst": "分析师姓名（或组织）",
      "opinion": "该部分的关键见解"
    }
  }
]

规则：
- 必须使用中文输出。
- 不要添加任何解释文本。
- 如果某个字段不存在，请保持为空字符串。
- 优先使用带单位的数字。
"""

    chunks = split_text(filtered_text, max_bytes=65000)
    total = len(chunks)
    all_items = []

    for idx, chunk in enumerate(chunks, start=1):
        log(f"[5] Extracting data with ARK ({idx}/{total}) ...")
        messages = [
            {"role": "system", "content": prompt_data},
            {"role": "user", "content": chunk}
        ]
        raw = ark_api_call(api_key, messages, stream=True)
        arr = extract_json_array_loose(raw)
        if isinstance(arr, list) and arr:
            all_items.extend(arr)
        else:
            all_items.append({"type": "raw_chunk_output", "content": {"text": raw[:8000]}})

    return all_items


def generate_chart_json(extracted_items, api_key: str):
    log("[7] Starting chart design ...")

    prompt_chart = """
你是一名可视化设计师。

目标：
为结构化数据和观点数据设计可视化方案。

规则：
1) 必须输出有效的 JSON 数组，不要额外文本。
2) 使用 ECharts / Mermaid / Markdown 表格 / 纯文本，按需选择。
3) 每个项目必须包含：
   - "type"
   - "content"
   - "visualization_slot": { "chart_code": "..." }
   - "interpretation": { "content": "<div class=\\"interpretation\\"><strong>智能洞察</strong>: ...</div>" }
4) 避免标签重叠，保持图表可读性。
5) 必须使用中文输出。
6) chart_code 应该是所选可视化方式的可运行代码片段：
   - 如果是 ECharts（包括词云图）：
     * 对于词云图，必须包含完整的 HTML 和 JavaScript 代码，包括 echarts-wordcloud 扩展库的引用
     * echarts-wordcloud CDN: <script src="https://cdn.jsdelivr.net/npm/echarts-wordcloud@2/dist/echarts-wordcloud.min.js"></script>
     * 词云图的 option 中 series.type 必须是 'wordCloud'（注意大小写）
     * 必须包含必要的配置项：shape、sizeRange、rotationRange、gridSize、textStyle、data
   - 如果是 ECharts（标准图表）：提供标准的 ECharts option 对象（JSON 格式）
   - 如果是 Mermaid：提供 mermaid 定义字符串。
   - 如果是 Markdown：提供 markdown 表格字符串。
7) 不要重复图表。优先选择 6个左右 高价值可视化模块。
8) 重要：所有图表的 content、chart_code、interpretation 等字段都必须有实际内容，不能是空白或 null。
"""

    messages = [
        {"role": "system", "content": prompt_chart},
        {"role": "user", "content": json.dumps(extracted_items, ensure_ascii=False)}
    ]
    raw = ark_api_call(api_key, messages, stream=True)
    arr = extract_json_array_loose(raw)
    if isinstance(arr, list):
        log("[8] Chart design completed.")
        return arr

    log("[8] Chart design completed (fallback as raw).")
    return [{"type": "raw_chart_output", "content": {"text": raw}}]


def generate_html_from_json(chart_items, api_key: str):
    log("[9] Starting page design ...")

    prompt_html = """
你是一名专业的网页设计师。
根据给定的 JSON 数组生成完整的 HTML5 页面。

硬性要求：
- 仅输出纯 HTML 代码，从 <!DOCTYPE html> 到 </html>。不要 markdown 代码块，不要解释。
- 必须使用中文输出。
- 包含必要的 CDN 库：
  <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/echarts-wordcloud@2/dist/echarts-wordcloud.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
- 每个图表块必须是一个卡片，不同类型的图表使用不同的容器方式：

  【ECharts 图表（bar、line、pie 等）】
  <div class="card">
    <div class="chart-title">营业收入（单位：亿元）</div>
    <div id="chart-{index}" class="chart"></div>
    <div class="interpretation"><strong>智能洞察</strong>: ...</div>
  </div>

  【Mermaid 流程图】
  <div class="card">
    <div class="chart-title">门店数量（单位：家）</div>
    <div class="mermaid">
      graph TD
        A --> B
        B --> C
    </div>
    <div class="interpretation"><strong>智能洞察</strong>: ...</div>
  </div>

  【Markdown 表格】
  <div class="card">
    <div class="chart-title">同比增长率（单位：百分比）</div>
    <div class="markdown-table">
      | 列1 | 列2 |
      | --- | --- |
      | 数据1 | 数据2 |
    </div>
    <div class="interpretation"><strong>智能洞察</strong>: ...</div>
  </div>

- Mermaid 重要规则：
  * Mermaid 容器必须使用 <div class="mermaid"> 标签包裹
  * Mermaid 内容直接写在 div 内部，不要使用代码块标记（三个反引号）
  * 在页面底部的 <script> 中调用 mermaid.initialize({ startOnLoad: true });
  * 常用 Mermaid 类型：graph TD（自上而下）、graph LR（从左到右）、flowchart TD、gantt、pie、sequenceDiagram 等
  * 节点定义：A[文本] 或 A((圆形)) 或 A{菱形}

- 样式要求：
  * 一致的间距：卡片之间 12px，内部填充 12px
  * 避免裁剪；坐标轴左对齐；图例必须保留在卡片内
  * 不要重复图表
  * **ECharts 图表内部不要设置 title 配置项**

- ECharts 配置要求：
  * 图例与图形区域之间必须保持 3 像素间距
  * 在 grid 配置中设置 top 或 bottom 属性，确保图例和图表之间有间距
  * 示例配置：grid: { top: 60 } 或根据图例高度调整

- 标题格式要求：
  * 标题必须包含单位信息，格式为"XXX（单位：XXX）"
  * 示例："营业收入（单位：亿元）"、"门店数量（单位：家）"、"同比增长率（单位：百分比）"
  * 单位必须紧跟标题，用括号包裹

输入 JSON 项目结构：
{
  "type": "echarts/mermaid/markdown",
  "title": "图表标题",
  "content": { ... },
  "visualization_slot": { "chart_code": "..." },
  "interpretation": { "content": "..." }
}
"""

    messages = [
        {"role": "system", "content": prompt_html},
        {"role": "user", "content": json.dumps(chart_items, ensure_ascii=False)}
    ]
    raw = ark_api_call(api_key, messages, stream=False, max_tokens=15000)
    return raw


# =========================
# Main pipeline
# =========================
def run(pdf_path: str, output_dir: str = None):
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    api_key = get_ark_api_key()

    # Set output directory
    if output_dir is None:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(BASE_DIR, "output")

    ensure_dir(output_dir)
    task_id = uuid4().hex[:8]
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    prefix = f"{base_name}_{task_id}"

    txt_path = os.path.join(output_dir, f"{prefix}.txt")
    filtered_path = os.path.join(output_dir, f"{prefix}_filtered.txt")
    extracted_json_path = os.path.join(output_dir, f"{prefix}_extracted.json")
    chart_json_path = os.path.join(output_dir, f"{prefix}_chart.json")
    html_path = os.path.join(output_dir, f"{prefix}.html")

    log("[2] Initiate Intelligent Document Reading ...")
    pages = pdf_to_text_pages(pdf_path)
    full_text = build_full_text(pages)
    safe_write(txt_path, full_text)
    log(f"[3] Completed overall document reading. Saved: {txt_path}")

    log("[4] Starting in-depth document reading (filtering) ...")
    filtered_pages = filter_financial_pages_from_pages(pages)
    filtered_text = build_filtered_text(filtered_pages)
    safe_write(filtered_path, filtered_text)
    log(f"[4] Filtered pages: {len(filtered_pages)}. Saved: {filtered_path}")

    log("[5] Reading the document in detail (ARK extraction) ...")
    extracted_items = extract_data_with_ark(filtered_text, api_key)
    safe_write(extracted_json_path, json.dumps(extracted_items, ensure_ascii=False, indent=2))
    log(f"[6] Document reading completed. Saved: {extracted_json_path}")

    chart_items = generate_chart_json(extracted_items, api_key)
    
    # 过滤掉无效/空白组件
    chart_items = filter_valid_charts(chart_items)
    
    if not chart_items:
        log("⚠️ Warning: No valid charts generated, skipping HTML generation")
        return None
    
    safe_write(chart_json_path, json.dumps(chart_items, ensure_ascii=False, indent=2))
    log(f"[8] Chart JSON saved: {chart_json_path}")

    html = generate_html_from_json(chart_items, api_key)
    safe_write(html_path, html)
    log(f"✅ HTML generated: {html_path}")

    log("\nDONE.")
    log(f"Open this file in browser:\n{html_path}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse financial report PDF and generate HTML visualization")
    parser.add_argument("pdf_path", help="Path to PDF file")
    parser.add_argument("--output-dir", help="Output directory (default: scripts/output)")
    args = parser.parse_args()

    run(args.pdf_path, args.output_dir)
