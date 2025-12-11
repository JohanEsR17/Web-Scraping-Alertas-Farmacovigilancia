import streamlit as st
import pandas as pd
import plotly.express as px
import os

# Configuración de la página
st.set_page_config(page_title="Dashboard Alertas Sanitarias", layout="wide")

# 1. CARGA DE DATOS
@st.cache_data
def load_data(filepath):
    file_path = "noticias_historial.csv"
    
    df = pd.read_csv(filepath)

    # Convierto la fecha a datetime
    df["fecha"] = df["fecha"].astype(str).str.split(" ").str[0]
    df['fecha'] = pd.to_datetime(df['fecha'], dayfirst=True, errors = "coerce")
    
    # Filtro por fecha desde el 1 de noviembre del 2025
    df = df[df['fecha'] >= "2025-11-20"].sort_values(by="fecha", ascending=False)

    return df

# Cargar datos
FILE_NAME = "noticias_historial.csv"
df = load_data(FILE_NAME)

# 2. INTERFAZ Y FILTROS
st.title("📊 Monitor de Alertas Sanitarias")
st.text("Datos recolectados desde el 20 de Noviembre del 2025")

if df is None:
    st.error(f"No se encontró el archivo '{FILE_NAME}'. Ejecuta primero el scraper.")
    st.stop()

# Filtro País
paises_disponibles = sorted(df['pais'].unique().tolist())

st.sidebar.header("Filtrar por País")
pais_seleccion = st.sidebar.multiselect("Seleccionar País", options=paises_disponibles, placeholder="(Seleccionar para filtrar)")

if not pais_seleccion:
    df_filtered = df.copy()
else:
    df_filtered = df[df['pais'].isin(pais_seleccion)]

if not pais_seleccion:
    st.sidebar.caption("👁️ Mostrando todos los países")

# 3. KPIS (Métricas clave)
col1, col2, col3 = st.columns(3)
col1.metric("Total Alertas", len(df_filtered))
col2.metric("Países Activos", df_filtered['pais'].nunique())
col3.metric("Última Actualización", df_filtered['fecha'].max().strftime('%d-%m-%Y'))

st.divider()

# 4. GRÁFICOS
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.subheader("Alertas por País")
    if not df_filtered.empty:
        conteo_pais = df_filtered['pais'].value_counts().reset_index()
        conteo_pais.columns = ['País', 'Cantidad']
        fig_pais = px.bar(conteo_pais, x='País', y='Cantidad', color='País', text='Cantidad')
        st.plotly_chart(fig_pais, use_container_width=True)
    else:
        st.info("Sin datos para mostrar.")

with col_chart2:
    st.subheader("Evolución Temporal (Por día)")
    if not df_filtered.empty:
        # Agrupar por fecha simple
        df_time = df_filtered.groupby('fecha').size().reset_index(name='Alertas')
        # Filtrar fechas dummy (1900)
        df_time = df_time[df_time['fecha'] > '2025-11-01']
        
        fig_time = px.line(df_time, x='fecha', y='Alertas', markers=True)
        st.plotly_chart(fig_time, use_container_width=True)
    else:
        st.info("Sin datos para mostrar.")

# 5. TABLA DE DATOS
st.subheader("Detalle de Alertas")

# Configurar columna de enlace para que sea clickeable
st.data_editor(
    df_filtered[['fecha', 'pais', 'institucion', 'titulo', 'url']],
    column_config={
        "url": st.column_config.LinkColumn("Enlace Oficial", display_text="🔗 Ver Alerta"),
        "fecha": st.column_config.DateColumn("Fecha Publicación", format="DD-MM-YYYY"),
        "pais": "País",
        "institucion": "Entidad",
        "titulo": st.column_config.TextColumn("Título de la Alerta", width="large")
    },
    hide_index=True,
    use_container_width=True,
    disabled=True # Hacer la tabla solo lectura
)