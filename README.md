# ML Arena — backend

Uma versão simplificada do MLflow: registra **runs** de modelos de ML (hiperparâmetros e métricas),
recebe um CSV de medido×previsto, gera gráficos de forma assíncrona e permite comparar dois runs
lado a lado. Trabalho Prático 1 de Desenvolvimento de Software para Nuvem (UFC).

Stack: FastAPI, SQLAlchemy 2.0 (async) + asyncpg, PostgreSQL, Alembic, Pydantic, uv e ruff.
Na AWS: RDS, S3, ElastiCache, DynamoDB, SNS/SQS e Auto Scaling.

## Pré-requisitos

- Python 3.14 e [uv](https://docs.astral.sh/uv/)
- Docker (para o Postgres local)

## Rodando localmente

```bash
cp .env.example .env            # ajuste os valores se quiser; o .env não vai para o git
docker compose up -d --build    # Postgres, Redis, migrations, API (:8000) e worker
```

O serviço `migrate` roda `alembic upgrade head` sozinho a cada `up`, depois que o Postgres aceita
conexões; a API e o worker só sobem se ele terminar com sucesso. Se a API não subir, veja
`docker compose logs migrate`.

A documentação interativa (gerada automaticamente) fica em **http://127.0.0.1:8000/docs**.

### Exemplo

As rotas de runs exigem login (JWT no header `Authorization: Bearer ...`). Cadastre um usuário,
faça login (o corpo é form-data, não JSON) e use o token devolvido:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/users/ -H "Content-Type: application/json" \
  -d '{"name": "Dev", "email": "dev@example.com", "password": "teste123"}'

TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -d "username=dev@example.com&password=teste123" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

curl -X POST http://127.0.0.1:8000/api/v1/runs \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "xgb-v1", "algorithm": "XGBoost", "hyperparams": {"max_depth": 6}, "metrics": {"test": {"rmse": 1.1}}}'
```

## Endpoints

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/health` | Health check (usado pelo ALB) |
| `POST` | `/api/v1/users/` | Cadastra um usuário |
| `GET` | `/api/v1/users/me` | Dados do usuário logado |
| `POST` | `/api/v1/auth/login` | Login (form-data); devolve o token JWT |
| `POST` | `/api/v1/runs` | Cria um run |
| `GET` | `/api/v1/runs` | Lista os runs do usuário (paginação e filtros) |
| `GET` | `/api/v1/runs/compare?run_a=&run_b=` | Compara dois runs lado a lado (com cache no Redis) |
| `GET` | `/api/v1/runs/{id}` | Detalhe de um run, com seus artifacts |
| `PATCH` | `/api/v1/runs/{id}` | Edita um run parcialmente |
| `DELETE` | `/api/v1/runs/{id}` | Apaga um run |
| `POST` | `/api/v1/runs/{id}/measured-predicted` | Sobe o CSV medido×previsto; o worker gera os plots |

Formatos completos de entrada e saída: **http://127.0.0.1:8000/docs**.

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
├── services/       # regras de negócio, S3, SNS e auditoria (DynamoDB)
├── repositories/   # acesso ao banco
├── core/           # configuração, segurança (JWT), cache (Redis) e cliente AWS
└── db/             # models/, session.py (async) e migrations/ (Alembic)
worker/             # consome a fila SQS e gera os plots de cada CSV
tests/              # pytest
```

## Decisão sobre o arquivo binário obrigatório

O enunciado exige ao menos um arquivo binário no fluxo principal. O CSV de entrada é texto, então o
requisito é cumprido pelos **dois plots PNG** gerados pelo worker e guardados no S3
(`measured_predicted.png` e `residuals.png`).
