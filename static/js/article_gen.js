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
    
    // Элементы прогресс-бара (теперь глобальные)
    const progressContainer = document.getElementById('gen-progress');
    const progressBar = document.getElementById('gen-bar');
    const progressMsg = document.getElementById('gen-msg');
    const logList = document.getElementById('log-list');
    const taskId = "{{ task_id|default:'' }}";
    
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

    // --- 5. ФУНКЦИЯ ЗАПУСКА (ГЛОБАЛЬНАЯ ЛОГИКА) ---
    function startGenerationProcess() {
        isGenerating = true;
        console.log("🚀 [ACTION] ЗАПУСК ГЕНЕРАЦИИ!");
        
        window.closeConfirmModal();
        
        // Показываем прогресс
        if (progressContainer) progressContainer.classList.remove('d-none');
        if (progressBar) progressBar.style.width = '0%';
        if (progressMsg) progressMsg.innerText = "Подготовка...";
        if (logList) logList.innerHTML = '';

        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerText = '⏳ Генерация идет...';
        }

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
            if (data.status === 'started') {
                connectSSE();
            } else {
                throw new Error(data.message || 'Ошибка сервера');
            }
        })
        .catch(error => {
            console.error("❌ Ошибка запуска:", error);
            alert("Ошибка: " + error.message);
            resetUIState();
        });
    }

    // --- 6. SSE ПОТОК ---
    function connectSSE() {
        if (!window.GEN_STREAM_URL) return;
        console.log("📡 Подключение к SSE...");
        
        if (taskId) {
            const eventSource = new EventSource(`/path/to/generate_stream/?task_id=${taskId}`);
            
            eventSource.onmessage = function(event) {
                const data = JSON.parse(event.data);
                
                // Обновляем прогрессбар
                const progressBar = document.getElementById('your-progress-bar-id');
                const progressText = document.getElementById('your-text-id');
                
                if (progressBar) {
                    progressBar.style.width = data.percent + '%';
                    progressBar.setAttribute('aria-valuenow', data.percent);
                }
                
                if (progressText) {
                    progressText.innerText = `${data.message} (${data.percent}%)`;
                }
        
                if (data.status === 'done') {
                    eventSource.close();
                    // Перезагрузка или редирект
                    setTimeout(() => window.location.reload(), 1000);
                } else if (data.status === 'error') {
                    eventSource.close();
                    alert(data.message);
                }
            };
        }
    };

    // --- 7. ЗАВЕРШЕНИЕ И СБРОС ---
    function finishGeneration(success, errorMsg) {
        window.onbeforeunload = null;
        isGenerating = false; // Сбрасываем флаг
        
        if (success) {
            if (progressMsg) progressMsg.innerText = "✅ Готово! Перенаправление...";
            if (submitBtn) {
                submitBtn.innerText = '✅ Успешно';
                submitBtn.classList.remove('btn-success');
                submitBtn.classList.add('btn-primary');
            }
            setTimeout(() => { window.location.href = "/article/"; }, 2000);
        } else {
            if (progressMsg) progressMsg.innerText = "❌ Ошибка!";
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerText = '🔄 Попробовать снова';
                submitBtn.classList.add('btn-danger');
            }
            if (errorMsg) alert("Ошибка: " + errorMsg);
        }
    }

    function resetUIState() {
        window.onbeforeunload = null;
        isGenerating = false;
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerText = '🚀 Запустить генерацию';
        }
        // Прогресс бар не скрываем, чтобы пользователь видел последний статус
    }

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