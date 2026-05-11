"""
generate_figures.py — Publication-quality figures for the research paper.

Reads ablation-raw.json and/or model-comparison-raw.json, produces PNG
figures in the specified output directory.

Usage:
  .venv/bin/python generate_figures.py                        (defaults)
  .venv/bin/python generate_figures.py \\
    --data-dir ../../data/result2 \\
    --output-dir findings2

Options:
  --data-dir   <path>  Directory containing raw JSON files
                       (default: ../../data/results relative to script)
  --output-dir <path>  Directory for output PNG files
                       (default: figures/ relative to script)

Ablation figures (fig1–fig5, fig10) are skipped if ablation-raw.json is absent.
Model figures (fig6–fig9) are skipped if model-comparison-raw.json is absent.
"""

import argparse
import json
import os
import re
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

# ─── CLI args ─────────────────────────────────────────────────────────────────

BASE = os.path.dirname(os.path.abspath(__file__))

parser = argparse.ArgumentParser(description="Generate research paper figures")
parser.add_argument(
    "--data-dir",
    default=os.path.join(BASE, "..", "data", "results"),
    help="Directory containing ablation-raw.json / model-comparison-raw.json",
)
parser.add_argument(
    "--output-dir",
    default=os.path.join(BASE, "figures"),
    help="Directory to write PNG figures into",
)
cli_args = parser.parse_args()

DATA    = os.path.realpath(cli_args.data_dir)
FIG_DIR = cli_args.output_dir if os.path.isabs(cli_args.output_dir) \
          else os.path.join(BASE, cli_args.output_dir)
os.makedirs(FIG_DIR, exist_ok=True)

ABLATION_PATH = os.path.join(DATA, "ablation-raw.json")
MODEL_PATH    = os.path.join(DATA, "model-comparison-raw.json")

# ─── Setup ────────────────────────────────────────────────────────────────────

sns.set_theme(style="whitegrid", font_scale=1.1)
plt.rcParams.update({
    "figure.dpi": 200,
    "savefig.dpi": 200,
    "font.family": "sans-serif",
})

# Color palettes
ABLATION_COLORS = ["#2196F3", "#FF9800", "#4CAF50", "#9C27B0", "#F44336"]
MODEL_COLORS = ["#2196F3", "#4CAF50", "#F44336", "#FF9800", "#9C27B0"]  # extended for >3 models
SAFE_COLOR = "#4CAF50"
UNSAFE_COLOR = "#F44336"

# ─── Helpers ──────────────────────────────────────────────────────────────────

def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def extract_size_b(model_name):
    """Extract numeric parameter count (billions) from tag like 'llama3.2:1b' or 'qwen3.5:9b'."""
    match = re.search(r":(\d+(?:\.\d+)?)b", model_name, re.IGNORECASE)
    return float(match.group(1)) if match else 0.0


def format_model_label(model_name):
    """Convert 'qwen3.5:4b' → 'Qwen3.5 4B', 'llama3.2:1b' → 'Llama3.2 1B'."""
    parts = model_name.split(":", 1)
    family = parts[0].replace("-", " ").title()
    size   = parts[1].upper() if len(parts) > 1 else ""
    return f"{family} {size}"


def get_models_sorted(model_data):
    """Return unique model names from data, sorted by parameter size ascending."""
    return sorted(set(r["model"] for r in model_data), key=extract_size_b)

def compute_metrics(results):
    tp = sum(1 for r in results if r["predictedLabel"] == "UNSAFE" and r["actualLabel"] == "UNSAFE")
    fp = sum(1 for r in results if r["predictedLabel"] == "UNSAFE" and r["actualLabel"] == "SAFE")
    fn = sum(1 for r in results if r["predictedLabel"] == "SAFE" and r["actualLabel"] == "UNSAFE")
    tn = sum(1 for r in results if r["predictedLabel"] == "SAFE" and r["actualLabel"] == "SAFE")
    total = tp + fp + fn + tn
    acc = (tp + tn) / total if total else 0
    prec = tp / (tp + fp) if (tp + fp) else 0
    rec = tp / (tp + fn) if (tp + fn) else 0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0
    fpr = fp / (fp + tn) if (fp + tn) else 0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "accuracy": acc,
            "precision": prec, "recall": rec, "f1": f1, "fpr": fpr, "total": total}


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 1: Ablation — Accuracy, Precision, Recall, F1 grouped bar chart
# ═══════════════════════════════════════════════════════════════════════════════

def fig1_ablation_metrics(abl_data):
    configs = ["rules-only", "semantic-only", "rules+semantic",
               "rules+semantic+rate+memory", "full-pipeline"]
    labels = ["C1: Rules", "C2: Semantic", "C3: Rules+Sem",
              "C4: +Rate+Mem", "C5: Full"]

    metrics_list = []
    for cfg in configs:
        subset = [r for r in abl_data if r["config"] == cfg]
        metrics_list.append(compute_metrics(subset))

    x = np.arange(len(configs))
    width = 0.18

    fig, ax = plt.subplots(figsize=(12, 6))

    metric_names = ["accuracy", "precision", "recall", "f1"]
    metric_labels = ["Accuracy", "Precision", "Recall", "F1"]
    colors = ["#2196F3", "#FF9800", "#4CAF50", "#9C27B0"]

    for i, (metric, label, color) in enumerate(zip(metric_names, metric_labels, colors)):
        vals = [m[metric] * 100 for m in metrics_list]
        bars = ax.bar(x + i * width, vals, width, label=label, color=color, alpha=0.85)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                    f"{val:.1f}", ha="center", va="bottom", fontsize=8)

    ax.set_xlabel("Pipeline Configuration")
    ax.set_ylabel("Score (%)")
    ax.set_title("Figure 1: Ablation Study — Per-Configuration Metrics")
    ax.set_xticks(x + width * 1.5)
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_ylim(0, 110)
    ax.legend(loc="upper right")
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))

    fig.savefig(os.path.join(FIG_DIR, "fig1_ablation_metrics.png"))
    plt.close(fig)
    print("  [OK] fig1_ablation_metrics.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 2: Ablation — Confusion matrix heatmaps (side by side)
# ═══════════════════════════════════════════════════════════════════════════════

def fig2_ablation_confusion(abl_data):
    configs = ["rules-only", "semantic-only", "rules+semantic",
               "rules+semantic+rate+memory", "full-pipeline"]
    labels = ["C1: Rules", "C2: Semantic", "C3: Rules+Sem",
              "C4: +Rate+Mem", "C5: Full"]

    fig, axes = plt.subplots(1, 5, figsize=(20, 5))
    fig.suptitle("Figure 2: Ablation — Confusion Matrices", fontsize=14, y=0.98)

    for ax, cfg, label in zip(axes, configs, labels):
        m = compute_metrics([r for r in abl_data if r["config"] == cfg])
        cm = np.array([[m["tn"], m["fp"]], [m["fn"], m["tp"]]])
        sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", ax=ax, cbar=False,
                    xticklabels=["Pred SAFE", "Pred UNSAFE"],
                    yticklabels=["Act SAFE", "Act UNSAFE"],
                    annot_kws={"fontsize": 14})
        ax.set_title(label, fontsize=10)

    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig2_ablation_confusion.png"))
    plt.close(fig)
    print("  [OK] fig2_ablation_confusion.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 3: Ablation — Per-category accuracy heatmap
# ═══════════════════════════════════════════════════════════════════════════════

def fig3_category_heatmap(abl_data):
    configs = ["rules-only", "semantic-only", "rules+semantic",
               "rules+semantic+rate+memory", "full-pipeline"]
    col_labels = ["C1: Rules", "C2: Semantic", "C3: Rules+Sem",
                  "C4: +Rate+Mem", "C5: Full"]
    categories = sorted(set(r["category"] for r in abl_data))

    matrix = []
    for cat in categories:
        row = []
        for cfg in configs:
            subset = [r for r in abl_data if r["config"] == cfg and r["category"] == cat]
            correct = sum(1 for r in subset if r["predictedLabel"] == r["actualLabel"])
            row.append(correct / len(subset) * 100 if subset else 0)
        matrix.append(row)

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.heatmap(matrix, annot=True, fmt=".1f", cmap="RdYlGn", ax=ax,
                xticklabels=col_labels, yticklabels=categories,
                vmin=0, vmax=100, linewidths=0.5,
                annot_kws={"fontsize": 10})
    ax.set_title("Figure 3: Per-Category Accuracy (%) Across Ablation Configs")
    ax.set_xlabel("Configuration")
    ax.set_ylabel("Attack Category")

    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig3_category_heatmap.png"))
    plt.close(fig)
    print("  [OK] fig3_category_heatmap.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 4: Ablation — FPR progression (bar chart)
# ═══════════════════════════════════════════════════════════════════════════════

def fig4_fpr_progression(abl_data):
    configs = ["rules-only", "semantic-only", "rules+semantic",
               "rules+semantic+rate+memory", "full-pipeline"]
    labels = ["C1: Rules", "C2: Semantic", "C3: Rules+Sem",
              "C4: +Rate+Mem", "C5: Full"]

    fprs = []
    for cfg in configs:
        m = compute_metrics([r for r in abl_data if r["config"] == cfg])
        fprs.append(m["fpr"] * 100)

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(labels, fprs, color=ABLATION_COLORS, alpha=0.85, edgecolor="white")

    for bar, val in zip(bars, fprs):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                f"{val:.1f}%", ha="center", va="bottom", fontsize=11, fontweight="bold")

    ax.set_ylabel("False Positive Rate (%)")
    ax.set_title("Figure 4: False Positive Rate Across Ablation Configs")
    ax.set_ylim(0, max(fprs) * 1.3)
    plt.xticks(rotation=15, ha="right")

    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig4_fpr_progression.png"))
    plt.close(fig)
    print("  [OK] fig4_fpr_progression.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 5: Ablation — Layer delta analysis (waterfall-style)
# ═══════════════════════════════════════════════════════════════════════════════

def fig5_delta_analysis(abl_data):
    configs = ["rules-only", "semantic-only", "rules+semantic",
               "rules+semantic+rate+memory", "full-pipeline"]

    metrics_list = []
    for cfg in configs:
        metrics_list.append(compute_metrics([r for r in abl_data if r["config"] == cfg]))

    transitions = [
        "C1→C2\n(rules→semantic)",
        "C2→C3\n(+rules)",
        "C3→C4\n(+rate+mem)",
        "C4→C5\n(+RAG)",
    ]

    metric_names = ["accuracy", "precision", "recall", "f1"]
    metric_labels = ["Accuracy", "Precision", "Recall", "F1"]

    fig, axes = plt.subplots(1, 4, figsize=(16, 5), sharey=True)
    fig.suptitle("Figure 5: Layer Contribution — Delta Analysis", fontsize=14)

    for ax, metric, label in zip(axes, metric_names, metric_labels):
        deltas = []
        for i in range(1, len(configs)):
            d = (metrics_list[i][metric] - metrics_list[i - 1][metric]) * 100
            deltas.append(d)

        colors = [SAFE_COLOR if d >= 0 else UNSAFE_COLOR for d in deltas]
        bars = ax.bar(transitions, deltas, color=colors, alpha=0.8, edgecolor="white")

        for bar, val in zip(bars, deltas):
            y = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2,
                    y + (1 if y >= 0 else -3),
                    f"{val:+.1f}", ha="center", va="bottom" if y >= 0 else "top",
                    fontsize=9, fontweight="bold")

        ax.set_title(label)
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_ylabel("Delta (pp)" if ax == axes[0] else "")

    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig5_delta_analysis.png"))
    plt.close(fig)
    print("  [OK] fig5_delta_analysis.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 6: Model Comparison — Grouped bar chart (Acc, Prec, Rec, F1)
# ═══════════════════════════════════════════════════════════════════════════════

def fig6_model_metrics(model_data):
    models = get_models_sorted(model_data)
    labels = [format_model_label(m) for m in models]

    metrics_list = []
    for model in models:
        subset = [r for r in model_data if r["model"] == model]
        metrics_list.append(compute_metrics(subset))

    x = np.arange(len(models))
    width = 0.18

    fig, ax = plt.subplots(figsize=(max(10, len(models) * 3), 6))

    metric_names = ["accuracy", "precision", "recall", "f1"]
    metric_labels = ["Accuracy", "Precision", "Recall", "F1"]
    colors = ["#2196F3", "#FF9800", "#4CAF50", "#9C27B0"]

    for i, (metric, label, color) in enumerate(zip(metric_names, metric_labels, colors)):
        vals = [m[metric] * 100 for m in metrics_list]
        bars = ax.bar(x + i * width, vals, width, label=label, color=color, alpha=0.85)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                    f"{val:.1f}", ha="center", va="bottom", fontsize=9)

    ax.set_xlabel("Model")
    ax.set_ylabel("Score (%)")
    ax.set_title("Figure 6: Model-Size Comparison — Performance Metrics")
    ax.set_xticks(x + width * 1.5)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 115)
    ax.legend(loc="lower right")

    fig.savefig(os.path.join(FIG_DIR, "fig6_model_metrics.png"))
    plt.close(fig)
    print("  [OK] fig6_model_metrics.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 7: Model Comparison — FP count stacked by subcategory
# ═══════════════════════════════════════════════════════════════════════════════

def fig7_model_fp_breakdown(model_data):
    models = get_models_sorted(model_data)
    labels = [format_model_label(m) for m in models]
    subcats = sorted(set(
        r.get("subcategory", "") for r in model_data
        if r["predictedLabel"] == "UNSAFE" and r["actualLabel"] == "SAFE"
    ) | {"simple_command", "edge_case_safe", "conversational", "data_input",
          "minimal_input", "multi_word_safe", "natural_language", "false_positive_bait"})

    fp_data = {}
    for sub in subcats:
        fp_data[sub] = []
        for model in models:
            fps = sum(1 for r in model_data
                      if r["model"] == model and r["predictedLabel"] == "UNSAFE"
                      and r["actualLabel"] == "SAFE" and r.get("subcategory") == sub)
            fp_data[sub].append(fps)

    total_fps = sum(sum(v) for v in fp_data.values())

    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(models))

    if total_fps == 0:
        # All models have zero FPs — show a clear "perfect" visualization
        bar_colors = [SAFE_COLOR] * len(models)
        ax.bar(x, [0] * len(models), color=bar_colors, edgecolor="white")
        ax.set_ylim(0, 5)
        ax.set_yticks(range(6))
        for i, label in enumerate(labels):
            ax.text(i, 2.0, "0 FP", ha="center", va="center",
                    fontsize=22, fontweight="bold", color=SAFE_COLOR)
            ax.text(i, 1.2, "100% Specificity", ha="center", va="center",
                    fontsize=10, color="#666666")
    else:
        bottom = np.zeros(len(models))
        cmap = plt.cm.Set2
        for i, sub in enumerate(subcats):
            vals = np.array(fp_data[sub])
            ax.bar(x, vals, bottom=bottom, label=sub, color=cmap(i / len(subcats)),
                   edgecolor="white", linewidth=0.5)
            bottom += vals

        for i, total in enumerate(bottom):
            ax.text(i, total + 0.5, f"{int(total)}", ha="center", va="bottom",
                    fontsize=12, fontweight="bold")
        ax.legend(loc="upper left", fontsize=8, ncol=2)

    ax.set_xlabel("Model")
    ax.set_ylabel("False Positive Count")
    ax.set_title("Figure 7: False Positives by Benign Subcategory")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)

    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig7_model_fp_breakdown.png"))
    plt.close(fig)
    print("  [OK] fig7_model_fp_breakdown.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 8: Model Comparison — Confusion matrices side by side
# ═══════════════════════════════════════════════════════════════════════════════

def fig8_model_confusion(model_data):
    models = get_models_sorted(model_data)
    labels = [format_model_label(m) for m in models]

    fig, axes = plt.subplots(1, len(models), figsize=(max(14, len(models) * 5), 5))
    fig.suptitle("Figure 8: Model Comparison — Confusion Matrices", fontsize=14, y=0.98)

    axes_list = [axes] if len(models) == 1 else list(axes)
    for ax, model, label in zip(axes_list, models, labels):
        m = compute_metrics([r for r in model_data if r["model"] == model])
        cm = np.array([[m["tn"], m["fp"]], [m["fn"], m["tp"]]])
        sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", ax=ax, cbar=False,
                    xticklabels=["Pred SAFE", "Pred UNSAFE"],
                    yticklabels=["Act SAFE", "Act UNSAFE"],
                    annot_kws={"fontsize": 16})
        ax.set_title(label, fontsize=11)

    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig8_model_confusion.png"))
    plt.close(fig)
    print("  [OK] fig8_model_confusion.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 9: Model Comparison — FPR vs Model Size (line chart)
# ═══════════════════════════════════════════════════════════════════════════════

def fig9_fpr_vs_size(model_data):
    models = get_models_sorted(model_data)
    sizes  = [extract_size_b(m) for m in models]
    labels = [f"{s:g}B" for s in sizes]

    fprs = []
    accs = []
    for model in models:
        m = compute_metrics([r for r in model_data if r["model"] == model])
        fprs.append(m["fpr"] * 100)
        accs.append(m["accuracy"] * 100)

    fig, ax1 = plt.subplots(figsize=(8, 5))

    ax1.plot(sizes, accs, "o-", color="#2196F3", linewidth=2, markersize=10, label="Accuracy")
    ax1.set_xlabel("Model Size (Billion Parameters)")
    ax1.set_ylabel("Accuracy (%)", color="#2196F3")
    ax1.tick_params(axis="y", labelcolor="#2196F3")

    ax2 = ax1.twinx()
    ax2.plot(sizes, fprs, "s--", color="#F44336", linewidth=2, markersize=10, label="FPR")
    ax2.set_ylabel("False Positive Rate (%)", color="#F44336")
    ax2.tick_params(axis="y", labelcolor="#F44336")

    for s, a, f in zip(sizes, accs, fprs):
        ax1.annotate(f"{a:.1f}%", (s, a), textcoords="offset points",
                     xytext=(0, 12), ha="center", fontsize=10, color="#2196F3")
        ax2.annotate(f"{f:.1f}%", (s, f), textcoords="offset points",
                     xytext=(0, -15), ha="center", fontsize=10, color="#F44336")

    ax1.set_xticks(sizes)
    ax1.set_xticklabels(labels)
    ax1.set_title("Figure 9: Accuracy & FPR vs. Model Size")

    lines1, lab1 = ax1.get_legend_handles_labels()
    lines2, lab2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, lab1 + lab2, loc="center right")

    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig9_fpr_vs_size.png"))
    plt.close(fig)
    print("  [OK] fig9_fpr_vs_size.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE M1: Model Comparison — Per-category accuracy heatmap
# ═══════════════════════════════════════════════════════════════════════════════

def figM1_model_category_heatmap(model_data):
    models = get_models_sorted(model_data)
    labels = [format_model_label(m) for m in models]
    categories = sorted(set(r["category"] for r in model_data))

    matrix = []
    for cat in categories:
        row = []
        for model in models:
            subset = [r for r in model_data if r["model"] == model and r["category"] == cat]
            correct = sum(1 for r in subset if r["predictedLabel"] == r["actualLabel"])
            row.append(correct / len(subset) * 100 if subset else 0)
        matrix.append(row)

    fig, ax = plt.subplots(figsize=(max(8, len(models) * 3), 7))
    sns.heatmap(matrix, annot=True, fmt=".1f", cmap="RdYlGn", ax=ax,
                xticklabels=labels, yticklabels=categories,
                vmin=0, vmax=100, linewidths=0.5,
                annot_kws={"fontsize": 10})
    ax.set_title("Per-Category Accuracy (%) Across Models")
    ax.set_xlabel("Model")
    ax.set_ylabel("Attack Category")

    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "figM1_model_category_heatmap.png"))
    plt.close(fig)
    print("  [OK] figM1_model_category_heatmap.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE M2: Model Comparison — Latency breakdown (grouped bar)
# ═══════════════════════════════════════════════════════════════════════════════

def figM2_model_latency(model_data):
    models = get_models_sorted(model_data)
    labels = [format_model_label(m) for m in models]

    latencies = {}
    for model in models:
        subset = [r for r in model_data if r["model"] == model]
        lats = sorted([r["latencyMs"] for r in subset])
        n = len(lats)
        latencies[model] = {
            "avg": sum(lats) / n if n else 0,
            "p50": lats[n // 2] if n else 0,
            "p95": lats[int(n * 0.95)] if n else 0,
        }

    x = np.arange(len(models))
    width = 0.25

    fig, ax = plt.subplots(figsize=(max(8, len(models) * 3), 6))

    stat_names = ["avg", "p50", "p95"]
    stat_labels = ["Average", "P50 (Median)", "P95"]
    colors = ["#2196F3", "#4CAF50", "#F44336"]

    for i, (stat, label, color) in enumerate(zip(stat_names, stat_labels, colors)):
        vals = [latencies[m][stat] / 1000 for m in models]  # convert to seconds
        bars = ax.bar(x + i * width, vals, width, label=label, color=color, alpha=0.85)
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                    f"{val:.1f}s", ha="center", va="bottom", fontsize=9)

    ax.set_xlabel("Model")
    ax.set_ylabel("Latency (seconds)")
    ax.set_title("Latency Breakdown by Model Size")
    ax.set_xticks(x + width)
    ax.set_xticklabels(labels)
    ax.legend(loc="upper left")

    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "figM2_model_latency.png"))
    plt.close(fig)
    print("  [OK] figM2_model_latency.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE M3: Model Comparison — F1 vs FPR scatter (like fig10 for ablation)
# ═══════════════════════════════════════════════════════════════════════════════

def figM3_model_f1_vs_fpr(model_data):
    models = get_models_sorted(model_data)

    fig, ax = plt.subplots(figsize=(8, 6))

    # Collect points first to detect overlaps
    points = []
    for model, color in zip(models, MODEL_COLORS):
        m = compute_metrics([r for r in model_data if r["model"] == model])
        label = format_model_label(model)
        points.append({"fpr": m["fpr"] * 100, "f1": m["f1"] * 100,
                        "label": label, "color": color})

    # Assign vertical offsets to separate overlapping labels
    for i, pt in enumerate(points):
        ax.scatter(pt["fpr"], pt["f1"], s=200, c=pt["color"], edgecolors="black",
                   linewidth=1, zorder=5)
        # Check if this point overlaps a previous one (within 0.5% on both axes)
        y_offset = 8
        for prev in points[:i]:
            if abs(pt["fpr"] - prev["fpr"]) < 0.5 and abs(pt["f1"] - prev["f1"]) < 0.5:
                y_offset = -18  # place below the dot instead
                break
        ax.annotate(pt["label"], (pt["fpr"], pt["f1"]),
                    textcoords="offset points", xytext=(8, y_offset), fontsize=10)

    ax.set_xlabel("False Positive Rate (%)")
    ax.set_ylabel("F1 Score (%)")
    ax.set_title("F1 vs. FPR Tradeoff (Model Comparison)")
    all_f1 = [pt["f1"] for pt in points]
    ax.set_ylim(max(0, min(all_f1) - 10), 105)

    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "figM3_model_f1_vs_fpr.png"))
    plt.close(fig)
    print("  [OK] figM3_model_f1_vs_fpr.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 10: Combined — Ablation F1 vs FPR tradeoff scatter
# ═══════════════════════════════════════════════════════════════════════════════

def fig10_f1_vs_fpr(abl_data):
    configs = ["rules-only", "semantic-only", "rules+semantic",
               "rules+semantic+rate+memory", "full-pipeline"]
    labels = ["C1: Rules", "C2: Semantic", "C3: Rules+Sem",
              "C4: +Rate+Mem", "C5: Full"]

    fig, ax = plt.subplots(figsize=(8, 6))

    for cfg, label, color in zip(configs, labels, ABLATION_COLORS):
        m = compute_metrics([r for r in abl_data if r["config"] == cfg])
        ax.scatter(m["fpr"] * 100, m["f1"] * 100, s=200, c=color, edgecolors="black",
                   linewidth=1, zorder=5)
        ax.annotate(label, (m["fpr"] * 100, m["f1"] * 100),
                    textcoords="offset points", xytext=(8, 8), fontsize=9)

    ax.set_xlabel("False Positive Rate (%)")
    ax.set_ylabel("F1 Score (%)")
    ax.set_title("Figure 10: F1 vs. FPR Tradeoff (Ablation Configs)")
    ax.set_xlim(-1, 25)
    ax.set_ylim(20, 105)

    fig.tight_layout()
    fig.savefig(os.path.join(FIG_DIR, "fig10_f1_vs_fpr.png"))
    plt.close(fig)
    print("  [OK] fig10_f1_vs_fpr.png")


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("\n  Figure Generator — Research Paper Findings")
    print("  ──────────────────────────────────────────")
    print(f"  Data dir:   {DATA}")
    print(f"  Output dir: {FIG_DIR}\n")

    abl_data   = None
    model_data = None

    if os.path.exists(ABLATION_PATH):
        abl_data = load_json(ABLATION_PATH)
        print(f"  Loaded ablation data:         {len(abl_data)} entries")
    else:
        print("  Ablation data not found — skipping fig1–fig5, fig10")

    if os.path.exists(MODEL_PATH):
        model_data = load_json(MODEL_PATH)
        print(f"  Loaded model comparison data: {len(model_data)} entries")
    else:
        print("  Model comparison data not found — skipping fig6–fig9")

    if not abl_data and not model_data:
        print("\n  No data files found. Nothing to generate.")
        return

    print()
    count = 0

    # Ablation figures (require ablation data)
    if abl_data:
        fig1_ablation_metrics(abl_data);  count += 1
        fig2_ablation_confusion(abl_data); count += 1
        fig3_category_heatmap(abl_data);   count += 1
        fig4_fpr_progression(abl_data);    count += 1
        fig5_delta_analysis(abl_data);     count += 1

    # Model comparison figures (require model data)
    if model_data:
        fig6_model_metrics(model_data);          count += 1
        fig7_model_fp_breakdown(model_data);     count += 1
        fig8_model_confusion(model_data);        count += 1
        fig9_fpr_vs_size(model_data);            count += 1
        figM1_model_category_heatmap(model_data); count += 1
        figM2_model_latency(model_data);          count += 1
        figM3_model_f1_vs_fpr(model_data);        count += 1

    # Combined (requires ablation data)
    if abl_data:
        fig10_f1_vs_fpr(abl_data); count += 1

    print(f"\n  Done! {count} figures saved to {FIG_DIR}/\n")


if __name__ == "__main__":
    main()
