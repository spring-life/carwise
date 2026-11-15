# 车研：购车资料检索与车型比较助手

车研收录中国市场 10 款比亚迪 2026 款车型的 43 个配置版本。用户可以比较具体版本的指导价和配置，查询官方手册，并通过来源链接和页码核对回答。

## 能做什么

- 搜索车型，选择年款和配置；页面标出每款车已收录的官网参数、手册和售后资料。
- 比较 2 至 3 个版本的官方指导价、能耗、轮胎和部分装备，查看字段来源与采集日期。
- 检索所选车型的手册及品牌售后服务流程，查看原文和 PDF 页码。
- 在资料问答页点击三个常见问题或自行提问；回答附经程序核对的引文。
- 从指定手册页抽取故障信号、风险、建议操作、保养周期和配置说明等结构化事实。
- 上传 PDF、HTML、Markdown 或纯文本资料，填写来源并关联车型。
- 生成服务异常时显示检索原文和回答状态。

## 设计取舍

1. 指导价和标称能耗来自配置目录，价格差值由程序计算，手册问题走原文检索。这样可以直接核对数值和出处。
2. 模型选出引文后，程序会在原片段中查找相同文字。找到才展示，避免把模型改写的句子当作手册原文。
3. 当前索引有 8739 个片段，使用 SQLite 保存数据、NumPy 计算余弦相似度。片段量达到十万级时，可评估专用向量索引。
4. 现有资料没有车主满意度、车型故障率和实际成交均价的统计来源。遇到这些问题，系统说明资料不足。
5. 官网参数回答标记为 `catalog`，核验通过的手册引文标记为 `evidence_selected`。问题范围不清、资料不足或生成失败时，界面分别显示澄清提示、拒答或候选原文。

## 快速开始

在项目根目录使用 Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
ollama pull quentinz/bge-small-zh-v1.5
ollama pull qwen2.5:3b
.\.venv\Scripts\python.exe -m carwise.fetch_sources
.\.venv\Scripts\python.exe -m carwise.ingest
.\.venv\Scripts\python.exe -m uvicorn carwise.main:app --host 127.0.0.1 --port 8765
```

打开 `http://127.0.0.1:8765/`。第一个 Ollama 模型生成中文文本向量，第二个模型组织资料问答。车型比较使用本地配置目录。使用 DeepSeek 生成回答时，在启动服务前设置 `CARWISE_LLM_PROVIDER=deepseek` 和 `CARWISE_DEEPSEEK_API_KEY`；文本向量仍由本地 Ollama 提供。

## 数据来源与范围

| 数据 | 来源与时间 | 本地文件或索引范围 |
| --- | --- | --- |
| 10 款车型、43 个配置版本的指导价与部分参数 | [比亚迪官网车型及参数页](https://www.byd.com/cn/)，基础快照采集于 2026-11-11；夏的发动机参数补采于 2026-11-15 | `data/catalog.json` |
| 2026 款秦L DM-i 用户手册，410 页 | [官方 PDF](https://www.byd.com/material/domestic-official/user-manual/dynasty/2026款秦L%20DM-i用户手册20260417.pdf)，发布日期 2026-04-17 | 全文 |
| 2026 款秦PLUS DM-i 用户手册，403 页 | [官方 PDF](https://www.byd.com/material/domestic-official/user-manual/dynasty/2026款秦PLUS%20DM-i用户手册260430-new.pdf)，发布日期 2026-04-30 | 全文 |
| 2026 款宋L DM-i 用户手册，380 页 | [官方 PDF](https://www.byd.com/material/domestic-official/user-manual/dynasty/2026款宋L%20DM-i用户手册%20260420.pdf)，发布日期 2026-04-20 | 全文 |
| 2026 款海鸥用户手册，354 页 | [官方 PDF](https://www.byd.com/material/domestic-official/user-manual/ocean/2026款海鸥用户手册260317.pdf)，发布日期 2026-03-17 | 全文 |
| 2026 款海狮06 EV 用户手册，384 页 | [官方 PDF](https://www.byd.com/material/__CN/domestic-official/user-manual/dynasty/2026款海狮06%20EV用户手册261014.pdf)，发布日期 2026-10-14 | 全文 |
| 2026 款海狮06 DM-i 用户手册，396 页 | [官方 PDF](https://www.byd.com/material/domestic-official/user-manual/ocean/2026款海狮06%20DM-i用户手册260526.pdf)，官网目录日期 2026-08-11 | 全文 |
| 2026 款海豹06 DM-i 旅行版用户手册，386 页 | [官方 PDF](https://www.byd.com/material/__CN/domestic-official/user-manual/ocean/2026款海豹06DM-i旅行版用户手册260825.pdf)，官网目录日期 2026-08-25 | 全文 |
| 2026 款海豹06GT 用户手册，380 页 | [官方 PDF](https://www.byd.com/material/__CN/domestic-official/user-manual/ocean/2026款海豹06GT用户手册261030.pdf) | 全文 |
| 2026 款海豹07 DM-i 用户手册，402 页 | [官方 PDF](https://www.byd.com/material/domestic-official/user-manual/ocean/2026款海豹07DM-i用户手册260604.pdf) | 全文 |
| 夏用户手册，464 页，官网未标年款 | [官方 ZIP](https://www.byd.com/material/domestic-official/user-manual/dynasty/夏用户手册_250905.zip)，官网目录日期 2025-09-22 | 提取 PDF 全文；2026 款适用性待核 |
| 比亚迪汽车售后服务流程 | [官网品牌页](https://www.byd.com/cn/after-sales-service) | 页面正文 |

十份手册共 3959 页，全文索引生成 8737 个片段；售后流程页生成 2 个片段。手册按车型关联配置版本，43 个版本均有资料记录。`data/documents.json` 保存资料链接、时间、关联配置和索引页段；下载原件与本地索引分别放在 `data/raw/` 和 `storage/`。官网配置记录采集日期，指导价以采集时的页面为准。

发动机规格、动力参数、轮胎、电池容量、标称油耗、纯电续航、座椅配置和官方指导价从官网参数快照读取，回答附参数页来源。首次保养时间与项目从手册原文定位；其他手册问题通过检索和引文核对回答。夏的五个配置另收录了官网发动机字段，数值按原页面展示。

刷新车型目录与配置参数：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[sync]"
.\.venv\Scripts\python.exe -m carwise.sync_byd --with-features
```

脚本通过 Microsoft Edge 读取官网参数页，校验返回的车型名称，并记录采集日期。

## API

| 接口 | 用途 |
| --- | --- |
| `GET /api/vehicles` | 查询车型和配置版本 |
| `GET /api/documents` | 查询资料及索引片段数 |
| `POST /api/documents` | 上传资料并关联车型 |
| `POST /api/compare` | 比较配置版本 |
| `POST /api/search` | 查看原文检索结果 |
| `POST /api/ask` | 返回官网参数、经引文核验的手册回答或澄清提示 |
| `POST /api/extract` | 抽取指定页的结构化事实 |
| `GET /api/health` | 查询车型数与索引片段数 |
| `GET /docs` | 查看交互式接口文档 |

问答请求示例：

```json
{
  "question": "秦L的胎压警告灯亮起时，手册建议怎么做？",
  "vehicle_ids": ["byd-2026-qin-l-dm-i-1668"]
}
```

## 参数选择

切片实验使用五份手册的部分页段和 26 道开发题，比较四档切片大小，重叠长度取切片大小的 17%。页码命中统计来自其中 19 道有页码标注的题；平均耗时包含本地 Ollama 的问题向量生成。

| 切片长度 | 重叠长度 | 片段总数 | 前 3 条页码命中 | 平均检索耗时 |
| ---: | ---: | ---: | ---: | ---: |
| 200 | 34 | 2008 | 19/19 | 681.77 毫秒 |
| 350 | 60 | 1237 | 19/19 | 858.80 毫秒 |
| 500 | 85 | 947 | 16/19 | 703.53 毫秒 |
| 800 | 136 | 645 | 17/19 | 712.34 毫秒 |

350 与 200 都命中 19/19 页，350 的索引少 771 个片段，因此采用 350。500 和 800 分别命中 16/19 和 17/19。实验结果见 `evaluation/chunk-size-ablation.json`。

## 评测

| 题集 | 题数 | 前 3 条页码命中 | 文档命中 | 无资料拒答 |
| --- | ---: | ---: | ---: | ---: |
| 开发集，部分页段索引 | 26 | 19/19 | 3/3 | 4/4 |
| 留出集，部分页段索引 | 20 + 5 | 16/20 | 18/20 | 5/5 |
| 留出集，全文索引回归 | 20 + 5 | 15/20 | 19/20 | 5/5 |

开发集的文档命中对应 3 道售后流程题，留出集对应 20 道手册题。留出题按固定种子从五份手册抽页，排除开发题标注页码，并在查看检索结果前根据原文编写。配置与题目分别记录在提交 `224a4d3` 和 `408da2d`。全文索引一行复用了留出题，结果属于回归检查。

### 回答质量测试

回答质量题集包含 76 道不同措辞的问题：官网配置字段 36 题、手册原文 22 题、无统计来源拒答 10 题，以及选车范围与澄清 8 题。脚本检查回答模式、关键事实、官方资料关联和手册引文与候选原文的一致性。题目及逐题结果见 `evaluation/answer-quality-questions.json` 和 `evaluation/answer-quality-results.json`。

| 测试日期 | 总通过 | 官网字段 | 手册回答 | 无资料拒答 | 范围与澄清 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2026-11-15 | 74/76 | 36/36 | 20/22 | 10/10 | 8/8 |

运行单元测试得到 29/29 通过；回答质量测试中 M16、M18 未通过，均与胎压告警处理建议的摘录有关。

运行回答质量评测：

```powershell
.\.venv\Scripts\python.exe tools\evaluate_answers.py --output "$env:TEMP\carwise-answer-quality-run.json"
```

运行现有测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## 已知局限

- 手册和官网售后流程页提供车辆功能及公开流程信息；真实道路油耗、车型故障率、车主售后满意度和实际成交均价需要另行取得可核查的统计或交易数据。
- 26 道开发题对照检索结果编制并参与参数选择，其满分表现只代表开发集。25 道留出题未参与参数选择；目前缺少跨品牌、跨资料批次的外部测试集，以及对回答质量和抽取准确率的系统人工评估。
- 夏的官网手册未标明年款，2026 款各配置的适用性尚未核实；手册也提示带星号的功能只适用于部分配置。海豹06GT、海豹07 DM-i 手册的官网目录时间与文件名日期不一致，项目没有推断其发布日期。
- 全文索引上的留出题页码命中为 15/20，部分页段索引为 16/20。新增五份手册还缺少独立题集和回答质量的人工核查。
- 相似度阈值和同页重复降权系数只在一小批开发题上校准过，更多车型和问法仍需验证。五道无资料题使用了当前明确识别的指标词，拒答率仅衡量这些问题。
- 引文校验只忽略空白字符；模型抄错表格后半段时，程序只展示可核对的连续原文。标点差异仍可能导致引文截断或误拒；后续可评估标点归一化或编辑距离容错。
- 回答质量的 76 题参与了开发阶段的规则调整，尚需新增独立题集与人工逐题复核。两道胎压告警题能定位对应手册，但模型摘录的处理动作不完整；不同告警状态也需要分别核查。
- 切片实验的检索耗时包含本地模型服务时间，单轮数据受设备负载影响。
