"""Testes de visitas (tabela `visits`), com o banco como oráculo."""

from datetime import date, timedelta

import pytest

from conftest import PREPARED_PET, today_utc

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
