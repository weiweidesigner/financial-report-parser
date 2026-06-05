# Output Format

## 目录
- [文件结构](#文件结构)
- [文件格式说明](#文件格式说明)
  - [文本提取文件](#文本提取文件)
  - [JSON 数据文件](#json-数据文件)
  - [HTML 报告](#html-报告)
- [文件命名规则](#文件命名规则)

## 概览
本文档说明财报解析 Skill 的输出文件格式和结构。处理完成后,在 `output/` 目录下会生成多个文件,记录从 PDF 到 HTML 的完整转换过程。

## 文件结构

处理单个 PDF 文件后会生成以下文件:
```
output/
├── {basename}_{task_id}.txt                    # 完整文本提取
├── {basename}_{task_id}_filtered.txt           # 财务页面筛选
├── {basename}_{task_id}_extracted.json         # 结构化数据
├── {basename}_{task_id}_chart.json             # 图表设计
└── {basename}_{task_id}.html                   # 最终 HTML 报告
```

## 文件格式说明

### 文本提取文件

#### 完整文本文件
**文件名**: `{basename}_{task_id}.txt`

**格式**:
```
--- Page 1 ---
[第一页的完整文本内容]

--- Page 2 ---
[第二页的完整文本内容]
...
```

**说明**:
- 包含 PDF 所有页面的文本内容
- 每页以 `--- Page N ---` 分隔
- 如果某页无法提取文本,标记为 `[NO TEXT EXTRACTED]`

#### 筛选文本文件
**文件名**: `{basename}_{task_id}_filtered.txt`

**格式**: 与完整文本文件格式相同,但仅包含财务相关页面

**筛选规则**:
- 页面数字出现次数 ≥ 6 次,或
- 数字出现次数 ≥ 3 次且包含财务关键词
- 财务关键词包括:净利润、收入、资产、负债、现金流、毛利率、ROE 等

### JSON 数据文件

#### 提取数据文件
**文件名**: `{basename}_{task_id}_extracted.json`

**格式**:
```json
[
  {
    "type": "structured_data",
    "content": {
      "field1": "value1",
      "field2": "value2",
      ...
    }
  },
  {
    "type": "opinion_data",
    "content": {
      "analyst": "Analyst Name (or Organization)",
      "opinion": "Key insight of this section"
    }
  },
  {
    "type": "raw_chunk_output",
    "content": {
      "text": "原始输出文本(最多8000字符)"
    }
  }
]
```

**类型说明**:
- `structured_data`: 结构化财务数据(指标、数值等)
- `opinion_data`: 分析师观点或关键见解
- `raw_chunk_output`: 提取失败时的原始输出

#### 图表设计文件
**文件名**: `{basename}_{task_id}_chart.json`

**格式**:
```json
[
  {
    "type": "...",
    "content": {...},
    "visualization_slot": {
      "chart_code": "图表代码(ECharts/Mermaid/Markdown)"
    },
    "interpretation": {
      "content": "<div class=\"interpretation\"><strong>AIme Insight</strong>: 见解内容</div>"
    }
  }
]
```

**可视化类型**:
- ECharts:交互式图表(饼图、柱状图、折线图等)
- Mermaid:流程图或关系图
- Markdown:表格或文本

### HTML 报告

**文件名**: `{basename}_{task_id}.html`

**结构**:
```html
<!DOCTYPE html>
<html>
<head>
  <title>Financial Report Analysis</title>
  <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
  <style>
    /* 页面样式 */
  </style>
</head>
<body>
  <div class="chart-card">
    <div class="chart-title">图表标题</div>
    <div id="chart-0" class="chart"></div>
    <div class="interpretation">
      <strong>AIme Insight</strong>: 见解分析
    </div>
  </div>
  <!-- 更多图表卡片 -->
</body>
</html>
```

**特点**:
- 完整的 HTML5 页面,可直接在浏览器打开
- 集成 ECharts 库,支持交互式图表
- 每个图表包含标题、可视化区域和见解分析
- 响应式布局,卡片间距 12px,内边距 12px

## 文件命名规则

### 任务 ID
- 格式:8 位十六进制字符串
- 生成方式:`uuid4().hex[:8]`
- 示例:`a1b2c3d4`

### 命名模式
所有文件遵循以下命名模式:
```
{basename}_{task_id}{suffix}.{ext}
```

**参数说明**:
- `basename`: PDF 文件基础名(不含扩展名)
- `task_id`: 8 位任务标识符
- `suffix`: 可选后缀(_filtered, _extracted, _chart)
- `ext`: 文件扩展名(.txt, .json, .html)

**示例**:
- 输入:`annual_report_2024.pdf`
- 任务 ID:`e5f6g7h8`
- 输出文件:
  - `annual_report_2024_e5f6g7h8.txt`
  - `annual_report_2024_e5f6g7h8_filtered.txt`
  - `annual_report_2024_e5f6g7h8_extracted.json`
  - `annual_report_2024_e5f6g7h8_chart.json`
  - `annual_report_2024_e5f6g7h8.html`

## 注意事项

1. **文件路径**:所有输出文件相对于 `output/` 目录
2. **编码格式**:文本文件和 HTML 文件使用 UTF-8 编码
3. **JSON 兼容性**:JSON 文件使用 UTF-8 编码,支持中文字符
4. **独立性**:HTML 报告是自包含的,无需额外资源(除 CDN)
5. **可追溯性**:任务 ID 确保每次处理的文件唯一性
