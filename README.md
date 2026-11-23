# petclinic-sql-api

Testes de API e de integridade de dados para o [Spring PetClinic REST](https://github.com/spring-petclinic/spring-petclinic-rest).
O banco é o oráculo: cada teste chama a API e confere o efeito direto no PostgreSQL.

> Status: em construção. Fase atual: **4 — pytest com banco como oráculo**.

## Stack

Python, pytest, PostgreSQL/SQL, Postman/Newman, Gherkin (pytest-bdd), k6, Docker Compose e GitHub Actions.

## Como rodar

Requer Docker com o plugin Compose.

```bash
docker compose up -d --wait                           # sobe API e PostgreSQL e espera os dois ficarem prontos
docker compose exec db psql -U petclinic petclinic    # abre o psql no banco
docker compose down -v                                # derruba e apaga os dados do banco
```

A imagem da API é fixada pelo digest da versão 4.0.2 em que os bugs foram reproduzidos, para o ambiente local e o
GitHub Actions rodarem sempre a mesma versão; o comentário no `docker-compose.yml` diz como trocar.

Os dois serviços têm healthcheck: o banco com `pg_isready`, a API com `curl` no `/v3/api-docs`. A API só sobe
depois do banco saudável, e o `--wait` só termina quando a API responde (cerca de 20 s).

Um terceiro serviço, `db-index-cleanup`, sobe depois que a API fica pronta e, a cada 10 s, apaga as cópias de índice
que ela cria a cada início (ver o aviso no BUG-02, em [BUGS.md](BUGS.md)). Assim limpa sozinho depois de `docker compose up`,
`docker compose restart` ou `docker compose restart api`. O healthcheck dele só fica saudável depois da primeira
limpeza sem erro; se ela falhar, o `--wait` também falha. Para ver as cópias, pare o serviço:
`docker compose stop db-index-cleanup` (e `docker compose start db-index-cleanup` para religar).

Testes:

```bash
npm ci                                                # instala o Newman na versão do package-lock.json
npx newman run postman/petclinic.postman_collection.json -e postman/local.postman_environment.json

python3 -m venv .venv                                 # ambiente virtual do pytest, só na primeira vez
.venv/bin/pip install -r requirements.txt             # versões exatas, inclusive as dependências indiretas
.venv/bin/pytest tests/api -v                         # testes com o banco como oráculo
```

Os testes do pytest chamam a API e conferem o efeito direto no banco. As fixtures compartilhadas ficam em
`tests/conftest.py`: elas esperam a API responder (por laço, nunca por espera fixa), abrem a conexão com o banco e
apagam no fim os dados que cada teste criou. Se a API ou o banco não estiverem no ar, o pytest para com código 3,
porque ambiente fora do ar não é resultado. Os endereços vêm de variáveis de ambiente (`API_BASE_URL`, `PGHOST`,
`PGPORT` e outras), com os valores do `docker-compose.yml` como padrão.
No GitHub Actions, o workflow [`pytest.yml`](.github/workflows/pytest.yml) faz o mesmo a cada push e pull request,
separado do workflow do Newman, para cada um mostrar a própria situação.

A coleção roda inteira e na ordem: ela cria os próprios dados, apaga tudo no fim e confere, no
`CT-API-INTEGRITY-01`, que os totais terminaram iguais aos do início. No GitHub Actions, o workflow
[`newman.yml`](.github/workflows/newman.yml) faz o mesmo a cada push e pull request: sobe o
`docker-compose.yml` no próprio runner, roda a coleção e guarda o relatório JUnit; se uma verificação
falhar, o job falha e mostra os logs da API e do banco.

- API: http://localhost:9966/petclinic/api
- Swagger: http://localhost:9966/petclinic/swagger-ui.html

## Fases

Núcleo (fases 0 a 4): já forma um projeto completo. Complemento (fases 5 a 8): só depois do núcleo.

- [x] **0. Repositório:** estrutura de pastas, `.gitignore`, este README, primeiro commit.
- [x] **1. Ambiente:** `docker-compose.yml` com API e PostgreSQL; ler o `initDB.sql`; escrever `docs/dicionario-de-dados.md`.
- [x] **2. SQL exploratório:** de 10 a 15 consultas de integridade em `sql/`.
- [x] **3. Postman:** CRUD de donos, pets e visitas com testes de status e corpo; Newman no GitHub Actions.
- [ ] **4. pytest com banco como oráculo:** chamada na API e verificação no banco; valor-limite e partição.
- [ ] **5. Contrato:** respostas validadas contra o OpenAPI da aplicação.
- [ ] **6. BDD:** de 5 a 8 cenários Gherkin para "agendar visita"; 2 ou 3 automatizados.
- [ ] **7. Jira:** bugs encontrados passando pelo ciclo completo; capturas aqui no README.
- [ ] **8. k6:** carga leve contra o ambiente local.

## Estrutura

```
docs/              dicionário de dados e casos de teste
BUGS.md            bugs e observações em detalhe
sql/               consultas exploratórias de integridade
sql/maintenance/   limpeza automática das cópias de índice (BUG-02)
postman/           coleção e environment do Newman
tests/api/         pytest com o banco como oráculo
tests/contract/    validação contra o OpenAPI
tests/bdd/         cenários Gherkin e pytest-bdd
k6/                teste de carga leve
.github/workflows/ CI
```

## Decisões

> Uma linha por decisão, sempre com o porquê.

- **PetClinic REST como sistema testado:** roda local e no CI, com acesso total ao banco; nada de site de terceiros nem ação irreversível.
- **PostgreSQL em vez do banco em memória:** permite consultar o efeito de cada chamada com SQL.
- …

## Consultas de integridade

Cada arquivo de `sql/` responde a uma pergunta sobre regras que o banco não garante (ver "Fora do banco" no
dicionário). Resultado no banco recém-criado (dados do `populateDB`), em 2026-11-13. Cada consulta foi conferida
também com dados ruins inseridos numa transação desfeita com `ROLLBACK`.

| Arquivo | Pergunta | Resultado |
|:---|:---|:---|
| `01_owners_invalid_telephone.sql` | Telefone fora de 10 dígitos? | Nenhum, nos 10 donos |
| `02_owners_missing_name.sql` | Dono sem nome ou sobrenome, ou só com espaços? | Nenhum |
| `03_pets_invalid_birth_date.sql` | Pet nascido no futuro ou com mais de 30 anos? | Nenhum no futuro; Samantha (7) e Max (8), de 1995-09-04, têm 31 anos |
| `04_visits_before_birth.sql` | Visita antes do nascimento do pet? | Nenhuma, nas 4 visitas |
| `05_visits_duplicated.sql` | Visita repetida (mesmo pet, data e descrição)? | Nenhuma |
| `06_types_specialties_duplicated_or_unnamed.sql` | Tipo ou especialidade sem nome ou repetido, inclusive com maiúsculas diferentes? | Nenhum, nos 6 tipos e 3 especialidades |
| `07_vets_without_specialty.sql` | Veterinário sem especialidade? | 2 dos 6: James Carter (1) e Sharon Jenkins (6) |
| `08_specialties_unused.sql` | Especialidade que nenhum veterinário usa? | Nenhuma |
| `09_users_password_not_bcrypt.sql` | Senha que não parece hash bcrypt? | Nenhuma; o único usuário (`admin`) tem hash `$2a$` de 60 caracteres |
| `10_roles_unknown.sql` | Papel fora dos três que a API conhece? | Nenhum; os 3 papéis são do `admin` |
| `11_duplicate_indexes.sql` | Índices duplicados? | Nenhum no banco novo; 7 a cada reinício da API (BUG-02), apagados pela limpeza automática em até 10 s |
| `12_owners_pets_visits_count.sql` | Quantos pets e visitas tem cada dono? | Todos os 10 têm pet (13 no total); Eduardo Rodriquez (3), Jean Coleman (6) e Carlos Estaban (10) têm 2; só a Jean tem visitas (as 4) |

O banco permite todos os casos acima; nos dados atuais só aparecem os pets antigos e os vets sem especialidade.

## Partições e valores-limite

Valores-limite e partições testados no pytest, com `pytest.mark.parametrize`. "Obtido" é o resultado da última
execução; quando difere do esperado, a linha aponta o bug.

| Campo | Partição / limite | Valor | Esperado | Obtido |
|-------|-------------------|-------|----------|--------|
| `telephone` (POST /api/owners) | abaixo do limite | 9 dígitos (`819999000`) | 400, nada gravado | 400, nada gravado |
| `telephone` (POST /api/owners) | no limite | 10 dígitos (`8199990002`) | 201, gravado igual | 201, gravado igual |
| `telephone` (POST /api/owners) | acima do limite (o banco tem `varchar(10)`) | 11 dígitos (`81999900021`) | 400, nada gravado | 400, nada gravado |
| `telephone` (POST /api/owners) | não numérico | `abc` | 400, nada gravado | 400, nada gravado |
| `telephone` (POST /api/owners) | 10 caracteres, com letras | `60855510ab` | 400, nada gravado | 400, nada gravado |
| `telephone` (POST /api/owners) | 10 caracteres, com espaços | `608 555 10` | 400, nada gravado | 400, nada gravado |
| `telephone` (POST /api/owners) | vazio (o `NOT NULL` do banco não barra) | `''` | 400, nada gravado | 400, nada gravado |
| `firstName` (POST /api/owners) | vazio | `''` | 400, nada gravado | 400, nada gravado |
| `firstName` (POST /api/owners) | menor tamanho válido | `A` (1 letra) | 201, gravado igual | 201, gravado igual |
| `firstName` (POST /api/owners) | só espaços (o banco aceita) | `'   '` | 400, nada gravado | 400, nada gravado |
| `lastName` (POST /api/owners) | vazio | `''` | 400, nada gravado | 400, nada gravado |
| `lastName` (POST /api/owners) | menor tamanho válido | `A` (1 letra) | 201, gravado igual | 201, gravado igual |
| `lastName` (POST /api/owners) | só espaços (o banco aceita) | `'   '` | 400, nada gravado | 400, nada gravado |
| `firstName` (POST /api/owners) | no limite (no banco, `text` sem limite) | 30 letras | 201, gravado inteiro | 201, gravado inteiro |
| `firstName` (POST /api/owners) | acima do limite | 31 letras | 400, nada gravado | 400, nada gravado |
| `lastName` (POST /api/owners) | no limite (no banco, `text` sem limite) | 30 letras | 201, gravado inteiro | 201, gravado inteiro |
| `lastName` (POST /api/owners) | acima do limite | 31 letras | 400, nada gravado | 400, nada gravado |
| `firstName` (POST /api/owners) | com dígito, tamanho válido | `Ana2` | 400, nada gravado | 400, nada gravado |
| `lastName` (POST /api/owners) | com dígito, tamanho válido | `Ana2` | 400, nada gravado | 400, nada gravado |
| `name` (POST /api/owners/{id}/pets) | vazio (o banco aceita) | `''` | 400, nada gravado | 400, nada gravado |
| `name` (POST /api/owners/{id}/pets) | só espaços (o banco aceita) | `'   '` | 400, nada gravado | 201, gravado (BUG-06) |
| `name` (POST /api/owners/{id}/pets) | no limite | 30 caracteres | 201, gravado inteiro | 201, gravado inteiro |
| `name` (POST /api/owners/{id}/pets) | acima do limite | 31 caracteres | 400, nada gravado | 400, nada gravado |
| `birthDate` (POST /api/owners/{id}/pets) | no limite: hoje, em UTC | data de hoje | 201, gravado igual | 201, gravado igual |
| `birthDate` (POST /api/owners/{id}/pets) | futuro, logo depois do limite | amanhã | 400, nada gravado | 400, nada gravado |
| `birthDate` (POST /api/owners/{id}/pets) | futuro distante (o banco aceita) | `2099-01-01` | 400, nada gravado | 400, nada gravado |
| `birthDate` (POST /api/owners/{id}/pets) | no limite: exatamente 50 anos, em UTC | hoje − 50 anos | 201, gravado igual | 201, gravado igual |
| `birthDate` (POST /api/owners/{id}/pets) | antiga, logo depois do limite | hoje − 50 anos − 1 dia | 400, nada gravado | 400, nada gravado |
| `birthDate` (POST /api/owners/{id}/pets) | antiga demais (o banco aceita) | `1800-01-01` | 400, nada gravado | 400, nada gravado |

## Achados

Dezessete bugs e duas observações, todos reproduzidos do zero e com evidência no banco. Os detalhes (passos,
esperado, obtido, evidência e causa) estão em [BUGS.md](BUGS.md).

| Bug | Resumo | Impacto | Issue |
|:---|:---|:---|:---|
| BUG-01 | `GET /api/owners/abc` responde 500 em vez de 400 e expõe o nome da exceção | médio | [#1](https://github.com/angelo-roque-barbosa/petclinic-sql-api/issues/1) |
| BUG-02 | Cada reinício da API cria mais uma cópia de 7 índices do banco (a suíte limpa as cópias automaticamente) | baixo, acumula | [#2](https://github.com/angelo-roque-barbosa/petclinic-sql-api/issues/2) |
| BUG-03 | Apagar um dono apaga também o tipo do pet; com tipo compartilhado, o dono não pode ser apagado | alto | [#3](https://github.com/angelo-roque-barbosa/petclinic-sql-api/issues/3) |
| BUG-04 | `POST /api/visits` com `id` no corpo sobrescreve uma visita existente e responde 201 | alto | [#4](https://github.com/angelo-roque-barbosa/petclinic-sql-api/issues/4) |
| BUG-05 | `GET /api/owners?lastName=` sem resultado responde 404 em vez de 200 com lista vazia | baixo a médio | [#5](https://github.com/angelo-roque-barbosa/petclinic-sql-api/issues/5) |
| BUG-06 | `POST` de pet aceita e grava nome só com espaços | baixo a médio | [#6](https://github.com/angelo-roque-barbosa/petclinic-sql-api/issues/6) |
| BUG-07 | Apagar um tipo de pet apaga todos os pets desse tipo, de qualquer dono, e as visitas deles | alto | [#7](https://github.com/angelo-roque-barbosa/petclinic-sql-api/issues/7) |
| BUG-08 | Corpo ilegível (data inválida, tipo errado ou JSON quebrado) responde 500 em vez de 400 | médio | [#8](https://github.com/angelo-roque-barbosa/petclinic-sql-api/issues/8) |
| BUG-09 | Id negativo na URL responde 500 em vez de 400 nas 22 operações que recebem id | médio | [#9](https://github.com/angelo-roque-barbosa/petclinic-sql-api/issues/9) |
| BUG-10 | `PUT` de pet e `POST` de visita pelo caminho de outro dono alteram o pet e respondem 204 e 201; o `POST` de visita aceita até dono inexistente | médio | [#10](https://github.com/angelo-roque-barbosa/petclinic-sql-api/issues/10) |
| BUG-11 | `POST` de visita aceita e grava descrição só com espaços | baixo a médio | [#11](https://github.com/angelo-roque-barbosa/petclinic-sql-api/issues/11) |
| BUG-12 | `POST` de visita aceita data anterior ao nascimento do pet | baixo a médio | [#12](https://github.com/angelo-roque-barbosa/petclinic-sql-api/issues/12) |
| BUG-13 | Data enviada como número é lida como dias desde 1970 e gravada: um timestamp vira visita no ano 4,9 milhões, com 201 | baixo a médio | [#13](https://github.com/angelo-roque-barbosa/petclinic-sql-api/issues/13) |
| BUG-14 | `POST /api/pettypes` aceita nome repetido, inclusive com outra caixa ou espaço no fim, e o `PUT` renomeia para um nome que já existe: o banco fica com `cat`, `Cat`, `CAT` e `cat ` | baixo a médio | [#14](https://github.com/angelo-roque-barbosa/petclinic-sql-api/issues/14) |
| BUG-15 | O mesmo do BUG-14 nas especialidades: `POST` e `PUT` aceitam nome repetido, inclusive com outra caixa ou espaço no fim | baixo a médio | [#15](https://github.com/angelo-roque-barbosa/petclinic-sql-api/issues/15) |
| BUG-16 | `DELETE` de especialidade em uso responde 404, como se ela não existisse; nada é apagado, porque o banco recusa | baixo a médio | [#16](https://github.com/angelo-roque-barbosa/petclinic-sql-api/issues/16) |
| BUG-17 | `POST` e `PUT` de veterinário resolvem a especialidade pelo nome: o `id` é ignorado, nome desconhecido some com 201/204 e o `PUT` apaga as que existiam | médio a alto | [#17](https://github.com/angelo-roque-barbosa/petclinic-sql-api/issues/17) |

**OBS-01:** o contrato documenta 200 como sucesso em sete endpoints, mas a API devolve 201 ou 204 (o correto). Não
é bug; fica para a validação de contrato da fase 5.

**OBS-02:** pet com tipo inexistente recebe 404 e nada é gravado, mas a recusa só acontece no banco e a resposta
expõe o nome da exceção. O mesmo vale para visita de pet inexistente.

## O que ficou de fora

> Preencher no fim, com o motivo.
