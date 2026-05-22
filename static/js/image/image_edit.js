// ============================================================================
// IMAGE EDIT — финальная рабочая версия
// ============================================================================

let selectedPromptIds = [];

// Выносим функции в глобальную область, чтобы модалка их видела
window.openConfirmModal = function(e, singleIdOrArray = null) {
    if (e) {
        e.preventDefault(); 
        e.stopPropagation();
    }

    // 🔥 ИСПРАВЛЕНО: Если передан конкретный ID (одиночный запуск), работаем строго с ним
    if (singleIdOrArray) {
        selectedPromptIds = Array.isArray(singleIdOrArray) ? singleIdOrArray : [singleIdOrArray];
    }

    if (selectedPromptIds.length === 0) {
        alert('Выберите хотя бы одну сцену!');
        return;
    }

    const providerSelect = document.getElementById('image-provider-select');
    if (!providerSelect || !providerSelect.value) {
        alert('Выберите провайдера!');
        return;
    }

    const countEl = document.getElementById('modal-prompt-count');
    if (countEl) countEl.innerText = selectedPromptIds.length;
    
    // ✅ Правильный ID модалки
    if (typeof openModal === 'function') {
        openModal('progress-modal');
    }
    
    startGeneration();
};

function startGeneration() {
    const provider = document.getElementById('image-provider-select')?.value;
    const size = document.getElementById('image-size-select')?.value;
    const style = document.getElementById('style-preset-select')?.value;
    
    const formData = new FormData();
    formData.append('provider', provider);
    formData.append('selected_prompts', selectedPromptIds.join(','));
    formData.append('aspect_ratio', size);
    formData.append('style_preset', style);

    fetch(window.location.href, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: formData
    })
    .then(r => r.json())
    .then(data => {
        // 🔥 ИСПРАВЛЕНО: Если бэкенд вернул сообщение, что всё уже сгенерировано, просто закрываем модалку
        if (data.success && data.message && !data.task_id) {
            alert(data.message);
            if (typeof closeModal === 'function') closeModal('progress-modal');
            return;
        }

        if (typeof window.startProgressTracking === 'function' && data.task_id) {
            window.startProgressTracking(
                '/images/api/generation-stream/', 
                data.task_id, 
                'progress-modal',
                function(result) {
                    if (result.success) {
                        console.log('🔄 Генерация завершена. Обновляем блоки без перезагрузки...');
                        
                        fetch(window.location.href)
                            .then(res => res.text())
                            .then(html => {
                                const parser = new DOMParser();
                                const doc = parser.parseFromString(html, 'text/html');
                                
                                const newBlocks = doc.querySelectorAll('.thumbnail-empty');
                                const currentBlocks = document.querySelectorAll('.thumbnail-empty');
                                
                                if (newBlocks.length > 0 && currentBlocks.length === newBlocks.length) {
                                    currentBlocks.forEach((block, i) => {
                                        block.innerHTML = newBlocks[i].innerHTML;
                                    });
                                    
                                    document.querySelectorAll('.thumbnail-empty img, .thumbnail-empty a[data-lightbox]').forEach(el => {
                                        el.addEventListener('click', function(e) {
                                            e.preventDefault();
                                            openLightbox(this.src || this.getAttribute('href'), this.alt || '');
                                        });
                                    });
                                } else {
                                    window.location.reload();
                                }
                            })
                            .catch(() => window.location.reload());
                    }
                }
            );
        } else {
            console.error('❌ Ошибка: ' + (data.error || 'Неизвестная ошибка'));
            alert('Ошибка: ' + (data.error || 'Не удалось запустить генерацию'));
            if (typeof closeModal === 'function') closeModal('progress-modal');
        }
    })
    .catch(err => {
        console.error('Fetch error:', err);
        if (typeof closeModal === 'function') closeModal('progress-modal');
    });
}

// Инициализация (DOMContentLoaded)
document.addEventListener('DOMContentLoaded', function() {
    console.log('🔍 image_edit.js инициализация...');

    document.querySelectorAll('textarea.form-control').forEach(tx => {
        tx.style.height = 'auto';
        tx.style.height = tx.scrollHeight + 'px';
        tx.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = this.scrollHeight + 'px';
        });
    });

    const selectAll = document.getElementById('select-all-prompts');
    const checkboxes = document.querySelectorAll('.prompt-checkbox');
    const generateBtn = document.getElementById('generate-images-btn');
    const providerSelect = document.getElementById('image-provider-select');

    function updateCount() {
        // 🔥 ИСПРАВЛЕНО: Считаем только отмеченные чекбоксы, которые НЕ ЗАБЛОКИРОВАНЫ
        const checked = Array.from(checkboxes).filter(cb => cb.checked && !cb.disabled);
        selectedPromptIds = checked.map(cb => cb.value);
        const count = checked.length;
        
        const countDisplay = document.getElementById('selected-count');
        const btnCountDisplay = document.getElementById('btn-count');
        if (countDisplay) countDisplay.innerText = `(выбрано: ${count})`;
        if (btnCountDisplay) btnCountDisplay.innerText = count;
        if (generateBtn) generateBtn.disabled = count === 0 || !providerSelect?.value;

        // Корректируем состояние кнопки "Выбрать все"
        if (selectAll) {
            const activeBoxes = Array.from(checkboxes).filter(cb => !cb.disabled);
            if (activeBoxes.length > 0) {
                selectAll.checked = checked.length === activeBoxes.length;
            } else {
                selectAll.checked = false;
            }
        }
    }

    if (selectAll) selectAll.addEventListener('change', function() {
        checkboxes.forEach(cb => {
            // 🔥 ИСПРАВЛЕНО: "Выбрать все" проставляет галочки только незаблокированным кадрам
            if (!cb.disabled) {
                cb.checked = this.checked;
            }
        });
        updateCount();
    });

    checkboxes.forEach(cb => cb.addEventListener('change', updateCount));
    if (providerSelect) providerSelect.addEventListener('change', updateCount);
    if (generateBtn) generateBtn.addEventListener('click', function(e) {
        window.openConfirmModal(e);
    });
});

// Лайтбокс (без изменений)
function openLightbox(imageUrl, title) {
    const overlay = document.getElementById('lightbox-overlay');
    const image = document.getElementById('lightbox-image');
    if (overlay && image) {
        image.src = imageUrl;
        overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}
function closeLightbox() {
    const overlay = document.getElementById('lightbox-overlay');
    if (overlay) {
        overlay.classList.remove('active');
        document.body.style.overflow = '';
    }
}

// 🔥 ИСПРАВЛЕНО: Кнопка точечного перезапуска конкретного кадра
function generateSingleImage(promptId) {
    if (confirm("Вы уверены, что хотите перегенерировать этот кадр? Старая картинка перезапишется.")) {
        // Вызываем модалку и передаем ID конкретного кадра напрямую в обход стандартных чекбоксов
        window.openConfirmModal(null, promptId); 
    }
}/**
 * Функция-триггер для открытия окна выбора файла при клике на контейнер
 */
function triggerManualUpload(containerElement) {
    if (!containerElement) return;
    
    const fileInput = containerElement.querySelector('input[type="file"]');
    if (fileInput) {
        fileInput.click(); // Открываем системное окно выбора файла
    }
}
document.addEventListener('DOMContentLoaded', function() {
    const styleSelect = document.getElementById('style-preset-select');
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    
    const styleReplacements = {
        'cinematic': 'Cinematic shot, cinematic dark lighting',
        'anime': 'Anime style, Studio Ghibli art, vibrant colors',
        'realistic': 'Photorealistic ultra-detailed photo, 8k',
        'artistic': 'Artistic oil painting, painterly style, dramatic artistic look',
        'custom': 'Comic book style, graphic novel art, ink contours'
    };

    // Общая функция отправки в БД
    function saveToDatabase(promptId, text, textareaElement) {
        // 🔥 ЗАЩИТА: Если текст пустой, отменяем сохранение, чтобы не затереть базу данных!
        if (!text || text.trim().length === 0) {
            console.warn(`⚠️ Попытка сохранить пустой текст для кадра #${promptId} заблокирована!`);
            textareaElement.style.borderColor = '#dc3545'; // Подсветим красным ошибку
            return;
        }

        const formData = new FormData();
        formData.append('action', 'autosave_single');
        formData.append('prompt_id', promptId);
        formData.append('prompt_text', text);

        fetch(window.location.href, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log(`✅ Текст кадра #${promptId} сохранен в БД`);
                textareaElement.style.borderColor = '#28a745'; // Зеленый — успех
                setTimeout(() => textareaElement.style.borderColor = '', 500);
            }
        })
        .catch(err => console.error("Ошибка автосохранения:", err));
    }

    // 1. Автосохранение при смене стиля (работает как раньше)
    if (styleSelect) {
        styleSelect.addEventListener('change', function() {
            const selectedStyle = this.value;
            if (selectedStyle === 'current') return;

            const replacementText = styleReplacements[selectedStyle];
            if (!replacementText) return;

            const activeCheckboxes = document.querySelectorAll('input[type="checkbox"]:checked');
            
            if (activeCheckboxes.length === 0) {
                alert("Выберите кадры чекбоксами, чтобы применить стиль!");
                return;
            }

            activeCheckboxes.forEach(checkbox => {
                const promptId = checkbox.value; 
                const textarea = document.querySelector(`textarea[name="prompt_${promptId}"]`);
                
                if (textarea) {
                    modifyTextarea(textarea, replacementText);
                    saveToDatabase(promptId, textarea.value, textarea);
                }
            });
        });
    }

    // 2. 🔥 БЕЗОПАСНОЕ РУЧНОЕ СОХРАНЕНИЕ
    document.querySelectorAll('textarea[name^="prompt_"]').forEach(textarea => {
        
        // Сохраняем, только когда юзер ЗАКОНЧИЛ редактирование и кликнул в другое место (вышел из поля)
        textarea.addEventListener('blur', function() {
            const promptId = this.name.replace('prompt_', '');
            saveToDatabase(promptId, this.value, this);
        });

        // Или если нажали Enter (удобно для быстрого сохранения)
        textarea.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) { 
                e.preventDefault(); // Чтобы не переносить строку
                this.blur(); // Вызовет событие blur и само сохранит
            }
        });
    });

    function modifyTextarea(textarea, replacementText) {
        let currentText = textarea.value.trim();
        const stylePattern = /^(Cinematic shot, cinematic dark lighting|Cinematic shot|Cinematic low-angle shot|Cinematic|Photorealistic ultra-detailed photo, 8k|Photorealistic|Anime style, Studio Ghibli art, vibrant colors|Anime style|Anime|Artistic oil painting, painterly style, dramatic artistic look|Artistic oil painting|Oil painting|Artistic|Comic book style, graphic novel art, ink contours|Comic book style|Custom style)/i;
        
        if (stylePattern.test(currentText)) {
            textarea.value = currentText.replace(stylePattern, replacementText);
        } else {
            textarea.value = replacementText + ", " + currentText;
        }
        
        textarea.style.transition = 'background-color 0.3s';
        textarea.style.backgroundColor = '#fffdeb';
        setTimeout(() => textarea.style.backgroundColor = '', 500);
    }
});
window.handleManualUpload = function(inputElement) {
    const file = inputElement.files[0];
    if (!file) return;

    // 1. Ищем форму по классу
    let promptId = inputElement.getAttribute('data-prompt-id');
    const form = inputElement.closest('.manual-upload-form');

    // 2. ФОЛБЭК: Если через форму не нашли, ищем по родительскому DIV .custom-upload-image
    if (!promptId || promptId === '') {
        const parentDiv = inputElement.closest('.custom-upload-image');
        if (parentDiv) {
            // На всякий случай заглянем в data-order или попробуем найти другие зацепки
            console.log("Пытаемся достать ID из родительского DIV...");
        }
    }

    // КРИТИЧЕСКАЯ ПРОВЕРКА: Если ID так и остался пустым, стопаем процесс ДО отправки на сервер
    if (!promptId || promptId.trim() === '') {
        console.error("❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось определить ID промпта из HTML-атрибутов!");
        alert("Ошибка интерфейса: Не найден ID кадра. Проверь код HTML-шаблона.");
        return; 
    }

    console.log(`📤 Файл выбран. Начинаем загрузку для кадра #${promptId}...`);

    const formData = new FormData();
    formData.append('action', 'manual_upload');
    formData.append('prompt_id', promptId);
    formData.append('image_file', file);

    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

    fetch(window.location.href, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': csrfToken
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log(`✅ Успешно загружено!`);
            alert("Картинка успешно загружена!");
            location.reload();
        } else {
            alert(`❌ Ошибка: ${data.error}`);
        }
    })
    .catch(err => {
        console.error("Ошибка при отправке:", err);
    });
};