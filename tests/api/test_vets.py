"""Testes de veterinários (tabelas `vets` e `vet_specialties`), com o banco como oráculo."""

from conftest import PREPARED_SPECIALTY_NAME, SECOND_SPECIALTY_NAME

# Veterinário padrão do docs/casos-de-teste.md: nome e sobrenome só com letras. As especialidades são as das
# fixtures, montadas em cada teste.
VET = {"firstName": "Helena", "lastName": "Costa"}

# Pergunta: qual é a linha de `vets` com o id que a API devolveu no POST?
# Recebe o id (%s) e devolve uma linha com first_name e last_name, nesta ordem. Se o veterinário não existir,
# não devolve linha.
SELECT_VET_BY_ID = """
SELECT first_name, last_name FROM vets WHERE id = %s;
"""

# Pergunta: quais especialidades estão ligadas a um veterinário?
# Recebe o id do veterinário (%s) e devolve uma linha por ligação, com um valor só: o specialty_id, em ordem
# crescente. Se o veterinário não tiver ligações, não devolve linha.
SELECT_SPECIALTY_IDS_BY_VET = """
SELECT specialty_id
FROM vet_specialties
WHERE vet_id = %s
ORDER BY specialty_id ASC;
"""


def test_criar_veterinario_com_especialidades_grava_o_nome_e_as_ligacoes(
    api, db, prepared_specialty, second_specialty, vets_to_delete
):
    """CT-API-VETS-01: criar um veterinário com duas especialidades responde 201, grava em `vets` o nome e o
    sobrenome enviados e em `vet_specialties` exatamente duas ligações, uma com cada especialidade."""
    # Preparar: as duas especialidades vêm das fixtures
    payload = {
        **VET,
        "specialties": [
            {"id": prepared_specialty, "name": PREPARED_SPECIALTY_NAME},
            {"id": second_specialty, "name": SECOND_SPECIALTY_NAME},
        ],
    }

    # Agir
    response = api.post("/vets", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        vets_to_delete.append(body["id"])

    # Verificar a resposta
    assert response.status_code == 201, f"POST /vets deveria responder 201, respondeu {response.status_code}"

    # Verificar o banco: o nome e o sobrenome enviados, e exatamente as duas ligações
    row = db.execute(SELECT_VET_BY_ID, (body["id"],)).fetchone()
    expected = (payload["firstName"], payload["lastName"])
    assert row == expected, f"a linha do veterinário {body['id']} deveria ser {expected}, é {row}"
    links = db.execute(SELECT_SPECIALTY_IDS_BY_VET, (body["id"],)).fetchall()
    expected_links = [(specialty_id,) for specialty_id in sorted((prepared_specialty, second_specialty))]
    assert links == expected_links, f"o veterinário {body['id']} deveria ter as ligações {expected_links}, tem {links}"
