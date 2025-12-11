import feedparser
from bs4 import BeautifulSoup
import time
from datetime import datetime
import re
from curl_cffi import requests
from urllib.parse import urljoin

'''
fuentes: https://bvcenadim.digemid.minsa.gob.pe/index.php/enlaces/agencias-reguladoras-en-el-mundo
'''

def scrape_peru():
    """Extrae la ultima noticia del Digemid"""
    print("  -> Scrapeando PERÚ - DIGEMID...")
    url_peru = "https://www.digemid.minsa.gob.pe/webDigemid/publicaciones/alertas-modificaciones/feed/"

    response = requests.get(
        url_peru,
        timeout=30,
        impersonate="chrome110",
        verify=False
    )
    response.raise_for_status()

    try:
        feed = feedparser.parse(response.content)
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
        response = requests.get(
            url,
            timeout=30,
            impersonate="chrome110",
            verify=False
        )
        response.raise_for_status()

        try:
            feed = feedparser.parse(response.content)
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
    print("  -> Scrapeando BRASIL - ANVISA...")
    url_brasil = "https://antigo.anvisa.gov.br/alertas"
    noticias_brasil = []

    try:
        response = requests.get(
            url_brasil, 
            impersonate="chrome110", 
            timeout=30,
            verify=False 
        )
        
        if response.status_code != 200:
            print(f" -> [ERROR] Status code: {response.status_code}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        contenedores = soup.find_all('div', class_='row-fluid lista-noticias')

        if not contenedores:
            print(" -> [ADVERTENCIA] No se encontraron noticias (Estructura pudo cambiar).")
            return []

        for contenedor in contenedores:
            link_tag = contenedor.select_one('div.titulo-resumo p.titulo a')
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

    except Exception as e:
        print(f"[!] Error fatal en ANVISA: {e}")
        return []
       
def scrape_colombia():
    ''' Extrae TODAS las alertas de la primera página del INVIMA de Colombia '''
    print("  -> Scrapeando COLOMBIA - INVIMA...")
    url_colombia = "https://app.invima.gov.co/alertas/alertas-sanitarias-general?field_tipo_de_documento_value=2&field_a_o_value=1"
    noticias_colombia = []

    try:       
        response = requests.get(url_colombia, timeout=15,impersonate="chrome110")
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

    except Exception as e:
        print(f"[!] Error fatal en scraping de COLOMBIA - INVIMA: {e}")
        return []

def scrape_mexico():
    ''' Extrae las primeras 10 alertas de CADA CATEGORÍA de COFEPRIS y las consolida. '''
    print("  -> Scrapeando MÉXICO - COFEPRIS...")
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
        # Bucle para iterar sobre CADA categoría
        for categoria, url in url_mexico_categorias.items():
            
            response = requests.get(url, timeout=20, impersonate="chrome110")
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

def scrape_argentina():
    print("  -> Scrapeando ARGENTINA - ANMAT...")
    
    urls_argentina = {
        'Medicamentos': 'https://www.argentina.gob.ar/anmat/alertas/medicamentos/noticias',
        'Alimentos': 'https://www.argentina.gob.ar/anmat/alertas/alimentos/noticias',
        'Productos Médicos': 'https://www.argentina.gob.ar/anmat/alertas/productosmedicos/noticias',
        'Cosmeticos': 'https://www.argentina.gob.ar/anmat/alertas/cosmeticos/noticias',
        'Domisanitarios': 'https://www.argentina.gob.ar/anmat/alertas/domisanitarios/noticias'
    }

    noticias_argentina = []
    
    # Iteramos por cada categoría del diccionario
    for categoria, url in urls_argentina.items():      
        try:
            # Petición con identidad de Chrome
            response = requests.get(
                url, 
                impersonate="chrome110", 
                timeout=20, 
                verify=False
            )
            
            if response.status_code != 200:
                print(f"    [!] Error {response.status_code} en {categoria}")
                continue

            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Selector clave: Buscamos las tarjetas de noticias (clase 'panel panel-default')
            tarjetas = soup.find_all('a', class_='panel panel-default')
            
            if not tarjetas:
                continue

            for tarjeta in tarjetas:
                h3_tag = tarjeta.find('h3')
                titulo = h3_tag.get_text(strip=True) if h3_tag else "Sin título"
                
                link_relativo = tarjeta.get('href')
                link_absoluto = urljoin("https://www.argentina.gob.ar", link_relativo)
                
                time_tag = tarjeta.find('time')
                fecha_norm = "Sin fecha"
                
                if time_tag and time_tag.get('datetime'):
                    fecha_raw = time_tag.get('datetime')
                    try:
                        fecha_dt = datetime.strptime(fecha_raw, '%Y-%m-%d %H:%M:%S')
                        fecha_norm = fecha_dt.strftime('%d-%m-%Y %H:%M')
                    except ValueError:
                        fecha_norm = fecha_raw
                
                noticias_argentina.append({
                    'url': link_absoluto,
                    'titulo': titulo,
                    'fecha': fecha_norm,
                    'pais': 'Argentina',
                    'institucion': 'ANMAT'
                })
            
            time.sleep(1)

        except Exception as e:
            print(f"    [!] Error crítico en {categoria}: {e}")

    return noticias_argentina

def scrape_bolivia():
    print(" -> Scrapeando BOLIVIA - AGEMED...")
    
    urls_fragmentos = {
        'Vigilancia y Control': 'https://apiwww.agemed.gob.bo/api/web/vigilanciacontrol%7Ccontenido',
        'Seguridad (DTU)': 'https://apiwww.agemed.gob.bo/api/web/dtu%7Ccontenido'
    }

    url_base_files = "https://www.agemed.gob.bo/"
    
    noticias_bolivia = []
    anio_actual = datetime.now().year 

    for categoria, url in urls_fragmentos.items():
        try:
            
            response = requests.get(
                url, 
                impersonate="chrome110", 
                timeout=20, 
                verify=False
            )
            
            if response.status_code != 200:
                print(f"    [!] Error {response.status_code} al obtener fragmento.")
                continue

            soup = BeautifulSoup(response.content, 'html.parser')
            
            filas = soup.find_all('tr')
            
            for fila in filas:
                cols = fila.find_all('td')
                
                # Validamos que sea una fila de datos (mínimo 4 columnas según tu estructura)
                # Estructura: [0] Alerta N°, [1] Descripción, [2] Fecha, [3] Botón Ver
                if len(cols) >= 4:
                    # 1. Extracción de Fecha y Filtro
                    fecha_texto = cols[2].get_text(strip=True)
                    
                    try:
                        # Formato observado: 01/12/2025
                        fecha_dt = datetime.strptime(fecha_texto, '%d/%m/%Y')
                        
                        # FILTRO ESTRICTO: Solo año actual
                        if fecha_dt.year != anio_actual:
                            continue
                            
                        fecha_norm = fecha_dt.strftime('%d-%m-%Y')
                        
                    except ValueError:
                        # Si falla es porque es un encabezado o fila vacía
                        continue

                    # 2. Extracción de Datos
                    identificador = cols[0].get_text(strip=True)
                    descripcion = cols[1].get_text(strip=True)
                    titulo_full = f"{identificador} - {descripcion}"
                    
                    # 3. Extracción de Link PDF
                    tag_a = cols[3].find('a')
                    link_pdf = None
                    if tag_a and tag_a.get('href'):
                        # Unimos la base "www.agemed" con la ruta relativa "archivo_farmacovigi/..."
                        link_pdf = urljoin(url_base_files, tag_a['href'])

                    noticias_bolivia.append({
                        'titulo': titulo_full,
                        'fecha': fecha_norm,
                        'url': link_pdf,
                        'pais': 'Bolivia',
                        'institucion': 'AGEMED'
                    })
                    
        except Exception as e:
            print(f"    [!] Error en {categoria}: {e}")

    unicos = {n['url']: n for n in noticias_bolivia if n['url']}.values()

    return list(unicos)

## Página de mrd la de venezuela, no hay nada en su huevada

def scrape_costarica():
    """
    Scrapea alertas de Costa Rica
    """
    print(" -> Scrapeando COSTA RICA...")
    
    # 1. Obtener año actual dinámicamente
    anio_actual = datetime.now().year

    # 2. Construcción dinámica de enlaces
    urls_costarica = {
        'Radiológica': 'https://www.ministeriodesalud.go.cr/index.php/biblioteca-de-archivos-left/documentos-ministerio-de-salud/alertas-sanitarias/alertas-radiologicas',
        'Productos Mercado': f'https://www.ministeriodesalud.go.cr/index.php/biblioteca-de-archivos-left/documentos-ministerio-de-salud/alertas-sanitarias/alertas-por-productos-en-el-mercado/{anio_actual}-advertencias-por-productos-en-el-mercado',
        'Farmacovigilancia': f'https://www.ministeriodesalud.go.cr/index.php/biblioteca-de-archivos-left/documentos-ministerio-de-salud/alertas-sanitarias/alertas-farmacovigilancia/advertencias-farmacovigilancia-{anio_actual}'
    }

    url_base = "https://www.ministeriodesalud.go.cr"
    noticias_cr = []

    patron_fecha_inicio = r'^\d{1,2}\s+de\s+[a-zA-Záéíóú]+\s+(?:de\s+\d{4})?[.\-]?\s*'

    for categoria, url in urls_costarica.items():
        
        try:
            response = requests.get(
                url, 
                impersonate="chrome110", 
                timeout=20, 
                verify=False
            )
            
            if response.status_code == 404:
                print(f"    [AVISO] La URL para el año {anio_actual} aún no existe o cambió.")
                continue
            elif response.status_code != 200:
                print(f"    [!] Error {response.status_code}")
                continue

            soup = BeautifulSoup(response.content, 'html.parser')
            items = soup.find_all('tr', class_='docman_item')

            if not items:
                print(f"    [ADVERTENCIA] No hay documentos aún en {categoria}")
                continue

            for item in items:
                tag_a = item.find('a', class_='docman_track_download')
                if not tag_a: continue

                titulo_sucio = tag_a.get('data-title', 'Sin título').strip()
            
                titulo_limpio = re.sub(patron_fecha_inicio, '', titulo_sucio, flags=re.IGNORECASE).strip()
                titulo_limpio = titulo_limpio.capitalize()

                tag_time = item.find('time', itemprop='datePublished')
                fecha_norm = "Sin fecha"
                
                if tag_time and tag_time.get('datetime'):
                    fecha_raw = tag_time.get('datetime')
                    try:
                        fecha_dt = datetime.strptime(fecha_raw, '%Y-%m-%d %H:%M:%S')
                        
                        # Filtro estricto de año
                        if fecha_dt.year != anio_actual:
                            continue
                        
                        fecha_norm = fecha_dt.strftime('%d-%m-%Y %H:%M')
                    except ValueError:
                        fecha_norm = fecha_raw

                # Enlace
                link_relativo = tag_a.get('href')
                link_pdf = urljoin(url_base, link_relativo) if link_relativo else None

                noticias_cr.append({
                    'titulo': titulo_limpio,
                    'fecha': fecha_norm,
                    'url': link_pdf,
                    'pais': 'Costa Rica',
                    'institucion': 'MinSalud',
                    'categoria': categoria
                })
            
            time.sleep(1)

        except Exception as e:
            print(f"    [!] Error en {categoria}: {e}")

    unicos = {n['url']: n for n in noticias_cr if n['url']}.values()
    
    return list(unicos)