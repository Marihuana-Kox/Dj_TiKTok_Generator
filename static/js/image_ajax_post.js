(function() {
    const form = document.querySelector('#project-create-form');
    const submitBtn = form?.querySelector('button[type="submit"]');
    const modal = document.getElementById('generation-modal');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const statusText = document.getElementById('status-text');

    if (form && submitBtn) {
        const actionUrl = form.dataset.actionUrl || '/images/create/';
        
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            submitBtn.disabled = true;
            submitBtn.innerHTML = '⏳ Генерация...';
            
            const formData = new FormData(form);
            
            fetch(actionUrl, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': formData.get('csrfmiddlewaretoken')
                },
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showProgressModal(data);
                } else {
                    alert('❌ Ошибка: ' + data.error);
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '🚀 Создать проект';
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('❌ Ошибка соединения');
                submitBtn.disabled = false;
                submitBtn.innerHTML = '🚀 Создать проект';
            });
        });
    }

    function showProgressModal(data) {
        if (!modal) return;
        modal.classList.remove('d-none');
        setTimeout(() => modal.classList.add('active'), 100);
        simulateProgress(data.redirect_url);
    }

    function simulateProgress(redirectUrl) {
        let width = 0;
        const interval = setInterval(() => {
            if (width >= 100) {
                clearInterval(interval);
                setTimeout(() => {
                    window.location.href = redirectUrl;
                }, 500);
            } else {
                width += Math.floor(Math.random() * 8) + 2;
                if (width > 100) width = 100;
                if (progressBar) progressBar.style.width = width + '%';
                if (progressText) progressText.innerText = width + '%';
                if (statusText) {
                    if (width < 30) statusText.innerText = "Анализ текста...";
                    else if (width < 60) statusText.innerText = "Генерация промптов...";
                    else if (width < 90) statusText.innerText = "Применение стиля...";
                    else statusText.innerText = "Финализация...";
                }
            }
        }, 150);
    }
})();