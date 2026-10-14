"""Export charts and evaluation scores from the notebook's saved outputs."""

import base64
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "legal_document_rag.ipynb"
ASSETS = ROOT / "docs" / "assets"
CHARTS = {
    "tQT1UIcOHSp9": "document-lengths.png",
    "Q8eiDTy2Ic8z": "word-frequencies.png",
    "M-_SrvDcMnKi": "similarity-first-10.png",
    "t31ngfZTJimS": "similarity-random-10.png",
    "f4f1f24a": "evaluation.png",
}
METRICS = {
    "hit_rate", "mrr", "faithfulness",
    "answer_relevancy", "context_precision", "context_recall",
}


def text(value: str | list[str]) -> str:
    return "".join(value) if isinstance(value, list) else value


def export_assets() -> None:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    cells = {cell["id"]: cell for cell in notebook["cells"]}
    images = {}
    for cell_id, filename in CHARTS.items():
        outputs = [
            output["data"]["image/png"]
            for output in cells[cell_id].get("outputs", [])
            if "image/png" in output.get("data", {})
        ]
        if len(outputs) != 1:
            raise ValueError(f"{cell_id} must contain one saved chart; found {len(outputs)}.")
        image = base64.b64decode(text(outputs[0]), validate=True)
        if not image.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError(f"{filename} is not a PNG image.")
        images[filename] = image

    tables = [
        text(output["data"]["text/plain"])
        for output in cells["f4f1f24a"].get("outputs", [])
        if "text/plain" in output.get("data", {})
    ]
    summary = next(
        (table for table in tables if "mean_score" in table and "valid_samples" in table), None
    )
    if summary is None:
        raise ValueError("The notebook has no saved evaluation summary.")
    scores = {}
    for line in summary.splitlines():
        parts = line.split()
        if len(parts) != 3 or parts[0] not in METRICS:
            continue
        mean, count = float(parts[1]), float(parts[2])
        if not math.isfinite(mean) or not 0 <= mean <= 1 or not count.is_integer() or count < 1:
            raise ValueError(f"Invalid saved score: {line}")
        scores[parts[0]] = {"mean_score": mean, "valid_samples": int(count)}
    if set(scores) != METRICS:
        raise ValueError("The evaluation summary must contain all six metrics.")

    question_ids = {
        match.group(1)
        for table in tables
        for match in re.finditer(r"(?m)^\s*\d+\s+((?:contractnli|cuad|maud)_\d+)\s", table)
    }
    if not question_ids or any(score["valid_samples"] > len(question_ids) for score in scores.values()):
        raise ValueError("The saved question count does not match the score counts.")

    ASSETS.mkdir(parents=True, exist_ok=True)
    for filename, image in images.items():
        (ASSETS / filename).write_bytes(image)
    report = {
        "source_notebook": "notebooks/legal_document_rag.ipynb",
        "evaluated_questions": len(question_ids),
        "scores": scores,
    }
    (ASSETS / "metrics.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(images)} charts and metrics for {len(question_ids)} questions.")
    print("Only saved notebook outputs were read. No model or API calls were made.")


if __name__ == "__main__":
    export_assets()
