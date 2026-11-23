# ruff: noqa: E501
# Long lines below are embedded notebook cell source and prose.
"""Render frozen holdout evidence; this module never fits models or calls providers."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import nbformat


def render(root, evidence, notebook):
    report = json.loads((evidence / "report.json").read_text(encoding="utf-8"))
    figures = evidence / "figures"
    figures.mkdir(exist_ok=True)
    names = list(report["results"])
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(names[::-1], [report["results"][n]["macro_f1"] for n in names[::-1]], color="#345ea8")
    ax.set(
        xlim=(0, 1),
        xlabel="Macro-F1 (10 fixed labels)",
        title="Synthetic holdout — frozen classifiers and LLM",
    )
    fig.tight_layout()
    fig.savefig(figures / "comparison.png", dpi=150)
    plt.close(fig)
    for name, result in report["results"].items():
        for field, suffix in [
            ("confusion_matrix", "raw"),
            ("confusion_matrix_row_normalized", "normalized"),
        ]:
            fig, ax = plt.subplots(figsize=(11, 8))
            im = ax.imshow(result[field], cmap="Blues", vmin=0)
            ax.set(
                xticks=range(len(result["prediction_labels"])),
                xticklabels=result["prediction_labels"],
                yticks=range(len(result["truth_labels"])),
                yticklabels=result["truth_labels"],
                xlabel="Predicted intent (failures retained)",
                ylabel="Annotated intent",
                title=f"{name} — synthetic holdout ({suffix})",
            )
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
            fig.colorbar(im, ax=ax)
            fig.tight_layout()
            fig.savefig(figures / f"{name}-{suffix}.png", dpi=130)
            plt.close(fig)
    relative = evidence.relative_to(root).as_posix()
    cells = [
        nbformat.v4.new_markdown_cell("""# CAP-02 / CAP-03: frozen synthetic holdout
**AWS ML Engineering · 9 October 2026**

Owner-approved synthetic benchmark: 120 language-model-generated messages, 30 per language and 12 per intent. Models, prompt and labels were frozen before evaluation; no post-test tuning. This is **not independently collected human data**, a population estimate, or a shopping-action safety test. Historical development results remain in `cap03-model-comparison.ipynb`.

Run All only reads local evidence and displays results. It never loads model binaries, trains, downloads weights or calls an API."""),
        nbformat.v4.new_code_cell(
            '''import hashlib, html, json
from pathlib import Path
from IPython.display import HTML, Image, Markdown, display
root = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "eval/datasets/capstone-v1").exists())
evidence = root / "'''
            + relative
            + """"
report = json.loads((evidence / "report.json").read_text(encoding="utf-8"))
release_path = root / "eval/datasets/capstone-v1/holdout-20261009/release.json"
release = json.loads(release_path.read_text(encoding="utf-8"))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
assert sha(release_path) == report["binding"]["release_sha256"]
for name in ["protocol", "records", "review", "overlap"]:
    assert sha(root / release[name]) == release[name + "_sha256"]
records = json.loads((root / release["records"]).read_text(encoding="utf-8"))
assert len(records) == 120
local = json.loads((evidence / "offline.json").read_text(encoding="utf-8"))
assert local["binding"] == report["binding"]
paid = report["paid_ledger"]
assert paid["binding"] == report["binding"]
rows = {name: {key: value["prediction"] for key,value in result["attempts"].items()}
        for name,result in local["families"].items()}
rows["llm"] = {key:value.get("result",{}).get("prediction","__failure__") for key,value in paid["attempts"].items()}
for name, result in report["results"].items():
    correct = sum(rows.get(name,{}).get(r["case_id"]) == r["expected"]["intent"] for r in records)
    assert abs(result["accuracy"] - correct / len(records)) < 1e-12
    assert sum(map(sum,result["confusion_matrix"])) == 120
    m=result["confusion_matrix"]
    f1=[2*m[i][i]/(sum(m[i])+sum(row[i] for row in m)) if sum(m[i])+sum(row[i] for row in m) else 0 for i in range(10)]
    assert abs(sum(f1)/10-result["macro_f1"]) < 1e-12
print("Release hashes, input counts, accuracy, macro-F1 and denominators verified.")
def table(headers, data):
    display(HTML("<table><tr>"+"".join("<th>"+html.escape(str(h))+"</th>" for h in headers)+"</tr>"+
        "".join("<tr>"+"".join("<td>"+html.escape(str(v))+"</td>" for v in row)+"</tr>" for row in data)+"</table>"))"""
        ),
        nbformat.v4.new_markdown_cell(
            "## Same-input comparison\nAll eight contenders classify the same text into the same ten labels. Invalid outputs and missing attempts remain in the denominator. Differences between previous validation scores and this new set are not a controlled improvement."
        ),
        nbformat.v4.new_code_cell("""table(["Model","Correct / 120","Accuracy","Macro-F1","Failures","Missing attempts"],
 [[name,round(r["accuracy"]*120),f"{r['accuracy']:.2%}",round(r["macro_f1"],4),r["failure_count"],len(r["missing_attempts"])] for name,r in report["results"].items()])
display(Image(filename=str(evidence / "figures/comparison.png")))"""),
        nbformat.v4.new_markdown_cell(
            "## Language slices\nThirty synthetic messages per language. These small, authored slices do not establish performance on real shoppers."
        ),
        nbformat.v4.new_code_cell("""table(["Model","Language","n","Accuracy","Macro-F1"],[[name,lang,s["count"],f"{s['accuracy']:.2%}",round(s["macro_f1"],4)]
 for name,r in report["results"].items() for lang,s in r["per_language"].items()])"""),
        nbformat.v4.new_markdown_cell(
            "## Inspect all errors\nChange `selected_model` to any model key. Labels were finalized before predictions and are not rewritten to improve scores."
        ),
        nbformat.v4.new_code_cell("""selected_model = "llm"
display(Image(filename=str(evidence / f"figures/{selected_model}-raw.png")))
errors=[r for r in records if rows.get(selected_model,{}).get(r["case_id"]) != r["expected"]["intent"]]
table(["ID","Language","Message","Annotated","Predicted"], [[r["case_id"],r["language_group"],r["input"]["message"],r["expected"]["intent"],rows.get(selected_model,{}).get(r["case_id"],"__failure__")] for r in errors])"""),
        nbformat.v4.new_markdown_cell(
            "## Latency and cost\nLocal measurements include fresh text processing (and encoder for embedding heads), after one non-test warm-up. LLM timings include network/key checks. They are single-request label classification, not full shopping-task timings. Local electricity/hardware cost was not measured. Training timings/configurations remain in the earlier reports; no models were retrained."
        ),
        nbformat.v4.new_code_cell("""table(["Model","Timing samples","p50 ms","p95 ms"],[[n,r["latency_ms"]["sample_count"],r["latency_ms"]["p50"],r["latency_ms"]["p95"]] for n,r in report["results"].items()])
print("Paid spent plus unresolved reservations:",paid["spent_plus_reserved_usd"])
print("Experiment cap:",paid["cap_usd"])
print("Unknown costs:",sum(a["actual_cost_usd"] is None for a in paid["attempts"].values()))
display(local["environment"])"""),
        nbformat.v4.new_markdown_cell(
            "## Reproduction and limitations\nSee `docs/cap02-cap03-closeout.md` for commands, scope amendment, provenance, review and overlap limits. Earlier training/validation releases remain immutable. Reusing this consumed holdout to tune future models would make later scores development evidence. The LLM has broad pretraining and gets label definitions; classifiers learned the task from labeled training examples. This is equal per-case input, not equal pretraining or supervision."
        ),
    ]
    doc = nbformat.v4.new_notebook(
        cells=cells,
        metadata={
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}
        },
    )
    nbformat.validate(doc)
    nbformat.write(doc, notebook)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--notebook", type=Path, required=True)
    args = parser.parse_args()
    render(Path.cwd(), args.evidence.resolve(), args.notebook)
