# AGENT.md

## 1. Arquitetura

O projeto será uma **REST API desenvolvida em Python com FastAPI**, seguindo uma arquitetura modular e separação de responsabilidades.

Estrutura de referência:

```text
project/
├── app/
│   ├── main.py
│   ├── core/
│   │   └── config.py
│   ├── api/
│   │   └── routes/
│   ├── clients/
│   ├── services/
│   ├── parsers/
│   └── schemas/
├── tests/
├── .env
├── .env.example
├── .gitignore
├── pyproject.toml
├── AGENT.md
```

**Responsabilidades:**
- `api/routes/`: endpoints HTTP e validação de parâmetros.
- `clients/`: comunicação com serviços externos.
- `services/`: regras de negócio e orquestração.
- `parsers/`: extração e transformação de dados.
- `schemas/`: modelos Pydantic de entrada e saída.
- `core/`: configurações e componentes compartilhados.
- `tests/`: testes automatizados com pytest.

Evitar lógica de negócio diretamente nas rotas.

## 2. Padrões de código

- Utilizar **Python 3.12+**.
- Aplicar **type hints** em todas as funções, métodos, parâmetros e retornos.
- Utilizar **docstrings em português brasileiro (pt-BR)** para módulos, classes e funções públicas.
- Manter nomes de variáveis, funções, classes e arquivos em inglês, seguindo PEP 8.
- Preferir funções pequenas, coesas e com responsabilidade única.
- Utilizar Pydantic v2 para contratos e validação de dados.
- Utilizar `async/await` para operações de I/O assíncronas.
- Utilizar `logging` em vez de `print`.
- Tratar erros explicitamente, sem suprimir exceções silenciosamente.
- Criar testes com pytest para funcionalidades e correções relevantes.

## 3. FastAPI

- Utilizar `APIRouter` para organizar endpoints.
- Utilizar injeção de dependências com `Depends` quando apropriado.
- Declarar `response_model` nas rotas.
- Retornar códigos HTTP adequados.
- Padronizar respostas de erro em JSON.
- Disponibilizar documentação automática em `/docs` e `/openapi.json`.
- Manter a API acessível em `127.0.0.1` por padrão.

## 4. Configuração e variáveis de ambiente

Centralizar as configurações em `app/core/config.py`, utilizando `pydantic-settings`.

Criar `.env.example` com as seguintes variáveis:

```dotenv
# LinkedIn
LINKEDIN_LI_AT=
LINKEDIN_JSESSIONID=
LINKEDIN_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36

# HTTP
HTTP_TIMEOUT_SECONDS=30

# Cache
CACHE_BACKEND=sqlite
CACHE_SQLITE_PATH=./data/jobs_cache.db
```

Regras:
- Criar `.env` a partir de `.env.example`, preservando configurações existentes.
- Nunca inventar credenciais ou inserir valores reais no código.
- Nunca versionar `.env` ou registrar tokens e cookies em logs.
- Versionar somente `.env.example`, sem segredos.
- Validar configurações obrigatórias na inicialização ou antes de utilizar a integração correspondente.

## 5. Qualidade e manutenção

- Priorizar simplicidade, legibilidade e manutenção.
- Evitar abstrações prematuras e dependências desnecessárias.
- Manter módulos desacoplados e testáveis.
- Não misturar comunicação HTTP, parsing e regras de negócio.
- Utilizar `ruff` para lint e formatação.
- Garantir que alterações não quebrem contratos públicos nem testes existentes.
