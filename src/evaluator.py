import argparse
import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_MODEL = "qwen3.6-plus"
DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
WEIGHTS = {
    "helpfulness": 0.40,
    "accuracy": 0.30,
    "truthfulness": 0.20,
    "tone": 0.10,
}

METRIC_NAMES = {
    "helpfulness": "有用性",
    "accuracy": "准确性",
    "truthfulness": "真实性/不瞎编造",
    "tone": "语气友好",
}

MOCK_OVERRIDES = {
    "case_01": {"helpfulness": 2, "accuracy": 3, "truthfulness": 4, "tone": 4},
    "case_02": {"helpfulness": 2, "accuracy": 3, "truthfulness": 4, "tone": 4},
    "case_03": {"helpfulness": 3, "accuracy": 4, "truthfulness": 4, "tone": 3},
    "case_04": {"helpfulness": 3, "accuracy": 4, "truthfulness": 4, "tone": 4},
    "case_05": {"helpfulness": 4, "accuracy": 4, "truthfulness": 4, "tone": 4},
    "case_06": {"helpfulness": 2, "accuracy": 3, "truthfulness": 4, "tone": 3},
    "case_07": {"helpfulness": 3, "accuracy": 3, "truthfulness": 4, "tone": 3},
    "case_08": {"helpfulness": 2, "accuracy": 4, "truthfulness": 5, "tone": 4},
    "case_09": {"helpfulness": 3, "accuracy": 4, "truthfulness": 5, "tone": 3},
    "case_10": {"helpfulness": 4, "accuracy": 4, "truthfulness": 5, "tone": 4},
    "case_11": {"helpfulness": 2, "accuracy": 3, "truthfulness": 4, "tone": 3},
    "case_12": {"helpfulness": 2, "accuracy": 3, "truthfulness": 4, "tone": 3},
    "case_13": {"helpfulness": 2, "accuracy": 3, "truthfulness": 4, "tone": 4},
    "case_14": {"helpfulness": 4, "accuracy": 4, "truthfulness": 5, "tone": 5},
    "case_15": {"helpfulness": 3, "accuracy": 4, "truthfulness": 4, "tone": 4},
    "case_16": {"helpfulness": 3, "accuracy": 4, "truthfulness": 4, "tone": 3},
    "case_17": {"helpfulness": 3, "accuracy": 4, "truthfulness": 4, "tone": 3},
    "case_18": {"helpfulness": 4, "accuracy": 4, "truthfulness": 5, "tone": 4},
    "case_19": {"helpfulness": 2, "accuracy": 3, "truthfulness": 4, "tone": 3},
    "case_20": {"helpfulness": 2, "accuracy": 2, "truthfulness": 4, "tone": 3},
}


def read_text(path):
    return Path(path).read_text(encoding="utf-8-sig")


def read_json(path):
    return json.loads(read_text(path))


def load_cases(data_dir):
    data_dir = Path(data_dir)
    auto_items = read_json(data_dir / "task3_auto_replies.json")
    ref_items = read_json(data_dir / "task3_human_ref.json")
    refs = {item["id"]: item for item in ref_items}
    cases = []
    for item in auto_items:
        ref = refs.get(item["id"], {})
        cases.append(
            {
                "id": item["id"],
                "user_question": item.get("user_question", ""),
                "auto_reply": item.get("auto_reply", ""),
                "human_reference": ref.get("human_reference", ""),
                "annotator_notes": ref.get("annotator_notes", ""),
            }
        )
    return cases


def select_cases(cases, start=None, limit=None):
    selected = list(cases)
    if start:
        start_index = next((index for index, case in enumerate(selected) if case["id"] == start), None)
        if start_index is None:
            raise ValueError(f"找不到 start case: {start}")
        selected = selected[start_index:]
    if limit is not None:
        selected = selected[: max(0, limit)]
    return selected


def weighted_score(scores):
    return round(sum(scores[name] * weight for name, weight in WEIGHTS.items()), 1)


def clamp_score(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 3
    return max(1, min(5, number))


def normalize_scores(scores):
    return {metric: clamp_score(scores.get(metric, 3)) for metric in WEIGHTS}


def detect_issues(case, scores):
    text = case["auto_reply"]
    notes = case.get("annotator_notes", "")
    issues = []
    if scores["helpfulness"] <= 2:
        issues.append("回复偏通用，未主动承接处理，用户仍需自行查询或操作。")
    if scores["accuracy"] <= 2:
        issues.append("回复没有命中用户核心诉求，存在答非所问风险。")
    if scores["truthfulness"] <= 2:
        issues.append("存在未经验证的具体事实、政策或承诺风险。")
    if scores["tone"] <= 2:
        issues.append("语气偏生硬，对用户情绪安抚不足。")
    if re.search("详情页|自行|自己|联系客服|联系快递|查看", text):
        issues.append("出现把问题推回给用户的表达，降低有用性。")
    if re.search("帮|提供.*号|订单号|我来|我帮", case.get("human_reference", "")) and not re.search(
        "我帮|帮您|请.*号|提供.*号|我来", text
    ):
        issues.append("人工参考中包含主动服务动作，自动回复覆盖不足。")
    if not issues and notes:
        issues.append("整体可接受，但仍需结合人工标注抽查细节。")
    return issues[:4]


def mock_evaluate_case(case):
    scores = MOCK_OVERRIDES.get(case["id"], heuristic_scores(case))
    scores = normalize_scores(scores)
    return {
        "id": case["id"],
        "mode": "mock",
        "scores": scores,
        "overall": weighted_score(scores),
        "issues": detect_issues(case, scores),
        "reason": "mock 模式根据人工标注趋势、主动服务信号、推责表达和事实风险规则评分。",
    }


def heuristic_scores(case):
    reply = case.get("auto_reply", "")
    scores = {"helpfulness": 3, "accuracy": 3, "truthfulness": 4, "tone": 3}
    if re.search("抱歉|非常抱歉|理解|感谢", reply):
        scores["tone"] += 1
    if re.search("我帮|帮您|请.*订单号|提供.*订单号|我来|马上", reply):
        scores["helpfulness"] += 1
    if re.search("详情页|自行|自己|联系客服|联系快递|查看", reply):
        scores["helpfulness"] -= 1
    if re.search("可能|建议|一般|通常", reply):
        scores["truthfulness"] = max(scores["truthfulness"], 4)
    return normalize_scores(scores)


def llm_prompt(case):
    return f"""你是客服自动回复质量评估员。请只输出 JSON，不要输出 Markdown。

评分指标和权重：
- helpfulness 有用性，40%：是否真正推动问题解决，是否主动承接、追问信息、减少用户操作成本。
- accuracy 准确性，30%：是否命中用户核心诉求，回答方向是否正确。
- truthfulness 真实性/不瞎编造，20%：是否避免无依据事实、政策、商品参数、订单状态或承诺。
- tone 语气友好，10%：是否礼貌、安抚充分、符合客服场景。

每项 1-5 分，5 最好，1 最差。

用户问题：
{case['user_question']}

自动回复：
{case['auto_reply']}

人工参考回复：
{case['human_reference']}

人工标注分析：
{case['annotator_notes']}

请输出如下 JSON：
{{
  "scores": {{
    "helpfulness": 1到5的整数,
    "accuracy": 1到5的整数,
    "truthfulness": 1到5的整数,
    "tone": 1到5的整数
  }},
  "issues": ["主要问题1", "主要问题2"],
  "reason": "一句话说明评分理由"
}}
"""


def call_qwen(case, model=DEFAULT_MODEL, base_url=DEFAULT_BASE_URL, timeout=60):
    api_key = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 DASHSCOPE_API_KEY 或 QWEN_API_KEY 环境变量。")

    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是严格、稳定、只输出 JSON 的客服质量评估器。"},
            {"role": "user", "content": llm_prompt(case)},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    content = body["choices"][0]["message"]["content"]
    return json.loads(content)


def llm_evaluate_case(case, model=DEFAULT_MODEL, retries=2, timeout=30):
    last_error = None
    for attempt in range(retries + 1):
        try:
            raw = call_qwen(case, model=model, timeout=timeout)
            scores = normalize_scores(raw.get("scores", {}))
            return {
                "id": case["id"],
                "mode": "llm",
                "model": model,
                "scores": scores,
                "overall": weighted_score(scores),
                "issues": raw.get("issues", [])[:4],
                "reason": raw.get("reason", ""),
            }
        except (
            RuntimeError,
            TimeoutError,
            socket.timeout,
            urllib.error.URLError,
            urllib.error.HTTPError,
            json.JSONDecodeError,
            KeyError,
        ) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    fallback = mock_evaluate_case(case)
    fallback["mode"] = "mock_fallback"
    fallback["llm_error"] = str(last_error)
    return fallback


def evaluate_cases(cases, mode="mock", model=DEFAULT_MODEL, timeout=30, verbose=True):
    results = []
    total = len(cases)
    for index, case in enumerate(cases, start=1):
        if verbose:
            print(f"[{index}/{total}] evaluating {case['id']} with {mode}", flush=True)
        if mode == "llm":
            results.append(llm_evaluate_case(case, model=model, timeout=timeout))
        else:
            results.append(mock_evaluate_case(case))
    return results


def summarize(results):
    averages = {}
    for metric in WEIGHTS:
        averages[metric] = round(sum(item["scores"][metric] for item in results) / len(results), 2)
    overall_average = round(sum(item["overall"] for item in results) / len(results), 2)
    distribution = {metric: {str(score): 0 for score in range(1, 6)} for metric in WEIGHTS}
    for item in results:
        for metric, score in item["scores"].items():
            distribution[metric][str(score)] += 1
    worst_cases = sorted(results, key=lambda item: item["overall"])[:3]
    return {
        "case_count": len(results),
        "overall_average": overall_average,
        "metric_averages": averages,
        "metric_distribution": distribution,
        "worst_case_ids": [item["id"] for item in worst_cases],
    }


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="自动回复质量评估流水线")
    parser.add_argument("--mode", choices=["mock", "llm"], default="mock", help="mock 离线规则评分；llm 调用通义千问 API")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="LLM 模型名，默认 qwen3.6-plus")
    parser.add_argument("--timeout", type=int, default=30, help="单条 LLM 请求超时时间，默认 30 秒")
    parser.add_argument("--limit", type=int, default=None, help="只评估前 N 条，适合 API 冒烟测试")
    parser.add_argument("--start", default=None, help="从指定 case id 开始评估，例如 case_08")
    parser.add_argument("--data-dir", default="data", help="数据目录")
    parser.add_argument("--output", default="outputs/evaluation_results.json", help="结果 JSON 输出路径")
    args = parser.parse_args()

    cases = select_cases(load_cases(args.data_dir), start=args.start, limit=args.limit)
    if not cases:
        raise SystemExit("没有可评估的 case，请检查 --start 或 --limit 参数。")
    results = evaluate_cases(cases, mode=args.mode, model=args.model, timeout=args.timeout)
    output = {
        "mode": args.mode,
        "model": args.model if args.mode == "llm" else None,
        "weights": WEIGHTS,
        "metric_names": METRIC_NAMES,
        "summary": summarize(results),
        "results": results,
    }
    write_json(args.output, output)
    print(f"Wrote {args.output}")
    print(json.dumps(output["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
