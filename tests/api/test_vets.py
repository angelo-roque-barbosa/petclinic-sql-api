"""Testes de veterinários (tabelas `vets` e `vet_specialties`), com o banco como oráculo."""

import pytest

from conftest import (
    COUNT_VET_SPECIALTIES,
    DELETE_VET,
    DELETE_VET_SPECIALTIES_BY_VET,
    INSERT_VET,
    INSERT_VET_SPECIALTY,
    PREPARED_SPECIALTY_NAME,
    PREPARED_VET,
    SECOND_SPECIALTY_NAME,
    THIRD_SPECIALTY_NAME,
)

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


@pytest.mark.parametrize(
    "first_name",
    [
        pytest.param("a" * 30, id="30-letras"),
        pytest.param("á" * 30, id="30-acentuadas-60-bytes"),
    ],
)
def test_criar_veterinario_com_nome_de_30_letras_grava_inteiro(api, db, vets_to_delete, first_name):
    """CT-API-VETS-03: um nome de veterinário com 30 letras, o limite do contrato, é aceito e gravado inteiro.
    O limite conta caracteres, não bytes: 30 letras acentuadas (60 bytes em UTF-8) também passam."""
    # Preparar
    assert len(first_name) == 30, f"o nome do teste deveria ter 30 letras, tem {len(first_name)}"
    payload = {**VET, "firstName": first_name, "specialties": []}

    # Agir
    response = api.post("/vets", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        vets_to_delete.append(body["id"])

    # Verificar a resposta
    assert response.status_code == 201, f"POST /vets com nome de 30 letras deveria responder 201, respondeu {response.status_code}"

    # Verificar o banco: o nome gravado é o enviado, sem corte, com o sobrenome enviado
    row = db.execute(SELECT_VET_BY_ID, (body["id"],)).fetchone()
    expected = (payload["firstName"], payload["lastName"])
    assert row == expected, f"o veterinário {body['id']} deveria ser {expected}, é {row}"


@pytest.mark.parametrize(
    "first_name",
    [
        pytest.param("a" * 31, id="31-letras"),
        pytest.param("Ana2", id="com-digito"),
        pytest.param("   ", id="so-espacos"),
    ],
)
def test_criar_veterinario_com_nome_fora_do_padrao_ou_do_limite_e_recusado_sem_gravar(api, db, vets_to_delete, first_name):
    """CT-API-VETS-03: um nome de veterinário com 31 letras, com dígito ou só com espaços responde 400
    apontando o campo `firstName` e não grava veterinário nenhum."""
    # Preparar
    payload = {**VET, "firstName": first_name, "specialties": []}
    vets_before = db.execute(COUNT_VETS).fetchone()[0]

    # Agir
    response = api.post("/vets", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        vets_to_delete.append(body["id"])

    # Verificar a resposta: 400, e o erro aponta só o campo firstName
    assert response.status_code == 400, f"POST /vets com firstName {first_name!r} deveria responder 400, respondeu {response.status_code}"
    errors = body.get("schemaValidationErrors") or []
    assert errors, "a resposta deveria listar os erros de validação"
    assert {error["field"] for error in errors} == {"firstName"}, (
        f"o erro deveria apontar só firstName, apontou {sorted({error['field'] for error in errors})}"
    )

    # Verificar o banco: o total de veterinários não muda
    vets_after = db.execute(COUNT_VETS).fetchone()[0]
    assert vets_after == vets_before, f"o total de veterinários deveria continuar {vets_before}, ficou {vets_after}"


def test_criar_veterinario_homonimo_grava_outro_sem_mudar_o_primeiro(api, db, prepared_vet, vets_to_delete):
    """CT-API-VETS-04: criar um veterinário com o mesmo nome e sobrenome de outro responde 201 com outro id, e
    o primeiro continua igual.

    Regra adotada: homônimos são permitidos, porque um veterinário é uma pessoa, não um item de catálogo como
    tipo e especialidade (BUG-14 e BUG-15)."""
    # Preparar: o primeiro veterinário foi gravado por SQL pela fixture; o envio repete o nome e o sobrenome
    existing_row = (PREPARED_VET["first_name"], PREPARED_VET["last_name"])
    payload = {"firstName": PREPARED_VET["first_name"], "lastName": PREPARED_VET["last_name"], "specialties": []}
    vets_before = db.execute(COUNT_VETS).fetchone()[0]

    # Agir
    response = api.post("/vets", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        vets_to_delete.append(body["id"])

    # Verificar a resposta: criado, com um id diferente do do veterinário existente
    assert response.status_code == 201, f"POST /vets de um homônimo deveria responder 201, respondeu {response.status_code}"
    assert body["id"] != prepared_vet, f"o homônimo deveria ter outro id, veio o mesmo do existente ({prepared_vet})"

    # Verificar o banco: um veterinário a mais, o novo gravado como enviado e o existente sem mudança
    vets_after = db.execute(COUNT_VETS).fetchone()[0]
    assert vets_after == vets_before + 1, f"o total de veterinários deveria subir para {vets_before + 1}, ficou {vets_after}"
    new_row = db.execute(SELECT_VET_BY_ID, (body["id"],)).fetchone()
    assert new_row == existing_row, f"o veterinário novo {body['id']} deveria ser {existing_row}, é {new_row}"
    row_after = db.execute(SELECT_VET_BY_ID, (prepared_vet,)).fetchone()
    assert row_after == existing_row, f"o veterinário existente {prepared_vet} deveria continuar {existing_row}, é {row_after}"


def test_criar_veterinario_com_especialidade_repetida_grava_uma_ligacao_so(api, db, prepared_specialty, vets_to_delete):
    """CT-API-VETS-05: criar um veterinário com a mesma especialidade duas vezes na lista responde 201 e grava
    uma ligação só com ela, porque a lista funciona como um conjunto.

    O banco recusaria a ligação repetida (regra UNIQUE em `vet_specialties`); o risco coberto é um 500 ou um
    veterinário gravado sem a ligação."""
    # Preparar: a especialidade da fixture aparece duas vezes na lista
    specialty = {"id": prepared_specialty, "name": PREPARED_SPECIALTY_NAME}
    payload = {**VET, "specialties": [specialty, dict(specialty)]}

    # Agir
    response = api.post("/vets", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        vets_to_delete.append(body["id"])

    # Verificar a resposta
    assert response.status_code == 201, f"POST /vets com especialidade repetida deveria responder 201, respondeu {response.status_code}"

    # Verificar o banco: o veterinário gravado e exatamente uma ligação, com a especialidade repetida
    row = db.execute(SELECT_VET_BY_ID, (body["id"],)).fetchone()
    expected = (payload["firstName"], payload["lastName"])
    assert row == expected, f"a linha do veterinário {body['id']} deveria ser {expected}, é {row}"
    links = db.execute(SELECT_SPECIALTY_IDS_BY_VET, (body["id"],)).fetchall()
    assert links == [(prepared_specialty,)], f"o veterinário {body['id']} deveria ter uma ligação só, com {prepared_specialty}; tem {links}"


# Veterinário de controle do CT-API-VETS-07: tem a especialidade A, como o veterinário atualizado, e tem de
# continuar com ela.
CONTROL_VET = {"first_name": "Marcos", "last_name": "Lima"}


@pytest.fixture
def control_vet(db):
    """Grava direto no banco o veterinário de controle (CONTROL_VET), sem especialidades, e entrega o id. No
    fim, apaga as ligações dele (um cenário pode ter acrescentado) e depois o veterinário; apagar zero linhas
    também serve.

    Quando o controle é ligado a especialidades de fixtures, peça esta fixture depois das de especialidade,
    para ele sair antes delas."""
    vet_id = db.execute(INSERT_VET, (CONTROL_VET["first_name"], CONTROL_VET["last_name"])).fetchone()[0]
    yield vet_id
    db.execute(DELETE_VET_SPECIALTIES_BY_VET, (vet_id,))
    db.execute(DELETE_VET, (vet_id,))


@pytest.fixture
def vet_with_a_and_b_and_control(db, prepared_specialty, second_specialty, third_specialty, prepared_vet, control_vet):
    """Liga por SQL o veterinário da fixture prepared_vet às especialidades A (prepared_specialty) e B
    (second_specialty), e o veterinário de controle (control_vet) a A. A terceira especialidade (C,
    third_specialty) fica sem veterinários. Entrega os ids.

    As ligações são apagadas pelas fixtures dos veterinários, que saem antes das especialidades, porque as
    fixtures são desmontadas na ordem inversa em que foram pedidas."""
    db.execute(INSERT_VET_SPECIALTY, (prepared_vet, prepared_specialty))
    db.execute(INSERT_VET_SPECIALTY, (prepared_vet, second_specialty))
    db.execute(INSERT_VET_SPECIALTY, (control_vet, prepared_specialty))
    yield {
        "vet_id": prepared_vet,
        "control_vet_id": control_vet,
        "a": prepared_specialty,
        "b": second_specialty,
        "c": third_specialty,
    }


def test_trocar_especialidades_do_veterinario_grava_exatamente_a_nova_lista(api, db, vet_with_a_and_b_and_control):
    """CT-API-VETS-07: o PUT de um veterinário com A e B trocando a lista para B e C responde 204 e deixa
    exatamente as ligações B e C. O veterinário de controle, que também tem A, continua com ela, e o total de
    ligações não muda (sai A, entra C)."""
    # Preparar: o cenário vem da fixture; o corpo repete o nome e traz a nova lista
    scenario = vet_with_a_and_b_and_control
    vet_id = scenario["vet_id"]
    payload = {
        "firstName": PREPARED_VET["first_name"],
        "lastName": PREPARED_VET["last_name"],
        "specialties": [
            {"id": scenario["b"], "name": SECOND_SPECIALTY_NAME},
            {"id": scenario["c"], "name": THIRD_SPECIALTY_NAME},
        ],
    }
    links_before = db.execute(COUNT_VET_SPECIALTIES).fetchone()[0]

    # Agir
    response = api.put(f"/vets/{vet_id}", json=payload)

    # Verificar a resposta
    assert response.status_code == 204, f"PUT /vets/{vet_id} deveria responder 204, respondeu {response.status_code}"

    # Verificar o banco: o veterinário tem exatamente B e C
    links = db.execute(SELECT_SPECIALTY_IDS_BY_VET, (vet_id,)).fetchall()
    expected_links = [(specialty_id,) for specialty_id in sorted((scenario["b"], scenario["c"]))]
    assert links == expected_links, f"o veterinário {vet_id} deveria ter exatamente as ligações {expected_links}, tem {links}"

    # o controle continua com A, e o total de ligações não muda
    control_links = db.execute(SELECT_SPECIALTY_IDS_BY_VET, (scenario["control_vet_id"],)).fetchall()
    assert control_links == [(scenario["a"],)], (
        f"o veterinário de controle {scenario['control_vet_id']} deveria continuar só com {scenario['a']}, tem {control_links}"
    )
    links_after = db.execute(COUNT_VET_SPECIALTIES).fetchone()[0]
    assert links_after == links_before, f"o total de ligações deveria continuar {links_before}, ficou {links_after}"


@pytest.fixture
def vet_with_specialty(db, prepared_specialty, prepared_vet):
    """Liga por SQL o veterinário da fixture prepared_vet à especialidade da prepared_specialty e entrega os
    dois ids. No fim, apaga as ligações do veterinário (zero também serve); o veterinário sai antes da
    especialidade, porque as fixtures são desmontadas na ordem inversa em que foram pedidas."""
    db.execute(INSERT_VET_SPECIALTY, (prepared_vet, prepared_specialty))
    yield {"vet_id": prepared_vet, "specialty_id": prepared_specialty}
    db.execute(DELETE_VET_SPECIALTIES_BY_VET, (prepared_vet,))


# Nome novo do CT-API-VETS-08: não existe no seed nem nas fixtures.
UPDATED_VET = {"firstName": "Beatriz", "lastName": "Rocha"}


def test_atualizar_nome_do_veterinario_grava_na_mesma_linha_e_mantem_a_ligacao(api, db, vet_with_specialty):
    """CT-API-VETS-08: o PUT de um veterinário com nome e sobrenome novos e a mesma especialidade responde 204,
    grava o nome novo na mesma linha, sem criar outro veterinário, e mantém a ligação com a especialidade.

    A lista precisa ir com a especialidade: o PUT troca a lista inteira (CT-API-VETS-07)."""
    # Preparar: o veterinário e a ligação vêm da fixture; aqui só o total antes
    vet_id = vet_with_specialty["vet_id"]
    specialty_id = vet_with_specialty["specialty_id"]
    payload = {**UPDATED_VET, "specialties": [{"id": specialty_id, "name": PREPARED_SPECIALTY_NAME}]}
    vets_before = db.execute(COUNT_VETS).fetchone()[0]

    # Agir
    response = api.put(f"/vets/{vet_id}", json=payload)

    # Verificar a resposta
    assert response.status_code == 204, f"PUT /vets/{vet_id} deveria responder 204, respondeu {response.status_code}"

    # Verificar o banco: a mesma linha com o nome novo, nenhum veterinário a mais e a ligação mantida
    row = db.execute(SELECT_VET_BY_ID, (vet_id,)).fetchone()
    expected = (payload["firstName"], payload["lastName"])
    assert row == expected, f"o veterinário {vet_id} deveria ser {expected}, é {row}"
    vets_after = db.execute(COUNT_VETS).fetchone()[0]
    assert vets_after == vets_before, f"o total de veterinários deveria continuar {vets_before}, ficou {vets_after}"
    links = db.execute(SELECT_SPECIALTY_IDS_BY_VET, (vet_id,)).fetchall()
    assert links == [(specialty_id,)], f"o veterinário {vet_id} deveria continuar ligado só a {specialty_id}, tem {links}"


def test_apagar_veterinario_sem_especialidade_remove_so_ele(api, db, prepared_vet, control_vet):
    """CT-API-VETS-09: apagar um veterinário sem especialidades responde 204 e remove só esse veterinário. O
    veterinário da fixture control_vet é o controle, e o total de ligações veterinário-especialidade também é
    conferido."""
    # Preparar: os dois veterinários, sem especialidades, vêm das fixtures; aqui só os totais antes
    vet_id = prepared_vet
    vets_before = db.execute(COUNT_VETS).fetchone()[0]
    links_before = db.execute(COUNT_VET_SPECIALTIES).fetchone()[0]

    # Agir
    response = api.delete(f"/vets/{vet_id}")

    # Verificar a resposta
    assert response.status_code == 204, f"DELETE /vets/{vet_id} deveria responder 204, respondeu {response.status_code}"

    # Verificar o banco: o veterinário não existe mais e saiu exatamente um
    assert db.execute(SELECT_VET_BY_ID, (vet_id,)).fetchone() is None, f"o veterinário {vet_id} não deveria mais existir"
    vets_after = db.execute(COUNT_VETS).fetchone()[0]
    assert vets_after == vets_before - 1, f"o total de veterinários deveria cair para {vets_before - 1}, ficou {vets_after}"

    # o controle continua igual e nenhuma ligação mudou
    control = db.execute(SELECT_VET_BY_ID, (control_vet,)).fetchone()
    expected_control = (CONTROL_VET["first_name"], CONTROL_VET["last_name"])
    assert control == expected_control, f"o veterinário de controle {control_vet} deveria continuar {expected_control}, é {control}"
    links_after = db.execute(COUNT_VET_SPECIALTIES).fetchone()[0]
    assert links_after == links_before, f"o total de ligações deveria continuar {links_before}, ficou {links_after}"
