"""Geração dos gráficos a partir do CSV. Função pura: sem AWS e sem banco.

Usado por `worker/consumer.py`. Matplotlib com backend `Agg` (sem tela, direto pra memória).
"""

import csv
import io

import matplotlib

matplotlib.use("Agg")  # sem tela no container: renderiza direto pra memória
import matplotlib.pyplot as plt


def read_pairs(data: bytes) -> tuple[list[float], list[float]]:
    """Lê as colunas measured e predicted. Levanta ValueError/KeyError se o CSV não servir."""
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    measured, predicted = [], []
    for row in reader:
        measured.append(float(row["measured"]))
        predicted.append(float(row["predicted"]))
    return measured, predicted


def _to_png(fig) -> bytes:
    """Converte uma figura do matplotlib em bytes PNG (em memória, sem arquivo temporário)."""
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    return buffer.getvalue()


def make_plots(measured: list[float], predicted: list[float]) -> dict[str, bytes]:
    """Gera os dois PNGs. As chaves são os tipos de artifact do banco."""
    residuals = [m - p for m, p in zip(measured, predicted, strict=False)]

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(measured, predicted, s=12, alpha=0.7)
    low = min(min(measured), min(predicted))
    high = max(max(measured), max(predicted))
    ax.plot(
        [low, high],
        [low, high],
        color="red",
        linestyle="--",
        linewidth=1,
        label="y = x",
    )
    ax.set_xlabel("Medido")
    ax.set_ylabel("Previsto")
    ax.set_title("Medido x previsto")
    ax.legend()
    measured_predicted = _to_png(fig)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.scatter(predicted, residuals, s=12, alpha=0.7)
    ax.axhline(0, color="red", linestyle="--", linewidth=1)
    ax.set_xlabel("Previsto")
    ax.set_ylabel("Resíduo (medido - previsto)")
    ax.set_title("Resíduos")
    residual_plot = _to_png(fig)

    return {
        "plot_measured_predicted": measured_predicted,
        "plot_residuals": residual_plot,
    }
