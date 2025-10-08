# Guía de Uso de Mar-IA-Jose

Bienvenido a Mar-IA-Jose, tu asistente de IA especializado en analizar documentación y ayudarte con tareas complejas. Esta guía está pensada para usuarios finales y resume cada funcionalidad disponible en la aplicación.

---

## 1. Primeros pasos

1. **Inicia sesión** con tus credenciales.
2. En el panel lateral encontrarás el botón **«Nueva Conversación»**. Cada conversación mantiene su propio contexto.
3. Usa la barra inferior para **enviar mensajes**, **subir archivos** o **acceder a herramientas adicionales**.

> Consejo: el mensaje de bienvenida resume la configuración actual del chat activo.

---

## 2. Gestión de conversaciones

- **Crear**: pulsa «Nueva Conversación». Se abrirá un chat limpio con el prompt por defecto.
- **Cambiar**: selecciona cualquier conversación del listado izquierdo. El contexto, archivos y prompt se cargan automáticamente.
- **Renombrar**: usa el icono ✏️ en cada conversación para darle un título descriptivo.
- **Eliminar**: con el icono 🗑️ eliminas la conversación. Si borras la última, Mar-IA-Jose crea automáticamente una nueva para que nunca te quedes sin chat activo.

---

## 3. Mensaje del sistema y prompts personalizados

El mensaje del sistema determina la personalidad y los límites de la IA:

- Pulsa **⚙️ Mensaje del Sistema** para abrir el editor.
- Puedes escribir uno nuevo o **aplicar tus prompts guardados**.
- Usa el botón **Guardar** para almacenar un prompt en tu catálogo personal.
- Cada usuario dispone de un prompt **«Default»** creado automáticamente. Este es el que se aplicará cuando abras una conversación nueva.

---

## 4. Gestión de archivos y base documental

1. **Subir archivos**: emplea el botón 📎 «Subir archivo». Se aceptan PDF, DOCX, TXT, CSV e imágenes (JPG/PNG/GIF).
2. **Cola de procesamiento**: el botón 🔄 muestra el estado de los archivos pendientes o recientemente procesados.
3. **Archivos adjuntos al chat**: el botón 📁 abre el panel con la lista de archivos asociados a la conversación actual.
4. **Eliminación**: dentro del panel puedes retirar documentos individuales. El sistema actualiza la conversación para mantener la coherencia.

Los documentos se indexan usando embeddings para que el asistente pueda citar y razonar sobre su contenido.

---

## 5. Modelos de IA disponibles

- El selector **«Modelo»** permite escoger la familia de modelos de Azure OpenAI disponible en tu suscripción. Actualmente solo esta disponible OpenAI GPT-5
- Tus preferencias se guardan en el navegador.
- Cambiar de modelo cancela automáticamente cualquier respuesta en curso para evitar inconsistencias.

---

## 6. Exportación a Word

Cuando el asistente genere un bloque de respuesta marcado con `[WORD_DOC] ... [/WORD_DOC]`, Mar-IA-Jose lo exporta automáticamente a un archivo `.docx` en la carpeta `data/word_docs/`. El enlace de descarga aparecerá en la respuesta JSON.

---

## 7. Privacidad y seguridad de los datos

- Todo el procesamiento se realiza en una **instancia privada de Azure** controlada por tu organización. No se envían conversaciones ni archivos a servicios públicos.
- Las conversaciones y los archivos subidos se guardan en el almacenamiento privado y las bases de datos SQL y VectorDB locales, todo protegido dentro de la red privada, protegidos con cifracio y restringidos mediante identidades gestionadas y reglas de acceso zero-trust.
- El tráfico entre los servicios internos (API, base de datos, almacenamiento y Azure OpenAI) está cifrado mediante TLS y se realiza en la infraestructura propia. No sale a internet ni se envia a ningún servicio de terceros nunca.
- Los administradores pueden purgar conversaciones y documentos siguiendo los procedimientos internos de cumplimiento y retención.

---

## 8. Limitaciones conocidas

- **Tamaño de archivos**: máximo 64 MB por subida.
- **Contenido sensible**: Azure OpenAI aplica filtros de moderación. Si la petición vulnera la política, recibirás un error `content_filter`.


---

## 9. Preguntas frecuentes (FAQ)

**¿Puedo usar la aplicación sin iniciar sesión?**  
No. El acceso está restringido para garantizar la privacidad de los datos y prompts.

**¿Cómo restablezco el prompt por defecto?**  
Abre el editor del mensaje del sistema y selecciona el prompt «Default» desde el desplegable de prompts guardados.

**¿Qué ocurre si cierro la pestaña a mitad de una respuesta?**  
La solicitud se cancela automáticamente gracias a un controlador `AbortController`, evitando que la cola de respuestas quede bloqueada.

**¿Se pueden compartir prompts entre usuarios?**  
No por ahora. Cada usuario gestiona su propio catálogo de prompts personalizados.


---

## 10. Soporte

Esta plataforma se ofrece 'as-is', si ningun tipo de soporte ni garantia.

No se garantiza la persistencia de los datos y en cualquier momento se podra realizar un purgado de los mismos si se considera necesario.

Para incidencias técnicas contacta con el administrador de la plataforma en el correo electronico luise92@gmail.com, a ver que podemos hacer.
