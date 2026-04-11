import streamlit as st
import pandas as pd
import plotly.express as px
import os

from database import init_db, insert_regionais, insert_rotas, regionais_is_empty, rotas_is_empty
from database import query_regionais, query_rotas, query_rotas_joined, query_analitico_faltam, query_grupos, clear_table, get_table_counts
from database import get_all_users, is_master_user, delete_user, save_rotas_admin, save_regionais_admin
from auth import register_user, authenticate_user, ensure_master_user, change_user_password
from utils import load_regionais_excel, load_lei_excel, dataframe_to_csv, dataframe_to_excel, REGIONAIS_FILE

# ── Configuração da página ──────────────────────────────────────────────────
st.set_page_config(page_title="Sistema de Rotas e Regionais", layout="wide", page_icon="")

# ── Inicializar banco de dados ──────────────────────────────────────────────
init_db()
ensure_master_user()
# ── Session state defaults ──────────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "page" not in st.session_state:
    st.session_state.page = "Home"
if "is_master" not in st.session_state:
    st.session_state.is_master = False


# ═══════════════════════════════════════════════════════════════════════════
# AUTENTICAÇÃO
# ═══════════════════════════════════════════════════════════════════════════

def _render_login_sidebar():
    """Login compacto na sidebar para usuários não autenticados."""
    with st.sidebar:
        st.markdown("## 🔐 Login")
        with st.form("login_form_sidebar", clear_on_submit=False):
            username = st.text_input("Usuário", key="sb_user")
            password = st.text_input("Senha", type="password", key="sb_pwd")
            submitted = st.form_submit_button("Entrar", use_container_width=True, type="primary")
            if submitted:
                ok, msg = authenticate_user(username, password)
                if ok:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.is_master = is_master_user(username)
                    st.rerun()
                else:
                    st.error(msg)


def show_login():
    st.title("🔐 Login")
    with st.form("login_form"):
        username = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar")
        if submitted:
            ok, msg = authenticate_user(username, password)
            if ok:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.is_master = is_master_user(username)
                st.rerun()
            else:
                st.error(msg)


def show_auth_page():
    show_login()


# ═══════════════════════════════════════════════════════════════════════════
# DASHBOARD PÚBLICO
# ═══════════════════════════════════════════════════════════════════════════

def page_public():
    """Dashboard público visível sem login."""
    st.title(" Painel de Rotas")
    st.caption("Visualização pública — faça login na barra lateral para acessar o sistema completo.")

    df = query_rotas_joined()

    if df.empty:
        st.info("⚠️ Nenhum dado disponível no momento.")
        return

    # ── Detecta colunas dinâmicas ───────────────────────────────────────────
    situacao_col = next((c for c in df.columns if "situa" in c.lower()), None)
    faltam_col   = next((c for c in df.columns if c.upper() == "FALTAM_VISITAR"), None)
    rota_col     = next((c for c in df.columns if c.upper() == "ROTA"), None)
    zona_col     = next((c for c in df.columns if c.upper() == "ZONA"), None)
    cidade_col   = next((c for c in df.columns if c.upper() == "CIDADE"), None)

    if cidade_col is None or rota_col is None:
        st.info("⚠️ Dados incompletos — faça o upload do LEI3020 e do arquivo Regionais.")
        return

    if faltam_col:
        df[faltam_col] = pd.to_numeric(df[faltam_col], errors="coerce").fillna(0)

    macro_col = next((c for c in df.columns if c.upper() == "MACRO"), None)
    micro_col = next((c for c in df.columns if c.upper() == "MICRO"), None)

    # ── Filtros por MACRO e MICRO ──────────────────────────────────────────
    with st.expander("🔍 Filtros", expanded=False):
        fcol1, fcol2 = st.columns(2)
        with fcol1:
            if macro_col and df[macro_col].dropna().nunique() > 0:
                macros_disp = sorted(df[macro_col].dropna().unique().tolist())
                macros_sel = st.multiselect("🗺️ MACRO:", macros_disp, key="pub_macro_sel")
                if macros_sel:
                    df = df[df[macro_col].isin(macros_sel)]
            else:
                st.caption("Coluna MACRO não disponível.")
        with fcol2:
            if micro_col and df[micro_col].dropna().nunique() > 0:
                micros_disp = sorted(df[micro_col].dropna().unique().tolist())
                micros_sel = st.multiselect("📍 MICRO:", micros_disp, key="pub_micro_sel")
                if micros_sel:
                    df = df[df[micro_col].isin(micros_sel)]
            else:
                st.caption("Coluna MICRO não disponível.")

    def _is_agendado(val):
        return "AGENDAD" in str(val).upper()

    n_agendado    = int(df[situacao_col].apply(_is_agendado).sum()) if situacao_col else 0
    total_faltam  = int(df[faltam_col].sum()) if faltam_col else 0
    total_cidades = df[cidade_col].nunique()
    total_rotas   = len(df)

    # ── KPIs ───────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🏙️ Cidades",             total_cidades)
    c2.metric("🛣️ Total de Rotas",       total_rotas)
    c3.metric("📍 Total Faltam Visitar",  f"{total_faltam:,}".replace(",", "."))
    c4.metric("📅 Rotas Agendadas",      n_agendado)

    st.divider()

    # ── Colunas a exibir por rota (cidade como coluna na linha) ────────────
    desired = [cidade_col, zona_col, rota_col, faltam_col, situacao_col,
               "SUPERVISOR_COMERCIAL", "ENCARREGADO_COMERCIAL"]
    cols_rota = [c for c in desired if c and c in df.columns]

    # ── Highlight: somente linhas AGENDADO ficam amarelas ──────────────────
    def _highlight_row(row):
        if situacao_col and _is_agendado(row.get(situacao_col, "")):
            return ["background-color: #FFF3CD; color: #856404; font-weight: bold"] * len(row)
        return [""] * len(row)

    # ── Um expander por grupo ──────────────────────────────────────────────
    grupos = sorted(df["grupo"].dropna().unique().tolist()) if "grupo" in df.columns else ["(sem grupo)"]

    for grupo in grupos:
        df_g = df[df["grupo"] == grupo].copy() if "grupo" in df.columns else df.copy()

        total_g   = int(df_g[faltam_col].sum()) if faltam_col else 0
        n_ag_g    = int(df_g[situacao_col].apply(_is_agendado).sum()) if situacao_col else 0
        cidades_g = df_g[cidade_col].nunique()

        badge = f"  |  📅 {n_ag_g} agendada(s)" if n_ag_g > 0 else ""
        label = (
            f"📦 {grupo}  —  {cidades_g} cidade(s)  |  "
            f"Faltam Visitar: {total_g:,}{badge}"
        ).replace(",", ".")

        df_show = df_g[cols_rota].copy()
        if faltam_col and faltam_col in df_show.columns:
            df_show = df_show.sort_values([cidade_col, faltam_col], ascending=[True, False])

        with st.expander(label, expanded=(n_ag_g > 0)):
            st.dataframe(
                df_show.style.apply(_highlight_row, axis=1),
                use_container_width=True,
                hide_index=True,
            )


# ═══════════════════════════════════════════════════════════════════════════
# CARREGAMENTO INICIAL DE REGIONAIS
# ═══════════════════════════════════════════════════════════════════════════

def ensure_regionais():
    """Load REGIONAIS.xlsx automatically if table is empty."""
    if not regionais_is_empty():
        return

    if os.path.isfile(REGIONAIS_FILE):
        try:
            df = load_regionais_excel()
            insert_regionais(df)
            st.toast(f"✅ Regionais carregadas automaticamente ({len(df)} registros).")
        except Exception as e:
            st.warning(f"Erro ao carregar regionais.xlsx automaticamente: {e}")
    else:
        st.warning(
            "⚠️ Arquivo regionais.xlsx não encontrado no diretório do projeto. "
            "Utilize a opção de upload manual na página Home."
        )


# ═══════════════════════════════════════════════════════════════════════════
# PÁGINAS
# ═══════════════════════════════════════════════════════════════════════════

def page_home():
    st.title("🏠 Página Inicial")
    st.markdown(f"Bem-vindo, **{st.session_state.username}**!")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Registros em Regionais", len(query_regionais()))
    with col2:
        st.metric("Registros em Rotas", len(query_rotas()))

    # Upload de regionais (sempre disponível)
    with st.expander("📥 Importar Regionais via Excel", expanded=regionais_is_empty()):
        if not regionais_is_empty():
            st.warning("⚠️ O upload irá **substituir** todos os dados existentes de Regionais.")
        uploaded = st.file_uploader("Envie o arquivo Regionais (.xlsx)", type=["xlsx"], key="reg_upload")
        if uploaded is not None:
            try:
                df_reg = load_regionais_excel(uploaded)
                st.info(f"Arquivo lido: **{len(df_reg)}** linhas, **{len(df_reg.columns)}** colunas.")
                st.dataframe(df_reg.head(5), use_container_width=True)
                if st.button("✅ Confirmar importação", type="primary", key="reg_confirm_import"):
                    insert_regionais(df_reg)
                    st.success(f"✅ Regionais importadas com sucesso! ({len(df_reg)} registros)")
                    st.rerun()
            except Exception as e:
                st.error(f"Erro ao processar o arquivo: {e}")


def page_upload():
    st.title("📤 Upload do Arquivo LEI3020")
    st.markdown(
        "Envie o arquivo de rotas (ex: **GF 01.xlsx**, **GF 02.xlsx**). "
        "O nome do grupo será detectado automaticamente pelo nome do arquivo. "
        "Se o grupo já existir, os dados dele serão **substituídos**. "
        "Grupos diferentes coexistem no banco."
    )

    grupos_existentes = query_grupos()

    uploaded = st.file_uploader(
        "Selecione o arquivo de rotas (.xlsx)",
        type=["xlsx"],
        key="lei_upload",
        help="O nome do grupo será extraído automaticamente do nome do arquivo.",
    )

    if uploaded is not None:
        # Extrai o nome do arquivo sem extensão como grupo padrão
        nome_arquivo = os.path.splitext(uploaded.name)[0].strip()

        grupo = st.text_input(
            "Nome do grupo:",
            value=nome_arquivo,
            key="grupo_nome",
            help="Detectado pelo nome do arquivo. Edite se necessário.",
        ).strip()

        if grupos_existentes:
            st.caption(
                "Grupos existentes: " + ", ".join(f"**{g}**" for g in grupos_existentes)
            )

        if not grupo:
            st.warning("⚠️ O nome do grupo não pode ser vazio.")
        else:
            df, msg = load_lei_excel(uploaded)
            if df is None:
                st.error(msg)
            else:
                status = "será atualizado" if grupo in grupos_existentes else "novo grupo"
                st.info(
                    f"Arquivo: **{uploaded.name}** — {len(df)} linhas, {len(df.columns)} colunas.  "
                    f"Grupo: **{grupo}** ({status})"
                )
                st.dataframe(df.head(10), use_container_width=True)

                if st.button("Confirmar Upload", type="primary"):
                    with st.spinner("Processando..."):
                        inserted, skipped, skipped_zonas = insert_rotas(df, zona_col="ZONA", grupo=grupo)

                    st.success(f"✅ Upload concluído! **{inserted}** registros inseridos no grupo **{grupo}**.")
                    if skipped_zonas:
                        st.warning(
                            f"⚠️ {len(skipped_zonas)} ZONA(s) não encontrada(s) em Regionais "
                            f"(us_id definido como NULL): {', '.join(sorted(skipped_zonas)[:20])}"
                        )


def page_visualizacao():
    st.title("📋 Visualização de Dados")

    view_option = st.radio(
        "Selecione a tabela:",
        ["Rotas", "Regionais", "Dados Combinados (JOIN)"],
        horizontal=True,
    )

    if view_option == "Rotas":
        df = query_rotas()
        if df.empty:
            st.info("Nenhum dado na tabela Rotas. Faça o upload do arquivo LEI3020.")
            return
        st.subheader(f"Tabela Rotas ({len(df)} registros)")
    elif view_option == "Regionais":
        df = query_regionais()
        if df.empty:
            st.info("Nenhum dado na tabela Regionais.")
            return
        st.subheader(f"Tabela Regionais ({len(df)} registros)")
    else:
        df = query_rotas_joined()
        if df.empty:
            st.info("Nenhum dado disponível para a junção.")
            return
        st.subheader(f"Dados Combinados ({len(df)} registros)")

    # Filters
    with st.expander("🔍 Filtros", expanded=False):
        filter_cols = st.multiselect("Filtrar por colunas:", df.columns.tolist())
        for col in filter_cols:
            unique_vals = df[col].dropna().unique().tolist()
            if len(unique_vals) <= 100:
                selected = st.multiselect(f"Valores de **{col}**:", unique_vals, key=f"filter_{col}")
                if selected:
                    df = df[df[col].isin(selected)]
            else:
                text_filter = st.text_input(f"Buscar em **{col}**:", key=f"text_{col}")
                if text_filter:
                    df = df[df[col].astype(str).str.contains(text_filter, case=False, na=False)]

    st.dataframe(df, use_container_width=True, height=500)

    # Export
    st.subheader("📥 Exportar Dados")
    col_csv, col_xlsx = st.columns(2)
    with col_csv:
        st.download_button(
            "⬇️ Baixar CSV",
            data=dataframe_to_csv(df),
            file_name="dados_exportados.csv",
            mime="text/csv",
        )
    with col_xlsx:
        st.download_button(
            "⬇️ Baixar Excel",
            data=dataframe_to_excel(df),
            file_name="dados_exportados.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def page_analises():
    st.title("📊 Análises e Relatórios")

    df_regionais = query_regionais()
    df_rotas = query_rotas()
    df_joined = query_rotas_joined()

    if df_rotas.empty and df_regionais.empty:
        st.info("Carregue os dados de Regionais e Rotas para visualizar análises.")
        return

    tab1, tab2, tab3, tab4 = st.tabs([
        " Por Região",
        " Situação das Rotas",
        " Resumo Regionais",
        " Faltam Visitar",
    ])

    # ── Tab 1: Análises por Região ──────────────────────────────────────────
    with tab1:
        if df_regionais.empty:
            st.info("Sem dados de Regionais.")
        else:
            st.subheader("Totais das rotas por agrupamento regional")
            group_col = st.selectbox(
                "Agrupar por:",
                [c for c in ["DIRETORIA", "MACRO", "MICRO", "CIDADE"] if c in df_regionais.columns],
                key="group_region",
            )

            # Métricas numéricas vêm de rotas (via JOIN: ZONA = US)
            rotas_numeric = [c for c in df_joined.columns if c in ("COM_MEDIÇÃO", "SEM_MEDIÇÃO", "FALTAM_VISITAR")]
            if not df_joined.empty and group_col and group_col in df_joined.columns and rotas_numeric:
                for nc in rotas_numeric:
                    df_joined[nc] = pd.to_numeric(df_joined[nc], errors="coerce").fillna(0)

                grouped = df_joined.groupby(group_col)[rotas_numeric].sum().reset_index()
                st.dataframe(grouped, use_container_width=True)

                metric_col = st.selectbox("Métrica para gráfico:", rotas_numeric, key="metric_region")
                fig = px.bar(
                    grouped.sort_values(metric_col, ascending=False).head(20),
                    x=group_col,
                    y=metric_col,
                    title=f"{metric_col} por {group_col} (Top 20)",
                    color=metric_col,
                    color_continuous_scale="Blues",
                )
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)

                # Pizza
                if len(grouped) <= 15:
                    fig_pie = px.pie(
                        grouped,
                        names=group_col,
                        values=metric_col,
                        title=f"Distribuição de {metric_col} por {group_col}",
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("Faça o upload do LEI3020 para visualizar totais por região.")

    # ── Tab 2: Situação das Rotas ───────────────────────────────────────────
    with tab2:
        if df_rotas.empty:
            st.info("Sem dados de Rotas. Faça o upload do LEI3020.xlsx.")
        else:
            situacao_col = None
            for candidate in ["SITUAÇÃO", "SITUACAO", "Situação", "Situacao", "situacao", "situação"]:
                if candidate in df_rotas.columns:
                    situacao_col = candidate
                    break

            if situacao_col is None:
                # Try partial match
                for c in df_rotas.columns:
                    if "situa" in c.lower():
                        situacao_col = c
                        break

            if situacao_col:
                st.subheader(f"Registros por {situacao_col}")
                sit_counts = df_rotas[situacao_col].value_counts().reset_index()
                sit_counts.columns = [situacao_col, "Quantidade"]
                st.dataframe(sit_counts, use_container_width=True)

                fig_bar = px.bar(
                    sit_counts,
                    x=situacao_col,
                    y="Quantidade",
                    title=f"Quantidade de registros por {situacao_col}",
                    color=situacao_col,
                )
                st.plotly_chart(fig_bar, use_container_width=True)

                fig_pie = px.pie(
                    sit_counts,
                    names=situacao_col,
                    values="Quantidade",
                    title=f"Proporção por {situacao_col}",
                )
                st.plotly_chart(fig_pie, use_container_width=True)

                # ── Destaque: Rotas Agendadas ──────────────────────────────
                st.divider()
                st.subheader(" Rotas Agendadas")

                df_agendado = df_rotas[
                    df_rotas[situacao_col].astype(str).str.upper().str.contains("AGENDAD", na=False)
                ]
                total_agendado = len(df_agendado)

                if total_agendado == 0:
                    st.info("Nenhuma rota com situação 'AGENDADO' encontrada.")
                else:
                    st.metric(" Total de Rotas Agendadas", total_agendado)

                    cols_show = [c for c in df_agendado.columns if c not in ("id", "us_id", "data_upload")]

                    def _highlight_agendado(row):
                        return ["background-color: #FFF3CD; color: #856404"] * len(row)

                    styled = df_agendado[cols_show].style.apply(_highlight_agendado, axis=1)
                    st.dataframe(styled, use_container_width=True, height=400)

                    col_csv, col_xlsx = st.columns(2)
                    with col_csv:
                        st.download_button(
                            "⬇️ Baixar CSV (Agendadas)",
                            data=dataframe_to_csv(df_agendado[cols_show]),
                            file_name="rotas_agendadas.csv",
                            mime="text/csv",
                            key="dl_agendado_csv",
                        )
                    with col_xlsx:
                        st.download_button(
                            "⬇️ Baixar Excel (Agendadas)",
                            data=dataframe_to_excel(df_agendado[cols_show]),
                            file_name="rotas_agendadas.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_agendado_xlsx",
                        )
            else:
                st.warning("Coluna de Situação não encontrada nos dados de Rotas.")

                # Show available columns for user reference
                st.write("Colunas disponíveis:", list(df_rotas.columns))

    # ── Tab 3: Resumo Regionais ─────────────────────────────────────────────
    with tab3:
        if df_regionais.empty:
            st.info("Sem dados de Regionais.")
        else:
            st.subheader("Contatos e Supervisores por Regional")
            contact_cols = [c for c in [
                "DIRETORIA", "MACRO", "MICRO", "CIDADE", "US",
                "GERENTE_MACRO", "CONTATO_GERENTES",
                "COORDENADOR", "CONTATO_COORDENADOR",
                "SUPERVISOR_COMERCIAL", "CONTATO_SUPERVISOR_COMERCIAL",
                "ENCARREGADO_COMERCIAL", "CONTATO_ENCARREGADO_COMERCIAL",
                "SUPERVISOR_OPERACIONAL",
                "SUPERVISOR_SERVIÇOS", "CONTATO_DO_SUPERVISOR_DE_SERVIÇOS",
            ] if c in df_regionais.columns]

            if contact_cols:
                search = st.text_input("🔍 Buscar (cidade, US, nome...):", key="tab3_search")
                df_show = df_regionais[contact_cols].copy()
                if search:
                    mask = df_show.apply(
                        lambda col: col.astype(str).str.contains(search, case=False, na=False)
                    ).any(axis=1)
                    df_show = df_show[mask]
                st.dataframe(df_show, use_container_width=True, height=450)
            else:
                st.warning("Colunas de contato não encontradas em Regionais.")

    # ── Tab 4: Analítico Faltam Visitar ────────────────────────────────────
    with tab4:
        df_analitico = query_analitico_faltam()

        if df_analitico.empty or df_analitico["FALTAM_VISITAR"].isna().all():
            st.info("Sem dados de rotas ou regionais. Faça o upload do LEI3020 e do arquivo Regionais.")
        else:
            df_analitico["FALTAM_VISITAR"] = pd.to_numeric(df_analitico["FALTAM_VISITAR"], errors="coerce").fillna(0)

            # ── Filtro por Grupo ──────────────────────────────────────────
            grupos_disp = sorted(df_analitico["grupo"].dropna().unique().tolist())
            grupo_sel = st.multiselect(
                " Filtrar por Grupo:",
                grupos_disp,
                default=grupos_disp,
                key="analitico_grupo_sel",
            )
            if grupo_sel:
                df_analitico = df_analitico[df_analitico["grupo"].isin(grupo_sel)]

            total_faltam = int(df_analitico["FALTAM_VISITAR"].sum())
            total_rotas = df_analitico["ROTA"].nunique()
            total_cidades = df_analitico["CIDADE"].nunique()

            c1, c2, c3 = st.columns(3)
            c1.metric(" Total Faltam Visitar", f"{total_faltam:,}".replace(",", "."))
            c2.metric(" Rotas com pendência", total_rotas)
            c3.metric(" Cidades envolvidas", total_cidades)

            st.divider()

            # ── Por Grupo ─────────────────────────────────────────────────
            if len(grupos_disp) > 1:
                st.subheader("Faltam Visitar — por Grupo")
                df_por_grupo = (
                    df_analitico
                    .groupby("grupo", dropna=False)["FALTAM_VISITAR"]
                    .sum()
                    .reset_index()
                    .sort_values("FALTAM_VISITAR", ascending=False)
                )
                df_por_grupo.columns = ["Grupo", "Faltam Visitar"]
                col_g1, col_g2 = st.columns([1, 2])
                with col_g1:
                    st.dataframe(df_por_grupo, use_container_width=True)
                with col_g2:
                    fig_grupo = px.bar(
                        df_por_grupo,
                        x="Grupo",
                        y="Faltam Visitar",
                        title="Faltam Visitar por Grupo",
                        color="Faltam Visitar",
                        color_continuous_scale="Blues",
                    )
                    st.plotly_chart(fig_grupo, use_container_width=True)
                st.divider()

            # ── Por Rota ──────────────────────────────────────────────────
            st.subheader("Faltam Visitar — por Rota")

            df_por_rota = (
                df_analitico
                .groupby(
                    ["grupo", "ZONA", "ROTA", "CIDADE", "SUPERVISOR_COMERCIAL", "ENCARREGADO_COMERCIAL"],
                    dropna=False,
                )["FALTAM_VISITAR"]
                .sum()
                .reset_index()
                .sort_values("FALTAM_VISITAR", ascending=False)
            )

            # Filtros rápidos
            with st.expander("🔍 Filtros", expanded=False):
                cidades_disp = sorted(df_por_rota["CIDADE"].dropna().unique().tolist())
                cidades_sel = st.multiselect("Cidade:", cidades_disp, key="analitico_cidades")
                if cidades_sel:
                    df_por_rota = df_por_rota[df_por_rota["CIDADE"].isin(cidades_sel)]

                supervisores_disp = sorted(df_por_rota["SUPERVISOR_COMERCIAL"].dropna().unique().tolist())
                sup_sel = st.multiselect("Supervisor Comercial:", supervisores_disp, key="analitico_sup")
                if sup_sel:
                    df_por_rota = df_por_rota[df_por_rota["SUPERVISOR_COMERCIAL"].isin(sup_sel)]

            st.dataframe(df_por_rota, use_container_width=True, height=400)

            # Gráfico Top 20 rotas
            fig_rota = px.bar(
                df_por_rota.head(20),
                x="ROTA",
                y="FALTAM_VISITAR",
                color="CIDADE",
                hover_data=["grupo", "ZONA", "SUPERVISOR_COMERCIAL", "ENCARREGADO_COMERCIAL"],
                title="Top 20 Rotas com mais Faltam Visitar",
                labels={"FALTAM_VISITAR": "Faltam Visitar"},
            )
            fig_rota.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig_rota, use_container_width=True)

            st.divider()

            # ── Por Cidade ────────────────────────────────────────────────
            st.subheader("Faltam Visitar — por Cidade")

            df_por_cidade = (
                df_analitico
                .groupby("CIDADE", dropna=False)["FALTAM_VISITAR"]
                .sum()
                .reset_index()
                .sort_values("FALTAM_VISITAR", ascending=False)
            )
            df_por_cidade.columns = ["CIDADE", "FALTAM_VISITAR"]

            col_tab, col_chart = st.columns([1, 1])
            with col_tab:
                st.dataframe(df_por_cidade, use_container_width=True, height=350)
            with col_chart:
                fig_cidade = px.bar(
                    df_por_cidade.head(15),
                    x="CIDADE",
                    y="FALTAM_VISITAR",
                    title="Top 15 Cidades — Faltam Visitar",
                    color="FALTAM_VISITAR",
                    color_continuous_scale="Reds",
                )
                fig_cidade.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_cidade, use_container_width=True)

            st.divider()

            # ── Exportar ──────────────────────────────────────────────────
            st.subheader("📥 Exportar Analítico Completo")
            col_csv, col_xlsx = st.columns(2)
            with col_csv:
                st.download_button(
                    "⬇️ Baixar CSV",
                    data=dataframe_to_csv(df_por_rota),
                    file_name="analitico_faltam_visitar.csv",
                    mime="text/csv",
                )
            with col_xlsx:
                st.download_button(
                    "⬇️ Baixar Excel",
                    data=dataframe_to_excel(df_por_rota),
                    file_name="analitico_faltam_visitar.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )


# ═══════════════════════════════════════════════════════════════════════════
# ADMIN
# ═══════════════════════════════════════════════════════════════════════════

def page_admin():
    st.title("👑 Administração")

    tab_users, tab_rotas, tab_regionais = st.tabs(["👤 Usuários", "🛣️ Rotas", "🗺️ Regionais"])

    # ── Usuários ──────────────────────────────────────────────────────────
    with tab_users:
        df_users = get_all_users()
        df_display = df_users.copy()
        df_display["Perfil"] = df_display["is_master"].apply(lambda x: "👑 Master" if x else "👤 Normal")
        st.subheader(f"Usuários cadastrados — {len(df_users)}")
        st.dataframe(df_display[["id", "username", "Perfil"]], use_container_width=True)
        st.divider()

        col_add, col_del, col_pwd = st.columns(3)

        with col_add:
            st.subheader("Adicionar usuário")
            with st.form("admin_add_user"):
                new_username = st.text_input("Usuário", key="admin_new_user")
                new_password = st.text_input("Senha", type="password", key="admin_new_pwd")
                new_is_master = st.checkbox("Perfil Master", key="admin_new_master")
                if st.form_submit_button("Criar"):
                    ok, msg = register_user(new_username, new_password, is_master=new_is_master)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

        with col_del:
            st.subheader("Excluir usuário")
            deletable = df_users[
                (df_users["username"] != st.session_state.username) &
                (df_users["is_master"] == 0)
            ]
            if deletable.empty:
                st.info("Nenhum usuário disponível para exclusão.")
            else:
                user_to_del = st.selectbox("Selecione:", deletable["username"].tolist(), key="del_user_sel")
                if st.button("🗑️ Excluir usuário", key="btn_del_user"):
                    uid = int(deletable[deletable["username"] == user_to_del]["id"].values[0])
                    delete_user(uid)
                    st.success(f"Usuário '{user_to_del}' excluído.")
                    st.rerun()

        with col_pwd:
            st.subheader("Alterar senha")
            user_to_edit = st.selectbox("Selecione:", df_users["username"].tolist(), key="edit_user_sel")
            with st.form("admin_change_pwd"):
                new_pwd = st.text_input("Nova senha", type="password")
                confirm_pwd = st.text_input("Confirmar senha", type="password")
                if st.form_submit_button("Alterar"):
                    if new_pwd != confirm_pwd:
                        st.error("Senhas não coincidem.")
                    else:
                        uid = int(df_users[df_users["username"] == user_to_edit]["id"].values[0])
                        ok, msg = change_user_password(uid, new_pwd)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)

    # ── Rotas ────────────────────────────────────────────────────────────
    with tab_rotas:
        df_rotas_adm = query_rotas()
        if df_rotas_adm.empty:
            st.info("Sem dados na tabela Rotas.")
        else:
            st.subheader(f"Editar / Excluir Rotas — {len(df_rotas_adm)} registros")
            st.caption("Edite as células diretamente ou delete linhas com o ícone 🗑. Clique em **Salvar** para confirmar.")
            edit_cols_r = [c for c in df_rotas_adm.columns if c not in ("id", "us_id", "data_upload")]
            edited_rotas = st.data_editor(
                df_rotas_adm[edit_cols_r],
                use_container_width=True,
                num_rows="dynamic",
                key="admin_rotas_editor",
                height=420,
            )
            if st.button("💾 Salvar alterações em Rotas", type="primary", key="save_rotas_adm"):
                with st.spinner("Salvando..."):
                    save_rotas_admin(edited_rotas)
                st.success("✅ Rotas atualizadas!")
                st.rerun()

    # ── Regionais ────────────────────────────────────────────────────────
    with tab_regionais:
        # === Importar via Excel ===
        with st.expander("📥 Importar Regionais via Excel", expanded=False):
            st.warning("⚠️ O upload irá **substituir** todos os dados existentes de Regionais.")
            uploaded_reg_adm = st.file_uploader(
                "Envie o arquivo Regionais (.xlsx)", type=["xlsx"], key="admin_reg_upload"
            )
            if uploaded_reg_adm is not None:
                try:
                    df_import_reg = load_regionais_excel(uploaded_reg_adm)
                    st.info(f"Arquivo lido: **{len(df_import_reg)}** linhas, **{len(df_import_reg.columns)}** colunas.")
                    st.dataframe(df_import_reg.head(5), use_container_width=True)
                    if st.button("✅ Confirmar importação", type="primary", key="admin_reg_confirm_import"):
                        insert_regionais(df_import_reg)
                        st.success(f"✅ Regionais importadas! ({len(df_import_reg)} registros)")
                        st.rerun()
                except Exception as e:
                    st.error(f"Erro ao processar o arquivo: {e}")

        st.divider()
        df_reg_adm = query_regionais()
        if df_reg_adm.empty:
            st.info("Sem dados na tabela Regionais.")
        else:
            st.subheader(f"Editar / Excluir Regionais — {len(df_reg_adm)} registros")
            st.caption("Edite as células diretamente ou delete linhas com o ícone 🗑. Clique em **Salvar** para confirmar.")
            edit_cols_reg = [c for c in df_reg_adm.columns if c != "id"]
            edited_reg = st.data_editor(
                df_reg_adm[edit_cols_reg],
                use_container_width=True,
                num_rows="dynamic",
                key="admin_reg_editor",
                height=420,
            )
            if st.button("💾 Salvar alterações em Regionais", type="primary", key="save_reg_adm"):
                with st.spinner("Salvando..."):
                    save_regionais_admin(edited_reg)
                st.success("✅ Regionais atualizadas! Vínculos com Rotas recalculados.")
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# BANCO DE DADOS
# ═══════════════════════════════════════════════════════════════════════════

def page_banco():
    st.title(" Gerenciamento do Banco de Dados")

    counts = get_table_counts()

    col1, col2, col3 = st.columns(3)
    col1.metric(" Usuários", counts["usuarios"])
    col2.metric(" Regionais", counts["regionais"])
    col3.metric(" Rotas", counts["rotas"])

    st.divider()

    tab_regionais, tab_rotas, tab_usuarios = st.tabs(["Regionais", "Rotas", "Usuários"])

    with tab_regionais:
        df = query_regionais()
        st.subheader(f"Tabela Regionais — {len(df)} registros")
        if not df.empty:
            st.dataframe(df, use_container_width=True, height=400)
        else:
            st.info("Tabela vazia.")
        st.divider()
        st.warning("⚠️ Limpar apaga **todos** os registros de Regionais permanentemente.")
        if st.button("🗑️ Limpar tabela Regionais", type="primary", key="clear_regionais"):
            if "confirm_clear_regionais" not in st.session_state:
                st.session_state.confirm_clear_regionais = True
                st.rerun()
        if st.session_state.get("confirm_clear_regionais"):
            st.error("Tem certeza? Esta ação não pode ser desfeita.")
            c1, c2 = st.columns(2)
            if c1.button("✅ Sim, limpar", key="yes_regionais"):
                clear_table("regionais")
                st.session_state.pop("confirm_clear_regionais", None)
                st.success("Tabela Regionais limpa com sucesso.")
                st.rerun()
            if c2.button("❌ Cancelar", key="no_regionais"):
                st.session_state.pop("confirm_clear_regionais", None)
                st.rerun()

    with tab_rotas:
        df = query_rotas()
        st.subheader(f"Tabela Rotas — {len(df)} registros")
        if not df.empty:
            st.dataframe(df, use_container_width=True, height=400)
        else:
            st.info("Tabela vazia.")
        st.divider()
        st.warning("⚠️ Limpar apaga **todos** os registros de Rotas permanentemente.")
        if st.button("🗑️ Limpar tabela Rotas", type="primary", key="clear_rotas"):
            if "confirm_clear_rotas" not in st.session_state:
                st.session_state.confirm_clear_rotas = True
                st.rerun()
        if st.session_state.get("confirm_clear_rotas"):
            st.error("Tem certeza? Esta ação não pode ser desfeita.")
            c1, c2 = st.columns(2)
            if c1.button("✅ Sim, limpar", key="yes_rotas"):
                clear_table("rotas")
                st.session_state.pop("confirm_clear_rotas", None)
                st.success("Tabela Rotas limpa com sucesso.")
                st.rerun()
            if c2.button("❌ Cancelar", key="no_rotas"):
                st.session_state.pop("confirm_clear_rotas", None)
                st.rerun()

    with tab_usuarios:
        import pandas as pd
        conn = __import__("database").get_connection()
        df_users = pd.read_sql_query("SELECT id, username FROM usuarios", conn)
        conn.close()
        st.subheader(f"Tabela Usuários — {len(df_users)} registros")
        if not df_users.empty:
            st.dataframe(df_users, use_container_width=True)
        else:
            st.info("Nenhum usuário cadastrado.")
        st.divider()
        st.warning("⚠️ Limpar apaga **todos** os usuários. Você precisará se recadastrar.")
        if st.button("🗑️ Limpar tabela Usuários", type="primary", key="clear_usuarios"):
            if "confirm_clear_usuarios" not in st.session_state:
                st.session_state.confirm_clear_usuarios = True
                st.rerun()
        if st.session_state.get("confirm_clear_usuarios"):
            st.error("Tem certeza? Você será deslogado imediatamente.")
            c1, c2 = st.columns(2)
            if c1.button("✅ Sim, limpar", key="yes_usuarios"):
                clear_table("usuarios")
                st.session_state.pop("confirm_clear_usuarios", None)
                st.session_state.logged_in = False
                st.session_state.username = ""
                st.session_state.page = "Home"
                st.rerun()
            if c2.button("❌ Cancelar", key="no_usuarios"):
                st.session_state.pop("confirm_clear_usuarios", None)
                st.rerun()

def main():
    if not st.session_state.logged_in:
        # Página pública: login na sidebar + dashboard visível
        _render_login_sidebar()
        page_public()
        return

    # Auto-load regionais on first access
    ensure_regionais()

    # Sidebar
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state.username}")
        st.divider()

        pages = {
            "🏠 Home": "Home",
            "📤 Upload LEI3020": "Upload",
            "📋 Visualização": "Visualização",
            "📊 Análises": "Análises",
            "🗄️ Banco de Dados": "Banco",
        }
        if st.session_state.get("is_master"):
            pages["👑 Admin"] = "Admin"

        for label, page_name in pages.items():
            if st.button(label, use_container_width=True):
                st.session_state.page = page_name
                st.rerun()

        st.divider()
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.page = "Home"
            st.rerun()

    # Route pages
    page = st.session_state.page
    if page == "Home":
        page_home()
    elif page == "Upload":
        page_upload()
    elif page == "Visualização":
        page_visualizacao()
    elif page == "Análises":
        page_analises()
    elif page == "Banco":
        page_banco()
    elif page == "Admin":
        if st.session_state.get("is_master"):
            page_admin()
        else:
            st.error("🚫 Acesso negado.")


if __name__ == "__main__":
    main()
