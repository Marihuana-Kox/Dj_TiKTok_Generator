// ============================================================================
// IMAGE EDIT — финальная рабочая версия
// ============================================================================

let selectedPromptIds = [];

// Выносим функции в глобальную область, чтобы модалка их видела
window.openConfirmModal = function(e) {
    if (e) e.preventDefault(); 

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
        if (typeof window.startProgressTracking === 'function') {
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
                                
                                // 🔑 Используем КЛАСС вместо ID. Замени '.gallery-block' на свой реальный класс контейнера
                                const newBlocks = doc.querySelectorAll('.thumbnail-empty');
                                const currentBlocks = document.querySelectorAll('.thumbnail-empty');
                                
                                if (newBlocks.length > 0 && currentBlocks.length === newBlocks.length) {
                                    currentBlocks.forEach((block, i) => {
                                        block.innerHTML = newBlocks[i].innerHTML;
                                    });
                                    
                                    // Перепривязка лайтбокса ко всем новым изображениям
                                    document.querySelectorAll('.thumbnail-empty img, .thumbnail-empty a[data-lightbox]').forEach(el => {
                                        el.addEventListener('click', function(e) {
                                            e.preventDefault();
                                            openLightbox(this.src || this.getAttribute('href'), this.alt || '');
                                        });
                                    });
                                } else {
                                    // Если структура изменилась (добавились/удалились блоки) → безопасный reload
                                    window.location.reload();
                                }
                            })
                            .catch(() => window.location.reload());
                    }
                }
            );
        } else {
            console.error('❌ Ошибка: ' + (data.error || 'Неизвестная ошибка'));
            if (typeof closeModal === 'function') closeModal('progress-modal');
        }
    })
    .catch(err => {
        console.error('Fetch error:', err);
        // alert('❌ Ошибка связи с сервером');
        if (typeof closeModal === 'function') closeModal('progress-modal');
    });
}

// Инициализация (DOMContentLoaded и остальное без изменений)
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
        const checked = Array.from(checkboxes).filter(cb => cb.checked);
        selectedPromptIds = checked.map(cb => cb.value);
        const count = checked.length;
        const countDisplay = document.getElementById('selected-count');
        const btnCountDisplay = document.getElementById('btn-count');
        if (countDisplay) countDisplay.innerText = `(выбрано: ${count})`;
        if (btnCountDisplay) btnCountDisplay.innerText = count;
        if (generateBtn) generateBtn.disabled = count === 0 || !providerSelect?.value;
    }

    if (selectAll) selectAll.addEventListener('change', function() {
        checkboxes.forEach(cb => cb.checked = this.checked);
        updateCount();
    });

    checkboxes.forEach(cb => cb.addEventListener('change', updateCount));
    if (providerSelect) providerSelect.addEventListener('change', updateCount);
    if (generateBtn) generateBtn.addEventListener('click', window.openConfirmModal);
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