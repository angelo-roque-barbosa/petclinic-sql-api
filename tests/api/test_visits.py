"""Testes de visitas (tabela `visits`), com o banco como oráculo."""

from datetime import date, timedelta

import pytest

from conftest import COUNT_VISITS, DELETE_PET, DELETE_VISIT, INSERT_PET, PREPARED_PET, PREPARED_VISIT, today_utc

# Visita padrão: a data fica entre o nascimento do pet da fixture (2020-05-10) e hoje.
VISIT = {"date": "2026-11-01", "description": "Consulta de rotina"}

# Pergunta: qual é a linha de `visits` com o id que a API devolveu no POST?
# A consulta deve trazer, nesta ordem, pet_id, visit_date e description,
# e receber o id como parâmetro (%s).
SELECT_VISIT_BY_ID = """
SELECT pet_id, visit_date, description
FROM visits
WHERE id = %s;
"""

def test_criar_visita_com_dados_validos_grava_a_visita_ligada_ao_pet(api, db, owner_with_pet, visits_to_delete):
    """CT-API-VISITS-01: criar uma visita com dados válidos grava a data e a descrição enviadas, ligada ao pet certo."""
    # Preparar: o dono e o pet vêm da fixture, gravados por SQL
    owner_id = owner_with_pet["owner_id"]
    pet_id = owner_with_pet["pet_id"]

    # Agir
    response = api.post(f"/owners/{owner_id}/pets/{pet_id}/visits", json=VISIT)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        visits_to_delete.append(body["id"])

    # Verificar a resposta
    assert response.status_code == 201, f"POST da visita deveria responder 201, respondeu {response.status_code}"
    assert isinstance(body.get("id"), int), "a resposta deveria trazer o id numérico da visita criada"

    # Verificar o banco: ligada ao pet da preparação, com a data e a descrição enviadas
    row = db.execute(SELECT_VISIT_BY_ID, (body["id"],)).fetchone()
    expected = (pet_id, date.fromisoformat(VISIT["date"]), VISIT["description"])
    assert row == expected, f"a linha da visita {body['id']} deveria ser {expected}, é {row}"


# Pergunta: quantas visitas um pet tem hoje?
# Recebe o id do pet (%s) e devolve uma linha só, com um único valor: a quantidade de visitas dele.
COUNT_VISITS_BY_PET = """
SELECT COUNT(*) FROM visits WHERE pet_id = %s;
"""


@pytest.mark.parametrize("missing_field", ["date", "description"])
def test_criar_visita_sem_campo_obrigatorio_e_recusada_sem_gravar(api, db, owner_with_pet, visits_to_delete, missing_field):
    """CT-API-VISITS-02: criar uma visita sem data ou sem descrição responde 400 apontando o campo e não grava
    visita para o pet."""
    # Preparar: a visita padrão sem o campo da vez; o dono e o pet, sem visitas, vêm da fixture
    owner_id = owner_with_pet["owner_id"]
    pet_id = owner_with_pet["pet_id"]
    payload = {field: value for field, value in VISIT.items() if field != missing_field}

    # Agir
    response = api.post(f"/owners/{owner_id}/pets/{pet_id}/visits", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        visits_to_delete.append(body["id"])

    # Verificar a resposta: 400, e o erro aponta só o campo que faltou
    assert response.status_code == 400, f"POST de visita sem {missing_field} deveria responder 400, respondeu {response.status_code}"
    errors = body.get("schemaValidationErrors") or []
    assert errors, "a resposta deveria listar os erros de validação"
    assert {error["field"] for error in errors} == {missing_field}, (
        f"o erro deveria apontar só {missing_field}, apontou {sorted({error['field'] for error in errors})}"
    )

    # Verificar o banco: o pet, criado sem visitas, continua sem visitas
    visits_of_pet = db.execute(COUNT_VISITS_BY_PET, (pet_id,)).fetchone()[0]
    assert visits_of_pet == 0, f"o pet {pet_id} deveria continuar sem visitas, tem {visits_of_pet}"


def test_criar_visita_com_descricao_vazia_e_recusada_sem_gravar(api, db, owner_with_pet, visits_to_delete):
    """CT-API-VISITS-03: criar uma visita com descrição vazia responde 400 apontando description e não grava
    visita para o pet.

    A descrição só com espaços também deveria ser recusada, mas hoje é aceita: é o BUG-11, coberto pelo
    CT-BUG-11-01."""
    # Preparar: a visita padrão com a descrição vazia; o dono e o pet, sem visitas, vêm da fixture
    owner_id = owner_with_pet["owner_id"]
    pet_id = owner_with_pet["pet_id"]
    payload = {**VISIT, "description": ""}

    # Agir
    response = api.post(f"/owners/{owner_id}/pets/{pet_id}/visits", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        visits_to_delete.append(body["id"])

    # Verificar a resposta: 400, e o erro aponta só a descrição
    assert response.status_code == 400, f"POST de visita com descrição vazia deveria responder 400, respondeu {response.status_code}"
    errors = body.get("schemaValidationErrors") or []
    assert errors, "a resposta deveria listar os erros de validação"
    assert {error["field"] for error in errors} == {"description"}, (
        f"o erro deveria apontar só description, apontou {sorted({error['field'] for error in errors})}"
    )

    # Verificar o banco: o pet, criado sem visitas, continua sem visitas
    visits_of_pet = db.execute(COUNT_VISITS_BY_PET, (pet_id,)).fetchone()[0]
    assert visits_of_pet == 0, f"o pet {pet_id} deveria continuar sem visitas, tem {visits_of_pet}"


def test_criar_visita_com_descricao_de_255_caracteres_grava_inteira(api, db, owner_with_pet, visits_to_delete):
    """CT-API-VISITS-04: descrição com 255 caracteres, o limite do contrato, é aceita e gravada inteira."""
    # Preparar: a visita padrão com a descrição no limite; o dono e o pet vêm da fixture
    owner_id = owner_with_pet["owner_id"]
    pet_id = owner_with_pet["pet_id"]
    payload = {**VISIT, "description": "a" * 255}
    assert len(payload["description"]) == 255, "a descrição do teste deveria ter 255 caracteres"

    # Agir
    response = api.post(f"/owners/{owner_id}/pets/{pet_id}/visits", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        visits_to_delete.append(body["id"])

    # Verificar a resposta
    assert response.status_code == 201, f"POST de visita com descrição de 255 caracteres deveria responder 201, respondeu {response.status_code}"

    # Verificar o banco: a linha inteira, com a descrição de 255 caracteres sem corte
    row = db.execute(SELECT_VISIT_BY_ID, (body["id"],)).fetchone()
    expected = (pet_id, date.fromisoformat(payload["date"]), payload["description"])
    assert row == expected, f"a linha da visita {body['id']} deveria ter a descrição de 255 caracteres, tem {len(row[2]) if row else None}"


def test_criar_visita_com_descricao_de_256_caracteres_e_recusada_sem_gravar(api, db, owner_with_pet, visits_to_delete):
    """CT-API-VISITS-04: descrição com 256 caracteres, um acima do limite, responde 400 e não grava visita."""
    # Preparar: a visita padrão com a descrição acima do limite; o dono e o pet, sem visitas, vêm da fixture
    owner_id = owner_with_pet["owner_id"]
    pet_id = owner_with_pet["pet_id"]
    payload = {**VISIT, "description": "a" * 256}
    assert len(payload["description"]) == 256, "a descrição do teste deveria ter 256 caracteres"

    # Agir
    response = api.post(f"/owners/{owner_id}/pets/{pet_id}/visits", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        visits_to_delete.append(body["id"])

    # Verificar a resposta: 400, e o erro aponta só a descrição
    assert response.status_code == 400, f"POST de visita com descrição de 256 caracteres deveria responder 400, respondeu {response.status_code}"
    errors = body.get("schemaValidationErrors") or []
    assert errors, "a resposta deveria listar os erros de validação"
    assert {error["field"] for error in errors} == {"description"}, (
        f"o erro deveria apontar só description, apontou {sorted({error['field'] for error in errors})}"
    )

    # Verificar o banco: o pet, criado sem visitas, continua sem visitas
    visits_of_pet = db.execute(COUNT_VISITS_BY_PET, (pet_id,)).fetchone()[0]
    assert visits_of_pet == 0, f"o pet {pet_id} deveria continuar sem visitas, tem {visits_of_pet}"


def test_criar_visita_no_dia_do_nascimento_do_pet_grava_a_data(api, db, owner_with_pet, visits_to_delete):
    """CT-API-VISITS-05: uma visita no dia do nascimento do pet, o primeiro dia permitido, é aceita e gravada
    com a data enviada.

    Datas anteriores ao nascimento também deveriam ser recusadas, mas hoje são aceitas: é o BUG-12, coberto
    pelo CT-BUG-12-01."""
    # Preparar: a data da visita é o nascimento que a fixture gravou para o pet
    owner_id = owner_with_pet["owner_id"]
    pet_id = owner_with_pet["pet_id"]
    birth = PREPARED_PET["birth_date"]
    payload = {**VISIT, "date": birth.isoformat()}

    # Agir
    response = api.post(f"/owners/{owner_id}/pets/{pet_id}/visits", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        visits_to_delete.append(body["id"])

    # Verificar a resposta
    assert response.status_code == 201, f"POST de visita no dia do nascimento ({birth}) deveria responder 201, respondeu {response.status_code}"

    # Verificar o banco: a linha inteira, com a data do nascimento
    row = db.execute(SELECT_VISIT_BY_ID, (body["id"],)).fetchone()
    expected = (pet_id, birth, payload["description"])
    assert row == expected, f"a linha da visita {body['id']} deveria ser {expected}, é {row}"


def test_criar_visita_com_data_futura_grava_o_agendamento(api, db, owner_with_pet, visits_to_delete):
    """CT-API-VISITS-06: uma visita com data no futuro (hoje + 30 dias, no fuso da API) é um agendamento, é
    aceita e fica gravada com a data exata enviada.

    Hoje a API não tem limite máximo de antecedência; essa regra ainda está a confirmar."""
    # Preparar: a data é calculada na hora do teste, para continuar no futuro em qualquer dia
    owner_id = owner_with_pet["owner_id"]
    pet_id = owner_with_pet["pet_id"]
    visit_date = today_utc() + timedelta(days=30)
    assert visit_date > today_utc(), "a data do teste deveria estar no futuro"
    payload = {**VISIT, "date": visit_date.isoformat()}

    # Agir
    response = api.post(f"/owners/{owner_id}/pets/{pet_id}/visits", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        visits_to_delete.append(body["id"])

    # Verificar a resposta
    assert response.status_code == 201, f"POST de visita agendada para {visit_date} deveria responder 201, respondeu {response.status_code}"

    # Verificar o banco: a linha inteira, com a data futura exata
    row = db.execute(SELECT_VISIT_BY_ID, (body["id"],)).fetchone()
    expected = (pet_id, visit_date, payload["description"])
    assert row == expected, f"a linha da visita {body['id']} deveria ser {expected}, é {row}"


# Pet nascido antes de 2020: o da fixture owner_with_pet nasceu em 2020-05-10, e uma visita em 2020-02-29
# cairia antes do nascimento (BUG-12). É o mesmo pet do CT-API-VISITS-07a no Postman.
PET_BORN_BEFORE_2020 = {"name": "Mel", "birth_date": date(2019, 1, 15)}


@pytest.fixture
def pet_born_before_2020(db, prepared_owner, prepared_pet_type):
    """Grava direto no banco um pet nascido em 2019-01-15, do dono e do tipo das fixtures prepared_owner e
    prepared_pet_type, e entrega os ids e uma lista `visit_ids` para o teste registrar as visitas criadas.

    No fim, apaga as visitas registradas e depois o pet, nessa ordem por causa da chave estrangeira de
    `visits`; apagar zero linhas também serve. O dono e o tipo são apagados depois, pelas fixtures de que esta
    depende."""
    created = {"owner_id": prepared_owner, "type_id": prepared_pet_type, "visit_ids": []}
    created["pet_id"] = db.execute(
        INSERT_PET,
        (PET_BORN_BEFORE_2020["name"], PET_BORN_BEFORE_2020["birth_date"], created["type_id"], created["owner_id"]),
    ).fetchone()[0]
    yield created
    for visit_id in created["visit_ids"]:
        db.execute(DELETE_VISIT, (visit_id,))
    db.execute(DELETE_PET, (created["pet_id"],))


def test_criar_visita_em_29_de_fevereiro_de_ano_bissexto_grava_a_data(api, db, pet_born_before_2020):
    """CT-API-VISITS-07: 29 de fevereiro de um ano bissexto (2020-02-29) é uma data válida, é aceita e fica
    gravada igual.

    O mesmo dia num ano não bissexto (2021-02-29) deveria ser recusado com 400, mas hoje a API responde 500:
    é o BUG-08, coberto pelo CT-BUG-08-01."""
    # Preparar: a data cai depois do nascimento do pet, para não esbarrar no BUG-12
    owner_id = pet_born_before_2020["owner_id"]
    pet_id = pet_born_before_2020["pet_id"]
    visit_date = date(2020, 2, 29)
    assert visit_date > PET_BORN_BEFORE_2020["birth_date"], "a data do teste deveria ser depois do nascimento do pet"
    payload = {**VISIT, "date": visit_date.isoformat()}

    # Agir
    response = api.post(f"/owners/{owner_id}/pets/{pet_id}/visits", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        pet_born_before_2020["visit_ids"].append(body["id"])

    # Verificar a resposta
    assert response.status_code == 201, f"POST de visita em {visit_date} deveria responder 201, respondeu {response.status_code}"

    # Verificar o banco: a linha inteira, com o 29 de fevereiro
    row = db.execute(SELECT_VISIT_BY_ID, (body["id"],)).fetchone()
    expected = (pet_id, visit_date, payload["description"])
    assert row == expected, f"a linha da visita {body['id']} deveria ser {expected}, é {row}"


def test_criar_visita_igual_a_uma_existente_grava_outra_sem_mudar_a_primeira(api, db, owner_with_pet_and_visit, visits_to_delete):
    """CT-API-VISITS-09: enviar uma visita igual a outra que o pet já tem (mesma data e descrição) cria uma
    visita nova, com outro id, e a existente continua igual.

    Regra adotada: visitas iguais são permitidas, porque podem ser legítimas (um curativo de manhã e outro à
    tarde). O risco coberto é o envio repetido sobrescrever a visita existente ou ser descartado."""
    # Preparar: a primeira visita foi gravada por SQL pela fixture; o envio repete a data e a descrição dela
    owner_id = owner_with_pet_and_visit["owner_id"]
    pet_id = owner_with_pet_and_visit["pet_id"]
    existing_id = owner_with_pet_and_visit["visit_id"]
    existing_row = (pet_id, PREPARED_VISIT["visit_date"], PREPARED_VISIT["description"])
    payload = {"date": PREPARED_VISIT["visit_date"].isoformat(), "description": PREPARED_VISIT["description"]}
    visits_before = db.execute(COUNT_VISITS_BY_PET, (pet_id,)).fetchone()[0]

    # Agir
    response = api.post(f"/owners/{owner_id}/pets/{pet_id}/visits", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        visits_to_delete.append(body["id"])

    # Verificar a resposta: criada, com um id diferente do da visita existente
    assert response.status_code == 201, f"POST de visita igual a uma existente deveria responder 201, respondeu {response.status_code}"
    assert body["id"] != existing_id, f"a visita nova deveria ter outro id, veio o mesmo da existente ({existing_id})"

    # Verificar o banco: uma visita a mais no pet, a nova gravada como enviada e a existente sem mudança
    visits_after = db.execute(COUNT_VISITS_BY_PET, (pet_id,)).fetchone()[0]
    assert visits_after == visits_before + 1, f"o pet {pet_id} deveria ter {visits_before + 1} visitas, tem {visits_after}"
    new_row = db.execute(SELECT_VISIT_BY_ID, (body["id"],)).fetchone()
    assert new_row == existing_row, f"a visita nova {body['id']} deveria ser {existing_row}, é {new_row}"
    row_after = db.execute(SELECT_VISIT_BY_ID, (existing_id,)).fetchone()
    assert row_after == existing_row, f"a visita existente {existing_id} deveria continuar {existing_row}, é {row_after}"


# Pergunta: qual é o maior id da tabela `pets` hoje?
# Devolve uma linha só, com um único valor: o maior id.
SELECT_MAX_PET_ID = """
SELECT MAX(id) FROM pets;
"""


def test_criar_visita_para_pet_inexistente_e_recusada_sem_gravar(api, db, owner_with_pet, visits_to_delete):
    """CT-API-VISITS-10: criar uma visita para um pet que não existe, num dono que existe, responde 404 e não
    grava visita nenhuma.

    Hoje a recusa vem da chave estrangeira do banco, e não de uma validação da API: é a OBS-02. O pet da
    fixture serve de controle, para a visita não ir parar no pet que o dono tem."""
    # Preparar: o pet inexistente é o maior id de `pets` + 1, lido do banco na hora
    owner_id = owner_with_pet["owner_id"]
    control_pet_id = owner_with_pet["pet_id"]
    missing_pet_id = db.execute(SELECT_MAX_PET_ID).fetchone()[0] + 1
    visits_before = db.execute(COUNT_VISITS).fetchone()[0]

    # Agir
    response = api.post(f"/owners/{owner_id}/pets/{missing_pet_id}/visits", json=VISIT)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        visits_to_delete.append(body["id"])

    # Verificar a resposta
    assert response.status_code == 404, f"POST de visita para o pet inexistente {missing_pet_id} deveria responder 404, respondeu {response.status_code}"

    # Verificar o banco: o total de visitas não muda e o pet de controle continua sem visitas
    visits_after = db.execute(COUNT_VISITS).fetchone()[0]
    assert visits_after == visits_before, f"o total de visitas deveria continuar {visits_before}, ficou {visits_after}"
    control_visits = db.execute(COUNT_VISITS_BY_PET, (control_pet_id,)).fetchone()[0]
    assert control_visits == 0, f"o pet de controle {control_pet_id} deveria continuar sem visitas, tem {control_visits}"
