"""Validação do CSV medido×previsto antes de aceitar o upload.

Função pura (sem AWS nem banco), então é fácil de testar. Chamada pelo `run_service.py`.
Quando o CSV é inválido, a mensagem diz o motivo e a linha, para mostrar ao usuário.
"""

import csv
import io
import math

MAX_CSV_BYTES = 5 * 1024 * 1024  # 5MB
REQUIRED_COLUMNS = ("measured", "predicted")


class CsvValidationError(ValueError):
    """O CSV não serve pra gerar os plots. A mensagem diz o motivo, pra mostrar ao usuário."""


def validate_measured_predicted_csv(data: bytes) -> None:
    """Confere se o CSV é texto UTF-8, tem as colunas measured e predicted, tem linhas e só valores numéricos finitos."""
    if not data.strip():
        raise CsvValidationError("O arquivo está vazio.")

    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CsvValidationError("O arquivo não é um CSV de texto (UTF-8).") from None

    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    missing = [column for column in REQUIRED_COLUMNS if column not in header]
    if missing:
        raise CsvValidationError(
            f"Faltam as colunas {', '.join(missing)}. O CSV precisa ter "
            f"{' e '.join(REQUIRED_COLUMNS)}."
        )

    rows = 0
    for line_number, row in enumerate(reader, start=2):
        rows += 1
        for column in REQUIRED_COLUMNS:
            raw = (row[column] or "").strip()
            try:
                value = float(raw)
            except ValueError:
                raise CsvValidationError(
                    f"Linha {line_number}: '{column}' precisa ser numérico, mas veio '{raw}'."
                ) from None
            if not math.isfinite(value):
                raise CsvValidationError(
                    f"Linha {line_number}: '{column}' precisa ser um número finito."
                ) from None

    if rows == 0:
        raise CsvValidationError("O CSV tem só o cabeçalho, sem linhas de dados.")
