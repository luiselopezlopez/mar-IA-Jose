document.addEventListener('DOMContentLoaded', function() {
    const chatMessages = document.getElementById('chat-messages');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const fileUpload = document.getElementById('file-upload');
    const uploadStatus = document.getElementById('upload-status');
    const newChatBtn = document.getElementById('new-chat-btn');
    const chatList = document.querySelector('.chat-list');
    const modelSelect = document.getElementById('model-select');
    const cameraBtn = document.getElementById('camera-btn');

    // Elementos del panel de archivos
    const filesPanel = document.getElementById('files-panel');
    const filesList = document.getElementById('files-list');
    const filesPanelClose = document.getElementById('files-panel-close');

    // Elementos del panel de cola de procesamiento
    const queuePanel = document.getElementById('queue-panel');
    const queueList = document.getElementById('queue-list');
    const queuePanelClose = document.getElementById('queue-panel-close');

    let currentChatId = null;
    let currentModelId = null;
    let chatInputImagesContainer = null;
    let attachedImages = [];

    // Cola de procesamiento de archivos
    let uploadQueue = [];
    let isProcessing = false;

    // Inicializar la funcionalidad de la cámara
    const openCamera = setupCamera();

    const themeToggle = document.getElementById('theme-toggle');

    // Verificar si hay una preferencia guardada
    const darkMode = localStorage.getItem('darkMode') === 'true';

    // Aplicar tema inicial
    if (darkMode) {
        document.body.classList.add('dark-mode');
        themeToggle.textContent = '☀️';
    }

    // Manejar cambio de tema
    themeToggle.addEventListener('click', function() {
        document.body.classList.toggle('dark-mode');
        const isDarkMode = document.body.classList.contains('dark-mode');
        localStorage.setItem('darkMode', isDarkMode);
        themeToggle.textContent = isDarkMode ? '☀️' : '🌙';
    });
    
    // Inicialización principal de la aplicación
    function initApp() {
        // Cargar la lista de chats
        loadChatList();
        
        // Cargar la lista de modelos disponibles
        loadAvailableModels();
          // Cargar la lista de archivos
        loadFiles();
        
        // Buscar y cargar el último chat activo (añadido por el servidor en la sesión)
        fetch('/api/chats')
            .then(response => response.json())
            .then(chats => {                if (chats && chats.length > 0) {
                    // Verificamos si ya hay una sesión activa con chat_id
                    const activeChatItem = document.querySelector('.chat-item.active');
                    if (activeChatItem) {
                        // Si ya hay un chat activo, lo cargamos
                        loadChat(activeChatItem.dataset.id);
                    } else {
                        // Si no hay chat activo, cargamos el primero de la lista (el más reciente)
                        loadChat(chats[0].id);
                    }
                } else {
                    // No hay chats, mostramos mensaje de bienvenida inicial
                    clearChatMessages();
                    showWelcomeMessage();
                }
            })
            .catch(error => console.error('Error obteniendo la lista de chats:', error));
    }

    // Función para mostrar el mensaje de bienvenida en el chat
    function showWelcomeMessage() {
        // Añadir mensaje de bienvenida
        addMessageToChat('assistant', 'Hola, soy Mar-IA-Jose. Un asistente de IA preparado para ayudarte en cuaquier tarea');
    }

    // Función para crear un nuevo chat
    function createNewChat() {
        fetch('/api/new_chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({}) // Add empty JSON body
        })
        .then(response => response.json())        .then(data => {
            currentChatId = data.chat_id;
            clearChatMessages();
            // Mostrar mensaje de bienvenida después de crear un nuevo chat
            showWelcomeMessage();
            loadChatList();
        })
        .catch(error => console.error('Error creating new chat:', error));
    }

    // Función para cargar la lista de chats
    function loadChatList() {
        fetch('/api/chats')
        .then(response => response.json())
        .then(chats => {
            chatList.innerHTML = '';
            chats.forEach(chat => {
                const chatItem = document.createElement('div');
                chatItem.className = 'chat-item';
                if (chat.id === currentChatId) {
                    chatItem.classList.add('active');
                }
                chatItem.dataset.id = chat.id;

                // Contenedor para el contenido del chat
                const chatContent = document.createElement('div');
                chatContent.className = 'chat-content';

                const preview = document.createElement('div');
                preview.className = 'chat-preview';
                preview.textContent = chat.preview;

                const date = document.createElement('div');
                date.className = 'chat-date';
                date.textContent = formatDate(chat.timestamp);

                chatContent.appendChild(preview);
                chatContent.appendChild(date);
                chatContent.addEventListener('click', () => loadChat(chat.id));

                // Contenedor para los botones de acción
                const chatActions = document.createElement('div');
                chatActions.className = 'chat-actions';

                // Botón para renombrar chat
                const renameBtn = document.createElement('button');
                renameBtn.className = 'chat-action-btn rename-chat';
                renameBtn.title = 'Renombrar chat';
                renameBtn.textContent = '✏️';
                renameBtn.addEventListener('click', (e) => {
                    e.stopPropagation(); // Evitar que se active el chat al hacer clic en el botón
                    openRenameChatModal(chat.id, chat.preview);
                });

                // Botón para eliminar chat
                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'chat-action-btn delete-chat';
                deleteBtn.title = 'Eliminar chat';
                deleteBtn.textContent = '🗑️';
                deleteBtn.addEventListener('click', (e) => {
                    e.stopPropagation(); // Evitar que se active el chat al hacer clic en el botón
                    deleteChat(chat.id);
                });

                chatActions.appendChild(renameBtn);
                chatActions.appendChild(deleteBtn);

                chatItem.appendChild(chatContent);
                chatItem.appendChild(chatActions);

                chatList.appendChild(chatItem);
            });
        })
        .catch(error => console.error('Error loading chat list:', error));
    }

    // Función para formatear fechas
    function formatDate(dateString) {
        if (!dateString) return '';
        const date = new Date(dateString);
        return date.toLocaleString();
    }    // Función para cargar un chat específico
    function loadChat(chatId) {
        currentChatId = chatId;

        // Actualizar la clase activa en la lista de chats
        document.querySelectorAll('.chat-item').forEach(item => {
            item.classList.remove('active');
            if (item.dataset.id === chatId) {
                item.classList.add('active');
            }
        });

        fetch(`/api/chat/${chatId}`)
        .then(response => response.json())        .then(messages => {
            clearChatMessages();
            
            // Si no hay mensajes, mostrar el mensaje de bienvenida
            if (messages.length === 0) {
                showWelcomeMessage();
            } else {
                // Mostrar los mensajes existentes
                messages.forEach(msg => {
                    addMessageToChat(msg.role, msg.content);
                });
            }
            
            // Asegurarse de que MathJax renderice toda la página después de cargar el chat
            if (window.MathJax) {
                window.MathJax.typesetPromise().catch((err) => {
                    console.error('Error al renderizar LaTeX después de cargar el chat:', err);
                });
            }
            
            scrollToBottom();
        })
        .catch(error => console.error('Error loading chat:', error));
    }

    // Función para limpiar los mensajes del chat
    function clearChatMessages() {
        chatMessages.innerHTML = '';
    }    // Función para añadir un mensaje al chat
    function addMessageToChat(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}-message`;

        // Procesar el contenido para formatear código, enlaces y fórmulas LaTeX
        const formattedContent = formatContent(content);

        messageDiv.innerHTML = formattedContent;
        chatMessages.appendChild(messageDiv);
        
        // Actualizar la renderización de MathJax
        if (window.MathJax) {
            window.MathJax.typesetPromise([messageDiv]).catch((err) => {
                console.error('Error al renderizar LaTeX:', err);
            });
        }
        
        scrollToBottom();
    }// Función para formatear el contenido (código, enlaces, LaTeX, etc.)
    function formatContent(content) {
        // Crear un elemento div para contener el HTML generado
        const div = document.createElement('div');

        // Preservar fórmulas LaTeX para que no sean procesadas por otras reglas
        let latexFormulas = [];
        let latexInlineFormulas = [];

        // Preservar fórmulas LaTeX de bloque \[ ... \]
        content = content.replace(/\\\[([\s\S]*?)\\\]/g, function(match, formula) {
            const id = latexFormulas.length;
            latexFormulas.push(formula);
            return `__LATEX_FORMULA_${id}__`;
        });

        // Preservar fórmulas LaTeX inline \( ... \)
        content = content.replace(/\\\(([\s\S]*?)\\\)/g, function(match, formula) {
            const id = latexInlineFormulas.length;
            latexInlineFormulas.push(formula);
            return `__LATEX_INLINE_${id}__`;
        });

        // Convertir Markdown a HTML
        // Primero manejamos los bloques de código
        content = content.replace(/```([\s\S]*?)```/g, function(match, code) {
            return '<pre><code>' + code.replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</code></pre>';
        });

        // Luego manejamos el código en línea
        content = content.replace(/`([^`]+)`/g, function(match, code) {
            return '<code>' + code.replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</code>';
        });

        // Manejar encabezados
        content = content.replace(/^### (.+)$/gm, '<h3>$1</h3>');
        content = content.replace(/^## (.+)$/gm, '<h2>$1</h2>');
        content = content.replace(/^# (.+)$/gm, '<h1>$1</h1>');

        // Manejar listas
        content = content.replace(/^\* (.+)$/gm, '<ul><li>$1</li></ul>');
        content = content.replace(/^\d+\. (.+)$/gm, '<ol><li>$1</li></ol>');

        // Manejar énfasis
        content = content.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        content = content.replace(/\*([^*]+)\*/g, '<em>$1</em>');

        // Manejar citas
        content = content.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>');

        // Convertir URLs en enlaces clickeables
        content = content.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank">$1</a>');

        // Convertir saltos de línea en <br>
        content = content.replace(/\n/g, '<br>');

        // Corregir listas anidadas
        content = content.replace(/<\/ul><br><ul>/g, '');
        content = content.replace(/<\/ol><br><ol>/g, '');

        // Restaurar fórmulas LaTeX de bloque
        latexFormulas.forEach((formula, id) => {
            content = content.replace(`__LATEX_FORMULA_${id}__`, `\\[${formula}\\]`);
        });

        // Restaurar fórmulas LaTeX inline
        latexInlineFormulas.forEach((formula, id) => {
            content = content.replace(`__LATEX_INLINE_${id}__`, `\\(${formula}\\)`);
        });

        return content;
    }

    // Función para mostrar indicador de escritura
    function showTypingIndicator() {
        const indicator = document.createElement('div');
        indicator.className = 'typing-indicator';
        indicator.innerHTML = '<span></span><span></span><span></span>';
        indicator.id = 'typing-indicator';
        chatMessages.appendChild(indicator);
        scrollToBottom();
    }

    // Función para ocultar indicador de escritura
    function hideTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) {
            indicator.remove();
        }
    }

    // Función para desplazarse al final del chat
    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Función para enviar un mensaje
    function sendMessage() {
        const message = chatInput.value.trim();
        if (!message) return;

        // Crear nuevo chat si no hay uno activo
        if (!currentChatId) {
            createNewChat();
            setTimeout(() => {
                sendMessageToServer(message);
            }, 500);
        } else {
            sendMessageToServer(message);
        }

        chatInput.value = '';
    }

    // Función para enviar mensaje al servidor
    function sendMessageToServer(message) {
        // Preparar el contenido del mensaje con imágenes si hay
        let messageContent = message;

        // Si hay imágenes adjuntas, añadirlas al mensaje
        if (attachedImages.length > 0) {
            // Crear un mensaje con formato HTML que incluya las imágenes
            let formattedMessage = message + '<br><br>';

            // Añadir cada imagen al mensaje
            attachedImages.forEach(imageData => {
                formattedMessage += `<img src="${imageData}" alt="Imagen adjunta"><br>`;
            });

            messageContent = formattedMessage;

            // Limpiar las imágenes adjuntas después de enviar
            attachedImages = [];
            if (chatInputImagesContainer) {
                chatInputImagesContainer.innerHTML = '';
                chatInputImagesContainer.style.display = 'none';
            }
        }

        // Añadir mensaje del usuario al chat
        addMessageToChat('user', messageContent);

        // Mostrar indicador de escritura
        showTypingIndicator();

        // Obtener el mensaje del sistema personalizado si existe
        const systemMessageInput = document.getElementById('system-message-input');
        const systemMessage = systemMessageInput ? systemMessageInput.value : null;

        fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: messageContent,
                chat_id: currentChatId,
                model_id: currentModelId,
                system_message: systemMessage
            })
        })
        .then(response => response.json())
        .then(data => {
            // Ocultar indicador de escritura
            hideTypingIndicator();

            // Añadir respuesta del asistente
            addMessageToChat('assistant', data.response);

            // Actualizar ID del chat si es necesario
            if (data.chat_id && (!currentChatId || currentChatId !== data.chat_id)) {
                currentChatId = data.chat_id;
                loadChatList();
            }
        })
        .catch(error => {
            console.error('Error sending message:', error);
            hideTypingIndicator();
            addMessageToChat('assistant', 'Lo siento, ha ocurrido un error al procesar tu mensaje.');
        });
    }

    // Función para subir archivos
    function uploadFile(file) {
        // Si es un PDF, mostrar el modal de opciones
        const fileExtension = file.name.split('.').pop().toLowerCase();

        if (fileExtension === 'pdf') {
            showPdfOptionsModal([file]);
            return;
        }

        // Para otros tipos de archivo, añadir a la cola y procesar
        addToUploadQueue(file, true);
    }

    // Función para mostrar el modal de opciones de PDF
    function showPdfOptionsModal(files) {
        const modal = document.getElementById('pdf-options-modal');
        modal.classList.add('open');

        // Actualizar el texto del modal para indicar múltiples archivos si es necesario
        const modalTitle = modal.querySelector('.modal-header h3');
        const modalDescription = modal.querySelector('.modal-body p');

        if (files.length > 1) {
            modalTitle.textContent = 'Opciones de Procesamiento de PDFs';
            modalDescription.textContent = `Selecciona cómo quieres procesar estos ${files.length} archivos PDF:`;
        } else {
            modalTitle.textContent = 'Opciones de Procesamiento de PDF';
            modalDescription.textContent = 'Selecciona cómo quieres procesar este archivo PDF:';
        }

        // Configurar el botón de procesar
        const processBtn = document.getElementById('process-pdf-btn');
        const closeButtons = modal.querySelectorAll('.modal-close');

        // Eliminar event listeners anteriores
        const newProcessBtn = processBtn.cloneNode(true);
        processBtn.parentNode.replaceChild(newProcessBtn, processBtn);

        // Añadir nuevo event listener
        newProcessBtn.addEventListener('click', function() {
            // Obtener la opción seleccionada
            const processWithOcr = document.getElementById('process-with-ocr').checked;
            modal.classList.remove('open');

            // Procesar todos los archivos PDF con la misma opción
            files.forEach(file => {
                addToUploadQueue(file, processWithOcr);
            });
        });

        // Configurar botones de cierre
        closeButtons.forEach(button => {
            button.addEventListener('click', function() {
                modal.classList.remove('open');
            });
        });
    }

    // Función para añadir un archivo a la cola de procesamiento
    function addToUploadQueue(file, processImages) {
        // Crear un elemento de cola
        const queueItem = {
            id: Date.now() + Math.random().toString(36).substr(2, 9),
            file: file,
            processImages: processImages,
            status: 'pending',
            logs: []
        };

        // Añadir a la cola
        uploadQueue.push(queueItem);

        // Añadir log inicial
        addProcessingLog(queueItem, `Archivo "${file.name}" añadido a la cola de procesamiento.`);

        // Actualizar la visualización de la cola
        updateQueueDisplay();

        // Mostrar el panel de cola si no está visible
        if (!queuePanel.classList.contains('open')) {
            queuePanel.classList.add('open');
            updateQueueToggleButtonText();
        }

        // Iniciar procesamiento si no hay nada en proceso
        if (!isProcessing) {
            processNextInQueue();
        }
    }

    // Función para procesar el siguiente archivo en la cola
    function processNextInQueue() {
        // Si no hay nada en la cola o ya se está procesando, salir
        if (uploadQueue.length === 0 || isProcessing) {
            return;
        }

        // Marcar como procesando
        isProcessing = true;

        // Obtener el primer elemento pendiente
        const queueItem = uploadQueue.find(item => item.status === 'pending');

        // Si no hay elementos pendientes, salir
        if (!queueItem) {
            isProcessing = false;
            return;
        }

        // Actualizar estado
        queueItem.status = 'processing';
        addProcessingLog(queueItem, `Iniciando procesamiento del archivo "${queueItem.file.name}"...`);
        updateQueueDisplay();

        // Actualizar el estado visible
        uploadStatus.textContent = `Procesando archivo ${queueItem.file.name}...`;

        // Procesar el archivo
        processAndUploadFile(queueItem);
    }

    // Función para procesar y subir el archivo
    function processAndUploadFile(queueItem) {
        const file = queueItem.file;
        const processImages = queueItem.processImages;

        const formData = new FormData();
        formData.append('file', file);
        formData.append('process_images', processImages);

        addProcessingLog(queueItem, `Subiendo archivo "${file.name}"...`);
        updateQueueDisplay();

        fetch('/api/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Actualizar estado
                queueItem.status = 'completed';
                addProcessingLog(queueItem, `Archivo "${file.name}" subido correctamente.`);

                if (!data.is_image) {
                    addProcessingLog(queueItem, `${data.chunks} fragmentos indexados para consulta.`);
                    // Añadir mensaje informativo al chat
                    addMessageToChat('assistant', `Archivo "${data.filename}" procesado correctamente. ${data.chunks} fragmentos indexados para consulta.`);
                }

                uploadStatus.textContent = data.message || `Archivo ${file.name} procesado correctamente`;
            } else {
                // Marcar como error
                queueItem.status = 'error';
                addProcessingLog(queueItem, `Error al procesar el archivo: ${data.error || 'Error desconocido'}`);
                uploadStatus.textContent = `Error al subir ${file.name}: ${data.error}`;
            }

            // Actualizar la visualización
            updateQueueDisplay();

            // Actualizar la lista de archivos
            loadFiles();

            // Marcar como no procesando
            isProcessing = false;

            // Procesar el siguiente en la cola
            processNextInQueue();
        })
        .catch(error => {
            console.error(`Error uploading file ${file.name}:`, error);

            // Marcar como error
            queueItem.status = 'error';
            addProcessingLog(queueItem, `Error al procesar el archivo: ${error.message || 'Error de conexión'}`);
            uploadStatus.textContent = `Error al subir el archivo ${file.name}.`;

            // Actualizar la visualización
            updateQueueDisplay();

            // Marcar como no procesando
            isProcessing = false;

            // Procesar el siguiente en la cola
            processNextInQueue();
        });
    }

    // Función para cargar la lista de archivos
    function loadFiles() {
        fetch('/api/files')
        .then(response => response.json())
        .then(data => {
            filesList.innerHTML = '';
            const files = data.files;

            if (files.length === 0) {
                filesList.innerHTML = '<div class="no-files">No hay archivos subidos</div>';
                return;
            }

            files.forEach(file => {
                const fileItem = document.createElement('div');
                fileItem.className = 'file-item';

                const fileName = document.createElement('div');
                fileName.className = 'file-name';
                fileName.textContent = file.name;
                fileName.title = file.name;

                const removeBtn = document.createElement('button');
                removeBtn.className = 'file-remove';
                removeBtn.innerHTML = '&times;';
                removeBtn.title = 'Eliminar archivo';
                removeBtn.addEventListener('click', () => removeFile(file.id, file.name));

                fileItem.appendChild(fileName);
                fileItem.appendChild(removeBtn);
                filesList.appendChild(fileItem);
            });
        })
        .catch(error => console.error('Error loading files:', error));
    }

    // Función para eliminar un archivo
    function removeFile(fileId, fileName) {
        if (confirm(`¿Estás seguro de que deseas eliminar el archivo "${fileName}"?`)) {
            fetch(`/api/files/${fileId}`, {
                method: 'DELETE'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    loadFiles();
                    addMessageToChat('assistant', `Archivo "${fileName}" eliminado correctamente.`);
                } else {
                    console.error('Error removing file:', data.error);
                }
            })
            .catch(error => console.error('Error removing file:', error));
        }
    }

    // Función para manejar imágenes adjuntas
    function setupImageAttachments() {
        // Crear contenedor para imágenes adjuntas si no existe
        if (!chatInputImagesContainer) {
            chatInputImagesContainer = document.createElement('div');
            chatInputImagesContainer.className = 'chat-input-images';
            chatInputImagesContainer.style.display = 'none';
            chatInput.parentNode.insertBefore(chatInputImagesContainer, chatInput);
        }
    }

    // Función para adjuntar una imagen
    function attachImage(file) {
        if (!file.type.startsWith('image/')) {
            uploadStatus.textContent = 'Solo se permiten archivos de imagen.';
            return;
        }

        setupImageAttachments();

        const reader = new FileReader();
        reader.onload = function(e) {
            const imageData = e.target.result;
            attachedImages.push(imageData);

            // Mostrar vista previa
            const imagePreview = document.createElement('div');
            imagePreview.className = 'image-preview-container';

            const img = document.createElement('img');
            img.src = imageData;
            img.className = 'image-preview';

            const removeBtn = document.createElement('button');
            removeBtn.innerHTML = '&times;';
            removeBtn.className = 'image-remove-btn';
            removeBtn.onclick = function() {
                const index = attachedImages.indexOf(imageData);
                if (index > -1) {
                    attachedImages.splice(index, 1);
                }
                imagePreview.remove();

                if (attachedImages.length === 0) {
                    chatInputImagesContainer.style.display = 'none';
                }
            };

            imagePreview.appendChild(img);
            imagePreview.appendChild(removeBtn);
            chatInputImagesContainer.appendChild(imagePreview);
            chatInputImagesContainer.style.display = 'flex';
        };

        reader.readAsDataURL(file);
    }

    // Función para capturar imagen de la cámara
    function setupCamera() {
        // Crear modal para la cámara
        const cameraModal = document.createElement('div');
        cameraModal.className = 'camera-modal';
        cameraModal.innerHTML = `
            <div class="camera-container">
                <video id="camera-video" autoplay></video>
            </div>
            <div class="camera-controls">
                <button class="camera-btn capture-btn">Capturar</button>
                <button class="camera-btn cancel-btn">Cancelar</button>
            </div>
        `;
        document.body.appendChild(cameraModal);

        const video = document.getElementById('camera-video');
        const captureBtn = cameraModal.querySelector('.capture-btn');
        const cancelBtn = cameraModal.querySelector('.cancel-btn');

        let stream = null;

        // Función para abrir la cámara
        function openCamera() {
            cameraModal.classList.add('open');

            navigator.mediaDevices.getUserMedia({ video: true })
                .then(function(mediaStream) {
                    stream = mediaStream;
                    video.srcObject = mediaStream;
                })
                .catch(function(error) {
                    console.error('Error accessing camera:', error);
                    alert('No se pudo acceder a la cámara: ' + error.message);
                    cameraModal.classList.remove('open');
                });
        }

        // Función para capturar imagen
        function captureImage() {
            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

            const imageData = canvas.toDataURL('image/jpeg');
            attachedImages.push(imageData);

            // Mostrar vista previa
            setupImageAttachments();

            const imagePreview = document.createElement('div');
            imagePreview.className = 'image-preview-container';

            const img = document.createElement('img');
            img.src = imageData;
            img.className = 'image-preview';

            const removeBtn = document.createElement('button');
            removeBtn.innerHTML = '&times;';
            removeBtn.className = 'image-remove-btn';
            removeBtn.onclick = function() {
                const index = attachedImages.indexOf(imageData);
                if (index > -1) {
                    attachedImages.splice(index, 1);
                }
                imagePreview.remove();

                if (attachedImages.length === 0) {
                    chatInputImagesContainer.style.display = 'none';
                }
            };

            imagePreview.appendChild(img);
            imagePreview.appendChild(removeBtn);
            chatInputImagesContainer.appendChild(imagePreview);
            chatInputImagesContainer.style.display = 'flex';

            // Cerrar la cámara
            closeCamera();
        }

        // Función para cerrar la cámara
        function closeCamera() {
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
                stream = null;
            }
            video.srcObject = null;
            cameraModal.classList.remove('open');
        }

        // Event listeners para la cámara
        captureBtn.addEventListener('click', captureImage);
        cancelBtn.addEventListener('click', closeCamera);

        return openCamera;
    }

    // Función para añadir logs de procesamiento
    function addProcessingLog(queueItem, message) {
        if (!queueItem) return;

        const timestamp = new Date().toLocaleTimeString();
        queueItem.logs.push(`[${timestamp}] ${message}`);
    }

    // Función para actualizar la visualización de la cola
    function updateQueueDisplay() {
        // Usar el contenedor de cola en el panel de cola en lugar del panel de archivos
        let queueContainer = queueList;

        // Limpiar el contenedor
        queueContainer.innerHTML = '';

        // Título de la sección ya no es necesario porque el panel ya tiene su propio título

        // Añadir cada elemento de la cola
        uploadQueue.forEach((item, index) => {
            const queueItemElement = document.createElement('div');
            queueItemElement.className = `queue-item queue-item-${item.status}`;

            // Información del archivo
            const fileInfo = document.createElement('div');
            fileInfo.className = 'queue-item-info';

            // Nombre y estado
            const fileName = document.createElement('div');
            fileName.className = 'queue-item-name';
            fileName.textContent = item.file.name;

            const fileStatus = document.createElement('div');
            fileStatus.className = 'queue-item-status';

            switch (item.status) {
                case 'pending':
                    fileStatus.textContent = 'Pendiente';
                    break;
                case 'processing':
                    fileStatus.textContent = 'Procesando...';
                    break;
                case 'completed':
                    fileStatus.textContent = 'Completado';
                    break;
                case 'error':
                    fileStatus.textContent = 'Error';
                    break;
            }

            fileInfo.appendChild(fileName);
            fileInfo.appendChild(fileStatus);

            // Botón para mostrar/ocultar logs
            const toggleLogsBtn = document.createElement('button');
            toggleLogsBtn.className = 'toggle-logs-btn';
            toggleLogsBtn.textContent = 'Ver logs';
            toggleLogsBtn.addEventListener('click', function() {
                const logsContainer = queueItemElement.querySelector('.queue-item-logs');
                if (logsContainer.style.display === 'none') {
                    logsContainer.style.display = 'block';
                    toggleLogsBtn.textContent = 'Ocultar logs';
                } else {
                    logsContainer.style.display = 'none';
                    toggleLogsBtn.textContent = 'Ver logs';
                }
            });

            // Contenedor de logs
            const logsContainer = document.createElement('div');
            logsContainer.className = 'queue-item-logs';
            logsContainer.style.display = 'none';

            // Añadir cada log
            item.logs.forEach(log => {
                const logElement = document.createElement('div');
                logElement.className = 'log-entry';
                logElement.textContent = log;
                logsContainer.appendChild(logElement);
            });

            queueItemElement.appendChild(fileInfo);
            queueItemElement.appendChild(toggleLogsBtn);
            queueItemElement.appendChild(logsContainer);

            queueContainer.appendChild(queueItemElement);
        });

        // Si hay elementos en la cola, mostrar el panel de cola
        if (uploadQueue.length > 0 && !queuePanel.classList.contains('open')) {
            queuePanel.classList.add('open');
            updateQueueToggleButtonText();
        }
    }

    // Event listeners
    sendBtn.addEventListener('click', sendMessage);
    chatInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Manejar pegado de imágenes
    chatInput.addEventListener('paste', function(e) {
        const items = (e.clipboardData || e.originalEvent.clipboardData).items;
        for (let i = 0; i < items.length; i++) {
            if (items[i].type.indexOf('image') !== -1) {
                const file = items[i].getAsFile();
                attachImage(file);
                e.preventDefault();
                break;
            }
        }
    });

    // Manejar arrastre de imágenes
    chatInput.addEventListener('dragover', function(e) {
        e.preventDefault();
        e.stopPropagation();
        chatInput.classList.add('drag-over');
    });

    chatInput.addEventListener('dragleave', function(e) {
        e.preventDefault();
        e.stopPropagation();
        chatInput.classList.remove('drag-over');
    });

    chatInput.addEventListener('drop', function(e) {
        e.preventDefault();
        e.stopPropagation();
        chatInput.classList.remove('drag-over');

        const files = e.dataTransfer.files;
        for (let i = 0; i < files.length; i++) {
            if (files[i].type.startsWith('image/')) {
                attachImage(files[i]);
            }
        }
    });

    fileUpload.addEventListener('change', function(e) {
        if (e.target.files.length > 0) {
            const files = Array.from(e.target.files);

            // Separar archivos por tipo
            const imageFiles = files.filter(file => file.type.startsWith('image/'));
            const pdfFiles = files.filter(file => file.name.split('.').pop().toLowerCase() === 'pdf');
            const otherFiles = files.filter(file => !file.type.startsWith('image/') && file.name.split('.').pop().toLowerCase() !== 'pdf');

            // Procesar imágenes
            imageFiles.forEach(file => attachImage(file));

            // Procesar otros archivos directamente
            otherFiles.forEach(file => addToUploadQueue(file, true));

            // Si hay PDFs, mostrar el modal de opciones solo una vez
            if (pdfFiles.length > 0) {
                showPdfOptionsModal(pdfFiles);
            }

            e.target.value = null; // Limpiar el input para permitir subir el mismo archivo nuevamente
        }
    });

    newChatBtn.addEventListener('click', createNewChat);

    // Event listener para el botón de cámara
    cameraBtn.addEventListener('click', function() {
        openCamera();
    });

    // Event listeners para el panel de archivos
    filesPanelClose.addEventListener('click', function() {
        filesPanel.classList.remove('open');
        // Actualizar el texto del botón toggle cuando se cierra el panel
        const filesToggleBtn = document.getElementById('files-toggle-toolbar');
        if (filesToggleBtn) {
            filesToggleBtn.textContent = '📁 Ver archivos';
        }
    });

    // Event listener para el botón de archivos
    const filesToggleBtn = document.getElementById('files-toggle-toolbar');
    filesToggleBtn.addEventListener('click', function() {
        filesPanel.classList.toggle('open');
        // Actualizar el texto del botón según el estado del panel
        if (filesPanel.classList.contains('open')) {
            filesToggleBtn.textContent = '📁 Ocultar archivos';
        } else {
            filesToggleBtn.textContent = '📁 Ver archivos';
        }
        loadFiles();
    });

    // Event listeners para el panel de cola de procesamiento
    queuePanelClose.addEventListener('click', function() {
        queuePanel.classList.remove('open');
        updateQueueToggleButtonText();
    });

    // Event listener para el botón de cola de procesamiento
    const queueToggleBtn = document.getElementById('queue-toggle-toolbar');
    queueToggleBtn.addEventListener('click', function() {
        queuePanel.classList.toggle('open');
        // Actualizar el texto del botón según el estado del panel
        if (queuePanel.classList.contains('open')) {
            queueToggleBtn.textContent = '🔄 Ocultar cola';
        } else {
            queueToggleBtn.textContent = '🔄 Ver cola';
        }
        // Actualizar la visualización de la cola
        updateQueueDisplay();
    });

    // Función para actualizar el texto del botón de cola según el estado del panel
    function updateQueueToggleButtonText() {
        const queueToggleBtn = document.getElementById('queue-toggle-toolbar');
        if (queueToggleBtn) {
            if (queuePanel.classList.contains('open')) {
                queueToggleBtn.textContent = '🔄 Ocultar cola';
            } else {
                queueToggleBtn.textContent = '🔄 Ver cola';
            }
        }
    }

    // Función para cargar los modelos disponibles
    function loadAvailableModels() {
        fetch('/api/models')
        .then(response => response.json())
        .then(data => {
            modelSelect.innerHTML = '';
            data.models.forEach(model => {
                const option = document.createElement('option');
                option.value = model.id;
                option.textContent = model.name;
                modelSelect.appendChild(option);
            });

            // Establecer el modelo seleccionado desde localStorage o usar el primero
            const savedModelId = localStorage.getItem('selectedModelId');
            if (savedModelId && modelSelect.querySelector(`option[value="${savedModelId}"]`)) {
                modelSelect.value = savedModelId;
                currentModelId = savedModelId;
            } else if (data.models.length > 0) {
                currentModelId = data.models[0].id;
            }
        })
        .catch(error => console.error('Error loading models:', error));
    }

    // Event listener para el cambio de modelo
    modelSelect.addEventListener('change', function() {
        currentModelId = this.value;
        localStorage.setItem('selectedModelId', currentModelId);
    });

    // Función para eliminar un chat
    function deleteChat(chatId) {
        if (confirm('¿Estás seguro de que deseas eliminar esta conversación?')) {
            fetch(`/api/chat/${chatId}`, {
                method: 'DELETE'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Si el chat eliminado es el actual, limpiar la vista
                    if (chatId === currentChatId) {
                        currentChatId = null;
                        clearChatMessages();
                    }
                    loadChatList();
                } else {
                    console.error('Error deleting chat:', data.error);
                }
            })
            .catch(error => console.error('Error deleting chat:', error));
        }
    }

    // Función para abrir el modal de renombrar chat
    function openRenameChatModal(chatId, currentTitle) {
        const modal = document.getElementById('rename-chat-modal');
        const titleInput = document.getElementById('chat-title-input');
        const saveBtn = document.getElementById('save-chat-title-btn');

        // Establecer el título actual en el input
        titleInput.value = currentTitle;

        // Mostrar el modal
        modal.classList.add('open');
        titleInput.focus();

        // Configurar el botón de guardar
        saveBtn.onclick = () => {
            const newTitle = titleInput.value.trim();
            if (newTitle) {
                updateChatTitle(chatId, newTitle);
                modal.classList.remove('open');
            }
        };

        // Configurar cierre del modal
        const closeButtons = modal.querySelectorAll('.modal-close, .cancel-btn');
        closeButtons.forEach(btn => {
            btn.onclick = () => modal.classList.remove('open');
        });
    }

    // Función para actualizar el título de un chat
    function updateChatTitle(chatId, newTitle) {
        fetch(`/api/chat/${chatId}/title`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                title: newTitle
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                loadChatList();
            } else {
                console.error('Error updating chat title:', data.error);
            }
        })
        .catch(error => console.error('Error updating chat title:', error));
    }

    // Función para abrir el modal de mensaje del sistema
    function openSystemMessageModal() {
        if (!currentChatId) {
            alert('Por favor, selecciona o crea un chat primero.');
            return;
        }

        const modal = document.getElementById('system-message-modal');
        const messageInput = document.getElementById('system-message-input');
        const saveBtn = document.getElementById('save-system-message-btn');

        // Obtener el mensaje del sistema actual si existe
        fetch(`/api/chat/${currentChatId}`)
        .then(response => response.json())
        .then(data => {
            // Buscar el mensaje del sistema en los datos del chat
            const systemMessage = data.system_message || '';
            messageInput.value = systemMessage;

            // Mostrar el modal
            modal.classList.add('open');
            messageInput.focus();

            // Configurar el botón de guardar
            saveBtn.onclick = () => {
                updateSystemMessage(currentChatId, messageInput.value);
                modal.classList.remove('open');
            };

            // Configurar cierre del modal
            const closeButtons = modal.querySelectorAll('.modal-close, .cancel-btn');
            closeButtons.forEach(btn => {
                btn.onclick = () => modal.classList.remove('open');
            });
        })
        .catch(error => console.error('Error loading system message:', error));
    }

    // Función para actualizar el mensaje del sistema
    function updateSystemMessage(chatId, systemMessage) {
        fetch(`/api/chat/${chatId}/system_message`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                system_message: systemMessage
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Opcional: mostrar un mensaje de éxito
                addMessageToChat('assistant', 'Mensaje del sistema actualizado correctamente.');
            } else {
                console.error('Error updating system message:', data.error);
            }
        })
        .catch(error => console.error('Error updating system message:', error));
    }

    // Configurar el botón de mensaje del sistema
    const systemMessageBtn = document.getElementById('system-message-btn');
    systemMessageBtn.addEventListener('click', openSystemMessageModal);

    // El botón de ver archivos ya está configurado arriba
    // No necesitamos un segundo event listener para el mismo botón

    // Función para cargar la versión de la aplicación
    function loadAppVersion() {
        fetch('/api/version')
        .then(response => response.json())
        .then(data => {
            const versionElement = document.getElementById('app-version');
            if (versionElement) {
                versionElement.textContent = data.version;
            }
        })
        .catch(error => console.error('Error loading app version:', error));
    }
    
    // Cargar versión de la aplicación
    loadAppVersion();
    
    // Iniciar la aplicación (carga chats, modelos y archivos)
    initApp();
});