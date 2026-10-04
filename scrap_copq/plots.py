"""Gráficas estáticas (matplotlib) para el notebook y el README."""
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np

INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, BASE, SURFACE = "#e1e0d9", "#c3c2b7", "#fcfcfb"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]   # paleta categórica validada (CVD)
ACCENT, DIM, CRITICAL = SERIES[0], "#d6d5ce", "#d03b3b"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "sans-serif", "font.size": 10, "text.color": INK,
    "axes.edgecolor": BASE, "axes.labelcolor": INK_2, "axes.titlesize": 12,
    "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.titlepad": 12,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "axes.grid": True, "axes.grid.axis": "y", "axes.axisbelow": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK_2, "ytick.labelcolor": INK_2,
    "ytick.left": False, "legend.frameon": False, "figure.dpi": 110, "savefig.dpi": 160,
    "savefig.bbox": "tight",
})
MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _thousands(ax, axis="y"):
    fmt = mtick.FuncFormatter(lambda v, _: f"{v / 1e3:,.0f}")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def copq_mensual(monthly):
    fig, ax = plt.subplots(figsize=(9, 4))
    x = np.arange(len(monthly))
    bottom = np.zeros(len(monthly))
    parts = [("costo_scrap_mxn", "Scrap"), ("costo_retrabajo_mxn", "Retrabajo"),
             ("costo_reclamos_mxn", "Reclamos de cliente")]
    for (col, label), color in zip(parts, SERIES):
        ax.bar(x, monthly[col], 0.55, bottom=bottom, color=color, label=label,
               edgecolor=SURFACE, linewidth=1.5)
        bottom += monthly[col].to_numpy()
    ax.set_xticks(x, [MONTHS[d.month - 1] for d in monthly.index])
    _thousands(ax)
    ax.set_ylabel("Miles de MXN")
    ax.set_title("Costo de no calidad por mes, 2025")
    ax.legend(loc="upper left", ncols=3, bbox_to_anchor=(0, 1.02))
    ax.set_ylim(0, bottom.max() * 1.18)
    return fig


def pareto_doble(by_pieces, by_cost, highlight="Falta de fusión"):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharex=True)
    for ax, df, title in zip(axes, (by_pieces, by_cost),
                             ("Por piezas desechadas", "Por costo (scrap + reclamos)")):
        df = df.iloc[::-1]
        colors = [ACCENT if d == highlight else DIM for d in df["defecto"]]
        ax.barh(df["defecto"], df["pct"], 0.6, color=colors)
        for y, (d, v) in enumerate(zip(df["defecto"], df["pct"])):
            ax.text(v + 0.6, y, f"{v:.0f} %", va="center", fontsize=9,
                    color=INK if d == highlight else INK_2,
                    fontweight="bold" if d == highlight else "normal")
        ax.set_title(title, fontsize=11)
        ax.grid(False)
        ax.tick_params(axis="x", bottom=False, labelbottom=False)
        ax.tick_params(axis="y", length=0)
        ax.spines["bottom"].set_visible(False)
    p, c = (df.loc[df["defecto"] == highlight, "pct"].iat[0] for df in (by_pieces, by_cost))
    fig.suptitle(f"{highlight}: {p:.0f} % de las piezas, {c:.0f} % del costo",
                 x=0.01, ha="left", fontsize=13, fontweight="bold")
    fig.tight_layout()
    return fig


def carta_control(classic, laney, line, events=()):
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True, sharey=True)
    for ax, df, title in zip(axes, (classic, laney), ("Carta p clásica", "Carta p′ de Laney")):
        ax.plot(df.index, df["p"], color=ACCENT, lw=1.2)
        ax.step(df.index, df["lsc"], where="mid", color=MUTED, lw=0.9)
        ax.step(df.index, df["lic"], where="mid", color=MUTED, lw=0.9)
        ax.axhline(df["lc"].iat[0], color=INK_2, lw=0.9)
        out = df[df["regla_1"]]
        ax.scatter(out.index, out["p"], s=22, color=CRITICAL, zorder=3, edgecolor=SURFACE, linewidth=1)
        share = len(out) / len(df)
        ax.set_title(f"{title}: {len(out)} días fuera de límites ({share:.0%})", fontsize=11)
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(1, decimals=0))
        ax.text(df.index[-1], df["lsc"].iat[-1], "  LSC", va="center", color=MUTED, fontsize=8)
        ax.text(df.index[-1], df["lc"].iat[-1], "  LC", va="center", color=INK_2, fontsize=8)
        ax.text(df.index[-1], df["lic"].iat[-1], "  LIC", va="center", color=MUTED, fontsize=8)
        for date, label in events:
            ax.annotate(label, (date, df.loc[date, "p"]), xytext=(-70, 8), textcoords="offset points",
                        fontsize=8, color=INK_2, arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.8})
    axes[1].xaxis.set_major_locator(mdates.MonthLocator())
    axes[1].xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: MONTHS[mdates.num2date(v).month - 1]))
    fig.suptitle(f"Tasa diaria de scrap · {line}", x=0.01, ha="left", fontsize=13, fontweight="bold")
    fig.tight_layout()
    return fig


def scrap_vs_mantenimiento(binned, threshold, focus="L2"):
    fig, ax = plt.subplots(figsize=(9, 4))
    for line, df in binned.groupby("linea"):
        color, lw, z = (ACCENT, 2, 3) if line == focus else (DIM, 1.5, 2)
        ax.plot(df["horas"], df["tasa"], color=color, lw=lw, marker="o", ms=4, zorder=z)
        ax.text(df["horas"].iat[-1] + 4, df["tasa"].iat[-1], line, va="center",
                color=INK if line == focus else INK_2, fontsize=9)
    ax.axvline(threshold, color=MUTED, lw=0.9)
    ax.text(threshold + 3, ax.get_ylim()[1] * 0.97, f"Umbral estimado: {threshold} h",
            va="top", fontsize=9, color=INK_2)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1, decimals=1))
    ax.set_xlabel("Horas de operación desde el último mantenimiento preventivo")
    ax.set_title(f"El scrap de {focus} sube después de ~{threshold} h sin mantenimiento")
    return fig


def odds_ratios(table):
    df = table.sort_values("odds_ratio")
    fig, ax = plt.subplots(figsize=(8, 4.6))
    y = np.arange(len(df))
    ax.hlines(y, df["ic95_inf"], df["ic95_sup"], color=ACCENT, lw=2)
    ax.scatter(df["odds_ratio"], y, s=36, color=ACCENT, zorder=3, edgecolor=SURFACE, linewidth=1.5)
    ax.axvline(1, color=MUTED, lw=0.9)
    ax.set_yticks(y, df.index)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Razón de momios del scrap (IC 95 %) · 1 = sin efecto")
    ax.set_title("¿Qué eleva la probabilidad de scrap?")
    return fig


def curva_mantenimiento(curve, current):
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.plot(curve.index, curve["ahorro_neto"], color=ACCENT, lw=2)
    best = curve["ahorro_neto"].idxmax()
    for x, label, offset, ha in ((best, f"Óptimo ≈ {best} h", (0, 10), "center"),
                                 (current, f"Actual: {current} h", (-10, -4), "right")):
        y = curve.loc[x, "ahorro_neto"]
        ax.scatter([x], [y], s=40, color=ACCENT if x == best else INK_2, zorder=3,
                   edgecolor=SURFACE, linewidth=1.5)
        ax.annotate(label, (x, y), xytext=offset, textcoords="offset points", ha=ha, va="top" if x != best else "bottom",
                    fontsize=9, color=INK if x == best else INK_2)
    ax.set_ylim(top=curve["ahorro_neto"].max() * 1.2)
    ax.axhline(0, color=BASE, lw=0.9)
    _thousands(ax)
    ax.set_ylabel("Miles de MXN al año")
    ax.set_xlabel("Intervalo de mantenimiento preventivo en L2 (horas de operación)")
    ax.set_title("Ahorro neto según el intervalo de mantenimiento de L2")
    return fig


def ahorro_por_palanca(savings, labels):
    df = savings.sort_values("ahorro_neto_p50")
    fig, ax = plt.subplots(figsize=(9, 2.8))
    y = np.arange(len(df))
    ax.barh(y, df["ahorro_neto_p50"], 0.32, color=ACCENT)
    ax.hlines(y, df["ahorro_neto_p10"], df["ahorro_neto_p90"], color=INK, lw=1.2)
    span = df["ahorro_neto_p90"].max()
    for yi, v, hi in zip(y, df["ahorro_neto_p50"], df["ahorro_neto_p90"]):
        ax.text(max(hi, 0) + span * 0.02, yi, f"{v / 1e3:,.0f} mil MXN", va="center", fontsize=9, color=INK_2)
    ax.set_xlim(min(0, df["ahorro_neto_p10"].min() * 1.15), span * 1.3)
    ax.set_yticks(y, [labels[i] for i in df.index])
    ax.tick_params(axis="y", length=0)
    ax.axvline(0, color=BASE, lw=0.9)
    _thousands(ax, "x")
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Ahorro neto anual, miles de MXN (mediana e intervalo P10–P90)")
    ax.set_title("Ahorro neto estimado por palanca")
    return fig
