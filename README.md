[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/KEr3YAoF)
[![Open in Codespaces](https://classroom.github.com/assets/launch-codespace-2972f46106e565e64193e422d61a12cf1da4916b45550586e14ef0a7c637dd04.svg)](https://classroom.github.com/open-in-codespaces?assignment_repo_id=23906985)

# Sistema de Gerenciamento de Eleições

prova da  disciplina de Programação e Administração de Banco de Dados (PABD) - TADS 4º Semestre.

## Funcionalidades

- Cadastro de eleitores, eleições e candidatos
- Gerenciamento do ciclo de eleição (abrir, encerrar, apurar)
- Votação com comprovante e QR Code
- Relatórios de apuração e auditoria de comparecimento
- API RESTful completa com documentação Swagger

## Instalação

1. Clone o repositório:
   ```bash
   git clone https://github.com/IFRN/tp2-desenvolvimento-de-api-rest-RamonCout0.git
   cd tp2-desenvolvimento-de-api-rest-RamonCout0
   ```

2. Crie e ative um ambiente virtual:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # ou
   source .venv/bin/activate  # Linux/Mac
   ```

3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

4. Execute as migrações:
   ```bash
   cd eleicoes_api
   python manage.py migrate
   ```

## Como Rodar

1. Inicie o servidor:
   ```bash
   python manage.py runserver
   ```

2. Acesse a API em `http://localhost:8000/`
3. Documentação Swagger: `http://localhost:8000/swagger/`
4. Documentação Redoc: `http://localhost:8000/redoc/`

## Endpoints Principais

### Eleitores
- `GET /eleicoes_api/eleitores/` - Listar eleitores
- `POST /eleicoes_api/eleitores/` - Criar eleitor

### Eleições
- `GET /eleicoes_api/eleicoes/` - Listar eleições
- `POST /eleicoes_api/eleicoes/` - Criar eleição
- `POST /eleicoes_api/eleicoes/{id}/abrir/` - Abrir eleição
- `POST /eleicoes_api/eleicoes/{id}/encerrar/` - Encerrar eleição
- `GET /eleicoes_api/eleicoes/{id}/apuracao/` - Apurar resultados
- `GET /eleicoes_api/eleicoes/{id}/votantes/` - Listar votantes
- `POST /eleicoes_api/eleicoes/{id}/votar/` - Registrar voto
- `POST /eleicoes_api/eleicoes/{id}/cadastrar-aptos/` - Cadastrar aptos em lote

### Candidatos
- `GET /eleicoes_api/candidatos/` - Listar candidatos
- `POST /eleicoes_api/candidatos/` - Criar candidato

### Comprovantes
- `GET /eleicoes_api/verificar-comprovante/?token=<TOKEN>` - Verificar comprovante
- `GET /eleicoes_api/comprovantes/qr/?token=<TOKEN>` - Gerar QR Code
