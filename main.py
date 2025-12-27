import os
import sys
from dotenv import load_dotenv, find_dotenv
import pandas as pd
import requests
from scraper import scrape_peru, scrape_chile, scrape_brasil, scrape_colombia, scrape_mexico, scrape_argentina, scrape_bolivia, scrape_costarica
import concurrent.futures
import html
from content_extractor import extract_content
from gemini_service import generar_resumen

# Cargar variables de entorno
load_dotenv(find_dotenv(), override=True)

# Configuración Global
ARCHIVO_HISTORIAL = "noticias_historial.csv"
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
SILENT_MODE = False # [IMPORTANTE] Si es True, guarda en CSV pero NO envía a Telegram

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    print("Error: Variables de entorno no configuradas")
    sys.exit(1)

LISTA_DE_SCRAPERS = [
    scrape_peru,
    scrape_chile,
    scrape_brasil,
    scrape_colombia,
    scrape_mexico,
    scrape_argentina,
    scrape_bolivia,
    scrape_costarica
]

def obtener_bandera(pais):
    banderas = {
        'Perú': '🇵🇪',
        'Chile': '🇨🇱',
        'Brasil': '🇧🇷',
        'Colombia': '🇨🇴',
        'México': '🇲🇽',
        'Argentina': '🇦🇷',
        'Bolivia': '🇧🇴',
        'Costa Rica': '🇨🇷'
    }
    return banderas.get(pais, '🌎')

def enviar_telegram(mensaje):
    if SILENT_MODE:
        print("  > [SILENT MODE] Mensaje omitido (no enviado a Telegram).")
        return

    print("Enviando mensaje...")
    url_bot = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        requests.post(url_bot, data=data)
        print(f"  > Enviado a {TELEGRAM_CHAT_ID}")
    except Exception as e:
        print(f"  > Error enviando a {TELEGRAM_CHAT_ID}: {e}")

def ejecutar_flujo():
    # 1. Cargar el historial
    try:
        df_historico = pd.read_csv(ARCHIVO_HISTORIAL)
        print(f"Historial cargado: {len(df_historico)} registros")
    except FileNotFoundError:
        df_historico = pd.DataFrame(columns=["url", "titulo", "fecha", "pais", "institucion", "resumen"])
        print("Historial no encontrado, creando nuevo archivo...")

    # 2. Recolectar noticias candidatas
    noticias_candidatas = []
    
    # Ejecución paralela con ThreadPoolExecutor
    print(f"Iniciando scraping paralelo con {len(LISTA_DE_SCRAPERS)} scrapers...")
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Enviamos todas las funciones a ejecutarse
        futuros = [executor.submit(scraper) for scraper in LISTA_DE_SCRAPERS]
        
        # Recogemos los resultados a medida que completan
        for futuro in concurrent.futures.as_completed(futuros):
            try:
                resultado = futuro.result()
                if resultado:
                    noticias_candidatas.extend(resultado)
            except Exception as e:
                print(f"  -> [ERROR CRÍTICO] Un scraper falló inesperadamente: {e}")

    if not noticias_candidatas:
        print("No se encontraron noticias candidatas")
        return

    df_candidatos = pd.DataFrame(noticias_candidatas)

    # 3. Detección de cambios
    # Si el historial tiene columnas viejas (sin pais/institucion/resumen), forzamos actualización
    if 'pais' not in df_historico.columns or 'resumen' not in df_historico.columns:
        print("Detectado formato antiguo de historial. Se actualizará todo.")
        df_novedades = df_candidatos
    else:
        url_historicas = df_historico['url']
        df_novedades = df_candidatos[~df_candidatos['url'].isin(url_historicas)]

    print(f"Se encontraron {len(df_novedades)} novedades")

    if not df_novedades.empty:
        # 4. Procesar y enviar alertas
        novedades_con_resumen = []
        
        for index, noticia in df_novedades.iterrows():
            print(f"\nProcesando alerta para {noticia['pais']} - {noticia['titulo'][:50]}...")
            
            # 4.1. Extraer contenido y generar resumen
            resumen = noticia['titulo']  # Fallback por defecto
            
            try:
                contenido = extract_content(noticia)
                
                if contenido:
                    print(f"  ✓ Contenido extraído: {len(contenido)} caracteres")
                    resumen = generar_resumen(contenido, noticia['titulo'])
                else:
                    print(f"  ! No se pudo extraer contenido, usando título original")
                    resumen = noticia['titulo']
            except Exception as e:
                print(f"  ! Error en extracción/resumen: {e}")
                resumen = noticia['titulo']
            
            # Agregar resumen a la noticia
            noticia_dict = noticia.to_dict()
            noticia_dict['resumen'] = resumen
            novedades_con_resumen.append(noticia_dict)
            
            # 4.2. Preparar y enviar mensaje a Telegram
            print(f"Enviando alerta a Telegram...")
            
            # Evitar error de caracteres especiales
            resumen_seguro = html.escape(str(resumen))
            institucion_segura = html.escape(str(noticia['institucion']))
            
            # Logica inteligente de enlaces
            link_web = noticia.get('url')
            link_pdf = noticia.get('pdf')

            texto_enlaces = ""
            # Caso A: Ambos enlaces disponibles (prioridad a web)
            if link_web and link_pdf:
                texto_enlaces = f"🔗 {link_web}"
            # Caso B: Solo Web
            elif link_web:
                texto_enlaces = f"🔗 {link_web}"
            # Caso C: Solo PDF
            elif link_pdf:
                texto_enlaces = f"📥 {link_pdf}"

            bandera = obtener_bandera(noticia['pais'])
            mensaje = (
                f"{bandera} <b>NUEVA ALERTA - {noticia['pais']}</b>\n"
                f"🏛 <b>Institución:</b> {institucion_segura}\n"
                f"📅 <b>Fecha:</b> {noticia['fecha']}\n\n"
                f"⚠️ <b>{resumen_seguro}</b>\n\n"
                f"{texto_enlaces}"
            )
            enviar_telegram(mensaje)
        
        # 5. Actualizar el historial
        # Convertir novedades con resumen a DataFrame
        df_novedades_actualizado = pd.DataFrame(novedades_con_resumen)
        
        # Concatenamos y guardamos con el nuevo formato
        if 'pais' not in df_historico.columns or 'resumen' not in df_historico.columns:
            # Si el historial es viejo, agregar columna resumen a candidatos
            if 'resumen' not in df_candidatos.columns:
                df_candidatos['resumen'] = df_candidatos['titulo']
            df_actualizado = df_candidatos.drop_duplicates(subset=['url'])
        else:
            df_actualizado = pd.concat([df_historico, df_novedades_actualizado]).drop_duplicates(subset=['url'])
            
        df_actualizado.to_csv(ARCHIVO_HISTORIAL, index=False)
        print(f"Historial actualizado: {len(df_actualizado)} registros")
    else:
        print("No se encontraron novedades")

if __name__ == "__main__":
    ejecutar_flujo()
