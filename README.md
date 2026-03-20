# 📊 Sistema de Rotas e Regionais

Aplicação web para gerenciamento e análise de dados de rotas e regionais, construída com **Streamlit** e **SQLite**.

---

## Deploy no Streamlit Community Cloud

### 1. Suba o projeto para um repositório GitHub

```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/<seu-usuario>/<seu-repo>.git
git push -u origin main
```

> **Importante:** o arquivo `app.db` é gerado automaticamente na inicialização e está no `.gitignore`. Não é necessário (nem recomendado) enviá-lo para o repositório.

### 2. Crie o app no Streamlit Community Cloud

1. Acesse [share.streamlit.io](https://share.streamlit.io) e faça login com sua conta GitHub.
2. Clique em **New app**.
3. Selecione o repositório e o arquivo principal: `app.py`.
4. Clique em **Deploy**.

### 3. Configure o Secret da senha master (opcional)

Por padrão o usuário master é criado com a senha `Master@2026`.  
Para usar uma senha personalizada:

1. No painel do app, clique em **⚙️ Settings → Secrets**.
2. Adicione:
   ```toml
   MASTER_PASSWORD = "SuaSenhaMaisFortePossivel"
   ```
3. Salve e o app reiniciará com a nova senha.

> **Atenção sobre persistência de dados:** O Streamlit Community Cloud usa sistema de arquivos efêmero — o banco de dados SQLite (`app.db`) é recriado do zero a cada reinício do servidor (após inatividade ou novo deploy). Por esse motivo, recomenda-se refazer o upload dos dados após cada reativação do app.

---

## Execução local

## Pré-requisitos

- **Python 3.11** ou superior
- **pip** (gerenciador de pacotes do Python)

---

## Instalação

### 1. Clone ou baixe o projeto

```bash
git clone <url-do-repositorio>
cd projeto
```

Ou extraia o `.zip` do projeto e navegue até a pasta.

### 2. Crie e ative um ambiente virtual (recomendado)

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

---

## Como executar

```bash
streamlit run app.py
```

A aplicação abrirá automaticamente no navegador em: **http://localhost:8501**

---

## Primeira Execução

1. Faça login com o usuário **master** (senha padrão: `Master@2026`).
2. No painel **Admin**, crie contas adicionais de usuário se necessário.
3. *(Opcional)* Coloque o arquivo `regionais.xlsx` na raiz do projeto — ele será carregado automaticamente. Caso contrário, faça o upload manual pela página **Home**.
4. Navegue até **Upload LEI3020** no menu lateral, selecione um **grupo** e envie o arquivo `LEI3020.xlsx` para importar os dados de rotas.

---

## Estrutura do Projeto

```
projeto/
├── app.py                  # Aplicação principal — interface e roteamento de páginas
├── auth.py                 # Autenticação e cadastro de usuários
├── database.py             # Gerenciamento do banco de dados SQLite
├── utils.py                # Leitura e exportação de arquivos Excel
├── requirements.txt        # Dependências do projeto
├── runtime.txt             # Versão do Python (para Streamlit Cloud)
├── .streamlit/
│   └── config.toml         # Configurações do Streamlit
└── app.db                  # Banco de dados (gerado automaticamente, não commitado)
```

---

## Arquivos de Dados

### `regionais.xlsx` (carregamento automático ou upload manual)

Coloque na raiz do projeto para carregamento automático ao iniciar.
Colunas esperadas (flexível — colunas extras são importadas dinamicamente):

| Coluna          | Descrição                        |
|-----------------|----------------------------------|
| US              | Identificador da unidade de serviço |
| DIRETORIA       | Diretoria responsável            |
| MACRO           | Macrorregião                     |
| MICRO           | Microrregião                     |
| MUNICIPIO       | Município                        |
| CIDADE          | Cidade                           |
| TOTAL_UC        | Total de unidades consumidoras   |
| COM_MEDICAO     | UCs com medição                  |
| SEM_MEDICAO     | UCs sem medição                  |
| FALTAM_VISITAR  | UCs a visitar                    |

### `LEI3020.xlsx` (upload via interface)

Enviado pela página **Upload LEI3020** dentro da aplicação.  
Coluna obrigatória: **`ZONA`** — usada para vincular rotas às regionais. Demais colunas são importadas dinamicamente.

---

## Páginas da Aplicação

| Página | Descrição |
|---|---|
| 📊 Dashboard Público | Visível sem login — mostra grupos e pendências por cidade |
| 🏠 Home | Resumo de registros e upload manual de Regionais |
| 📤 Upload LEI3020 | Importação do arquivo de rotas com seleção de grupo |
| 📋 Visualização | Consulta das tabelas com filtros e exportação CSV/Excel |
| 📊 Análises | Gráficos: por região, situação, resumo e faltam visitar |
| ⚙️ Admin | Gerenciamento de usuários, rotas e regionais (master only) |

---

## Banco de Dados

O banco de dados SQLite (`app.db`) é criado automaticamente na raiz do projeto na primeira execução. Nenhuma configuração adicional é necessária.

Tabelas criadas:

- **`usuarios`** — credenciais de acesso (`is_master` distingue admins)
- **`regionais`** — dados do arquivo `regionais.xlsx`
- **`rotas`** — dados do arquivo `LEI3020.xlsx`, vinculados a regionais, organizados por `grupo`

---

## Dependências

| Pacote | Versão mínima | Finalidade |
|---|---|---|
| streamlit | 1.30.0 | Interface web |
| pandas | 2.0.0 | Manipulação de dados |
| openpyxl | 3.1.0 | Leitura/escrita de arquivos xlsx |
| plotly | 5.18.0 | Gráficos interativos |

---

## Solução de Problemas

**`streamlit: command not found`**  
→ Verifique se o ambiente virtual está ativo e as dependências instaladas.

**`ModuleNotFoundError`**  
→ Execute `pip install -r requirements.txt` novamente com o ambiente virtual ativado.

**Arquivo `regionais.xlsx` não encontrado**  
→ Coloque o arquivo na mesma pasta que `app.py`, ou faça o upload manual pela página Home após o login.

**Porta 8501 já em uso**  
→ Execute com uma porta alternativa:
```bash
streamlit run app.py --server.port 8502
```
