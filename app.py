import gradio as gr
import requests
import json
import os
import time
from dotenv import load_dotenv
from datetime import datetime
import tempfile

# Cargar variables de entorno
load_dotenv()

# Configuración de modelos
MODEL_MAPPING = {
    "Ministral 8B Instruct 2410": "ministral-8b-instruct-2410",
    "Gemma 2 9B Instruct": "gemma-2-9b-it",
    "Meta Llama 3.1 8B Instruct": "meta-llama-3.1-8b-instruct",
    "Qwen2.5 7B Instruct": "qwen2.5-7b-instruct"
}

# Configuración de la API
API_URL = "http://localhost:7860/v1/chat/completions"

# Tema personalizado
theme = gr.themes.Soft(
    primary_hue="sky",
    secondary_hue="sky",
    neutral_hue="blue",
    font=gr.themes.GoogleFont("Poppins")
).set(
    button_primary_background_fill="*primary_500",
    button_primary_background_fill_hover="*primary_600",
    block_label_text_size="lg",
    block_title_text_size="xl",
    block_background_fill="transparent",
    block_border_width="0px",
    block_shadow="none",
    input_background_fill="#e8f0fe",
    input_border_width="1px",
    input_border_color="*primary_200",
    input_shadow="none",
    input_radius="8px"
)

# Guía de características
GUIDE = """
### 🎯 Guía de uso

#### 📚 Modelos disponibles
- **Ministral 8B Instruct**: modelo base versátil, bueno para historias generales
- **Gemma 2 9B**: excelente para historias creativas y diálogos naturales
- **Meta Llama 3.1 8B**: destaca en coherencia narrativa y desarrollo de personajes
- **Qwen2.5 7B**: especializado en historias detalladas y descripciones vívidas

#### 🎨 Controles creativos
- **Temperatura**: controla la creatividad y aleatoriedad
  - 0.0-0.3: historias más predecibles y coherentes
  - 0.4-0.7: balance entre creatividad y coherencia
  - 0.8-1.0: historias más experimentales y únicas

- **Diversidad (Top-P)**: afecta la variedad de palabras
  - Valores bajos: vocabulario más conservador
  - Valores altos: mayor riqueza léxica

- **Penalización de repetición**: evita repeticiones
  - 1.0: permite algunas repeticiones naturales
  - 1.5: balance recomendado
  - 2.0: evita fuertemente las repeticiones

#### 📏 Longitudes de historia
- **Corta**: ~250 palabras, perfecta para historias rápidas
- **Media**: ~500 palabras, ideal para la mayoría de narrativas
- **Larga**: ~1000 palabras, para historias más desarrolladas
"""

# CSS para mejorar la presentación
css = """
.story-output {
    font-family: cursive;
    line-height: 1.8;
}

.story-title {
    font-size: 2em;
    font-weight: bold;
    text-align: center;
    color: #ffa500;
    margin: 0.5em 0 1.5em 0;
    font-family: 'Poppins', sans-serif;
    padding: 10px;
    border-bottom: 2px solid #e2e8f0;
}

.story-content {
    font-size: 1.1em;
    text-align: justify;
    padding: 0 10px;
}

.download-button {
    margin: 10px auto !important;
    max-width: 200px !important;
}

.download-button > .wrap {
    border: 1px solid #e2e8f0 !important;
    border-radius: 8px !important;
    padding: 5px !important;
    background: #f8fafc !important;
}

.download-button:hover > .wrap {
    background: #f1f5f9 !important;
}

.generating-message {
    background: linear-gradient(-45deg, #e8f3ff, #d1e5ff, #b8d8ff, #9ecaff);
    background-size: 400% 400%;
    animation: gradient 3s ease infinite;
    padding: 1em;
    border-radius: 8px;
    text-align: center;
    font-family: 'Poppins', sans-serif;
    color: #2c5282;
    margin: 1em 0;
    font-size: 1.2em;
}

@keyframes gradient {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}
"""

def generate_story(main_character, secondary_character, location, key_action, temperature, 
                  model_choice, genre, story_length, include_dialogue, top_p, repeat_penalty):
    try:
        # Valores por defecto
        main_character = main_character.strip() if main_character else "Germán"
        secondary_character = secondary_character.strip() if secondary_character else "Carlos"
        location = location.strip() if location else "una playa desierta"
        key_action = key_action.strip() if key_action else "practicar surf en verano"

        # Limpiar emojis del género y longitud
        genre = genre.split()[0] if genre else "Aventura"
        story_length = story_length.split()[0] if story_length else "Media"

        # Mapear longitud de historia a tokens (ahora más flexible)
        length_tokens = {
            "Corta": "una historia breve de aproximadamente 200-300 palabras",
            "Media": "una historia de longitud media de aproximadamente 400-600 palabras",
            "Larga": "una historia extensa de aproximadamente 800-1200 palabras"
        }

        # Construir el prompt
        dialogue_instruction = "con diálogos naturales entre los personajes" if include_dialogue else "enfocándote en la narrativa descriptiva"
        
        system_prompt = f"""Eres un escritor creativo especializado en crear historias cautivadoras.
Tu tarea es escribir {length_tokens[story_length]} en el género de {genre}.

Ajusta tu estilo según estos parámetros:
- Creatividad: {temperature} (0=conservador, 1=muy creativo)
- Diversidad de vocabulario: {top_p} (mayor valor = vocabulario más rico)
- Repetición: {repeat_penalty} (mayor valor = menos repeticiones)

La historia debe tener un título atractivo en la primera línea, separado del contenido por una línea en blanco.
El título debe ser conciso y cautivador, sin usar caracteres especiales ni formatos.

Escribe de manera fluida y natural, sin preocuparte por el conteo exacto de palabras."""

        user_prompt = f"""Escribe una historia sobre {main_character} y {secondary_character} en {location}, donde {key_action}.
La historia debe ser {dialogue_instruction}.

Con creatividad {temperature}:
- Si es bajo (0-0.3): mantén la narrativa más predecible y coherente
- Si es medio (0.4-0.7): equilibra creatividad con coherencia
- Si es alto (0.8-1.0): sé más experimental y único

El formato debe ser así:
[Título de la historia]

[Contenido de la historia...]"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # Configuración de la petición
        payload = {
            "messages": messages,
            "temperature": float(temperature),
            "top_p": float(top_p),
            "repeat_penalty": float(repeat_penalty),
            "model": MODEL_MAPPING[model_choice],
            "stream": False  # Asegurarnos de que no use streaming
        }

        # Realizar la petición a la API con timeout extendido y reintentos
        max_retries = 3
        retry_delay = 2  # segundos
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    API_URL,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=120  # 2 minutos de timeout
                )
                
                if response.status_code == 200:
                    story = response.json()["choices"][0]["message"]["content"].strip()
                    return story
                else:
                    error_msg = f"Error del servidor (código {response.status_code})"
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return f"⚠️ {error_msg}. Por favor, verifica que LM Studio esté ejecutándose correctamente."
                    
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return "⚠️ Error: La conexión tardó demasiado tiempo. Por favor, intenta de nuevo."
                
            except requests.exceptions.ConnectionError:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return "⚠️ Error de conexión: No se pudo conectar con LM Studio. Por favor, verifica que esté ejecutándose."
                
            except json.JSONDecodeError:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return "⚠️ Error: La respuesta del servidor no tiene el formato correcto."
                
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return f"⚠️ Error inesperado: {str(e)}"

    except Exception as e:
        return f"⚠️ Error en la preparación de la historia: {str(e)}"

def format_story(story):
    """Formatea la historia para mostrar el título más grande"""
    if isinstance(story, str) and not story.startswith("⚠️"):
        # Dividir el texto en líneas y limpiar espacios en blanco
        lines = [line.strip() for line in story.split('\n') if line.strip()]
        
        if not lines:
            return story
            
        # El título es siempre la primera línea no vacía
        title = lines[0].strip()
        # Eliminar cualquier carácter especial del título
        title = title.replace('*', '').replace('#', '').replace('-', '').strip()
        
        # El contenido es todo lo demás
        content = '\n'.join(lines[1:]).strip()
        
        # Si no hay contenido, usar todo como contenido
        if not content:
            content = title
            title = "Historia"
            
        return f'<div class="story-title">{title}</div>\n<div class="story-content">{content}</div>'
    return story

def save_as_txt(story_text):
    if not story_text or story_text.startswith("⚠️"):
        return None
        
    try:
        # Extraer título y contenido del HTML
        if '<div class="story-title">' in story_text:
            title_start = story_text.find('<div class="story-title">') + len('<div class="story-title">')
            title_end = story_text.find('</div>')
            content_start = story_text.find('<div class="story-content">') + len('<div class="story-content">')
            content_end = story_text.rfind('</div>')
            
            title = story_text[title_start:title_end].strip()
            content = story_text[content_start:content_end].strip()
        else:
            # Fallback a texto plano
            lines = story_text.split('\n', 1)
            title = lines[0].strip()
            content = lines[1].strip() if len(lines) > 1 else ""

        # Crear el contenido del archivo con formato mejorado
        txt_content = f"""
{title}
{'='*len(title)}

{content}

---
Generador de historias germangarest
Fecha: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}
"""
        
        # Crear nombre de archivo basado en el título
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_title = safe_title.replace(' ', '_')
        date = datetime.now().strftime("%d-%m-%Y")
        filename = f"{safe_title}_{date}.txt"
        
        # Guardar en la carpeta de Descargas del usuario
        downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
        txt_path = os.path.join(downloads_path, filename)
        
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(txt_content.strip())
        
        return txt_path
    except Exception as e:
        print(f"Error al guardar TXT: {str(e)}")
        return None

def generate_with_status(main_character, secondary_character, location, key_action,
                       temperature, model_choice, genre, story_length, 
                       include_dialogue, top_p, repeat_penalty):
    try:
        # Generar la historia
        story = generate_story(main_character, secondary_character, location, key_action,
                             temperature, model_choice, genre, story_length,
                             include_dialogue, top_p, repeat_penalty)
        
        # Formatear la historia
        formatted_story = format_story(story)
        
        return True, formatted_story
            
    except Exception as e:
        return True, f"⚠️ Error: {str(e)}"

# Crear la interfaz de Gradio
with gr.Blocks(theme=theme, css=css) as demo:
    gr.Markdown(
        """
        # 📚 Generador de historias germangarest
        ### Crea historias únicas con inteligencia artificial 🤖✨
        """
    )
    
    with gr.Tabs():
        with gr.Tab("✍️ Crear historia"):
            with gr.Group():
                gr.Markdown("### 👥 Personajes")
                with gr.Row():
                    with gr.Column(scale=1):
                        main_character = gr.Textbox(
                            label="🌟 Personaje principal",
                            placeholder="Ej: Germán",
                            value="",
                            info="¿Cómo se llama el protagonista? (Por defecto: Germán)"
                        )
                        secondary_character = gr.Textbox(
                            label="👤 Personaje secundario",
                            placeholder="Ej: Carlos",
                            value="",
                            info="¿Quién acompaña al protagonista? (Por defecto: Carlos)"
                        )
                    
                    with gr.Column(scale=1):
                        location = gr.Textbox(
                            label="📍 Lugar",
                            placeholder="Ej: una playa desierta",
                            value="",
                            info="¿Dónde transcurre la historia? (Por defecto: una playa desierta)"
                        )
                        key_action = gr.Textbox(
                            label="🎯 Acción clave",
                            placeholder="Ej: practicar surf en verano",
                            value="",
                            info="¿Qué evento crucial ocurre? (Por defecto: practicar surf en verano)"
                        )

            with gr.Group():
                gr.Markdown("### 🎨 Estilo de la historia")
                with gr.Row():
                    with gr.Column(scale=1):
                        model = gr.Dropdown(
                            choices=list(MODEL_MAPPING.keys()),
                            value="Ministral 8B Instruct 2410",
                            label="🤖 Modelo de IA"
                        )
                        genre = gr.Dropdown(
                            choices=[
                                "Aventura 🌎",
                                "Fantasía ✨",
                                "Misterio 🔍",
                                "Romance 💝",
                                "Comedia 😄",
                                "Terror 👻"
                            ],
                            value="Aventura 🌎",
                            label="📚 Género"
                        )
                    
                    with gr.Column(scale=1):
                        temperature = gr.Slider(
                            minimum=0.0,
                            maximum=1.0,
                            value=0.5,
                            step=0.1,
                            label="🌡️ Temperatura (creatividad)",
                            info="Controla la creatividad del texto"
                        )
                        story_length = gr.Radio(
                            choices=["Corta (~250 palabras) 📝", "Media (~500 palabras) 📄", "Larga (~1000 palabras) 📚"],
                            value="Media (~500 palabras) 📄",
                            label="📏 Longitud"
                        )

            with gr.Accordion("⚙️ Configuración Avanzada", open=False):
                with gr.Row():
                    include_dialogue = gr.Checkbox(
                        label="💬 Incluir Diálogos",
                        value=False,
                        info="¿Quieres que la historia incluya conversaciones?"
                    )
                    top_p = gr.Slider(
                        minimum=0.1,
                        maximum=1.0,
                        value=0.9,
                        step=0.1,
                        label="🎲 Diversidad (Top-P)",
                        info="Controla la variedad del vocabulario"
                    )
                    repeat_penalty = gr.Slider(
                        minimum=1.0,
                        maximum=2.0,
                        value=1.2,
                        step=0.1,
                        label="🔄 Penalización de repetición",
                        info="Evita repeticiones en el texto"
                    )

            with gr.Row():
                generate_btn = gr.Button("✨ Generar historia ✨", variant="primary", scale=1)
            
            with gr.Row():
                generating_message = gr.HTML(
                    value='<div class="generating-message">✨ Generando historia...</div>',
                    visible=False
                )
            
            story_output = gr.Markdown(
                elem_classes=["story-output"],
                value=""
            )
            
            with gr.Row():
                download_btn = gr.Button(
                    "📥 Descargar historia",
                    visible=False,
                    elem_classes=["download-button"],
                    variant="primary",
                    size="lg"
                )

        with gr.Tab("ℹ️ Guía de uso"):
            gr.Markdown(GUIDE)

    # Conectar el botón con la función
    generate_btn.click(
        fn=generate_with_status,
        inputs=[
            main_character, secondary_character, location, key_action,
            temperature, model, genre, story_length, include_dialogue, top_p, repeat_penalty
        ],
        outputs=[generating_message, story_output] 
    )
    
    # Función para descargar la historia
    def download_story(story):
        if not story:
            return gr.Warning("No hay historia para descargar")
        file_path = save_as_txt(story)
        if file_path:
            return gr.Info("Historia guardada en tu carpeta de descargas")
        return gr.Warning("No se pudo guardar la historia")
    
    # Conectar el botón de descarga
    download_btn.click(
        fn=download_story,
        inputs=[story_output],
        outputs=[]
    )
    
    # Mostrar el botón de descarga solo cuando hay una historia
    def update_download_visibility(story):
        return gr.update(visible=bool(story) and not str(story).startswith("⚠️"))
    
    story_output.change(
        fn=update_download_visibility,
        inputs=[story_output],
        outputs=[download_btn]
    )

# Iniciar la aplicación
if __name__ == "__main__":
    demo.launch(share=True, server_port=5000)
