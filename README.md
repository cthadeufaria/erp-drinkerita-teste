# ERP Protótipo Web

Protótipo ERP web simples em `Flask + SQLite + Bootstrap`, com módulos de clientes, produtos, estoque, vendas e financeiro básico. A aplicação roda localmente, sem depender de banco externo ou outros serviços.

## Pré-requisitos

- Python 3.10+ instalado
- `pip` disponível no terminal

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Execução local

```bash
python app.py
```

Ao subir, o Flask ficará escutando em `0.0.0.0` na porta `5000` por padrão.

## Acesso no navegador

- Localhost: `http://127.0.0.1:5000`
- Mesmo computador: `http://localhost:5000`
- LAN/exemplo de rede local: `http://192.168.0.10:5000`

Se quiser outra porta, defina a variável `PORT` antes de executar:

```bash
PORT=8000 python app.py
```

## Credenciais demo

- `carlos` / `demo` -> perfil `admin`
- `clawdinha` / `demo` -> perfil `financeiro`
- `donaluci` / `demo` -> perfil `financeiro`

## O que o protótipo entrega

- Login com sessão usando usuários seed
- Dashboard com KPIs básicos
- CRUD de clientes
- CRUD de produtos
- Controle simples de estoque com movimentações
- Registro de vendas com baixa de estoque
- Financeiro básico com contas a receber e a pagar
- Seed automático com dados de demonstração
- Formatação BR para moeda (`R$`) e datas (`dd/mm/aaaa`)

## Banco de dados

O arquivo SQLite `erp.db` é criado automaticamente na primeira execução. O seed inicial também roda automaticamente apenas quando o banco ainda não possui usuários.

## Arquivos criados

- `app.py`: aplicação principal Flask, rotas, autenticação, schema SQLite e seed inicial
- `templates/base.html`: layout principal com navegação Bootstrap
- `templates/login.html`: tela de login
- `templates/dashboard.html`: dashboard com KPIs e resumos
- `templates/clients/`: telas de listagem e formulário de clientes
- `templates/products/`: telas de listagem e formulário de produtos
- `templates/stock/list.html`: visão de estoque e formulário de movimentação
- `templates/sales/`: telas de listagem e criação de vendas
- `templates/finance/`: telas de listagem e formulário financeiro
- `static/style.css`: pequenos ajustes visuais
- `requirements.txt`: dependências Python do projeto
- `erp.db`: banco SQLite gerado automaticamente em runtime
