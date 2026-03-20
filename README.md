# 📊 Sistema de Rotas e Regionais

Aplicação web para gerenciamento e análise de dados de rotas e regionais, construída com **Streamlit** e **SQLite**.

---

## Pré-requisitos

- **Python 3.10** ou superior
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

1. Na tela inicial, clique na aba **Cadastro** e crie uma conta de usuário.
2. Vá para a aba **Login** e entre com as credenciais criadas.
3. *(Opcional)* Coloque o arquivo `regionais.xlsx` na raiz do projeto — ele será carregado automaticamente. Caso contrário, faça o upload manual pela página **Home**.
4. Navegue até **Upload LEI3020** no menu lateral e envie o arquivo `LEI3020.xlsx` para importar os dados de rotas.

---

## Estrutura do Projeto

```
projeto/
├── app.py            # Aplicação principal — interface e roteamento de páginas
├── auth.py           # Autenticação e cadastro de usuários
├── database.py       # Gerenciamento do banco de dados SQLite
├── utils.py          # Leitura e exportação de arquivos Excel
├── requirements.txt  # Dependências do projeto
├── regionais.xlsx    # (opcional) Carregado automaticamente na inicialização
└── app.db            # Banco de dados gerado automaticamente na primeira execução
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

| Página             | Descrição                                                          |
|--------------------|--------------------------------------------------------------------|
| 🏠 Home            | Resumo de registros e upload manual de Regionais                   |
| 📤 Upload LEI3020  | Importação do arquivo de rotas (substitui dados anteriores)        |
| 📋 Visualização    | Consulta das tabelas com filtros e exportação CSV/Excel            |
| 📊 Análises        | Gráficos e tabelas dinâmicas de regionais e situação das rotas     |

---

## Banco de Dados

O banco de dados SQLite (`app.db`) é criado automaticamente na raiz do projeto na primeira execução. Nenhuma configuração adicional é necessária.

Tabelas criadas:

- **`usuarios`** — credenciais de acesso
- **`regionais`** — dados do arquivo `regionais.xlsx`
- **`rotas`** — dados do arquivo `LEI3020.xlsx`, vinculados a regionais

---

## Dependências

| Pacote      | Versão mínima | Finalidade                       |
|-------------|---------------|----------------------------------|
| streamlit   | 1.30.0        | Interface web                    |
| pandas      | 2.0.0         | Manipulação de dados             |
| openpyxl    | 3.1.0         | Leitura/escrita de arquivos xlsx |
| plotly      | 5.18.0        | Gráficos interativos             |

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
