document.addEventListener("DOMContentLoaded", function () {
  const articleSelect = document.getElementById("article_select");
  const languageSelect = document.getElementById("language_select");
  const form = document.getElementById("audio-create-form");

  // ==========================================
  // 1. ТВОЙ ИСХОДНЫЙ БЛОК (Динамические языки) - ОСТАВЛЕН БЕЗ ИЗМЕНЕНИЙ
  // ==========================================
 function fetchLanguages(clusterId) {
  if (!clusterId) return;

  languageSelect.disabled = true;
  languageSelect.innerHTML =
    '<option value="" disabled selected>Загрузка языков...</option>';

  fetch(`?action=get_languages&cluster_id=${clusterId}`, {
    headers: { "X-Requested-With": "XMLHttpRequest" },
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.success && data.languages.length > 0) {
        languageSelect.innerHTML =
          '<option value="" disabled selected>-- Выберите язык перевода --</option>';
        data.languages.forEach((lang) => {
          languageSelect.innerHTML += `<option value="${lang.code}">${lang.name} (${lang.words} слов)</option>`;
        });
        languageSelect.disabled = false;
      } else {
        languageSelect.innerHTML =
          '<option value="" disabled>Нет доступных переводов</option>';
      }
    })
    .catch(() => {
      languageSelect.innerHTML =
        '<option value="" disabled>Ошибка загрузки</option>';
    });
}

// 2. Вешаем обработчик события на изменение селекта (ручной выбор)
if (articleSelect) {
  articleSelect.addEventListener("change", function () {
    fetchLanguages(this.value);
  });

  // 3. 🔥 АВТО-ЗАПУСК: Если при загрузке страницы в селекте УЖЕ есть значение
  if (articleSelect.value) {
    fetchLanguages(articleSelect.value);
  }
}

  // ==========================================
  // 2. ОТПРАВКА ФОРМЫ (Интеграция модалки)
  // ==========================================
  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault(); // Останавливаем стандартную перезагрузку страницы

      // НАПРАВЛЯЕМ МОДКУ НА ЭКРАН И ИНИЦИАЛИЗИРУЕМ СТАРТ
      if (typeof window.openModal === "function") {
        window.openModal("progress-modal");
        window.updateProgress(0, "Инициализация...");

        // Очищаем контейнер логов перед новым запуском
        const logContainer = document.getElementById("gen-progress-log");
        if (logContainer) logContainer.innerHTML = "";

        window.addProgressLog("🚀 Подготовка конвейера нарезки...", "info");
      }

      const formData = new FormData(form);
      
      if (articleSelect && articleSelect.value) {
          formData.append('cluster_id', articleSelect.value);
      }
      if (languageSelect && languageSelect.value) {
          formData.append('language_code', languageSelect.value);
      }

      // Небольшой дебаг в консоль браузера перед отправкой
      console.log("✈️ Отправка данных нарезки:", {
          cluster_id: formData.get('cluster_id'),
          language_code: formData.get('language_code')
      });

      fetch(form.getAttribute("action"), {
        method: "POST",
        body: formData,
        headers: { "X-Requested-With": "XMLHttpRequest" },
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.success && data.task_id) {
            // Начинаем циклический опрос прогресса
            startProgressPolling(data.task_id);
          } else {
            if (typeof window.finishProgress === "function") {
              window.finishProgress(
                false,
                "❌ Не удалось инициализировать задачу",
              );
            }
          }
        })
        .catch((err) => {
          console.error("Ошибка старта процесса:", err);
          if (typeof window.finishProgress === "function") {
            window.finishProgress(false, "💥 Сбой отправки формы");
          }
        });
    });
  }

  // ==========================================
  // 3. ФУНКЦИЯ ПОЛЛИНГА (Тотальный дебаг статусов)
  // ==========================================
  function startProgressPolling(taskId) {
    let lastLogCount = 0;
    console.log("🎯 Функция поллинга СТАРТОВАЛА для задачи:", taskId);

    const interval = setInterval(() => {
      fetch(`/audio/api/generation-progress/${taskId}/`, {
        headers: { "X-Requested-With": "XMLHttpRequest" },
      })
        .then((res) => {
          if (!res.ok) throw new Error(`Ошибка сервера: ${res.status}`);
          return res.json();
        })
        .then((progress) => {
          // 🔥 ВЫВОДИМ КАЖДЫЙ ОТВЕТ СЕРВЕРА В КОНСОЛЬ ГАРАНТИРОВАННО
          console.log(
            `📡 [Поллинг] Прогресс: ${progress.percent}%, Статус в базе: "${progress.status}"`,
            progress,
          );

          if (typeof window.updateProgress === "function") {
            window.updateProgress(progress.percent, progress.message);
          }

          if (progress.logs && Array.isArray(progress.logs)) {
            if (progress.logs.length > lastLogCount) {
              const newLogs = progress.logs.slice(lastLogCount);
              newLogs.forEach((msg) => {
                if (typeof window.addProgressLog === "function") {
                  window.addProgressLog(msg, "info");
                }
              });
              lastLogCount = progress.logs.length;
            }
          }

          // Проверяем финиш (расширили условия на случай разных статусов)
          if (
            progress.status === "done" ||
            progress.status === "success" ||
            progress.status === "completed" ||
            progress.percent === 100
          ) {
            clearInterval(interval);
            console.log(
              "🏁 Условие финиша СРАБОТАЛО! Подготовка к редиректу...",
            );

            if (typeof window.finishProgress === "function") {
              window.finishProgress(
                true,
                progress.message || "🎉 Нарезка завершена!",
              );
            }

            // Проверяем все возможные варианты ссылки
            const targetUrl =
              progress.redirect_url ||
              progress.url ||
              (progress.project_id
                ? `/audio/${progress.project_id}/edit/`
                : null);

            if (targetUrl) {
              console.log("✈️ Исполнение редиректа на адрес:", targetUrl);
              window.location.href = targetUrl;
            } else {
              console.error(
                "❌ Ссылка не найдена в ответе. Проверь ключи во views.py",
              );
            }
          }

          if (progress.status === "error" || progress.status === "failed") {
            clearInterval(interval);
            if (typeof window.finishProgress === "function") {
              window.finishProgress(
                false,
                progress.message || "Ошибка обработки",
              );
            }
          }
        })
        .catch((err) => {
          clearInterval(interval);
          console.error("❌ Критическая ошибка внутри fetch-поллинга:", err);
        });
    }, 400);
  }
});
