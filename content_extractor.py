import json
import os
from bs4 import BeautifulSoup
import fitz  # PyMuPDF
import requests
from curl_cffi import requests as curl_requests
import tempfile

# Cargar configuración
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'extraction_config.json')

def load_config():
    """Carga la configuración de extracción por país"""
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[!] Error cargando configuración: {e}")
        return {}

CONFIG = load_config()

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
        response = curl_requests.get(
            url,
            impersonate="chrome110",
            timeout=15,
            verify=False
        )
        
        if response.status_code != 200:
            print(f"[!] Error HTTP {response.status_code} al extraer HTML de {url}")
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remover elementos no deseados
        for selector in remove_selectors:
            for element in soup.select(selector):
                element.decompose()
        
        # Area de Extracción
        scope = soup.select_one(container_selector) if container_selector else soup
        if not scope:
            print(f"[!] No se encontró el contenedor para {pais}")
            return None

        # Extracción de texto
        fragmentos = []
        for selector in selectors:
            elementos = scope.select(selector)
            for elem in elementos:
                texto_limpio = elem.get_text(separator = ' ', strip = True)
                if texto_limpio:
                    fragmentos.append(texto_limpio)
        
        texto_final = ' '.join(fragmentos)
        
        # Limpiar espacios múltiples
        texto_final = ' '.join(texto_final.split())
        
        return texto_final if texto_final else None
        
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
        response = curl_requests.get(
            url,
            impersonate="chrome110",
            timeout=20,
            verify=False
        )
        
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
    config = CONFIG.get(pais, {})
    content_type = config.get('content_type', 'pdf')
    
    print(f"  → Extrayendo contenido ({content_type}) para {pais}...")
    
    if content_type == 'html':
        # Países con HTML: Argentina, Brasil
        url = noticia.get('url')
        return extract_text_from_html(url, pais)
    
    elif content_type == 'pdf':
        # Para Perú, usar el link PDF si existe
        if pais == 'Perú' and noticia.get('pdf'):
            url = noticia.get('pdf')
        else:
            url = noticia.get('url')
        
        return extract_text_from_pdf(url)
    
    return None
