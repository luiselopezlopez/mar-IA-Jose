# pyright: reportGeneralTypeIssues=false, reportMissingImports=false, reportMissingModuleSource=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportUnknownParameterType=false, reportAttributeAccessIssue=false
import os
from typing import Any, cast
import uuid
import json
import io
import base64
import time
from threading import Lock
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, get_flashed_messages, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI
from werkzeug.utils import secure_filename
import hashlib
import shutil
from sqlalchemy import text, inspect as sa_inspect
from sqlalchemy.exc import IntegrityError
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import AzureOpenAIEmbeddings
from dotenv import load_dotenv
from models import db, User, Chat, Message, File, UserPrompt, KnowledgeBase
from doc_export import guardar_respuesta_en_word  # Exportación manual a Word
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


def _env_int(var_name: str, default: int) -> int:
    """Lee un entero desde las variables de entorno con un valor por defecto seguro."""
    raw = os.environ.get(var_name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning(f"Valor inválido para {var_name}={raw}. Usando {default}.", "app.config")
        return default


def _env_float(var_name: str, default: float) -> float:
    """Lee un float desde las variables de entorno con un valor por defecto seguro."""
    raw = os.environ.get(var_name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning(f"Valor inválido para {var_name}={raw}. Usando {default}.", "app.config")
        return default

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
KNOWLEDGE_BASE_DIR = os.path.join(VECTORDB_DIR, 'knowledge_bases')
os.makedirs(KNOWLEDGE_BASE_DIR, exist_ok=True)
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

DEFAULT_RAG_TOP_K = max(1, _env_int("RAG_TOP_K_DEFAULT", 3))
MAX_RAG_TOP_K = max(DEFAULT_RAG_TOP_K, _env_int("RAG_TOP_K_MAX", 20))
DEFAULT_TEMPERATURE = min(max(_env_float("TEMPERATURE_DEFAULT", 1.0), 0.0), 2.0)
DEFAULT_HISTORY_LIMIT = max(1, _env_int("MESSAGE_HISTORY_DEFAULT", 10))
MAX_HISTORY_LIMIT = max(DEFAULT_HISTORY_LIMIT, _env_int("MESSAGE_HISTORY_MAX", 50))

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
login_manager.login_view = 'login'  # type: ignore[assignment]

@login_manager.user_loader
def load_user(user_id):
    # Updated to use Session.get() instead of query.get() which is deprecated in SQLAlchemy 2.0
    return db.session.get(User, int(user_id))

# Configuración de Azure OpenAI
AZURE_OPENAI_ENDPOINT = os.environ.get("azure_endpoint") or ""
AZURE_OPENAI_KEY = os.environ.get("api_key") or ""
AZURE_OPENAI_DEPLOYMENT = os.environ.get("model_name", "gpt-35-turbo") or "gpt-35-turbo"
AZURE_OPENAI_API_VERSION = os.environ.get("api_version") or os.environ.get("_version") or "2023-05-15"
AZURE_OPENAI_EMBEDDING_ENDPOINT= os.environ.get("embedding_endpoint") or ""
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.environ.get("embedding_deployment") or ""
AZURE_OPENAI_EMBEDDING_API = os.environ.get("embedding_api") or "2023-05-15"
AZURE_OPENAI_EMBEDDING_APIKEY = os.environ.get("embedding_api_key") or ""

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
            "api_version": AZURE_OPENAI_API_VERSION,
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
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT
        )

    # Buscar configuración del modelo seleccionado
    selected_model = next((model for model in AVAILABLE_MODELS if model["id"] == model_id), None)

    if not selected_model:
        # Si no se encuentra el modelo, usar el predeterminado
        logger.warning(f"Modelo solicitado '{model_id}' no encontrado, usando predeterminado", "app.get_openai_client")
        return AzureOpenAI(
            api_key=AZURE_OPENAI_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
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
                api_version=AZURE_OPENAI_API_VERSION,
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
    api_key=AZURE_OPENAI_EMBEDDING_APIKEY,
    azure_endpoint=AZURE_OPENAI_EMBEDDING_ENDPOINT,
    api_version=AZURE_OPENAI_EMBEDDING_API,
)


EMBEDDING_PROGRESS = {}
EMBEDDING_PROGRESS_LOCK = Lock()


def set_embedding_progress(progress_id: str | None, **updates):
    if not progress_id:
        return
    with EMBEDDING_PROGRESS_LOCK:
        state = EMBEDDING_PROGRESS.get(progress_id)
        if not state:
            state = {
                'created_at': datetime.utcnow().isoformat()
            }
        state.update(updates)
        state['updated_at'] = datetime.utcnow().isoformat()
        EMBEDDING_PROGRESS[progress_id] = state


def is_rate_limit_error(exc):
    """Detecta si la excepción proviene de un límite de peticiones (HTTP 429)."""
    status_code = getattr(exc, 'status_code', None)
    if status_code == 429:
        return True
    http_status = getattr(exc, 'http_status', None)
    if http_status == 429:
        return True
    error_code = getattr(getattr(exc, 'error', None), 'code', None)
    if error_code in (429, '429'):
        return True
    message = str(exc).lower()
    return '429' in message or 'rate limit' in message


def build_vectorstore_with_retry(chunks, embedding_client, *, base_delay=10, max_delay=30, progress_id=None):
    """Crea la base vectorial aplicando reintentos con backoff ante errores 429."""
    attempt = 0
    last_exc = None
    set_embedding_progress(progress_id, status="starting", attempt=0, waiting_seconds=0, completed=False)
    while True:
        attempt += 1
        try:
            set_embedding_progress(progress_id, status="processing", attempt=attempt, waiting_seconds=0, completed=False)
            vectorstore = FAISS.from_documents(chunks, embedding_client)
            set_embedding_progress(progress_id, status="completed", attempt=attempt, waiting_seconds=0, completed=True)
            return vectorstore
        except Exception as exc:
            last_exc = exc
            if not is_rate_limit_error(exc):
                set_embedding_progress(
                    progress_id,
                    status="failed",
                    attempt=attempt,
                    waiting_seconds=0,
                    completed=True,
                    error=str(exc)
                )
                break

            wait_time = min(base_delay * (2 ** (attempt - 1)), max_delay)
            logger.warning(
                f"Límite de peticiones al generar embeddings (intento {attempt}). Reintentando en {wait_time} segundos.",
                "app.build_vectorstore_with_retry"
            )
            set_embedding_progress(
                progress_id,
                status="rate_limited",
                attempt=attempt,
                waiting_seconds=wait_time,
                completed=False
            )
            time.sleep(wait_time)
            set_embedding_progress(progress_id, status="reintentando", attempt=attempt, waiting_seconds=0, completed=False)

    if last_exc is None:
        raise RuntimeError("No se pudo construir la base vectorial por un motivo desconocido.")

    raise last_exc


def get_user_id():
    """Obtiene el ID del usuario actual o crea uno temporal para sesiones no autenticadas"""
    if current_user.is_authenticated:
        logger.debug(f"Usuario autenticado: {current_user.username} (ID: {current_user.id})", "app.get_user_id")
        return current_user.id
    elif 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
        logger.debug(f"Creando ID temporal para sesión: {session['user_id']}", "app.get_user_id")
    return session['user_id']

def _resolve_int_setting(value, default, minimum=None, maximum=None):
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        resolved = default
    if minimum is not None:
        resolved = max(minimum, resolved)
    if maximum is not None:
        resolved = min(maximum, resolved)
    return resolved

def _resolve_float_setting(value, default, minimum=None, maximum=None, precision=None):
    try:
        resolved = float(value)
    except (TypeError, ValueError):
        resolved = default
    if minimum is not None:
        resolved = max(minimum, resolved)
    if maximum is not None:
        resolved = min(maximum, resolved)
    if precision is not None:
        factor = 10 ** precision
        resolved = round(resolved * factor) / factor
    return resolved

def save_chat_history(user_id, messages, system_message=None, title=None, file_hashes=None,
                      rag_top_k=None, temperature=None, message_history_limit=None,
                      attached_bases=None):
    """Guarda el historial de chat y sus parámetros en un archivo JSON."""
    chat_id = session.get('chat_id', str(uuid.uuid4()))
    session['chat_id'] = chat_id
    logger.debug(f"Guardando historial de chat para usuario {user_id}, chat_id: {chat_id}", "app.save_chat_history")

    filename = os.path.join(DATA_DIR, f"{user_id}_{chat_id}.json")

    existing_data = {}
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as existing_file:
                existing_data = json.load(existing_file)
        except Exception as exc:  # pragma: no cover - resiliencia adicional
            logger.warning(f"No se pudo leer historial previo para {chat_id}: {exc}", "app.save_chat_history")

    # Determinar el título del chat
    if not title and messages:
        # Usar el primer mensaje como título si no se proporciona uno
        preview = messages[0]['content'][:50] + '...' if messages else 'Chat vacío'
        title = preview

    # Asegurar un título por defecto
    if not title:
        title = 'Nueva conversación'

    # Usar los file_hashes y knowledge bases proporcionados o los de la sesión actual
    if file_hashes is None:
        file_hashes = session.get('file_hashes', [])
    if attached_bases is None:
        attached_bases = session.get('attached_bases', [])

    file_hashes = list(file_hashes or [])
    attached_bases = list(attached_bases or [])

    resolved_top_k = _resolve_int_setting(
        rag_top_k if rag_top_k is not None else existing_data.get('rag_top_k'),
        DEFAULT_RAG_TOP_K,
        minimum=1,
        maximum=MAX_RAG_TOP_K
    )
    resolved_temperature = _resolve_float_setting(
        temperature if temperature is not None else existing_data.get('temperature'),
        DEFAULT_TEMPERATURE,
        minimum=0.0,
        maximum=2.0,
        precision=1
    )
    resolved_history_limit = _resolve_int_setting(
        message_history_limit if message_history_limit is not None else existing_data.get('message_history_limit'),
        DEFAULT_HISTORY_LIMIT,
        minimum=1,
        maximum=MAX_HISTORY_LIMIT
    )

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump({
            'chat_id': chat_id,
            'timestamp': datetime.now().isoformat(),
            'messages': messages,
            'system_message': system_message,
            'title': title,
            'file_hashes': file_hashes,
            'rag_top_k': resolved_top_k,
            'temperature': resolved_temperature,
            'message_history_limit': resolved_history_limit,
            'attached_bases': attached_bases
        }, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Chat guardado: {title[:30]}... (ID: {chat_id})", "app.save_chat_history")
    session['attached_bases'] = attached_bases
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
    session['attached_bases'] = []

    save_chat_history(
        user_id,
        [],
        resolved_system_message,
        resolved_title,
        rag_top_k=DEFAULT_RAG_TOP_K,
        temperature=DEFAULT_TEMPERATURE,
        message_history_limit=DEFAULT_HISTORY_LIMIT,
        attached_bases=[]
    )

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
                data = json.load(f)

            if not isinstance(data, dict):
                data = {}

            data['messages'] = data.get('messages', [])
            data['system_message'] = data.get('system_message')
            data['title'] = data.get('title')
            data['file_hashes'] = data.get('file_hashes', [])
            data['attached_bases'] = data.get('attached_bases', [])
            data['rag_top_k'] = _resolve_int_setting(data.get('rag_top_k'), DEFAULT_RAG_TOP_K, minimum=1, maximum=MAX_RAG_TOP_K)
            data['temperature'] = _resolve_float_setting(data.get('temperature'), DEFAULT_TEMPERATURE, minimum=0.0, maximum=2.0, precision=1)
            data['message_history_limit'] = _resolve_int_setting(data.get('message_history_limit'), DEFAULT_HISTORY_LIMIT, minimum=1, maximum=MAX_HISTORY_LIMIT)

            session['attached_bases'] = data['attached_bases']

            return data
    logger.debug(f"No se encontró chat con ID: {chat_id}", "app.get_chat_data")
    session['attached_bases'] = []
    return {
        "messages": [],
        "system_message": None,
        "title": None,
        "file_hashes": [],
        "attached_bases": [],
        "rag_top_k": DEFAULT_RAG_TOP_K,
        "temperature": DEFAULT_TEMPERATURE,
        "message_history_limit": DEFAULT_HISTORY_LIMIT,
        "timestamp": None
    }

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


def _persist_attached_bases(user_id, chat_id, chat_data, attached_bases):
    """Actualiza el historial del chat con la lista de bases RAG asociadas."""

    chat_id = save_chat_history(
        user_id,
        chat_data.get('messages', []),
        chat_data.get('system_message'),
        chat_data.get('title'),
        chat_data.get('file_hashes', []),
        rag_top_k=chat_data.get('rag_top_k'),
        temperature=chat_data.get('temperature'),
        message_history_limit=chat_data.get('message_history_limit'),
        attached_bases=list(attached_bases or [])
    )

    if session.get('chat_id') == chat_id:
        session['attached_bases'] = list(attached_bases or [])

    return chat_id


def serialize_knowledge_base(kb, attached=False):
    """Convierte una base de conocimiento en un dict listo para JSON."""

    return {
        "id": kb.id,
        "name": kb.name,
        "created_at": kb.created_at.isoformat() if kb.created_at else None,
        "attached": attached,
        "source_chat_id": kb.source_chat_id,
    }


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

    default_prompt = UserPrompt(user_id=user_id, name='Default', prompt_text=DEFAULT_SYSTEM_PROMPT)  # type: ignore[call-arg]
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


def ensure_user_type_consistency():
    """Garantiza que la columna user_type exista y los roles estén correctamente asignados."""
    try:
        inspector = sa_inspect(db.engine)
        user_table_name = User.__tablename__
        column_names = {column['name'] for column in inspector.get_columns(user_table_name)}

        with db.engine.begin() as connection:
            if 'user_type' not in column_names:
                logger.info("Añadiendo columna user_type a la tabla de usuarios", "app.ensure_user_type_consistency")
                connection.execute(text(f"ALTER TABLE {user_table_name} ADD COLUMN user_type INTEGER DEFAULT 1"))

            # Asegurar valores por defecto para filas existentes sin user_type
            connection.execute(text(
                f"UPDATE {user_table_name} SET user_type = 1 WHERE user_type IS NULL"
            ))

            # Si no existe ningún admin, convertir al usuario más antiguo en admin
            connection.execute(text(
                f"UPDATE {user_table_name} SET user_type = 0 "
                f"WHERE id = (SELECT id FROM {user_table_name} ORDER BY id ASC LIMIT 1) "
                f"AND NOT EXISTS (SELECT 1 FROM {user_table_name} WHERE user_type = 0)"
            ))

        logger.info("Roles de usuario actualizados: se garantiza al menos un administrador", "app.ensure_user_type_consistency")
    except Exception as exc:
        logger.error(f"No se pudo asegurar la consistencia de user_type: {exc}", "app.ensure_user_type_consistency")
        db.session.rollback()


def migrate_vectorstores_to_chat_system():
    """Migra las bases vectoriales existentes del sistema por archivo al sistema por chat"""
    try:
        logger.info("Iniciando migración de bases vectoriales al sistema por chat", "app.migrate_vectorstores")
        
        # Verificar si ya existe el directorio de migración (para evitar re-migrar)
        migration_marker = os.path.join(VECTORDB_DIR, '.migrated_to_chat_system')
        if os.path.exists(migration_marker):
            logger.debug("Migración ya realizada anteriormente", "app.migrate_vectorstores")
            return
        
        migrated_count = 0
        error_count = 0
        
        # Obtener todos los chats existentes
        for filename in os.listdir(DATA_DIR):
            if filename.endswith('.json') and '_' in filename:
                try:
                    # Extraer user_id y chat_id del nombre del archivo
                    parts = filename.replace('.json', '').split('_', 1)
                    if len(parts) != 2:
                        continue
                    
                    user_id, chat_id = parts
                    
                    # Cargar datos del chat
                    with open(os.path.join(DATA_DIR, filename), 'r', encoding='utf-8') as f:
                        chat_data = json.load(f)
                    
                    file_hashes = chat_data.get('file_hashes', [])
                    if not file_hashes:
                        continue
                    
                    logger.debug(f"Migrando chat {chat_id} con {len(file_hashes)} archivos", "app.migrate_vectorstores")
                    
                    # Recopilar todos los chunks de los archivos del chat
                    all_chunks = []
                    valid_file_hashes = []
                    
                    for file_hash in file_hashes:
                        old_db_path = os.path.join(VECTORDB_DIR, file_hash)
                        if os.path.exists(old_db_path):
                            try:
                                # Cargar la base vectorial antigua
                                vectorstore = FAISS.load_local(old_db_path, embeddings, allow_dangerous_deserialization=True)
                                
                                # Obtener todos los documentos
                                docs = list(vectorstore.docstore._dict.values())  # type: ignore[attr-defined]
                                
                                # Añadir metadatos del archivo a cada documento
                                for doc in docs:
                                    if 'file_hash' not in doc.metadata:
                                        doc.metadata['file_hash'] = file_hash
                                
                                all_chunks.extend(docs)
                                valid_file_hashes.append(file_hash)
                                logger.debug(f"Cargados {len(docs)} chunks del archivo {file_hash}", "app.migrate_vectorstores")
                                
                            except Exception as e:
                                logger.warning(f"Error al cargar base vectorial antigua {file_hash}: {str(e)}", "app.migrate_vectorstores")
                                continue
                    
                    if all_chunks:
                        # Crear nueva base vectorial para el chat
                        chat_db_path = os.path.join(VECTORDB_DIR, str(chat_id))
                        os.makedirs(chat_db_path, exist_ok=True)
                        
                        new_vectorstore = build_vectorstore_with_retry(all_chunks, embeddings)
                        new_vectorstore.save_local(chat_db_path)
                        
                        logger.info(f"Chat {chat_id} migrado con {len(all_chunks)} chunks de {len(valid_file_hashes)} archivos", "app.migrate_vectorstores")
                        migrated_count += 1
                        
                        # Actualizar el chat con solo los file_hashes válidos
                        if len(valid_file_hashes) != len(file_hashes):
                            chat_data['file_hashes'] = valid_file_hashes
                            with open(os.path.join(DATA_DIR, filename), 'w', encoding='utf-8') as f:
                                json.dump(chat_data, f, ensure_ascii=False, indent=2)
                            logger.debug(f"Actualizada lista de archivos del chat {chat_id}", "app.migrate_vectorstores")
                    
                except Exception as e:
                    logger.error(f"Error al migrar chat desde archivo {filename}: {str(e)}", "app.migrate_vectorstores")
                    error_count += 1
                    continue
        
        # Crear marcador de migración
        with open(migration_marker, 'w', encoding='utf-8') as f:
            f.write(f"Migración completada: {datetime.now().isoformat()}\n")
            f.write(f"Chats migrados: {migrated_count}\n")
            f.write(f"Errores: {error_count}\n")
        
        logger.info(f"Migración completada: {migrated_count} chats migrados, {error_count} errores", "app.migrate_vectorstores")
        
        # Opcional: limpiar bases vectoriales antiguas después de un tiempo
        # (comentado por seguridad, se puede descomentar después de verificar que todo funciona)
        # cleanup_old_vectorstores()
        
    except Exception as e:
        logger.error(f"Error durante la migración de bases vectoriales: {str(e)}", "app.migrate_vectorstores")


def cleanup_old_vectorstores():
    """Limpia las bases vectoriales antiguas (solo por hash de archivo) después de la migración.
    
    PRECAUCIÓN: Solo ejecutar después de verificar que la migración fue exitosa.
    """
    try:
        logger.info("Iniciando limpieza de bases vectoriales antiguas", "app.cleanup_old_vectorstores")
        
        cleaned_count = 0
        for item in os.listdir(VECTORDB_DIR):
            item_path = os.path.join(VECTORDB_DIR, item)
            
            # Saltar archivos y directorios especiales
            if item.startswith('.') or not os.path.isdir(item_path):
                continue
            
            # Si el nombre es un hash MD5 (32 caracteres hexadecimales), es del sistema antiguo
            if len(item) == 32 and all(c in '0123456789abcdef' for c in item.lower()):
                try:
                    shutil.rmtree(item_path)
                    cleaned_count += 1
                    logger.debug(f"Base vectorial antigua eliminada: {item}", "app.cleanup_old_vectorstores")
                except Exception as e:
                    logger.warning(f"No se pudo eliminar base vectorial antigua {item}: {str(e)}", "app.cleanup_old_vectorstores")
        
        logger.info(f"Limpieza completada: {cleaned_count} bases vectoriales antiguas eliminadas", "app.cleanup_old_vectorstores")
        
    except Exception as e:
        logger.error(f"Error durante la limpieza de bases vectoriales antiguas: {str(e)}", "app.cleanup_old_vectorstores")

def extract_images_from_pdf(file_path):
    """Extrae imágenes de un archivo PDF y realiza OCR o genera descripciones usando GPT-4o"""
    image_texts = []
    logger.info(f"Iniciando extracción de imágenes del PDF: {os.path.basename(file_path)}", "app.extract_images_from_pdf")
    try:
        if hasattr(fitz, "open"):
            doc = fitz.open(file_path)  # type: ignore[attr-defined]
        elif hasattr(fitz, "Document"):
            doc = fitz.Document(file_path)
        else:
            logger.warning(
                "PyMuPDF (fitz) no expone 'open' ni 'Document'; se omite extracción de imágenes",
                "app.extract_images_from_pdf",
            )
            return []
    except Exception as exc:
        logger.error(f"No se pudo abrir el PDF con PyMuPDF: {exc}", "app.extract_images_from_pdf")
        return []

    # Seleccionar el modelo a usar para OCR de imágenes. Si no hay modelo, omitir OCR para evitar 404 repetidos.
    ocr_model_id = AZURE_OPENAI_DEPLOYMENT or (AVAILABLE_MODELS[0]["id"] if AVAILABLE_MODELS else None)
    if not ocr_model_id:
        logger.warning("No hay modelo configurado para OCR de imágenes; se omite extracción de imágenes", "app.extract_images_from_pdf")
        return []

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

            # Omitir imágenes diminutas para reducir carga y errores de rate limit
            MIN_SIDE = 64
            MIN_AREA = 4096
            if image.width < MIN_SIDE and image.height < MIN_SIDE and (image.width * image.height) < MIN_AREA:
                logger.debug(
                    f"Omitiendo imagen diminuta ({image.width}x{image.height}) en página {page_num+1}, índice {img_index+1}",
                    "app.extract_images_from_pdf",
                )
                continue

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
                model_client: Any = get_openai_client(ocr_model_id)

                # Reintentos básicos ante rate limits
                response = None
                attempt = 0
                while attempt < 3 and response is None:
                    attempt += 1
                    try:
                        response = model_client.chat.completions.create(  # type: ignore[attr-defined]
                            model=ocr_model_id,
                            messages=[
                                {"role": "system", "content": "Eres un asistente especializado en extraer texto de imágenes y describir su contenido. Si hay texto visible en la imagen, extráelo con precisión. Si no hay texto o es poco relevante, proporciona una descripción detallada de lo que ves. No puedes realizar sugerencias sobre acciones posteriores ni añadir nada más."},
                                {"role": "user", "content": [
                                    {"type": "text", "text": "Reconoce el texto de la imagen y donde haya una imagen, describela. La descripcion de la imagen ha de estar ubicada justo donde estaba la imagen en el documento. No añadas nada, solo devuelve el texto reconocido y las descripciones de las imagenes. No sugieras acciones posteriores ni nada más."},
                                    {"type": "image_url", "image_url": {"url": img_url}}
                                ]}
                            ],
                        )
                    except Exception as exc:  # pragma: no cover - resiliencia runtime
                        if is_rate_limit_error(exc) and attempt < 3:
                            wait_time = min(2 * attempt, 6)
                            logger.warning(
                                f"Rate limit al procesar imagen (intento {attempt}/3). Reintentando en {wait_time}s...",
                                "app.extract_images_from_pdf",
                            )
                            time.sleep(wait_time)
                            continue
                        # Propagar el error para manejo posterior
                        raise

                result_raw = response.choices[0].message.content  # type: ignore[index]
                result = result_raw or ""
                print(f"[DEBUG] Respuesta recibida de {ocr_model_id} ({len(result)} caracteres)")

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
                error_msg = f"Error al procesar la imagen con el modelo {ocr_model_id}: {str(e)}"
                print(f"[ERROR] {error_msg}")
                logger.error(error_msg, "app.extract_images_from_pdf")

                # Tras error, esperar un poco para no disparar más rate limits en bucles grandes
                time.sleep(1)

                # Si el error indica despliegue inexistente, no seguir intentando en más imágenes.
                if "DeploymentNotFound" in str(e):
                    logger.error("Deployment de OCR no encontrado; se omite el resto de imágenes para evitar errores repetidos", "app.extract_images_from_pdf")
                    doc.close()
                    return image_texts

                image_texts.append(f"[ERROR EN PROCESAMIENTO DE IMAGEN - Página {page_num+1}, Imagen {img_index+1}]: No se pudo procesar la imagen. Error: {str(e)}")

    print(f"\n[DEBUG] Procesamiento de PDF completado. Total de textos/descripciones extraídos: {len(image_texts)}")
    doc.close()
    return image_texts

def process_file_for_chat(file_path, chat_id, process_mode="full", progress_id=None):
    """Procesa un archivo para RAG y lo añade a la base vectorial del chat específico
    
    Args:
        file_path: Ruta al archivo a procesar
        chat_id: ID del chat al que pertenece el archivo
        process_mode: "full" (texto + OCR por imagen), "text_only" (solo texto), "ocr_only" (OCR consolidado por página con imágenes).
        progress_id: ID para seguimiento del progreso
    
    Returns:
        tuple: (file_hash, num_chunks) - hash del archivo y número de fragmentos procesados
    """
    file_extension = os.path.splitext(file_path)[1].lower()
    logger.info(f"Procesando archivo para chat {chat_id}: {os.path.basename(file_path)} ({file_extension})", "app.process_file_for_chat")

    process_mode = process_mode or "full"
    if process_mode not in {"full", "text_only", "ocr_only"}:
        process_mode = "full"

    image_texts: list[str] = []
    page_ocr_texts: list[tuple[int, str]] = []  # (page_index, text)
    if file_extension == '.pdf':
        # Extraer imágenes y realizar OCR por imagen (modo completo)
        if process_mode == "full":
            try:
                logger.info("Iniciando extracción de imágenes del PDF", "app.process_file_for_chat")
                image_texts = extract_images_from_pdf(file_path)
            except Exception as e:
                error_msg = f"Error al extraer imágenes del PDF: {str(e)}"
                logger.error(error_msg, "app.process_file_for_chat")
                print(error_msg)
                image_texts = []  # No bloquear el resto del proceso

        # OCR consolidado por página si se solicitó
        if process_mode == "ocr_only":
            doc = None
            try:
                doc = fitz.open(file_path)
                ocr_model_id = AZURE_OPENAI_DEPLOYMENT or (AVAILABLE_MODELS[0]["id"] if AVAILABLE_MODELS else None)
                if not ocr_model_id:
                    logger.warning("No hay modelo configurado para OCR de imágenes (ocr_only)", "app.process_file_for_chat")
                else:
                    for page_idx, page in enumerate(doc):
                        images = page.get_images(full=True)
                        if not images:
                            continue
                        # Renderizar página completa a imagen
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        buffered = io.BytesIO()
                        img.save(buffered, format="JPEG")
                        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                        img_url = f"data:image/jpeg;base64,{img_base64}"

                        # Reintentos ante rate limit
                        response = None
                        attempt = 0
                        while attempt < 3 and response is None:
                            attempt += 1
                            try:
                                client = get_openai_client(ocr_model_id)
                                response = client.chat.completions.create(  # type: ignore[attr-defined]
                                    model=ocr_model_id,
                                    messages=[
                                        {"role": "system", "content": "Eres un asistente especializado en extraer texto de páginas completas (imagen renderizada) y describir su contenido visual. Devuelve texto legible y una breve descripción si aplica."},
                                        {"role": "user", "content": [
                                            {"type": "text", "text": "Haz OCR de toda la página y describe brevemente las partes visuales relevantes si las hay."},
                                            {"type": "image_url", "image_url": {"url": img_url}},
                                        ]},
                                    ],
                                )
                            except Exception as exc:  # pragma: no cover
                                if is_rate_limit_error(exc) and attempt < 3:
                                    wait_time = min(2 * attempt, 6)
                                    logger.warning(
                                        f"Rate limit OCR página {page_idx+1} (intento {attempt}/3). Esperando {wait_time}s",
                                        "app.process_file_for_chat",
                                    )
                                    time.sleep(wait_time)
                                    continue
                                raise

                        if response:
                            result_raw = response.choices[0].message.content  # type: ignore[index]
                            page_ocr_texts.append((page_idx, result_raw or ""))
                        time.sleep(0.5)  # pequeño respiro entre páginas con imágenes
            except Exception as exc:
                logger.error(f"Error en OCR consolidado de PDF: {exc}", "app.process_file_for_chat")
            finally:
                if doc:
                    doc.close()

        # Cargar el documento normalmente
        try:
            loader = PyPDFLoader(file_path)
        except Exception as e:
            error_msg = f"Error al cargar el PDF con PyPDFLoader: {str(e)}"
            logger.error(error_msg, "app.process_file_for_chat")
            # Intentar con alternativa
            from langchain_community.document_loaders import PyPDFium2Loader
            try:
                loader = PyPDFium2Loader(file_path)
                logger.info("PDF cargado con éxito usando PyPDFium2Loader como alternativa", "app.process_file_for_chat")
            except Exception as e2:
                # Si todo falla, intentar con un loader más básico
                from langchain_community.document_loaders import UnstructuredPDFLoader
                try:
                    loader = UnstructuredPDFLoader(file_path)
                    logger.info("PDF cargado con éxito usando UnstructuredPDFLoader como última alternativa", "app.process_file_for_chat")
                except Exception as e3:
                    # Error fatal, no se puede procesar el PDF
                    error_msg = f"No se pudo cargar el PDF con ningún cargador disponible: {str(e3)}"
                    logger.error(error_msg, "app.process_file_for_chat")
                    raise ValueError(error_msg)
    elif file_extension == '.docx':
        loader = Docx2txtLoader(file_path)
    elif file_extension in ['.txt', '.md', '.csv']:
        loader = TextLoader(file_path)
    else:
        error_msg = f"Formato de archivo no soportado: {file_extension}"
        logger.error(error_msg, "app.process_file_for_chat")
        raise ValueError(error_msg)

    try:
        documents = loader.load()
        set_embedding_progress(progress_id, status="document_loaded", attempt=0, waiting_seconds=0, completed=False)

        # Verificar si hay documentos antes de procesarlos
        if not documents:
            # Intentar fallback básico con PyPDF2
            fallback_text = ""
            if file_extension == '.pdf':
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(file_path)
                    fallback_text = "\n".join((page.extract_text() or "") for page in reader.pages)
                except Exception as fallback_exc:
                    logger.warning(f"Fallback PyPDF2 sin contenido: {fallback_exc}", "app.process_file_for_chat")

            # Si hay textos de imágenes, usarlos como contenido
            if fallback_text.strip():
                from langchain_core.documents import Document
                documents = [Document(page_content=fallback_text, metadata={"source": file_path})]
            elif file_extension == '.pdf' and image_texts:
                from langchain_core.documents import Document
                for i, text in enumerate(image_texts):
                    documents.append(Document(page_content=text, metadata={"source": file_path, "page": f"imagen-{i+1}"}))
            else:
                raise ValueError("No se pudo extraer contenido del archivo")

        # Si hay textos de imágenes, añadirlos como documentos adicionales (modo full)
        if file_extension == '.pdf' and image_texts and process_mode == "full":
            from langchain_core.documents import Document
            for i, text in enumerate(image_texts):
                img_doc = Document(
                    page_content=text,
                    metadata={"source": file_path, "page": f"imagen-{i+1}", "mode": "full_ocr"}
                )
                documents.append(img_doc)

        # Para modo ocr_only: reemplazar páginas con imágenes por su OCR consolidado
        if file_extension == '.pdf' and process_mode == "ocr_only" and page_ocr_texts:
            # Identificar páginas con imágenes
            pages_with_images = {idx for idx, _ in page_ocr_texts}

            filtered_docs = []
            for doc in documents:
                page_meta = doc.metadata.get("page")
                try:
                    page_idx = int(page_meta) if page_meta is not None else None
                except (TypeError, ValueError):
                    page_idx = None

                if page_idx is not None and page_idx in pages_with_images:
                    # Omitir el texto original de esas páginas para no duplicar
                    continue
                filtered_docs.append(doc)

            from langchain_core.documents import Document
            for page_idx, text in page_ocr_texts:
                filtered_docs.append(
                    Document(
                        page_content=text,
                        metadata={"source": file_path, "page": page_idx + 1, "mode": "ocr_page"}
                    )
                )

            documents = filtered_docs

        # Dividir documentos en chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        chunks = text_splitter.split_documents(documents)
        set_embedding_progress(progress_id, status="chunking", attempt=0, waiting_seconds=0, completed=False)

        # Verificar si hay chunks antes de crear la base de datos vectorial
        if not chunks:
            raise ValueError(
                "El archivo no contiene texto extraíble. Instala PyMuPDF para OCR o proporciona un PDF con texto seleccionable."
            )

        # Añadir hash del archivo a los metadatos de cada chunk para poder identificarlo después
        file_hash = hashlib.md5(open(file_path, 'rb').read()).hexdigest()
        filename = os.path.basename(file_path)
        for chunk in chunks:
            chunk.metadata['file_hash'] = file_hash
            chunk.metadata['filename'] = filename

        # Añadir chunks a la base vectorial del chat
        add_chunks_to_chat_vectorstore(chat_id, chunks, progress_id)

        return file_hash, len(chunks), chunks
    except Exception as e:
        # Capturar errores específicos y proporcionar un mensaje más descriptivo
        set_embedding_progress(progress_id, status="failed", completed=True, error=str(e))
        raise ValueError(f"Error al procesar el archivo: {str(e)}")


def _add_chunks_to_vectorstore(store_path, new_chunks, *, progress_id=None, context_label="chat", log_source="app.add_chunks_to_vectorstore"):
    """Añade documentos a una carpeta FAISS concreta, creando o fusionando según corresponda."""
    index_path = os.path.join(store_path, "index.faiss")
    metadata_path = os.path.join(store_path, "index.pkl")
    has_valid_vectorstore = os.path.exists(index_path) and os.path.exists(metadata_path)

    set_embedding_progress(progress_id, status="vectorizing", attempt=0, waiting_seconds=0, completed=False)

    try:
        if os.path.exists(store_path) and not has_valid_vectorstore:
            logger.warning(
                f"La carpeta de {context_label} existe pero los archivos de índice faltan. Se recreará la base vectorial.",
                log_source,
            )
            shutil.rmtree(store_path, ignore_errors=True)
            os.makedirs(store_path, exist_ok=True)
            has_valid_vectorstore = False

        vectorstore = None
        if has_valid_vectorstore:
            logger.debug(
                f"Cargando base vectorial existente para {context_label}",
                log_source,
            )
            try:
                vectorstore = FAISS.load_local(
                    store_path,
                    embeddings,
                    allow_dangerous_deserialization=True,
                )
            except Exception as load_error:
                logger.warning(
                    f"No se pudo cargar la base vectorial existente para {context_label}: {load_error}. Se recreará.",
                    log_source,
                )
                shutil.rmtree(store_path, ignore_errors=True)
                os.makedirs(store_path, exist_ok=True)
                vectorstore = None

        if vectorstore is not None:
            logger.debug(
                f"Añadiendo {len(new_chunks)} nuevos chunks a la base vectorial de {context_label}",
                log_source,
            )
            new_vectorstore = build_vectorstore_with_retry(new_chunks, embeddings, progress_id=progress_id)
            vectorstore.merge_from(new_vectorstore)
        else:
            logger.debug(
                f"Creando nueva base vectorial para {context_label}",
                log_source,
            )
            if not os.path.exists(store_path):
                os.makedirs(store_path, exist_ok=True)
            vectorstore = build_vectorstore_with_retry(new_chunks, embeddings, progress_id=progress_id)

        vectorstore.save_local(store_path)
        logger.info(
            f"Base vectorial de {context_label} actualizada con {len(new_chunks)} chunks",
            log_source,
        )

    except Exception as e:
        logger.error(f"Error al actualizar base vectorial de {context_label}: {str(e)}", log_source)
        raise


def add_chunks_to_chat_vectorstore(chat_id, new_chunks, progress_id=None):
    """Añade chunks a la base vectorial específica del chat."""
    chat_db_path = os.path.join(VECTORDB_DIR, str(chat_id))
    _add_chunks_to_vectorstore(
        chat_db_path,
        new_chunks,
        progress_id=progress_id,
        context_label=f"chat {chat_id}",
        log_source="app.add_chunks_to_chat_vectorstore",
    )


def _resolve_vectorstore_path(path_fragment: str | None) -> str | None:
    if not path_fragment:
        return None
    if os.path.isabs(path_fragment):
        return path_fragment
    return os.path.join(VECTORDB_DIR, path_fragment)


def extend_attached_knowledge_bases(user_id, attached_ids, new_chunks):
    """Añade nuevos documentos a todas las bases RAG asociadas al chat actual."""
    if not attached_ids or not new_chunks:
        return

    ids = list(dict.fromkeys(attached_ids))
    if not ids:
        return

    bases = (
        KnowledgeBase.query.filter(
            KnowledgeBase.user_id == user_id,
            KnowledgeBase.id.in_(ids)
        ).all()
    )

    if not bases:
        return

    for kb in bases:
        store_path = _resolve_vectorstore_path(kb.vectorstore_path)
        if not store_path:
            logger.warning(
                f"La base RAG '{kb.name}' ({kb.id}) no tiene una ruta válida. Se omite la actualización.",
                "app.extend_attached_knowledge_bases",
            )
            continue

        try:
            _add_chunks_to_vectorstore(
                store_path,
                new_chunks,
                progress_id=None,
                context_label=f"base RAG '{kb.name}'",
                log_source="app.extend_attached_knowledge_bases",
            )
        except Exception as exc:
            logger.error(
                f"Error al ampliar la base RAG '{kb.name}' ({kb.id}): {exc}",
                "app.extend_attached_knowledge_bases",
            )


def rebuild_chat_vectorstore(chat_id, file_hashes_to_keep, progress_id=None):
    """Reconstruye la base vectorial del chat con solo los archivos especificados
    
    Args:
        chat_id: ID del chat
        file_hashes_to_keep: Lista de hashes de archivos que se deben mantener
        progress_id: ID para seguimiento del progreso
    """
    chat_db_path = os.path.join(VECTORDB_DIR, str(chat_id))
    
    if not file_hashes_to_keep:
        # Si no hay archivos que mantener, eliminar toda la base vectorial
        if os.path.exists(chat_db_path):
            shutil.rmtree(chat_db_path)
            logger.info(f"Base vectorial del chat {chat_id} eliminada (no hay archivos)", "app.rebuild_chat_vectorstore")
        return
    
    if not os.path.exists(chat_db_path):
        logger.warning(f"Base vectorial del chat {chat_id} no existe para reconstruir", "app.rebuild_chat_vectorstore")
        return
    
    try:
        # Cargar base vectorial existente
        vectorstore = FAISS.load_local(chat_db_path, embeddings, allow_dangerous_deserialization=True)
        
        # Obtener todos los documentos
        all_docs = vectorstore.docstore._dict.values()  # type: ignore[attr-defined]
        
        # Filtrar documentos que pertenecen a archivos que se deben mantener
        filtered_docs = [
            doc for doc in all_docs 
            if doc.metadata.get('file_hash') in file_hashes_to_keep
        ]
        
        if not filtered_docs:
            # No hay documentos que mantener, eliminar la base vectorial
            shutil.rmtree(chat_db_path)
            logger.info(f"Base vectorial del chat {chat_id} eliminada (documentos filtrados)", "app.rebuild_chat_vectorstore")
            return
        
        # Recrear la base vectorial solo con los documentos filtrados
        set_embedding_progress(progress_id, status="rebuilding", attempt=0, waiting_seconds=0, completed=False)
        
        # Eliminar la base existente
        shutil.rmtree(chat_db_path)
        os.makedirs(chat_db_path, exist_ok=True)
        
        # Crear nueva base vectorial con los documentos filtrados
        new_vectorstore = build_vectorstore_with_retry(filtered_docs, embeddings, progress_id=progress_id)
        new_vectorstore.save_local(chat_db_path)
        
        logger.info(f"Base vectorial del chat {chat_id} reconstruida con {len(filtered_docs)} chunks de {len(file_hashes_to_keep)} archivos", "app.rebuild_chat_vectorstore")
        
    except Exception as e:
        logger.error(f"Error al reconstruir base vectorial del chat {chat_id}: {str(e)}", "app.rebuild_chat_vectorstore")
        raise

def query_documents_for_chat(query, chat_id, k=3, user_id=None, extra_base_ids=None):
    """Consulta documentos relevantes de las bases vectoriales del chat y bases guardadas anexadas."""
    if not (chat_id or extra_base_ids):
        return []

    vector_paths = []
    if chat_id:
        chat_db_path = os.path.join(VECTORDB_DIR, str(chat_id))
        if os.path.exists(chat_db_path):
            vector_paths.append(chat_db_path)
        else:
            logger.debug(f"No existe base vectorial para el chat {chat_id}", "app.query_documents_for_chat")

    if extra_base_ids and user_id:
        for kb_id in extra_base_ids:
            kb = KnowledgeBase.query.filter_by(id=kb_id, user_id=user_id).first()
            if not kb:
                continue
            kb_path = os.path.join(VECTORDB_DIR, kb.vectorstore_path)
            if os.path.exists(kb_path):
                vector_paths.append(kb_path)

    if not vector_paths:
        return []

    results = []
    for path in vector_paths:
        try:
            vectorstore = FAISS.load_local(
                path,
                embeddings,
                allow_dangerous_deserialization=True,
            )
            results.extend(vectorstore.similarity_search(query, k=k))
        except Exception as exc:
            logger.warning(
                f"No se pudo consultar la base vectorial en {path}: {exc}",
                "app.query_documents_for_chat_warn"
            )

    if not results:
        return []

    sorted_results = sorted(results, key=lambda doc: doc.metadata.get('score', 0), reverse=True)
    logger.debug(
        f"Encontrados {len(sorted_results)} documentos combinados para el chat {chat_id}",
        "app.query_documents_for_chat"
    )
    return sorted_results[:k]


# Mantener función legacy para compatibilidad con código existente
def query_documents(query, file_hashes, k=3):
    """Consulta documentos relevantes para RAG (función legacy para compatibilidad)"""
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
            # Asignar tipo según si existen usuarios previos (el primero será admin)
            existing_users = User.query.count()
            new_user_type = 0 if existing_users == 0 else 1

            user = User(username=username, email=email, user_type=new_user_type)  # type: ignore[call-arg]
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
    is_admin = bool(getattr(current_user, 'is_admin', False))
    app_version, _ = read_app_version()
    logger.debug(
        f"Renderizando index para usuario {getattr(current_user, 'username', 'desconocido')} (ID: {user_id}) con permisos admin={is_admin}",
        "app.index"
    )
    
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
        session['attached_bases'] = chat_data.get('attached_bases', [])
        logger.debug(f"Cargando file_hashes para chat inicial: {len(session['file_hashes'])} archivos", "app.index")
    else:
        # No hay chats existentes, crear uno nuevo
        logger.debug(f"No hay chats existentes, creando uno nuevo", "app.index")
        chat_id = str(uuid.uuid4())
        session['chat_id'] = chat_id
        # Inicializar file_hashes vacíos para el nuevo chat
        session['file_hashes'] = []
        session['attached_bases'] = []
        # Crear un nuevo chat con título predeterminado
        save_chat_history(
            user_id,
            [],
            None,
            "Nueva conversación",
            rag_top_k=DEFAULT_RAG_TOP_K,
            temperature=DEFAULT_TEMPERATURE,
            message_history_limit=DEFAULT_HISTORY_LIMIT,
            attached_bases=[]
        )
        # Actualizar la lista de chats
        chats = get_user_chats(user_id)

    return render_template(
        'index.html',
        chats=chats,
        is_admin=is_admin,
        app_version=app_version,
        rag_top_k_default=DEFAULT_RAG_TOP_K,
        rag_top_k_max=MAX_RAG_TOP_K,
        temperature_default=DEFAULT_TEMPERATURE,
        history_default=DEFAULT_HISTORY_LIMIT,
        history_max=MAX_HISTORY_LIMIT,
    )

@app.route('/api/chat', methods=['POST'])
def chat():
    """Endpoint para procesar mensajes de chat"""
    data = request.get_json(silent=True) or {}
    user_message = data.get('message', '')
    chat_id = data.get('chat_id')
    model_id = data.get('model_id')  # Obtener el modelo seleccionado
    custom_system_message = data.get('system_message')  # Obtener mensaje de sistema personalizado
    requested_top_k = data.get('rag_top_k')
    requested_temperature = data.get('temperature')

    user_id = get_user_id()

    # Cargar historial de chat existente o crear uno nuevo
    messages = load_chat_history(user_id, chat_id)

    # Obtener datos completos del chat para acceder al mensaje del sistema guardado
    chat_data = get_chat_data(user_id, chat_id)
    saved_system_message = chat_data.get('system_message')
    stored_top_k = chat_data.get('rag_top_k', DEFAULT_RAG_TOP_K)
    stored_temperature = chat_data.get('temperature', DEFAULT_TEMPERATURE)
    stored_history_limit = chat_data.get('message_history_limit', DEFAULT_HISTORY_LIMIT)

    rag_top_k = _resolve_int_setting(requested_top_k, stored_top_k, minimum=1, maximum=MAX_RAG_TOP_K)
    generation_temperature = _resolve_float_setting(requested_temperature, stored_temperature, minimum=0.0, maximum=2.0, precision=1)
    message_history_limit = _resolve_int_setting(data.get('message_history_limit'), stored_history_limit, minimum=1, maximum=MAX_HISTORY_LIMIT)
    
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
        image_urls = []
        for img in img_tags:
            src = getattr(img, 'get', lambda *_: None)('src')
            if isinstance(src, str) and src.startswith('data:image/'):
                image_urls.append(src)

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

    # Realizar RAG usando la base vectorial del chat
    context = ""
    attached_bases = chat_data.get('attached_bases', [])
    relevant_docs = query_documents_for_chat(
        user_message,
        chat_id,
        k=rag_top_k,
        user_id=user_id,
        extra_base_ids=attached_bases,
    )
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

    # Añadir recordatorio ligero para respuestas estructuradas cuando se soliciten documentos
    system_message += (
        "\n\nNOTA: Si el usuario pide explícitamente un documento (informe, especificación, report, proposal) "
        "responde con un documento completo en Markdown bien estructurado (títulos, secciones, listas, tablas si aplica)."
    )

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
    
    # Añadir historial de conversación limitado por la configuración activa
    messages_to_add = messages[-message_history_limit:]
    
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
                temperature=generation_temperature,
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
                    temperature=generation_temperature,
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
            temperature=generation_temperature,
            max_completion_tokens=4090
        )
        assistant_message = response.choices[0].message.content
    else:
        response = model_client.chat.completions.create(
            model=model_id if model_id else AZURE_OPENAI_DEPLOYMENT,
            messages=api_messages,
            temperature=generation_temperature,
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

    chat_id = save_chat_history(
        user_id,
        messages,
        system_message_to_save,
        chat_data.get('title'),
        file_hashes=file_hashes,
        rag_top_k=rag_top_k,
        temperature=generation_temperature,
        message_history_limit=message_history_limit
    )

    original_assistant_message = assistant_message

    return jsonify({
        "response": original_assistant_message.strip(),
        "raw_response": original_assistant_message,
        "chat_id": chat_id
    })


@app.route('/api/export_word', methods=['POST'])
@login_required
def export_word():
    """Genera un documento Word a partir del contenido enviado por el cliente."""
    payload = request.get_json(silent=True) or {}
    content = payload.get('content')

    if not isinstance(content, str):
        return jsonify({"error": "Contenido inválido"}), 400

    content = content.strip()
    if not content:
        return jsonify({"error": "No hay contenido para exportar"}), 400

    output_dir = os.environ.get('WORD_DOC_OUTPUT_DIR', os.path.join('data', 'word_docs'))

    try:
        file_path = guardar_respuesta_en_word(content, output_dir)
    except Exception as exc:  # pragma: no cover - protección adicional
        logger.error(f"Error generando documento Word: {exc}", "app.export_word")
        return jsonify({"error": "No se pudo generar el documento Word"}), 500

    file_name = os.path.basename(file_path)
    download_url = f"/api/word_docs/{file_name}"

    logger.info(f"Documento Word generado bajo demanda: {file_name}", "app.export_word")

    return jsonify({
        "file_name": file_name,
        "download_url": download_url
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
            session.get('file_hashes', []),
            rag_top_k=current_chat_data.get('rag_top_k'),
            temperature=current_chat_data.get('temperature'),
            message_history_limit=current_chat_data.get('message_history_limit'),
            attached_bases=session.get('attached_bases', [])
        )
        logger.debug(f"Guardado estado del chat actual {current_chat_id} antes de cambiar", "app.get_chat")
    
    # Cargar datos del nuevo chat
    chat_data = get_chat_data(user_id, chat_id)
    messages = chat_data.get('messages', [])
    
    # Actualizar la sesión con el ID del nuevo chat
    session['chat_id'] = chat_id
    
    # Actualizar los file_hashes en la sesión con los del chat seleccionado
    session['file_hashes'] = chat_data.get('file_hashes', [])
    session['attached_bases'] = chat_data.get('attached_bases', [])
    logger.debug(f"Cargando chat {chat_id} con {len(session['file_hashes'])} archivos asociados", "app.get_chat")
    
    # Devolver datos completos del chat, no solo mensajes
    return jsonify({
        'messages': messages,
        'system_message': chat_data.get('system_message'),
        'title': chat_data.get('title'),
        'file_hashes': chat_data.get('file_hashes', []),
        'rag_top_k': chat_data.get('rag_top_k', DEFAULT_RAG_TOP_K),
        'temperature': chat_data.get('temperature', DEFAULT_TEMPERATURE),
        'message_history_limit': chat_data.get('message_history_limit', DEFAULT_HISTORY_LIMIT),
        'attached_bases': chat_data.get('attached_bases', [])
    })

@app.route('/api/upload', methods=['POST'])
@login_required
def upload_file():
    """Endpoint para subir archivos y añadirlos a la base RAG del chat actual"""
    if 'file' not in request.files:
        logger.warning("No se proporcionó archivo en la solicitud", "app.upload_file")
        return jsonify({"error": "No se proporcionó archivo"}), 400
    
    file = request.files['file']
    process_mode = request.form.get('process_mode')
    if not process_mode:
        # compatibilidad con booleano anterior
        process_images_legacy = request.form.get('process_images', 'true').lower() == 'true'
        process_mode = 'full' if process_images_legacy else 'text_only'

    if process_mode not in {'full', 'text_only', 'ocr_only'}:
        process_mode = 'full'
    progress_id = request.form.get('upload_id') or str(uuid.uuid4())
    
    if file.filename == '':
        logger.warning("Nombre de archivo vacío", "app.upload_file")
        return jsonify({"error": "No se seleccionó archivo"}), 400
    
    # Verificar que hay un chat activo
    chat_id = session.get('chat_id')
    if not chat_id:
        logger.warning("No hay chat activo para subir archivo", "app.upload_file")
        return jsonify({"error": "No hay chat activo. Crea un nuevo chat primero."}), 400
    
    if file:
        try:
            filename = secure_filename(file.filename)
            logger.info(f"Procesando archivo subido para chat {chat_id}: {filename}", "app.upload_file")
            set_embedding_progress(progress_id, status="queued", filename=filename, completed=False, attempt=0, waiting_seconds=0)
            
            # Guardar archivo
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Procesar archivo para RAG y añadirlo al chat actual
            file_hash, num_chunks, chunks = process_file_for_chat(file_path, chat_id, process_mode, progress_id=progress_id)
            
            # Guardar referencia al archivo en la sesión
            if 'file_hashes' not in session:
                session['file_hashes'] = []
            
            if file_hash not in session['file_hashes']:
                session['file_hashes'].append(file_hash)
            
            # Actualizar el chat actual con el nuevo file_hash
            user_id = get_user_id()
            chat_data = get_chat_data(user_id, chat_id)
            save_chat_history(
                user_id, 
                chat_data.get('messages', []), 
                chat_data.get('system_message'), 
                chat_data.get('title'),
                session['file_hashes'],
                rag_top_k=chat_data.get('rag_top_k'),
                temperature=chat_data.get('temperature'),
                message_history_limit=chat_data.get('message_history_limit'),
                attached_bases=session.get('attached_bases', [])
            )
            logger.debug(f"Chat {chat_id} actualizado con nuevo archivo: {filename}", "app.upload_file")

            attached_bases = session.get('attached_bases', [])
            try:
                extend_attached_knowledge_bases(user_id, attached_bases, chunks)
            except Exception:
                # El helper ya registra el detalle del error; no interrumpimos la carga del archivo.
                pass
            
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
            
            logger.info(f"Archivo procesado exitosamente para chat {chat_id}: {filename} ({num_chunks} fragmentos)", "app.upload_file")
            set_embedding_progress(progress_id, status="completed", completed=True, attempt=None, waiting_seconds=0, file_hash=file_hash, chunks=num_chunks)
            return jsonify({
                "success": True,
                "filename": filename,
                "file_hash": file_hash,
                "chunks": num_chunks,
                "progress_id": progress_id,
                "chat_id": chat_id
            })
            
        except ValueError as e:
            logger.error(f"Error al procesar archivo (valor): {str(e)}", "app.upload_file")
            set_embedding_progress(progress_id, status="failed", completed=True, error=str(e))
            return jsonify({"error": str(e), "progress_id": progress_id}), 400
        except Exception as e:
            logger.error(f"Error al procesar archivo: {str(e)}", "app.upload_file")
            set_embedding_progress(progress_id, status="failed", completed=True, error=str(e))
            return jsonify({"error": str(e), "progress_id": progress_id}), 500
    
    return jsonify({"error": "Error desconocido"}), 500


@app.route('/api/upload/progress/<progress_id>', methods=['GET'])
@login_required
def get_upload_progress(progress_id):
    with EMBEDDING_PROGRESS_LOCK:
        progress = EMBEDDING_PROGRESS.get(progress_id)

    if not progress:
        return jsonify({
            "found": False,
            "progress": None,
            "server_time": datetime.utcnow().isoformat()
        })

    return jsonify({
        "found": True,
        "progress": progress,
        "server_time": datetime.utcnow().isoformat()
    })

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
            session.get('file_hashes', []),
            rag_top_k=current_chat_data.get('rag_top_k'),
            temperature=current_chat_data.get('temperature'),
            message_history_limit=current_chat_data.get('message_history_limit'),
            attached_bases=session.get('attached_bases', [])
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
    """Endpoint para eliminar un archivo del chat actual y reconstruir su base RAG"""
    file_hashes = session.get('file_hashes', [])
    chat_id = session.get('chat_id')

    if not chat_id:
        return jsonify({"error": "No hay chat activo"}), 400

    if file_hash in file_hashes:
        file_hashes.remove(file_hash)
        session['file_hashes'] = file_hashes

        # Actualizar el chat actual con la lista de archivos modificada
        user_id = get_user_id()
        chat_data = get_chat_data(user_id, chat_id)
        save_chat_history(
            user_id, 
            chat_data.get('messages', []), 
            chat_data.get('system_message'), 
            chat_data.get('title'),
            file_hashes,
            rag_top_k=chat_data.get('rag_top_k'),
            temperature=chat_data.get('temperature'),
            message_history_limit=chat_data.get('message_history_limit'),
            attached_bases=session.get('attached_bases', [])
        )
        logger.debug(f"Chat {chat_id} actualizado tras eliminar archivo {file_hash}", "app.delete_file")

        # Reconstruir la base vectorial del chat sin el archivo eliminado
        try:
            rebuild_chat_vectorstore(chat_id, file_hashes)
            logger.info(f"Base vectorial del chat {chat_id} reconstruida sin archivo {file_hash}", "app.delete_file")
        except Exception as e:
            logger.error(f"Error al reconstruir base vectorial tras eliminar archivo: {str(e)}", "app.delete_file")
            # No retornamos error porque el archivo ya se eliminó de la lista
        
        return jsonify({"success": True, "chat_id": chat_id})

    return jsonify({"error": "Archivo no encontrado"}), 404


@app.route('/api/knowledge_bases', methods=['GET'])
@login_required
def list_knowledge_bases():
    """Devuelve las bases RAG guardadas por el usuario actual."""

    user_id = get_user_id()
    chat_id = request.args.get('chat_id')
    attached = set()

    if chat_id:
        chat_data = get_chat_data(user_id, chat_id)
        attached = set(chat_data.get('attached_bases', []))

    bases = (
        KnowledgeBase.query.filter_by(user_id=user_id)
        .order_by(KnowledgeBase.created_at.desc())
        .all()
    )

    return jsonify({
        "knowledge_bases": [serialize_knowledge_base(base, base.id in attached) for base in bases],
        "attached_bases": list(attached)
    })


@app.route('/api/knowledge_bases', methods=['POST'])
@login_required
def save_knowledge_base():
    """Guarda la base vectorial del chat actual con un nombre personalizado."""

    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    chat_id = data.get('chat_id') or session.get('chat_id')
    user_id = get_user_id()

    if not name:
        return jsonify({"error": "El nombre es obligatorio"}), 400
    if not chat_id:
        return jsonify({"error": "No hay chat activo para guardar"}), 400

    chat_db_path = os.path.join(VECTORDB_DIR, str(chat_id))
    if not os.path.exists(chat_db_path):
        return jsonify({"error": "Este chat no tiene una base RAG para guardar"}), 400

    if KnowledgeBase.query.filter_by(user_id=user_id, name=name).first():
        return jsonify({"error": "Ya existe una base con ese nombre"}), 409

    kb_id = str(uuid.uuid4())
    relative_path = os.path.join('knowledge_bases', kb_id)
    destination = os.path.join(KNOWLEDGE_BASE_DIR, kb_id)

    try:
        shutil.copytree(chat_db_path, destination)
    except Exception as exc:
        logger.error(f"No se pudo copiar la base vectorial del chat {chat_id} a {destination}: {exc}", "app.save_knowledge_base")
        return jsonify({"error": "No se pudo guardar la base RAG"}), 500

    kb = KnowledgeBase(
        id=kb_id,
        user_id=user_id,
        name=name,
        vectorstore_path=relative_path,
        source_chat_id=chat_id,
    )

    db.session.add(kb)
    db.session.commit()

    logger.info(f"Base RAG guardada ({name}) por el usuario {user_id}", "app.save_knowledge_base")

    return jsonify({
        "success": True,
        "knowledge_base": serialize_knowledge_base(kb)
    }), 201


@app.route('/api/chat/<chat_id>/knowledge_bases', methods=['GET'])
@login_required
def get_chat_knowledge_bases(chat_id):
    """Lista las bases guardadas del usuario e indica cuáles están asociadas al chat."""

    user_id = get_user_id()
    chat_file = os.path.join(DATA_DIR, f"{user_id}_{chat_id}.json")
    if not os.path.exists(chat_file):
        return jsonify({"error": "Chat no encontrado"}), 404

    chat_data = get_chat_data(user_id, chat_id)
    attached = set(chat_data.get('attached_bases', []))

    bases = (
        KnowledgeBase.query.filter_by(user_id=user_id)
        .order_by(KnowledgeBase.created_at.desc())
        .all()
    )

    return jsonify({
        "knowledge_bases": [serialize_knowledge_base(base, base.id in attached) for base in bases],
        "attached_bases": list(attached)
    })


@app.route('/api/chat/<chat_id>/knowledge_bases/<kb_id>', methods=['POST'])
@login_required
def attach_knowledge_base(chat_id, kb_id):
    """Asocia una base guardada al chat actual."""

    user_id = get_user_id()
    kb = KnowledgeBase.query.filter_by(id=kb_id, user_id=user_id).first()
    if not kb:
        return jsonify({"error": "Base RAG no encontrada"}), 404

    chat_file = os.path.join(DATA_DIR, f"{user_id}_{chat_id}.json")
    if not os.path.exists(chat_file):
        return jsonify({"error": "Chat no encontrado"}), 404

    chat_data = get_chat_data(user_id, chat_id)
    attached = set(chat_data.get('attached_bases', []))

    if kb_id not in attached:
        attached.add(kb_id)
        _persist_attached_bases(user_id, chat_id, chat_data, attached)

    return jsonify({"success": True, "attached_bases": list(attached)})


@app.route('/api/chat/<chat_id>/knowledge_bases/<kb_id>', methods=['DELETE'])
@login_required
def detach_knowledge_base(chat_id, kb_id):
    """Desasocia una base guardada del chat actual."""

    user_id = get_user_id()
    chat_file = os.path.join(DATA_DIR, f"{user_id}_{chat_id}.json")
    if not os.path.exists(chat_file):
        return jsonify({"error": "Chat no encontrado"}), 404

    chat_data = get_chat_data(user_id, chat_id)
    attached = set(chat_data.get('attached_bases', []))

    if kb_id in attached:
        attached.remove(kb_id)
        _persist_attached_bases(user_id, chat_id, chat_data, attached)

    return jsonify({"success": True, "attached_bases": list(attached)})
            
def read_app_version(default="0.0.0"):
    """Lee la versión de la aplicación desde el archivo version.txt."""
    version_path = os.path.join(os.getcwd(), 'version.txt')
    try:
        with open(version_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if content:
                return content, True
            logger.warning("Archivo version.txt vacío", "app.read_app_version")
    except FileNotFoundError:
        logger.warning("Archivo version.txt no encontrado", "app.read_app_version")
    except Exception as exc:
        logger.error(f"Error al leer version.txt: {exc}", "app.read_app_version")
    return default, False


@app.route('/api/version', methods=['GET'])
def get_version():
    """Endpoint para obtener la versión de la aplicación"""
    version, success = read_app_version()
    status_code = 200 if success else 500
    return jsonify({"version": version}), status_code


@app.route('/api/help/content', methods=['GET'])
@login_required
def get_help_content():
    """Devuelve el contenido del archivo HELP.md para mostrar la ayuda."""
    help_path = os.path.join(os.getcwd(), 'HELP.md')

    try:
        with open(help_path, 'r', encoding='utf-8') as fh:
            content = fh.read()
        return jsonify({"content": content})
    except FileNotFoundError:
        logger.error("Archivo HELP.md no encontrado", "app.get_help_content")
        return jsonify({"error": "HELP no encontrado"}), 404
    except Exception as exc:
        logger.error(f"Error al leer HELP.md: {exc}", "app.get_help_content")
        return jsonify({"error": "No se pudo cargar la ayuda"}), 500


@app.route('/help', methods=['GET'])
@login_required
def help_page():
    """Renderiza la página de ayuda en una nueva pestaña."""
    return render_template('help.html')


@app.route('/api/account/change-password', methods=['POST'])
@login_required
def change_password():
    """Actualiza la contraseña del usuario autenticado."""
    data = request.get_json(silent=True) or {}
    current_password = (data.get('current_password') or '').strip()
    new_password = (data.get('new_password') or '').strip()

    if not current_password or not new_password:
        return jsonify({
            "success": False,
            "error": "La contraseña actual y la nueva son obligatorias."
        }), 400

    if len(new_password) < 8:
        return jsonify({
            "success": False,
            "error": "La nueva contraseña debe tener al menos 8 caracteres."
        }), 400

    if not current_user.check_password(current_password):
        logger.warning(
            f"Intento fallido de cambio de contraseña para usuario {current_user.id}",
            "app.change_password"
        )
        return jsonify({
            "success": False,
            "error": "La contraseña actual no es correcta."
        }), 400

    if current_password == new_password:
        return jsonify({
            "success": False,
            "error": "La nueva contraseña debe ser diferente a la actual."
        }), 400

    try:
        current_user.set_password(new_password)
        db.session.commit()
        logger.info(
            f"Contraseña actualizada para el usuario {current_user.id}",
            "app.change_password"
        )
        return jsonify({"success": True}), 200
    except Exception as exc:
        db.session.rollback()
        logger.error(
            f"Error al actualizar la contraseña para el usuario {current_user.id}: {exc}",
            "app.change_password"
        )
        return jsonify({
            "success": False,
            "error": "No se pudo actualizar la contraseña. Inténtalo nuevamente."
        }), 500


@app.route('/api/admin/users', methods=['GET'])
@login_required
def admin_list_users():
    """Devuelve la lista de usuarios para administración."""
    if not current_user.is_admin:
        logger.warning(
            f"Intento de listar usuarios sin privilegios por parte del usuario {current_user.id}",
            "app.admin_list_users"
        )
        return jsonify({
            "success": False,
            "error": "No tienes permisos para realizar esta acción."
        }), 403

    users = User.query.order_by(User.created_at.asc()).all()
    total_admins = sum(1 for user in users if user.is_admin)

    return jsonify({
        "success": True,
        "total_admins": total_admins,
        "users": [{
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_admin": user.is_admin,
            "is_self": user.id == current_user.id,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        } for user in users]
    })


@app.route('/api/admin/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
def admin_reset_user_password(user_id):
    """Permite a un administrador restablecer la contraseña de otro usuario."""
    if not current_user.is_admin:
        logger.warning(
            f"Intento de resetear contraseña sin privilegios por parte del usuario {current_user.id}",
            "app.admin_reset_user_password"
        )
        return jsonify({
            "success": False,
            "error": "No tienes permisos para realizar esta acción."
        }), 403

    target_user = db.session.get(User, user_id)
    if not target_user:
        return jsonify({
            "success": False,
            "error": "Usuario no encontrado."
        }), 404

    if target_user.id == current_user.id:
        return jsonify({
            "success": False,
            "error": "Utiliza tu propio formulario para actualizar tu contraseña."
        }), 400

    data = request.get_json(silent=True) or {}
    new_password = (data.get('new_password') or '').strip()

    if not new_password:
        return jsonify({
            "success": False,
            "error": "La nueva contraseña es obligatoria."
        }), 400

    if len(new_password) < 8:
        return jsonify({
            "success": False,
            "error": "La nueva contraseña debe tener al menos 8 caracteres."
        }), 400

    try:
        target_user.set_password(new_password)
        db.session.commit()
        logger.info(
            f"Contraseña restablecida para el usuario {target_user.id} por admin {current_user.id}",
            "app.admin_reset_user_password"
        )
        return jsonify({"success": True})
    except Exception as exc:
        db.session.rollback()
        logger.error(
            f"Error al restablecer la contraseña del usuario {user_id}: {exc}",
            "app.admin_reset_user_password"
        )
        return jsonify({
            "success": False,
            "error": "No se pudo restablecer la contraseña. Inténtalo nuevamente."
        }), 500


@app.route('/api/admin/users/<int:user_id>/role', methods=['PATCH'])
@login_required
def admin_update_user_role(user_id):
    """Permite otorgar o revocar privilegios de administrador."""
    if not current_user.is_admin:
        logger.warning(
            f"Intento de actualizar rol sin privilegios por parte del usuario {current_user.id}",
            "app.admin_update_user_role"
        )
        return jsonify({
            "success": False,
            "error": "No tienes permisos para realizar esta acción."
        }), 403

    target_user = db.session.get(User, user_id)
    if not target_user:
        return jsonify({
            "success": False,
            "error": "Usuario no encontrado."
        }), 404

    data = request.get_json(silent=True) or {}

    if 'is_admin' not in data:
        return jsonify({
            "success": False,
            "error": "El valor 'is_admin' es obligatorio."
        }), 400

    raw_value = data.get('is_admin')

    try:
        if isinstance(raw_value, bool):
            desired_admin = raw_value
        elif isinstance(raw_value, str):
            normalized = raw_value.strip().lower()
            if normalized in {'true', '1', 'yes', 'on'}:
                desired_admin = True
            elif normalized in {'false', '0', 'no', 'off'}:
                desired_admin = False
            else:
                raise ValueError("Valor de cadena inválido")
        elif isinstance(raw_value, (int, float)):
            desired_admin = bool(raw_value)
        else:
            raise ValueError("Tipo de dato inválido")
    except ValueError:
        return jsonify({
            "success": False,
            "error": "El valor 'is_admin' debe ser booleano."
        }), 400

    if target_user.is_admin and not desired_admin:
        remaining_admins = User.query.filter(User.user_type == 0, User.id != user_id).count()
        if remaining_admins == 0:
            return jsonify({
                "success": False,
                "error": "Debe existir al menos un administrador en el sistema."
            }), 400

    if target_user.is_admin == desired_admin:
        total_admins = User.query.filter(User.user_type == 0).count()
        return jsonify({
            "success": True,
            "unchanged": True,
            "total_admins": total_admins,
            "user": {
                "id": target_user.id,
                "username": target_user.username,
                "is_admin": target_user.is_admin,
                "is_self": target_user.id == current_user.id
            }
        })

    try:
        target_user.user_type = 0 if desired_admin else 1
        db.session.commit()
        total_admins = User.query.filter(User.user_type == 0).count()
        logger.info(
            f"Rol actualizado para usuario {target_user.id} por admin {current_user.id}. Admin={desired_admin}",
            "app.admin_update_user_role"
        )
        return jsonify({
            "success": True,
            "total_admins": total_admins,
            "user": {
                "id": target_user.id,
                "username": target_user.username,
                "is_admin": target_user.is_admin,
                "is_self": target_user.id == current_user.id
            }
        })
    except Exception as exc:
        db.session.rollback()
        logger.error(
            f"Error al actualizar el rol del usuario {user_id}: {exc}",
            "app.admin_update_user_role"
        )
        return jsonify({
            "success": False,
            "error": "No se pudo actualizar el rol del usuario. Inténtalo nuevamente."
        }), 500


@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@login_required
def admin_delete_user(user_id):
    """Elimina un usuario junto con sus datos asociados."""
    if not current_user.is_admin:
        logger.warning(
            f"Intento de eliminar usuario sin privilegios por parte del usuario {current_user.id}",
            "app.admin_delete_user"
        )
        return jsonify({
            "success": False,
            "error": "No tienes permisos para realizar esta acción."
        }), 403

    target_user = db.session.get(User, user_id)
    if not target_user:
        return jsonify({
            "success": False,
            "error": "Usuario no encontrado."
        }), 404

    if target_user.id == current_user.id:
        return jsonify({
            "success": False,
            "error": "No puedes eliminar tu propia cuenta desde este panel."
        }), 400

    if target_user.is_admin:
        remaining_admins = User.query.filter(User.user_type == 0, User.id != user_id).count()
        if remaining_admins == 0:
            return jsonify({
                "success": False,
                "error": "No puedes eliminar al único administrador disponible."
            }), 400

    try:
        # Eliminar archivos de historial de chat
        removed_chat_files = 0
        for filename in os.listdir(DATA_DIR):
            if filename.startswith(f"{user_id}_") and filename.endswith('.json'):
                file_path = os.path.join(DATA_DIR, filename)
                try:
                    os.remove(file_path)
                    removed_chat_files += 1
                except FileNotFoundError:
                    logger.warning(f"Archivo de chat no encontrado durante la eliminación: {file_path}", "app.admin_delete_user")
                except Exception as exc:
                    logger.warning(f"No se pudo eliminar archivo {file_path}: {exc}", "app.admin_delete_user")

        # Eliminar registros y vectores asociados a archivos
        user_files = File.query.filter_by(user_id=user_id).all()
        for user_file in user_files:
            db_path = os.path.join(VECTORDB_DIR, user_file.file_hash)
            if os.path.exists(db_path):
                shutil.rmtree(db_path, ignore_errors=True)
            db.session.delete(user_file)

        # Limpiar archivos temporales asociados en uploads/users
        users_upload_dir = os.path.join(UPLOAD_DIR, 'users')
        if os.path.isdir(users_upload_dir):
            for filename in os.listdir(users_upload_dir):
                if filename.startswith(f"{user_id}_"):
                    file_path = os.path.join(users_upload_dir, filename)
                    try:
                        os.remove(file_path)
                    except FileNotFoundError:
                        logger.debug(f"Archivo de upload ya inexistente: {file_path}", "app.admin_delete_user")
                    except Exception as exc:
                        logger.warning(f"No se pudo eliminar archivo de upload {file_path}: {exc}", "app.admin_delete_user")

        # Eliminar chats y prompts relacionados
        user_chats = Chat.query.filter_by(user_id=user_id).all()
        for chat in user_chats:
            db.session.delete(chat)

        user_prompts = UserPrompt.query.filter_by(user_id=user_id).all()
        for prompt in user_prompts:
            db.session.delete(prompt)

        db.session.delete(target_user)
        db.session.commit()

        logger.info(
            f"Usuario {target_user.username} (ID {target_user.id}) eliminado por admin {current_user.username}",
            "app.admin_delete_user"
        )
        return jsonify({"success": True, "removed_chat_files": removed_chat_files})
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Error al eliminar usuario {user_id}: {exc}", "app.admin_delete_user")
        return jsonify({
            "success": False,
            "error": "No se pudo eliminar al usuario. Inténtalo nuevamente."
        }), 500


@app.route('/api/chat/<chat_id>', methods=['DELETE'])
def delete_chat(chat_id):
    """Endpoint para eliminar un chat y su base de datos RAG asociada"""
    user_id = get_user_id()
    filename = os.path.join(DATA_DIR, f"{user_id}_{chat_id}.json")

    if os.path.exists(filename):
        os.remove(filename)
        logger.info(f"Archivo de chat eliminado: {filename}", "app.delete_chat")

        # Eliminar la base de datos vectorial asociada al chat
        chat_db_path = os.path.join(VECTORDB_DIR, str(chat_id))
        if os.path.exists(chat_db_path):
            try:
                shutil.rmtree(chat_db_path)
                logger.info(f"Base vectorial del chat {chat_id} eliminada: {chat_db_path}", "app.delete_chat")
            except Exception as e:
                logger.error(f"Error al eliminar base vectorial del chat {chat_id}: {str(e)}", "app.delete_chat")

        # Limpiar sesión si es el chat actual
        if session.get('chat_id') == chat_id:
            session.pop('chat_id', None)
            session.pop('file_hashes', None)

        # Verificar si quedan chats
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
    data = request.get_json(silent=True) or {}
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
        chat_data.get('file_hashes', []),
        rag_top_k=chat_data.get('rag_top_k'),
        temperature=chat_data.get('temperature'),
        message_history_limit=chat_data.get('message_history_limit'),
        attached_bases=chat_data.get('attached_bases', [])
    )

    # Si es el chat actual, actualizar también la sesión
    if session.get('chat_id') == chat_id:
        session['file_hashes'] = chat_data.get('file_hashes', [])
        session['attached_bases'] = chat_data.get('attached_bases', [])

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
        chat_data.get('file_hashes', []),
        rag_top_k=chat_data.get('rag_top_k'),
        temperature=chat_data.get('temperature'),
        message_history_limit=chat_data.get('message_history_limit'),
        attached_bases=chat_data.get('attached_bases', [])
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
    ensure_user_type_consistency()
    backfill_missing_default_prompts()
    migrate_vectorstores_to_chat_system()

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