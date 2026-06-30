# 自动回复质量评估流水线

本项目用于评估 `task3_auto_replies.json` 中 20 条客服自动回复质量。评估依据来自业务方模糊要求：回复要有用、准确、真实、不瞎编、语气友好；并用 `task3_human_ref.json` 中的人工参考回复和标注分析做弱金标准验证。

## 指标与权重

本项目使用 1-5 分制，5 分最好，1 分最差。

| 指标 | 权重 | 定义 | 量化方式 |
| --- | ---: | --- | --- |
| 有用性 | 40% | 回复是否真正推动问题解决，是否主动承接、追问信息、减少用户操作成本 | 5 分表示主动给出落地方案并帮助处理；3 分表示只有通用规则；1 分表示没有实质帮助 |
| 准确性 | 30% | 回复是否命中用户核心诉求，回答方向是否正确 | 5 分表示完整命中诉求；3 分表示方向大致正确但偏泛；1 分表示答非所问 |
| 真实性/不瞎编造 | 20% | 回复是否避免无依据事实、政策、商品参数、订单状态或承诺 | 5 分表示事实完全可信；3 分表示表达偏泛但未明显编造；1 分表示存在核心事实编造 |
| 语气友好 | 10% | 回复是否礼貌、安抚充分，符合客服场景 | 5 分表示有共情和服务感；3 分表示中性礼貌；1 分表示冒犯、推责或激化情绪 |

总分公式：

```text
总分 = 有用性 * 0.40 + 准确性 * 0.30 + 真实性 * 0.20 + 语气友好 * 0.10
```

选择理由：这批样例中最常见的问题不是“完全错误”，而是“回复看似合理但没有帮用户解决问题”，所以有用性权重最高。准确性是基础质量；真实性用于控制自动客服风险；语气友好作为体验补充。

## 两种评估模式

### 1. mock 模式

mock 模式不调用真实 LLM API，使用规则和人工标注趋势进行评分。

适用场景：

- 没有 API Key
- 需要离线演示
- 需要稳定、可复现的结果

运行：

```bash
python src/evaluator.py --mode mock
python src/report.py
```

### 2. LLM 模式：通义千问 API

LLM 模式会调用阿里云 DashScope 的 OpenAI 兼容接口，让模型按 rubric 对每条 case 打分并输出原因。

本项目默认模型：

```text
qwen3.6-plus
```

选择理由：`qwen3.6-plus` 比 flash 类模型更适合做细粒度质量评估，成本又低于 max 类模型，适合作为本任务默认评估模型。

设置 API Key：

```powershell
$env:DASHSCOPE_API_KEY="你的API_KEY"
```

或：

```powershell
$env:QWEN_API_KEY="你的API_KEY"
```

运行：

```bash
python src/evaluator.py --mode llm --model qwen3.6-plus
python src/report.py
```

建议第一次设置 API Key 后先只跑 1 条，确认接口可用：

```bash
python src/evaluator.py --mode llm --model qwen3.6-plus --timeout 10 --limit 1
```

如果中断或只想从某条继续测试，可以指定起始 case：

```bash
python src/evaluator.py --mode llm --model qwen3.6-plus --start case_08 --limit 3
```

接口配置：

```text
Base URL: https://dashscope.aliyuncs.com/compatible-mode/v1
Model: qwen3.6-plus
Temperature: 0.1
```

如果 LLM 调用失败，程序会自动回退到 mock 评分，并在结果中记录 `llm_error`。

## 输出文件

运行后生成：

```text
outputs/evaluation_results.json
outputs/evaluation_report.md
```

`evaluation_results.json` 包含每条 case 的单项分、总分、问题列表和评分理由。  
`evaluation_report.md` 包含整体得分、各指标平均分、分布、最差 3 条 case 和局限性分析。

## 如何用人工标注验证

`task3_human_ref.json` 不用于让系统照抄人工回复，而是作为弱金标准验证评估方法：

1. 对齐人工标注的问题类型：例如“正确但没用”“只给通用说明”“未主动查询订单/商品”“情绪安抚不足”。
2. 检查分数趋势是否一致：例如 case_08 应该准确性较高、有用性较低；case_14 应该总分较高；case_20 应该准确性和有用性较低。
3. 用人工参考回复中的关键动作做对照：例如“请提供订单号”“我帮您查”“我帮您联系快递”等动作是否被自动回复覆盖。

## 局限性

- 没有真实业务系统数据时，真实性只能根据文本证据判断，无法真正查询订单、物流、商品和优惠券状态。
- mock 模式稳定但语义理解有限，只适合做可复现基线。
- LLM 模式语义理解更强，但可能受模型版本、prompt、温度、网络/API 状态影响。
- 人工参考回复是弱金标准，不是唯一正确答案；更严谨的线上评估应增加样本量，并引入多名标注员一致性验证。

## AI 工具使用说明

本项目使用 AI 辅助完成指标拆解、评估方案设计、代码实现和 README 撰写。真实评分可选择调用通义千问 `qwen3.6-plus` API；没有 API Key 时可使用 mock 模式完成可复现演示。

## 测试

本项目测试使用 Python 标准库 `unittest`，不依赖额外包：

```bash
python -m unittest discover -s tests
```
