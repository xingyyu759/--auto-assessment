import argparse
import json
from pathlib import Path

from evaluator import METRIC_NAMES, WEIGHTS, load_cases


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def score_bar(distribution):
    return ", ".join(f"{score}分:{count}" for score, count in distribution.items())


def build_case_lookup(data_dir):
    return {case["id"]: case for case in load_cases(data_dir)}


def render_report(evaluation, data_dir):
    summary = evaluation["summary"]
    cases = build_case_lookup(data_dir)
    lines = [
        "# 自动回复质量评估报告",
        "",
        "## 评估配置",
        "",
        f"- 评估模式：{evaluation['mode']}",
        f"- LLM 模型：{evaluation.get('model') or '未使用，mock 模式'}",
        "- 指标权重："
    ]
    for metric, weight in WEIGHTS.items():
        lines.append(f"  - {METRIC_NAMES[metric]}：{int(weight * 100)}%")

    lines.extend(
        [
            "",
            "## 总体结果",
            "",
            f"- 样本数：{summary['case_count']}",
            f"- 整体平均分：{summary['overall_average']} / 5",
            "",
            "## 各指标平均分",
            "",
            "| 指标 | 平均分 | 权重 |",
            "| --- | ---: | ---: |",
        ]
    )
    for metric, average in summary["metric_averages"].items():
        lines.append(f"| {METRIC_NAMES[metric]} | {average} | {int(WEIGHTS[metric] * 100)}% |")

    lines.extend(["", "## 各指标分布", ""])
    for metric, distribution in summary["metric_distribution"].items():
        lines.append(f"- {METRIC_NAMES[metric]}：{score_bar(distribution)}")

    lines.extend(["", "## 最差 3 条 Case 分析", ""])
    result_map = {item["id"]: item for item in evaluation["results"]}
    for case_id in summary["worst_case_ids"]:
        result = result_map[case_id]
        case = cases[case_id]
        lines.extend(
            [
                f"### {case_id}",
                "",
                f"- 总分：{result['overall']} / 5",
                "- 单项分："
            ]
        )
        for metric, score in result["scores"].items():
            lines.append(f"  - {METRIC_NAMES[metric]}：{score}")
        lines.extend(
            [
                f"- 用户问题：{case['user_question']}",
                f"- 自动回复：{case['auto_reply']}",
                f"- 人工参考：{case['human_reference']}",
                f"- 人工分析：{case['annotator_notes']}",
                "- 系统识别问题：",
            ]
        )
        for issue in result.get("issues", []):
            lines.append(f"  - {issue}")
        lines.extend(["", f"- 评分理由：{result.get('reason', '')}", ""])

    lines.extend(
        [
            "## 与人工标注的一致性验证",
            "",
            "- case_08：人工认为属于“正确但没用”，系统应体现为准确性/真实性较高、有用性较低。",
            "- case_14：人工认为建议反馈处理较好，系统应给出较高总分。",
            "- case_20：人工认为重复流程、答非所问，系统应给出较低准确性和有用性。",
            "",
            "这类验证不是要求自动评估完全复刻人工回复，而是检查评分是否能复现人工指出的主要问题类型。",
            "",
            "## 局限性与改进",
            "",
            "- 缺少真实订单、物流、商品和优惠券系统数据时，真实性只能基于文本证据判断。",
            "- mock 模式可复现、可离线，但语义理解有限，适合演示流水线和做基线。",
            "- LLM 模式理解能力更强，但会受模型版本、prompt、温度和网络/API 状态影响。",
            "- 人工参考回复是弱金标准，不代表唯一正确答案；后续应扩大样本并引入多名标注员一致性检验。",
        ]
    )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="生成自动回复质量评估 Markdown 报告")
    parser.add_argument("--input", default="outputs/evaluation_results.json", help="评估 JSON 路径")
    parser.add_argument("--data-dir", default="data", help="数据目录")
    parser.add_argument("--output", default="outputs/evaluation_report.md", help="报告输出路径")
    args = parser.parse_args()

    evaluation = read_json(args.input)
    report = render_report(evaluation, args.data_dir)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(report, encoding="utf-8-sig")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
