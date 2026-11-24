"""Testes de especialidades (tabela `specialties`), com o banco como oráculo."""

# Especialidade padrão: o contrato só aceita letras, espaço, `-`, `&` e `/` no nome, então não há sufixo
# numérico. "dermatologia" não existe no populateDB.sql, e cada teste apaga a especialidade que criou.
SPECIALTY = {"name": "dermatologia"}

# Pergunta: qual é o nome gravado na linha de `specialties` com o id que a API devolveu no POST?
# Recebe o id (%s) e devolve uma linha com um valor só: o name. Se a especialidade não existir, não devolve
# linha.
SELECT_SPECIALTY_BY_ID = """
SELECT name FROM specialties WHERE id = %s;
"""


def test_criar_especialidade_com_nome_valido_grava_o_nome(api, db, specialties_to_delete):
    """CT-API-SPECIALTIES-01: criar uma especialidade com nome válido responde 201 e grava em `specialties` o
    nome enviado."""
    # Preparar
    payload = dict(SPECIALTY)

    # Agir
    response = api.post("/specialties", json=payload)
    body = response.json()
    if isinstance(body, dict) and "id" in body:
        specialties_to_delete.append(body["id"])

    # Verificar a resposta
    assert response.status_code == 201, f"POST /specialties deveria responder 201, respondeu {response.status_code}"

    # Verificar o banco: a linha do id devolvido tem o nome enviado
    row = db.execute(SELECT_SPECIALTY_BY_ID, (body["id"],)).fetchone()
    expected = (payload["name"],)
    assert row == expected, f"a linha da especialidade {body['id']} deveria ser {expected}, é {row}"
