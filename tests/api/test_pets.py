"""Testes de pets (tabela `pets`), com o banco como oráculo."""

from datetime import date

import pytest

from conftest import PREPARED_PET_TYPE_NAME

# Pet padrão do docs/casos-de-teste.md: nome com letras, nascimento no passado. O tipo é o da fixture.
PET = {"name": "Rex", "birthDate": "2020-05-10"}

# Pergunta: qual é a linha de `pets` com o id que a API devolveu no POST?
# A consulta deve trazer, nesta ordem, name, birth_date, owner_id e type_id,
# e receber o id como parâmetro (%s).
SELECT_PET_BY_ID = """
SELECT name, birth_date, owner_id, type_id
FROM pets
WHERE id = %s;
"""


def test_criar_pet_com_dados_validos_grava_o_pet_ligado_ao_dono_e_ao_tipo(
    api, db, prepared_owner, prepared_pet_type, pets_to_delete
):
    """CT-API-PETS-01: criar um pet com dados válidos grava os dados enviados, ligado ao dono e ao tipo certos."""
    # Preparar: o dono e o tipo vêm das fixtures, gravados por SQL
    owner_id = prepared_owner
    type_id = prepared_pet_type
    payload = {**PET, "type": {"id": type_id, "name": PREPARED_PET_TYPE_NAME}}

    # Agir
    response = api.post(f"/owners/{owner_id}/pets", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        pets_to_delete.append(body["id"])

    # Verificar a resposta
    assert response.status_code == 201, f"POST /owners/{owner_id}/pets deveria responder 201, respondeu {response.status_code}"
    assert isinstance(body.get("id"), int), "a resposta deveria trazer o id numérico do pet criado"

    # Verificar o banco: nome e nascimento enviados, ligado ao dono e ao tipo da preparação
    row = db.execute(SELECT_PET_BY_ID, (body["id"],)).fetchone()
    expected = (PET["name"], date.fromisoformat(PET["birthDate"]), owner_id, type_id)
    assert row == expected, f"a linha do pet {body['id']} deveria ser {expected}, é {row}"


# Pergunta: quantos pets um dono tem hoje?
# Recebe o id do dono (%s) e devolve uma linha só, com um único valor: a quantidade de pets dele.
COUNT_PETS_BY_OWNER = """
SELECT COUNT(*) FROM pets WHERE owner_id = %s;
"""


@pytest.mark.parametrize("missing_field", ["name", "birthDate", "type"])
def test_criar_pet_sem_campo_obrigatorio_e_recusado_sem_gravar(
    api, db, prepared_owner, prepared_pet_type, pets_to_delete, missing_field
):
    """CT-API-PETS-02: criar um pet sem nome, sem data de nascimento ou sem tipo responde 400 apontando o
    campo e não grava pet para o dono."""
    # Preparar: o pet padrão sem o campo da vez; o dono e o tipo vêm das fixtures
    owner_id = prepared_owner
    full_payload = {**PET, "type": {"id": prepared_pet_type, "name": PREPARED_PET_TYPE_NAME}}
    payload = {field: value for field, value in full_payload.items() if field != missing_field}

    # Agir
    response = api.post(f"/owners/{owner_id}/pets", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        pets_to_delete.append(body["id"])

    # Verificar a resposta: 400, e o erro aponta só o campo que faltou
    assert response.status_code == 400, f"POST de pet sem {missing_field} deveria responder 400, respondeu {response.status_code}"
    errors = body.get("schemaValidationErrors") or []
    assert errors, "a resposta deveria listar os erros de validação"
    assert {error["field"] for error in errors} == {missing_field}, (
        f"o erro deveria apontar só {missing_field}, apontou {sorted({error['field'] for error in errors})}"
    )

    # Verificar o banco: o dono, criado sem pets, continua sem pets
    pets_of_owner = db.execute(COUNT_PETS_BY_OWNER, (owner_id,)).fetchone()[0]
    assert pets_of_owner == 0, f"o dono {owner_id} deveria continuar sem pets, tem {pets_of_owner}"


def test_criar_pet_com_nome_vazio_e_recusado_sem_gravar(api, db, prepared_owner, prepared_pet_type, pets_to_delete):
    """CT-API-PETS-03: criar um pet com nome vazio responde 400 apontando name e não grava pet para o dono.

    O nome só com espaços também deveria ser recusado, mas hoje é aceito: é o BUG-06, coberto pelo CT-BUG-06-01."""
    # Preparar: o pet padrão com o nome vazio; o dono e o tipo vêm das fixtures
    owner_id = prepared_owner
    payload = {**PET, "name": "", "type": {"id": prepared_pet_type, "name": PREPARED_PET_TYPE_NAME}}

    # Agir
    response = api.post(f"/owners/{owner_id}/pets", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        pets_to_delete.append(body["id"])

    # Verificar a resposta: 400, e o erro aponta só o nome
    assert response.status_code == 400, f"POST de pet com nome vazio deveria responder 400, respondeu {response.status_code}"
    errors = body.get("schemaValidationErrors") or []
    assert errors, "a resposta deveria listar os erros de validação"
    assert {error["field"] for error in errors} == {"name"}, (
        f"o erro deveria apontar só name, apontou {sorted({error['field'] for error in errors})}"
    )

    # Verificar o banco: o dono, criado sem pets, continua sem pets
    pets_of_owner = db.execute(COUNT_PETS_BY_OWNER, (owner_id,)).fetchone()[0]
    assert pets_of_owner == 0, f"o dono {owner_id} deveria continuar sem pets, tem {pets_of_owner}"


def test_criar_pet_com_nome_de_30_caracteres_grava_o_nome_inteiro(api, db, prepared_owner, prepared_pet_type, pets_to_delete):
    """CT-API-PETS-04: nome do pet com 30 caracteres, o limite do contrato, é aceito e gravado inteiro."""
    # Preparar: o pet padrão com o nome no limite; o dono e o tipo vêm das fixtures
    owner_id = prepared_owner
    payload = {**PET, "name": "a" * 30, "type": {"id": prepared_pet_type, "name": PREPARED_PET_TYPE_NAME}}
    assert len(payload["name"]) == 30, "o nome do teste deveria ter 30 caracteres"

    # Agir
    response = api.post(f"/owners/{owner_id}/pets", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        pets_to_delete.append(body["id"])

    # Verificar a resposta
    assert response.status_code == 201, f"POST de pet com nome de 30 caracteres deveria responder 201, respondeu {response.status_code}"

    # Verificar o banco: a linha inteira, com o nome de 30 caracteres sem corte
    row = db.execute(SELECT_PET_BY_ID, (body["id"],)).fetchone()
    expected = (payload["name"], date.fromisoformat(PET["birthDate"]), owner_id, prepared_pet_type)
    assert row == expected, f"a linha do pet {body['id']} deveria ser {expected}, é {row}"


def test_criar_pet_com_nome_de_31_caracteres_e_recusado_sem_gravar(api, db, prepared_owner, prepared_pet_type, pets_to_delete):
    """CT-API-PETS-04: nome do pet com 31 caracteres, um acima do limite, responde 400 e não grava pet."""
    # Preparar: o pet padrão com o nome acima do limite; o dono e o tipo vêm das fixtures
    owner_id = prepared_owner
    payload = {**PET, "name": "a" * 31, "type": {"id": prepared_pet_type, "name": PREPARED_PET_TYPE_NAME}}
    assert len(payload["name"]) == 31, "o nome do teste deveria ter 31 caracteres"

    # Agir
    response = api.post(f"/owners/{owner_id}/pets", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        pets_to_delete.append(body["id"])

    # Verificar a resposta: 400, e o erro aponta só o nome
    assert response.status_code == 400, f"POST de pet com nome de 31 caracteres deveria responder 400, respondeu {response.status_code}"
    errors = body.get("schemaValidationErrors") or []
    assert errors, "a resposta deveria listar os erros de validação"
    assert {error["field"] for error in errors} == {"name"}, (
        f"o erro deveria apontar só name, apontou {sorted({error['field'] for error in errors})}"
    )

    # Verificar o banco: o dono, criado sem pets, continua sem pets
    pets_of_owner = db.execute(COUNT_PETS_BY_OWNER, (owner_id,)).fetchone()[0]
    assert pets_of_owner == 0, f"o dono {owner_id} deveria continuar sem pets, tem {pets_of_owner}"
