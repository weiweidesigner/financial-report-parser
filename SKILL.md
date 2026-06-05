---
name: financial-report-parser
description: 解析财报PDF并生成结构化HTML报告。适用于PDF格式的财务报表、年报、季报等文档的智能解读和数据可视化。支持自动提取关键财务数据、生成图表并输出完整的HTML分析报告。
dependency:
  python:
    - pdfplumber>=0.10.0
    - requests>=2.28.0
---

# Financial Report Parser

## 任务目标
本 Skill 用于:
- 解析用户上传的 PDF 格式财报文档,提取结构化财务数据
- 生成包含图表和见解的可视化 HTML 报告并展示
- 适用于财务分析、投资研究等场景

能力包含:
- PDF 文本提取与页面解析
- 财务相关页面智能筛选
- 基于大模型的财务数据结构化提取
- 自动生成可视化图表和 HTML 报告

触发条件:
- 用户上传财报 PDF 文件
- 需要将 PDF 转换为结构化 HTML 格式并展示
- 需要提取财报中的关键财务数据

## 前置准备

### 依赖说明
```
pdfplumber>=0.10.0
requests>=2.28.0
```

### 凭证配置
本 Skill 使用火山引擎 ARK API 进行数据提取和报告生成。不要把真实密钥写入代码或提交到 Git。

安装后将密钥写入本地 `.env`:
```bash
python scripts/configure_secrets.py 'ARK_API_KEY=your-api-key'
```

从 GitHub 安装后可用一条命令写入本地密钥:
```bash
npx skills add https://github.com/<owner>/<repo> && python ~/.codex/skills/financial-report-parser/scripts/configure_secrets.py 'ARK_API_KEY=your-api-key'
```

也可以在安装命令或运行命令里传入环境变量:
```bash
ARK_API_KEY='your-api-key' python scripts/process.py <pdf_path>
```

可选配置:
- `ARK_API_KEY` 或 `VOLC_ARK_API_KEY`: 火山引擎 ARK API Key
- `ARK_BASE_URL`: 默认 `https://ark.cn-beijing.volces.com/api/v3`
- `ARK_LLM_MODEL`: 默认脚本内置模型

## 操作步骤

### 标准流程

1. **接收用户上传的 PDF 文件**
   - 用户上传财报 PDF 文件
   - 确认 PDF 文件可读性,确保包含文本内容而非纯扫描图片

2. **执行解析处理**
   - 调用 `scripts/process.py` 处理 PDF 文件
   - 命令格式:
     ```bash
     python scripts/process.py <pdf_path>
     ```
   - 参数说明:
     - `pdf_path`: 用户上传的 PDF 文件路径

3. **输出并展示 HTML 报告**
   - 处理完成后,在 `output/` 目录生成 HTML 文件
   - 直接向用户展示生成的 HTML 报告
   - HTML 文件包含完整的可视化分析结果(图表、数据表格、见解)

### 处理流程说明

脚本内部执行以下步骤:

1. **PDF 解析** (pdfplumber)
   - 提取每一页的文本内容

2. **智能筛选**
   - 基于关键词(净利润、收入、资产等)和数字密度
   - 筛选出包含财务数据的页面

3. **数据提取** (火山引擎 ARK API)
   - 调用大模型从筛选后的文本中提取结构化数据

4. **图表设计** (火山引擎 ARK API)
   - 基于提取的数据设计可视化方案
   - 生成 ECharts 图表代码

5. **HTML 生成** (火山引擎 ARK API)
   - 生成完整的 HTML5 页面
   - 包含图表、数据表格和见解分析

### 输出文件说明

- **最终输出**: `{basename}_{task_id}.html` - 完整的 HTML 可视化报告
- **中间文件** (如需查看):
  - `{basename}_{task_id}.txt`: 完整文本提取
  - `{basename}_{task_id}_filtered.txt`: 财务页面筛选
  - `{basename}_{task_id}_extracted.json`: 结构化数据
  - `{basename}_{task_id}_chart.json`: 图表设计

### 可选分支

**当 PDF 文件较大时**:
- 脚本会自动分块处理
- 每个块分别调用 API 提取数据
- 最终合并所有结果

**当提取失败时**:
- 脚本会保存原始输出
- 在 JSON 中标记为 `raw_chunk_output`
- 不影响整体流程继续执行

## 资源索引

### 必要脚本
- 见 [scripts/process.py](scripts/process.py) (用途:PDF 解析、数据提取和 HTML 生成的完整流程)

### 领域参考
- 见 [references/output-format.md](references/output-format.md) (何时读取:需要了解输出文件格式和结构时)

## 注意事项

- PDF 文件应包含可提取的文本内容,不支持纯扫描图片
- 处理过程会调用大模型 API,可能需要一定时间
- 输出文件名包含任务 ID,便于追溯
- HTML 报告是自包含的,可直接在浏览器打开查看
- API 密钥优先级: 环境变量 `ARK_API_KEY` > `VOLC_ARK_API_KEY`;技能目录下的 `.env` 会自动读取
- `.env` 只用于本地安装后的私密配置,不要提交到 Git

## 使用示例

### 示例 1: 解析用户上传的年报
```bash
# 用户上传 annual_report_2024.pdf
python scripts/process.py ./annual_report_2024.pdf
# 输出: output/annual_report_2024_a1b2c3d4.html
# 直接展示 HTML 报告给用户
```

### 示例 2: 处理季报
```bash
# 用户上传 q3_financial_report.pdf
python scripts/process.py ./q3_financial_report.pdf
# 输出: output/q3_financial_report_e5f6g7h8.html
# 直接展示 HTML 报告给用户
```
