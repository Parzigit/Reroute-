import os
import sys
import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

sys.path.insert(0, os.path.dirname(__file__))
from sdn_bayesian_system import BayesianFlowAdmission
from fuzzy_flow_admission import FuzzyFlowAdmission

OUT = os.path.join(os.path.dirname(__file__), "comparison_results")
os.makedirs(OUT, exist_ok=True)

bayes = BayesianFlowAdmission(prior_la=0.5)
fuzzy = FuzzyFlowAdmission(threshold=0.5)

CAPACITY = 1000.0 
def evaluate_both(pu, rb_mbps):
    """Returns (bayes_pla, bayes_decision, fuzzy_la, fuzzy_decision)."""
    rb_positive = rb_mbps > 0
    if rb_positive:
        p_la = bayes.compute_link_availability(pu, True)
    else:
        p_la = 0.0
    b_dec = "ADMIT" if p_la > 0.5 else "BLOCK"

    if rb_mbps <= 0:
        return p_la, b_dec, 0.0, "BLOCK"

    f_la, f_dec, _ = fuzzy.compute_link_availability(pu, rb_mbps, CAPACITY)
    return p_la, b_dec, f_la, f_dec


def analysis_1_posterior_flatness():
    """
    Hold PU constant at several levels; sweep RB from 1 to 800 Mbps.
    Show that Bayesian P(LA) is constant while Fuzzy LA varies.
    """
    print("\n[1] Posterior Flatness — Bayesian RB Insensitivity")

    rb_range = np.linspace(1, 800, 200)
    pu_levels = [30, 50, 60, 70]
    colors_b = ["#8b5cf6", "#a78bfa", "#c4b5fd", "#ddd6fe"]
    colors_f = ["#06b6d4", "#22d3ee", "#67e8f9", "#a5f3fc"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
    fig.suptitle("Posterior Flatness: Bayesian vs Fuzzy Response to RB",
                 fontsize=14, fontweight="bold", color="#1e293b")

    stats = {}
    for i, pu in enumerate(pu_levels):
        b_vals = []
        f_vals = []
        for rb in rb_range:
            pla, _, fla, _ = evaluate_both(pu, rb)
            b_vals.append(pla)
            f_vals.append(fla)

        b_vals = np.array(b_vals)
        f_vals = np.array(f_vals)

        ax1.plot(rb_range, b_vals, color=colors_b[i], linewidth=2,
                 label=f"PU={pu}%")
        ax2.plot(rb_range, f_vals, color=colors_f[i], linewidth=2,
                 label=f"PU={pu}%")

        b_range = b_vals.max() - b_vals.min()
        f_range = f_vals.max() - f_vals.min()
        stats[pu] = {"bayes_range": b_range, "fuzzy_range": f_range}
        print(f"  PU={pu}%: Bayesian Δ={b_range:.4f}, Fuzzy Δ={f_range:.4f}")

    for ax, title in [(ax1, "Bayesian P(LA)"), (ax2, "Fuzzy LA")]:
        ax.set_xlabel("Residual Bandwidth (Mbps)", fontsize=11)
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_ylim(-0.05, 1.05)
        ax.axhline(0.5, color="#94a3b8", linestyle="--", linewidth=0.8, alpha=0.5)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.15)
        ax.set_facecolor("#f8fafc")

    ax1.set_ylabel("Availability Score", fontsize=11)
    ax1.annotate("Bayesian: FLAT lines — RB\nmagnitude has zero effect",
                 xy=(400, 0.85), fontsize=9, color="#6b21a8",
                 bbox=dict(boxstyle="round,pad=0.3", facecolor="#f3e8ff", alpha=0.8))

    fig.tight_layout(rect=[0, 0, 1, 0.93])
    path = os.path.join(OUT, "01_posterior_flatness.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  → saved {path}")
    return stats

def analysis_2_disagreement_zone():
    """
    Sweep PU×RB grid. For each point, record whether Bayesian and Fuzzy
    agree or disagree. Visualise the disagreement region as a heatmap.
    """
    print("\n[2] Disagreement Zone Analysis")

    pu_range = np.linspace(5, 95, 100)
    rb_range = np.linspace(1, 800, 100)
    PU, RB = np.meshgrid(pu_range, rb_range)

    # 0=both admit, 1=both block, 2=bayes admit & fuzzy block, 3=reverse
    decision_map = np.zeros_like(PU, dtype=int)
    b_scores = np.zeros_like(PU)
    f_scores = np.zeros_like(PU)

    disagree_points = []

    for i in range(PU.shape[0]):
        for j in range(PU.shape[1]):
            pu, rb = PU[i, j], RB[i, j]
            pla, bdec, fla, fdec = evaluate_both(pu, rb)
            b_scores[i, j] = pla
            f_scores[i, j] = fla

            if bdec == "ADMIT" and fdec == "ADMIT":
                decision_map[i, j] = 0
            elif bdec == "BLOCK" and fdec == "BLOCK":
                decision_map[i, j] = 1
            elif bdec == "ADMIT" and fdec == "BLOCK":
                decision_map[i, j] = 2
                disagree_points.append((pu, rb, pla, fla))
            else:
                decision_map[i, j] = 3
                disagree_points.append((pu, rb, pla, fla))

    n_total = PU.size
    n_agree = np.sum((decision_map == 0) | (decision_map == 1))
    n_bayes_only = np.sum(decision_map == 2)
    n_fuzzy_only = np.sum(decision_map == 3)
    n_disagree = n_bayes_only + n_fuzzy_only

    print(f"  Agreement:      {n_agree}/{n_total} ({100*n_agree/n_total:.1f}%)")
    print(f"  Disagreement:   {n_disagree}/{n_total} ({100*n_disagree/n_total:.1f}%)")
    print(f"    Bayes ADMIT, Fuzzy BLOCK: {n_bayes_only} ({100*n_bayes_only/n_total:.1f}%)")
    print(f"    Fuzzy ADMIT, Bayes BLOCK: {n_fuzzy_only} ({100*n_fuzzy_only/n_total:.1f}%)")

    if disagree_points:
        d_pu = [p[0] for p in disagree_points]
        print(f"  Disagreement PU range: {min(d_pu):.1f}%–{max(d_pu):.1f}%")
        d_rb = [p[1] for p in disagree_points]
        print(f"  Disagreement RB range: {min(d_rb):.0f}–{max(d_rb):.0f} Mbps")

    # Plot
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))
    fig.suptitle("Decision Space: Bayesian vs Fuzzy",
                 fontsize=14, fontweight="bold", color="#1e293b")

    from matplotlib.colors import ListedColormap
    cmap = ListedColormap(["#22c55e", "#64748b", "#f97316", "#3b82f6"])
    labels = ["Both ADMIT", "Both BLOCK", "Bayes ADMIT\nFuzzy BLOCK", "Fuzzy ADMIT\nBayes BLOCK"]

    im = axes[0].pcolormesh(PU, RB, decision_map, cmap=cmap, vmin=-0.5, vmax=3.5)
    axes[0].set_title("Decision Agreement Map", fontweight="bold")
    axes[0].set_xlabel("Port Utilization (%)")
    axes[0].set_ylabel("Residual Bandwidth (Mbps)")
    cbar = fig.colorbar(im, ax=axes[0], ticks=[0, 1, 2, 3])
    cbar.ax.set_yticklabels(labels, fontsize=8)

    # Bayesian score heatmap
    im2 = axes[1].pcolormesh(PU, RB, b_scores, cmap="RdYlGn", vmin=0, vmax=1)
    axes[1].set_title("Bayesian P(LA)", fontweight="bold")
    axes[1].set_xlabel("Port Utilization (%)")
    axes[1].set_ylabel("Residual Bandwidth (Mbps)")
    fig.colorbar(im2, ax=axes[1])
    axes[1].contour(PU, RB, b_scores, levels=[0.5], colors=["black"],
                    linewidths=1.5, linestyles="--")

    # Fuzzy score heatmap
    im3 = axes[2].pcolormesh(PU, RB, f_scores, cmap="RdYlGn", vmin=0, vmax=1)
    axes[2].set_title("Fuzzy LA", fontweight="bold")
    axes[2].set_xlabel("Port Utilization (%)")
    axes[2].set_ylabel("Residual Bandwidth (Mbps)")
    fig.colorbar(im3, ax=axes[2])
    axes[2].contour(PU, RB, f_scores, levels=[0.5], colors=["black"],
                    linewidths=1.5, linestyles="--")

    for ax in axes:
        ax.set_facecolor("#f8fafc")

    fig.tight_layout(rect=[0, 0, 1, 0.93])
    path = os.path.join(OUT, "02_disagreement_zone.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  → saved {path}")

    return {
        "agreement_pct": 100 * n_agree / n_total,
        "disagree_pct": 100 * n_disagree / n_total,
        "bayes_admits_fuzzy_blocks": n_bayes_only,
        "fuzzy_admits_bayes_blocks": n_fuzzy_only,
        "disagree_pu_range": (min(d_pu), max(d_pu)) if disagree_points else (0, 0),
    }

def analysis_3_path_ranking():
    """
    Generate 3 candidate alternate paths with varying link conditions.
    Show that Bayesian gives nearly identical scores while Fuzzy differentiates.
    """
    print("\n[3] Path Ranking — Discriminating between candidate paths")

    paths = {
        "Path A\n(Best)": [
            (20, 700), (25, 650), (15, 800), (30, 600),  
        ],
        "Path B\n(Medium)": [
            (45, 350), (40, 400), (50, 300), (35, 450),  
        ],
        "Path C\n(Worst)": [
            (60, 150), (55, 200), (65, 100), (58, 180), 
        ],
    }

    results = {}
    print(f"  {'Path':<15} {'Bayes Avg':<12} {'Bayes Std':<12} {'Fuzzy Avg':<12} {'Fuzzy Std':<12}")
    print(f"  {'─'*63}")

    for name, links in paths.items():
        b_scores = []
        f_scores = []
        for pu, rb in links:
            pla, _, fla, _ = evaluate_both(pu, rb)
            b_scores.append(pla)
            f_scores.append(fla)

        b_avg, b_std = np.mean(b_scores), np.std(b_scores)
        f_avg, f_std = np.mean(f_scores), np.std(f_scores)
        short = name.replace("\n", " ")
        print(f"  {short:<15} {b_avg:<12.4f} {b_std:<12.4f} {f_avg:<12.4f} {f_std:<12.4f}")
        results[name] = {
            "bayes_scores": b_scores, "fuzzy_scores": f_scores,
            "bayes_avg": b_avg, "fuzzy_avg": f_avg,
        }

    # Discriminability = spread between best and worst path's average score
    path_names = list(results.keys())
    b_spread = results[path_names[0]]["bayes_avg"] - results[path_names[2]]["bayes_avg"]
    f_spread = results[path_names[0]]["fuzzy_avg"] - results[path_names[2]]["fuzzy_avg"]
    print(f"\n  Bayesian spread (Best - Worst): {b_spread:.4f}")
    print(f"  Fuzzy spread    (Best - Worst): {f_spread:.4f}")
    print(f"  Fuzzy discriminability ratio:   {f_spread/b_spread:.1f}x better")

    # Plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle("Path Ranking: Can the module differentiate candidate paths?",
                 fontsize=14, fontweight="bold", color="#1e293b")

    x = np.arange(len(paths))
    width = 0.35
    b_avgs = [results[n]["bayes_avg"] for n in path_names]
    f_avgs = [results[n]["fuzzy_avg"] for n in path_names]

    bars_b = ax1.bar(x - width/2, b_avgs, width, label="Bayesian P(LA)",
                     color="#8b5cf6", alpha=0.85, edgecolor="#6d28d9")
    bars_f = ax1.bar(x + width/2, f_avgs, width, label="Fuzzy LA",
                     color="#06b6d4", alpha=0.85, edgecolor="#0891b2")

    ax1.set_xticks(x)
    ax1.set_xticklabels(path_names, fontsize=9)
    ax1.set_ylabel("Average Availability Score")
    ax1.set_ylim(0, 1.1)
    ax1.axhline(0.5, color="#ef4444", linestyle="--", linewidth=1, alpha=0.5,
                label="Admission threshold")
    ax1.legend(fontsize=9)
    ax1.set_title("Average Score per Path", fontweight="bold")
    ax1.grid(True, axis="y", alpha=0.15)
    ax1.set_facecolor("#f8fafc")

    for bar in bars_b:
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                 f"{bar.get_height():.3f}", ha="center", fontsize=8, color="#6d28d9")
    for bar in bars_f:
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                 f"{bar.get_height():.3f}", ha="center", fontsize=8, color="#0891b2")

    link_labels = ["Link 1", "Link 2", "Link 3", "Link 4"]
    for i, (name, data) in enumerate(results.items()):
        ax2.plot(link_labels, data["bayes_scores"], "o--", color="#8b5cf6",
                 alpha=0.4 + 0.2*i, markersize=5)
        ax2.plot(link_labels, data["fuzzy_scores"], "s-", color="#06b6d4",
                 alpha=0.4 + 0.2*i, markersize=5, label=name.replace("\n", " ") if i == 0 else None)

    ax2.set_ylabel("Link Availability Score")
    ax2.set_ylim(0, 1.1)
    ax2.axhline(0.5, color="#ef4444", linestyle="--", linewidth=1, alpha=0.5)
    ax2.set_title("Per-Link Scores (all 3 paths)", fontweight="bold")
    ax2.annotate("Bayesian scores\nclustered together\n→ can't rank paths",
                 xy=(2.5, 0.92), fontsize=9, color="#6b21a8",
                 bbox=dict(boxstyle="round,pad=0.3", facecolor="#f3e8ff", alpha=0.8))
    ax2.grid(True, alpha=0.15)
    ax2.set_facecolor("#f8fafc")

    fig.tight_layout(rect=[0, 0, 1, 0.93])
    path_out = os.path.join(OUT, "03_path_ranking.png")
    fig.savefig(path_out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  → saved {path_out}")

    return {"bayes_spread": b_spread, "fuzzy_spread": f_spread,
            "ratio": f_spread / b_spread if b_spread > 0 else float("inf")}


def analysis_4_admission_quality():
    """
    Generate 2000 random (PU, RB) link conditions.
    For each admitted link, record its RB. Compare:
    - Median RB of Bayesian-admitted links
    - Median RB of Fuzzy-admitted links
    Bayesian admits lower-headroom links that fuzzy would reject.
    """
    print("\n[4] Admission Quality Score — Headroom of admitted links")

    np.random.seed(42)
    n_samples = 5000

    pu_samples = np.random.uniform(10, 90, n_samples)
    rb_samples = np.random.uniform(1, 800, n_samples)

    b_admitted_rb = []
    f_admitted_rb = []
    b_admitted_pu = []
    f_admitted_pu = []
    both_admit_rb = []
    bayes_only_rb = []

    for pu, rb in zip(pu_samples, rb_samples):
        pla, bdec, fla, fdec = evaluate_both(pu, rb)
        if bdec == "ADMIT":
            b_admitted_rb.append(rb)
            b_admitted_pu.append(pu)
            if fdec == "BLOCK":
                bayes_only_rb.append(rb)
        if fdec == "ADMIT":
            f_admitted_rb.append(rb)
            f_admitted_pu.append(pu)
        if bdec == "ADMIT" and fdec == "ADMIT":
            both_admit_rb.append(rb)

    b_admitted_rb = np.array(b_admitted_rb)
    f_admitted_rb = np.array(f_admitted_rb)

    print(f"  Bayesian admits: {len(b_admitted_rb)}/{n_samples} "
          f"({100*len(b_admitted_rb)/n_samples:.1f}%)")
    print(f"  Fuzzy admits:    {len(f_admitted_rb)}/{n_samples} "
          f"({100*len(f_admitted_rb)/n_samples:.1f}%)")

    b_median = np.median(b_admitted_rb) if len(b_admitted_rb) else 0
    f_median = np.median(f_admitted_rb) if len(f_admitted_rb) else 0
    b_p25 = np.percentile(b_admitted_rb, 25) if len(b_admitted_rb) else 0
    f_p25 = np.percentile(f_admitted_rb, 25) if len(f_admitted_rb) else 0

    print(f"  Bayesian median RB of admitted: {b_median:.1f} Mbps (P25={b_p25:.1f})")
    print(f"  Fuzzy median RB of admitted:    {f_median:.1f} Mbps (P25={f_p25:.1f})")
    print(f"  Bayes-only admits (fuzzy rejects): {len(bayes_only_rb)}")
    if bayes_only_rb:
        print(f"    Their median RB: {np.median(bayes_only_rb):.1f} Mbps "
              f"(these are the risky admits)")

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle("Admission Quality: What headroom do admitted links have?",
                 fontsize=14, fontweight="bold", color="#1e293b")

    bins = np.linspace(0, 800, 40)
    axes[0].hist(b_admitted_rb, bins=bins, alpha=0.6, color="#8b5cf6",
                 label=f"Bayesian (n={len(b_admitted_rb)}, med={b_median:.0f})",
                 edgecolor="#6d28d9")
    axes[0].hist(f_admitted_rb, bins=bins, alpha=0.6, color="#06b6d4",
                 label=f"Fuzzy (n={len(f_admitted_rb)}, med={f_median:.0f})",
                 edgecolor="#0891b2")
    axes[0].axvline(b_median, color="#8b5cf6", linestyle="--", linewidth=2)
    axes[0].axvline(f_median, color="#06b6d4", linestyle="--", linewidth=2)
    axes[0].set_xlabel("Residual Bandwidth (Mbps)")
    axes[0].set_ylabel("Count of Admitted Links")
    axes[0].set_title("RB Distribution of Admitted Links", fontweight="bold")
    axes[0].legend(fontsize=9)
    axes[0].grid(True, alpha=0.15)
    axes[0].set_facecolor("#f8fafc")

    axes[1].scatter(b_admitted_pu, b_admitted_rb, alpha=0.15, s=8,
                    color="#8b5cf6", label="Bayes admits")
    axes[1].scatter(f_admitted_pu, f_admitted_rb, alpha=0.15, s=8,
                    color="#06b6d4", label="Fuzzy admits")
    axes[1].set_xlabel("Port Utilization (%)")
    axes[1].set_ylabel("Residual Bandwidth (Mbps)")
    axes[1].set_title("Admitted Link Conditions", fontweight="bold")
    axes[1].legend(fontsize=9)
    axes[1].grid(True, alpha=0.15)
    axes[1].set_facecolor("#f8fafc")

    box_data = [b_admitted_rb, f_admitted_rb]
    bp = axes[2].boxplot(box_data, labels=["Bayesian", "Fuzzy"],
                         patch_artist=True, widths=0.5)
    bp["boxes"][0].set_facecolor("#8b5cf6")
    bp["boxes"][0].set_alpha(0.5)
    bp["boxes"][1].set_facecolor("#06b6d4")
    bp["boxes"][1].set_alpha(0.5)
    bp["medians"][0].set_color("#4c1d95")
    bp["medians"][1].set_color("#164e63")
    axes[2].set_ylabel("Residual Bandwidth (Mbps)")
    axes[2].set_title("RB Headroom Comparison", fontweight="bold")
    axes[2].grid(True, alpha=0.15)
    axes[2].set_facecolor("#f8fafc")

    fig.tight_layout(rect=[0, 0, 1, 0.93])
    path = os.path.join(OUT, "04_admission_quality.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  → saved {path}")

    return {
        "bayes_admit_count": len(b_admitted_rb),
        "fuzzy_admit_count": len(f_admitted_rb),
        "bayes_median_rb": b_median,
        "fuzzy_median_rb": f_median,
        "bayes_p25_rb": b_p25,
        "fuzzy_p25_rb": f_p25,
        "bayes_only_count": len(bayes_only_rb),
        "bayes_only_median_rb": np.median(bayes_only_rb) if bayes_only_rb else 0,
    }


def analysis_5_pu_sensitivity():
    """
    Sweep PU at several fixed RB levels. Shows that:
    - Bayesian curves all collapse to the same line (RB has no effect)
    - Fuzzy curves fan out based on RB magnitude
    """
    print("\n[5] PU Sensitivity at Fixed RB Levels")

    pu_range = np.linspace(5, 95, 200)
    rb_levels = [50, 150, 300, 500]
    colors = ["#ef4444", "#f97316", "#22c55e", "#3b82f6"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
    fig.suptitle("PU vs Availability at Different RB Levels",
                 fontsize=14, fontweight="bold", color="#1e293b")

    for i, rb in enumerate(rb_levels):
        b_vals = []
        f_vals = []
        for pu in pu_range:
            pla, _, fla, _ = evaluate_both(pu, rb)
            b_vals.append(pla)
            f_vals.append(fla)

        ax1.plot(pu_range, b_vals, color=colors[i], linewidth=2,
                 label=f"RB={rb} Mbps")
        ax2.plot(pu_range, f_vals, color=colors[i], linewidth=2,
                 label=f"RB={rb} Mbps")

    for ax, title in [(ax1, "Bayesian P(LA)"), (ax2, "Fuzzy LA")]:
        ax.set_xlabel("Port Utilization (%)")
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_ylim(-0.05, 1.05)
        ax.axhline(0.5, color="#94a3b8", linestyle="--", linewidth=0.8, alpha=0.5)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.15)
        ax.set_facecolor("#f8fafc")

    ax1.set_ylabel("Availability Score")
    ax1.annotate("All 4 RB curves overlap\n→ Bayesian can't distinguish\nRB=50 from RB=500",
                 xy=(15, 0.15), fontsize=9, color="#dc2626",
                 bbox=dict(boxstyle="round,pad=0.3", facecolor="#fef2f2", alpha=0.8))
    ax2.annotate("Curves fan out\n→ Fuzzy correctly gives\nhigher LA when RB is larger",
                 xy=(10, 0.15), fontsize=9, color="#166534",
                 bbox=dict(boxstyle="round,pad=0.3", facecolor="#f0fdf4", alpha=0.8))

    fig.tight_layout(rect=[0, 0, 1, 0.93])
    path = os.path.join(OUT, "05_pu_sensitivity.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  → saved {path}")


def print_summary(flatness, disagree, ranking, quality):
    """Print a clean summary table for the paper."""
    print("\n" + "=" * 75)
    print("  SUMMARY — Honest Bayesian vs Fuzzy Comparison")
    print("=" * 75)

    print("\n  Table 1: Posterior Flatness (RB Insensitivity)")
    print(f"  {'PU Level':<15} {'Bayesian Δ':<18} {'Fuzzy Δ':<18}")
    print(f"  {'─'*51}")
    for pu, data in flatness.items():
        b = data["bayes_range"]
        f = data["fuzzy_range"]
        print(f"  PU={pu}%{'':<8} {b:<18.6f} {f:<18.6f}")
    print(f"\n  → Bayesian P(LA) changes by < 0.001 across entire RB range")
    print(f"    because RB enters the CPT as a boolean (positive/negative),")
    print(f"    discarding magnitude. Fuzzy uses continuous RB membership.")

    print(f"\n  Table 2: Decision Agreement")
    print(f"  Agreement rate:              {disagree['agreement_pct']:.1f}%")
    print(f"  Bayes ADMIT, Fuzzy BLOCK:    {disagree['bayes_admits_fuzzy_blocks']} cases")
    print(f"  Disagreement PU range:       {disagree['disagree_pu_range'][0]:.0f}%–{disagree['disagree_pu_range'][1]:.0f}%")

    print(f"\n  Table 3: Path Ranking Discriminability")
    print(f"  Bayesian spread (Best-Worst): {ranking['bayes_spread']:.4f}")
    print(f"  Fuzzy spread (Best-Worst):    {ranking['fuzzy_spread']:.4f}")
    print(f"  Fuzzy is {ranking['ratio']:.1f}x more discriminating")

    print(f"\n  Table 4: Admission Quality (n=5000 random links)")
    print(f"  {'Metric':<35} {'Bayesian':<15} {'Fuzzy':<15}")
    print(f"  {'─'*65}")
    print(f"  {'Admission count':<35} {quality['bayes_admit_count']:<15} {quality['fuzzy_admit_count']:<15}")
    print(f"  {'Median RB of admitted (Mbps)':<35} {quality['bayes_median_rb']:<15.1f} {quality['fuzzy_median_rb']:<15.1f}")
    print(f"  {'P25 RB of admitted (Mbps)':<35} {quality['bayes_p25_rb']:<15.1f} {quality['fuzzy_p25_rb']:<15.1f}")
    print(f"  {'Bayes-only admits (fuzzy rejects)':<35} {quality['bayes_only_count']:<15}")
    print(f"  {'Their median RB (Mbps)':<35} {quality['bayes_only_median_rb']:<15.1f}")

    # Write to file
    report_path = os.path.join(OUT, "comparison_summary.txt")
    import io
    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()
    print("Honest Bayesian vs Fuzzy Comparison — Summary Statistics")
    print("=" * 60)
    print(f"\n1. Posterior Flatness")
    print(f"   Bayesian RB sensitivity: ZERO (RB is binary in CPT)")
    print(f"   Fuzzy RB sensitivity: continuous via membership functions")
    for pu, data in flatness.items():
        print(f"   PU={pu}%: Bayes Δ={data['bayes_range']:.6f}, Fuzzy Δ={data['fuzzy_range']:.4f}")
    print(f"\n2. Decision Agreement: {disagree['agreement_pct']:.1f}%")
    print(f"   Bayes admits that Fuzzy blocks: {disagree['bayes_admits_fuzzy_blocks']} cases")
    print(f"   Disagreement in PU range: {disagree['disagree_pu_range'][0]:.0f}%-{disagree['disagree_pu_range'][1]:.0f}%")
    print(f"\n3. Path Ranking Discriminability")
    print(f"   Fuzzy spread: {ranking['fuzzy_spread']:.4f} vs Bayesian: {ranking['bayes_spread']:.4f}")
    print(f"   Fuzzy is {ranking['ratio']:.1f}x more discriminating for path selection")
    print(f"\n4. Admission Quality (n=5000)")
    print(f"   Bayesian median RB: {quality['bayes_median_rb']:.1f} Mbps")
    print(f"   Fuzzy median RB:    {quality['fuzzy_median_rb']:.1f} Mbps")
    print(f"   Bayes-only admits:  {quality['bayes_only_count']} (median RB={quality['bayes_only_median_rb']:.1f})")
    sys.stdout = old_stdout
    with open(report_path, "w") as f:
        f.write(buffer.getvalue())
    print(f"\n  → Summary saved to {report_path}")
    print("=" * 75)


if __name__ == "__main__":
    print("Honest Bayesian vs Fuzzy Comparison")
    print("=" * 50)

    flatness = analysis_1_posterior_flatness()
    disagree = analysis_2_disagreement_zone()
    ranking  = analysis_3_path_ranking()
    quality  = analysis_4_admission_quality()
    analysis_5_pu_sensitivity()

    print_summary(flatness, disagree, ranking, quality)

    print(f"\n  All charts saved to: {OUT}/")
    print("  Done.")
