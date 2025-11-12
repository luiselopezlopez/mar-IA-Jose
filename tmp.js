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
    const cameraBtn = document.getElementById('camera-btn');
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

            currentChatData = {
                messages: [],
                system_message: defaultPromptText
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

    // Función para añadir un mensaje al chat (optimizada para mensajes individuales)
    function addMessageToChat(role, content, options = {}) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}-message`;

        const prepared = prepareMessageData(content, options.rawContent);
        let formattedContent = '';

        // Verificar si el contenido es un array (formato multimodal) o texto simple
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
        
        // Actualizar la renderización de MathJax solo para este mensaje específico
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
