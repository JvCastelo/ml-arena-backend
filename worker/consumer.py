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

from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.exc import OperationalError

from app.core.aws import aws_session
from app.core.config import settings
from app.core.cache import invalidate_user_cache
from app.db.models import Artifact, Run
from app.db.session import session_scope
from app.repositories import artifact_repository, run_repository
from app.services import audit_service, storage
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


async def _audit_worker(user_id: int, action: str, run_id: int, details: dict) -> None:
    """Registra uma ação de auditoria do worker, com detalhes do run."""
    try:
        await audit_service.log_user_action(
            user_id=user_id,
            action=action,
            resource_id=run_id,
            details=details,
        )
    except Exception as e:
        logger.exception(
            "Run %s: falha ao gravar auditoria (%s): %s", run_id, action, e
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

        duration = time.monotonic() - started
        await run_repository.update_run(
            session,
            run,
            {"status": "done", "processing_duration_s": duration},
        )
    await _audit_worker(
        user_id=run.user_id,
        action="PROCESS_RUN_DONE",
        run_id=run_id,
        details={"processing_duration_s": duration, "plots": list(PLOT_FILES.keys())},
    )
    await invalidate_user_cache(user_id=run.user_id)
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
    await _audit_worker(
        user_id=run.user_id,
        action="PROCESS_RUN_FAILED",
        run_id=run_id,
        details={"error_message": message},
    )
    await invalidate_user_cache(user_id=run.user_id)


async def handle_message(message: dict, sqs_client) -> None:
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

    await sqs_client.delete_message(
        QueueUrl=settings.sqs_queue_url, ReceiptHandle=message["ReceiptHandle"]
    )


async def run_forever() -> None:
    """Loop principal: pede mensagem à fila, trata e repete. Se a fila falhar, espera 5s e tenta de novo."""
    logger.info("Worker escutando a fila %s", settings.sqs_queue_url)

    sqs_config = Config(
        read_timeout=30, connect_timeout=10, retries={"max_attempts": 3}
    )

    while True:
        try:
            async with aws_session.client("sqs", config=sqs_config) as sqs:
                while True:
                    response = await sqs.receive_message(
                        QueueUrl=settings.sqs_queue_url,
                        MaxNumberOfMessages=1,
                        WaitTimeSeconds=20,
                        AttributeNames=["ApproximateReceiveCount"],
                    )
                    for message in response.get("Messages", []):
                        await handle_message(message, sqs)
        except (BotoCoreError, ClientError):
            logger.exception("Falha ao consultar a fila; tentando de novo em 5s.")
            await asyncio.sleep(5)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    asyncio.run(run_forever())
