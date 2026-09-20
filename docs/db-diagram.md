# Modelo de dados (RDS / PostgreSQL)

Rascunho para revisão. Decisões tomadas até aqui: usuários com login e-mail + senha (JWT), runs privados por usuário, status e erro tanto no run quanto por artifact.

```mermaid
erDiagram
    users ||--o{ runs : "possui"
    runs ||--o{ artifacts : "gera"

    users {
        int id PK
        varchar name
        varchar email UK "login"
        varchar password_hash "bcrypt/argon2, nunca texto puro"
        timestamptz created_at
    }

    runs {
        int id PK
        int user_id FK "NOT NULL, indexado"
        varchar name "label do run"
        varchar algorithm "texto livre"
        jsonb hyperparams "default {}"
        jsonb metrics "train/test, default {}"
        varchar status "created | processing | done | failed"
        text error_message "nullable"
        float processing_duration_s "nullable, preenchido pelo worker"
        timestamptz created_at
        timestamptz updated_at
    }

    artifacts {
        int id PK
        int run_id FK "ON DELETE CASCADE"
        varchar type "csv_actual_predicted | plot_measured_predicted | plot_residuals"
        varchar s3_key "runs/{run_id}/..."
        bigint size_bytes "nullable até o arquivo existir"
        varchar status "pending | processing | done | failed"
        text error_message "nullable"
        timestamptz created_at
    }
```

## Restrições e índices

- `users.email`: `UNIQUE NOT NULL`.
- `runs.status`, `artifacts.status`, `artifacts.type`: `CHECK` nos valores permitidos.
- `artifacts`: `UNIQUE (run_id, type)`.
- `runs`: índice em `(user_id, created_at)` (listagem "meus runs, mais novos primeiro").
- `runs.updated_at`: atualizado a cada edição (`onupdate` no SQLAlchemy).
