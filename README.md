# 车研：购车资料检索与车型比较助手

一个独立的中国市场购车研究项目。用户选择精确到**车型、年款、配置版本**的车辆后，可以比较官网指导价和部分配置，并对官方手册提问。回答展示原文、出处及 PDF 页码。项目将结构化比较与 RAG 分开：数值由目录计算，模型只根据检索到的资料解释。

当前版本覆盖比亚迪 2026 款 10 款车型、43 个配置版本、5 份官网 PDF 用户手册，以及一份品牌售后服务流程页面。它是一个可扩展的首批样本，**不是全车型数据库**。

## 当前能做什么

- 比较 2 至 3 个具体版本的官方指导价、NEDC 亏电油耗、纯电续航、电池容量、轮胎和部分装备。
- 在车型库按品牌或车型搜索，查看车型图片、版本数量和官方指导价范围，再进入具体配置选择。
- 查看每项配置与价格的官网来源和采集日期。年款、配置、价格币种和能耗口径不会被隐式合并。
- 下载、解析 PDF，保留原始页码并建立本地向量索引。
- 按所选车型限定检索范围；对话模型挑选与问题相关的原文句子，程序验证引文确实存在后再展示。
- 在引用旁按“抽取本页要点”，得到带字段类型的结构化事实；所有引文在返回前与 PDF 原文核对。
- 在模型不可用时展示原文检索结果，不假装已经生成了答案。
- 在资料库上传 PDF、HTML、Markdown 或 TXT，填写来源并关联车型后建立本地索引；用户资料不会自动提交到 Git。

**资料边界：** 手册说明车辆功能、警示、保养和救援流程；官网售后页面说明品牌公开的服务流程。它们不能证明真实道路油耗、某款车的故障率或车主售后满意度。目前也没有经核实的召回记录、事故理赔体验或经销商成交价。针对这些问题，系统应说明资料不足。后续只有找到可核查来源并完成评测，才会增加相关能力。

## 快速开始（Windows PowerShell）

在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip -i https://pypi.org/simple
.\.venv\Scripts\python.exe -m pip install -e ".[dev]" -i https://pypi.org/simple
```

如果下载速度不稳定，分两次执行上面两条命令；安装阶段不需要重新下载 `data/raw/` 里的 PDF。

本地 RAG 需要 [Ollama](https://ollama.com/) 提供两个模型。`ollama list` 若能正常列出模型，表示本地服务通常已启动；否则打开 Ollama 应用。首次下载只需执行一次：

```powershell
ollama pull quentinz/bge-small-zh-v1.5
ollama pull qwen2.5:3b
```

第一个是中文**向量模型**，负责把问题和文档片段编码成可比较的数字；第二个是**对话模型**，负责根据检索到的片段组织回答。价格差值由程序计算，不交给对话模型。

下载官方手册并建立索引：

```powershell
.\.venv\Scripts\python.exe -m carwise.fetch_sources
.\.venv\Scripts\python.exe -m carwise.ingest
```

启动网页：

```powershell
.\.venv\Scripts\python.exe -m uvicorn carwise.main:app --host 127.0.0.1 --port 8765
```

打开 `http://127.0.0.1:8765/`。如果已有服务占用 8765 端口，换一个空闲端口。

不下载模型时，车型比较仍可运行；文档问答需要先建立索引。调用 `/api/search` 能单独检查检索结果，便于区分“没找到资料”和“生成回答失败”。

## 数据与来源

| 数据 | 官方来源 | 本地保存方式 |
| --- | --- | --- |
| 比亚迪 2026 款 10 款车型、43 个版本、指导价及部分配置 | [比亚迪官网车型目录](https://www.byd.com/cn/)、各车型参数对比页 | `data/catalog.json`，记录采集日期 |
| 秦L DM-i 用户手册 | [官网 PDF](https://www.byd.com/material/domestic-official/user-manual/dynasty/2026款秦L%20DM-i用户手册20260417.pdf) | `data/raw/`，Git 忽略 |
| 秦PLUS DM-i 用户手册 | [官网 PDF](https://www.byd.com/material/domestic-official/user-manual/dynasty/2026款秦PLUS%20DM-i用户手册260430-new.pdf) | `data/raw/`，Git 忽略 |
| 比亚迪售后服务流程 | [官网品牌页](https://www.byd.com/cn/after-sales-service) | `data/raw/`，Git 忽略 |
| 2026 款宋L DM-i、海鸥、海狮06 EV 用户手册 | [比亚迪官网用户手册](https://www.byd.com/cn/user-manual) | `data/raw/`，Git 忽略 |

当前 5 份 PDF 原文共约 1,931 页。为了在普通电脑上完成首版索引，`data/documents.json` 选取每份手册的安全警示、故障提示、保养和救援相关页段；引用仍使用 PDF 的实际页码。这个选择限制了可回答问题的范围。扩大覆盖时修改 `page_ranges` 并重新运行导入即可。

官网配置快照可用以下命令刷新。逐配置参数需 Playwright 调用浏览器展示的官方参数表，因此需要已安装的 Microsoft Edge：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[sync]"
.\.venv\Scripts\python.exe -m carwise.sync_byd --with-features
```

刷新前检查官网页面是否仍对应相同年款。脚本对官网返回的车型名称做校验，但价格与配置仍应人工抽样核对。官网对配置变更保留说明，本项目只展示采集当天的快照，不宣称实时价格。

## 模型切换

默认使用 Ollama 本地的 `qwen2.5:3b` 生成回答。已经拥有可直接调用的 DeepSeek API key 时，可在当前 PowerShell 会话中设置环境变量：

```powershell
$env:CARWISE_LLM_PROVIDER = "deepseek"
$env:CARWISE_DEEPSEEK_API_KEY = "你的密钥"
```

然后重启网页服务。**不要把密钥发给任何人，也不要写入仓库文件。** 即使切换生成模型，中文向量模型仍由 Ollama 在本地提供。DeepSeek Harness 使用过密钥，不代表这个新项目能自动读取它；这两者需要分开配置。

## API

- `GET /api/vehicles`：列出可选配置版本。
- `GET /api/documents`：列出已收录资料及索引片段数。
- `POST /api/documents`：上传并索引一份本地资料；表单字段包括 `file`、`title`、`source_url`、`source_type` 和 JSON 格式的 `vehicle_ids`。
- `POST /api/compare`：按版本 ID 校验并返回可比较的数据。
- `POST /api/search`：仅返回检索到的原文及来源，适合调试 RAG。
- `POST /api/ask`：检索后挑选并验证引文；返回 `evidence_selected`、`retrieval_only` 或 `no_evidence` 模式。
- `POST /api/extract`：从指定文档页抽取结构化事实，并验证字段引文。
- `GET /api/health`：显示车型数和已索引片段数。
- `GET /docs`：FastAPI 自动接口文档。

请求示例：

```json
{
  "question": "秦L的胎压警告灯亮起时，手册建议怎么做？",
  "vehicle_ids": ["byd-2026-qin-l-dm-i-1668"]
}
```

## 为什么这样设计

RAG 的路径是：PDF 按页解析 → 切成可检索片段 → 向量模型编码 → 在 SQLite 中保存向量并用 NumPy 做余弦相似度检索 → 连同出处交给对话模型挑选引文 → 程序验证引文确实在原文中 → 返回引文和来源。LangChain 当前用于文本切分与提示词编排。首版约数百页资料，精确检索便于检查每一步；文档量大幅增加时应换专用向量索引。

车型版本用固定 ID 关联资料。配置表中的价格和油耗必须有来源，缺少数据时显示“暂无可靠数据”。NEDC 亏电油耗是标准测试值，不等同于车主实际油耗；不同测试口径不应直接排序。模型只接收检索得到的文本，选出的引文必须与原文在空白差异之外一致。向量相似度阈值和同页重复命中降权用于保守拒答；售后满意度、故障率、实际成交均价等当前没有统计来源的指标会被明确拒答。所有规则仍需在更多题目上校准。

## 验证与下一阶段

运行基础校验：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

`evaluation/questions.json` 包含 26 道人工标注题：19 道手册有明确页码的事实题、3 道售后流程页的事实题、4 道现有资料无法支持的购车问题。运行 `python -m carwise.evaluate` 可复现当前结果：手册正确页进入前 3 条为 **19/19**，售后流程文档进入前 3 条为 **3/3**，无资料题拒答为 **4/4**。报告保存在 `evaluation/retrieval-results.json`。这是开发题集，不是独立测试集，也不是回答质量或抽取准确率的证明。

项目继续扩展前还需：补充合法可用的真实油耗、召回及售后反馈来源；验证不同来源的时间、车型与配置映射；人工核查更多抽取页和引文相关性；构建独立于调参问题的测试集。未完成这些验收前，不应在简历上声称覆盖这些主题或泛化效果。

