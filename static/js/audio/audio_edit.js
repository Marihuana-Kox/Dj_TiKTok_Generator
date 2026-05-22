// ==========================================
// 1. ГЛАВНАЯ ФУНКЦИЯ СИНТЕЗА (Интегрирована с глобальной модалкой)
// ==========================================
async function synthesizeTrack(event, btnElement, trackIdOrArray) {
  // Жёстко блокируем перезагрузку страницы, которую пытается сделать submit
  if (event) {
    event.preventDefault();
    event.stopPropagation();
  }

  // Приводим к единому формату: всегда работаем с массивом ID (даже если кликнули по одному треку)
  const trackIds = Array.isArray(trackIdOrArray)
    ? trackIdOrArray
    : [trackIdOrArray];

  // Ищем глобальные настройки (вверху страницы)
  const providerSelect = document.getElementById("audio-provider-select");
  const voiceSelect = document.getElementById("voice-preset-select");

  const provider = providerSelect ? providerSelect.value : "";
  const voice = voiceSelect ? voiceSelect.value : "";

  // Если это одиночный запуск, проверим текст на пустоту для безопасности
  if (!Array.isArray(trackIdOrArray)) {
    const card = document.getElementById(`track-card-${trackIdOrArray}`);
    if (card) {
      const textarea = card.querySelector(".track-textarea");
      const text = textarea ? textarea.value.trim() : "";
      if (!text) {
        alert("❌ Нельзя озвучить пустой текст!");
        return;
      }
    }
  }

  try {
    const csrfInput = document.querySelector("[name=csrfmiddlewaretoken]");
    if (!csrfInput)
      throw new Error("На странице не найден токен безопасности CSRF!");

    // ========================================================
    // ШАГ 1. СНАЧАЛА СОХРАНЯЕМ ТЕКСТ ДЛЯ ВСЕХ ТРЕКОВ ИЗ ПАЧКИ
    // ========================================================
    for (const id of trackIds) {
      const card = document.getElementById(`track-card-${id}`);
      if (card) {
        const textarea = card.querySelector(".track-textarea");
        if (textarea) {
          const textValue = textarea.value;
          try {
            // Отдельный, быстрый запрос СТРОГО на сохранение текста
            await fetch(`/audio/track/${id}/save-text/`, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfInput.value,
                "X-Requested-With": "XMLHttpRequest",
              },
              body: JSON.stringify({ text: textValue }),
            });
            console.log(`📝 Текст фрагмента #${id} успешно сохранен в БД.`);
          } catch (saveErr) {
            console.error(`🚨 Не удалось сохранить текст для фрагмента #${id}:`, saveErr);
          }
        }
      }
    }

    // ========================================================
    // ШАГ 2. И ТОЛЬКО ТЕПЕРЬ ЗАПУСКАЕМ СИНТЕЗ (Твой оригинальный код)
    // ========================================================
    // Этот запрос летит на эндпоинт синтеза и несет в себе настройки голоса
    const response = await fetch("/audio/track/synthesize/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfInput.value,
        "X-Requested-With": "XMLHttpRequest",
      },
      body: JSON.stringify({
        track_ids: trackIds,
        provider: provider,
        voice_preset: voice,
      }),
    });

    const data = await response.json();
    console.log("Ответ initialization генерации:", data);

    if (data.success && data.task_id) {
      // Визуально переводм карточки, ушедшие на озвучку, в режим ожидания
      trackIds.forEach((id) => {
        const card = document.getElementById(`track-card-${id}`);
        if (card) {
          const badge = card.querySelector(".badge");
          if (badge) {
            badge.className = "badge badge-work";
            badge.textContent = "В обработке";
          }
        }
      });

      // 2. Запускаем штатный живой SSE-поток отслеживания из твоего modal.js
      if (typeof window.startProgressTracking === "function") {
        window.startProgressTracking(
          "/audio/api/generation-stream/", // Твой рабочий эндпоинт прогресса
          data.task_id, // ID запущенного процесса
          "progress-modal", // ID модалки на экране
          function (result) {
            // Этот callback сработает автоматически, когда сервер пришлет статус "done"
            console.log("🎉 Озвучка пачки фрагментов успешно завершена!");
            
            // Динамически переводим обработанные ID карточек в статус "Успешно"
            trackIds.forEach((id) => {
              const card = document.getElementById(`track-card-${id}`);
              if (card) {
                const badge = card.querySelector(".badge");
                if (badge) {
                  badge.className = "badge badge-done";
                  badge.textContent = "Успешно";
                }
                
                // Также блокируем чекбокс завершенного трека для безопасности
                const cb = card.querySelector(".prompt-checkbox");
                if (cb) {
                  cb.checked = false;
                  cb.setAttribute("disabled", "disabled");
                }
              }
            });

            // Проверяем, готовы ли вообще все треки на странице, чтобы зажечь кнопку видео
            checkProjectVideoReady();
          },
        );
      } else {
        console.error(
          "🚨 Ошибка: Глобальная функция startProgressTracking не найдена.",
        );
      }
    } else {
      alert(`Ошибка: ${data.error || "Не удалось запустить генерацию"}`);
    }
  } catch (err) {
    console.error("🚨 Крах операции:", err);
    alert(`Системная ошибка конвейера: ${err.message}`);
  }
}

// ==========================================
// 2. ИНИЦИАЛИЗАЦИЯ ИНТЕРФЕЙСА И ОБРАБОТЧИКОВ
// ==========================================
document.addEventListener("DOMContentLoaded", function () {
  console.log("✅ audio_edit.js загружен и готов к работе");

  const selectAllCheckbox = document.getElementById("select-all-prompts");
  const trackCheckboxes = document.querySelectorAll(".prompt-checkbox");
  const generateAudioBtn = document.getElementById("generate-audio-btn");
  const btnCountSpan = document.getElementById("btn-count");
  const selectedCountSpan = document.getElementById("selected-count");
  const textareas = document.querySelectorAll(".track-textarea");

  // Функция пересчета выбранных строк и активации кнопок
  function updateInterfaceState() {
    // const checkedBoxes = document.querySelectorAll(".prompt-checkbox:checked");
    const checkedBoxes = document.querySelectorAll(".prompt-checkbox:checked:not([disabled])");
    const count = checkedBoxes.length;

    // Обновляем счетчик на главной кнопке
    if (btnCountSpan) btnCountSpan.textContent = count;
    if (selectedCountSpan)
      selectedCountSpan.textContent = `(выбрано: ${count})`;
    if (generateAudioBtn) generateAudioBtn.disabled = count === 0;

    // Включаем или выключаем кнопки сохранения в зависимости от чекбокса
    trackCheckboxes.forEach((cb) => {
      const card = cb.closest(".card");
      if (card) {
        const saveBtn = card.querySelector(".track-save-btn");
        if (saveBtn) {
          saveBtn.disabled = !cb.checked;
        }
      }
    });

    // Управляем главным чекбоксом "Выбрать все"
    if (selectAllCheckbox && trackCheckboxes.length > 0) {
      const nonDisabledBoxes = document.querySelectorAll(".prompt-checkbox:not([disabled])");
      if (nonDisabledBoxes.length > 0) {
        selectAllCheckbox.checked = checkedBoxes.length === nonDisabledBoxes.length;
      } else {
        selectAllCheckbox.checked = false;
      }
    }
  }

  // ПОДКЛЮЧАЕМ КНОПКУ МАССОВОЙ ОЗВУЧКИ: «⚡ Озвучить выбранные (X)»
  if (generateAudioBtn) {
    generateAudioBtn.removeAttribute("onclick"); // Счищаем старые инлайн привязки
    generateAudioBtn.addEventListener("click", function (e) {
      e.preventDefault();

      // Собираем ID всех чекбоксов, которые отметил пользователь
      const checkedBoxes = document.querySelectorAll(
        ".prompt-checkbox:checked",
      );
      const ids = Array.from(checkedBoxes).map((cb) => cb.value);

      if (ids.length > 0) {
        // Вызываем ту же самую универсальную функцию, передавая массив ID
        synthesizeTrack(e, this, ids);
      }
    });
  }

  // Обработчик для "Выбрать все"
  if (selectAllCheckbox) {
    selectAllCheckbox.addEventListener("change", function () {
      trackCheckboxes.forEach((cb) => {
        // 🔥 ИСПРАВЛЕНО: Отмечаем только те чекбоксы, которые не заблокированы
        if (!cb.hasAttribute("disabled")) {
          cb.checked = selectAllCheckbox.checked;
        }
      });
      updateInterfaceState();
    });
  }

  // Обработчик для одиночных чекбоксов
  trackCheckboxes.forEach((cb) => {
    cb.addEventListener("change", updateInterfaceState);
  });

  // Инициализация счетчиков символов и слов при вводе
  textareas.forEach((textarea) => {
    function handleTextChange(isInitialLoad = false) {
      const nameAttr = textarea.getAttribute("name");
      if (!nameAttr) return;

      const trackId = nameAttr.replace("text_", "");
      const card = document.getElementById(`track-card-${trackId}`);
      if (!card) return;

      const charSpan = card.querySelector(".char-counter strong");
      const wordSpan = card.querySelector(".word-counter strong");

      const text = textarea.value.trim();
      const charCount = text.length;
      const wordCount =
        text === "" ? 0 : text.split(/\s+/).filter((w) => w.length > 0).length;

      if (charSpan) charSpan.textContent = charCount;
      if (wordSpan) wordSpan.textContent = wordCount;

      // Если это ввод пользователя (а не первая загрузка), разблокируем кнопку сохранения
      if (!isInitialLoad) {
        const saveBtn = card.querySelector(".track-save-btn");
        if (saveBtn) {
          // Разрешаем сохранять изменения только если чекбокс активен
          const cb = card.querySelector(".prompt-checkbox");
          if (cb && cb.checked) {
            saveBtn.disabled = false;
          }
        }
      }
    }

    textarea.addEventListener("input", function () {
      handleTextChange(false);
    });

    // Запускаем один раз при загрузке страницы, чтобы просчитать начальные цифры
    handleTextChange(true);
  });

  // Первый запуск для инициализации состояний кнопок
  updateInterfaceState();

  // Инициализация кастомных плееров
  initCustomAudioPlayers();
});

// ==========================================
// 3. 💾 ФУНКЦИЯ СОХРАНЕНИЯ ТЕКСТА КАРТОЧКИ В БД
// ==========================================
async function saveTrackText(event, btnElement, trackId) {
  event.preventDefault();

  const card = document.getElementById(`track-card-${trackId}`);
  if (!card) return;

  const textarea = card.querySelector(".track-textarea");
  const text = textarea ? textarea.value.trim() : "";

  if (!text) {
    alert("❌ Нельзя сохранить пустой текст!");
    return;
  }

  btnElement.disabled = true;
  const originalText = btnElement.innerHTML;
  btnElement.innerHTML = "⏳ Сохраняю...";

  try {
    const csrfInput = document.querySelector("[name=csrfmiddlewaretoken]");
    if (!csrfInput)
      throw new Error("На странице не найден токен безопасности CSRF!");

    const response = await fetch(`/audio/track/${trackId}/save-text/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfInput.value,
      },
      body: JSON.stringify({ text: text }),
    });

    const data = await response.json();

    if (data.success) {
      btnElement.innerHTML = "✅ Сохранено";
      setTimeout(() => {
        btnElement.innerHTML = originalText;
        btnElement.disabled = true; // Выключаем, так как текст совпадает с базой
      }, 1500);
    } else {
      alert(`Ошибка сохранения: ${data.error}`);
      btnElement.disabled = false;
      btnElement.innerHTML = originalText;
    }
  } catch (err) {
    console.error("🚨 Ошибка при сохранении:", err);
    alert(`Системная ошибка: ${err.message}`);
    btnElement.disabled = false;
    btnElement.innerHTML = originalText;
  }
}

// ==========================================
// 4. ИНИЦИАЛИЗАЦИЯ КАСТОМНЫХ АУДИОПЛЕЕРОВ
// ==========================================
function initCustomAudioPlayers() {
  const players = document.querySelectorAll(".custom-audio-player");

  players.forEach((player) => {
    const audio = player.querySelector("audio");
    const playBtn = player.querySelector(".play-btn");
    const timeCurrent = player.querySelector(".time-current");
    const timeTotal = player.querySelector(".time-total");
    const progressContainer = player.querySelector(
      ".player-progress-container",
    );
    const progressBar = player.querySelector(".player-progress-bar");

    if (!audio || !playBtn) return;

    // Переключение Воспроизведение / Пауза
    playBtn.addEventListener("click", function () {
      // Останавливаем все другие плееры на странице перед запуском этого
      document.querySelectorAll("audio").forEach((otherAudio) => {
        if (otherAudio !== audio && !otherAudio.paused) {
          otherAudio.pause();
          const otherPlayer = otherAudio.closest(".custom-audio-player");
          if (otherPlayer) {
            const otherPlayBtn = otherPlayer.querySelector(".play-btn");
            if (otherPlayBtn) otherPlayBtn.innerHTML = "▶";
          }
        }
      });

      if (audio.paused) {
        audio.play();
        playBtn.innerHTML = "⏸";
      } else {
        audio.pause();
        playBtn.innerHTML = "▶";
      }
    });

    // Обновление прогресса при воспроизведении
    audio.addEventListener("timeupdate", function () {
      if (audio.duration) {
        const percentage = (audio.currentTime / audio.duration) * 100;
        if (progressBar) progressBar.style.width = percentage + "%";
        if (timeCurrent)
          timeCurrent.textContent = formatTime(audio.currentTime);
      }
    });

    // Длительность трека при загрузке метаданных
    audio.addEventListener("loadedmetadata", function () {
      if (timeTotal) timeTotal.textContent = formatTime(audio.duration);
      if (timeCurrent) timeCurrent.textContent = formatTime(0);
    });

    // Если метаданные уже были загружены до привязки события
    if (audio.readyState >= 1 && timeTotal) {
      timeTotal.textContent = formatTime(audio.duration);
    }

    // Клик по таймлайну (перемотка трека)
    if (progressContainer) {
      progressContainer.addEventListener("click", function (e) {
        const rect = progressContainer.getBoundingClientRect();
        const clickX = e.clientX - rect.left;
        const width = rect.width;
        if (width > 0 && audio.duration) {
          const newTime = (clickX / width) * audio.duration;
          audio.currentTime = newTime;
        }
      });
    }

    // Возврат кнопки в исходное состояние по окончании аудио
    audio.addEventListener("ended", function () {
      playBtn.innerHTML = "▶";
      if (progressBar) progressBar.style.width = "0%";
      if (timeCurrent) timeCurrent.textContent = formatTime(0);
    });
  });
}

/** Вспомогательная функция форматирования времени (секунды -> ММ:СС) */
function formatTime(seconds) {
  if (isNaN(seconds)) return "00:00";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return (mins < 10 ? "0" : "") + mins + ":" + (secs < 10 ? "0" : "") + secs;
}

// ==========================================
// 5. АВТОУДАЛЕНИЕ ПЛАШЕК С ОШИБКАМИ ЧЕРЕЗ 20 СЕКУНД
// ==========================================
function setupAlertAutoremove() {
  const alerts = document.querySelectorAll(".alert");

  alerts.forEach((alertBox) => {
    if (!alertBox.dataset.hasTimer) {
      alertBox.dataset.hasTimer = "true";

      setTimeout(() => {
        alertBox.style.transition =
          "opacity 0.5s ease, margin 0.5s ease, padding 0.5s ease, height 0.5s ease";
        alertBox.style.opacity = "0";

        setTimeout(() => {
          alertBox.remove();
          console.log("🗑️ Плашка ошибки успешно удалена из DOM по таймеру.");
        }, 500);
      }, 20000);
    }
  });
}

setupAlertAutoremove();
window.triggerAlertAutoremove = setupAlertAutoremove;

// ==========================================
// 6. ЖИВАЯ ПРОВЕРКА ДЛЯ КНОПКИ ВИДЕОРЕДАКТОРА И МИКСА
// ==========================================
function checkProjectVideoReady() {
  console.log("🔍 Проверка готовности аудиодорожек...");
  const allBadges = document.querySelectorAll(".space-y-3 .badge");
  let allTracksSuccess = true;

  if (allBadges.length === 0) return;

  allBadges.forEach((badge) => {
    const text = badge.textContent.trim();
    if (!badge.classList.contains("badge-done") && text !== "Успешно") {
      allTracksSuccess = false;
    }
  });

  // Если абсолютно все фрагменты стали успешными
  if (allTracksSuccess) {
    // 1. Активируем кнопку перехода в видеоредактор
    const videoBtn = document.getElementById("go-to-video-editor-btn");
    if (videoBtn) {
      console.log("🚀 Все фрагменты успешны. Активируем кнопку Сборки Видео.");
      videoBtn.classList.remove("disabled");
      videoBtn.removeAttribute("aria-disabled");
      videoBtn.style.pointerEvents = "auto";
      videoBtn.style.opacity = "1";
    }

    // 2. Убираем песочные часы из блока "Полный микс статьи" и пишем, что всё готово
    const mixContainer = document.getElementById("final-audio-container");
    if (mixContainer) {
      // Проверяем, нет ли там уже готового плеера (чтобы не стереть его случайно)
      if (!mixContainer.querySelector("audio")) {
        mixContainer.innerHTML = `
          <div class="text-success text-small p-2 bg-light-green rounded w-100 border text-center fw-bold" style="background-color: #d4edda; color: #155724; border-color: #c3e6cb;">
              ✅ Все фрагменты готовы к сборке!
          </div>
        `;
      }
    }
  }
}