import os
import re as _re  # Para limpiar etiquetas [WORD_DOC]
import uuid
import json
import io
import base64
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, get_flashed_messages, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI
from werkzeug.utils import secure_filename
import hashlib
from sqlalchemy.exc import IntegrityError
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import AzureOpenAIEmbeddings
from dotenv import load_dotenv
from models import db, User, Chat, Message, File, UserPrompt
from doc_export import procesar_respuesta  # Nuevo: exportación automática a Word

# Utilidad para limpiar marcadores [WORD_DOC] del texto mostrado al usuario
def clean_word_doc_markers(text):
    if not isinstance(text, str):
        return text
    try:
        cleaned = _re.sub(r"\[WORD_DOC\]", "", text)
        cleaned = _re.sub(r"\[/WORD_DOC\]", "", cleaned)
        return cleaned.strip()
    except Exception as e:
        logger.error(f"Error limpiando marcadores WORD_DOC: {e}", "app.clean_word_doc_markers")
        return text

# Detección heurística de intención de generar documento Word
def detect_word_doc_intent(message: str):
    """Detecta si el usuario está solicitando explícitamente la generación de un documento.

    Devuelve (bool, list[str]) indicando si hay intención y las razones activadas.
    """
    reasons = []
    if not isinstance(message, str) or not message.strip():
        return False, reasons
    text = message.lower()
    # Eliminamos etiquetas HTML simples para evitar ruido
    text = _re.sub(r"<[^>]+>", " ", text)

    # Disparadores explícitos (tokens manuales)
    explicit_tokens = ["!doc", "/doc", "[doc]", "<doc>"]
    for tok in explicit_tokens:
        if tok in text:
            reasons.append(f"token:{tok}")
            return True, reasons

    keywords = [
        # Español
        "documento", "word", "docx", "informe", "especificación", "especificacion", "reporte",
        "memoria", "documentación", "documentacion", "plantilla", "propuesta", "resumen ejecutivo",
        "especificaciones", "ficha técnica", "ficha tecnica", "manual", "guía", "guia", "acta",
        "acta de reunión", "minuta", "cronograma", "análisis", "analisis", "caso de uso", "casos de uso",
        # Inglés
        "document", "report", "spec", "specification", "proposal", "whitepaper", "design doc", "design document",
        "requirements", "requirement document", "architecture document", "manual", "guide", "playbook", "runbook"
    ]
    verbs = [
        # Español
        "genera", "generar", "crear", "crea", "elabora", "elaborar", "redacta", "redactar", "haz", "produce", "producir", "monta", "construye",
        # Inglés
        "generate", "create", "build", "produce", "draft", "write", "compose", "prepare"
    ]

    # Señales directas: combinación verbo + palabra clave
    for v in verbs:
        for k in keywords:
            if f"{v} un {k}" in text or f"{v} una {k}" in text or f"{v} el {k}" in text or f"{v} a {k}" in text or f"{v} {k}" in text:
                reasons.append(f"combo:{v}+{k}")
                return True, reasons

    # Palabras clave aisladas acompañadas de formato deseado o verbos
    keyword_hit = [k for k in keywords if k in text]
    verb_hit = [v for v in verbs if v in text]
    if keyword_hit and verb_hit:
        reasons.append(f"keywords:{','.join(keyword_hit[:3])}")
        reasons.append(f"verbs:{','.join(verb_hit[:3])}")
        return True, reasons

    # Exportación / conversión
    if any(kw in text for kw in keyword_hit) and ("exporta" in text or "convierte" in text or "en word" in text or "to word" in text):
        reasons.append("export_convert")
        return True, reasons

    # Patrones regex generales
    regex_patterns = [
        r"genera.+documento", r"crea.+informe", r"elabora.+documento", r"redacta.+especificaci[óo]n",
        r"(documento|informe|report) completo", r"estructura (del )?(documento|informe|report)", r"plantilla.+(documento|informe|report)",
        r"create (a )?(detailed )?(design|architecture) document", r"write (the )?spec"
    ]
    if any(_re.search(p, text) for p in regex_patterns):
        reasons.append("regex_pattern")
        return True, reasons

    # Estructuras solicitadas típicas de documentos
    structural_cues = [
        "tabla de contenidos", "table of contents", "índice", "indice", "secciones", "apartados",
        "table of content", "toc", "outline", "section 1", "section 2"
    ]
    if any(cue in text for cue in structural_cues) and keyword_hit:
        reasons.append("structural_cues")
        return True, reasons

    # Indicios de formato extenso (pide secciones numeradas)
    if _re.search(r"secci[óo]n(es)? [1-9]", text) and keyword_hit:
        reasons.append("section_numbering")
        return True, reasons

    return False, reasons
import fitz  # PyMuPDF
from PIL import Image
import numpy as np
from azure.core.credentials import AzureKeyCredential
import logger  # Importar el módulo de logging

# Cargar variables de entorno
logger.info("Iniciando carga de variables de entorno", "app.warmup")
load_dotenv()
logger.info("Variables de entorno cargadas desde archivo .env", "app.warmup")

# Configurar nivel de log según entorno
env_level = os.environ.get('FLASK_ENV')
if env_level == 'development':
    logger.set_level(logger.LEVEL_DEBUG)
    logger.info(f"Nivel de log establecido a DEBUG por entorno: {env_level}", "app.warmup")
else:
    logger.info(f"Entorno detectado: {env_level or 'producción'}", "app.warmup")

logger.info("Iniciando aplicación ChechuGPT", "app")

app = Flask(__name__)
logger.info("Inicializando aplicación Flask", "app.warmup")

# Configuración de la aplicación Flask
secret_key = os.environ.get("SECRET_KEY", "default_secret_key")
app.secret_key = secret_key
logger.info(f"Secret key configurada: {'[PERSONALIZADA]' if secret_key != 'default_secret_key' else '[VALOR POR DEFECTO]'}", "app.warmup")

# Configurar rutas de directorios desde variables de entorno
DATA_DIR = os.environ.get('DATA_DIR', os.path.join('data', 'users'))
UPLOAD_DIR = os.environ.get('UPLOAD_DIR', os.path.join('data', 'upload'))
VECTORDB_DIR = os.environ.get('VECTORDB_DIR', os.path.join('data', 'vectordb'))
INSTANCE_DIR = os.environ.get('INSTANCE_DIR', os.path.join('data', 'instance'))

# Asegurar que existan los directorios necesarios
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(VECTORDB_DIR, exist_ok=True)
os.makedirs(INSTANCE_DIR, exist_ok=True)
logger.info(f"Directorios configurados: DATA_DIR={DATA_DIR}, UPLOAD_DIR={UPLOAD_DIR}, VECTORDB_DIR={VECTORDB_DIR}, INSTANCE_DIR={INSTANCE_DIR}", "app.warmup")

app.config['UPLOAD_FOLDER'] = UPLOAD_DIR
logger.info(f"Carpeta de uploads configurada: {app.config['UPLOAD_FOLDER']}", "app.warmup")

app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # 64MB max upload
logger.info(f"Tamaño máximo de upload configurado: {app.config['MAX_CONTENT_LENGTH'] / (1024 * 1024)}MB", "app.warmup")

# Mensaje de sistema por defecto utilizado en toda la aplicación
DEFAULT_SYSTEM_PROMPT = (
    "Eres un asistente útil que responde a las preguntas del usuario de manera clara y concisa. "
    "Si no sabes la respuesta, di que no lo sabes. No inventes respuestas."
)

# Modificar la URL de la base de datos para usar la ruta absoluta en INSTANCE_DIR
database_path = os.path.abspath(os.path.join(INSTANCE_DIR, 'mar-ia-jose.db'))
# Asegurar que la ruta usa el formato correcto para SQLite (forward slashes)
database_path = database_path.replace('\\', '/')
# Configurar la URL de la base de datos
database_url = f'sqlite:///{database_path}'
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
logger.info(f"URL de base de datos configurada: {database_url}", "app.warmup")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
logger.info("SQLALCHEMY_TRACK_MODIFICATIONS desactivado", "app.warmup")

# Initialize database
db.init_app(app)

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    # Updated to use Session.get() instead of query.get() which is deprecated in SQLAlchemy 2.0
    return db.session.get(User, int(user_id))

# Configuración de Azure OpenAI
AZURE_OPENAI_ENDPOINT = os.environ.get("azure_endpoint")
AZURE_OPENAI_KEY = os.environ.get("api_key")
AZURE_OPENAI_DEPLOYMENT = os.environ.get("model_name", "gpt-35-turbo")
AZURE_OPENAI_EMBEDDING_ENDPOINT= os.environ.get("embedding_endpoint")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.environ.get("embedding_deployment")
AZURE_OPENAI_EMBEDDING_API = os.environ.get("embedding_api")
AZURE_OPENAI_EMBEDDING_APIKEY = os.environ.get("embedding_api_key")

# Configuración de DeepSeek-R1
R1_MODEL = os.environ.get("R1_model")
R1_ENDPOINT = os.environ.get("R1_endpoint")
R1_CREDENTIAL = os.environ.get("R1_credential")

# Configuración de o1-mini
O1MINI_MODEL = os.environ.get("model_name_o1mini")
O1MINI_ENDPOINT = os.environ.get("azure_endpoint_o1mini")
O1MINI_KEY = os.environ.get("api_key_o1mini")
O1MINI_API_VERSION = os.environ.get("api_version_o1mini")

# Configuración de MAI-DS-R1
MAI_DS_R1_MODEL = os.environ.get("MAI_DS_R1_model")
MAI_DS_R1_ENDPOINT = os.environ.get("MAI_DS_R1_endpoint")
MAI_DS_R1_API_KEY = os.environ.get("MAI_DS_R1_api_key")

# Definir modelos disponibles
def get_available_models():
    """Obtiene la lista de modelos disponibles en la configuración"""
    models = [
        {
            "id": AZURE_OPENAI_DEPLOYMENT,
            "name": AZURE_OPENAI_DEPLOYMENT,
            "endpoint": AZURE_OPENAI_ENDPOINT,
            "api_key": AZURE_OPENAI_KEY,
            "api_version": os.environ.get("_version", "2023-05-15")
        }
    ]    # Añadir DeepSeek-R1 si está configurado
    if R1_MODEL and R1_ENDPOINT and R1_CREDENTIAL:
        models.append({
            "id": R1_MODEL,
            "name": "DeepSeek-R1",
            "endpoint": R1_ENDPOINT,
            "api_key": R1_CREDENTIAL,
            "api_version": os.environ.get("api_version", "2023-05-15"),
            "model_type": "azure_ai_inference"
        })
    
    # Añadir o1-mini si está configurado
    if O1MINI_MODEL and O1MINI_ENDPOINT and O1MINI_KEY:
        models.append({
            "id": O1MINI_MODEL,
            "name": "o1-mini",
            "endpoint": O1MINI_ENDPOINT,
            "api_key": O1MINI_KEY,
            "api_version": O1MINI_API_VERSION
        })
    
    # Añadir MAI-DS-R1 si está configurado
    if MAI_DS_R1_MODEL and MAI_DS_R1_ENDPOINT and MAI_DS_R1_API_KEY:
        models.append({
            "id": MAI_DS_R1_MODEL,
            "name": "MAI-DS-R1",
            "endpoint": MAI_DS_R1_ENDPOINT,
            "api_key": MAI_DS_R1_API_KEY,
            "api_version": os.environ.get("api_version", "2023-05-15"),
            "model_type": "azure_ai_inference"
        })

    return models

# Obtener modelos disponibles
AVAILABLE_MODELS = get_available_models()

# Función para obtener cliente de OpenAI según el modelo seleccionado
def get_openai_client(model_id=None):
    """Obtiene un cliente de OpenAI configurado para el modelo especificado"""
    # Si no se especifica modelo, usar el predeterminado
    logger.debug(f"Solicitando cliente OpenAI para modelo: {model_id or 'predeterminado'}", "app.get_openai_client")
    if not model_id:
        return AzureOpenAI(
            api_key=AZURE_OPENAI_KEY,
            api_version=os.environ.get("api_version", "2023-05-15"),
            azure_endpoint=AZURE_OPENAI_ENDPOINT
        )

    # Buscar configuración del modelo seleccionado
    selected_model = next((model for model in AVAILABLE_MODELS if model["id"] == model_id), None)

    if not selected_model:
        # Si no se encuentra el modelo, usar el predeterminado
        logger.warning(f"Modelo solicitado '{model_id}' no encontrado, usando predeterminado", "app.get_openai_client")
        return AzureOpenAI(
            api_key=AZURE_OPENAI_KEY,
            api_version=os.environ.get("api_version", "2023-05-15"),
            azure_endpoint=AZURE_OPENAI_ENDPOINT
        )
    
    # Verificar si es un modelo que usa Azure AI Inference SDK
    if selected_model.get("model_type") == "azure_ai_inference":
        try:
            # Importar el cliente de Azure AI Inference
            from azure.ai.inference import ChatCompletionsClient
            from azure.core.credentials import AzureKeyCredential
            
            logger.debug(f"Creando cliente Azure AI Inference para modelo: {model_id}", "app.get_openai_client")
            return ChatCompletionsClient(
                endpoint=selected_model["endpoint"],
                credential=AzureKeyCredential(selected_model["api_key"])
            )
        except ImportError:
            logger.error(f"No se pudo importar el módulo azure.ai.inference. Asegúrese de instalar la dependencia: pip install azure-ai-inference", "app.get_openai_client")
            # Fallback al cliente predeterminado
            return AzureOpenAI(
                api_key=AZURE_OPENAI_KEY,
                api_version=os.environ.get("api_version", "2023-05-15"),
                azure_endpoint=AZURE_OPENAI_ENDPOINT
            )

    # Crear cliente con la configuración del modelo seleccionado
    logger.debug(f"Creando cliente para modelo: {model_id}", "app.get_openai_client")
    return AzureOpenAI(
        api_key=selected_model["api_key"],
        api_version=selected_model["api_version"],
        azure_endpoint=selected_model["endpoint"]
    )

# Inicializar cliente predeterminado de Azure OpenAI
client = get_openai_client()

# Inicializar embeddings para RAG
embeddings = AzureOpenAIEmbeddings(
    azure_deployment=AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
    openai_api_key=AZURE_OPENAI_EMBEDDING_APIKEY,
    azure_endpoint=AZURE_OPENAI_EMBEDDING_ENDPOINT,
    api_version=AZURE_OPENAI_EMBEDDING_API,
)


def get_user_id():
    """Obtiene el ID del usuario actual o crea uno temporal para sesiones no autenticadas"""
    if current_user.is_authenticated:
        logger.debug(f"Usuario autenticado: {current_user.username} (ID: {current_user.id})", "app.get_user_id")
        return current_user.id
    elif 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
        logger.debug(f"Creando ID temporal para sesión: {session['user_id']}", "app.get_user_id")
    return session['user_id']

def save_chat_history(user_id, messages, system_message=None, title=None, file_hashes=None):
    """Guarda el historial de chat en un archivo JSON"""
    chat_id = session.get('chat_id', str(uuid.uuid4()))
    session['chat_id'] = chat_id
    logger.debug(f"Guardando historial de chat para usuario {user_id}, chat_id: {chat_id}", "app.save_chat_history")

    filename = os.path.join(DATA_DIR, f"{user_id}_{chat_id}.json")

    # Determinar el título del chat
    if not title and messages:
        # Usar el primer mensaje como título si no se proporciona uno
        preview = messages[0]['content'][:50] + '...' if messages else 'Chat vacío'
        title = preview

    # Asegurar un título por defecto
    if not title:
        title = 'Nueva conversación'

    # Usar los file_hashes proporcionados o los de la sesión actual
    if file_hashes is None:
        file_hashes = session.get('file_hashes', [])

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump({
            'chat_id': chat_id,
            'timestamp': datetime.now().isoformat(),
            'messages': messages,
            'system_message': system_message,
            'title': title,
            'file_hashes': file_hashes
        }, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Chat guardado: {title[:30]}... (ID: {chat_id})", "app.save_chat_history")
    return chat_id


def create_new_chat_session(user_id, system_message=None, title=None):
    """Crea un nuevo chat para el usuario asegurando valores por defecto consistentes."""
    resolved_system_message = (system_message or '').strip()

    if not resolved_system_message:
        resolved_system_message = DEFAULT_SYSTEM_PROMPT
        if current_user.is_authenticated:
            user_default = UserPrompt.query.filter_by(user_id=current_user.id, name='Default').first()
            if user_default and user_default.prompt_text:
                resolved_system_message = user_default.prompt_text

    resolved_title = (title or '').strip() or 'Nueva conversación'

    chat_id = str(uuid.uuid4())
    session['chat_id'] = chat_id
    session['file_hashes'] = []

    save_chat_history(user_id, [], resolved_system_message, resolved_title)

    return {
        "chat_id": chat_id,
        "system_message": resolved_system_message,
        "title": resolved_title
    }


def load_chat_history(user_id, chat_id=None):
    """Carga el historial de chat desde un archivo JSON"""
    if chat_id:
        filename = os.path.join(DATA_DIR, f"{user_id}_{chat_id}.json")
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                session['chat_id'] = chat_id
                return data['messages']

    # Si no hay chat_id o no existe el archivo, devolver una lista vacía
    return []

def get_chat_data(user_id, chat_id):
    """Obtiene todos los datos de un chat específico"""
    if chat_id:
        filename = os.path.join(DATA_DIR, f"{user_id}_{chat_id}.json")
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                logger.debug(f"Cargando datos de chat: {chat_id}", "app.get_chat_data")
                return json.load(f)    # Si no hay chat_id o no existe el archivo, devolver un diccionario vacío
    logger.debug(f"No se encontró chat con ID: {chat_id}", "app.get_chat_data")
    return {"messages": [], "system_message": None, "title": None, "file_hashes": []}

def get_user_chats(user_id):
    """Obtiene la lista de chats del usuario"""
    chats = []
    for filename in os.listdir(DATA_DIR):
        if filename.startswith(f"{user_id}_") and filename.endswith('.json'):
            chat_id = filename.replace(f"{user_id}_", "").replace('.json', "")
            with open(os.path.join(DATA_DIR, filename), 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Usar el título personalizado si existe, de lo contrario usar el primer mensaje
                preview = data.get('title') or (data['messages'][0]['content'][:50] + '...' if data['messages'] else 'Chat vacío')
                chats.append({
                    'id': chat_id,
                    'timestamp': data.get('timestamp', ''),
                    'preview': preview,
                    'system_message': data.get('system_message')
                })

    # Ordenar por timestamp, más reciente primero
    chats.sort(key=lambda x: x['timestamp'], reverse=True)
    return chats


def ensure_default_user_prompt(user_id, commit=False):
    """Garantiza que el usuario tenga un prompt 'Default'.

    Args:
        user_id (int): Identificador del usuario autenticado.
        commit (bool): Si es True realiza commit inmediato tras crear el prompt.

    Returns:
        bool: True si se creó un nuevo prompt, False si ya existía o no se pudo crear.
    """
    if user_id is None:
        return False

    existing_prompt = UserPrompt.query.filter_by(user_id=user_id, name='Default').first()
    if existing_prompt:
        return False

    default_prompt = UserPrompt(user_id=user_id, name='Default', prompt_text=DEFAULT_SYSTEM_PROMPT)
    db.session.add(default_prompt)

    if commit:
        try:
            db.session.commit()
            logger.info(
                f"Prompt 'Default' creado automáticamente para el usuario {user_id}",
                "app.ensure_default_user_prompt"
            )
            return True
        except IntegrityError:
            db.session.rollback()
            logger.warning(
                f"Intento duplicado de crear prompt 'Default' para el usuario {user_id}",
                "app.ensure_default_user_prompt"
            )
            return False

    return True


def backfill_missing_default_prompts():
    """Crea el prompt 'Default' para usuarios existentes que aún no lo tienen."""
    users = User.query.all()
    created_count = 0

    for user in users:
        try:
            created = ensure_default_user_prompt(user.id, commit=False)
            if created:
                created_count += 1
        except Exception as exc:
            db.session.rollback()
            logger.error(
                f"Error creando prompt 'Default' para usuario {user.id}: {exc}",
                "app.backfill_missing_default_prompts"
            )

    if created_count:
        try:
            db.session.commit()
            logger.info(
                f"Se añadieron prompts 'Default' para {created_count} usuarios existentes",
                "app.backfill_missing_default_prompts"
            )
        except IntegrityError as exc:
            db.session.rollback()
            logger.error(
                f"Error al confirmar la creación de prompts 'Default' para usuarios existentes: {exc}",
                "app.backfill_missing_default_prompts"
            )

def extract_images_from_pdf(file_path):
    """Extrae imágenes de un archivo PDF y realiza OCR o genera descripciones usando GPT-4o"""
    image_texts = []
    logger.info(f"Iniciando extracción de imágenes del PDF: {os.path.basename(file_path)}", "app.extract_images_from_pdf")
    doc = fitz.Document(file_path)  # Usando Document en lugar de open

    logger.debug(f"Procesando PDF con {len(doc)} páginas", "app.extract_images_from_pdf")

    # Crear directorio temporal para imágenes si no existe
    temp_img_dir = os.path.join(UPLOAD_DIR, 'temp_images')
    os.makedirs(temp_img_dir, exist_ok=True)

    for page_num, page in enumerate(doc):
        # Extraer imágenes de la página
        image_list = page.get_images(full=True)
        print(f"\n[DEBUG] Procesando página {page_num+1}/{len(doc)} - Encontradas {len(image_list)} imágenes")

        for img_index, img in enumerate(image_list):
            print(f"\n[DEBUG] Procesando imagen {img_index+1}/{len(image_list)} de la página {page_num+1}")
            xref = img[0]  # número de referencia de la imagen
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]

            # Convertir bytes a imagen PIL
            image = Image.open(io.BytesIO(image_bytes))
            print(f"[DEBUG] Dimensiones de la imagen: {image.width}x{image.height}")

            try:
                # Convertir imagen RGBA a RGB si es necesario
                if image.mode == 'RGBA':
                    print(f"[DEBUG] Convirtiendo imagen de formato RGBA a RGB")
                    # Crear un fondo blanco y componer la imagen RGBA sobre él
                    rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                    rgb_image.paste(image, mask=image.split()[3])  # Usar canal alfa como máscara
                    image = rgb_image
                elif image.mode != 'RGB':
                    print(f"[DEBUG] Convirtiendo imagen de formato {image.mode} a RGB")
                    image = image.convert('RGB')
                
                # Guardar la imagen temporalmente
                temp_img_path = os.path.join(temp_img_dir, f"temp_img_{page_num}_{img_index}.jpg")
                image.save(temp_img_path)
                print(f"[DEBUG] Imagen guardada temporalmente en: {temp_img_path}")

                # Convertir imagen a base64 para enviarla a GPT-4o
                buffered = io.BytesIO()
                image.save(buffered, format="JPEG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                img_url = f"data:image/jpeg;base64,{img_base64}"
                print(f"[DEBUG] Imagen convertida a base64 para envío al modelo")

                # Llamar a GPT-4o para extraer texto y generar descripción
                print(f"[DEBUG] Enviando imagen a modelo para OCR/descripción...")
                model_client = get_openai_client("gpt-4.1")
                response = model_client.chat.completions.create(
                    model="gpt-4.1",
                    messages=[
                        {"role": "system", "content": "Eres un asistente especializado en extraer texto de imágenes y describir su contenido. Si hay texto visible en la imagen, extráelo con precisión. Si no hay texto o es poco relevante, proporciona una descripción detallada de lo que ves."},
                        {"role": "user", "content": [
                            {"type": "text", "text": "Reconoce el texto de la imagen y donde haya una imagen, describela. La descripcion de la imagen ha de estar ubicada justo donde estaba la imagen en el documento."},
                            {"type": "image_url", "image_url": {"url": img_url}}
                        ]}
                    ],                                     
                )

                result = response.choices[0].message.content
                print(f"[DEBUG] Respuesta recibida de GPT-4o ({len(result)} caracteres)")

                # Eliminar la imagen temporal
                os.remove(temp_img_path)
                print(f"[DEBUG] Imagen temporal eliminada")

                # Determinar si el resultado es principalmente texto extraído o una descripción
                if "TEXTO EXTRAÍDO:" in result or "TEXTO ENCONTRADO:" in result or result.count('\n') > 3:
                    # Parece ser principalmente texto extraído
                    image_texts.append(f"[TEXTO DE IMAGEN - Página {page_num+1}, Imagen {img_index+1}]: {result}")
                    print(f"\n[OCR RESULTADO] Página {page_num+1}, Imagen {img_index+1}:")
                    print("-" * 80)
                    print(result)
                    print("-" * 80)
                    print(f"[DEBUG] Texto extraído con el modelo: {result[:100]}..." if len(result) > 100 else f"[DEBUG] Texto extraído con GPT-4o: {result}")
                else:
                    # Parece ser principalmente una descripción
                    image_texts.append(f"[DESCRIPCIÓN DE IMAGEN - Página {page_num+1}, Imagen {img_index+1}]: {result}")
                    print(f"\n[DESCRIPCIÓN RESULTADO] Página {page_num+1}, Imagen {img_index+1}:")
                    print("-" * 80)
                    print(result)
                    print("-" * 80)
                    print(f"[DEBUG] Descripción generada con GPT-4.1: {result[:100]}..." if len(result) > 100 else f"[DEBUG] Descripción generada con GPT-4o: {result}")

            except Exception as e:
                error_msg = f"Error al procesar la imagen con GPT-4.1: {str(e)}"
                print(f"[ERROR] {error_msg}")
                image_texts.append(f"[ERROR EN PROCESAMIENTO DE IMAGEN - Página {page_num+1}, Imagen {img_index+1}]: No se pudo procesar la imagen. Error: {str(e)}")

    print(f"\n[DEBUG] Procesamiento de PDF completado. Total de textos/descripciones extraídos: {len(image_texts)}")
    doc.close()
    return image_texts

def process_file(file_path, process_images=True):
    """Procesa un archivo para RAG
    
    Args:
        file_path: Ruta al archivo a procesar
        process_images: Si es True, procesa las imágenes en PDFs con OCR. Si es False, solo procesa el texto.
    """
    file_extension = os.path.splitext(file_path)[1].lower()
    logger.info(f"Procesando archivo: {os.path.basename(file_path)} ({file_extension})", "app.process_file")    
    
    if file_extension == '.pdf':
        # Extraer imágenes y realizar OCR antes de cargar el documento solo si process_images es True
        image_texts = []
        if file_extension == '.pdf' and process_images:
            try:
                logger.info("Iniciando extracción de imágenes del PDF", "app.process_file")
                image_texts = extract_images_from_pdf(file_path)
            except Exception as e:
                error_msg = f"Error al extraer imágenes del PDF: {str(e)}"
                logger.error(error_msg, "app.process_file")
                print(error_msg)
                # Continuar con el procesamiento del PDF sin las imágenes
                image_texts = []  # Asegurar que está vacío para no afectar el resto del proceso

        # Cargar el documento normalmente
        try:
            loader = PyPDFLoader(file_path)
        except Exception as e:
            error_msg = f"Error al cargar el PDF con PyPDFLoader: {str(e)}"
            logger.error(error_msg, "app.process_file")
            # Intentar con alternativa
            from langchain_community.document_loaders import PyPDFium2Loader
            try:
                loader = PyPDFium2Loader(file_path)
                logger.info("PDF cargado con éxito usando PyPDFium2Loader como alternativa", "app.process_file")
            except Exception as e2:
                # Si todo falla, intentar con un loader más básico
                from langchain_community.document_loaders import UnstructuredPDFLoader
                try:
                    loader = UnstructuredPDFLoader(file_path)
                    logger.info("PDF cargado con éxito usando UnstructuredPDFLoader como última alternativa", "app.process_file")
                except Exception as e3:
                    # Error fatal, no se puede procesar el PDF
                    error_msg = f"No se pudo cargar el PDF con ningún cargador disponible: {str(e3)}"
                    logger.error(error_msg, "app.process_file")
                    raise ValueError(error_msg)
    elif file_extension == '.docx':
        loader = Docx2txtLoader(file_path)
    elif file_extension in ['.txt', '.md', '.csv']:
        loader = TextLoader(file_path)
    else:
        error_msg = f"Formato de archivo no soportado: {file_extension}"
        logger.error(error_msg, "app.process_file")
        raise ValueError(error_msg)

    try:
        documents = loader.load()

        # Verificar si hay documentos antes de procesarlos
        if not documents:
            raise ValueError("No se pudo extraer contenido del archivo")

        # Si hay textos de imágenes, añadirlos como documentos adicionales
        if file_extension == '.pdf' and image_texts:
            # Crear un documento adicional con los textos de las imágenes
            for i, text in enumerate(image_texts):
                # Añadir cada texto de imagen como un documento separado
                from langchain_core.documents import Document
                img_doc = Document(
                    page_content=text,
                    metadata={"source": file_path, "page": f"imagen-{i+1}"}
                )
                documents.append(img_doc)

        # Dividir documentos en chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        chunks = text_splitter.split_documents(documents)

        # Verificar si hay chunks antes de crear la base de datos vectorial
        if not chunks:
            raise ValueError("No se pudo dividir el contenido del archivo en fragmentos")

        # Crear o actualizar la base de datos vectorial
        file_hash = hashlib.md5(open(file_path, 'rb').read()).hexdigest()
        db_path = os.path.join(VECTORDB_DIR, file_hash)

        # Crear vectorstore con FAISS
        vectorstore = FAISS.from_documents(chunks, embeddings)
        vectorstore.save_local(db_path)

        return file_hash, len(chunks)
    except Exception as e:
        # Capturar errores específicos y proporcionar un mensaje más descriptivo
        raise ValueError(f"Error al procesar el archivo: {str(e)}")

def query_documents(query, file_hashes, k=3):
    """Consulta documentos relevantes para RAG"""
    if not file_hashes:
        return []

    results = []
    for file_hash in file_hashes:
        db_path = os.path.join(VECTORDB_DIR, file_hash)
        if os.path.exists(db_path):
            # Add allow_dangerous_deserialization parameter when loading the vector store
            vectorstore = FAISS.load_local(db_path, embeddings, allow_dangerous_deserialization=True)
            docs = vectorstore.similarity_search(query, k=k)
            results.extend(docs)

    # Ordenar por relevancia y limitar a los k más relevantes
    results = sorted(results, key=lambda x: x.metadata.get('score', 0), reverse=True)[:k]
    return results

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de inicio de sesión"""
    if current_user.is_authenticated:
        logger.debug(f"Usuario ya autenticado: {current_user.username}, redirigiendo a index", "app.login")
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        logger.debug(f"Intento de inicio de sesión para usuario: {username}", "app.login")

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            logger.info(f"Inicio de sesión exitoso: {username}", "app.login")
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            logger.warning(f"Intento de inicio de sesión fallido para usuario: {username}", "app.login")
            flash('Usuario o contraseña incorrectos', 'error')

    return render_template('login.html', messages=get_flashed_messages(with_categories=True))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Página de registro de usuario"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Validar datos
        if password != confirm_password:
            flash('Las contraseñas no coinciden', 'error')
            return render_template('register.html', messages=get_flashed_messages(with_categories=True))

        # Verificar si el usuario o email ya existen
        if User.query.filter_by(username=username).first():
            flash('El nombre de usuario ya está en uso', 'error')
            return render_template('register.html', messages=get_flashed_messages(with_categories=True))

        if User.query.filter_by(email=email).first():
            flash('El correo electrónico ya está registrado', 'error')
            return render_template('register.html', messages=get_flashed_messages(with_categories=True))

        # Crear nuevo usuario y su prompt por defecto en una única transacción
        try:
            user = User(username=username, email=email)
            user.set_password(password)

            db.session.add(user)
            db.session.flush()  # Obtener ID antes del commit

            ensure_default_user_prompt(user.id, commit=False)

            db.session.commit()
            logger.info(f"Usuario registrado correctamente: {username}", "app.register")
        except Exception as exc:
            db.session.rollback()
            logger.error(f"Error al registrar usuario {username}: {exc}", "app.register")
            flash('Ocurrió un error al completar el registro. Inténtalo nuevamente.', 'error')
            return render_template('register.html', messages=get_flashed_messages(with_categories=True))

        flash('Registro exitoso. Ahora puedes iniciar sesión.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', messages=get_flashed_messages(with_categories=True))

@app.route('/logout')
@login_required
def logout():
    """Cerrar sesión"""
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
def index():
    """Página principal de la aplicación"""
    if not current_user.is_authenticated:
        return redirect(url_for('login'))

    user_id = get_user_id()
    chats = get_user_chats(user_id)
    
    # Determinar el chat que se abrirá automáticamente
    if chats:
        # Tomar el chat más reciente (el primero de la lista, ya que están ordenados por timestamp descendente)
        latest_chat = chats[0]
        chat_id = latest_chat['id']
        logger.debug(f"Abriendo último chat: {latest_chat['preview'][:30]}... (ID: {chat_id})", "app.index")
        # Guardar el chat_id en la sesión
        session['chat_id'] = chat_id
        
        # Cargar los file_hashes específicos del chat
        chat_data = get_chat_data(user_id, chat_id)
        session['file_hashes'] = chat_data.get('file_hashes', [])
        logger.debug(f"Cargando file_hashes para chat inicial: {len(session['file_hashes'])} archivos", "app.index")
    else:
        # No hay chats existentes, crear uno nuevo
        logger.debug(f"No hay chats existentes, creando uno nuevo", "app.index")
        chat_id = str(uuid.uuid4())
        session['chat_id'] = chat_id
        # Inicializar file_hashes vacíos para el nuevo chat
        session['file_hashes'] = []
        # Crear un nuevo chat con título predeterminado
        save_chat_history(user_id, [], None, "Nueva conversación")
        # Actualizar la lista de chats
        chats = get_user_chats(user_id)

    return render_template('index.html', chats=chats)

@app.route('/api/chat', methods=['POST'])
def chat():
    """Endpoint para procesar mensajes de chat"""
    data = request.json
    user_message = data.get('message', '')
    chat_id = data.get('chat_id')
    model_id = data.get('model_id')  # Obtener el modelo seleccionado
    custom_system_message = data.get('system_message')  # Obtener mensaje de sistema personalizado

    user_id = get_user_id()

    # Cargar historial de chat existente o crear uno nuevo
    messages = load_chat_history(user_id, chat_id)

    # Obtener datos completos del chat para acceder al mensaje del sistema guardado
    chat_data = get_chat_data(user_id, chat_id)
    saved_system_message = chat_data.get('system_message')
    
    # Usar los file_hashes específicos del chat actual
    file_hashes = chat_data.get('file_hashes', [])

    # Procesar el mensaje del usuario para detectar imágenes en formato base64
    # Verificar si el mensaje contiene etiquetas de imagen HTML
    contains_images = '<img src="data:image/' in user_message

    # Añadir mensaje del usuario
    if contains_images:
        # Extraer todas las imágenes base64 del mensaje HTML
        import re
        try:
            from bs4 import BeautifulSoup
            # Crear un objeto BeautifulSoup para analizar el HTML
            soup = BeautifulSoup(user_message, 'html.parser')
        except ImportError:
            logger.error("No se pudo importar BeautifulSoup. Instalando la dependencia...", "app.chat")
            # Manejar el caso donde bs4 no está instalado
            import subprocess
            subprocess.check_call(["pip", "install", "beautifulsoup4"])
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(user_message, 'html.parser')

        # Extraer el texto sin las etiquetas de imagen
        text_content = soup.get_text()

        # Extraer todas las imágenes
        img_tags = soup.find_all('img')
        image_urls = [img.get('src') for img in img_tags if img.get('src') and img.get('src').startswith('data:image/')]

        # Crear un mensaje multimodal para GPT-4o
        content = []

        # Añadir el texto si existe
        if text_content.strip():
            content.append({"type": "text", "text": text_content.strip()})

        # Añadir cada imagen como un componente de tipo imagen, validando el formato base64
        for img_url in image_urls:
            # Verificar que la imagen tenga datos base64 válidos
            if 'base64,' in img_url:
                base64_parts = img_url.split('base64,')
                if len(base64_parts) > 1 and base64_parts[1].strip():
                    try:
                        # Intentar decodificar para verificar que es base64 válido
                        base64.b64decode(base64_parts[1])
                        content.append({"type": "image_url", "image_url": {"url": img_url}})
                    except Exception as e:
                        logger.warning(f"Error al decodificar base64: {e}", "app.chat")
                else:
                    logger.warning("Formato de imagen incorrecto: datos base64 vacíos", "app.chat")
            else:
                logger.warning(f"Formato de imagen incorrecto: {img_url[:30]}...", "app.chat")

        # Añadir el mensaje multimodal al historial
        messages.append({"role": "user", "content": content})
    else:
        # Si no hay imágenes, añadir el mensaje como texto normal
        messages.append({"role": "user", "content": user_message})

    # Detectar intención de documento antes de construir el system prompt
    intent_detected, intent_reasons = detect_word_doc_intent(user_message)
    if env_level == 'development':
        logger.debug(f"Intent detection: detected={intent_detected} reasons={intent_reasons}", "app.chat.intent")

    # Realizar RAG si hay archivos subidos
    context = ""
    if file_hashes:
        relevant_docs = query_documents(user_message, file_hashes)
        if relevant_docs:
            context = "Información relevante de los documentos:\n\n"
            for i, doc in enumerate(relevant_docs):
                context += f"{i+1}. {doc.page_content}\n\n"

    # Preparar mensajes para la API
    api_messages = []

    # Determinar qué mensaje de sistema usar (prioridad: mensaje enviado en la solicitud > mensaje guardado > mensaje predeterminado)
    system_message = custom_system_message or saved_system_message

    # Si no hay mensaje personalizado y hay contexto, usar el mensaje con contexto
    if not system_message and context:
        system_message = f"""Eres un asistente útil. Utiliza la siguiente información de los documentos para responder a las preguntas del usuario:

{context}

Si la información no es suficiente para responder, utiliza tu conocimiento general pero indica que estás complementando con información que no está en los documentos."""
    # Si no hay mensaje personalizado ni contexto, usar el mensaje predeterminado
    elif not system_message:
        system_message = DEFAULT_SYSTEM_PROMPT
    # Si hay mensaje personalizado y contexto, añadir el contexto al mensaje personalizado
    elif context:
        system_message = f"{system_message}\n\nAdemás, utiliza la siguiente información de los documentos para responder:\n\n{context}"

    # Si se detectó intención de documento, reforzar instrucciones para forzar bloque [WORD_DOC]
    if intent_detected:
        doc_instruction = (
            "\n\nIMPORTANTE: El usuario solicita un documento formal. Debes responder UNICAMENTE con un "
            "bloque delimitado por [WORD_DOC] y [/WORD_DOC] que contenga TODO el contenido del documento en Markdown "
            "estructurado (título principal con #, secciones con ##, listas, tablas si procede, código si es necesario). "
            "No añadas texto fuera de ese bloque. Incluye una estructura lógica, y si procede un índice opcional al inicio."
        )
        system_message += doc_instruction
    else:
        # Instrucción ligera siempre presente para que el modelo conozca el mecanismo
        system_message += "\n\nNOTA: Si el usuario pide explícitamente un documento (informe, especificación, report, proposal) responde usando un único bloque [WORD_DOC] ... [/WORD_DOC] con el documento en Markdown estructurado."

    # Determinar el deployment a usar
    deployment = model_id if model_id else AZURE_OPENAI_DEPLOYMENT
    
    # Verificar si el modelo es o1-mini, que no soporta mensajes con rol 'system'
    is_o1mini = deployment == O1MINI_MODEL
    
    # Verificar si es un modelo que usa Azure AI Inference SDK
    selected_model = next((model for model in AVAILABLE_MODELS if model["id"] == model_id), None)
    is_azure_ai_inference = selected_model and selected_model.get("model_type") == "azure_ai_inference"
    
    # Si no es o1-mini, añadir el mensaje de sistema normalmente
    if not is_o1mini:
        api_messages.append({"role": "system", "content": system_message})
    
    # Añadir historial de conversación (limitado a los últimos 10 mensajes)
    messages_to_add = messages[-10:]
    
    # Para o1-mini, si hay mensajes de usuario, añadir el contenido del sistema al primer mensaje
    if is_o1mini and messages_to_add and messages_to_add[0]["role"] == "user":
        logger.info(f"Modelo o1-mini detectado. Adaptando formato de mensajes sin rol 'system'", "app.chat")
        # Crear una copia del primer mensaje para no modificar el original
        first_msg = messages_to_add[0].copy()
        
        # Si el contenido es una lista (mensaje multimodal), añadir al principio
        if isinstance(first_msg["content"], list):
            # Añadir el mensaje de sistema como primer elemento de texto
            first_msg["content"].insert(0, {"type": "text", "text": f"{system_message}\n\nPregunta del usuario: "})
        else:
            # Si es texto simple, concatenar
            first_msg["content"] = f"{system_message}\n\nPregunta del usuario: {first_msg['content']}"
        
        # Reemplazar el primer mensaje con la versión modificada
        api_messages.append(first_msg)
        # Añadir el resto de mensajes sin modificar
        api_messages.extend(messages_to_add[1:])
    else:
        # Para otros modelos o si no hay mensajes de usuario, añadir todos los mensajes normalmente
        api_messages.extend(messages_to_add)    # Obtener el cliente para el modelo seleccionado
    model_client = get_openai_client(model_id)
    
    # Llamar a la API según el tipo de modelo
    if is_azure_ai_inference:
        try:
            # Importar el módulo necesario para Azure AI Inference
            from azure.ai.inference.models import SystemMessage, UserMessage, AssistantMessage
            
            # Convertir mensajes al formato de Azure AI Inference
            inference_messages = []
            for msg in api_messages:
                if msg["role"] == "system":
                    inference_messages.append(SystemMessage(content=msg["content"]))
                elif msg["role"] == "user":
                    # Manejar contenido multimodal si es necesario
                    if isinstance(msg["content"], list):
                        # Por ahora, extraer solo el texto para compatibilidad
                        text_content = ""
                        for item in msg["content"]:
                            if isinstance(item, dict) and item.get("type") == "text":
                                text_content += item.get("text", "")
                        inference_messages.append(UserMessage(content=text_content))
                    else:
                        inference_messages.append(UserMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    inference_messages.append(AssistantMessage(content=msg["content"]))
            
            # Realizar llamada a la API de Azure AI Inference
            logger.debug(f"Llamando a Azure AI Inference con {len(inference_messages)} mensajes para modelo {model_id}", "app.chat")
            
            # El parámetro model no es necesario para Azure AI Inference porque ya está configurado en el endpoint
            response = model_client.complete(
                messages=inference_messages,
                temperature=1.0,
                max_tokens=4090
            )
            
            logger.debug(f"Respuesta recibida de Azure AI Inference: {type(response)}", "app.chat")
            
            # Extraer respuesta
            # La estructura de respuesta es diferente en Azure AI Inference
            if hasattr(response.choices[0], 'message'):
                assistant_message = response.choices[0].message.content
            elif hasattr(response.choices[0], 'delta'):
                assistant_message = response.choices[0].delta.content
            else:
                # Intentar obtener la respuesta de manera alternativa
                logger.debug(f"Estructura de respuesta desconocida: {response}", "app.chat")
                assistant_message = str(response.choices[0])
                
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"Error al usar Azure AI Inference: {str(e)}", "app.chat")
            logger.error(f"Traceback completo: {error_traceback}", "app.chat")
            
            # Intenta obtener más información sobre el error
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logger.error(f"Respuesta de error del API: {e.response.text}", "app.chat")
            
            # Fallback a la API estándar
            logger.info(f"Intentando fallback a la API estándar para el modelo {model_id}", "app.chat")
            try:
                response = model_client.chat.completions.create(
                    model=model_id if model_id else AZURE_OPENAI_DEPLOYMENT,
                    messages=api_messages,
                    temperature=1.0,
                    max_tokens=4090
                )
                assistant_message = response.choices[0].message.content
            except Exception as fallback_error:
                logger.error(f"Error en fallback a API estándar: {str(fallback_error)}", "app.chat")
                assistant_message = "Lo siento, hubo un problema al comunicarse con el modelo de IA. Por favor, intenta de nuevo o selecciona otro modelo."
    # Para o1-mini, usar max_completion_tokens en lugar de max_tokens
    elif is_o1mini:
        logger.info(f"Usando parámetro max_completion_tokens para modelo o1-mini", "app.chat")
        response = model_client.chat.completions.create(
            model=model_id if model_id else AZURE_OPENAI_DEPLOYMENT,
            messages=api_messages,
            temperature=1.0,
            max_completion_tokens=4090
        )
        assistant_message = response.choices[0].message.content
    else:
        response = model_client.chat.completions.create(
            model=model_id if model_id else AZURE_OPENAI_DEPLOYMENT,
            messages=api_messages,
            temperature=1.0,
            max_tokens=4090
            # El parámetro max_tokens_per_message no es compatible con la versión actual de la API
        )
        assistant_message = response.choices[0].message.content

    # Añadir respuesta al historial
    messages.append({"role": "assistant", "content": assistant_message})

    # Guardar historial actualizado with el mensaje de sistema si se proporcionó uno nuevo
    if custom_system_message:
        system_message_to_save = custom_system_message
    else:
        system_message_to_save = saved_system_message

    chat_id = save_chat_history(user_id, messages, system_message_to_save, chat_data.get('title'))

    # Fallback: si había intención de documento y el modelo NO devolvió bloque, auto-envolver
    auto_wrapped = False
    auto_wrapped_reason = None
    # Fallback 1: había intención clara pero no bloque
    if intent_detected and "[WORD_DOC]" not in assistant_message:
        assistant_message = f"[WORD_DOC]\n{assistant_message.strip()}\n[/WORD_DOC]"
        auto_wrapped = True
        auto_wrapped_reason = "intent_detected_no_block"
        if env_level == 'development':
            logger.debug("Auto-wrap aplicado (intent_detected_no_block)", "app.chat.autowrap")
    # Fallback 2: no detectado pero salida parece estructurada tipo documento (varios headings + longitud)
    if not auto_wrapped and not intent_detected:
        heading_count = len(_re.findall(r"^#{1,3} ", assistant_message, flags=_re.MULTILINE))
        if heading_count >= 3 and len(assistant_message) > 400 and "[WORD_DOC]" not in assistant_message:
            assistant_message = f"[WORD_DOC]\n{assistant_message.strip()}\n[/WORD_DOC]"
            auto_wrapped = True
            auto_wrapped_reason = f"structural_heads={heading_count}"
            if env_level == 'development':
                logger.debug(f"Auto-wrap aplicado (structural heuristic) heads={heading_count}", "app.chat.autowrap")

    # Mantener copia original (ya con posible auto-wrap) para exportación antes de limpiar
    original_assistant_message = assistant_message

    # Procesar posible bloque de documentación para exportar a Word (usa original)
    export_info = {}
    try:
        export_info = procesar_respuesta(original_assistant_message)
    except Exception as e:
        logger.error(f"Error procesando exportación Word: {e}", "app.chat")
        export_info = {"tiene_bloque": False, "error": str(e)}

    # Limpiar tags [WORD_DOC] para mostrar en UI
    cleaned_response = clean_word_doc_markers(original_assistant_message)

    file_path = export_info.get("ruta_archivo") if export_info else None
    file_name = os.path.basename(file_path) if file_path else None

    return jsonify({
        "response": cleaned_response.strip(),
        "chat_id": chat_id,
        "word_doc": {
            "generated": export_info.get("tiene_bloque", False),
            "intent_detected": intent_detected,
            "intent_reasons": intent_reasons,
            "auto_wrapped": auto_wrapped,
            "auto_wrapped_reason": auto_wrapped_reason,
            "file_path": file_path,
            "file_name": file_name,
            "download_url": f"/api/word_docs/{file_name}" if file_name else None,
            "error": export_info.get("error")
        }
    })


@app.route('/api/word_docs/<filename>', methods=['GET'])
@login_required
def download_word_doc(filename):
    """Descarga segura de documentos Word generados.

    Solo permite archivos en el directorio configurado y con extensión .docx.
    """
    base_dir = os.environ.get('WORD_DOC_OUTPUT_DIR', os.path.join('data', 'word_docs'))
    # Normalizar ruta
    safe_base = os.path.abspath(base_dir)
    requested_path = os.path.abspath(os.path.join(safe_base, filename))

    # Validaciones de seguridad básicas
    if not requested_path.startswith(safe_base):
        logger.warning(f"Intento de acceso no permitido a {requested_path}", "app.download_word_doc")
        return jsonify({"error": "Acceso no permitido"}), 403
    if not filename.lower().endswith('.docx'):
        return jsonify({"error": "Extensión inválida"}), 400
    if not os.path.exists(requested_path):
        return jsonify({"error": "Archivo no encontrado"}), 404

    # Enviar archivo
    try:
        from flask import send_file
        return send_file(requested_path, as_attachment=True, download_name=filename)
    except Exception as e:
        logger.error(f"Error enviando archivo Word: {e}", "app.download_word_doc")
        return jsonify({"error": "No se pudo descargar el archivo"}), 500

@app.route('/api/chats', methods=['GET'])
def get_chats():
    """Endpoint para obtener la lista de chats del usuario"""
    user_id = get_user_id()
    chats = get_user_chats(user_id)
    return jsonify(chats)

@app.route('/api/chat/<chat_id>', methods=['GET'])
def get_chat(chat_id):
    """Endpoint para cargar un chat específico"""
    user_id = get_user_id()
    
    # Guardar el estado actual del chat antes de cambiarlo (si existe)
    current_chat_id = session.get('chat_id')
    if current_chat_id and current_chat_id != chat_id:
        # Solo guardar el estado si estamos cambiando a un chat diferente
        current_messages = load_chat_history(user_id, current_chat_id)
        current_chat_data = get_chat_data(user_id, current_chat_id)
        # Guardar el chat actual con los file_hashes actuales
        save_chat_history(
            user_id, 
            current_messages, 
            current_chat_data.get('system_message'), 
            current_chat_data.get('title'),
            session.get('file_hashes', [])
        )
        logger.debug(f"Guardado estado del chat actual {current_chat_id} antes de cambiar", "app.get_chat")
    
    # Cargar datos del nuevo chat
    chat_data = get_chat_data(user_id, chat_id)
    messages = chat_data.get('messages', [])
    
    # Actualizar la sesión con el ID del nuevo chat
    session['chat_id'] = chat_id
    
    # Actualizar los file_hashes en la sesión con los del chat seleccionado
    session['file_hashes'] = chat_data.get('file_hashes', [])
    logger.debug(f"Cargando chat {chat_id} con {len(session['file_hashes'])} archivos asociados", "app.get_chat")
    
    # Devolver datos completos del chat, no solo mensajes
    return jsonify({
        'messages': messages,
        'system_message': chat_data.get('system_message'),
        'title': chat_data.get('title'),
        'file_hashes': chat_data.get('file_hashes', [])
    })

@app.route('/api/upload', methods=['POST'])
@login_required
def upload_file():
    """Endpoint para subir archivos"""
    if 'file' not in request.files:
        logger.warning("No se proporcionó archivo en la solicitud", "app.upload_file")
        return jsonify({"error": "No se proporcionó archivo"}), 400
    
    file = request.files['file']
    process_images = request.form.get('process_images', 'true').lower() == 'true'
    
    if file.filename == '':
        logger.warning("Nombre de archivo vacío", "app.upload_file")
        return jsonify({"error": "No se seleccionó archivo"}), 400
    
    if file:
        try:
            filename = secure_filename(file.filename)
            logger.info(f"Procesando archivo subido: {filename}", "app.upload_file")
            
            # Guardar archivo
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Procesar archivo para RAG
            file_hash, num_chunks = process_file(file_path, process_images)
            
            # Guardar referencia al archivo en la sesión
            if 'file_hashes' not in session:
                session['file_hashes'] = []
            
            if file_hash not in session['file_hashes']:
                session['file_hashes'].append(file_hash)
            
            # Actualizar el chat actual con el nuevo file_hash
            user_id = get_user_id()
            chat_id = session.get('chat_id')
            if chat_id:
                # Cargar datos actuales del chat
                chat_data = get_chat_data(user_id, chat_id)
                # Guardar el chat con los file_hashes actualizados
                save_chat_history(
                    user_id, 
                    chat_data.get('messages', []), 
                    chat_data.get('system_message'), 
                    chat_data.get('title'),
                    session['file_hashes']
                )
                logger.debug(f"Chat {chat_id} actualizado con nuevo archivo: {filename}", "app.upload_file")
            
            # Guardar en base de datos si el usuario está autenticado
            if current_user.is_authenticated:
                # Verificar si ya existe
                existing_file = File.query.filter_by(file_hash=file_hash).first()
                if not existing_file:
                    new_file = File(
                        id=str(uuid.uuid4()),
                        user_id=current_user.id,
                        filename=filename,
                        file_hash=file_hash
                    )
                    db.session.add(new_file)
                    db.session.commit()
                    logger.info(f"Archivo guardado en base de datos: {filename}", "app.upload_file")
            
            logger.info(f"Archivo procesado exitosamente: {filename} ({num_chunks} fragmentos)", "app.upload_file")
            return jsonify({
                "success": True,
                "filename": filename,
                "file_hash": file_hash,
                "chunks": num_chunks
            })
            
        except Exception as e:
            logger.error(f"Error al procesar archivo: {str(e)}", "app.upload_file")
            return jsonify({"error": str(e)}), 500
    
    return jsonify({"error": "Error desconocido"}), 500

@app.route('/api/models', methods=['GET'])
def get_models():
    """Endpoint para obtener los modelos disponibles"""
    return jsonify({
        "models": [{
            "id": model["id"],
            "name": model["name"]
        } for model in AVAILABLE_MODELS]
    })

@app.route('/api/new_chat', methods=['POST'])
def new_chat():
    """Endpoint para crear un nuevo chat"""
    user_id = get_user_id()
    
    # Guardar el estado actual del chat antes de crear uno nuevo
    current_chat_id = session.get('chat_id')
    if current_chat_id:
        current_messages = load_chat_history(user_id, current_chat_id)
        current_chat_data = get_chat_data(user_id, current_chat_id)
        # Guardar el chat actual con los file_hashes actuales
        save_chat_history(
            user_id, 
            current_messages, 
            current_chat_data.get('system_message'), 
            current_chat_data.get('title'),
            session.get('file_hashes', [])
        )
        logger.debug(f"Guardado estado del chat actual {current_chat_id} antes de crear uno nuevo", "app.new_chat")
    
    data = request.get_json(silent=True) or {}

    new_chat_info = create_new_chat_session(
        user_id,
        system_message=data.get('system_message'),
        title=data.get('title')
    )

    return jsonify({"chat_id": new_chat_info["chat_id"]})

@app.route('/api/files', methods=['GET'])
def get_files():
    """Endpoint para obtener la lista de archivos subidos"""
    file_hashes = session.get('file_hashes', [])
    files = []

    # Obtener información de los archivos subidos
    for file_hash in file_hashes:
        # Buscar el archivo original en la carpeta de uploads
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.isfile(file_path):
                # Verificar si el hash coincide
                if hashlib.md5(open(file_path, 'rb').read()).hexdigest() == file_hash:
                    files.append({
                        "id": file_hash,
                        "name": filename,
                        "date": datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                    })
                    break

    return jsonify({"files": files})

@app.route('/api/files/<file_hash>', methods=['DELETE'])
def delete_file(file_hash):
    """Endpoint para eliminar un archivo de la sesión"""
    file_hashes = session.get('file_hashes', [])

    if file_hash in file_hashes:
        file_hashes.remove(file_hash)
        session['file_hashes'] = file_hashes

        # Actualizar el chat actual con la lista de archivos modificada
        user_id = get_user_id()
        chat_id = session.get('chat_id')
        if chat_id:
            # Cargar datos actuales del chat
            chat_data = get_chat_data(user_id, chat_id)
            # Guardar el chat con los file_hashes actualizados
            save_chat_history(
                user_id, 
                chat_data.get('messages', []), 
                chat_data.get('system_message'), 
                chat_data.get('title'),
                file_hashes
            )
            logger.debug(f"Chat {chat_id} actualizado tras eliminar archivo {file_hash}", "app.delete_file")

        # Opcional: eliminar la base de datos vectorial
        db_path = os.path.join(VECTORDB_DIR, file_hash)
        if os.path.exists(db_path):
            import shutil
            shutil.rmtree(db_path)
        return jsonify({"success": True})

    return jsonify({"error": "Archivo no encontrado"}), 404
            
@app.route('/api/version', methods=['GET'])
def get_version():
    """Endpoint para obtener la versión de la aplicación"""
    try:
        with open('version.txt', 'r') as f:
            version = f.read().strip()
        return jsonify({"version": version})
    except Exception as e:
        logger.error(f"Error al leer la versión: {str(e)}", "app.get_version")
        return jsonify({"version": "0.0.0"}), 500

@app.route('/api/chat/<chat_id>', methods=['DELETE'])
def delete_chat(chat_id):
    """Endpoint para eliminar un chat"""
    user_id = get_user_id()
    filename = os.path.join(DATA_DIR, f"{user_id}_{chat_id}.json")

    if os.path.exists(filename):
        os.remove(filename)

        if session.get('chat_id') == chat_id:
            session.pop('chat_id', None)
            session.pop('file_hashes', None)

        remaining_chats = [
            name for name in os.listdir(DATA_DIR)
            if name.startswith(f"{user_id}_") and name.endswith('.json')
        ]

        if not remaining_chats:
            new_chat_info = create_new_chat_session(user_id)
            return jsonify({
                "success": True,
                "new_chat": new_chat_info
            })

        return jsonify({"success": True})

    return jsonify({"error": "Chat no encontrado"}), 404


@app.route('/api/user_prompts', methods=['GET'])
@login_required
def list_user_prompts():
    """Devuelve los prompts guardados por el usuario autenticado."""
    prompts = (
        UserPrompt.query
        .filter_by(user_id=current_user.id)
        .order_by(UserPrompt.created_at.desc())
        .all()
    )

    return jsonify({
        "prompts": [
            {
                "id": prompt.id,
                "name": prompt.name,
                "prompt_text": prompt.prompt_text,
                "created_at": prompt.created_at.isoformat()
            }
            for prompt in prompts
        ]
    })


@app.route('/api/user_prompts', methods=['POST'])
@login_required
def create_user_prompt():
    """Crea o actualiza un prompt guardado para el usuario actual."""
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    prompt_text = (data.get('prompt_text') or '').strip()

    if not name:
        return jsonify({"error": "El nombre del prompt es obligatorio."}), 400
    if not prompt_text:
        return jsonify({"error": "El contenido del prompt no puede estar vacío."}), 400

    existing_prompt = UserPrompt.query.filter_by(user_id=current_user.id, name=name).first()

    if existing_prompt:
        existing_prompt.prompt_text = prompt_text
        db.session.commit()
        logger.info(f"Prompt '{name}' actualizado para el usuario {current_user.id}", "app.create_user_prompt")
        return jsonify({
            "success": True,
            "updated": True,
            "prompt": {
                "id": existing_prompt.id,
                "name": existing_prompt.name,
                "prompt_text": existing_prompt.prompt_text,
                "created_at": existing_prompt.created_at.isoformat()
            }
        }), 200

    new_prompt = UserPrompt(user_id=current_user.id, name=name, prompt_text=prompt_text)
    db.session.add(new_prompt)
    db.session.commit()

    logger.info(f"Prompt '{name}' creado para el usuario {current_user.id}", "app.create_user_prompt")
    return jsonify({
        "success": True,
        "created": True,
        "prompt": {
            "id": new_prompt.id,
            "name": new_prompt.name,
            "prompt_text": new_prompt.prompt_text,
            "created_at": new_prompt.created_at.isoformat()
        }
    }), 201

@app.route('/api/chat/<chat_id>/system_message', methods=['PUT'])
def update_system_message(chat_id):
    """Endpoint para actualizar el mensaje de sistema de un chat"""
    user_id = get_user_id()
    data = request.json
    system_message = data.get('system_message')

    # Cargar datos del chat
    chat_data = get_chat_data(user_id, chat_id)

    if not chat_data or not chat_data.get('messages'):
        return jsonify({"error": "Chat no encontrado"}), 404

    # Actualizar y guardar manteniendo los file_hashes específicos de este chat
    chat_id = save_chat_history(
        user_id, 
        chat_data.get('messages', []), 
        system_message, 
        chat_data.get('title'), 
        chat_data.get('file_hashes', [])
    )

    # Si es el chat actual, actualizar también la sesión
    if session.get('chat_id') == chat_id:
        session['file_hashes'] = chat_data.get('file_hashes', [])

    return jsonify({"success": True, "chat_id": chat_id})

@app.route('/api/chat/<chat_id>/title', methods=['PUT'])
def update_chat_title(chat_id):
    """Endpoint para actualizar el título de un chat"""
    user_id = get_user_id()
    data = request.json
    title = data.get('title')

    if not title:
        return jsonify({"error": "Título no proporcionado"}), 400

    # Cargar datos del chat
    chat_data = get_chat_data(user_id, chat_id)

    if not chat_data:
        return jsonify({"error": "Chat no encontrado"}), 404

    # Actualizar y guardar manteniendo los file_hashes específicos
    chat_id = save_chat_history(
        user_id, 
        chat_data.get('messages', []), 
        chat_data.get('system_message'), 
        title, 
        chat_data.get('file_hashes', [])
    )

    return jsonify({"success": True, "chat_id": chat_id})

@app.route('/api/chat/<chat_id>/files', methods=['GET'])
def get_chat_files(chat_id):
    """Endpoint para obtener la lista de archivos asociados a un chat específico"""
    user_id = get_user_id()
    chat_data = get_chat_data(user_id, chat_id)
    file_hashes = chat_data.get('file_hashes', [])
    files = []

    # Obtener información de los archivos asociados a este chat
    for file_hash in file_hashes:
        # Buscar el archivo original en la carpeta de uploads
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.isfile(file_path):
                # Verificar si el hash coincide
                if hashlib.md5(open(file_path, 'rb').read()).hexdigest() == file_hash:
                    files.append({
                        "id": file_hash,
                        "name": filename,
                        "date": datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                    })
                    break

    return jsonify({"files": files})

# Crear tablas de la base de datos si no existen
# Note: before_first_request was removed in Flask 2.3.0

# Register a function to create tables with app context
with app.app_context():
    db.create_all()
    backfill_missing_default_prompts()

@app.route('/chat-stream', methods=['POST'])
@login_required
def chat_stream():
    """Endpoint para procesar mensajes de chat con streaming"""
    try:
        data = request.get_json()
        message = data.get('message', '')
        chat_id = data.get('chat_id')
        model_id = data.get('model_id')
        
        # Validar que se recibió un mensaje
        if not message.strip():
            return jsonify({'error': 'Mensaje vacío'}), 400
            
        # Obtener o crear chat
        if not chat_id:
            # Crear nuevo chat
            chat = Chat(user_id=current_user.id, title=message[:30])
            db.session.add(chat)
            db.session.commit()
            chat_id = chat.id
        else:
            # Verificar que el chat existe y pertenece al usuario
            chat = Chat.query.filter_by(id=chat_id, user_id=current_user.id).first()
            if not chat:
                return jsonify({'error': 'Chat no encontrado'}), 404
        
        # Guardar mensaje del usuario
        user_message = Message(chat_id=chat_id, role="user", content=message)
        db.session.add(user_message)
        db.session.commit()
        
        # Obtener historial de mensajes para contexto
        messages_history = Message.query.filter_by(chat_id=chat_id).order_by(Message.timestamp).all()
        
        # Preparar mensajes para la API
        api_messages = []
        for msg in messages_history:
            api_messages.append({"role": msg.role, "content": msg.content})
        
        # Obtener cliente de OpenAI para el modelo seleccionado
        client = get_openai_client(model_id)
        
        # Verificar si es un modelo que usa Azure AI Inference SDK
        selected_model = next((model for model in AVAILABLE_MODELS if model["id"] == model_id), None)
        is_azure_ai_inference = selected_model and selected_model.get("model_type") == "azure_ai_inference"
        
        def generate():
            # Inicializar respuesta acumulada
            accumulated_response = ""
            
            if is_azure_ai_inference:
                try:
                    from azure.ai.inference.models import SystemMessage, UserMessage, AssistantMessage
                    
                    # Convertir mensajes al formato de Azure AI Inference
                    inference_messages = []
                    for msg in messages_history:
                        if msg.role == "system":
                            inference_messages.append(SystemMessage(content=msg.content))
                        elif msg.role == "user":
                            inference_messages.append(UserMessage(content=msg.content))
                        elif msg.role == "assistant":
                            inference_messages.append(AssistantMessage(content=msg.content))
                    
                    # Si no hay mensaje de sistema, añadir uno por defecto
                    if not any(isinstance(msg, SystemMessage) for msg in inference_messages):
                        inference_messages.insert(0, SystemMessage(content="Eres un asistente útil y amigable."))
                    
                    # Realizar llamada a la API de Azure AI Inference con streaming
                    stream = client.complete(
                        messages=inference_messages,
                        max_tokens=800,
                        model=model_id,
                        stream=True
                    )
                    
                    # Procesar cada fragmento de la respuesta
                    for update in stream:
                        if update.choices and update.choices[0].delta and update.choices[0].delta.content is not None:
                            content = update.choices[0].delta.content
                            accumulated_response += content
                            yield f"data: {json.dumps({'content': content, 'chat_id': chat_id})}\n\n"
                    
                except Exception as e:
                    logger.error(f"Error al usar Azure AI Inference streaming: {str(e)}", "app.chat_stream")
                    error_msg = f"Error al usar el modelo {model_id}: {str(e)}"
                    yield f"data: {json.dumps({'content': error_msg, 'chat_id': chat_id})}\n\n"
                    yield f"data: {json.dumps({'content': '[DONE]', 'chat_id': chat_id})}\n\n"
                    return
            else:
                # Realizar llamada a la API con streaming para modelos OpenAI
                stream = client.chat.completions.create(
                    model=model_id or AZURE_OPENAI_DEPLOYMENT,
                    messages=api_messages,
                    temperature=0.7,
                    max_tokens=800,
                    top_p=0.95,
                    frequency_penalty=0,
                    presence_penalty=0,
                    stop=None,
                    stream=True
                )
                
                # Procesar cada fragmento de la respuesta
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content is not None:
                        content = chunk.choices[0].delta.content
                        accumulated_response += content
                        yield f"data: {json.dumps({'content': content, 'chat_id': chat_id})}\n\n"
            
            # Guardar respuesta completa del asistente
            assistant_message = Message(chat_id=chat_id, role="assistant", content=accumulated_response)
            db.session.add(assistant_message)
            
            # Actualizar título del chat si es nuevo
            if len(messages_history) <= 1:
                chat.title = message[:30]
                
            db.session.commit()
            
            # Enviar señal de finalización
            yield f"data: {json.dumps({'content': '[DONE]', 'chat_id': chat_id})}\n\n"
        
        return Response(generate(), mimetype='text/event-stream')
        
    except Exception as e:
        logger.error(f"Error en chat_stream: {str(e)}", "app.chat_stream")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)