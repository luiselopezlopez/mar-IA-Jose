document.addEventListener('DOMContentLoaded', function() {
    const chatMessages = document.getElementById('chat-messages');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const fileUpload = document.getElementById('file-upload');
    const uploadStatus = document.getElementById('upload-status');
    const newChatBtn = document.getElementById('new-chat-btn');
    const chatList = document.querySelector('.chat-list');
    const modelSelect = document.getElementById('model-select');
    const ragTopKInput = document.getElementById('rag-top-k');
    const temperatureInput = document.getElementById('temperature-input');
    const messageHistoryLimitInput = document.getElementById('message-history-limit');
    const cameraBtn = document.getElementById('camera-btn');
    const downloadConversationBtn = document.getElementById('download-conversation-btn');
    const helpBtn = document.getElementById('help-btn');
    const DEFAULT_SYSTEM_PROMPT_TEXT = "Eres un asistente útil que responde a las preguntas del usuario de manera clara y concisa. Si no sabes la respuesta, di que no lo sabes. No inventes respuestas.";
    const savedPromptsSelect = document.getElementById('saved-prompts-select');
    const storeSystemPromptBtn = document.getElementById('store-system-prompt-btn');
    const systemPromptsFeedback = document.getElementById('system-prompts-feedback');
    const userMenuToggle = document.getElementById('user-menu-toggle');
    const userMenuDropdown = document.getElementById('user-menu-dropdown');
    const userMenuItems = document.querySelectorAll('.user-menu-item');
    const changePasswordTrigger = document.querySelector('[data-action="change-password"]');
    const changePasswordModal = document.getElementById('change-password-modal');
    const changePasswordForm = document.getElementById('change-password-form');
    const changePasswordFeedback = document.getElementById('change-password-feedback');
    const changePasswordSubmitBtn = document.getElementById('change-password-submit');
    const changePasswordInputs = {
        current: document.getElementById('current-password'),
        next: document.getElementById('new-password'),
        confirm: document.getElementById('confirm-new-password')
    };
    const manageUsersTrigger = document.querySelector('[data-action="manage-users"]');
    const manageUsersModal = document.getElementById('manage-users-modal');
    const manageUsersTableBody = document.getElementById('manage-users-table-body');
    const manageUsersFeedback = document.getElementById('manage-users-feedback');
    const manageUsersCloseButtons = manageUsersModal ? manageUsersModal.querySelectorAll('.modal-close, [data-role="close-manage-users"]') : [];
    const adminResetSection = document.getElementById('admin-reset-password-section');
    const adminResetForm = document.getElementById('admin-reset-password-form');
    const adminResetPasswordInput = document.getElementById('admin-reset-password');
    const adminResetPasswordConfirmInput = document.getElementById('admin-reset-password-confirm');
    const adminResetFeedback = document.getElementById('admin-reset-password-feedback');
    const adminResetTargetName = document.getElementById('admin-reset-target-name');
    const adminResetCancelBtn = document.getElementById('admin-reset-password-cancel');
    const currentUserIsAdmin = document.body && document.body.dataset ? document.body.dataset.isAdmin === 'true' : false;

    const DEFAULT_RAG_TOP_K = (() => {
        if (!ragTopKInput) {
            return 3;
        }
        const initial = ragTopKInput.defaultValue || ragTopKInput.getAttribute('value') || ragTopKInput.value;
        const parsed = parseInt(initial, 10);
        if (!Number.isFinite(parsed)) {
            return 3;
        }
        return Math.min(Math.max(parsed, 1), 20);
    })();

    const DEFAULT_TEMPERATURE = (() => {
        if (!temperatureInput) {
            return 1.0;
        }
        const initial = temperatureInput.defaultValue || temperatureInput.getAttribute('value') || temperatureInput.value;
        const parsed = parseFloat(initial);
        if (!Number.isFinite(parsed)) {
            return 1.0;
        }
        const clamped = Math.min(Math.max(parsed, 0), 2);
        return Math.round(clamped * 10) / 10;
    })();

    const DEFAULT_HISTORY_LIMIT = (() => {
        if (!messageHistoryLimitInput) {
            return 10;
        }
        const initial = messageHistoryLimitInput.defaultValue || messageHistoryLimitInput.getAttribute('value') || messageHistoryLimitInput.value;
        const parsed = parseInt(initial, 10);
        if (!Number.isFinite(parsed)) {
            return 10;
        }
        return Math.min(Math.max(parsed, 1), 50);
    })();

    function normalizeTopK(value) {
        const parsed = parseInt(value, 10);
        if (!Number.isFinite(parsed)) {
            return DEFAULT_RAG_TOP_K;
        }
        return Math.min(Math.max(parsed, 1), 20);
    }

    function normalizeTemperature(value) {
        const parsed = parseFloat(value);
        if (!Number.isFinite(parsed)) {
            return DEFAULT_TEMPERATURE;
        }
        const clamped = Math.min(Math.max(parsed, 0), 2);
        return Math.round(clamped * 10) / 10;
    }

    function normalizeHistoryLimit(value) {
        const parsed = parseInt(value, 10);
        if (!Number.isFinite(parsed)) {
            return DEFAULT_HISTORY_LIMIT;
        }
        return Math.min(Math.max(parsed, 1), 50);
    }

    if (changePasswordSubmitBtn && !changePasswordSubmitBtn.dataset.originalText) {
        changePasswordSubmitBtn.dataset.originalText = changePasswordSubmitBtn.textContent;
    }

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
    let activeChatRequestController = null;
    // Catálogo de prompts personales obtenido del backend.
    let savedPromptsCache = [];
    let adminUsersState = { users: [], totalAdmins: 0 };
    let adminResetTargetId = null;

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

    function openUserMenu() {
        if (!userMenuDropdown || !userMenuToggle) {
            return;
        }

        userMenuDropdown.classList.add('open');
        userMenuDropdown.setAttribute('aria-hidden', 'false');
        userMenuToggle.setAttribute('aria-expanded', 'true');

        const firstItem = userMenuDropdown.querySelector('.user-menu-item');
        if (firstItem) {
            setTimeout(() => firstItem.focus(), 0);
        }
    }

    function closeUserMenu() {
        if (!userMenuDropdown || !userMenuToggle) {
            return;
        }

        userMenuDropdown.classList.remove('open');
        userMenuDropdown.setAttribute('aria-hidden', 'true');
        userMenuToggle.setAttribute('aria-expanded', 'false');
    }

    function setChangePasswordFeedback(message, type = 'info') {
        if (!changePasswordFeedback) {
            return;
        }

        changePasswordFeedback.textContent = message || '';
        changePasswordFeedback.classList.remove('error', 'success');

        if (type === 'error') {
            changePasswordFeedback.classList.add('error');
        } else if (type === 'success') {
            changePasswordFeedback.classList.add('success');
        }
    }

    function openChangePasswordModal() {
        if (!changePasswordModal || !changePasswordForm) {
            return;
        }

        changePasswordForm.reset();
        setChangePasswordFeedback('');
        changePasswordModal.classList.add('open');
        changePasswordModal.setAttribute('aria-hidden', 'false');

        const currentInput = changePasswordInputs.current;
        if (currentInput) {
            setTimeout(() => currentInput.focus(), 50);
        }
    }

    function closeChangePasswordModal() {
        if (!changePasswordModal) {
            return;
        }

        changePasswordModal.classList.remove('open');
        changePasswordModal.setAttribute('aria-hidden', 'true');

        if (changePasswordSubmitBtn) {
            changePasswordSubmitBtn.disabled = false;
            const originalText = changePasswordSubmitBtn.dataset.originalText || 'Actualizar contraseña';
            changePasswordSubmitBtn.textContent = originalText;
        }
    }

    function setManageUsersFeedback(message, type = 'info') {
        if (!manageUsersFeedback) {
            return;
        }

        manageUsersFeedback.textContent = message || '';
        manageUsersFeedback.classList.remove('error', 'success');

        if (type === 'error') {
            manageUsersFeedback.classList.add('error');
        } else if (type === 'success') {
            manageUsersFeedback.classList.add('success');
        }
    }

    function setAdminResetPasswordFeedback(message, type = 'info') {
        if (!adminResetFeedback) {
            return;
        }

        adminResetFeedback.textContent = message || '';
        adminResetFeedback.classList.remove('error', 'success');

        if (type === 'error') {
            adminResetFeedback.classList.add('error');
        } else if (type === 'success') {
            adminResetFeedback.classList.add('success');
        }
    }

    function hideAdminResetPasswordSection() {
        if (!adminResetSection || !adminResetForm) {
            return;
        }

        adminResetSection.hidden = true;
        adminResetSection.classList.remove('active');
        adminResetTargetId = null;
        adminResetForm.reset();
        setAdminResetPasswordFeedback('');
    }

    function showAdminResetPasswordSection(user) {
        if (!adminResetSection || !adminResetForm) {
            return;
        }

        adminResetTargetId = user?.id ?? null;
        adminResetSection.hidden = false;
        adminResetSection.classList.add('active');
        adminResetForm.reset();
        setAdminResetPasswordFeedback('');

        if (adminResetTargetName) {
            adminResetTargetName.textContent = user?.username || '';
        }

        if (adminResetPasswordInput) {
            setTimeout(() => adminResetPasswordInput.focus(), 50);
        }
    }

    async function loadManageUsers() {
        if (!manageUsersTableBody) {
            return;
        }

        manageUsersTableBody.innerHTML = '';
        const loadingRow = document.createElement('tr');
        const loadingCell = document.createElement('td');
        loadingCell.colSpan = 5;
        loadingCell.className = 'manage-users-empty';
        loadingCell.textContent = 'Cargando información…';
        loadingRow.appendChild(loadingCell);
        manageUsersTableBody.appendChild(loadingRow);

        try {
            const response = await fetch('/api/admin/users');
            const data = await response.json().catch(() => ({}));

            if (!response.ok || !data.success) {
                const errorMessage = data.error || 'No se pudo obtener la lista de usuarios.';
                setManageUsersFeedback(errorMessage, 'error');
                loadingCell.textContent = 'No se pudo cargar la información.';
                return;
            }

            adminUsersState = {
                users: Array.isArray(data.users) ? data.users : [],
                totalAdmins: Number.isFinite(data.total_admins) ? data.total_admins : 0
            };
            setManageUsersFeedback('');
            renderManageUsers(adminUsersState.users, adminUsersState.totalAdmins);
        } catch (error) {
            console.error('Error loading admin users:', error);
            setManageUsersFeedback('Error de conexión al cargar la lista de usuarios.', 'error');
            loadingCell.textContent = 'No se pudo cargar la información.';
        }
    }

    function updateAdminToggleAvailability(totalAdmins) {
        if (!manageUsersTableBody) {
            return;
        }

        const effectiveTotal = Number.isFinite(Number(totalAdmins)) ? Number(totalAdmins) : 0;
        const checkboxes = manageUsersTableBody.querySelectorAll('.admin-role-checkbox');

        checkboxes.forEach(checkbox => {
            const isAdmin = checkbox.dataset.currentValue === 'true';
            const username = checkbox.dataset.username || 'este usuario';
            const shouldDisable = isAdmin && effectiveTotal <= 1;
            const actionVerb = isAdmin ? 'Revocar' : 'Conceder';
            const tooltip = `${actionVerb} permisos de administrador a ${username}`;

            checkbox.setAttribute('aria-label', tooltip);

            checkbox.disabled = shouldDisable;
            if (shouldDisable) {
                checkbox.title = 'Debe existir al menos un administrador en el sistema.';
            } else {
                checkbox.title = tooltip;
            }

            const toggleLabel = checkbox.closest('.admin-role-toggle');
            if (toggleLabel) {
                if (shouldDisable) {
                    toggleLabel.classList.add('disabled');
                } else {
                    toggleLabel.classList.remove('disabled');
                }
            }
        });
    }

    function renderManageUsers(users, totalAdmins) {
        if (!manageUsersTableBody) {
            return;
        }

        manageUsersTableBody.innerHTML = '';

        if (!users || users.length === 0) {
            const emptyRow = document.createElement('tr');
            const emptyCell = document.createElement('td');
            emptyCell.colSpan = 5;
            emptyCell.className = 'manage-users-empty';
            emptyCell.textContent = 'No hay usuarios registrados.';
            emptyRow.appendChild(emptyCell);
            manageUsersTableBody.appendChild(emptyRow);
            return;
        }

        users.forEach(user => {
            const row = document.createElement('tr');
            row.dataset.userId = user.id;
            row.dataset.username = user.username || '';
            row.dataset.isAdmin = user.is_admin ? 'true' : 'false';
            row.dataset.isSelf = user.is_self ? 'true' : 'false';

            const nameCell = document.createElement('td');
            const nameStrong = document.createElement('strong');
            nameStrong.textContent = user.username || 'Usuario';
            nameCell.appendChild(nameStrong);

            const idMeta = document.createElement('div');
            idMeta.className = 'manage-users-meta';
            idMeta.textContent = `ID ${user.id}`;
            nameCell.appendChild(idMeta);

            const roleCell = document.createElement('td');
            roleCell.className = 'manage-users-role';

            const roleToggleLabel = document.createElement('label');
            roleToggleLabel.className = 'admin-role-toggle';

            const roleCheckbox = document.createElement('input');
            roleCheckbox.type = 'checkbox';
            roleCheckbox.className = 'admin-role-checkbox';
            roleCheckbox.checked = Boolean(user.is_admin);
            roleCheckbox.dataset.userId = user.id;
            roleCheckbox.dataset.username = user.username || '';
            roleCheckbox.dataset.currentValue = user.is_admin ? 'true' : 'false';
            roleCheckbox.dataset.isSelf = user.is_self ? 'true' : 'false';
            roleCheckbox.setAttribute('aria-label', `${user.is_admin ? 'Revocar' : 'Otorgar'} permisos de administrador a ${user.username || 'este usuario'}`);

            const roleStatus = document.createElement('span');
            roleStatus.className = 'admin-role-status';
            roleStatus.textContent = user.is_admin ? 'Administrador' : 'Usuario';

            roleToggleLabel.appendChild(roleCheckbox);
            roleToggleLabel.appendChild(roleStatus);
            roleCell.appendChild(roleToggleLabel);

            const emailCell = document.createElement('td');
            emailCell.textContent = user.email || '—';

            const createdCell = document.createElement('td');
            createdCell.textContent = user.created_at ? formatDate(user.created_at) : '—';

            const actionsCell = document.createElement('td');
            actionsCell.className = 'manage-users-actions';

            const resetBtn = document.createElement('button');
            resetBtn.type = 'button';
            resetBtn.classList.add('secondary-btn');
            resetBtn.dataset.action = 'reset';
            resetBtn.textContent = 'Resetear contraseña';
            resetBtn.disabled = user.is_self;

            const deleteBtn = document.createElement('button');
            deleteBtn.type = 'button';
            deleteBtn.classList.add('danger-btn');
            deleteBtn.dataset.action = 'delete';
            deleteBtn.textContent = 'Eliminar';
            deleteBtn.disabled = user.is_self || (user.is_admin && totalAdmins <= 1);

            actionsCell.appendChild(resetBtn);
            actionsCell.appendChild(deleteBtn);

            row.appendChild(nameCell);
            row.appendChild(roleCell);
            row.appendChild(emailCell);
            row.appendChild(createdCell);
            row.appendChild(actionsCell);

            manageUsersTableBody.appendChild(row);
        });

        updateAdminToggleAvailability(totalAdmins);
    }

    async function deleteManageUser(userId) {
        if (!userId) {
            return;
        }

        try {
            const response = await fetch(`/api/admin/users/${userId}`, {
                method: 'DELETE'
            });

            const data = await response.json().catch(() => ({}));

            if (!response.ok || !data.success) {
                const errorMessage = data.error || 'No se pudo eliminar al usuario.';
                setManageUsersFeedback(errorMessage, 'error');
                return;
            }

            setManageUsersFeedback('Usuario eliminado correctamente.', 'success');

            if (adminResetTargetId && Number(adminResetTargetId) === Number(userId)) {
                hideAdminResetPasswordSection();
            }

            await loadManageUsers();
        } catch (error) {
            console.error('Error deleting user:', error);
            setManageUsersFeedback('Error de conexión al eliminar al usuario.', 'error');
        }
    }

    async function handleAdminRoleToggleChange(checkbox) {
        if (!checkbox) {
            return;
        }

        const userId = Number(checkbox.dataset.userId);
        if (!userId) {
            return;
        }

        const previousState = checkbox.dataset.currentValue === 'true';
        const desiredState = checkbox.checked;
        const username = checkbox.dataset.username || '';
        const statusLabel = checkbox.closest('label')?.querySelector('.admin-role-status');

        if (previousState === desiredState) {
            updateAdminToggleAvailability(adminUsersState.totalAdmins);
            if (statusLabel) {
                statusLabel.textContent = desiredState ? 'Administrador' : 'Usuario';
            }
            return;
        }

        if (!desiredState && previousState) {
            const currentAdmins = Number.isFinite(Number(adminUsersState.totalAdmins))
                ? Number(adminUsersState.totalAdmins)
                : adminUsersState.users.filter(user => user.is_admin).length;

            if (currentAdmins <= 1) {
                setManageUsersFeedback('Debe existir al menos un administrador en el sistema.', 'error');
                checkbox.checked = true;
                checkbox.dataset.currentValue = 'true';
                if (statusLabel) {
                    statusLabel.textContent = 'Administrador';
                }
                updateAdminToggleAvailability(adminUsersState.totalAdmins);
                return;
            }
        }

        checkbox.disabled = true;
        if (statusLabel) {
            statusLabel.textContent = 'Actualizando…';
        }
        setManageUsersFeedback('Actualizando permisos...', 'info');

        try {
            const response = await fetch(`/api/admin/users/${userId}/role`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ is_admin: desiredState })
            });

            const data = await response.json().catch(() => ({}));

            if (!response.ok || !data.success) {
                const errorMessage = data.error || 'No se pudo actualizar los permisos de administrador.';
                setManageUsersFeedback(errorMessage, 'error');
                checkbox.checked = previousState;
                checkbox.dataset.currentValue = previousState ? 'true' : 'false';
                if (statusLabel) {
                    statusLabel.textContent = previousState ? 'Administrador' : 'Usuario';
                }
                updateAdminToggleAvailability(adminUsersState.totalAdmins);
                return;
            }

            const successMessage = desiredState
                ? `Permisos de administrador otorgados${username ? ` a ${username}` : ''}.`
                : `Permisos de administrador revocados${username ? ` a ${username}` : ''}.`;
            setManageUsersFeedback(successMessage, 'success');

            checkbox.dataset.currentValue = desiredState ? 'true' : 'false';
            if (statusLabel) {
                statusLabel.textContent = desiredState ? 'Administrador' : 'Usuario';
            }

            if (Array.isArray(adminUsersState.users)) {
                adminUsersState.users = adminUsersState.users.map(user => {
                    if (Number(user.id) === Number(userId)) {
                        return {
                            ...user,
                            is_admin: desiredState
                        };
                    }
                    return user;
                });
            }

            const totalAdminsFromServer = Number(data.total_admins);
            if (!Number.isNaN(totalAdminsFromServer)) {
                adminUsersState.totalAdmins = totalAdminsFromServer;
            } else if (Array.isArray(adminUsersState.users)) {
                adminUsersState.totalAdmins = adminUsersState.users.reduce((count, user) => count + (user.is_admin ? 1 : 0), 0);
            }

            const row = checkbox.closest('tr');
            if (row) {
                row.dataset.isAdmin = desiredState ? 'true' : 'false';
            }

            updateAdminToggleAvailability(adminUsersState.totalAdmins);
        } catch (error) {
            console.error('Error updating admin status:', error);
            setManageUsersFeedback('Error de conexión al actualizar los permisos.', 'error');
            checkbox.checked = previousState;
            checkbox.dataset.currentValue = previousState ? 'true' : 'false';
            if (statusLabel) {
                statusLabel.textContent = previousState ? 'Administrador' : 'Usuario';
            }
            updateAdminToggleAvailability(adminUsersState.totalAdmins);
        } finally {
            checkbox.disabled = false;
        }
    }

    function openManageUsersModal() {
        if (!manageUsersModal) {
            return;
        }

        setManageUsersFeedback('');
        hideAdminResetPasswordSection();
        manageUsersModal.classList.add('open');
        manageUsersModal.setAttribute('aria-hidden', 'false');
        loadManageUsers();
    }

    function closeManageUsersModal() {
        if (!manageUsersModal) {
            return;
        }

        manageUsersModal.classList.remove('open');
        manageUsersModal.setAttribute('aria-hidden', 'true');
        hideAdminResetPasswordSection();
    }

    if (userMenuToggle && userMenuDropdown) {
        userMenuToggle.addEventListener('click', (event) => {
            event.stopPropagation();
            const isOpen = userMenuDropdown.classList.contains('open');
            if (isOpen) {
                closeUserMenu();
            } else {
                openUserMenu();
            }
        });

        userMenuDropdown.addEventListener('click', (event) => {
            event.stopPropagation();
        });

        userMenuItems.forEach(item => {
            item.addEventListener('click', () => {
                closeUserMenu();
            });
        });
    }

    if (changePasswordTrigger) {
        changePasswordTrigger.addEventListener('click', () => {
            closeUserMenu();
            openChangePasswordModal();
        });
    }

    if (currentUserIsAdmin && manageUsersTrigger) {
        manageUsersTrigger.addEventListener('click', () => {
            closeUserMenu();
            openManageUsersModal();
        });
    }

    if (changePasswordModal) {
        changePasswordModal.setAttribute('aria-hidden', 'true');

        const modalCloseButtons = changePasswordModal.querySelectorAll('.modal-close');
        modalCloseButtons.forEach(button => {
            button.addEventListener('click', () => {
                closeChangePasswordModal();
            });
        });
    }

    if (manageUsersModal) {
        manageUsersModal.setAttribute('aria-hidden', 'true');

        manageUsersCloseButtons.forEach(button => {
            button.addEventListener('click', () => {
                closeManageUsersModal();
            });
        });

        manageUsersModal.addEventListener('click', (event) => {
            if (event.target === manageUsersModal) {
                closeManageUsersModal();
            }
        });
    }

    document.addEventListener('click', (event) => {
        if (userMenuDropdown && userMenuDropdown.classList.contains('open')) {
            const clickedInsideDropdown = userMenuDropdown.contains(event.target);
            const clickedToggle = userMenuToggle && userMenuToggle.contains(event.target);
            if (!clickedInsideDropdown && !clickedToggle) {
                closeUserMenu();
            }
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            if (userMenuDropdown && userMenuDropdown.classList.contains('open')) {
                closeUserMenu();
            }

            if (changePasswordModal && changePasswordModal.classList.contains('open')) {
                closeChangePasswordModal();
            }

            if (manageUsersModal && manageUsersModal.classList.contains('open')) {
                closeManageUsersModal();
            }
        }
    });

    if (manageUsersTableBody) {
        manageUsersTableBody.addEventListener('click', (event) => {
            const actionButton = event.target.closest('button[data-action]');
            if (!actionButton || actionButton.disabled) {
                return;
            }

            const row = actionButton.closest('tr');
            if (!row) {
                return;
            }

            const userId = Number(row.dataset.userId);
            const username = row.dataset.username || '';
            const action = actionButton.dataset.action;

            if (action === 'reset') {
                const targetUser = adminUsersState.users.find(user => Number(user.id) === Number(userId));
                if (!targetUser) {
                    setManageUsersFeedback('No se pudo identificar al usuario seleccionado.', 'error');
                    return;
                }

                setManageUsersFeedback('');
                showAdminResetPasswordSection(targetUser);
                return;
            }

            if (action === 'delete') {
                const confirmation = window.confirm(`¿Deseas eliminar al usuario "${username}"? Esta acción no se puede deshacer.`);
                if (!confirmation) {
                    return;
                }

                setManageUsersFeedback('Eliminando usuario...', 'info');
                deleteManageUser(userId);
            }
        });

        manageUsersTableBody.addEventListener('change', (event) => {
            const checkbox = event.target.closest('.admin-role-checkbox');
            if (!checkbox || checkbox.disabled) {
                return;
            }

            handleAdminRoleToggleChange(checkbox);
        });
    }

    if (adminResetForm) {
        adminResetForm.addEventListener('submit', async (event) => {
            event.preventDefault();

            if (!adminResetTargetId) {
                setAdminResetPasswordFeedback('Selecciona un usuario de la lista para resetear su contraseña.', 'error');
                return;
            }

            const newPassword = adminResetPasswordInput ? adminResetPasswordInput.value.trim() : '';
            const confirmPassword = adminResetPasswordConfirmInput ? adminResetPasswordConfirmInput.value.trim() : '';

            if (!newPassword || !confirmPassword) {
                setAdminResetPasswordFeedback('Introduce y confirma la nueva contraseña.', 'error');
                return;
            }

            if (newPassword.length < 8) {
                setAdminResetPasswordFeedback('La nueva contraseña debe tener al menos 8 caracteres.', 'error');
                return;
            }

            if (newPassword !== confirmPassword) {
                setAdminResetPasswordFeedback('Las contraseñas no coinciden.', 'error');
                return;
            }

            const submitBtn = adminResetForm.querySelector('button[type="submit"]');
            if (submitBtn) {
                if (!submitBtn.dataset.originalText) {
                    submitBtn.dataset.originalText = submitBtn.textContent;
                }
                submitBtn.disabled = true;
                submitBtn.textContent = 'Guardando…';
            }

            setAdminResetPasswordFeedback('Actualizando contraseña...', 'info');

            try {
                const response = await fetch(`/api/admin/users/${adminResetTargetId}/reset-password`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        new_password: newPassword
                    })
                });

                const data = await response.json().catch(() => ({}));

                if (!response.ok || !data.success) {
                    const errorMessage = data.error || 'No se pudo resetear la contraseña.';
                    setAdminResetPasswordFeedback(errorMessage, 'error');
                    return;
                }

                setAdminResetPasswordFeedback('Contraseña actualizada correctamente.', 'success');
                adminResetForm.reset();

                setTimeout(() => {
                    hideAdminResetPasswordSection();
                }, 1200);

                await loadManageUsers();
            } catch (error) {
                console.error('Error resetting user password:', error);
                setAdminResetPasswordFeedback('Error de conexión al resetear la contraseña.', 'error');
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = submitBtn.dataset.originalText || 'Guardar nueva contraseña';
                }
            }
        });
    }

    if (adminResetCancelBtn) {
        adminResetCancelBtn.addEventListener('click', () => {
            hideAdminResetPasswordSection();
        });
    }

    if (changePasswordForm) {
        changePasswordForm.addEventListener('submit', async (event) => {
            event.preventDefault();

            const currentPassword = changePasswordInputs.current ? changePasswordInputs.current.value.trim() : '';
            const newPassword = changePasswordInputs.next ? changePasswordInputs.next.value.trim() : '';
            const confirmPassword = changePasswordInputs.confirm ? changePasswordInputs.confirm.value.trim() : '';

            if (!currentPassword || !newPassword || !confirmPassword) {
                setChangePasswordFeedback('Todos los campos son obligatorios.', 'error');
                return;
            }

            if (newPassword.length < 8) {
                setChangePasswordFeedback('La nueva contraseña debe tener al menos 8 caracteres.', 'error');
                return;
            }

            if (newPassword !== confirmPassword) {
                setChangePasswordFeedback('Las nuevas contraseñas no coinciden.', 'error');
                return;
            }

            if (changePasswordSubmitBtn) {
                changePasswordSubmitBtn.disabled = true;
                if (!changePasswordSubmitBtn.dataset.originalText) {
                    changePasswordSubmitBtn.dataset.originalText = changePasswordSubmitBtn.textContent;
                }
                changePasswordSubmitBtn.textContent = 'Actualizando…';
            }

            setChangePasswordFeedback('Actualizando contraseña...', 'info');

            try {
                const response = await fetch('/api/account/change-password', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        current_password: currentPassword,
                        new_password: newPassword
                    })
                });

                const data = await response.json().catch(() => ({}));

                if (!response.ok || !data.success) {
                    const errorMessage = data.error || 'No se pudo actualizar la contraseña.';
                    setChangePasswordFeedback(errorMessage, 'error');
                } else {
                    setChangePasswordFeedback('Contraseña actualizada correctamente.', 'success');
                    changePasswordForm.reset();
                    setTimeout(() => {
                        closeChangePasswordModal();
                    }, 1200);
                }
            } catch (error) {
                console.error('Error cambiando contraseña:', error);
                setChangePasswordFeedback('Error de conexión al actualizar la contraseña.', 'error');
            } finally {
                if (changePasswordSubmitBtn) {
                    changePasswordSubmitBtn.disabled = false;
                    if (changePasswordSubmitBtn.dataset.originalText) {
                        changePasswordSubmitBtn.textContent = changePasswordSubmitBtn.dataset.originalText;
                    }
                }
            }
        });
    }
    
    // Inicialización principal de la aplicación
    function initApp() {
        // Cargar la lista de modelos disponibles primero (es más rápido)
        loadAvailableModels();
        
        // Cargar la lista de archivos (también rápido)
        loadFiles();
        
        // Cargar la lista de chats
        loadChatList();
        
        // Buscar y cargar el último chat activo (añadido por el servidor en la sesión)
        // Usar un pequeño timeout para permitir que la UI se renderice primero
        setTimeout(() => {
            fetch('/api/chats')
                .then(response => response.json())
                .then(chats => {                    if (chats && chats.length > 0) {
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
        }, 100); // Pequeño delay para mejorar la percepción de velocidad
    }

    // Función para mostrar el mensaje de bienvenida en el chat
    function showWelcomeMessage() {
        // Añadir mensaje de bienvenida
        addMessageToChat('assistant', 'Hola, soy Mar-IA-Jose. Un asistente de IA preparado para ayudarte en cuaquier tarea');
    }

    // Función para crear un nuevo chat
    async function createNewChat() {
        const systemMessageInput = document.getElementById('system-message-input');
        const currentSystemMessage = systemMessageInput ? systemMessageInput.value : '';

        await persistCurrentSystemMessage(currentChatId, currentSystemMessage);
        cancelActiveChatRequest();

        try {
            const response = await fetch('/api/new_chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({})
            });

            if (!response.ok) {
                throw new Error(`Error HTTP ${response.status}`);
            }

            const data = await response.json();
            currentChatId = data.chat_id;

            const defaultPromptEntry = savedPromptsCache.find(prompt => prompt.name === 'Default');
            const defaultPromptText = defaultPromptEntry ? defaultPromptEntry.prompt_text : DEFAULT_SYSTEM_PROMPT_TEXT;

            if (systemMessageInput) {
                systemMessageInput.value = defaultPromptText;
            }

            if (ragTopKInput) {
                ragTopKInput.value = DEFAULT_RAG_TOP_K;
            }

            if (temperatureInput) {
                temperatureInput.value = DEFAULT_TEMPERATURE.toFixed(1);
            }

            if (messageHistoryLimitInput) {
                messageHistoryLimitInput.value = DEFAULT_HISTORY_LIMIT;
            }

            currentChatData = {
                messages: [],
                system_message: defaultPromptText,
                rag_top_k: DEFAULT_RAG_TOP_K,
                temperature: DEFAULT_TEMPERATURE,
                message_history_limit: DEFAULT_HISTORY_LIMIT
            };

            clearChatMessages();
            clearChatInputState();
            showWelcomeMessage();
            loadChatList();
        } catch (error) {
            console.error('Error creating new chat:', error);
        }
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
    }

    async function persistCurrentSystemMessage(chatId, systemMessageValue) {
        if (!chatId) {
            return;
        }

        const newValue = systemMessageValue ?? '';
        const storedValue = (currentChatId === chatId && currentChatData)
            ? (currentChatData.system_message || '')
            : '';

        if (newValue === storedValue) {
            return;
        }

        try {
            const response = await fetch(`/api/chat/${chatId}/system_message`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    system_message: newValue
                })
            });

            if (!response.ok) {
                console.error('No se pudo guardar el mensaje del sistema antes de cambiar de conversación.');
                return;
            }

            if (currentChatId === chatId) {
                currentChatData = currentChatData || {};
                currentChatData.system_message = newValue;
            }
        } catch (error) {
            console.error('Error guardando el mensaje del sistema:', error);
        }
    }

    // Función para cargar un chat específico
    async function loadChat(chatId) {
        if (!chatId) {
            return;
        }

    const systemMessageInput = document.getElementById('system-message-input');
    const currentSystemMessage = systemMessageInput ? systemMessageInput.value : '';
    const previousChatId = currentChatId;

    await persistCurrentSystemMessage(previousChatId, currentSystemMessage);

        cancelActiveChatRequest();
        clearChatInputState();

    currentChatId = chatId;
    currentChatData = null;

        // Actualizar la clase activa en la lista de chats
        document.querySelectorAll('.chat-item').forEach(item => {
            item.classList.remove('active');
            if (item.dataset.id === chatId) {
                item.classList.add('active');
            }
        });

        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'loading-indicator';
        loadingDiv.innerHTML = '<div class="loading-spinner"></div><span>Cargando conversación...</span>';
        loadingDiv.id = 'chat-loading-indicator';

        clearChatMessages();
        chatMessages.appendChild(loadingDiv);

        try {
            const response = await fetch(`/api/chat/${chatId}`);
            if (!response.ok) {
                throw new Error(`Error HTTP ${response.status}`);
            }

            const data = await response.json();
            currentChatId = chatId;
            currentChatData = data;

            const loadingIndicator = document.getElementById('chat-loading-indicator');
            if (loadingIndicator) {
                loadingIndicator.remove();
            }

            clearChatMessages();

            if (systemMessageInput) {
                const nextSystemPrompt = data.system_message || DEFAULT_SYSTEM_PROMPT_TEXT;
                systemMessageInput.value = nextSystemPrompt;
                setSystemPromptsFeedback('');
            }

            const resolvedTopK = normalizeTopK(data.rag_top_k);
            if (ragTopKInput) {
                ragTopKInput.value = resolvedTopK;
            }

            const resolvedTemperature = normalizeTemperature(data.temperature);
            if (temperatureInput) {
                temperatureInput.value = resolvedTemperature.toFixed(1);
            }

            const resolvedHistoryLimit = normalizeHistoryLimit(data.message_history_limit);
            if (messageHistoryLimitInput) {
                messageHistoryLimitInput.value = resolvedHistoryLimit;
            }

            currentChatData.rag_top_k = resolvedTopK;
            currentChatData.temperature = resolvedTemperature;
            currentChatData.message_history_limit = resolvedHistoryLimit;

            const messages = data.messages || data;

            if (messages.length === 0) {
                showWelcomeMessage();
            } else {
                messages.forEach(msg => {
                    const options = {
                        rawContent: typeof msg.content === 'string' ? msg.content : null,
                        suppressScroll: true
                    };
                    addMessageToChat(msg.role, msg.content, options);
                });
            }

            if (window.MathJax) {
                window.MathJax.typesetPromise([chatMessages]).catch((err) => {
                    console.error('Error al renderizar LaTeX después de cargar el chat:', err);
                });
            }

            scrollToBottom();
        } catch (error) {
            console.error('Error loading chat:', error);
            const loadingIndicator = document.getElementById('chat-loading-indicator');
            if (loadingIndicator) {
                loadingIndicator.remove();
            }
            clearChatMessages();
            addMessageToChat('assistant', 'Error al cargar la conversación. Por favor, intenta de nuevo.');
        }
    }

    // Función para limpiar los mensajes del chat
    function clearChatMessages() {
        chatMessages.innerHTML = '';
    }

    function prepareMessageData(content, rawContent) {
        let displayContent = '';

        if (Array.isArray(content)) {
            displayContent = content;
        } else if (typeof content === 'string') {
            displayContent = content;
        } else if (typeof rawContent === 'string') {
            displayContent = rawContent;
        }

        let rawForExport = '';

        if (typeof rawContent === 'string' && rawContent.trim()) {
            rawForExport = rawContent;
        } else if (typeof content === 'string') {
            rawForExport = content;
        } else if (Array.isArray(content)) {
            rawForExport = content
                .map(item => (item && item.type === 'text' && typeof item.text === 'string') ? item.text : '')
                .filter(Boolean)
                .join('\n')
                .trim();
        }

        return {
            displayContent,
            rawForExport
        };
    }

    function attachExportButton(messageDiv) {
        if (!messageDiv || messageDiv.querySelector('.message-toolbar')) {
            return;
        }

        const toolbar = document.createElement('div');
        toolbar.className = 'message-toolbar';

        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'export-word-btn';
        button.title = 'Exportar mensaje como Word';
        button.setAttribute('aria-label', 'Exportar mensaje como Word');
        button.innerText = '📄';

        button.addEventListener('click', (event) => {
            event.stopPropagation();
            exportMessageAsWord(messageDiv);
        });

        toolbar.appendChild(button);
        messageDiv.insertBefore(toolbar, messageDiv.firstChild);
        messageDiv.classList.add('has-export-action');
    }

    async function exportMessageAsWord(messageElement) {
        if (!messageElement) {
            return;
        }

        let exportContent = messageElement.__rawContent;

        if (typeof exportContent !== 'string' || !exportContent.trim()) {
            const body = messageElement.querySelector('.message-body');
            exportContent = body ? body.innerText : messageElement.innerText;
        }

        exportContent = exportContent ? exportContent.trim() : '';

        if (!exportContent) {
            alert('No hay contenido disponible para exportar.');
            return;
        }

        try {
            const response = await fetch('/api/export_word', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ content: exportContent })
            });

            const data = await response.json();

            if (!response.ok || !data.download_url) {
                throw new Error(data.error || 'No se pudo generar el documento Word.');
            }

            window.open(data.download_url, '_blank', 'noopener');
        } catch (error) {
            console.error('Error exportando mensaje a Word:', error);
            alert(error.message || 'No se pudo exportar el mensaje a Word.');
        }
    }

    function sanitizeExportContent(rawContent) {
        if (typeof rawContent !== 'string' || !rawContent.trim()) {
            return '';
        }

        let sanitized = rawContent.replace(/<br\s*\/?\>/gi, '\n');
        sanitized = sanitized.replace(/<img[^>]*>/gi, '');
        sanitized = sanitized.replace(/<\/(?:p|div)>/gi, '\n');
        sanitized = sanitized.replace(/&nbsp;/gi, ' ');

        const tempContainer = document.createElement('div');
        tempContainer.innerHTML = sanitized;
        sanitized = (tempContainer.textContent || tempContainer.innerText || '').replace(/\u00a0/g, ' ');

        return sanitized.replace(/\r/g, '').trim();
    }

    function getMessageExportContent(messageElement) {
        if (!messageElement) {
            return '(sin contenido)';
        }

        const rawContent = typeof messageElement.__rawContent === 'string' ? messageElement.__rawContent.trim() : '';
        let content = sanitizeExportContent(rawContent);

        if (!content) {
            const body = messageElement.querySelector('.message-body');
            const bodyText = body ? body.innerText : messageElement.innerText;
            content = (bodyText || '').replace(/\r/g, '').trim();
        }

        const imageCount = messageElement.querySelectorAll('img').length;
        if (imageCount > 0) {
            const placeholder = imageCount === 1 ? '[Imagen adjunta]' : `[${imageCount} imágenes adjuntas]`;
            content = content ? `${content}\n\n${placeholder}` : placeholder;
        }

        if (!content) {
            return '(sin contenido)';
        }

        return content.replace(/\n{3,}/g, '\n\n');
    }

    function getActiveChatTitle() {
        if (currentChatData && typeof currentChatData.title === 'string' && currentChatData.title.trim()) {
            return currentChatData.title.trim();
        }

        const activePreview = document.querySelector('.chat-item.active .chat-preview');
        if (activePreview && activePreview.textContent) {
            const candidate = activePreview.textContent.trim();
            if (candidate) {
                return candidate;
            }
        }

        return '';
    }

    function buildConversationExportContent() {
        if (!chatMessages) {
            return '';
        }

        const messageNodes = Array.from(chatMessages.querySelectorAll('.message'));
        if (messageNodes.length === 0) {
            return '';
        }

        const lines = [];
        const conversationTitle = getActiveChatTitle() || 'Conversación';
        lines.push(`# ${conversationTitle}`);
        lines.push('');
        lines.push(`Generado: ${new Date().toLocaleString()}`);

        const systemMessageInput = document.getElementById('system-message-input');
        const systemMessageValue = (
            currentChatData && typeof currentChatData.system_message === 'string' && currentChatData.system_message.trim()
                ? currentChatData.system_message.trim()
                : (systemMessageInput ? systemMessageInput.value.trim() : '')
        );

        if (systemMessageValue) {
            lines.push('');
            lines.push('## Mensaje del sistema');
            lines.push('');
            lines.push(systemMessageValue);
        }

        lines.push('');
        lines.push('## Historial');
        lines.push('');

        const roleLabels = {
            user: 'Usuario',
            assistant: 'Asistente',
            system: 'Sistema',
            tool: 'Herramienta'
        };

        messageNodes.forEach((node, index) => {
            const role = node.dataset.role
                || (Array.from(node.classList).find(cls => cls.endsWith('-message')) || '').replace('-message', '')
                || 'mensaje';

            const label = roleLabels[role] || role.charAt(0).toUpperCase() + role.slice(1);
            const content = getMessageExportContent(node);

            lines.push(`### Mensaje ${index + 1} · ${label}`);
            lines.push('');
            lines.push(content);
            lines.push('');
        });

        return lines.join('\n').trim();
    }

    async function exportConversationAsWord() {
        if (!currentChatId) {
            alert('Selecciona o crea un chat antes de exportar la conversación.');
            return;
        }

        const exportContent = buildConversationExportContent();
        if (!exportContent) {
            alert('No hay mensajes disponibles para exportar.');
            return;
        }

        try {
            const response = await fetch('/api/export_word', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ content: exportContent })
            });

            const data = await response.json();

            if (!response.ok || !data.download_url) {
                throw new Error(data.error || 'No se pudo generar el documento Word.');
            }

            window.open(data.download_url, '_blank', 'noopener');
        } catch (error) {
            console.error('Error exportando la conversación a Word:', error);
            alert(error.message || 'No se pudo exportar la conversación.');
        }
    }

    // Función para añadir un mensaje al chat (optimizada para mensajes individuales)
    function addMessageToChat(role, content, options = {}) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}-message`;
        messageDiv.dataset.role = role;

        const prepared = prepareMessageData(content, options.rawContent);
        let formattedContent = '';

        if (Array.isArray(prepared.displayContent)) {
            prepared.displayContent.forEach(item => {
                if (item.type === 'text') {
                    formattedContent += formatContent(item.text);
                } else if (item.type === 'image_url' && item.image_url && item.image_url.url) {
                    formattedContent += `<img src="${item.image_url.url}" alt="Imagen adjunta" style="max-width: 100%; height: auto; margin: 10px 0;">`;
                }
            });
        } else {
            formattedContent = formatContent(prepared.displayContent);
        }

        const bodyDiv = document.createElement('div');
        bodyDiv.className = 'message-body';
        bodyDiv.innerHTML = formattedContent;
        messageDiv.appendChild(bodyDiv);

        messageDiv.__rawContent = typeof prepared.rawForExport === 'string' ? prepared.rawForExport.trim() : '';

        if (options.attachExportButton !== false && (role === 'assistant' || role === 'user')) {
            attachExportButton(messageDiv);
        }

        chatMessages.appendChild(messageDiv);

        if (window.MathJax) {
            window.MathJax.typesetPromise([messageDiv]).catch((err) => {
                console.error('Error al renderizar LaTeX:', err);
            });
        }

        if (!options.suppressScroll) {
            scrollToBottom();
        }

        return messageDiv;
    }
    // Función para formatear el contenido (código, enlaces, LaTeX, etc.)
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

    function cancelActiveChatRequest() {
        if (activeChatRequestController) {
            activeChatRequestController.abort();
            activeChatRequestController = null;
            hideTypingIndicator();
        }
    }

    function clearChatInputState() {
        if (chatInput) {
            chatInput.value = '';
        }

        attachedImages = [];

        if (chatInputImagesContainer) {
            chatInputImagesContainer.innerHTML = '';
            chatInputImagesContainer.style.display = 'none';
        }
    }

    // Función para desplazarse al final del chat
    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Función para enviar un mensaje
    async function sendMessage() {
        const message = chatInput.value.trim();
        if (!message) return;

        // Crear nuevo chat si no hay uno activo
        if (!currentChatId) {
            await createNewChat();
        }

        sendMessageToServer(message);
        chatInput.value = '';
    }

    function cacheMessage(role, content) {
        if (!currentChatData || typeof currentChatData !== 'object') {
            currentChatData = {};
        }

        if (!Array.isArray(currentChatData.messages)) {
            currentChatData.messages = [];
        }

        currentChatData.messages.push({
            role,
            content
        });
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

    // Cancelar peticiones anteriores y preparar una nueva
    cancelActiveChatRequest();
    activeChatRequestController = new AbortController();

    // Añadir mensaje del usuario al chat
    addMessageToChat('user', messageContent, { rawContent: messageContent });
    cacheMessage('user', messageContent);

        // Mostrar indicador de escritura
        showTypingIndicator();

        // Obtener el mensaje del sistema personalizado si existe
        const systemMessageInput = document.getElementById('system-message-input');
        const systemMessage = systemMessageInput ? systemMessageInput.value : null;

        if (systemMessageInput) {
            if (!currentChatData || typeof currentChatData !== 'object') {
                currentChatData = {};
            }
            currentChatData.system_message = systemMessage || '';
        }

        // Obtener parámetros de RAG y generación
        const normalizedTopK = ragTopKInput ? normalizeTopK(ragTopKInput.value) : DEFAULT_RAG_TOP_K;
        if (ragTopKInput && ragTopKInput.value !== String(normalizedTopK)) {
            ragTopKInput.value = normalizedTopK;
        }

        const normalizedTemperature = temperatureInput ? normalizeTemperature(temperatureInput.value) : DEFAULT_TEMPERATURE;
        if (temperatureInput) {
            const formattedTemperature = normalizedTemperature.toFixed(1);
            if (temperatureInput.value !== formattedTemperature) {
                temperatureInput.value = formattedTemperature;
            }
        }

        const normalizedHistoryLimit = messageHistoryLimitInput ? normalizeHistoryLimit(messageHistoryLimitInput.value) : DEFAULT_HISTORY_LIMIT;
        if (messageHistoryLimitInput && messageHistoryLimitInput.value !== String(normalizedHistoryLimit)) {
            messageHistoryLimitInput.value = normalizedHistoryLimit;
        }

        if (!currentChatData || typeof currentChatData !== 'object') {
            currentChatData = {};
        }
        currentChatData.rag_top_k = normalizedTopK;
        currentChatData.temperature = normalizedTemperature;
        currentChatData.message_history_limit = normalizedHistoryLimit;

        fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            signal: activeChatRequestController.signal,
            body: JSON.stringify({
                message: messageContent,
                chat_id: currentChatId,
                model_id: currentModelId,
                system_message: systemMessage,
                rag_top_k: normalizedTopK,
                temperature: normalizedTemperature,
                message_history_limit: normalizedHistoryLimit
            })
        })
        .then(response => response.json())
        .then(data => {
            // Ocultar indicador de escritura
            hideTypingIndicator();

            // Añadir respuesta del asistente
            addMessageToChat('assistant', data.response, {
                rawContent: data.raw_response
            });
            const assistantContent = (typeof data.raw_response === 'string' && data.raw_response.trim())
                ? data.raw_response
                : (typeof data.response === 'string' ? data.response : '');
            cacheMessage('assistant', assistantContent);

            // Actualizar ID del chat si es necesario
            if (data.chat_id && (!currentChatId || currentChatId !== data.chat_id)) {
                currentChatId = data.chat_id;
                loadChatList();
            }
        })
        .catch(error => {
            if (error.name === 'AbortError') {
                console.info('Solicitud de chat cancelada:', error);
                return;
            }
            console.error('Error sending message:', error);
            hideTypingIndicator();
            const fallbackMessage = 'Lo siento, ha ocurrido un error al procesar tu mensaje.';
            addMessageToChat('assistant', fallbackMessage);
            cacheMessage('assistant', fallbackMessage);
        })
        .finally(() => {
            activeChatRequestController = null;
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
            logs: [],
            progressId: null,
            progressPoller: null,
            progressState: null,
            lastProgressMessage: null
        };

        queueItem.progressId = queueItem.id;

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

    function stopUploadProgressWatcher(queueItem) {
        if (!queueItem) return;
        if (queueItem.progressPoller) {
            clearInterval(queueItem.progressPoller);
            queueItem.progressPoller = null;
        }
    }

    function fetchUploadProgressOnce(queueItem, { forceUpdate = false } = {}) {
        if (!queueItem || !queueItem.progressId) {
            return Promise.resolve();
        }

        return fetch(`/api/upload/progress/${encodeURIComponent(queueItem.progressId)}`)
            .then(response => response.json())
            .then(data => {
                if (!data || !data.found || !data.progress) {
                    return;
                }
                handleUploadProgressUpdate(queueItem, data.progress, { forceUpdate });
            })
            .catch(error => {
                console.debug('Upload progress poll error:', error);
            });
    }

    function startUploadProgressWatcher(queueItem) {
        if (!queueItem || !queueItem.progressId) {
            return;
        }

        stopUploadProgressWatcher(queueItem);

        // Obtener un estado inicial inmediatamente
        fetchUploadProgressOnce(queueItem);

        queueItem.progressPoller = setInterval(() => {
            fetchUploadProgressOnce(queueItem);
        }, 5000);
    }

    function getProgressMessage(progress, queueItem) {
        if (!progress) {
            return '';
        }

        const attempt = progress.attempt ? Number(progress.attempt) : null;
        const wait = progress.waiting_seconds ? Number(progress.waiting_seconds) : 0;
        const fileName = queueItem?.file?.name || progress.filename || 'archivo';
        const attemptLabel = attempt && attempt > 0 ? ` (intento ${attempt})` : '';

        switch (progress.status) {
            case 'queued':
                return `"${fileName}" en cola. Preparando procesamiento…`;
            case 'document_loaded':
                return `Contenido de "${fileName}" cargado. Analizando texto…`;
            case 'chunking':
                return `Dividiendo "${fileName}" en fragmentos…`;
            case 'vectorizing':
            case 'starting':
                return `Generando embeddings para "${fileName}"${attemptLabel}…`;
            case 'processing':
                return `Generando embeddings para "${fileName}"${attemptLabel}…`;
            case 'rate_limited':
                if (wait > 0) {
                    return `Límite de peticiones alcanzado${attemptLabel}. Nuevo intento en ${wait} s…`;
                }
                return `Límite de peticiones alcanzado${attemptLabel}. Reintentando…`;
            case 'reintentando':
                return `Reintentando generación de embeddings${attemptLabel}…`;
            case 'completed':
                return `Embeddings generados correctamente para "${fileName}".`;
            case 'failed':
                return `Error procesando "${fileName}": ${progress.error || 'revisa los registros.'}`;
            default:
                return '';
        }
    }

    function getProgressStatusLabel(progress) {
        if (!progress) {
            return '';
        }

        switch (progress.status) {
            case 'queued':
                return 'En cola';
            case 'document_loaded':
                return 'Documento cargado';
            case 'chunking':
                return 'Preparando fragmentos';
            case 'vectorizing':
            case 'starting':
            case 'processing':
                return 'Generando embeddings';
            case 'rate_limited':
                return 'Esperando reintento';
            case 'reintentando':
                return 'Reintentando';
            case 'completed':
                return 'Completado';
            case 'failed':
                return 'Error';
            default:
                return '';
        }
    }

    function handleUploadProgressUpdate(queueItem, progress, { forceUpdate = false } = {}) {
        if (!queueItem || !progress) {
            return;
        }

        const previousProgress = queueItem.progressState;
        const previousStatus = previousProgress ? previousProgress.status : null;
        queueItem.progressState = progress;

        const message = getProgressMessage(progress, queueItem);
        const shouldLog = forceUpdate || (message && message !== queueItem.lastProgressMessage);
        const shouldRefreshStatus = forceUpdate || previousStatus !== progress.status;

        if (shouldLog) {
            if (message) {
                addProcessingLog(queueItem, message);
                queueItem.lastProgressMessage = message;
                if (queueItem.status === 'processing') {
                    uploadStatus.textContent = message;
                }
            }
            updateQueueDisplay();
        } else if (progress.status === 'rate_limited' && queueItem.status === 'processing') {
            // Mantener actualizado el estado visible aunque no haya nuevo log
            uploadStatus.textContent = message || uploadStatus.textContent;
        }

        if (shouldRefreshStatus && !shouldLog) {
            updateQueueDisplay();
        }

        if (progress.completed) {
            stopUploadProgressWatcher(queueItem);
        }
    }

    // Función para procesar y subir el archivo
    function processAndUploadFile(queueItem) {
        const file = queueItem.file;
        const processImages = queueItem.processImages;

        const formData = new FormData();
        formData.append('file', file);
        formData.append('process_images', processImages);
        if (queueItem.progressId) {
            formData.append('upload_id', queueItem.progressId);
        }

        addProcessingLog(queueItem, `Subiendo archivo "${file.name}"...`);
        updateQueueDisplay();

        startUploadProgressWatcher(queueItem);

        fetch('/api/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data && data.progress_id && !queueItem.progressId) {
                queueItem.progressId = data.progress_id;
            }

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
                stopUploadProgressWatcher(queueItem);
                fetchUploadProgressOnce(queueItem, { forceUpdate: true });
            } else {
                // Marcar como error
                queueItem.status = 'error';
                addProcessingLog(queueItem, `Error al procesar el archivo: ${data.error || 'Error desconocido'}`);
                uploadStatus.textContent = `Error al subir ${file.name}: ${data.error}`;
                stopUploadProgressWatcher(queueItem);
                fetchUploadProgressOnce(queueItem, { forceUpdate: true });
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
            stopUploadProgressWatcher(queueItem);
            fetchUploadProgressOnce(queueItem, { forceUpdate: true });

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
            let imageData = e.target.result;
            
            // Verificar y corregir el formato de la imagen
            if (imageData) {
                // Asegurarse de que el formato base64 sea correcto
                const imageType = file.type; // Por ejemplo: 'image/png', 'image/jpeg'
                const correctPrefix = `data:${imageType};base64,`;
                
                // Si la imagen no tiene el formato correcto, corregirlo
                if (!imageData.startsWith(correctPrefix)) {
                    console.log('Corrigiendo formato de imagen:', imageData.substring(0, 30));
                    // Extraer solo los datos base64 si ya tiene algún prefijo
                    let base64Data = imageData;
                    if (imageData.includes('base64,')) {
                        base64Data = imageData.split('base64,')[1];
                    } else if (imageData.includes(',')) {
                        base64Data = imageData.split(',')[1];
                    }
                    
                    // Reconstruir con el prefijo correcto
                    imageData = `${correctPrefix}${base64Data}`;
                }
                
                // Verificar que la imagen tenga datos base64 después del prefijo
                if (imageData.endsWith('base64,') || imageData.split('base64,')[1] === '') {
                    console.error('Error: Imagen sin datos base64 válidos');
                    uploadStatus.textContent = 'Error: Formato de imagen inválido';
                    return; // No adjuntar la imagen si no tiene datos base64
                }
                
                // Verificar que los datos base64 sean válidos
                try {
                    const base64Part = imageData.split('base64,')[1];
                    atob(base64Part); // Intenta decodificar para verificar que es base64 válido
                } catch (error) {
                    console.error('Error: Datos base64 inválidos', error);
                    uploadStatus.textContent = 'Error: Datos de imagen inválidos';
                    return; // No adjuntar la imagen si los datos base64 son inválidos
                }
            }
            
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

            const progress = item.progressState;
            let statusText = '';

            if (item.status === 'processing' && progress) {
                statusText = getProgressStatusLabel(progress) || 'Procesando...';
            } else if (item.status === 'completed') {
                statusText = 'Completado';
            } else if (item.status === 'error') {
                statusText = 'Error';
            } else if (item.status === 'pending') {
                statusText = 'Pendiente';
            }

            if (!statusText) {
                statusText = 'Procesando...';
            }

            fileStatus.textContent = statusText;

            fileInfo.appendChild(fileName);
            fileInfo.appendChild(fileStatus);

            if (item.lastProgressMessage) {
                const progressDetail = document.createElement('div');
                progressDetail.className = 'queue-item-progress-message';
                progressDetail.textContent = item.lastProgressMessage;
                fileInfo.appendChild(progressDetail);
            }

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

    if (downloadConversationBtn) {
        downloadConversationBtn.addEventListener('click', function(event) {
            event.preventDefault();
            exportConversationAsWord();
        });
    }

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
                    const systemMessageInput = document.getElementById('system-message-input');

                    if (data.new_chat) {
                        currentChatId = data.new_chat.chat_id;

                        if (systemMessageInput) {
                            systemMessageInput.value = data.new_chat.system_message || '';
                        }

                        currentChatData = {
                            messages: [],
                            system_message: data.new_chat.system_message || ''
                        };

                        clearChatMessages();
                        clearChatInputState();
                        showWelcomeMessage();
                    } else if (chatId === currentChatId) {
                        // Si el chat eliminado es el actual y aún quedan otros, limpiar vista
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

    // Variable para almacenar los datos del chat actual
    let currentChatData = null;

    /**
     * Muestra un mensaje contextual dentro del modal de prompts guardados.
     * @param {string} message Mensaje a mostrar.
     * @param {boolean} isError Indica si el mensaje corresponde a un error.
     */
    function setSystemPromptsFeedback(message, isError = false) {
        if (!systemPromptsFeedback) {
            return;
        }

        systemPromptsFeedback.textContent = message || '';
        if (isError) {
            systemPromptsFeedback.classList.add('error');
        } else {
            systemPromptsFeedback.classList.remove('error');
        }
    }

    /**
     * Rellena el desplegable con los prompts guardados en caché.
     * @param {string} [selectedPromptId] ID que se debe mantener seleccionado tras el renderizado.
     */
    function populateSavedPromptsDropdown(selectedPromptId = '') {
        if (!savedPromptsSelect) {
            return;
        }

        savedPromptsSelect.innerHTML = '';

        const placeholderOption = document.createElement('option');
        placeholderOption.value = '';
        placeholderOption.textContent = savedPromptsCache.length
            ? 'Selecciona un prompt guardado…'
            : 'No tienes prompts guardados todavía';
        placeholderOption.selected = true;
        savedPromptsSelect.appendChild(placeholderOption);

        savedPromptsSelect.disabled = savedPromptsCache.length === 0;

        savedPromptsCache.forEach(prompt => {
            const option = document.createElement('option');
            option.value = prompt.id.toString();
            option.textContent = prompt.name;
            savedPromptsSelect.appendChild(option);
        });

        if (selectedPromptId) {
            savedPromptsSelect.value = selectedPromptId;
            savedPromptsSelect.dispatchEvent(new Event('change'));
        } else {
            savedPromptsSelect.value = '';
        }
    }

    /**
     * Solicita los prompts guardados al backend y refresca el desplegable.
     * @param {string} [selectedPromptId] ID que se debe seleccionar al terminar.
     */
    function fetchSavedPrompts(selectedPromptId = '') {
        if (!savedPromptsSelect) {
            return Promise.resolve();
        }

        setSystemPromptsFeedback('Cargando prompts guardados…');

        return fetch('/api/user_prompts')
            .then(response => {
                if (!response.ok) {
                    if (response.status === 401) {
                        // El usuario debe autenticarse para usar el catálogo personal.
                        savedPromptsCache = [];
                        populateSavedPromptsDropdown();
                        setSystemPromptsFeedback('Inicia sesión para guardar tus prompts.', true);
                        return null;
                    }
                    throw new Error('No se pudieron cargar los prompts guardados.');
                }
                return response.json();
            })
            .then(data => {
                if (!data) {
                    return;
                }

                savedPromptsCache = data.prompts || [];
                populateSavedPromptsDropdown(selectedPromptId);
                setSystemPromptsFeedback(savedPromptsCache.length ? '' : 'No tienes prompts guardados todavía.');
            })
            .catch(error => {
                console.error('Error obteniendo prompts guardados:', error);
                setSystemPromptsFeedback(error.message || 'Error al cargar los prompts guardados.', true);
            });
    }

    if (savedPromptsSelect) {
        savedPromptsSelect.addEventListener('change', () => {
            const selectedId = savedPromptsSelect.value;

            if (!selectedId) {
                setSystemPromptsFeedback('');
                return;
            }

            const selectedPrompt = savedPromptsCache.find(prompt => prompt.id.toString() === selectedId);

            if (selectedPrompt) {
                const messageInput = document.getElementById('system-message-input');
                if (messageInput) {
                    messageInput.value = selectedPrompt.prompt_text;
                    messageInput.focus();
                }
                setSystemPromptsFeedback(`Prompt "${selectedPrompt.name}" cargado.`);
            }
        });
    }

    if (storeSystemPromptBtn) {
        storeSystemPromptBtn.addEventListener('click', () => {
            const messageInput = document.getElementById('system-message-input');
            if (!messageInput) {
                return;
            }

            const promptText = messageInput.value.trim();
            if (!promptText) {
                setSystemPromptsFeedback('Escribe un prompt antes de guardarlo.', true);
                messageInput.focus();
                return;
            }

            const currentSelection = savedPromptsCache.find(prompt => prompt.id.toString() === savedPromptsSelect?.value);
            const defaultName = currentSelection ? currentSelection.name : '';

            const promptName = window.prompt('Introduce un nombre para el prompt que deseas guardar:', defaultName);
            if (promptName === null) {
                return;
            }

            const trimmedName = promptName.trim();
            if (!trimmedName) {
                setSystemPromptsFeedback('El nombre del prompt no puede estar vacío.', true);
                return;
            }

            fetch('/api/user_prompts', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    name: trimmedName,
                    prompt_text: promptText
                })
            })
                .then(response => response.json().then(data => ({ ok: response.ok, data })))
                .then(({ ok, data }) => {
                    if (!ok || !data.success) {
                        throw new Error(data.error || 'No se pudo guardar el prompt.');
                    }

                    const savedPromptId = data.prompt?.id ? data.prompt.id.toString() : '';
                    setSystemPromptsFeedback(`Prompt "${data.prompt.name}" guardado correctamente.`);
                    fetchSavedPrompts(savedPromptId);
                })
                .catch(error => {
                    console.error('Error al guardar prompt:', error);
                    setSystemPromptsFeedback(error.message || 'Error al guardar el prompt.', true);
                });
        });
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

        // Refrescar la lista de prompts guardados cada vez que se abre el modal
        fetchSavedPrompts();

        // Si tenemos los datos del chat actual, usar el system message de ahí
        if (currentChatData && currentChatData.system_message !== undefined) {
            const systemMessage = currentChatData.system_message || '';
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
        } else {
            // Si no tenemos los datos en memoria, cargarlos del servidor
            fetch(`/api/chat/${currentChatId}`)
            .then(response => response.json())
            .then(data => {
                // Almacenar los datos del chat actual
                currentChatData = data;
                
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
                // Actualizar los datos del chat actual en memoria
                if (currentChatData) {
                    currentChatData.system_message = systemMessage;
                }
                
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

    if (helpBtn) {
        helpBtn.addEventListener('click', (event) => {
            event.preventDefault();
            window.open('/help', '_blank', 'noopener');
        });
    }
    
    // Iniciar la aplicación (carga chats, modelos y archivos)
    initApp();
});