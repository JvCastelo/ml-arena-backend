"""Testa as decisões do worker sobre cada mensagem (apagar, devolver à fila, marcar failed).

Sem banco nem AWS: `process_run` e `_mark_failed` são trocados por funções falsas, e o cliente
SQS só anota as mensagens apagadas.
"""

import asyncio
import json

import pytest

from worker import consumer


class FakeSQS:
    def __init__(self):
        self.deleted = []

    async def delete_message(self, QueueUrl, ReceiptHandle):  # noqa: N803 (nome do boto3)
        self.deleted.append(ReceiptHandle)


def _message(body, attempts=1):
    return {
        "Body": body,
        "ReceiptHandle": "rh-1",
        "Attributes": {"ApproximateReceiveCount": str(attempts)},
    }


@pytest.fixture
def calls(monkeypatch):
    """Registra quem foi marcado como failed; process_run levanta o erro configurado."""
    state = {"failed": [], "error": None}

    async def fake_process_run(run_id):
        if state["error"]:
            raise state["error"]

    async def fake_mark_failed(run_id, message):
        state["failed"].append(run_id)

    monkeypatch.setattr(consumer, "process_run", fake_process_run)
    monkeypatch.setattr(consumer, "_mark_failed", fake_mark_failed)
    return state


@pytest.mark.parametrize(
    "body",
    [
        "não é json",
        json.dumps({"Type": "Notification", "Message": "{}"}),  # envelope do SNS
        json.dumps({"run_id": "abc"}),
    ],
)
def test_mensagem_invalida_e_descartada_sem_derrubar(calls, body):
    sqs = FakeSQS()
    asyncio.run(consumer.handle_message(_message(body), sqs))
    assert sqs.deleted == ["rh-1"]
    assert calls["failed"] == []


def test_sucesso_apaga_a_mensagem(calls):
    sqs = FakeSQS()
    asyncio.run(consumer.handle_message(_message(json.dumps({"run_id": 1})), sqs))
    assert sqs.deleted == ["rh-1"]


def test_erro_de_dado_marca_failed_na_hora(calls):
    calls["error"] = ValueError("CSV ruim")
    sqs = FakeSQS()
    asyncio.run(consumer.handle_message(_message(json.dumps({"run_id": 1})), sqs))
    assert calls["failed"] == [1]
    assert sqs.deleted == ["rh-1"]


def test_erro_inesperado_volta_para_a_fila(calls):
    calls["error"] = ConnectionError("Redis fora do ar")
    sqs = FakeSQS()
    asyncio.run(consumer.handle_message(_message(json.dumps({"run_id": 1})), sqs))
    assert sqs.deleted == []
    assert calls["failed"] == []


def test_erro_inesperado_na_ultima_tentativa_marca_failed(calls):
    calls["error"] = ConnectionError("Redis fora do ar")
    sqs = FakeSQS()
    message = _message(json.dumps({"run_id": 1}), attempts=consumer.MAX_ATTEMPTS)
    asyncio.run(consumer.handle_message(message, sqs))
    assert calls["failed"] == [1]
    assert sqs.deleted == ["rh-1"]
