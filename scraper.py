import cloudscraper
import feedparser
from bs4 import BeautifulSoup
import time
from datetime import datetime
import re
import requests
import ssl
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Suprimir advertencias de SSL inseguro
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Configuración de SSL para compatibilidad con versiones antiguas
class LegacySSLAdapter(HTTPAdapter):
    """
    Esta clase fuerza al sistema a usar protocolos de seguridad antiguos (SECLEVEL=1).
    Sin esto, GitHub Actions bloqueará la conexión a servidores viejos como ANVISA.
    """
    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context(ciphers='DEFAULT:@SECLEVEL=1')
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = context
        return super(LegacySSLAdapter, self).init_poolmanager(*args, **kwargs)

'''
fuentes: https://bvcenadim.digemid.minsa.gob.pe/index.php/enlaces/agencias-reguladoras-en-el-mundo
'''

def scrape_peru():
    """Extrae la ultima noticia del Digemid"""
    print("  -> Scrapeando PERÚ - DIGEMID...")
    url_peru = "https://www.digemid.minsa.gob.pe/webDigemid/publicaciones/alertas-modificaciones/feed/"

    try:
        feed = feedparser.parse(url_peru)
        noticias_peru = []

        for entry in feed.entries:
            fecha_str = "Sin Fecha"
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                fecha_struct = entry.published_parsed
                fecha_str = time.strftime("%d-%m-%Y %H:%M:%S", fecha_struct)
            noticias_peru.append({
                'url': entry.link,
                'titulo': entry.title,
                'fecha': fecha_str,
                'pais': 'Perú',
                'institucion': 'DIGEMID'
            })
        
        return noticias_peru

    except Exception as e:
        print(f"  -> [ERROR] Falló el scraping de DIGEMID: {e}")
        return []

def scrape_chile():
    ''' Extrae las ultimas alertas del Instituto de Salud Pública de Chile'''
    print("  -> Scrapeando CHILE - ISPCH...")
    url_chile = {
        "Alerta Medicamentos": "https://www.ispch.gob.cl/categorias-alertas/anamed/feed/",
        "Alerta Dispositivos Medicos": "https://www.ispch.gob.cl/categorias-alertas/dispositivos-medicos/feed/",
        "Alerta Desinfectantes": "https://www.ispch.gob.cl/categorias-alertas/desinfectantes-y-sanitizantes/feed/"
    }

    noticias_chile = []

    for subcategoria, url in url_chile.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                fecha_str = "Sin Fecha"
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    fecha_struct = entry.published_parsed
                    fecha_str = time.strftime("%d-%m-%Y %H:%M:%S", fecha_struct)
                noticias_chile.append({
                    'url': entry.link,
                    'titulo': entry.title,
                    'fecha': fecha_str,
                    'pais': 'Chile',
                    'institucion': 'ISPCH'
                })

        except Exception as e:
            print(f"  -> [ERROR] Falló el scraping de CHILE - {subcategoria}: {e}")
            return []

    return noticias_chile

def scrape_brasil():
    ''' Extrae las ultimas alertas de ANVISA de Brasil '''
    print("  -> Scrapeando BRASIL - ANVISA...")
    url_brasil = "https://antigo.anvisa.gov.br/alertas"
    noticias_brasil = []

    try:
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            },
            interpreter='nodejs'
        )

        # Configuración de SSL para compatibilidad con versiones antiguas
        scraper.mount('https://', LegacySSLAdapter())

        response = scraper.get(url_brasil, timeout=60, verify=False)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        contenedores = soup.find_all('div', class_='row-fluid lista-noticias')

        if not contenedores:
            print("  -> [ERROR] No se encontró ningun contenedor de noticia")
            return []

        for contenedor in contenedores:
            # Enlace - Título
            link_tag = contenedor.select_one('div.titulo-resumo p.titulo a')

            # Fecha
            fecha_tag = contenedor.select_one('div.span3.data-hora p.data .icon-calendar')
            hora_tag = contenedor.select_one('div.span3.data-hora p.hora .icon-time')

            if link_tag and fecha_tag and link_tag.get('href'):
                fecha_bruto = fecha_tag.parent.text.strip()
                hora_bruto = hora_tag.parent.text.strip()
                fecha_hora_bruto = f"{fecha_bruto} {hora_bruto}"
                
                try:
                    fecha_dt = datetime.strptime(fecha_hora_bruto, '%d/%m/%Y %H:%M')
                    fecha_normalizada = fecha_dt.strftime('%d-%m-%Y %H:%M')
                except ValueError:
                    fecha_normalizada = fecha_bruto

                noticias_brasil.append({
                    'url': link_tag.get('href'),
                    'titulo': link_tag.text.strip(),
                    'fecha': fecha_normalizada,
                    'pais': 'Brasil',
                    'institucion': 'ANVISA'
                })
            
        print(f"  -> Se extrajeron {len(noticias_brasil)} noticias de la Página 1 de BRASIL - ANVISA.")
        return noticias_brasil

    except requests.exceptions.SSLError as e:
        print(f"[BRASIL - ANVISA] Error SSL, servidor inestable: {e}")    

    except Exception as e:
        print(f"[!] Error fatal en scraping de BRASIL - ANVISA: {e}")
        return []
            
def scrape_colombia():
    ''' Extrae TODAS las alertas de la primera página del INVIMA de Colombia '''
    print("  -> Scrapeando COLOMBIA - INVIMA...")
    url_colombia = "https://app.invima.gov.co/alertas/alertas-sanitarias-general?field_tipo_de_documento_value=2&field_a_o_value=1"
    noticias_colombia = []

    try:
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        
        response = scraper.get(url_colombia, timeout=15)
        response.raise_for_status() 

        soup = BeautifulSoup(response.content, 'html.parser')
        contenedores = soup.find_all('div', class_='alertas-invima-list')

        if not contenedores:
            print("  -> [ERROR] No se encontró ningún contenedor de noticia (clase 'alertas-invima-list')")
            return []

        for contenedor in contenedores:
            titulo_tag = contenedor.select_one('div.views-field-title span.field-content')
            fecha_tag = contenedor.select_one('div.views-field-field-a-o div.field-content')
            link_tag = contenedor.select_one('span.views-field-field-comunicado-invima a')

            if titulo_tag and fecha_tag and link_tag and link_tag.get('href'):
                fecha_bruto = fecha_tag.text.strip()
                fecha_normalizada = datetime.strptime(fecha_bruto, '%Y-%m-%d').strftime('%d-%m-%Y')

                noticias_colombia.append({
                    'url': link_tag.get('href'),
                    'titulo': titulo_tag.text.strip(),
                    'fecha': fecha_normalizada,
                    'pais': 'Colombia',
                    'institucion': 'INVIMA'
                })

        print(f"  -> Se extrajeron {len(noticias_colombia)} noticias de la Página 1 de COLOMBIA - INVIMA.")
        return noticias_colombia
    except Exception as e:
        print(f"[!] Error fatal en scraping de COLOMBIA - INVIMA: {e}")
        return []

def scrape_mexico():
    ''' Extrae las primeras 10 alertas de CADA CATEGORÍA de COFEPRIS y las consolida. '''
    URL_BASE_COFEPRIS = "https://www.gob.mx/cofepris/documentos/alertas-sanitarias-de-"
    LIMITE_NOTICIAS = 10 

    # 1. Definición de URLs por Categoría
    url_mexico_categorias = {
        "Dispositivos Médicos": f"{URL_BASE_COFEPRIS}dispositivos-medicos",
        "Medicamentos": f"{URL_BASE_COFEPRIS}medicamentos",
        "Alimentos": f"{URL_BASE_COFEPRIS}alimentos",
        "Bebidas Alcoholicas": f"{URL_BASE_COFEPRIS}bebidas-alcoholicas",
        "Suplementos Alimenticios": f"{URL_BASE_COFEPRIS}suplementos-alimenticios"
    }
    
    noticias_mexico = []

    try:
        scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )
        
        # Bucle para iterar sobre CADA categoría
        for categoria, url in url_mexico_categorias.items():
            
            response = scraper.get(url, timeout=20)
            response.raise_for_status() 

            soup = BeautifulSoup(response.content, 'html.parser')
            contenedores = soup.find_all('li', class_='clearfix documents')            
            contenedores_recientes = contenedores[:LIMITE_NOTICIAS] 

            if not contenedores_recientes:
                print(f"  -> [ERROR] No se encontraron contenedores en {categoria}.")
                continue 

            # Iterar sobre los 10 más recientes de esta categoría
            for contenedor in contenedores_recientes:
                
                titulo_div = contenedor.select_one('div.col-md-10')
                link_tag = contenedor.select_one('div.col-md-2 a')
                
                if titulo_div and link_tag and link_tag.get('href'):
                    
                    titulo_completo = titulo_div.text.strip()
                    fecha_normalizada = "Sin Fecha"

                    match = re.search(r'(\d{8})', titulo_completo)
                    if match:
                        fecha_str_ddmmyyyy = match.group(1)
                        try:
                            fecha_dt = datetime.strptime(fecha_str_ddmmyyyy, '%d%m%Y')
                            fecha_normalizada = fecha_dt.strftime('%d-%m-%Y')
                        except ValueError:
                            fecha_normalizada = fecha_str_ddmmyyyy
                    
                    titulo_sin_ext = titulo_completo.split('.pdf')[0]
                    if match:
                        # Intenta remover la fecha de 8 dígitos que encontró
                        titulo_limpio = titulo_sin_ext.replace(fecha_str_ddmmyyyy, '').strip('_').strip()
                    else:
                        titulo_limpio = titulo_sin_ext
                        
                    enlace_completo = f"https://www.gob.mx{link_tag.get('href')}" 
                    
                    noticias_mexico.append({
                        'url': enlace_completo,
                        'titulo': titulo_limpio,
                        'fecha': fecha_normalizada,
                        'pais': 'México',
                        'institucion': 'COFEPRIS'
                    })

    except Exception as e:
        print(f"[!] Error fatal en el scraping de MÉXICO - COFEPRIS: {e}")
        return []
        
    return noticias_mexico