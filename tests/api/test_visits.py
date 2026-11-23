"""Testes de visitas (tabela `visits`), com o banco como oráculo."""

from datetime import date

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
