import json
import os
from bs4 import BeautifulSoup
import fitz  # PyMuPDF
import requests
import tempfile
try:
    from curl_cffi import requests as curl_requests
except ModuleNotFoundError:
    import requests as curl_requests
    _HAS_CURL_CFFI_REQUESTS = False
else:
    _HAS_CURL_CFFI_REQUESTS = True
import re
from urllib.parse import urljoin, urlparse

# Cargar configuración
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'extraction_config.json')
DRUGOFFICE_SOURCE_ID = "drugoffice_other_safety_alerts"
DRUGOFFICE_ORIGINAL_REFERENCE_PHRASES = [
    "please refer to the following website",
    "please refer to the following websites",
    "please refer to the following link",
    "please refer to the following links",
    "请参阅以下网站",
    "請參閱以下網站",
    "请查看以下网站",
    "請查看以下網頁",
]

def load_config():
    """Carga la configuración de extracción por país"""
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[!] Error cargando configuración: {e}")
        return {}

CONFIG = load_config()


def _get_drugoffice_detail_html(url, timeout=15):
    if _HAS_CURL_CFFI_REQUESTS:
        return curl_requests.get(url, impersonate="chrome110", timeout=timeout, verify=False)

    return curl_requests.get(url, timeout=timeout, verify=False)


def _get_html(url, timeout=15):
    if _HAS_CURL_CFFI_REQUESTS:
        return curl_requests.get(url, impersonate="chrome110", timeout=timeout, verify=False)

    return curl_requests.get(url, timeout=timeout, verify=False)


def _get_pdf(url, timeout=20):
    if _HAS_CURL_CFFI_REQUESTS:
        return curl_requests.get(url, impersonate="chrome110", timeout=timeout, verify=False)

    return curl_requests.get(url, timeout=timeout, verify=False)


def clean_text(value):
    if value is None:
        return ""
    return " ".join(str(value).split())


def _normalize_extracted_url(base_url, href):
    """Resolve relative links and ignore non-HTTP links."""
    if href is None:
        return None
    href = clean_text(href)
    href_lower = href.lower()
    if not href or href_lower.startswith(("javascript:", "mailto:", "tel:", "#")):
        return None

    absolute_url = urljoin(base_url, href)
    return absolute_url


def _is_external_non_drugoffice_url(url):
    parsed = urlparse(url or "")
    if not (parsed.scheme.startswith("http") and parsed.netloc):
        return False

    return "drugoffice.gov.hk" not in parsed.netloc.lower()


def _extract_text_from_soup(soup, config_key):
    config = CONFIG.get(config_key, {})
    container_selector = config.get('container')
    selectors = config.get('selectors', ['article', 'main', 'div.content'])
    remove_selectors = config.get('remove_selectors', ['script', 'style', 'nav', 'footer'])

    # Remover elementos no deseados
    for selector in remove_selectors:
        for element in soup.select(selector):
            element.decompose()

    scope = soup.select_one(container_selector) if container_selector else soup
    if not scope:
        return None

    fragmentos = []
    for selector in selectors:
        elementos = scope.select(selector)
        for elem in elementos:
            texto_limpio = elem.get_text(separator=' ', strip=True)
            if texto_limpio:
                fragmentos.append(texto_limpio)

    texto_final = ' '.join(fragmentos)
    return ' '.join(texto_final.split()) or None


def _find_reference_anchor_url(soup, page_url):
    phrase_selectors = ["p", "div", "td", "tr", "li", "span", "h1", "h2", "h3", "th"]
    for element in soup.find_all(phrase_selectors):
        text = clean_text(element.get_text(" ")).lower()
        if not text:
            continue

        if not any(phrase in text for phrase in DRUGOFFICE_ORIGINAL_REFERENCE_PHRASES):
            continue

        for anchor in element.find_all('a', href=True):
            absolute_url = _normalize_extracted_url(page_url, anchor.get('href'))
            if _is_external_non_drugoffice_url(absolute_url):
                return absolute_url

    return None


def _find_first_external_link(soup, page_url):
    for anchor in soup.find_all('a', href=True):
        absolute_url = _normalize_extracted_url(page_url, anchor.get('href'))
        if _is_external_non_drugoffice_url(absolute_url):
            return absolute_url
    return None


def extract_drugoffice_original_source_url(detail_html, detail_url):
    """Extract optional original authority URL from a Drug Office HTML detail page."""
    if not detail_html:
        return None

    soup = BeautifulSoup(detail_html, 'html.parser')

    preferred = _find_reference_anchor_url(soup, detail_url)
    if preferred:
        return preferred

    return _find_first_external_link(soup, detail_url)

def resolve_config_key(noticia):
    """Prioriza source_id para fuentes multi-jurisdicción y cae a pais."""
    return noticia.get('source_id') or noticia.get('pais')

def extract_text_from_html(url, pais):
    """
    Extrae texto de una página HTML usando selectores configurados por país
    
    Args:
        url: URL de la página HTML
        pais: Nombre del país para obtener configuración
        
    Returns:
        str: Primeras 1500 caracteres de texto extraído
    """
    try:
        # Obtener configuración del país
        config = CONFIG.get(pais, {})
        container_selector = config.get('container')
        selectors = config.get('selectors', ['article', 'main', 'div.content'])
        remove_selectors = config.get('remove_selectors', ['script', 'style', 'nav', 'footer'])

        # Hacer request
        response = _get_html(url, timeout=15)
        
        if response.status_code != 200:
            print(f"[!] Error HTTP {response.status_code} al extraer HTML de {url}")
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        return _extract_text_from_soup(soup, pais)
        
    except Exception as e:
        print(f"[!] Error extrayendo HTML de {url}: {e}")
        return None

def extract_text_from_pdf(url):
    """
    Extrae texto de un PDF usando PyMuPDF
    
    Args:
        url: URL del archivo PDF
        
    Returns:
        str: Primeras 1500 caracteres de texto extraído
    """
    try:
        # Descargar PDF en la memoria RAM
        response = _get_pdf(url, timeout=20)
        
        if response.status_code != 200:
            print(f"[!] Error HTTP {response.status_code} al descargar PDF de {url}")
            return None
        
        # Guardar temporalmente
        with fitz.open(stream=response.content, filetype="pdf") as doc:
            fragmentos = []
            num_paginas = min(3, len(doc))

            for page_num in range(num_paginas):
                page = doc.load_page(page_num)
                texto = page.get_text('text')
                if texto:
                    fragmentos.append(texto)
            
            texto_final = ' '.join(fragmentos)
            
            # Limpiar espacios múltiples
            texto_final = ' '.join(texto_final.split())
            
            return texto_final if texto_final else None
                
    except Exception as e:
        print(f"[!] Error extrayendo PDF de {url}: {e}")
        return None

def extract_content(noticia):
    """
    Extrae contenido de una noticia según su país y tipo de contenido
    
    Args:
        noticia: Dict con información de la noticia (debe incluir 'pais', 'url', opcionalmente 'pdf')
        
    Returns:
        str: Texto extraído o None si falla
    """
    pais = noticia.get('pais')
    config_key = resolve_config_key(noticia)
    config = CONFIG.get(config_key, {})
    content_type = config.get('content_type', 'pdf')
    
    print(f"  → Extrayendo contenido ({content_type}) para {pais}...")

    url = noticia.get('pdf') or noticia.get('url')
    if url and str(url).lower().split('?', 1)[0].endswith('.pdf'):
        return extract_text_from_pdf(url)
    
    if content_type == 'html':
        # Países con HTML: Argentina, Brasil
        response = extract_text_from_html(url, config_key)

        if config_key == DRUGOFFICE_SOURCE_ID and isinstance(url, str):
            page_response = _get_drugoffice_detail_html(url, timeout=15)
            if page_response.status_code == 200:
                original_url = extract_drugoffice_original_source_url(page_response.content, url)
                if original_url:
                    noticia["url_fuente_original"] = original_url

        return response
    
    elif content_type == 'pdf':
        # Para Perú, usar el link PDF si existe
        if pais == 'Perú' and noticia.get('pdf'):
            url = noticia.get('pdf')
        else:
            url = noticia.get('url')
        
        return extract_text_from_pdf(url)
    
    return None
