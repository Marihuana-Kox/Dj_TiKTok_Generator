console.log('🔍 image_edit.js загружен');

let generationInterval = null;
let selectedPromptIds = [];

(function() {
    console.log('🔍 Инициализация...');
    
    // Textareas
    const textareas = document.querySelectorAll('textarea.form-control');
    console.log('🔍 Textarea найдено:', textareas.length);
    textareas.forEach(tx => {
        tx.style.height = 'auto';
        tx.style.height = tx.scrollHeight + 'px';
    });

    // Элементы
    const selectAll = document.getElementById('select-all-prompts');
    const checkboxes = document.querySelectorAll('.prompt-checkbox');
    const selectedCount = document.getElementById('selected-count');
    const btnCount = document.getElementById('btn-count');
    const generateBtn = document.getElementById('generate-images-btn');
    const providerSelect = document.getElementById('image-provider-select');

    console.log('🔍 select-all-prompts:', selectAll ? '✅' : '❌');
    console.log('🔍 prompt-checkbox:', checkboxes.length);
    console.log('🔍 generate-images-btn:', generateBtn ? '✅' : '❌');
    console.log('🔍 provider-select:', providerSelect ? '✅' : '❌');

    function updateCount() {
        const checked = Array.from(checkboxes).filter(cb => cb.checked);
        selectedPromptIds = checked.map(cb => cb.value);
        const count = checked.length;
        
        console.log('🔍 updateCount:', count, 'выбрано, IDs:', selectedPromptIds);
        
        if (selectedCount) selectedCount.innerText = `(выбрано: ${count})`;
        if (btnCount) btnCount.innerText = count;
        if (generateBtn) generateBtn.disabled = count === 0 || !providerSelect?.value;
    }

    if (selectAll) {
        selectAll.addEventListener('change', function() {
            console.log('🔍 Клик "Выбрать все"');
            checkboxes.forEach(cb => cb.checked = this.checked);
            updateCount();
        });
    }

    checkboxes.forEach((cb, i) => {
        cb.addEventListener('change', function() {
            console.log('🔍 Клик чекбокс #', i);
            updateCount();
        });
    });

    if (providerSelect) {
        providerSelect.addEventListener('change', function() {
            console.log('🔍 Смена провайдера:', this.value);
            updateCount();
        });
    }

    if (generateBtn) {
        generateBtn.addEventListener('click', function() {
            console.log('🔍 КЛИК ПО КНОПКЕ ГЕНЕРАЦИИ!');
            console.log('🔍 selectedPromptIds:', selectedPromptIds);
            console.log('🔍 provider:', providerSelect?.value);
            openConfirmModal();
        });
    } else {
        console.error('❌ КНОПКА generate-images-btn НЕ НАЙДЕНА!');
    }

    const modalConfirmBtn = document.getElementById('modal-confirm-btn');
    if (modalConfirmBtn) {
        modalConfirmBtn.addEventListener('click', function() {
            console.log('🔍 КЛИК ПО КНОПКЕ ПОДТВЕРЖДЕНИЯ!');
            startGeneration();
        });
    } else {
        console.error('❌ КНОПКА modal-confirm-btn НЕ НАЙДЕНА!');
    }

    console.log('🔍 Инициализация завершена');
})();

function openConfirmModal() {
    console.log('🔍 openConfirmModal вызван');
    console.log('🔍 selectedPromptIds:', selectedPromptIds);
    
    const providerSelect = document.getElementById('image-provider-select');
    const sizeSelect = document.getElementById('image-size-select');
    const styleSelect = document.getElementById('style-preset-select');
    
    // Заполняем данные
    const countEl = document.getElementById('modal-prompt-count');
    const providerEl = document.getElementById('modal-provider');
    const sizeEl = document.getElementById('modal-size');
    const styleEl = document.getElementById('modal-style');
    
    console.log('🔍 Элементы:', { count: !!countEl, provider: !!providerEl, size: !!sizeEl, style: !!styleEl });
    
    if (countEl) countEl.innerText = selectedPromptIds.length;
    if (providerEl) providerEl.innerText = providerSelect?.options[providerSelect.selectedIndex]?.text || '-';
    if (sizeEl) sizeEl.innerText = sizeSelect?.value || '-';
    if (styleEl) styleEl.innerText = styleSelect?.options[styleSelect.selectedIndex]?.text || '-';
    
    // Показываем модалку
    const modal = document.getElementById('generation-confirm-modal');
    if (modal) {
        modal.classList.remove('d-none');
        modal.classList.add('active');
        modal.style.visibility = 'visible';
    }
}

function closeConfirmModal() {
    const modal = document.getElementById('generation-confirm-modal');
    if (modal) modal.classList.add('d-none');
    if (modal) modal.classList.add('active');
    if (modal) modal.style.visibility = 'visible';
}

function openProgressModal() {
    console.log('🔍 openProgressModal вызван');
    const modal = document.getElementById('generation-progress-modal');
    if (modal) modal.classList.remove('d-none');
    if (modal) modal.classList.add('active');
    if (modal) modal.style.visibility = 'visible';
}

function closeProgressModal() {
    const modal = document.getElementById('generation-progress-modal');
    if (modal) modal.classList.add('d-none');
    if (modal) modal.classList.add('active');
    if (modal) modal.style.visibility = 'visible';
    if (generationInterval) { clearInterval(generationInterval); generationInterval = null; }
}

function renderPromptStatusList() {
    const container = document.getElementById('prompt-status-list');
    if (!container) return;
    container.innerHTML = selectedPromptIds.map(id => 
        `<div class="prompt-status-item pending" id="status-prompt-${id}">
            <span>Сцена #${id}</span><span class="status-text">⏳ Ожидание</span>
        </div>`
    ).join('');
}

function updatePromptStatus(promptId, status) {
    const el = document.getElementById(`status-prompt-${promptId}`);
    if (!el) return;
    el.className = `prompt-status-item ${status}`;
    const texts = { pending: '⏳ Ожидание', generating: '🔄 Генерация...', success: '✅ Готово', failed: '❌ Ошибка' };
    el.querySelector('.status-text').innerText = texts[status] || status;
}

function startGeneration() {
    console.log('🔍 startGeneration вызван');
    closeConfirmModal();
    openProgressModal();
    
    const provider = document.getElementById('image-provider-select')?.value;
    const size = document.getElementById('image-size-select')?.value;
    const style = document.getElementById('style-preset-select')?.value;
    
    console.log('🔍 Отправка AJAX:', { provider, size, style, selectedPromptIds });
    
    fetch(window.location.href, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: new URLSearchParams({
            'provider': provider,
            'selected_prompts': selectedPromptIds.join(','),
            'aspect_ratio': size,
            'style_preset': style,
            'start_generation': 'true'
        })
    })
    .then(r => {
        console.log('🔍 Ответ сервера:', r.status);
        return r.json();
    })
    .then(data => {
        console.log('🔍 Данные:', data);
        if (data.success) {
            startProgressPolling(data.task_id);
        } else {
            showToast('❌ ' + data.error, 'error');
            closeProgressModal();
        }
    })
    .catch(err => {
        console.error('🔍 Ошибка:', err);
        showToast('❌ Ошибка соединения', 'error');
        closeProgressModal();
    });
}

function startProgressPolling(taskId) {
    console.log('🔍 startProgressPolling:', taskId);
    generationInterval = setInterval(() => {
        fetch(`/images/api/generation-progress/${taskId}/`)
            .then(r => r.json())
            .then(data => {
                console.log('🔍 Progress:', data);
                if (data.completed) {
                    clearInterval(generationInterval);
                    document.getElementById('total-progress-bar').style.width = '100%';
                    document.getElementById('total-progress-percent').innerText = '100%';
                    document.getElementById('close-progress-btn').disabled = false;
                    showToast('✅ Готово!', 'success');
                    setTimeout(() => location.reload(), 2000);
                } else {
                    const percent = data.total_count > 0 ? Math.round((data.completed_count / data.total_count) * 100) : 0;
                    document.getElementById('total-progress-bar').style.width = percent + '%';
                    document.getElementById('total-progress-percent').innerText = percent + '%';
                    if (data.prompts_status) data.prompts_status.forEach(p => updatePromptStatus(p.id, p.status));
                }
            })
            .catch(err => console.error('Polling error:', err));
    }, 2000);
}

function showToast(message, type = 'success') {
    const toast = document.getElementById('toast-notification');
    if (!toast) { alert(message); return; }
    document.getElementById('toast-icon').innerText = type === 'success' ? '✅' : '❌';
    document.getElementById('toast-message').innerText = message;
    toast.classList.remove('d-none');
    setTimeout(() => toast.classList.add('d-none'), 4000);
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie) {
        for (let c of document.cookie.split(';')) {
            c = c.trim();
            if (c.startsWith(name + '=')) {
                cookieValue = decodeURIComponent(c.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
// ============================================================================
// ЛАЙТБОКС ДЛЯ ИЗОБРАЖЕНИЙ
// ============================================================================
function openLightbox(imageUrl, title) {
    const overlay = document.getElementById('lightbox-overlay');
    const image = document.getElementById('lightbox-image');
    const titleEl = document.getElementById('lightbox-title');
    
    if (overlay && image) {
        image.src = imageUrl;
        titleEl.innerText = title || '';
        overlay.classList.add('active');
        document.body.style.overflow = 'hidden'; // Блокируем скролл
    }
}

function closeLightbox() {
    const overlay = document.getElementById('lightbox-overlay');
    if (overlay) {
        overlay.classList.remove('active');
        document.body.style.overflow = ''; // Возвращаем скролл
    }
}

// Закрытие по Esc
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeLightbox();
    }
});