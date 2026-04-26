document.addEventListener('DOMContentLoaded', function() {
    console.log("🚀 [DEBUG] Article Generator Script Loaded");

    // --- 1. ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ (доступны всем функциям) ---
    const form = document.getElementById('article-gen-form');
    const confirmModal = document.getElementById('confirm-modal');
    const confirmList = document.getElementById('confirm-list');
    const warningBox = document.getElementById('warning-box');
    const warningText = document.getElementById('warning-text');
    const confirmStartBtn = document.getElementById('confirm-start-btn');
    const closeBtn = document.getElementById('close-confirm');
    const promptsToggle = document.getElementById('enable-prompts-toggle');
    const promptContainer = document.getElementById('prompt-settings-container');
    
    let submitBtn = form ? form.querySelector('button[type="submit"]') : null;
    let isGenerating = false; // Флаг защиты от двойного клика

    if (!form) {
        console.error("❌ Форма не найдена!");
        return;
    }

    // --- 2. ЛОГИКА ПЕРЕКЛЮЧАТЕЛЯ ПРОМПТОВ ---
    if (promptsToggle && promptContainer) {
        const inputs = promptContainer.querySelectorAll('input, select, textarea');
        const updatePromptState = () => {
            const isEnabled = promptsToggle.checked;
            promptContainer.classList.toggle('opacity-50', !isEnabled);
            promptContainer.classList.toggle('pointer-events-none', !isEnabled);
            inputs.forEach(el => el.disabled = !isEnabled);
        };
        promptsToggle.addEventListener('change', updatePromptState);
        updatePromptState();
    }

    // Логика радиокнопок (Авто/Ручной)
    const radioButtons = document.querySelectorAll('input[name="image_mode"]');
    const manualCountBlock = document.getElementById('manual-count-block');
    if (radioButtons.length > 0 && manualCountBlock) {
        const toggleManualBlock = () => {
            const isManual = document.querySelector('input[name="image_mode"]:checked')?.value === 'manual';
            manualCountBlock.style.display = isManual ? 'block' : 'none';
        };
        radioButtons.forEach(radio => radio.addEventListener('change', toggleManualBlock));
        toggleManualBlock();
    }

    // --- 3. УТИЛИТЫ МОДАЛКИ ---
    window.closeConfirmModal = function() {
        if (!confirmModal) return;
        confirmModal.classList.add('d-none');
        confirmModal.style.display = ''; 
        console.log("❌ Модалка закрыта.");
    };

    if (closeBtn) closeBtn.addEventListener('click', window.closeConfirmModal);
    if (confirmModal) {
        confirmModal.addEventListener('click', (e) => {
            if (e.target === confirmModal) window.closeConfirmModal();
        });
    }

    // --- 4. ОБРАБОТКА ОТПРАВКИ ФОРМЫ ---
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Защита от повторного открытия, если процесс уже идет
        if (isGenerating) {
            alert("Генерация уже запущена! Пожалуйста, дождитесь завершения.");
            return;
        }

        console.log("✋ [DEBUG] Кнопка нажата. Валидация...");

        if(warningBox) warningBox.classList.add('d-none');
        if(confirmList) confirmList.innerHTML = '';
        if(confirmStartBtn) confirmStartBtn.style.display = 'flex';

        const selectedIdeas = Array.from(document.querySelectorAll('.idea-checkbox:checked'));
        const selectedLangs = Array.from(document.querySelectorAll('input[name="languages"]:checked'));
        const isPromptsEnabled = promptsToggle ? promptsToggle.checked : true;
        
        let summaryHtml = '';
        const errors = [];

        if (selectedIdeas.length === 0) errors.push("⚠️ <strong>Не выбрана ни одна тема!</strong>");
        else summaryHtml += `<li class="mb-2"><strong>📝 Темы:</strong> ${selectedIdeas.length} шт.</li>`;

        if (selectedLangs.length === 0) errors.push("⚠️ Не выбран язык.");
        else {
            const langNames = selectedLangs.map(l => l.nextElementSibling?.innerText.split('(')[0].trim() || l.value).join(', ');
            summaryHtml += `<li class="mb-2"><strong>🌍 Языки:</strong> ${langNames}</li>`;
        }

        if (isPromptsEnabled) {
            const imageMode = document.querySelector('input[name="image_mode"]:checked')?.value || 'auto';
            const artStyle = document.getElementById('id_art_style')?.value;
            const aspectRatio = document.getElementById('id_aspect_ratio')?.value || '9:16';
            const manualCount = document.getElementById('id_manual_scene_count')?.value || 5;
            const modeText = imageMode === 'auto' ? 'Автоматический' : `Ручной (${manualCount} сцен)`;
            
            summaryHtml += `<li class="mb-2"><strong>🎨 Режим:</strong> ${modeText}</li>`;
            summaryHtml += `<li class="mb-2"><strong>📐 Пропорции:</strong> ${aspectRatio}</li>`;
            if (artStyle) summaryHtml += `<li class="mb-2"><strong>✨ Стиль:</strong> ${artStyle}</li>`;
        } else {
            summaryHtml += `<li class="mb-2 text-warning"><strong>🎨 Картинки:</strong> ОТКЛЮЧЕНЫ</li>`;
        }

        const providerEl = document.getElementById('id_ai_provider');
        if (providerEl) summaryHtml += `<li class="mb-2"><strong>🤖 AI:</strong> ${providerEl.options[providerEl.selectedIndex].text}</li>`;

        if (errors.length > 0) {
            if (warningText) warningText.innerHTML = errors.join('<br>');
            if (warningBox) warningBox.classList.remove('d-none');
            if (confirmStartBtn) confirmStartBtn.style.display = 'none';
            if (confirmModal) {
                confirmModal.classList.remove('d-none');
                Object.assign(confirmModal.style, { display: 'flex', opacity: '1', visibility: 'visible', zIndex: '9999' });
            }
        } else {
            if (confirmList) confirmList.innerHTML = summaryHtml;
            if (warningBox) warningBox.classList.add('d-none');
            
            if (confirmStartBtn) {
                confirmStartBtn.style.display = 'flex';
                // Клонируем кнопку для сброса старых слушателей
                const newBtn = confirmStartBtn.cloneNode(true);
                confirmStartBtn.parentNode.replaceChild(newBtn, confirmStartBtn);
                
                newBtn.addEventListener('click', function() {
                    if (isGenerating) return;
                    startGenerationProcess();
                });
            }
            
            if (confirmModal) {
                confirmModal.classList.remove('d-none');
                Object.assign(confirmModal.style, { display: 'flex', opacity: '1', visibility: 'visible', zIndex: '9999' });
            }
        }
    });

    // --- 5. ФУНКЦИЯ ЗАПУСКА (ОБНОВЛЕННАЯ) ---
    function startGenerationProcess() {
        isGenerating = true;
        console.log("🚀 [ACTION] ЗАПУСК ГЕНЕРАЦИИ!");
        
        window.closeConfirmModal();
        
        // Блокируем кнопку
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerText = '⏳ Генерация идет...';
        }

        // Предупреждение при закрытии страницы
        window.onbeforeunload = function() { return "Генерация идет..."; };

        const formData = new FormData(form);
        console.log("📡 Отправка данных на:", window.GEN_API_URL);
        
        fetch(window.GEN_API_URL, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCookie('csrftoken')
            }
        })
        .then(response => {
            if (!response.ok) throw new Error(`HTTP Error: ${response.status}`);
            return response.json();
        })
        .then(data => {
            console.log("📥 Ответ сервера:", data);
            
            if (data.status === 'started' && data.task_id) {
                // ✅ ВАЖНО: Запускаем новый трекер прогресса
                if (typeof initProgressTracker === 'function' && window.GEN_STREAM_URL) {
                    initProgressTracker(window.GEN_STREAM_URL, data.task_id);
                } else {
                    console.error("Функция initProgressTracker не найдена или нет URL потока");
                }
            } else {
                throw new Error(data.message || 'Ошибка сервера: не получен task_id');
            }
        })
        .catch(error => {
            console.error("❌ Ошибка запуска:", error);
            alert("Ошибка: " + error.message);
            resetUIState();
        });
    }

    // --- 6. СБРОС СОСТОЯНИЯ (ПРИ ОШИБКЕ) ---
    function resetUIState() {
        window.onbeforeunload = null;
        isGenerating = false;
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerText = '🚀 Запустить генерацию';
        }
    }

    // --- 7. УТИЛИТА ДЛЯ COOKIE ---
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
});