"""Generate the two paper figures directly from the audited output artifacts.
No hand-typed numbers: every value is read from outputs/score-main-v1r.json
and outputs/retrieval-recall-main-v1r.json, the same files zeus's reviewer-2
audit checked. Palette validated via the dataviz skill's validator (blue
#2a78d6 / red #e34948, all checks pass, ALL adjacent-pair CVD delta-E >= 74.6).
Print-target: single-hue, thin marks, direct labels, grayscale-legible.
"""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

BLUE = "#2a78d6"
RED = "#e34948"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
GOOD = "#0ca30c"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Segoe UI", "Arial", "DejaVu Sans"],
    "font.size": 8.5,
    "axes.edgecolor": MUTED,
    "axes.linewidth": 0.6,
    "text.color": INK,
    "axes.labelcolor": INK2,
    "xtick.color": MUTED,
    "ytick.color": INK,
    "svg.fonttype": "none",
})

LANG_NAME = {"gu": "Gujarati", "kn": "Kannada", "ml": "Malayalam",
             "mr": "Marathi", "te": "Telugu", "hi": "Hindi", "bn": "Bengali",
             "ta": "Tamil"}

# ---------- Figure 1: GRR forest plot (decision-table row 1) ----------
sc = json.load(open(r"D:\Research\xlkg\outputs\score-main-v1r.json", encoding="utf-8"))
grr = sc["grr"]
langs = ["gu", "mr", "te", "kn", "ml"]  # sorted by GRR descending for readability
order = sorted(langs, key=lambda l: grr[f"qwen3-8b/relation/{l}"]["grr"])
verdict = {"gu": "repaired", "mr": "repaired", "te": "repaired",
           "kn": "partial", "ml": "beyond taxonomy"}

fig, ax = plt.subplots(figsize=(4.6, 2.5), dpi=300)
ys = list(range(len(order)))
for y, lang in zip(ys, order):
    cell = grr[f"qwen3-8b/relation/{lang}"]
    g = cell["grr"]
    lo, hi = cell["ci95"]
    ax.plot([lo, hi], [y, y], color=BLUE, lw=1.4, solid_capstyle="round", zorder=2)
    ax.plot(g, y, "o", color=BLUE, ms=5.5, zorder=3,
            markeredgecolor="white", markeredgewidth=0.6)
    ax.text(hi + 0.09, y, f"{verdict[lang]}", va="center", ha="left",
            fontsize=7.3, color=INK2, style="italic")

# reference zones from the frozen decision table
ax.axvspan(-0.5, 0.35, color=GRID, alpha=0.5, zorder=0)
ax.axvline(0.75, color=MUTED, lw=0.7, ls=(0, (2, 2)), zorder=1)
ax.axvline(1.0, color=GOOD, lw=0.8, ls=(0, (1, 1.5)), zorder=1)
top = len(order) - 0.15
ax.text(1.0, top + 0.5, "English ceiling", fontsize=6.5,
        color=GOOD, ha="center", va="bottom")
ax.annotate("REPAIRED\nthreshold", xy=(0.75, top), xytext=(-0.15, top + 0.9),
            fontsize=6.3, color=MUTED, ha="center", va="bottom",
            arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.5,
                            connectionstyle="arc3,rad=-0.15"))

ax.set_yticks(ys)
ax.set_yticklabels([LANG_NAME[l] for l in order])
ax.set_xlabel("Gap Recovery Ratio (unclipped), 95% CI")
ax.set_xlim(-0.55, 2.75)
ax.set_ylim(-0.6, top + 1.55)
ax.spines[["top", "right", "left"]].set_visible(False)
ax.tick_params(left=False)
ax.grid(axis="x", color=GRID, lw=0.5, zorder=0)
ax.set_axisbelow(True)
fig.tight_layout(pad=0.3)
fig.savefig(r"D:\Research\xlkg\paper\fig_grr.pdf", bbox_inches="tight")
print("wrote fig_grr.pdf")
plt.close(fig)

# ---------- Figure 2: retrieval recall@8, direct vs pivot (Qwen3-8B) ----------
rr = json.load(open(r"D:\Research\xlkg\outputs\retrieval-recall-main-v1r.json", encoding="utf-8"))
langs8 = ["hi", "bn", "te", "ta", "kn", "ml", "mr", "gu"]
d_vals = [rr[f"qwen3-8b/direct/{l}"]["subject_recall_at8"] for l in langs8]
p_vals = [rr[f"qwen3-8b/pivot/{l}"]["subject_recall_at8"] for l in langs8]
order2 = sorted(range(len(langs8)), key=lambda i: d_vals[i])
langs8 = [langs8[i] for i in order2]
d_vals = [d_vals[i] for i in order2]
p_vals = [p_vals[i] for i in order2]

fig, ax = plt.subplots(figsize=(4.6, 2.7), dpi=300)
ys = list(range(len(langs8)))
for y, d, p in zip(ys, d_vals, p_vals):
    ax.plot([p, d], [y, y], color=MUTED, lw=1.1, zorder=1)
# alpha so near-tied pairs (Kannada: .215 vs .217) show as a visible blend
# rather than one marker fully occluding the other
ax.plot(p_vals, ys, "o", color=RED, ms=6, zorder=3, label="pivot (via English)",
        markeredgecolor="white", markeredgewidth=0.6, alpha=0.82)
ax.plot(d_vals, ys, "o", color=BLUE, ms=6, zorder=3, label="direct (native + top-up)",
        markeredgecolor="white", markeredgewidth=0.6, alpha=0.82)

en_recall = rr["qwen3-8b/english/en"]["subject_recall_at8"]
ax.axvline(en_recall, color=GOOD, lw=0.8, ls=(0, (1, 1.5)), zorder=0)
ax.text(en_recall, len(langs8) - 0.15, "English\ncontrol", fontsize=6.3,
        color=GOOD, ha="center", va="bottom")
ax.set_ylim(-0.7, len(langs8) + 0.55)

ax.set_yticks(ys)
ax.set_yticklabels([LANG_NAME[l] for l in langs8])
ax.set_xlabel("Subject-candidate recall@8")
ax.set_xlim(0.05, 0.72)
ax.spines[["top", "right", "left"]].set_visible(False)
ax.tick_params(left=False)
ax.grid(axis="x", color=GRID, lw=0.5, zorder=0)
ax.set_axisbelow(True)
ax.legend(loc="lower right", frameon=False, fontsize=7.3, handletextpad=0.3,
          borderaxespad=0.2)
fig.tight_layout(pad=0.3)
fig.savefig(r"D:\Research\xlkg\paper\fig_retrieval.pdf", bbox_inches="tight")
print("wrote fig_retrieval.pdf")
plt.close(fig)

# ---------- print the exact source values for the caption/verification ----------
print("\n=== Fig 1 source values ===")
for lang in order:
    c = grr[f"qwen3-8b/relation/{lang}"]
    print(lang, "grr=", c["grr"], "ci=", c["ci95"], "verdict=", verdict[lang])
print("\n=== Fig 2 source values ===")
for l, d, p in zip(langs8, d_vals, p_vals):
    print(l, "direct=", d, "pivot=", p)
print("english control recall@8 =", en_recall)
