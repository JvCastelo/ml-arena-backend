"""Worker: consome a fila SQS e gera os plots de cada CSV enviado.

Roda como processo separado (`python -m worker.consumer`), fora da API. Para cada mensagem:
baixa o CSV do S3, gera os dois PNGs (`worker/processing.py`), sobe os PNGs, e atualiza
run e artifacts no banco. Erro de dado marca como failed na hora; erro de infraestrutura
volta pra fila até a 3ª tentativa. Os logs ETAPA 1/2/3 mostram onde cada run está.
"""

import asyncio
import json
import logging
import time
from functools import cache

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.db.models import Artifact, Run
from app.db.session import session_scope
from app.repositories import artifact_repository, run_repository
from app.services import storage
from worker.processing import make_plots, read_pairs

logger = logging.getLogger("worker")

CSV_TYPE = "csv_measured_predicted"
# Caminho de cada plot no bucket, por tipo de artifact (convenção do spec, seção 6).
PLOT_FILES = {
    "plot_measured_predicted": "plots/measured_predicted.png",
    "plot_residuals": "plots/residuals.png",
}
# Mesmo número do maxReceiveCount da fila. Na última tentativa o worker decide o fim,
# então a mensagem nunca precisa cair na DLQ por falha transitória.
MAX_ATTEMPTS = 3
# Erro de dado: o CSV não serve. Não adianta tentar de novo.
PERMANENT_ERRORS = (ValueError, KeyError)
# Erro de infraestrutura: S3, SQS ou banco fora do ar. Vale tentar de novo.
TRANSIENT_ERRORS = (BotoCoreError, ClientError, OperationalError)


@cache
def _sqs_client():
    # Sem timeout, uma resposta perdida na rede deixava o worker preso no recebimento.
    # O long poll dura até 20s, então o read_timeout fica acima disso.
    """Cliente boto3 do SQS, criado uma vez, com timeouts de rede (ver comentário)."""
    return boto3.client(
        "sqs",
        region_name=settings.aws_region,
        config=Config(read_timeout=30, connect_timeout=10, retries={"max_attempts": 3}),
    )


def _receive():
    """Consulta a fila com long polling de 20s. Devolve até uma mensagem (ou nenhuma)."""
    return _sqs_client().receive_message(
        QueueUrl=settings.sqs_queue_url,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=20,  # long polling: espera até 20s por mensagem, sem ficar consultando
        AttributeNames=["ApproximateReceiveCount"],
    )


def _delete(receipt_handle: str) -> None:
    """Apaga a mensagem da fila. Só é chamado quando a mensagem foi tratada de vez (sucesso ou falha final)."""
    _sqs_client().delete_message(
        QueueUrl=settings.sqs_queue_url, ReceiptHandle=receipt_handle
    )


async def _ensure_plot_artifact(
    session, run_id: int, plot_type: str, key: str
) -> Artifact:
    """Garante o artifact de um plot, marcando como processing. Cria se não existe, ou reaproveita a linha de tentativa anterior."""
    artifact = await artifact_repository.get_artifact_by_type(
        session, run_id, plot_type
    )
    if artifact is None:
        return await artifact_repository.create_artifact(
            session, run_id, plot_type, key, status="processing"
        )
    return await artifact_repository.update_artifact(
        session, artifact, status="processing", error_message=None
    )


async def process_run(run_id: int) -> None:
    """O trabalho de verdade: CSV do S3 → plots → S3 → banco."""
    async with session_scope() as session:
        run = await session.get(Run, run_id)
        if run is None:
            logger.info("Run %s não existe mais; descartando a mensagem.", run_id)
            return
        if run.status == "done":
            return  # mensagem repetida (o SQS entrega pelo menos uma vez): já foi feito

        csv_artifact = await artifact_repository.get_artifact_by_type(
            session, run_id, CSV_TYPE
        )
        if csv_artifact is None or csv_artifact.status != "done":
            raise ValueError("CSV ainda não está disponível para este run.")

        started = time.monotonic()
        await run_repository.update_run(
            session, run, {"status": "processing", "error_message": None}
        )

        plot_artifacts = {}
        for plot_type, filename in PLOT_FILES.items():
            key = f"runs/{run_id}/{filename}"
            plot_artifacts[plot_type] = await _ensure_plot_artifact(
                session, run_id, plot_type, key
            )

        logger.info("ETAPA 2 iniciada: run %s, baixando o CSV.", run_id)
        data = await storage.download_object(csv_artifact.s3_key)
        measured, predicted = read_pairs(data)
        images = await asyncio.to_thread(make_plots, measured, predicted)

        for plot_type, filename in PLOT_FILES.items():
            image = images[plot_type]
            await storage.upload_bytes(f"runs/{run_id}/{filename}", image, "image/png")
            await artifact_repository.update_artifact(
                session, plot_artifacts[plot_type], status="done", size_bytes=len(image)
            )

        await run_repository.update_run(
            session,
            run,
            {"status": "done", "processing_duration_s": time.monotonic() - started},
        )
    logger.info("ETAPA 3 concluída: run %s processado.", run_id)


async def _mark_failed(run_id: int, message: str) -> None:
    """Marca o run e os artifacts pendentes como failed, com o motivo. Usado quando não há mais o que tentar."""
    async with session_scope() as session:
        run = await session.get(Run, run_id)
        if run is None:
            return
        for artifact in await artifact_repository.list_artifacts_for_run(
            session, run_id
        ):
            if artifact.status in ("pending", "processing"):
                await artifact_repository.update_artifact(
                    session, artifact, status="failed", error_message=message
                )
        await run_repository.update_run(
            session, run, {"status": "failed", "error_message": message}
        )


async def handle_message(message: dict) -> None:
    """Trata uma mensagem: decide se apaga da fila (feito ou falha final) ou se deixa voltar (erro transitório)."""
    body = json.loads(message["Body"])
    run_id = body["run_id"]
    attempts = int(message["Attributes"]["ApproximateReceiveCount"])
    logger.info("ETAPA 1 recebida: run %s (tentativa %s).", run_id, attempts)

    try:
        await process_run(run_id)
    except PERMANENT_ERRORS as exc:
        # O detalhe técnico vai pro log; o usuário vê só a mensagem geral.
        logger.warning("Run %s: CSV não pôde ser processado: %r", run_id, exc)
        await _mark_failed(run_id, "Processamento falhou: o CSV não pôde ser lido.")
    except TRANSIENT_ERRORS:
        if attempts < MAX_ATTEMPTS:
            logger.exception(
                "Run %s: erro transitório na tentativa %s; tentando de novo.",
                run_id,
                attempts,
            )
            return  # não apaga: a mensagem volta pra fila depois do visibility timeout
        logger.exception("Run %s: esgotou as %s tentativas.", run_id, MAX_ATTEMPTS)
        await _mark_failed(run_id, "Falha no processamento. Tente reenviar o CSV.")

    await asyncio.to_thread(_delete, message["ReceiptHandle"])


async def run_forever() -> None:
    """Loop principal: pede mensagem à fila, trata e repete. Se a fila falhar, espera 5s e tenta de novo."""
    logger.info("Worker escutando a fila %s", settings.sqs_queue_url)
    while True:
        try:
            response = await asyncio.to_thread(_receive)
        except BotoCoreError, ClientError:
            logger.exception("Falha ao consultar a fila; tentando de novo em 5s.")
            await asyncio.sleep(5)
            continue
        for message in response.get("Messages", []):
            await handle_message(message)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    asyncio.run(run_forever())
