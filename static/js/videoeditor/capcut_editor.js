/**
 * МОДУЛЬ ИНТЕРАКТИВНОГО ТАЙМЛАЙНА И ИНСПЕКТОРА
 * Управляет таймлайном, мультивыбором, инспекторами настроек.
 */

// Глобальное состояние таймлайна
window.timelineState = {};
let selectedOrders = []; // Массив для множественного выделения клипов
const pixelsPerSecond = 6; // 1 секунда времени = 6 пикселей ширины
let timelineHistoryStack = [];

// Функции-мосты для работы с выделением из внешних модулей
window.getSelectedOrders = () => selectedOrders;
window.setSelectedOrders = (newOrders) => { selectedOrders = newOrders; };

document.addEventListener('DOMContentLoaded', () => {
    // 1. Оживляем вкладки библиотеки ресурсов (Картинки / Аудио)
    setupTabs('.resource-tab-btn', '.resource-pool-pane', 'data-resource');

    // 2. Инициализируем структуру стейта и бейджи на таймлайне
    initTimelineState();
    
    // 3. Навешиваем все события на инпуты панели и клики по таймлайну
    setupDOMEventListeners();

    // 4. Инициализируем Drag and Drop (если внешний файл подключен)
    if (typeof window.initDragAndDrop === 'function') {
        window.initDragAndDrop();
    }

    const tabPlayButtons = document.querySelectorAll('.audio-tab-play-btn');

    tabPlayButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation(); // Исключаем ложные срабатывания на таймлайне

            const card = btn.closest('.audio-asset-card');
            const internalAudio = card.querySelector('.tab-internal-player');
            const iconSpan = btn.querySelector('.play-icon');

            // 1. Если этот файл уже играет — ставим его на паузу
            if (!internalAudio.paused) {
                internalAudio.pause();
                btn.classList.remove('playing');
                iconSpan.innerText = '▶';
            } else {
                // 2. Если запускаем новый — тушим ВСЕ остальные аудио во вкладке
                document.querySelectorAll('.tab-internal-player').forEach(audio => {
                    audio.pause();
                    audio.currentTime = 0;
                });
                document.querySelectorAll('.audio-tab-play-btn').forEach(button => {
                    button.classList.remove('playing');
                    const icon = button.querySelector('.play-icon');
                    if (icon) icon.innerText = '▶';
                });

                // 3. Ставим на паузу главные плееры редактора, чтобы звуки не накладывались
                const globalPlayer = document.getElementById('global-timeline-player');
                if (globalPlayer) globalPlayer.pause();
                
                const mainEditorPlayer = document.getElementById('main-editor-player');
                if (mainEditorPlayer) mainEditorPlayer.pause();
                
                const videoPlayer = document.getElementById('videoPlayer');
                if (videoPlayer) videoPlayer.pause();

                // 4. Включаем текущий файл
                internalAudio.play().then(() => {
                    btn.classList.add('playing');
                    iconSpan.innerText = '⏸';
                }).catch(err => {
                    console.error("Ошибка воспроизведения аудио в карточке:", err);
                });
            }

            // Автоматический сброс кнопки, когда аудиозапись доиграет до конца
            internalAudio.onended = () => {
                btn.classList.remove('playing');
                iconSpan.innerText = '▶';
            };
        });
    });
    // 5. Инициализация аудио-плеера для предпрослушки треков таймлайна
    initAudioPlayer();
    syncResourceBarButtons();
});

// --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ИНИЦИАЛИЗАЦИИ ---

function setupTabs(triggerSelector, paneSelector, dataAttr) {
    const triggers = document.querySelectorAll(triggerSelector);
    const panes = document.querySelectorAll(paneSelector);

    triggers.forEach(btn => {
        btn.addEventListener('click', function() {
            triggers.forEach(t => t.classList.remove('active'));
            panes.forEach(p => p.classList.remove('active'));

            this.classList.add('active');
            const targetId = this.getAttribute(dataAttr);
            const targetPane = document.getElementById(targetId);
            if (targetPane) targetPane.classList.add('active');
        });
    });
}

function initTimelineState() {
    document.querySelectorAll('.capcut-clip[data-type="video"]').forEach(clip => {
        const order = parseInt(clip.getAttribute('data-order'));
        const duration = parseFloat(clip.getAttribute('data-duration')) || 5.0;

        if (!clip.querySelector('.clip-fx-status-bar')) {
            const statusBar = document.createElement('div');
            statusBar.className = 'clip-fx-status-bar';
            statusBar.innerHTML = `
                <span class="fx-badge badge-anim">FX</span>
                <span class="fx-badge badge-filter">🎨</span>
                <span class="fx-badge badge-trans">🔀</span>
                <span class="fx-badge badge-text">📝</span>
                <span class="fx-badge badge-mirror-x" style="display:none; color:#00bcd4;">↔</span>
                <span class="fx-badge badge-mirror-y" style="display:none; color:#00bcd4;">↕</span>
            `;
            clip.appendChild(statusBar);
        }

        window.timelineState[order] = {
            duration: duration,
            user_duration: duration, // Запоминаем стартовую пользовательскую длину
            video_effects: clip.getAttribute('data-effect') || "none",
            filter: clip.getAttribute('data-filter') || "none",
            transition: clip.getAttribute('data-transition') || "none",
            mirror_x: clip.getAttribute('data-mirror-x') === 'true',
            mirror_y: clip.getAttribute('data-mirror-y') === 'true',
            text_overlay: { 
                text: clip.getAttribute('data-text') || "", 
                font: clip.getAttribute('data-font') || "Arial", 
                font_size: 30, 
                font_color: clip.getAttribute('data-font-color') || "#FFFFFF", 
                position: clip.getAttribute('data-position') || "bottom" 
            },
            audio_effects: { 
                volume: parseInt(clip.getAttribute('data-volume')) || 100, 
                fade_in: parseFloat(clip.getAttribute('data-fade-in')) || 0, 
                fade_out: parseFloat(clip.getAttribute('data-fade-out')) || 0 
            }
        };
    });
    
    refreshTimelineLayout();
    if (typeof window.updateTimelineAfterDOMChange === 'function') {
        window.updateTimelineAfterDOMChange();
    }
}

function setupDOMEventListeners() {
    setupTabs('.tab-trigger-btn', '.tab-content-pane', 'data-target');
    
    const previewImage = document.getElementById('monitor-preview-image');
    const emptyState = document.getElementById('emptyMonitorState');
    const btnDuplicate = document.getElementById('clipDuplicateBtn');
    const videoTrack = document.querySelector('.timeline-track.video-track');

    if (btnDuplicate) {
        btnDuplicate.addEventListener('click', (e) => {
            e.stopPropagation();
            if (selectedOrders.length === 0) {
                alert("Сначала выберите кадр на таймлайне для дублирования!");
                return;
            }
            saveTimelineSnapshot();

            const sourceOrder = selectedOrders[selectedOrders.length - 1];
            const sourceClip = document.querySelector(`.capcut-clip[data-type="video"][data-order="${sourceOrder}"]`);
            const sourceConfig = window.timelineState[sourceOrder];

            if (sourceClip && sourceConfig && videoTrack) {
                const targetOrder = sourceOrder + 1; // Новый кадр должен стать следующим

                // 1. Раздвигаем window.timelineState, освобождая место для targetOrder
                const newTimelineState = {};
                Object.keys(window.timelineState).forEach(orderKey => {
                    const currentOrder = parseInt(orderKey);
                    if (currentOrder <= sourceOrder) {
                        newTimelineState[currentOrder] = window.timelineState[currentOrder];
                    } else {
                        newTimelineState[currentOrder + 1] = window.timelineState[currentOrder];
                    }
                });

                // 2. Клонируем конфигурацию родителя в освободившуюся ячейку
                newTimelineState[targetOrder] = {
                    duration: sourceConfig.duration,
                    user_duration: sourceConfig.user_duration || sourceConfig.duration,
                    video_effects: sourceConfig.video_effects,
                    filter: sourceConfig.filter,
                    transition: sourceConfig.transition,
                    mirror_x: sourceConfig.mirror_x,
                    mirror_y: sourceConfig.mirror_y,
                    text_overlay: { ...sourceConfig.text_overlay },
                    audio_effects: { ...sourceConfig.audio_effects }
                };
                
                // Перезаписываем глобальный стейт раздвинутыми данными
                window.timelineState = newTimelineState;

                // 3. Клонируем сам DOM-элемент кадра
                const duplicatedClip = sourceClip.cloneNode(true);
                duplicatedClip.classList.remove('active', 'selected-active');

                // Навешиваем клик на новый клон
                duplicatedClip.addEventListener('click', (e) => {
                    e.stopPropagation();
                    handleClipClick(duplicatedClip);
                });

                // ВСТАВЛЯЕМ СТРОГО СПРАВА ОТ РОДИТЕЛЯ (afterend)
                sourceClip.insertAdjacentElement('afterend', duplicatedClip);

                // 4. Пересчет порядка и верстки
                window.updateStateOrderFromDOM(); 
                refreshTimelineLayout();
                
                if (typeof window.updateTimelineAfterDOMChange === 'function') {
                    window.updateTimelineAfterDOMChange();
                }
                
                duplicatedClip.click();
            }
        });
    }

    const btnDelete = document.getElementById('clipDeleteBtn');
    if (btnDelete) {
        btnDelete.addEventListener('click', (e) => {
            e.stopPropagation();
            if (selectedOrders.length === 0) {
                alert("Выберите кадр для удаления!");
                return;
            }

            // 1. Снимок для истории (чтобы работало Ctrl+Z)
            saveTimelineSnapshot();

            // 2. Удаление из конфига и DOM
            selectedOrders.forEach(order => {
                const clipEl = document.querySelector(`.capcut-clip[data-type="video"][data-order="${order}"]`);
                
                if (window.timelineState[order]) {
                    delete window.timelineState[order]; // Удаляем из нашего JSON-стейта
                }
                if (clipEl) {
                    clipEl.remove(); // Удаляем с экрана
                }
            });

            selectedOrders = [];
            
            // 3. Обновление интерфейса
            refreshTimelineLayout();
            if (typeof window.updateTimelineAfterDOMChange === 'function') {
                window.updateTimelineAfterDOMChange();
            }
            syncResourceBarButtons();

            // 4. САМОЕ ГЛАВНОЕ: Отправка изменений на сервер!
            // Если у тебя в проекте есть функция сохранения проекта (обычно называется saveProjectState или sendStateToServer)
            // вызови её именно здесь:
            if (typeof window.saveProjectState === 'function') {
                window.saveProjectState(); 
            } else {
                console.warn("Функция сохранения на сервер не найдена! Проверь, как у тебя отправляется JSON.");
            }
        });
    }

    const btnUndo = document.getElementById('clipUndoBtn');
    if (btnUndo) {
        btnUndo.addEventListener('click', (e) => {
            e.stopPropagation();
            if (timelineHistoryStack.length === 0) {
                alert("Нет действий для отмены!");
                return;
            }

            const lastSnapshot = timelineHistoryStack.pop();
            window.timelineState = lastSnapshot.state;

            if (videoTrack) {
                videoTrack.innerHTML = lastSnapshot.html;
            }

            selectedOrders = lastSnapshot.selected;

            // document.querySelectorAll('.capcut-clip[data-type="video"]').forEach(clip => {
            //     const newClip = clip.cloneNode(true);
            //     clip.parentNode.replaceChild(newClip, clip);

            //     newClip.addEventListener('click', (e) => {
            //         e.stopPropagation();
            //         handleClipClick(newClip);
            //     });
            // });
            // =========================================================================
// ЕДИНАЯ ФУНКЦИЯ ДЛЯ НАВЕШИВАНИЯ СОБЫТИЙ НА ОДИН КОНКРЕТНЫЙ КАДР
// =========================================================================
            window.attachClipEvents = function(clip) {
                if (!clip) return;

                // Очищаем старый обработчик, если он вдруг был (защита от дублирования)
                clip.onclick = null; 

                // Основной клик — выделение и открытие инспектора
                clip.addEventListener('click', (e) => {
                    e.stopPropagation();
                    
                    const order = parseInt(clip.getAttribute('data-order'));

                    if (selectedOrders.includes(order)) {
                        if (selectedOrders.length > 1) {
                            selectedOrders = selectedOrders.filter(id => id !== order);
                            clip.classList.remove('selected-active', 'active');
                        }
                    } else {
                        selectedOrders.push(order);
                        clip.classList.add('selected-active', 'active'); 
                    }

                    const titleEl = document.getElementById('selectedClipTitle');
                    if (titleEl) titleEl.innerText = `(Выделено сцен: ${selectedOrders.length})`;

                    if (selectedOrders.length > 0) {
                        window.loadClipSettingsToPanel(selectedOrders[selectedOrders.length - 1]);
                    }
                });

                // Сюда же точечно подключаем Drag & Drop ТОЛЬКО для этого кадра
                if (typeof window.attachDragAndDropToElement === 'function') {
                    window.attachDragAndDropToElement(clip);
                }
            };

            // Измененная функция настройки DOM
            function setupDOMEventListeners() {
                setupTabs('.tab-trigger-btn', '.tab-content-pane', 'data-target');
                
                const previewImage = document.getElementById('monitor-preview-image');
                const emptyState = document.getElementById('emptyMonitorState');
                const btnDuplicate = document.getElementById('clipDuplicateBtn');
                const videoTrack = document.querySelector('.timeline-track.video-track');

                // ... (весь твой код кнопок дублирования, удаления, отмены Ctrl+Z остается без изменений) ...

                // ВМЕСТО СТАРОГО КОДА КЛИКОВ ПО КАДРАМ — ПРОСТО ВЫЗЫВАЕМ НАШУ ФУНКЦИЮ:
                document.querySelectorAll('.capcut-clip[data-type="video"]').forEach(clip => {
                    window.attachClipEvents(clip);
                });

                // Глобальный клик по экрану для снятия выделения (оставляем как у тебя)
                document.addEventListener('click', (e) => {
                    const inspector = document.querySelector('.properties-editor-panel') || document.querySelector('.right-sidebar') || document.getElementById('clipDuplicateBtn') || document.getElementById('clipDeleteBtn') || document.getElementById('clipUndoBtn');
                    if (inspector && inspector.contains(e.target)) return;
                    if (e.target.closest('.capcut-clip')) return;

                    if (selectedOrders.length > 0) saveTimelineSnapshot();

                    document.querySelectorAll('.capcut-clip[data-type="video"]').forEach(clip => {
                        clip.classList.remove('selected-active', 'active');
                    });

                    selectedOrders = [];
                    const titleEl = document.getElementById('selectedClipTitle');
                    if (titleEl) titleEl.innerText = `(Выделено сцен: 0)`;

                    if (previewImage) previewImage.classList.add('hidden');
                    if (emptyState) emptyState.classList.remove('hidden');
                });

                // ... (все твои обработчики изменений инпутов duration, effect, filter и т.д. остаются ниже) ...
            }
            refreshTimelineLayout();
            if (typeof window.initDragAndDrop === 'function') window.initDragAndDrop();

            if (selectedOrders.length > 0) {
                loadClipSettingsToPanel(selectedOrders[selectedOrders.length - 1]);
            } else {
                const titleEl = document.getElementById('selectedClipTitle');
                if (titleEl) titleEl.innerText = `(Выделено сцен: 0)`;
                if (previewImage) previewImage.classList.add('hidden');
                if (emptyState) emptyState.classList.remove('hidden');
            }
            syncResourceBarButtons();
        });
    }

    function handleClipClick(clipElement) {
        const order = parseInt(clipElement.getAttribute('data-order'));

        if (selectedOrders.includes(order)) {
            if (selectedOrders.length > 1) {
                selectedOrders = selectedOrders.filter(id => id !== order);
                clipElement.classList.remove('selected-active', 'active');
            }
        } else {
            selectedOrders.push(order);
            clipElement.classList.add('selected-active', 'active'); 
        }

        const titleEl = document.getElementById('selectedClipTitle');
        if (titleEl) titleEl.innerText = `(Выделено сцен: ${selectedOrders.length})`;

        if (selectedOrders.length > 0) {
            loadClipSettingsToPanel(selectedOrders[selectedOrders.length - 1]);
        }
    }

    document.querySelectorAll('.capcut-clip[data-type="video"]').forEach(clip => {
        clip.addEventListener('click', (e) => {
            e.stopPropagation();
            handleClipClick(clip);
        });
    });

    document.addEventListener('click', (e) => {
        const inspector = document.querySelector('.properties-editor-panel') || document.querySelector('.right-sidebar') || document.getElementById('clipDuplicateBtn') || document.getElementById('clipDeleteBtn') || document.getElementById('clipUndoBtn');
        if (inspector && inspector.contains(e.target)) return;
        if (e.target.closest('.capcut-clip')) return;

        if (selectedOrders.length > 0) saveTimelineSnapshot();

        document.querySelectorAll('.capcut-clip[data-type="video"]').forEach(clip => {
            clip.classList.remove('selected-active', 'active');
        });

        selectedOrders = [];
        const titleEl = document.getElementById('selectedClipTitle');
        if (titleEl) titleEl.innerText = `(Выделено сцен: 0)`;

        if (previewImage) previewImage.classList.add('hidden');
        if (emptyState) emptyState.classList.remove('hidden');
    });

    const durInput = document.getElementById('clipDurationInput');
    if (durInput) {
        durInput.addEventListener('change', () => { saveTimelineSnapshot(); });
        durInput.addEventListener('input', (e) => {
            const val = parseFloat(e.target.value).toFixed(1);
            const durVal = document.getElementById('durationVal');
            if (durVal) durVal.innerText = val + 's';
            
            selectedOrders.forEach(order => {
                if (window.timelineState[order]) {
                    window.timelineState[order].duration = parseFloat(val);
                    window.timelineState[order].user_duration = parseFloat(val); 
                }
            });
            refreshTimelineLayout();

            if (typeof window.updateTimelineAfterDOMChange === 'function') {
                window.updateTimelineAfterDOMChange();
            }
        });
    }

    const effectInput = document.getElementById('clipEffectType');
    if (effectInput) {
        effectInput.addEventListener('change', (e) => {
            saveTimelineSnapshot();
            applyParamToSelected('video_effects', e.target.value);
        });
    }

    const filterInput = document.getElementById('clipFilterType');
    if (filterInput) {
        filterInput.addEventListener('change', (e) => {
            saveTimelineSnapshot();
            applyParamToSelected('filter', e.target.value);
        });
    }

    const transInput = document.getElementById('clipTransitionType');
    if (transInput) {
        transInput.addEventListener('change', (e) => {
            saveTimelineSnapshot();
            applyParamToSelected('transition', e.target.value);
        });
    }

    const textInput = document.getElementById('clipTextInput') || document.getElementById('clipTextOverlay');
    if (textInput) {
        textInput.addEventListener('change', () => { saveTimelineSnapshot(); });
        textInput.addEventListener('input', (e) => {
            selectedOrders.forEach(order => {
                if (window.timelineState[order]) {
                    window.timelineState[order].text_overlay.text = e.target.value;
                    updateBadgesVisibility(order);
                }
            });
        });
    }

    const fontInput = document.getElementById('clipFontInput') || document.getElementById('clipTextFont');
    if (fontInput) fontInput.addEventListener('change', (e) => { saveTimelineSnapshot(); applyTextParamToSelected('font', e.target.value); });

    const colorInput = document.getElementById('clipFontColorInput') || document.getElementById('clipTextColor');
    if (colorInput) colorInput.addEventListener('change', (e) => { saveTimelineSnapshot(); applyTextParamToSelected('font_color', e.target.value); });

    const posInput = document.getElementById('clipPositionInput') || document.getElementById('clipTextPosition');
    if (posInput) posInput.addEventListener('change', (e) => { saveTimelineSnapshot(); applyTextParamToSelected('position', e.target.value); });

    const volInput = document.getElementById('audioVolumeInput');
    if (volInput) {
        volInput.addEventListener('change', () => { saveTimelineSnapshot(); });
        volInput.addEventListener('input', (e) => {
            const volVal = document.getElementById('volumeVal');
            if (volVal) volVal.innerText = e.target.value + '%';
            applyAudioParamToSelected('volume', parseInt(e.target.value));
        });
    }

    const fadeInInput = document.getElementById('audioFadeIn');
    if (fadeInInput) fadeInInput.addEventListener('change', (e) => { saveTimelineSnapshot(); applyAudioParamToSelected('fade_in', parseFloat(e.target.value)); });

    const fadeOutInput = document.getElementById('audioFadeOut');
    if (fadeOutInput) fadeOutInput.addEventListener('change', (e) => { saveTimelineSnapshot(); applyAudioParamToSelected('fade_out', parseFloat(e.target.value)); });
}

function saveTimelineSnapshot() {
    const stateCopy = JSON.parse(JSON.stringify(window.timelineState));
    const videoTrack = document.querySelector('.timeline-track.video-track');
    const htmlSnapshot = videoTrack ? videoTrack.innerHTML : '';
    
    timelineHistoryStack.push({
        state: stateCopy,
        html: htmlSnapshot,
        selected: [...selectedOrders]
    });

    if (timelineHistoryStack.length > 10) timelineHistoryStack.shift();
}

function applyParamToSelected(key, value) {
    selectedOrders.forEach(order => {
        if (window.timelineState[order]) {
            window.timelineState[order][key] = value;
            updateBadgesVisibility(order);
        }
    });
    if (typeof window.triggerAutoSave === 'function') {
        window.triggerAutoSave();
    }
}

window.updateBadgesVisibility = updateBadgesVisibility;

function applyTextParamToSelected(subKey, value) {
    selectedOrders.forEach(order => {
        if (window.timelineState[order]) window.timelineState[order].text_overlay[subKey] = value;
    });
    if (typeof window.triggerAutoSave === 'function') {
        window.triggerAutoSave();
    }
}

function applyAudioParamToSelected(subKey, value) {
    selectedOrders.forEach(order => {
        if (window.timelineState[order]) window.timelineState[order].audio_effects[subKey] = value;
    });
    if (typeof window.triggerAutoSave === 'function') {
        window.triggerAutoSave();
    }
}

function loadClipSettingsToPanel(order) {
    const config = window.timelineState[order];
    if (!config) return;

    if (document.getElementById('clipDurationInput')) document.getElementById('clipDurationInput').value = config.duration;
    if (document.getElementById('durationVal')) document.getElementById('durationVal').innerText = config.duration.toFixed(1) + 's';
    if (document.getElementById('clipEffectType')) document.getElementById('clipEffectType').value = config.video_effects;
    if (document.getElementById('clipFilterType')) document.getElementById('clipFilterType').value = config.filter;
    if (document.getElementById('clipTransitionType')) document.getElementById('clipTransitionType').value = config.transition;

    const textInput = document.getElementById('clipTextInput') || document.getElementById('clipTextOverlay');
    if (textInput) textInput.value = config.text_overlay.text;

    const fontInput = document.getElementById('clipFontInput') || document.getElementById('clipTextFont');
    if (fontInput) fontInput.value = config.text_overlay.font;

    const colorInput = document.getElementById('clipFontColorInput') || document.getElementById('clipTextColor');
    if (colorInput) colorInput.value = config.text_overlay.font_color;

    const posInput = document.getElementById('clipPositionInput') || document.getElementById('clipTextPosition');
    if (posInput) posInput.value = config.text_overlay.position;

    if (document.getElementById('audioVolumeInput')) document.getElementById('audioVolumeInput').value = config.audio_effects.volume;
    if (document.getElementById('volumeVal')) document.getElementById('volumeVal').innerText = config.audio_effects.volume + '%';
    if (document.getElementById('audioFadeIn')) document.getElementById('audioFadeIn').value = config.audio_effects.fade_in;
    if (document.getElementById('audioFadeOut')) document.getElementById('audioFadeOut').value = config.audio_effects.fade_out;
    
    const btnMirrorX = document.getElementById('clipMirrorX');
    const btnMirrorY = document.getElementById('clipMirrorY');
    const previewImage = document.getElementById('monitor-preview-image');

    if (btnMirrorX && btnMirrorY) {
        btnMirrorX.classList.toggle('active-fx-btn', config.mirror_x || false);
        btnMirrorY.classList.toggle('active-fx-btn', config.mirror_y || false);
        
        const clipEl = document.querySelector(`.capcut-clip[data-type="video"][data-order="${order}"]`);
        if (clipEl && previewImage) {
            previewImage.src = clipEl.querySelector('img').src;
            previewImage.classList.remove('hidden');
            const scaleX = config.mirror_x ? '-1' : '1';
            const scaleY = config.mirror_y ? '-1' : '1';
            previewImage.style.transform = `scale(${scaleX}, ${scaleY})`;
        }
    }
}

function updateBadgesVisibility(order) {
    const clip = document.querySelector(`.capcut-clip[data-type="video"][data-order="${order}"]`);
    if (!clip) return;

    const config = window.timelineState[order];
    if (!config) return;
    
    const bAnim = clip.querySelector('.badge-anim');
    const bFilter = clip.querySelector('.badge-filter');
    const bTrans = clip.querySelector('.badge-trans');
    const bText = clip.querySelector('.badge-text');
    const badgeX = clip.querySelector('.badge-mirror-x');
    const badgeY = clip.querySelector('.badge-mirror-y');

    if (bAnim) bAnim.classList.toggle('is-active', config.video_effects !== 'none');
    if (bFilter) bFilter.classList.toggle('is-active', config.filter !== 'none');
    if (bTrans) bTrans.classList.toggle('is-active', config.transition !== 'none');
    if (bText) bText.classList.toggle('is-active', config.text_overlay.text.trim() !== '');
    if (badgeX) badgeX.style.display = config.mirror_x ? 'inline-block' : 'none';
    if (badgeY) badgeY.style.display = config.mirror_y ? 'inline-block' : 'none';
}

function refreshTimelineLayout() {
    let totalTimelineSeconds = 0;

    Object.keys(window.timelineState).forEach(order => {
        const config = window.timelineState[order];
        const clipEl = document.querySelector(`.capcut-clip[data-type="video"][data-order="${order}"]`);
        if (clipEl) {
            clipEl.style.width = (config.duration * pixelsPerSecond) + 'px';
        }
        totalTimelineSeconds += config.duration;
        updateBadgesVisibility(order);
    });

    document.querySelectorAll('.capcut-clip.audio-block').forEach(audioClip => {
        const d = parseFloat(audioClip.getAttribute('data-duration'));
        if (d) audioClip.style.width = (d * pixelsPerSecond) + 'px';
    });

    const timebar = document.getElementById('dynamic-timebar');
    if (!timebar) return;
    
    timebar.innerHTML = '';
    const maxScaleSeconds = Math.ceil(totalTimelineSeconds + 20);

    for (let s = 0; s <= maxScaleSeconds; s++) {
        const tick = document.createElement('div');
        tick.className = 'time-tick';
        tick.style.width = pixelsPerSecond + 'px';

        if (s % 5 === 0) {
            tick.classList.add('major');
            tick.innerHTML = `<span>${s}s</span>`;
        }
        timebar.appendChild(tick);
    }
}

function initAudioPlayer() {
    const player = document.getElementById('global-timeline-player');
    if (!player) return;
    let currentPlayingClip = null;

    document.querySelectorAll('.capcut-clip.audio-block').forEach(clip => {
        clip.addEventListener('click', function(e) {
            e.stopPropagation(); 

            const audioSrc = this.getAttribute('data-src');
            const icon = this.querySelector('.play-status-icon');

            if (currentPlayingClip === this) {
                if (!player.paused) {
                    player.pause();
                    this.classList.remove('playing');
                    if (icon) icon.innerText = '▶';
                } else {
                    player.play();
                    this.classList.add('playing');
                    if (icon) icon.innerText = '⏸';
                }
                return;
            }

            if (currentPlayingClip) {
                currentPlayingClip.classList.remove('playing');
                const oldIcon = currentPlayingClip.querySelector('.play-status-icon');
                if (oldIcon) oldIcon.innerText = '▶';
            }

            currentPlayingClip = this;
            player.src = audioSrc;
            player.load();
            
            player.play()
                .then(() => {
                    this.classList.add('playing');
                    if (icon) icon.innerText = '⏸';
                })
                .catch(err => console.error("Не удалось воспроизвести аудио:", err));
        });
    });

    player.addEventListener('ended', () => {
        if (currentPlayingClip) {
            currentPlayingClip.classList.remove('playing');
            const icon = currentPlayingClip.querySelector('.play-status-icon');
            if (icon) icon.innerText = '▶';
            currentPlayingClip = null;
        }
    });
}

function updateStateOrderFromDOM() {
    const clips = document.querySelectorAll('.capcut-clip[data-type="video"]');
    const nextState = {};
    const nextSelected = [];

    clips.forEach((clip, index) => {
        const targetOrder = index + 1;
        const currentOrder = parseInt(clip.getAttribute('data-order'));

        if (window.timelineState[currentOrder]) {
            nextState[targetOrder] = window.timelineState[currentOrder];
        }

        if (selectedOrders.includes(currentOrder)) {
            nextSelected.push(targetOrder);
        }

        clip.setAttribute('data-order', targetOrder);
        
        const badge = clip.querySelector('.capcut-badge');
        if (badge) badge.innerText = `Кадр ${targetOrder}`;
    });

    window.timelineState = nextState;
    selectedOrders = nextSelected;

    const titleEl = document.getElementById('selectedClipTitle');
    if (titleEl) titleEl.innerText = `(Выделено сцен: ${selectedOrders.length})`;
}

/**
 * Синхронизация кнопок в ресурс-баре на основе присутствия картинок на таймлайне
 */
function syncResourceBarButtons() {
    // Получаем список ИМЕН ФАЙЛОВ, а не полных URL (это надежнее)
    const getFileName = (url) => url.split('/').pop().toLowerCase();
    
    const timelineSrcs = new Set();
    document.querySelectorAll('.capcut-clip img').forEach(img => {
        if (img.src) timelineSrcs.add(getFileName(img.src));
    });

    const resourceCards = document.querySelectorAll('.image-asset-card');
    
    resourceCards.forEach(card => {
        const cardImg = card.querySelector('img');
        if (!cardImg) return;

        const fileName = getFileName(cardImg.src);
        const btn = card.querySelector('.resource-action-btn'); // Ищем твой класс кнопки

        if (btn) {
            // Если файл есть на таймлайне, скрываем кнопку
            if (timelineSrcs.has(fileName)) {
                btn.style.display = 'none';
            } else {
                btn.style.display = 'block';
                // При клике сразу добавляем (если еще не привязано)
                btn.onclick = () => addImageToTimelineFromResource(fileName);
            }
        }
    });
}
// Делаем функции доступными глобально
window.syncResourceBarButtons = syncResourceBarButtons;
window.loadClipSettingsToPanel = loadClipSettingsToPanel;
window.updateStateOrderFromDOM = updateStateOrderFromDOM;
window.saveTimelineSnapshot = saveTimelineSnapshot;
window.refreshTimelineLayout = refreshTimelineLayout;