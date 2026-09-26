# Contexto do projeto — ML Arena

Este arquivo é lido automaticamente por qualquer sessão do Claude Code aberta neste repositório.
Foi escrito pelo Arthur (e pelo Claude da sessão dele) para passar o estado do projeto a quem
continuar o trabalho. **Se você é o Claude do jv, leia inteiro antes de sugerir código: a seção
"Pendências" diz o que é dele agora (a autenticação) e o passo a passo para começar.**

## O trabalho

Trabalho Prático 1 de Desenvolvimento de Software para Nuvem (UFC), **prazo: 10/10/2026, 23h59**.
Uma versão simplificada do MLflow ("ML Arena"): registra runs de modelos de ML (hiperparâmetros e
métricas), recebe um CSV de medido×previsto, processa de forma assíncrona (worker separado)
gerando dois plots, e permite comparar dois runs lado a lado.

Serviços AWS obrigatórios (cada ausência é penalidade fixa na nota): **RDS, S3, ElastiCache,
DynamoDB, SNS/SQS e Auto Scaling** (ALB + ASG, 1 a 3 instâncias), mais interface gráfica (−1,0 se
faltar). A API precisa ser **stateless**: o ALB pode mandar cada requisição a uma instância
diferente, então nada de estado em memória ou disco local.

`docs/spec.md` (especificação completa e decisões de produto do Arthur) está no `.gitignore` e
**não existe neste clone** se você é o jv. Peça ao Arthur se precisar. O que foi decidido fica
registrado nos arquivos de `docs/` (versionados), que valem mais que qualquer rascunho.

## Stack (decisões fechadas — não reabrir sem motivo)

- **FastAPI** (a ideia inicial era Flask; a equipe trocou), Pydantic v2 para os formatos de
  entrada/saída, `fastapi[standard]` (traz uvicorn, httpx, jinja2).
- **SQLAlchemy 2.0 assíncrono** + **asyncpg**, contra **PostgreSQL** (RDS na AWS; Docker no local).
- **Alembic** para migrations. **pydantic-settings** para configuração (variáveis de ambiente/`.env`).
- **uv** para dependências, **ruff** para lint e formatação, **pytest** para testes.

## Estrutura

```
app/
├── main.py              # instância do FastAPI, lifespan, GET /health
├── api/
│   ├── deps.py          # SessionDep e CurrentUserDep (dependências das rotas)
│   └── v1/
│       ├── router.py    # agrega os routers sob /api/v1
│       └── routes/      # uma rota por assunto (runs.py hoje; auth.py será do jv)
├── schemas/             # Pydantic: o formato do JSON que entra e sai (≠ models do banco)
├── core/                # config.py (Settings); security.py e logging.py ainda vazios
└── db/
    ├── models/          # SQLAlchemy: User, Run, Artifact (o schema do banco)
    ├── session.py       # engine async, get_session (FastAPI) e session_scope (fora do FastAPI)
    └── migrations/      # Alembic (versions/ tem a migration inicial)
notebooks/db_smoke_test.py   # validação do banco por células (`# %%`), só roda no VS Code/Jupyter
tests/                       # pytest (hoje só o /health)
docs/                        # db-diagram.md, api-contract.md (spec.md é local do Arthur)
```

## Como rodar

```bash
cp .env.example .env                    # e ajuste a senha, se quiser
docker compose up -d                    # Postgres local
uv sync
uv run alembic upgrade head             # cria as tabelas (não existe mais create_all)
uv run fastapi dev app/main.py          # http://127.0.0.1:8000/docs
uv run pytest
uv run ruff check . && uv run ruff format .
```

Não há cadastro ainda, e sem usuário nenhuma rota de `runs` funciona. Para criar um usuário de
desenvolvimento (o `id` devolvido vai no header `X-User-Id`):

```bash
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
INSERT INTO users (name, email, password_hash) VALUES ('Dev', 'dev@example.com', 'x') RETURNING id;
SQL
```

## O que já está pronto

- **Modelo de dados fechado, migrado e testado** (`app/db/models/`, `docs/db-diagram.md`).
  `alembic check` confirma que models e banco estão em sincronia.
- **Sessão async** (`app/db/session.py`), validada célula por célula em `notebooks/db_smoke_test.py`
  (inserts, JSONB, CHECK/UNIQUE, cascade). O `create_all` e a sessão síncrona foram removidos.
- **API**: `GET /health` e o **CRUD de runs** (`POST/GET /api/v1/runs`, `GET/PATCH/DELETE
  /api/v1/runs/{id}`). Formatos exatos em `docs/api-contract.md`. Foi validado com 10 testes
  contra um banco real (isolamento entre usuários, paginação, PATCH parcial, cascade).
- **Autenticação PROVISÓRIA**: `get_current_user` (em `app/api/deps.py`) lê o header `X-User-Id`.
  Existe só para o CRUD poder ser escrito e testado antes da auth real. **É insegura (qualquer
  cliente vira qualquer usuário) e não pode ir para a AWS.**

## Decisões tomadas (e o porquê)

- **Runs são privados por usuário.** Todo acesso filtra por dono **dentro da query**
  (`get_owned_run`), então não há checagem de permissão separada para esquecer. Run de outro
  usuário responde **404** (não 403), para não revelar que o id existe.
- **`User → Run` sem cascade** (o banco recusa apagar usuário com runs; evita deixar arquivos
  órfãos no S3). **`Run → Artifact` com cascade** (`ON DELETE CASCADE` + `passive_deletes`).
- **`status` do run** (`created|processing|done|failed`) **não é editável pelo cliente**: quem o
  define é o worker. O PATCH só aceita `name`, `algorithm`, `hyperparams`, `metrics`.
- **Artifact tem status e erro próprios** (um plot pode falhar sem o outro). `type` e `status` são
  restritos por `CHECK` no banco; adicionar um valor exige migration manual (veja armadilhas).
- **Paginação** de `GET /runs` com envelope `{items, total, limit, offset}`, limite 1–100.
- **`/health` fica fora de `/api/v1` e não toca no banco**: o ALB o chama o tempo todo, e se ele
  dependesse do RDS uma oscilação do banco faria o ASG derrubar instâncias saudáveis.
- **`naming_convention`** no `Base` (nomes previsíveis de constraints), para o Alembic conseguir
  alterá-las depois.

## Armadilhas já descobertas (leia antes de mexer)

1. **Toda rota que escreve deve chamar `await session.commit()` ela mesma.** O commit do
   `get_session` roda *depois* de a resposta ser enviada; se o banco recusar a escrita ali, o
   cliente já recebeu `200`. Testado: sem o commit explícito a API mentia; com ele devolve 500.
2. **Async não faz lazy load.** Ler `run.artifacts` sem ter pedido dá `MissingGreenlet`. Peça
   junto na query: `selectinload(Run.artifacts)`. O `expire_on_commit=False` do `session.py` pelo
   mesmo motivo (não dá para recarregar atributos vencidos).
3. **Depois de um UPDATE, faça `await session.refresh(obj)`** se for devolver o objeto: o
   `updated_at` é recalculado pelo banco. No INSERT não precisa (o Postgres devolve os defaults).
4. **O autogenerate do Alembic não detecta mudança em `CHECK` constraints.** Se mudar a lista de
   `type`/`status`, escreva a migration à mão.
5. **`fastapi dev app/main.py` exige `app/__init__.py`** (sem ele: `No module named 'app'`).
6. **`pytest` puro só enxerga `app/` por causa de `pythonpath = ["."]` no `pyproject.toml`.**
7. **Ordem das rotas:** ao criar `GET /runs/compare`, declare-a **antes** de `GET /runs/{run_id}`,
   senão o FastAPI tenta converter "compare" para `int` e responde 422.
8. **Testes async:** fixture async com `autouse` quebra testes síncronos; e cada teste roda num
   event loop novo, então é preciso `await engine.dispose()` ao final (ver a nota no contrato).
9. **`passlib` + `bcrypt 5.0` está quebrado** (ver Pendências).
10. O ruff acusa `await` no topo do notebook (`F704`/`PLE1142`): é falso alarme, já ignorado em
    `notebooks/*` no `pyproject.toml`. O notebook só roda pelo VS Code/Jupyter.

## Pendências e quem faz

### Autenticação — é do jv agora

Passo a passo sugerido (as decisões abertas estão em `docs/api-contract.md`):

1. **Consertar o hash de senha antes de tudo.** Reprodução: `CryptContext(schemes=["bcrypt"])
   .hash("teste123")` levanta `ValueError: password cannot be longer than 72 bytes`. Causa: o
   `passlib 1.7.4` (sem manutenção) testa o backend com um segredo >72 bytes e o `bcrypt 5`
   passou a recusar. Saídas: usar `bcrypt` direto, ou `pwdlib` (recomendado pela doc do FastAPI),
   ou fixar `bcrypt<5`. Remover o `passlib` das dependências se não for usado.
2. Acrescentar ao `Settings` (`app/core/config.py`) e ao `.env.example` o segredo do JWT
   (`JWT_SECRET_KEY`) e a expiração. O `pyjwt` já está instalado.
3. `app/core/security.py`: hash/verificação de senha e criação/validação do JWT.
4. `app/api/v1/routes/auth.py` com `POST /auth/register` e `POST /auth/login`, registrado em
   `app/api/v1/router.py`. Erros de auth seguem o padrão `{"detail": ...}` com 401.
5. **Trocar só o corpo de `get_current_user`** em `app/api/deps.py` para ler o token
   (`Authorization: Bearer ...`), **mantendo a assinatura e o `CurrentUserDep`**: as rotas de
   runs não mudam. Apagar o código do header `X-User-Id`.
6. Escrever testes (o usuário 1 não enxerga o run do usuário 2 é o mais importante).

Usuários que já existem no banco de desenvolvimento têm `password_hash` falso; recrie-os pelo
`register` depois.

### Próximos passos do projeto (por ordem de risco)

1. **Log de auditoria no DynamoDB** (`app/services/audit.py`): toda ação de CRUD grava tipo da
   ação, dados manipulados e hora. **Os endpoints de runs ainda não gravam nada** (há TODO no
   `delete_run`). Partition key `user_id`, sort key `timestamp`.
2. **Upload do CSV → S3 → SNS/SQS → worker** que gera os dois plots (`POST
   /runs/{id}/actual-predicted`). É o coração do trabalho e a parte mais arriscada.
3. **`GET /runs/compare`** e **cache no ElastiCache** (chave canonizada com os ids em ordem).
4. **Frontend** (obrigatório): Jinja2 via FastAPI + JS puro na tela de comparação + Bootstrap.
5. **Deploy**: EC2, RDS, ALB + Auto Scaling (CPU >70% sobe, <25% desce), teste de carga, vídeo.
   Um spike cedo na AWS Academy (criar RDS, S3, DynamoDB, SNS/SQS, ElastiCache) evita descobrir
   tarde algum bloqueio do Learner Lab. Lembrete: RDS/ElastiCache consomem o orçamento do Lab
   mesmo parados.

### Pequenas, sem dono

- `docker-compose.yaml` diverge do `.env.example` (defaults `admin/123456/meu_banco` × `postgres`),
  usa Postgres 15 (alinhar com a versão do RDS) e publica a porta em todas as interfaces (antes
  era só `127.0.0.1`).
- `Dockerfile` e `core/logging.py` vazios; `python-dotenv` é dependência redundante (o
  pydantic-settings já lê o `.env`).
- Testes de `runs` não estão no repositório (existe um conjunto de 9 casos validado; reescrever).
  Os testes hoje usariam o banco de desenvolvimento; um banco só de testes é melhoria futura.

## Fluxo de git

`atv01_arthur` / `atv01_jv` (ou uma branch por assunto) → PR → `develop` → (quando estável) → PR →
`main`. Nunca commitar direto em `main` nem em `develop`. **O Claude só faz commit e push quando o
usuário pede; o merge da PR é sempre feito pelos humanos** (Arthur e jv se revisam).

## Como trabalhar aqui

O projeto também é de aprendizado: explique o porquê das decisões e valide o que propõe rodando
(`ruff`, `pytest`, `alembic check`), sem afirmar o que não foi testado. Atualize este arquivo e o
`docs/api-contract.md` ao fechar uma decisão, para o próximo a abrir o projeto não partir do zero.
