# Contexto do projeto — ML Arena

Este arquivo é lido automaticamente por qualquer sessão do Claude Code aberta neste repositório.
Se você é o Claude do jv: isto foi escrito pelo Arthur (e pelo Claude da sessão dele) pra te passar
o estado atual do projeto antes de continuar o trabalho. Leia inteiro antes de sugerir código.

## O trabalho

Trabalho Prático 1 de Desenvolvimento de Software para Nuvem (UFC). Uma versão simplificada do
MLflow ("ML Arena"): registra runs de modelos de ML, guarda métricas/hiperparâmetros, processa um
CSV de medido×previsto de forma assíncrona (worker separado) gerando plots, e permite comparar
dois runs lado a lado. Precisa usar RDS, S3, ElastiCache, DynamoDB, SNS/SQS e Auto Scaling — são
obrigatórios, cada ausência é penalidade fixa na nota.

**Importante:** `docs/spec.md` (o documento completo da especificação + decisões de produto do
Arthur) está no `.gitignore` e por isso **não está neste clone** se você é o jv. Se precisar do
contexto completo, peça o arquivo ao Arthur diretamente. Os documentos abaixo, em `docs/`, **são**
compartilhados e é neles que as decisões técnicas ficam registradas à medida que são fechadas.

## O que já está pronto (branch `create_database_arthur`, PR aberta pra `develop`)

- **Modelo de dados fechado e testado**: `users`, `runs`, `artifacts` em PostgreSQL, via
  SQLAlchemy 2.0 (`app/models/`). Detalhes, restrições e o porquê de cada decisão estão em
  `docs/db-diagram.md` — leia antes de propor mudança no schema.
- **Conexão com o banco**: `app/config.py` (variáveis de ambiente, ver `.env.example`) e
  `app/db.py` (engine + `get_session()`, um context manager que faz commit/rollback automático).
- **Ambiente local**: Postgres via `docker-compose.yaml` (`docker compose up -d`), tabelas criadas
  com `uv run python -m scripts.create_tables`.
- **Validação do banco**: `notebooks/db_smoke_test.py` (células `#%%`, roda no VS Code) — testa
  insert/update, o round-trip do JSONB, as CHECK constraints de `status`/`type`, o
  `UNIQUE(run_id, type)` e o cascade (`Run → Artifact` cascateia ao apagar; `User → Run` é
  restringido, ou seja, não dá pra apagar um usuário com runs existentes).
- **Ferramental**: `uv` para dependências, `ruff` para lint/format (`uv run ruff check .` /
  `uv run ruff format .`), `ipykernel` como dev dependency pro notebook.
- Autenticação **decidida mas não implementada ainda**: login por e-mail + senha, JWT (API
  precisa ser stateless pra Parte 2 funcionar com ALB + Auto Scaling), runs privados por usuário
  (todo acesso a um run filtra por dono).

## O que precisa ser atacado agora

**Contrato da API**, antes de escrever qualquer rota Flask. Está todo planejado em
**`docs/api-contract.md`**: a lista de endpoints (vinda do `spec.md`), o que já foi decidido sobre
auth e o modelo de dados, e — o mais importante — a lista, rota por rota, do que ainda falta
decidir (formato de request/response, autenticação, paginação, etc.), numa ordem sugerida pra
discutir.

Abra `docs/api-contract.md` e comece por ali. A ordem sugerida é autenticação primeiro (toda rota
de `runs` depende de saber quem está logado), depois `POST /runs`, e seguindo o fluxo natural de
uso do app. Ao fechar o formato de uma rota, edite o próprio arquivo com a decisão final — é ele
que vai virar a especificação de cada rota em `app/routes/`.

## Fluxo de git

`atv01_arthur` / `atv01_jv` (ou branches por feature) → PR → `develop` → (quando estável) → PR →
`main`. Nunca commitar direto em `main`. PRs entre vocês dois, sem merge automático — quem revisa
decide quando mergear.
