/**
 * МОДУЛЬ УПРАВЛЕНИЯ РЕНДЕРИНГОМ И АВТОМАТИЧЕСКОГО РАСПРЕДЕЛЕНИЯ КЛИПОВ
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log("🎯 Скрипт видеоредактора успешно инициализирован и готов к работе!");

    const renderButton = document.getElementById('startRenderBtn');
    
    const progressBlock = document.getElementById('progressBlock');
    const progressMessage = document.getElementById('progressMessage');
    const progressPercent = document.getElementById('progressPercent');
    const progressBar = document.getElementById('progressBar');
    
    const videoPlayer = document.getElementById('videoPlayer');
    const emptyMonitorState = document.getElementById('emptyMonitorState');
    const downloadVideoBtn = document.getElementById('downloadVideoBtn');
    const videoResultBlock = document.getElementById('videoResultBlock');

    // Находим CSRF-токен
    let csrfToken = '';
    const csrfTokenNode = document.querySelector('[name=csrfmiddlewaretoken]');
    if (csrfTokenNode) {
        csrfToken = csrfTokenNode.value;
    } else {
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        if (match) csrfToken = match[1];
    }

    let checkProgressInterval = null;

    // Автоматически распределяем изображения по длине аудио при загрузке страницы
    renderFlexibleTimeline();

    // Функция запуска рендеринга / пересборки
    async function initVideoRender(e) {
        if (e) {
            e.preventDefault(); 
            e.stopPropagation(); 
        }
        
        console.log("🚀 Клик по кнопке #startRenderBtn зафиксирован! Запуск...");
        
        const mainPlayer = document.getElementById('main-editor-player');
        if (mainPlayer) {
            mainPlayer.pause();
            mainPlayer.src = "";
            mainPlayer.load();
            mainPlayer.style.display = 'none';
            mainPlayer.classList.add('hidden');
        }
        if (videoPlayer) {
            videoPlayer.pause();
            videoPlayer.src = "";
            videoPlayer.load();
            videoPlayer.style.display = 'none';
            videoPlayer.classList.add('hidden');
        }

        if (renderButton) {
            renderButton.disabled = true;
            renderButton.style.display = 'none';
            renderButton.classList.add('hidden');
        }
        if (downloadVideoBtn) {
            downloadVideoBtn.style.display = 'none';
            downloadVideoBtn.classList.add('hidden');
        }

        if (progressBlock) {
            progressBlock.classList.remove('hidden');
            progressBlock.style.setProperty('display', 'block', 'important');
            progressBlock.style.display = 'block';
        }
        if (progressBar) progressBar.style.width = '5%';
        if (progressPercent) progressPercent.innerText = '5%';
        if (progressMessage) progressMessage.innerText = '🎬 Инициализация MoviePy и очистка диска...';
        
        if (emptyMonitorState) {
            emptyMonitorState.classList.remove('hidden');
            emptyMonitorState.style.display = 'block';
        }
        if (videoResultBlock) {
            videoResultBlock.classList.add('hidden');
            videoResultBlock.style.display = 'none';
        }

        const finalTimelinePayload = [];

        if (window.timelineState) {
            Object.keys(window.timelineState).forEach(order => {
                const sceneData = window.timelineState[order];
                
                let imageFilename = "";
                const clipEl = document.querySelector(`.capcut-clip[data-type="video"][data-order="${order}"]`);
                if (clipEl) {
                    const imgEl = clipEl.querySelector('img');
                    if (imgEl) {
                        const src = imgEl.src;
                        imageFilename = src.substring(src.lastIndexOf('/') + 1);
                    }
                }

                finalTimelinePayload.push({
                    "order": parseInt(order),
                    "meta_settings": {
                        "image_name": imageFilename,
                        "duration": parseFloat(sceneData.duration) || 5.0,
                        "video_effects": sceneData.video_effects || 'none',
                        "filter": sceneData.filter || 'none',
                        "transition": sceneData.transition || 'none',
                        "mirror_x": sceneData.mirror_x || false,
                        "mirror_y": sceneData.mirror_y || false,
                        "text_overlay": {
                            "text": sceneData.text_overlay?.text || '',
                            "font": sceneData.text_overlay?.font || 'Arial',
                            "font_color": sceneData.text_overlay?.font_color || '#FFFFFF',
                            "position": sceneData.text_overlay?.position || 'bottom'
                        },
                        "audio_effects": {
                            "volume": parseInt(sceneData.audio_effects?.volume || 100),
                            "fade_in": parseFloat(sceneData.audio_effects?.fade_in || 0.0),
                            "fade_out": parseFloat(sceneData.audio_effects?.fade_out || 0.0)
                        }
                    }
                });
            });
        }

        try {
            let response = await fetch(window.location.href, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ 
                    action: 'start_render',
                    timeline: finalTimelinePayload
                })
            });

            let data = await response.json();
            console.log("Ответ сервера на старт:", data);
            
            if ((data.success || data.status === 'success') && data.task_id) {
                startPolling(data.task_id);
            } else {
                alert('Ошибка запуска: ' + (data.error || data.message || 'Неизвестная ошибка сервера.'));
                resetButtons();
            }
        } catch (err) {
            console.error('💥 Критическая ошибка POST:', err);
            resetButtons();
        }
    }

    if (renderButton) {
        renderButton.addEventListener('click', initVideoRender);
    } else {
        console.error("❌ ВНИМАНИЕ: Кнопка с id='startRenderBtn' не найдена в HTML!");
    }

    function startPolling(taskId) {
        console.log(`⏱️ Включаем цикличный опрос сервера для Task ID: ${taskId}`);
        checkProgressInterval = setInterval(async () => {
            try {
                let response = await fetch(`${window.location.href}?task_id=${taskId}`, {
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                });
                let data = await response.json();
                console.log("📊 Ответ сервера (GET статус):", data);

                if (data.percent !== undefined) {
                    if (progressBar) progressBar.style.width = data.percent + '%';
                    if (progressPercent) progressPercent.innerText = data.percent + '%';
                }
                if (data.message && progressMessage) {
                    progressMessage.innerText = data.message;
                }

                if (data.status === 'error') {
                    clearInterval(checkProgressInterval);
                    alert('Ошибка рендеринга: ' + data.message);
                    resetButtons();
                }

                const isFinished = data.status === 'done' || 
                                   data.status === 'success' || 
                                   data.completed === true ||
                                   (data.percent === 100 && data.video_url);

                if (isFinished) {
                    clearInterval(checkProgressInterval);
                    console.log("🎉 Видео полностью собрано на сервере! Запрашиваем готовый плеер...");

                    if (progressBlock) progressBlock.style.display = 'none';
                    if (emptyMonitorState) emptyMonitorState.style.display = 'none';

                    fetch(window.location.href)
                        .then(response => response.text())
                        .then(html => {
                            const parser = new DOMParser();
                            const doc = parser.parseFromString(html, 'text/html');

                            const newPlayer = doc.getElementById('main-editor-player');
                            const oldPlayer = document.getElementById('main-editor-player');

                            if (newPlayer && oldPlayer) {
                                console.log("📺 Найдено готовое видео! Перезагружаем DOM-элемент плеера...");
                                
                                oldPlayer.outerHTML = newPlayer.outerHTML;

                                const reloadedPlayer = document.getElementById('main-editor-player');
                                if (reloadedPlayer) {
                                    reloadedPlayer.classList.remove('hidden');
                                    reloadedPlayer.style.display = 'block';
                                    
                                    const currentSrc = reloadedPlayer.src || reloadedPlayer.querySelector('source')?.src;
                                    if (currentSrc) {
                                        const freshUrl = currentSrc.split('?')[0] + '?t=' + new Date().getTime();
                                        reloadedPlayer.src = freshUrl;
                                    }
                                    
                                    reloadedPlayer.load();
                                    reloadedPlayer.play().catch(e => {
                                        console.log("▶️ Автоплей заблокирован браузером, видео готово к просмотру по клику.");
                                    });
                                }
                            } else {
                                console.warn("⚠️ Не удалось найти плеер в ответе сервера. Перезагружаем страницу целиком...");
                                window.location.reload();
                            }

                            if (downloadVideoBtn) {
                                const currentProjectId = window.location.pathname.split('/')[3];
                                downloadVideoBtn.setAttribute('href', `/video/project/${currentProjectId}/download/`);
                                downloadVideoBtn.setAttribute('download', `project_${currentProjectId}.mp4`);
                                downloadVideoBtn.classList.remove('hidden');
                                downloadVideoBtn.style.display = 'inline-flex';
                                downloadVideoBtn.onclick = null;
                            }

                            if (renderButton) {
                                renderButton.disabled = false;
                                renderButton.className = 'capcut-btn-secondary';
                                renderButton.innerHTML = '🔄 Пересобрать заново';
                                renderButton.classList.remove('hidden');
                                renderButton.style.display = 'inline-flex';
                            }
                        })
                        .catch(err => {
                            console.error("💥 Ошибка AJAX запроса плеера:", err);
                            window.location.reload();
                        });
                }
            } catch (err) {
                console.error('❌ Ошибка при опросе прогресса:', err);
            }
        }, 1500);
    }

    function resetButtons() {
        if (renderButton) {
            renderButton.disabled = false; 
            renderButton.style.display = 'inline-flex';
            renderButton.classList.remove('hidden');
        }
        if (progressBlock) progressBlock.style.display = 'none';
    }
});

function renderFlexibleTimeline() {
    const pixelsPerSecond = 6; 
    const bufferSeconds = 10;
    
    const timebar = document.getElementById('dynamic-timebar');
    if (!timebar) return;

    const videoClips = document.querySelectorAll('.capcut-clip[data-type="video"]');
    const audioClips = document.querySelectorAll('.capcut-clip[data-type="audio"]');

    const audioDisplay = document.getElementById('total-audio-display');
    const videoDisplay = document.getElementById('total-video-display');

    let totalAudioDuration = 0;
    audioClips.forEach(clip => {
        // Заменяем запятую на точку, чтобы JavaScript прочитал сотые доли секунд
        let rawDuration = (clip.getAttribute('data-duration') || "0").replace(',', '.');
        totalAudioDuration += parseFloat(rawDuration) || 0;
    });

    console.log(totalAudioDuration)

    if (totalAudioDuration === 0) totalAudioDuration = 30; 
    if (audioDisplay) audioDisplay.innerText = totalAudioDuration.toFixed(2);

    let totalVideoDuration = 0;
    const autoAlignCheckbox = document.getElementById('auto-align-audio');

    // ================================================================
    // РЕЖИМ А: Свободный (Ручной) режим — берем честную сумму data-duration
    // ================================================================
    if (autoAlignCheckbox && !autoAlignCheckbox.checked) {
        
        videoClips.forEach(clip => {
            const order = parseInt(clip.getAttribute('data-order'));
            
            let baseDuration = 5.0;
            if (window.timelineState && window.timelineState[order]) {
                baseDuration = parseFloat(window.timelineState[order].duration) || parseFloat(clip.getAttribute('data-duration')) || 5.0;
            } else {
                baseDuration = parseFloat(clip.getAttribute('data-duration')) || 5.0;
            }

            if (window.timelineState && window.timelineState[order] && window.timelineState[order].user_duration !== undefined) {
                baseDuration = parseFloat(window.timelineState[order].user_duration);
            }

            let finalClipDuration = baseDuration;

            if (window.timelineState && window.timelineState[order]) {
                window.timelineState[order].user_duration = baseDuration; 
                window.timelineState[order].duration = finalClipDuration;
            }

            clip.style.width = (finalClipDuration * pixelsPerSecond) + 'px';
            
            // 🔥 ЧЕСТНОЕ СЛОЖЕНИЕ: Прибавляем реальную длину кадра к общему хронометражу
            totalVideoDuration += finalClipDuration; 
            
            if (typeof window.updateBadgesVisibility === 'function') {
                window.updateBadgesVisibility(order);
            }
        });

    // ================================================================
    // РЕЖИМ Б: Автоматический подгон под звук (Магнит)
    // ================================================================
    } else {
        if (videoClips.length > 0) {
            const baseDurationPerImage = totalAudioDuration / videoClips.length;

            videoClips.forEach(clip => {
                const order = parseInt(clip.getAttribute('data-order'));
                let finalClipDuration = baseDurationPerImage;

                if (window.timelineState && window.timelineState[order]) {
                    window.timelineState[order].duration = parseFloat(finalClipDuration.toFixed(2));
                }

                clip.setAttribute('data-duration', finalClipDuration.toFixed(2));
                clip.style.width = (finalClipDuration * pixelsPerSecond) + 'px';
                
                if (typeof window.updateBadgesVisibility === 'function') {
                    window.updateBadgesVisibility(order);
                }
            });
            
            totalVideoDuration = totalAudioDuration;
        }
    }

    if (totalVideoDuration < 0) totalVideoDuration = 0;
    if (videoDisplay) videoDisplay.innerText = totalVideoDuration.toFixed(2);

    const maxDuration = Math.max(totalAudioDuration, totalVideoDuration);
    drawTimelineTicks(maxDuration, 10, pixelsPerSecond, timebar);
}

function drawTimelineTicks(duration, buffer, pixelsPerSecond, timebar) {
    const scaleTotalSeconds = Math.ceil(duration + buffer);
    timebar.innerHTML = '';

    for (let s = 0; s <= scaleTotalSeconds; s++) {
        const tick = document.createElement('div');
        tick.className = 'time-tick';
        tick.style.width = pixelsPerSecond + 'px';

        if (s % 5 === 0) {
            tick.classList.add('major');
            tick.innerHTML = `<span>${s}s</span>`;
        } else {
            tick.innerHTML = ``;
        }
        timebar.appendChild(tick);
    }
}

window.renderFlexibleTimeline = renderFlexibleTimeline;

document.addEventListener('DOMContentLoaded', () => {
    const autoAlignCheckbox = document.getElementById('auto-align-audio');
    
    if (autoAlignCheckbox) {
        autoAlignCheckbox.addEventListener('change', () => {
            window.renderFlexibleTimeline();
        });
    }

    document.addEventListener('input', (e) => {
        if (e.target.classList.contains('scene-duration-input') || e.target.id === 'clipDurationInput') {
            let order = e.target.closest('[data-order]')?.getAttribute('data-order');
            if (!order && window.getSelectedOrders) {
                const selected = window.getSelectedOrders();
                if (selected.length > 0) order = selected[selected.length - 1];
            }
            
            if (order && window.timelineState && window.timelineState[order]) {
                window.timelineState[order].duration = parseFloat(e.target.value) || 0;
                window.timelineState[order].user_duration = parseFloat(e.target.value) || 0;
            }

            if (autoAlignCheckbox && autoAlignCheckbox.checked) {
                autoAlignCheckbox.checked = false;
                console.log("📌 Автоподгон отключен из-за ручного изменения секунд кадра.");
            }
            
            window.renderFlexibleTimeline();
        }
    });

    document.addEventListener('change', (e) => {
        if (e.target.classList.contains('scene-transition-select') || e.target.id === 'clipTransitionType') {
            let order = e.target.closest('[data-order]')?.getAttribute('data-order');
            if (!order && window.getSelectedOrders) {
                const selected = window.getSelectedOrders();
                if (selected.length > 0) order = selected[selected.length - 1];
            }
            
            if (order && window.timelineState && window.timelineState[order]) {
                window.timelineState[order].transition = e.target.value;
            }

            window.renderFlexibleTimeline();
        }
    });
});

window.updateTimelineAfterDOMChange = function() {
    console.log("🧩 DOM таймлайна изменился. Выполняем пересчет...");
    if (typeof window.renderFlexibleTimeline === 'function') {
        window.renderFlexibleTimeline();
    }
};