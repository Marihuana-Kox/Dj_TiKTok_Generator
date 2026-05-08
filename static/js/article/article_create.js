// ============================================================================
// ARTICLE CREATE — форма, валидация, AJAX, SSE прогресс
// Страница: /article/create/
// ============================================================================

let eventSource = null;
let isGenerating = false;
let submitBtn = null;  // ← ГЛОБАЛЬНАЯ ПЕРЕМЕННАЯ
let form = null;       // ← ГЛОБАЛЬНАЯ ПЕРЕМЕННАЯ

document.addEventListener('DOMContentLoaded', function() {
    console.log('🔍 article_create.js инициализация...');

    form = document.getElementById('article-gen-form');
    submitBtn = form?.querySelector('button[type="submit"]');
    const progressModal = document.getElementById('progress-modal');
    const closeProgressBtn = document.getElementById('close-progress-modal');

    if (!form || !submitBtn) {
        console.log('⚠️ Форма не найдена, article_create.js не активен');
        return;
    }

    // Переключение настроек промптов
    initPromptSettings();

    // Выбор всех идей
    initSelectAll();

    // Клик по строке → чекбокс
    initRowClick();

    // Отправка формы
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        if (isGenerating) {
            showToast('⏳ Генерация уже запущена', 'error');
            return;
        }

        // Валидация
        const selectedCheckboxes = document.querySelectorAll('input[name="idea_selection"]:checked');
        if (selectedCheckboxes.length === 0) {
            showToast('⚠️ Выберите хотя бы одну идею', 'error');
            return;
        }

        const formData = new FormData(form);
        startGeneration(formData);
    });

    // Закрытие прогресс модалки
    if (closeProgressBtn) {
        closeProgressBtn.addEventListener('click', function() {
            closeModal('progress-modal');
        });
    }

    console.log('✅ article_create.js готов');
});

// ============================================================================
// НАСТРОЙКИ ПРОМПТОВ
// ============================================================================

function initPromptSettings() {
    const promptsToggle = document.getElementById('enable-prompts-toggle');
    const promptBlock = document.getElementById('prompt-settings-container');
    const manualRadio = document.querySelector('input[name="image_mode"][value="manual"]');
    const manualBlock = document.getElementById('manual-count-block');

    function toggleSettings() {
        const isEnabled = promptsToggle ? promptsToggle.checked : true;
        const isManual = manualRadio ? manualRadio.checked : false;

        if (!isEnabled) {
            if (promptBlock) {
                promptBlock.style.display = 'none';
                promptBlock.classList.add('d-none');
            }
        } else {
            if (promptBlock) {
                promptBlock.style.display = 'block';
                promptBlock.classList.remove('d-none');
            }
            if (manualBlock) {
                manualBlock.style.display = isManual ? 'block' : 'none';
                manualBlock.classList.toggle('d-none', !isManual);
            }
        }
    }

    if (promptsToggle) promptsToggle.addEventListener('change', toggleSettings);
    if (manualRadio) manualRadio.addEventListener('change', toggleSettings);
    
    const autoRadio = document.querySelector('input[name="image_mode"][value="auto"]');
    if (autoRadio) autoRadio.addEventListener('change', toggleSettings);

    toggleSettings();
}

// ============================================================================
// ЧЕКБОКСЫ
// ============================================================================

function initSelectAll() {
    const selectAll = document.getElementById('select-all-ideas');
    const checkboxes = document.querySelectorAll('.idea-checkbox');

    if (selectAll) {
        selectAll.addEventListener('change', function() {
            checkboxes.forEach(cb => {
                cb.checked = this.checked;
                cb.dispatchEvent(new Event('change'));
            });
        });
    }
}

function initRowClick() {
    document.querySelectorAll('.idea-row').forEach(row => {
        row.addEventListener('click', function(e) {
            if (e.target.type !== 'checkbox') {
                const checkbox = row.querySelector('.idea-checkbox');
                if (checkbox) {
                    checkbox.checked = !checkbox.checked;
                    checkbox.dispatchEvent(new Event('change'));
                }
            }
        });
    });
}

// ============================================================================
// ГЕНЕРАЦИЯ + SSE ПРОГРЕСС
// ============================================================================

function startGeneration(formData) {
    console.log('🚀 startGeneration вызван');
    
    if (!submitBtn) {
        console.error('❌ submitBtn не найден!');
        return;
    }
    
    isGenerating = true;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '⏳ Обработка...';

    openModal('progress-modal');
    updateProgress(0, 'Инициализация...');

    const url = window.GEN_API_URL || form.action || '/article/api/start-generation/';

    fetch(url, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: formData
    })
    .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
    })
    .then(data => {
        if (data.status === 'started') {
            startProgressTracking(window.GEN_STREAM_URL || '/article/api/generation-stream/');
        } else {
            throw new Error(data.message || 'Ошибка сервера');
        }
    })
    .catch(err => {
        console.error('❌ Ошибка:', err);
        showToast('❌ ' + err.message, 'error');
        isGenerating = false;
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '🚀 Запустить генерацию';
        }
        closeModal('progress-modal');
    });
}

function startProgressTracking(url) {
    console.log('📡 SSE подключение:', url);

    if (eventSource) eventSource.close();
    eventSource = new EventSource(url);

    eventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            console.log('📊 Прогресс:', data);

            if (data.percent !== undefined) {
                updateProgress(data.percent, data.message);
            }

            if (data.status === 'done') {
                finishProgress(true, '✅ Готово!', '/article/', 2000);
                eventSource.close();
            } else if (data.status === 'error') {
                finishProgress(false, '❌ ' + (data.message || 'Ошибка'));
                eventSource.close();
                isGenerating = false;
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '🚀 Запустить генерацию';
                }
            }
        } catch (e) {
            console.error('Ошибка парсинга SSE:', e);
        }
    };

    eventSource.onerror = function(err) {
        console.error('❌ SSE ошибка:', err);
        eventSource.close();
        
        const progressBar = document.getElementById('gen-progress-bar');
        if (progressBar && parseFloat(progressBar.style.width) >= 100) {
            finishProgress(true, '✅ Завершено');
        } else {
            finishProgress(false, '⚠️ Соединение прервано');
            isGenerating = false;
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = '🚀 Запустить генерацию';
            }
        }
    };
}

console.log('✅ article_create.js загружен');