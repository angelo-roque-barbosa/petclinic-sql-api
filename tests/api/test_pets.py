"""Testes de pets (tabela `pets`), com o banco como oráculo."""

from datetime import date

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
