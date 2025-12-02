import streamlit as st
import pandas as pd
import plotly.express as px
import os

# Configuración de la página (Debe ser la primera instrucción de Streamlit)
st.set_page_config(page_title="Dashboard Alertas Sanitarias", layout="wide")

# 1. CARGA DE DATOS
@st.cache_data
def load_data(filepath):
    if not os.path.exists(filepath):
        return None
    
    # Leer CSV
    df = pd.read_csv(filepath)
    
    # Limpieza y conversión de fechas
    # errors='coerce' transformará fechas inválidas (como "Sin Fecha") en NaT
    df['fecha_dt'] = pd.to_datetime(df['fecha'], dayfirst=True, errors='coerce')
    
    # Extraer solo fecha (sin hora) para agrupaciones
    df['fecha_simple'] = df['fecha_dt'].dt.date
    
    # Llenar NaT con una fecha dummy o eliminar si es crítico
    df['fecha_dt'] = df['fecha_dt'].fillna(pd.Timestamp('1900-01-01'))
    
    return df

# Cargar datos (Asegúrate de que este archivo exista o cambia el nombre)
FILE_NAME = "noticias_historial.csv"
df = load_data(FILE_NAME)

# 2. INTERFAZ Y FILTROS
st.title("📊 Monitor de Alertas Sanitarias - Latam")

if df is None:
    st.error(f"No se encontró el archivo '{FILE_NAME}'. Ejecuta primero el scraper.")
    st.stop()

# Sidebar: Filtros
st.sidebar.header("Filtros")

# Filtro País
paises_disponibles = df['pais'].unique().tolist()
pais_seleccion = st.sidebar.multiselect("Seleccionar País", paises_disponibles, default=paises_disponibles)

# Filtro Institución
inst_disponibles = df['institucion'].unique().tolist()
inst_seleccion = st.sidebar.multiselect("Seleccionar Institución", inst_disponibles, default=inst_disponibles)

# Aplicar filtros
mask = (df['pais'].isin(pais_seleccion)) & (df['institucion'].isin(inst_seleccion))
df_filtered = df[mask]

# 3. KPIS (Métricas clave)
col1, col2, col3 = st.columns(3)
col1.metric("Total Alertas", len(df_filtered))
col2.metric("Países Activos", df_filtered['pais'].nunique())
col3.metric("Última Actualización", df_filtered['fecha_dt'].max().strftime('%d-%m-%Y') if not df_filtered.empty else "-")

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
        df_time = df_filtered.groupby('fecha_simple').size().reset_index(name='Alertas')
        # Filtrar fechas dummy (1900)
        df_time = df_time[df_time['fecha_simple'] > pd.Timestamp('2000-01-01').date()]
        
        fig_time = px.line(df_time, x='fecha_simple', y='Alertas', markers=True)
        st.plotly_chart(fig_time, use_container_width=True)
    else:
        st.info("Sin datos para mostrar.")

# 5. TABLA DE DATOS
st.subheader("Detalle de Alertas")

# Configurar columna de enlace para que sea clickeable
st.data_editor(
    df_filtered[['fecha', 'pais', 'institucion', 'titulo', 'url']],
    column_config={
        "url": st.column_config.LinkColumn("Enlace Oficial"),
        "fecha": "Fecha Publicación",
        "pais": "País",
        "institucion": "Entidad",
        "titulo": "Título de la Alerta"
    },
    hide_index=True,
    use_container_width=True,
    disabled=True # Hacer la tabla solo lectura
)