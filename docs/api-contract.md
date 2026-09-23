# Contrato da API — planejamento

> Documento de trabalho, para discutir e decidir junto (Arthur e jv), do mesmo jeito que fizemos
> com o modelo de dados em `docs/db-diagram.md`. Nada aqui é decisão fechada — é o ponto de
> partida pra conversa. Ao decidir algo, edite este arquivo com a decisão final antes de codar a
> rota (trava o formato de dado antes da implementação, é o motivo do documento existir).

## Onde isso vem do spec

`docs/spec.md`, seção 4, lista os endpoints mínimos exigidos, mas só como tabela de
método+rota+descrição, sem formato de request/response e sem autenticação (que foi decidida
depois, numa conversa que não está no spec.md ainda). Esse rascunho original:

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/runs` | Cria um run (algoritmo + hyperparams + métricas train/test) |
| `GET` | `/runs` | Lista runs — candidato a cache |
| `GET` | `/runs/{id}` | Detalhe de um run, com artifacts e URLs dos plots |
| `PUT`/`PATCH` | `/runs/{id}` | Edita metadados (o "U" do CRUD) |
| `DELETE` | `/runs/{id}` | Remove o run e os artifacts (S3 + RDS) |
| `POST` | `/runs/{id}/actual-predicted` | Upload do CSV → S3 + dispara SNS/SQS |
| `GET` | `/runs/compare?a={id}&b={id}` | Payload pronto pra tela de comparação |
| `GET` | `/health` | Health check, necessário pro ALB na Parte 2 |

## O que já foi decidido (não reabrir, ver `docs/db-diagram.md`)

- Usuários com login por e-mail + senha, autenticação via **JWT** (API stateless, obrigatório pra
  Parte 2 — o ALB roteia pra qualquer instância).
- **Runs são privados por usuário.** Todo acesso a um run filtra por dono.
- Modelo de dados fechado: `users`, `runs`, `artifacts` — ver `docs/db-diagram.md` pros campos
  exatos. Reparem que `runs.notes` **não existe** (foi cortado), o que muda o que o `PATCH`
  original previa editar.
- `runs.status`: `created | processing | done | failed`. `artifacts.status`:
  `pending | processing | done | failed`. `artifacts.type`:
  `csv_actual_predicted | plot_measured_predicted | plot_residuals`.

## O que falta decidir aqui

Sugestão de ordem, porque autenticação é pré-requisito de tudo o resto (toda rota de `runs`
precisa saber "logado como quem"):

1. **Autenticação**
   - `POST /auth/register`: quais campos, o que devolve (token direto, ou precisa logar depois?).
   - `POST /auth/login`: request e response (formato do JWT, tempo de expiração).
   - Como as rotas protegidas recebem o token (`Authorization: Bearer ...`) e como a API extrai o
     `user_id` dele.
   - Formato de erro de autenticação (401) — padronizar pra todas as rotas.

2. **`POST /runs`**
   - Campos obrigatórios vs. opcionais no request (name, algorithm, hyperparams, metrics — todos
     na criação, ou métricas podem vir depois?).
   - Validação: o que acontece se `hyperparams`/`metrics` vierem com formato errado?
   - Formato da resposta (o run criado inteiro, ou só o `id`?).

3. **`GET /runs`**
   - Paginação: fica pra depois, ou já implementa (`?page=`/`?limit=`)?
   - Quais campos aparecem na listagem (o spec original cita "candidato a cache" — decidir isso
     junto com `docs/db-diagram.md`, que ainda não fala de cache/Redis).
   - Filtros (por algoritmo, por status)?

4. **`GET /runs/{id}`**
   - Formato exato do payload, incluindo os artifacts (com URLs pré-assinadas do S3 — como isso
     aparece no JSON?).
   - 404 quando o run não existe ou não é do usuário logado (não vazar se existe e é de outro
     usuário, ou tanto faz?).

5. **`PATCH /runs/{id}`**
   - Quais campos são editáveis agora que `notes` não existe mais: `name`? `algorithm`?
     `hyperparams`? `metrics`? Faz sentido editar métricas depois de criado?
   - `PUT` ou só `PATCH`? (`PUT` substituiria o recurso inteiro, `PATCH` edita parcialmente — o
     uso aqui é sempre parcial, então provavelmente só `PATCH` já basta.)

6. **`DELETE /runs/{id}`**
   - Confirma: apaga no RDS (cascade já testado, ver `notebooks/db_smoke_test.py`) e precisa
     também apagar os objetos no S3 antes/depois — quem dispara isso?
   - Resposta: `204` sem corpo, ou algum corpo?

7. **`POST /runs/{id}/actual-predicted`** (upload do CSV)
   - Content-Type (`multipart/form-data`?), tamanho máximo aceito.
   - O que a rota faz de síncrono (upload pro S3) vs. assíncrono (o worker, via SNS/SQS) —
     crítico não bloquear a resposta HTTP esperando o processamento.
   - Resposta: o artifact criado com `status=pending`?
   - Rota também recebe uma imagem opcional (decisão em aberto do `spec.md`, seção 2, sobre qual é
     o arquivo binário obrigatório)? Ou fica só o CSV aqui e a imagem é outro endpoint?

8. **`GET /runs/compare`**
   - Formato do payload combinado (dois lados, cada um com metadados + métricas + hyperparams +
     URLs dos plots).
   - Isso é o candidato a cache no ElastiCache (`docs/spec.md`, seção 7) — a chave e o TTL ainda
     não foram discutidos/decididos formalmente.

9. **`GET /health`**
   - O mais simples de todos, mas decidir se ele testa a conexão com o banco (health check "de
     verdade") ou só responde `200` fixo (health check "liveness"). Pro ALB da Parte 2, geralmente
     o suficiente é só confirmar que o processo Flask está de pé.

## Como preencher este documento

Pra cada rota decidida, adicionar aqui (ou substituir a entrada da lista acima) algo como:

```
### POST /auth/login

Request:
{ "email": "...", "password": "..." }

Response 200:
{ "token": "...", "user": { "id": 1, "name": "...", "email": "..." } }

Erros:
- 401 se credenciais inválidas
```

Quando o contrato de uma rota estiver fechado, ela vira a especificação que guia o código da rota
em `app/routes/`.
