"""Testes de donos (tabela `owners`), com o banco como oráculo."""

# Dono padrão do docs/casos-de-teste.md: nome e sobrenome só com letras, telefone com 10 dígitos.
OWNER = {
    "firstName": "Clara",
    "lastName": "Lima",
    "address": "Rua do Sol, 30",
    "city": "Olinda",
    "telephone": "8199990002",
}

# Pergunta: qual é a linha de `owners` com o id que a API devolveu no POST?
# A consulta deve trazer, nesta ordem, first_name, last_name, address, city e telephone,
# e receber o id como parâmetro (%s), sem montar o texto da consulta com o valor.
SELECT_OWNER_BY_ID = """ 
SELECT first_name, last_name, address, city, telephone FROM owners WHERE id = %s;
  """

def test_criar_dono_com_dados_validos_grava_os_dados_enviados(api, db, owners_to_delete):
    """CT-API-OWNERS-01: criar um dono com dados válidos grava no banco exatamente os dados enviados."""
    # Agir
    response = api.post("/owners", json=OWNER)
    body = response.json()
    # Registra o dono na limpeza antes de qualquer verificação: se uma delas falhar, ele é apagado mesmo assim
    if isinstance(body, dict) and "id" in body:
        owners_to_delete.append(body["id"])

    # Verificar a resposta
    assert response.status_code == 201, f"POST /owners deveria responder 201, respondeu {response.status_code}"
    assert isinstance(body.get("id"), int), "a resposta deveria trazer o id numérico do dono criado"
    assert {field: body[field] for field in OWNER} == OWNER, "a resposta deveria trazer os campos enviados"

    # Verificar o banco: o esperado vem do que foi enviado, não da resposta da API
    row = db.execute(SELECT_OWNER_BY_ID, (body["id"],)).fetchone()
    assert row is not None, f"o banco deveria ter uma linha em owners com id {body['id']}"
    expected = (OWNER["firstName"], OWNER["lastName"], OWNER["address"], OWNER["city"], OWNER["telephone"])
    assert row == expected, f"a linha gravada deveria ser {expected}, é {row}"
