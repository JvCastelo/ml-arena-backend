# ML Arena — backend

Uma versão simplificada do MLflow: registra **runs** de modelos de ML (hiperparâmetros e métricas),
recebe um CSV de medido×previsto, gera gráficos de forma assíncrona e permite comparar dois runs
lado a lado. Trabalho Prático 1 de Desenvolvimento de Software para Nuvem (UFC).

Stack: FastAPI, SQLAlchemy 2.0 (async) + asyncpg, PostgreSQL, Alembic, Pydantic, uv e ruff.
Na AWS: RDS, S3, ElastiCache, DynamoDB, SNS/SQS e Auto Scaling (ver `docs/`).

## Pré-requisitos

- Python 3.14 e [uv](https://docs.astral.sh/uv/)
- Docker (para o Postgres local)

## Rodando localmente

```bash
cp .env.example .env            # ajuste os valores se quiser; o .env não vai para o git
docker compose up -d            # sobe o Postgres
uv sync                         # instala as dependências
uv run alembic upgrade head     # cria as tabelas
uv run fastapi dev app/main.py  # API em http://127.0.0.1:8000
```

A documentação interativa (gerada automaticamente) fica em **http://127.0.0.1:8000/docs**.

### Usuário de desenvolvimento

Ainda não existe cadastro, e as rotas de runs exigem um usuário. Crie um direto no banco e use o
`id` devolvido no header `X-User-Id` (autenticação provisória, veja `docs/api-contract.md`):

```bash
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
INSERT INTO users (name, email, password_hash) VALUES ('Dev', 'dev@example.com', 'x') RETURNING id;
SQL
```

### Exemplo

```bash
curl -X POST http://127.0.0.1:8000/api/v1/runs \
  -H "X-User-Id: 1" -H "Content-Type: application/json" \
  -d '{"name": "xgb-v1", "algorithm": "XGBoost", "hyperparams": {"max_depth": 6}, "metrics": {"test": {"rmse": 1.1}}}'
```

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/health` | Health check (usado pelo ALB) |
| `POST` | `/api/v1/runs` | Cria um run |
| `GET` | `/api/v1/runs` | Lista os runs do usuário (paginação e filtros) |
| `GET` | `/api/v1/runs/{id}` | Detalhe de um run, com seus artifacts |
| `PATCH` | `/api/v1/runs/{id}` | Edita um run parcialmente |
| `DELETE` | `/api/v1/runs/{id}` | Apaga um run |

Formatos completos, erros e o que ainda falta: `docs/api-contract.md`.

## Desenvolvimento

```bash
uv run pytest                           # testes
uv run ruff check . && uv run ruff format .
uv run alembic revision --autogenerate -m "descrição"   # nova migration (revise o arquivo!)
uv run alembic upgrade head             # aplica migrations
uv run alembic check                    # confere se os models batem com o banco
docker compose down -v                  # apaga o banco local (recomeça do zero)
```

`notebooks/db_smoke_test.py` valida o banco célula por célula (inserts, constraints, cascade); só
roda no VS Code/Jupyter, com o banco de pé e as migrations aplicadas.

## Estrutura

```
app/
├── main.py         # FastAPI, lifespan e /health
├── api/            # deps.py (dependências) e v1/ (router + routes/)
├── schemas/        # Pydantic: formato do JSON de entrada e saída
├── core/           # configuração (config.py)
└── db/             # models/, session.py (async) e migrations/ (Alembic)
docs/               # db-diagram.md (modelo de dados), api-contract.md (contrato da API)
CLAUDE.md           # contexto do projeto para sessões do Claude Code
```

## Documentação

- [`docs/db-diagram.md`](docs/db-diagram.md): modelo de dados, restrições e como alterar o schema.
- [`docs/api-contract.md`](docs/api-contract.md): contrato da API e decisões em aberto.
- [`CLAUDE.md`](CLAUDE.md): estado do projeto, decisões, armadilhas e próximos passos.

## Decisão sobre o arquivo binário obrigatório

O enunciado exige ao menos um arquivo binário no fluxo principal. O CSV de entrada é texto, então o
requisito é cumprido pelos **dois plots PNG** gerados pelo worker e guardados no S3
(`measured_predicted.png` e `residuals.png`). *(Decisão ainda em discussão; ver `docs/api-contract.md`.)*
