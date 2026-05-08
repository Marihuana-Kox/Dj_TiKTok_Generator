// ============================================================================
// IMAGE EDIT — редактирование, чекбоксы, генерация картинок
// Страница: /images/*/edit/
// ============================================================================

let generationInterval = null;
let selectedPromptIds = [];

(function() {
    console.log('🔍 image_edit.js инициализация...');

    // Textareas
    document.querySelectorAll('textarea.form-control').forEach(tx => {
        tx.style.height = 'auto';
        tx.style.height = tx.scrollHeight + 'px';
        tx.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = this.scrollHeight + 'px';
        });
    });

    // Элементы
    const selectAll = document.getElementById('select-all-prompts');
    const checkboxes = document.querySelectorAll('.prompt-checkbox');
    const selectedCount = document.getElementById('selected-count');
    const btnCount = document.getElementById('btn-count');
    const generateBtn = document.getElementById('generate-images-btn');
    const providerSelect = document.getElementById('image-provider-select');

    function updateCount() {
        const checked = Array.from(checkboxes).filter(cb => cb.checked);
        selectedPromptIds = checked.map(cb => cb.value);
        const count = checked.length;
        
        if (selectedCount) selectedCount.innerText = `(выбрано: ${count})`;
        if (btnCount) btnCount.innerText = count;
        if (generateBtn) generateBtn.disabled = count === 0 || !providerSelect?.value;
    }

    if (selectAll) {
        selectAll.addEventListener('change', function() {
            checkboxes.forEach(cb => cb.checked = this.checked);
            updateCount();
        });
    }

    checkboxes.forEach(cb => cb.addEventListener('change', updateCount));
    if (providerSelect) providerSelect.addEventListener('change', updateCount);
    if (generateBtn) generateBtn.addEventListener('click', openConfirmModal);

    const modalConfirmBtn = document.getElementById('modal-confirm-btn');
    if (modalConfirmBtn) {
        modalConfirmBtn.addEventListener('click', function() {
            startGeneration();
        });
    }

    console.log('🔍 image_edit.js готов');
})();

// ============================================================================
// МОДАЛКА ПОДТВЕРЖДЕНИЯ (вызывает глобальную openModal)
// ============================================================================

function openConfirmModal() {
    const providerSelect = document.getElementById('image-provider-select');
    const sizeSelect = document.getElementById('image-size-select');
    const styleSelect = document.getElementById('style-preset-select');
    
    const countEl = document.getElementById('modal-prompt-count');
    const providerEl = document.getElementById('modal-provider');
    const sizeEl = document.getElementById('modal-size');
    const styleEl = document.getElementById('modal-style');
    
    if (countEl) countEl.innerText = selectedPromptIds.length;
    if (providerEl) providerEl.innerText = providerSelect?.options[providerSelect.selectedIndex]?.text || '-';
    if (sizeEl) sizeEl.innerText = sizeSelect?.value || '-';
    if (styleEl) styleEl.innerText = styleSelect?.options[styleSelect.selectedIndex]?.text || '-';
    
    openModal('global-progress-modal');
}

// ============================================================================
// ГЕНЕРАЦИЯ
// ============================================================================

function startGeneration() {
    const provider = document.getElementById('image-provider-select')?.value;
    const size = document.getElementById('image-size-select')?.value;
    const style = document.getElementById('style-preset-select')?.value;
    
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
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            startProgressPolling(data.task_id);
        } else {
            showToast('❌ ' + data.error, 'error');
            closeModal('global-progress-modal');
        }
    })
    .catch(err => {
        console.error('Ошибка:', err);
        showToast('❌ Ошибка соединения', 'error');
        closeModal('global-progress-modal');
    });
}

function startProgressPolling(taskId) {
    generationInterval = setInterval(() => {
        fetch(`/images/api/generation-progress/${taskId}/`)
            .then(r => r.json())
            .then(data => {
                if (data.completed) {
                    clearInterval(generationInterval);
                    finishProgress(true, '✅ Готово!', null, 2000);
                } else {
                    const percent = data.total_count > 0 ? Math.round((data.completed_count / data.total_count) * 100) : 0;
                    updateProgress(percent, `Сгенерировано ${data.completed_count} из ${data.total_count}`);
                }
            })
            .catch(err => console.error('Polling error:', err));
    }, 2000);
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
        if (titleEl) titleEl.innerText = title || '';
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

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closeLightbox();
});