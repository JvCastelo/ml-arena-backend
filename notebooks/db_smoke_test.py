# %% [markdown]
# # Smoke test do banco (models + sessão async)
#
# Roda célula por célula (Shift+Enter no VS Code). Cada célula abre sua
# própria `async with session_scope()`, simulando uma requisição isolada da
# API — é assim que o FastAPI vai usar isso, uma sessão por request, nunca
# uma sessão compartilhada entre chamadas.
#
# Só roda pelo VS Code/Jupyter: o `await` no topo das células não é válido
# num `python notebooks/db_smoke_test.py` comum.
#
# Pré-requisitos: `docker compose up -d` rodando, `.env` preenchido e
# `uv run alembic upgrade head` já aplicado.

# %%
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.db.models import Artifact, Run, User
from app.db.session import session_scope

# %% [markdown]
# ## 1. Criar um user (equivalente a um POST de cadastro)

# %%
async with session_scope() as session:
    user = User(
        name="Arthur",
        email="smoke-test@example.com",
        password_hash="fake-hash-not-real-bcrypt",
    )
    session.add(user)
    await session.flush()  # atribui o user.id sem esperar o fim do "with"
    user_id = user.id

print("user criado, id =", user_id)

# %% [markdown]
# ## 2. Criar um run para esse user (POST /runs)

# %%
async with session_scope() as session:
    run = Run(
        user_id=user_id,
        name="xgb-depth6-v1",
        algorithm="XGBoost",
        hyperparams={"max_depth": 6, "n_estimators": 200},
        metrics={"train": {"rmse": 0.91}, "test": {"rmse": 1.12}},
    )
    session.add(run)
    await session.flush()
    run_id = run.id

print("run criado, id =", run_id, "status default deveria ser 'created'")

# %% [markdown]
# ## 3. Upload simulado: csv + os dois plots (o worker faria os plots depois)

# %%
async with session_scope() as session:
    session.add_all(
        [
            Artifact(
                run_id=run_id,
                type="csv_actual_predicted",
                s3_key=f"runs/{run_id}/actual_predicted.csv",
                status="done",
                size_bytes=2048,
            ),
            Artifact(
                run_id=run_id,
                type="plot_measured_predicted",
                s3_key=f"runs/{run_id}/plots/measured_predicted.png",
            ),
            Artifact(
                run_id=run_id,
                type="plot_residuals",
                s3_key=f"runs/{run_id}/plots/residuals.png",
            ),
        ]
    )

print("3 artifacts criados")

# %% [markdown]
# ## 4. Ler de volta (GET /runs/{id}) — confere o JSONB e a lista de artifacts

# %%
async with session_scope() as session:
    run = await session.get(Run, run_id, options=[selectinload(Run.artifacts)])
    print("algorithm  :", run.algorithm)
    print("hyperparams:", run.hyperparams, type(run.hyperparams))
    print("metrics    :", run.metrics)
    print("status     :", run.status)
    print("artifacts  :", [(a.type, a.status) for a in run.artifacts])

# %% [markdown]
# ## 5. Editar o run (PATCH /runs/{id}) — muda o status pra "processing"

# %%
async with session_scope() as session:
    run = await session.get(Run, run_id)
    run.status = "processing"

async with session_scope() as session:
    run = await session.get(Run, run_id)
    print("status depois do PATCH:", run.status)
    print("updated_at:", run.updated_at)

# %% [markdown]
# ## 6. Status inválido deve ser recusado pelo CHECK (ck_runs_status_valid)

# %%
try:
    async with session_scope() as session:
        run = await session.get(Run, run_id)
        run.status = "lixo_que_nao_existe"
except IntegrityError as e:
    print("recusado como esperado:", type(e.orig).__name__)

# confirma que o valor não mudou de verdade (o rollback funcionou)
async with session_scope() as session:
    print("status continua:", (await session.get(Run, run_id)).status)

# %% [markdown]
# ## 7. Duplicar o type de um artifact no mesmo run deve falhar (UNIQUE)

# %%
try:
    async with session_scope() as session:
        session.add(
            Artifact(
                run_id=run_id,
                type="plot_residuals",  # já existe pra esse run_id
                s3_key=f"runs/{run_id}/plots/residuals-dup.png",
            )
        )
except IntegrityError as e:
    print("recusado como esperado:", type(e.orig).__name__)

# %% [markdown]
# ## 8. Apagar o user com run ainda existindo deve falhar (sem cascade em User.runs)

# %%
try:
    async with session_scope() as session:
        await session.delete(await session.get(User, user_id))
except IntegrityError as e:
    print("recusado como esperado:", type(e.orig).__name__)

# %% [markdown]
# ## 9. Apagar o run — os 3 artifacts devem sumir sozinhos (cascade de verdade)

# %%
async with session_scope() as session:
    before = (
        await session.scalars(select(Artifact).where(Artifact.run_id == run_id))
    ).all()
    print("artifacts antes do delete:", len(before))

    await session.delete(await session.get(Run, run_id))

async with session_scope() as session:
    after = (
        await session.scalars(select(Artifact).where(Artifact.run_id == run_id))
    ).all()
    print("artifacts depois do delete:", len(after), "(esperado: 0)")

# %% [markdown]
# ## 10. Agora sim, apagar o user (sem runs, deve funcionar)

# %%
async with session_scope() as session:
    await session.delete(await session.get(User, user_id))

async with session_scope() as session:
    print("user ainda existe?", (await session.get(User, user_id)) is not None)

print("smoke test concluído")

# %%
