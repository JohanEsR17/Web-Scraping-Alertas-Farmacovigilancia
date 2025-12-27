import os
from google import genai
from google.genai import types

# System instruction para Gemini
SYSTEM_INSTRUCTION = """
Resume el texto en 20-30 palabras, explicando solo la causa de la alerta o modificación del medicamento.
Menciona el producto involucrado y el motivo principal (defecto, riesgo, error, retiro, cambio, etc.).
No agregues recomendaciones, acciones ni especulaciones. No inventes información que no esté en el texto.
Si el texto está en otro idioma, traduce y redacta SIEMPRE el resumen en español.
"""

def generar_resumen(texto_contenido, titulo_original=""):
    """
    Genera un resumen de 20-30 palabras usando Gemini API
    
    Args:
        texto_contenido: Texto extraído del documento (hasta 1500 caracteres)
        titulo_original: Título original como fallback
        
    Returns:
        str: Resumen generado o título original si falla
    """
    try:
        # Configurar cliente Gemini
        api_key = os.environ.get('GEMINI_API_KEY')
        
        if not api_key:
            print("[!] GEMINI_API_KEY no encontrada en variables de entorno")
            return titulo_original
        
        client = genai.Client(api_key=api_key)
        
        # Preparar prompt
        prompt = f"Texto a resumir:\n\n{texto_contenido}"
        
        # Generar resumen
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                thinking_config = types.ThinkingConfig(thinkingBudget = 2),
                temperature=0.2,
                max_output_tokens=100
            )
        )
        
        # Extraer texto de la respuesta
        if response and response.text:
            resumen = response.text.strip()
            print(f"  ✓ Resumen generado: {resumen[:50]}...")
            return resumen
        else:
            print("[!] Gemini no devolvió respuesta válida")
            return titulo_original
            
    except Exception as e:
        print(f"[!] Error generando resumen con Gemini: {e}")
        return titulo_original
