"""Testes de veterinários (tabelas `vets` e `vet_specialties`), com o banco como oráculo."""

import pytest

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


# Pergunta: quantos veterinários existem hoje?
# Devolve uma linha só, com um único valor: o total de linhas de `vets`.
COUNT_VETS = """
SELECT COUNT(*) FROM vets;
"""


@pytest.mark.parametrize(
    ("field", "value"),
    [
        pytest.param("firstName", None, id="sem-firstName"),
        pytest.param("lastName", None, id="sem-lastName"),
        pytest.param("firstName", "", id="firstName-vazio"),
        pytest.param("lastName", "", id="lastName-vazio"),
    ],
)
def test_criar_veterinario_sem_nome_ou_sobrenome_e_recusado_sem_gravar(api, db, vets_to_delete, field, value):
    """CT-API-VETS-02: criar um veterinário sem nome ou sem sobrenome (campo ausente ou vazio) responde 400
    apontando só o campo da variação e não grava veterinário nenhum.

    O banco aceitaria nome e sobrenome NULL: quem recusa é a validação da API. O corpo leva `specialties`
    vazia, porque a lista é obrigatória e, sem ela, o erro apontaria outro campo."""
    # Preparar: o veterinário padrão sem especialidades, com o campo da vez ausente (value None) ou vazio
    payload = {**VET, "specialties": []}
    if value is None:
        del payload[field]
    else:
        payload[field] = value
    vets_before = db.execute(COUNT_VETS).fetchone()[0]

    # Agir
    response = api.post("/vets", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        vets_to_delete.append(body["id"])

    # Verificar a resposta: 400, e o erro aponta só o campo da variação
    assert response.status_code == 400, f"POST /vets com {payload} deveria responder 400, respondeu {response.status_code}"
    errors = body.get("schemaValidationErrors") or []
    assert errors, "a resposta deveria listar os erros de validação"
    assert {error["field"] for error in errors} == {field}, (
        f"o erro deveria apontar só {field}, apontou {sorted({error['field'] for error in errors})}"
    )

    # Verificar o banco: o total de veterinários não muda
    vets_after = db.execute(COUNT_VETS).fetchone()[0]
    assert vets_after == vets_before, f"o total de veterinários deveria continuar {vets_before}, ficou {vets_after}"
