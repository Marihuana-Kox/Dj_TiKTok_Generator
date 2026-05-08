// ============================================================================
// IMAGE CREATE — форма создания проекта
// Страница: /images/create/
// ============================================================================

(function() {
    console.log('🔍 image_create.js инициализация...');

    const form = document.querySelector('#project-create-form');
    const submitBtn = form?.querySelector('button[type="submit"]');

    if (!form || !submitBtn) {
        console.log('⚠️ Форма не найдена, image_create.js не активен');
        return;
    }

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        submitBtn.disabled = true;
        submitBtn.innerHTML = '⏳ Генерация...';
        
        const formData = new FormData(form);
        const actionUrl = form.dataset.actionUrl || '/images/create/';
        
        fetch(actionUrl, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCookie('csrfmiddlewaretoken')
            },
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                openModal('global-progress-modal');
                updateProgress(0, 'Инициализация...');
                simulateProgress(data.redirect_url);
            } else {
                showToast('❌ ' + data.error, 'error');
                submitBtn.disabled = false;
                submitBtn.innerHTML = '🚀 Создать проект';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showToast('❌ Ошибка соединения', 'error');
            submitBtn.disabled = false;
            submitBtn.innerHTML = '🚀 Создать проект';
        });
    });

    function simulateProgress(redirectUrl) {
        let width = 0;
        const interval = setInterval(() => {
            if (width >= 100) {
                clearInterval(interval);
                finishProgress(true, '✅ Готово!', redirectUrl, 500);
            } else {
                width += Math.floor(Math.random() * 8) + 2;
                if (width > 100) width = 100;
                updateProgress(width, 'Генерация...');
            }
        }, 150);
    }

    console.log('✅ image_create.js готов');
})();