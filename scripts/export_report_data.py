"""Export the interactive report from saved outputs without API calls."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = ["Hit@5", "MRR@5", "Faithfulness", "Answer relevancy", "Context precision", "Context recall"]
KEYS = ["hit_rate", "mrr", "faithfulness", "answer_relevancy", "context_precision", "context_recall"]


def main() -> None:
    notebook = json.loads((ROOT / "notebooks" / "legal_document_rag.ipynb").read_text(encoding="utf-8"))
    tables = [
        "".join(output["data"]["text/plain"])
        for cell in notebook["cells"]
        for output in cell.get("outputs", [])
        if "text/plain" in output.get("data", {})
    ]
    questions = []
    for table in tables:
        if "qid" not in table or "context_recall" not in table:
            continue
        for line in table.splitlines():
            parts = line.split()
            if len(parts) == 9 and re.fullmatch(r"(contractnli|cuad|maud)_\d+", parts[1]):
                scores = [float(value) for value in parts[3:]]
                if not all(0 <= value <= 1 for value in scores):
                    raise ValueError(f"Invalid question scores: {line}")
                questions.append({"id": parts[1], "group": parts[2], "scores": scores})
    metrics = json.loads((ROOT / "docs" / "assets" / "metrics.json").read_text(encoding="utf-8"))
    if len(questions) != metrics["evaluated_questions"]:
        raise ValueError("Saved question table and metrics.json disagree.")

    corpus = next(table for table in tables if "chars" in table and "words" in table and "privacy_qa" in table)
    names = {"contractnli": "ContractNLI", "cuad": "CUAD", "maud": "MAUD", "privacy_qa": "PrivacyQA"}
    groups = []
    for line in corpus.splitlines():
        parts = line.split()
        if parts and parts[0] in names and len(parts) == 9:
            groups.append([names[parts[0]], int(parts[1]), int(parts[6])])
    if len(groups) != 4 or sum(row[1] for row in groups) != 644:
        raise ValueError("The saved corpus summary is incomplete.")
    corpus_views = {}
    for key, label, index in [("documents", "Document count", 1), ("length", "Mean words per document", 2), ("words", "Estimated total words", 3)]:
        values = [row[index] if index < 3 else row[1] * row[2] for row in groups]
        corpus_views[key] = {
            "label": label, "xTitle": label, "columns": ["Collection", label],
            "rows": [[row[0], value] for row, value in zip(groups, values)],
            "note": "Word totals use document counts multiplied by rounded mean word counts." if key == "words" else "Values come from the notebook's saved corpus summary.",
            "traces": [{"type": "bar", "orientation": "h", "x": values, "y": [row[0] for row in groups],
                        "hovertemplate": "%{y}: %{x:,.0f}<extra></extra>"}],
            "yaxis": {"autorange": "reversed"}
        }
    evaluation_views = {}
    for key, label in [("all", "All 10 questions"), ("contractnli", "ContractNLI: 3 questions"), ("cuad", "CUAD: 4 questions"), ("maud", "MAUD: 3 questions")]:
        subset = [q for q in questions if key == "all" or q["group"] == key]
        scores = [metrics["scores"][name]["mean_score"] for name in KEYS] if key == "all" else [
            round(sum(q["scores"][i] for q in subset) / len(subset), 3) for i in range(6)
        ]
        evaluation_views[key] = {
            "label": label, "xTitle": "Score (0 to 1)", "xaxis": {"range": [0, 1]},
            "yaxis": {"autorange": "reversed"},
            "columns": ["Metric", "Mean score"], "rows": list(zip(LABELS, scores)),
            "note": "Overall scores use metrics.json. Collection means use the rounded saved per-question scores. This is a small diagnostic sample, not a benchmark-wide estimate.",
            "traces": [{"type": "bar", "orientation": "h", "x": scores, "y": LABELS,
                        "hovertemplate": "%{y}: %{x:.3f}<extra></extra>"}]
        }
    ranks = [0] * 6
    for question in questions:
        rank = round(1 / question["scores"][1]) if question["scores"][1] else 0
        ranks[rank] += 1
    rank_labels = ["No hit", "Rank 1", "Rank 2", "Rank 3", "Rank 4", "Rank 5"]
    report = {
        "source": "Saved notebook outputs; LegalBench-RAG publication year: 2024.",
        "questions": questions,
        "charts": {
            "corpus": {"title": "Corpus composition", "views": corpus_views},
            "evaluation": {"title": "Retrieval and answer scores", "views": evaluation_views},
            "question-scores": {"title": "Scores for every evaluated question", "views": {"all": {
                "label": "All questions", "note": "Click a row or use the question selector. Hit@5 and MRR@5 use reference-span overlap. The other four metrics are LLM-judged.",
                "columns": ["Question", *LABELS], "rows": [[q["id"], *q["scores"]] for q in questions],
                "traces": [{"type": "heatmap", "x": LABELS, "y": [q["id"] for q in questions],
                            "z": [q["scores"] for q in questions], "zmin": 0, "zmax": 1,
                            "showscale": False, "xgap": 3, "ygap": 3,
                            "hovertemplate": "%{y}<br>%{x}: %{z:.3f}<extra></extra>"}],
                "layout": {"margin": {"l": 115, "r": 10, "t": 10, "b": 90}},
                "xaxis": {"tickangle": -35}, "yaxis": {"autorange": "reversed"}
            }}},
            "ranking": {"title": "Rank of the first overlapping chunk", "views": {"all": {
                "label": "All questions", "xTitle": "First reference-span overlap", "yTitle": "Questions",
                "yaxis": {"dtick": 1}, "columns": ["Rank", "Questions"], "rows": list(zip(rank_labels, ranks)),
                "note": "A hit means any overlap with a reference span, not necessarily a complete clause or a correct answer.",
                "traces": [{"type": "bar", "x": rank_labels, "y": ranks, "hovertemplate": "%{x}: %{y} questions<extra></extra>"}]
            }}}
        }
    }
    chunk_table = next(table for table in tables if "chunks_per_doc" in table and "privacy_qa" in table)
    chunks = []
    for line in chunk_table.splitlines():
        parts = line.split()
        if parts and parts[0] in names and len(parts) == 4:
            chunks.append([names[parts[0]], int(parts[1]), float(parts[3])])
    if sum(row[1] for row in chunks) != 63914:
        raise ValueError("Chunk counts do not match the saved index size.")
    report["charts"]["index-size"] = {"title": "Index size by collection", "views": {}}
    for key, label, column in [("total", "Total chunks", 1), ("per-document", "Chunks per document", 2)]:
        report["charts"]["index-size"]["views"][key] = {
            "label": label, "yTitle": label, "note": "The chunk table comes from saved indexing outputs. Windows contain up to 1,500 characters with a 200-character overlap.",
            "columns": ["Collection", label], "rows": [[row[0], row[column]] for row in chunks],
            "traces": [{"type": "bar", "x": [row[0] for row in chunks], "y": [row[column] for row in chunks]}]
        }
    eligible_table = next(table for table in tables if "mean_snippets" in table and "answerable" in table)
    eligible = []
    for line in eligible_table.splitlines():
        parts = line.split()
        if parts and parts[0] in names and len(parts) == 4:
            eligible.append([names[parts[0]], int(parts[1]), int(parts[2])])
    if sum(row[2] for row in eligible) != 6033:
        raise ValueError("Eligible question counts have changed.")
    report["charts"]["eligibility"] = {"title": "Question eligibility", "views": {"all": {
        "label": "Available source documents", "yTitle": "Questions",
        "note": "A question is eligible when its referenced source document is available. Eligibility does not guarantee the system can answer it. Only ten eligible questions were evaluated.",
        "columns": ["Collection", "Eligible", "Missing source"], "rows": [[row[0], row[2], row[1] - row[2]] for row in eligible],
        "layout": {"barmode": "stack"},
        "traces": [
            {"type": "bar", "name": "Source available", "x": [row[0] for row in eligible], "y": [row[2] for row in eligible]},
            {"type": "bar", "name": "Source unavailable", "x": [row[0] for row in eligible], "y": [row[1] - row[2] for row in eligible]}
        ]
    }}}
    length_rows = []
    for line in corpus.splitlines():
        parts = line.split()
        if parts and parts[0] in names and len(parts) == 9:
            length_rows.append([names[parts[0]], int(parts[7]), int(parts[6]), int(parts[8])])
    report["charts"]["lengths"] = {"title": "Document length ranges", "views": {"all": {
        "label": "Collection ranges", "xTitle": "Words per document (logarithmic scale)",
        "xaxis": {"type": "log"}, "yaxis": {"autorange": "reversed"},
        "note": "Dots show the mean. Lines run from the shortest to the longest document, not a confidence interval. The horizontal axis is logarithmic.",
        "columns": ["Collection", "Minimum words", "Mean words", "Maximum words"], "rows": length_rows,
        "traces": [{"type": "scatter", "mode": "markers", "name": "Mean and range",
                    "x": [row[2] for row in length_rows], "y": [row[0] for row in length_rows],
                    "error_x": {"type": "data", "symmetric": False,
                                "array": [row[3] - row[2] for row in length_rows],
                                "arrayminus": [row[2] - row[1] for row in length_rows]},
                    "hovertemplate": "%{y}<br>Mean: %{x:,} words<extra></extra>"}]
    }}}
    output = ROOT / "docs" / "report-data.js"
    output.write_text("window.REPORT = " + json.dumps(report, ensure_ascii=True, allow_nan=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"Exported {len(questions)} questions and {len(report['charts'])} charts to {output.name}.")


if __name__ == "__main__":
    main()
