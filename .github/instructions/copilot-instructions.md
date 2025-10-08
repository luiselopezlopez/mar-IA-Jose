# Mar-IA-Jose Copilot Instructions

## Project Overview
Mar-IA-Jose is a Flask-based AI chat application that integrates multiple Azure OpenAI models (GPT, DeepSeek-R1, o1-mini) with document processing and vector search capabilities using FAISS. Users can upload documents (PDF, DOCX, TXT), which are processed into embeddings for contextual AI conversations.

## Core Architecture

### Application Structure
- **Single-file Flask app** (`app.py` - 1363 lines): All routes, models, and business logic in one file
- **Database models** (`models.py`): SQLAlchemy models for User, Chat, Message, File
- **Custom logging** (`logger.py`): Structured logging with production/development modes
- **Data persistence**: File-based storage in `data/` directory with SQLite database

### Key Components
1. **Multi-model AI integration**: Supports 4+ Azure OpenAI endpoints with dynamic model switching
2. **Document processing pipeline**: Upload → Text extraction → Chunking → Embeddings → FAISS vector store
3. **User authentication**: Flask-Login with session management
4. **Real-time chat**: Server-sent events for streaming responses

## Development Patterns

### Environment Configuration
All configuration via environment variables - see extensive config block in `app.py` lines 94-150:
```python
# Multiple AI model endpoints
AZURE_OPENAI_ENDPOINT = os.environ.get("azure_endpoint")
R1_ENDPOINT = os.environ.get("R1_endpoint")
O1MINI_ENDPOINT = os.environ.get("azure_endpoint_o1mini")
```

### Directory Structure Pattern
- `data/users/{user_id}/` - Per-user file storage
- `data/vectordb/` - FAISS indexes per user
- `data/upload/` - Temporary file processing
- `data/instance/` - SQLite database location

### Custom Logging System
Use the custom logger module instead of standard Python logging:
```python
import logger
logger.info("Message", "module.function")  # Custom format with module context
```

## Critical Workflows

### Document Processing Flow
1. Upload via `/api/upload` → temporary storage in `UPLOAD_DIR`
2. Text extraction using PyPDF2/Docx2txt based on file type
3. Chunking with `RecursiveCharacterTextSplitter` (chunk_size=1000, overlap=200)
4. Embedding generation via Azure OpenAI embeddings endpoint
5. FAISS vector store creation/update per user
6. File metadata stored in database with hash-based deduplication

### Model Selection Logic
Dynamic model availability in `get_available_models()` - only configured models appear in UI. Each model has different client initialization patterns (standard Azure OpenAI vs azure-ai-inference).

### Database Operations
Uses SQLAlchemy 2.0+ patterns - avoid deprecated `.query.get()`, use `db.session.get()` instead.

## Azure Deployment

### Container Deployment
- **Dockerfile**: Uses Apache + mod_wsgi for production (not development Flask server)
- **PowerShell scripts**: `deploy-to-azure.ps1` and `luise_deploy-to-azure.ps1` for ACR + Web App deployment
- **Environment variables**: Extensive Azure OpenAI configuration required (see deploy script templates)

### Production Considerations
- File storage uses absolute paths with forward slashes for cross-platform compatibility
- Production detection via `WEBSITE_SITE_NAME` environment variable
- 64MB file upload limit configured in Flask

## Frontend Architecture

### JavaScript Structure (`static/js/app.js`)
- **No framework**: Vanilla JavaScript with event-driven architecture
- **Real-time updates**: Server-sent events for streaming chat responses
- **File management**: Upload queue system with progress tracking
- **Theme switching**: Dark/light mode with localStorage persistence

### API Endpoints Pattern
All AJAX endpoints use `/api/` prefix:
- `/api/chat` - POST for new messages
- `/api/files` - GET/DELETE for file management  
- `/api/models` - GET for available AI models
- `/chat-stream` - POST for streaming responses

## Testing & Debugging

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables in .env file
# Run with Flask development server
flask run
```

### Docker Local Testing
```bash
# Use docker-compose in docker_local/ directory
cd docker_local && docker-compose up
```

### Production Logging
Custom logger automatically adjusts verbosity based on `FLASK_ENV`. Use logger module methods for consistent formatting across development and Azure App Service.

## Documentation Export Convention

Assistant responses can trigger automatic Word (.docx) generation when they include a specially marked block:

```
[WORD_DOC]
Contenido de la documentación (puede incluir títulos, párrafos y líneas en blanco)
[/WORD_DOC]
```

Implementation details:
- Detection and export logic lives in `doc_export.py` (functions: `extraer_bloque_word`, `guardar_respuesta_en_word`, `procesar_respuesta`).
- The `/api/chat` endpoint calls `procesar_respuesta` after generating `assistant_message`.
- Generated files are stored under `data/word_docs/` (override with env var `WORD_DOC_OUTPUT_DIR`).
- JSON response from `/api/chat` now includes:
	```json
	{
		"word_doc": {
			"generated": true|false,
			"file_path": "ruta/absoluta/al/archivo.docx" | null,
			"error": null | "mensaje"
		}
	}
	```
- File name pattern: `documentacion_YYYYMMDD_HHMMSS.docx`.
- Each document structure: heading, timestamp, separator line, then paragraphs preserving blank lines.
 - Markdown support: extended parsing (headings, nested lists, block quotes, tables, links rendered as "texto (url)", bold, italic, inline & fenced code). Tablas usan estilo básico; listas ordenadas simplificadas.

Agent guidance:
- To request an export: instruct the model (prompt engineering) to wrap the desired documentation inside the markers.
- Do NOT nest markers or include unclosed tags—only the first well-formed block is processed.
- If enhancing: keep regex in `doc_export.py` aligned with marker specification.