# Contrato da API

> Documento vivo, mantido por Arthur e jv. As rotas marcadas **[fechado]** estão implementadas e
> testadas; o formato delas só muda com combinado entre os dois. As marcadas **[em aberto]** têm
> proposta, mas ainda precisam de decisão. Ao fechar uma decisão, edite este arquivo antes de
> codar a rota: ele é a especificação. Os formatos vivem em código como schemas Pydantic
> (`app/schemas/`), e a documentação interativa gerada fica em `/docs` com a API rodando.

## Convenções

- Prefixo `/api/v1` em tudo, **exceto** `GET /health` (na raiz, sem auth, sem tocar no banco).
- JSON em UTF-8. Datas em ISO 8601 com fuso (`2026-09-26T14:53:50.951881Z`). Ids inteiros.
- **Erros** seguem o padrão do FastAPI, `{"detail": ...}`:

| Código | Quando |
|---|---|
| `401` | Sem usuário identificado (header ausente ou usuário inexistente) |
| `404` | Run inexistente **ou de outro usuário** (não revelamos que o id existe) |
| `422` | Corpo, parâmetro de query ou de rota inválido (`detail` lista os campos) |
| `500` | Erro inesperado, inclusive escrita recusada pelo banco |

## O que já está decidido

- Stack: FastAPI, Pydantic v2, SQLAlchemy async. Modelo de dados fechado (`docs/db-diagram.md`).
- **Runs são privados por usuário**: todo acesso filtra por dono e nunca se aceita `user_id` do
  corpo da requisição.
- **Autenticação por JWT** (a API precisa ser stateless para o Auto Scaling da Parte 2).
- `status` do run (`created | processing | done | failed`) **não é editável pelo cliente**.

### Autenticação provisória (remover antes do deploy)

Enquanto a auth real não existe, o usuário logado é o do header **`X-User-Id: <id>`**
(`get_current_user` em `app/api/deps.py`). É insegura por definição: qualquer cliente se passa
por qualquer usuário. **Não pode ir para a AWS.** A auth real troca só o corpo dessa função; as
rotas dependem apenas de `CurrentUserDep`.

---

## Runs **[fechado]**

Todas exigem o usuário logado. Um `Run` nunca expõe o `user_id`.

### `POST /api/v1/runs` → 201

Cria um run com `status = "created"`.

```json
{
  "name": "xgb-depth6-v1",
  "algorithm": "XGBoost",
  "hyperparams": {"max_depth": 6, "n_estimators": 200},
  "metrics": {"train": {"rmse": 0.91}, "test": {"rmse": 1.12}}
}
```

- `name` e `algorithm`: obrigatórios, 1–120 caracteres.
- `hyperparams` e `metrics`: objetos JSON (padrão `{}`). O formato interno é livre; por
  convenção `metrics` é `{"train": {...}, "test": {...}}`.

Resposta (`RunRead`):

```json
{
  "id": 5,
  "name": "xgb-depth6-v1",
  "algorithm": "XGBoost",
  "hyperparams": {"max_depth": 6, "n_estimators": 200},
  "metrics": {"train": {"rmse": 0.91}, "test": {"rmse": 1.12}},
  "status": "created",
  "error_message": null,
  "processing_duration_s": null,
  "created_at": "2026-09-26T14:54:12.676010Z",
  "updated_at": "2026-09-26T14:54:12.676010Z"
}
```

### `GET /api/v1/runs` → 200

Lista **só os runs do usuário**, do mais novo ao mais antigo (`created_at`, desempate por `id`).

| Query | Padrão | Regra |
|---|---|---|
| `limit` | 20 | 1 a 100 |
| `offset` | 0 | ≥ 0 |
| `algorithm` | — | igualdade exata |
| `status` | — | `created`, `processing`, `done` ou `failed` (outro valor → 422) |

```json
{"items": [ /* RunRead */ ], "total": 3, "limit": 20, "offset": 0}
```

`total` é o número de runs que batem com os filtros, independente da página.

### `GET /api/v1/runs/{id}` → 200

`RunRead` mais a lista `artifacts` (`RunDetail`):

```json
{
  "id": 5, "name": "...", "status": "processing", "...": "...",
  "artifacts": [
    {"id": 1, "type": "csv_actual_predicted", "status": "done",
     "size_bytes": 2048, "error_message": null, "created_at": "2026-09-26T14:55:00Z"}
  ]
}
```

A chave do S3 (`s3_key`) **não** é exposta; as URLs dos plots virão como URLs pré-assinadas quando
o S3 existir (decisão em aberto abaixo). `type`: `csv_actual_predicted`, `plot_measured_predicted`
ou `plot_residuals`. `status` do artifact: `pending | processing | done | failed`.

### `PATCH /api/v1/runs/{id}` → 200

Edição **parcial**: só os campos enviados mudam. Aceita `name`, `algorithm`, `hyperparams` e
`metrics` (mesmas regras do POST). Um campo enviado como `null` → 422; campos desconhecidos
(como `status`) são ignorados. Devolve o `RunRead` atualizado, com o `updated_at` novo.

### `DELETE /api/v1/runs/{id}` → 204

Sem corpo. O banco apaga os artifacts (`ON DELETE CASCADE`).
**TODO:** apagar também os objetos do S3 e gravar a ação no log de auditoria.

---

## Em aberto

### Autenticação — jv

- `POST /auth/register` e `POST /auth/login`: campos do request, o que devolvem (token direto no
  cadastro, ou é preciso logar?), regras de senha.
- Formato do JWT (algoritmo, claims) e expiração. Como as rotas recebem o token
  (`Authorization: Bearer ...`).
- Erros de auth: `401` com `{"detail": ...}`, igual às demais rotas.
- Antes de tudo, o hash de senha (o `passlib` + `bcrypt 5` está quebrado; ver `CLAUDE.md`).
- Critério de aceitação: o usuário 1 não enxerga nem altera o run do usuário 2.

### `POST /runs/{id}/actual-predicted` — upload do CSV

Proposta, a confirmar: `multipart/form-data` com o arquivo. A rota sobe o CSV ao S3 (síncrono),
cria o artifact `csv_actual_predicted` como `done`, muda o run para `processing`, **publica no SNS**
e responde **`202 Accepted`** sem esperar o processamento (o worker desacoplado gera os plots e
atualiza os status). Decidir: tamanho máximo, o que acontece se já existir CSV (o `UNIQUE
(run_id, type)` já impede um segundo), e se a resposta devolve o run ou só o artifact.

### `GET /runs/compare?a={id}&b={id}`

Payload já pronto para a tela: os dois runs (metadados, hiperparâmetros, métricas) e as URLs
pré-assinadas dos plots. É o candidato a cache no ElastiCache (chave com os ids em ordem
canônica, TTL curto). **Declare esta rota antes de `GET /runs/{run_id}`**, senão o FastAPI tenta
converter `"compare"` para inteiro e responde 422. Ambos os runs precisam ser do usuário (404 se
algum não for).

### Log de auditoria (DynamoDB)

Toda ação de CRUD grava tipo da ação, dados manipulados e hora (`user_id` como partition key,
`timestamp` como sort key). Ainda não há chamada nas rotas de runs; entra num serviço
(`app/services/audit.py`) chamado por cada rota que escreve.

### Arquivo binário obrigatório

O CSV é texto. Proposta: os dois plots PNG gerados pelo worker (`plot_measured_predicted`,
`plot_residuals`) cumprem o requisito. Confirmar com o professor/monitor, ou aceitar também o
upload opcional de uma imagem.

### Health check

`GET /health` responde `{"status": "ok"}` sem tocar no banco (é para o ALB saber que o processo
está de pé). Se algum dia for preciso um teste de prontidão (`/health/ready`, com `SELECT 1`),
deve ser outra rota, para o ALB não derrubar instâncias por oscilação do RDS.

---

## Como testar rotas

Os testes usam `httpx.AsyncClient` com `ASGITransport` e `pytest.mark.anyio`. Duas armadilhas
que já custaram tempo:

- **Fixture async com `autouse=True` quebra os testes síncronos** (como o do `/health`). Ponha a
  limpeza dentro do fixture `client`.
- **Cada teste roda num event loop novo**, e conexões do pool criadas num loop não servem no
  seguinte: termine o fixture `client` com `await engine.dispose()`.

Cada teste deve criar os próprios usuários (com e-mail único) e apagar o que criou (runs primeiro,
depois usuários: `User → Run` não tem cascade). Hoje os testes rodam contra o banco de
desenvolvimento; um banco só de testes é melhoria futura.
