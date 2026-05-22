(function () {
  // console.log('✅ modal.js загружен (глобальная унифицированная версия)');

  let eventSource = null;
  let currentModalId = "progress-modal";
  let currentTaskId = null;
  let currentCancelUrl = null;

  // --- Открытие/Закрытие ---
  window.openModal = function (modalId) {
    const modal = document.getElementById(modalId || "progress-modal");
    if (!modal) return;
    modal.classList.remove("d-none");
    modal.style.display = "flex";
    document.body.style.overflow = "hidden";
    currentModalId = modalId || "progress-modal";
  };

  window.closeModal = function (modalId) {
    const modal = document.getElementById(modalId || currentModalId);
    if (!modal) return;
    modal.classList.add("d-none");
    modal.style.display = "none";
    document.body.style.overflow = "";
  };

  // --- Плавное обновление прогресса + БЕГУЩИЕ ЦИФРЫ ---
  window.updateProgress = function (targetPercent, message) {
    const progressBar = document.getElementById("gen-progress-bar");
    const progressPercent = document.getElementById("gen-progress-percent");
    const progressMessage = document.getElementById("gen-progress-message");

    if (progressMessage && message) progressMessage.textContent = message;
    if (progressBar) {
      progressBar.style.transition = "width 0.8s linear";
      progressBar.style.width = targetPercent + "%";
    }
    if (progressPercent) {
      const startPercent = parseInt(progressPercent.textContent) || 0;
      const duration = 800;
      const startTime = performance.now();
      function animate(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const currentNum = Math.floor(
          startPercent + (targetPercent - startPercent) * progress,
        );
        progressPercent.textContent = currentNum + "%";
        if (progress < 1) requestAnimationFrame(animate);
      }
      requestAnimationFrame(animate);
    }
  };

  // --- Логирование ---
  window.addProgressLog = function (message, type = "info") {
    const log = document.getElementById("gen-progress-log");
    if (!log || !message) return;
    const li = document.createElement("li");
    li.textContent = message;
    li.className = type;
    log.appendChild(li);
    log.scrollTop = log.scrollHeight;
  };

  // --- Финализация (Зелёная полоса, задержка, редирект/колбэк) ---
  window.finishProgress = function (
    success,
    message,
    redirectUrl = null,
    delay = 3000,
    callback = null,
  ) {
    const progressBar = document.getElementById("gen-progress-bar");
    const progressMessage = document.getElementById("gen-progress-message");

    if (progressBar) {
      progressBar.style.transition =
        "width 0.5s ease, background-color 0.5s ease";
      progressBar.style.width = "100%";
      progressBar.style.backgroundColor = success ? "#4caf50" : "#ef4444";
      progressBar.classList.remove("progress-bar-animated");
    }

    const finalMsg = success
      ? message || "✅ Все успешно сгенерировалось!"
      : message || "❌ Ошибка выполнения";
    if (progressMessage) progressMessage.textContent = finalMsg;
    window.addProgressLog(finalMsg, success ? "success" : "error");

    setTimeout(() => {
      if (callback && typeof callback === "function")
        callback({ success, redirectUrl });
      if (success && redirectUrl) {
        window.location.href = redirectUrl;
      } else if (!redirectUrl) {
        window.closeModal(currentModalId);
      }
    }, delay);
  };

  // --- ГЛОБАЛЬНЫЙ SSE ТРЕКЕР (УНИФИЦИРОВАННЫЙ) ---
  window.startProgressTracking = function (
    streamUrl,
    taskId,
    modalId = "progress-modal",
    callback = null,
    cancelUrl = null,
  ) {
    currentModalId = modalId || "progress-modal";
    currentTaskId = taskId;
    currentCancelUrl = cancelUrl;

    window.openModal(currentModalId);
    window.updateProgress(0, "Инициализация...");
    window.addProgressLog("🚀 Генерация запущена", "info");

    if (eventSource) eventSource.close();

    const url = new URL(streamUrl, window.location.origin);
    if (taskId) url.searchParams.set("task_id", taskId);

    eventSource = new EventSource(url.toString());

    eventSource.onmessage = function (event) {
      try {
        const data = JSON.parse(event.data);

        if (data.percent !== undefined) {
          window.updateProgress(data.percent, data.message);
        }

        if (data.logs && Array.isArray(data.logs)) {
          const logContainer = document.getElementById("gen-progress-log");
          if (logContainer) {
            logContainer.innerHTML = "";
            data.logs.forEach((msg) => window.addProgressLog(msg, "info"));
          }
        } else if (data.message) {
          window.addProgressLog(
            data.message,
            data.status === "error" ? "error" : "info",
          );
        }

        if (data.status === "done") {
          eventSource.close();
          window.finishProgress(
            true,
            data.message,
            data.redirect_url || null,
            3000,
            callback,
          );
        } else if (data.status === "error") {
          eventSource.close();
          window.finishProgress(
            false,
            data.message || "Ошибка генерации",
            null,
            0,
            callback,
          );
        }
      } catch (e) {
        console.error("❌ Ошибка парсинга SSE:", e, event.data);
      }
    };

    eventSource.onerror = function () {
      console.warn("⚠️ SSE: потеря связи с сервером");
    };
  };

  window.stopProgressTracking = function () {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  };

  // --- Обработчики кнопок закрытия/отмены ---
  document.addEventListener("DOMContentLoaded", function () {
    const closeBtn = document.getElementById("close-progress-modal");
    if (closeBtn) {
      closeBtn.addEventListener("click", function () {
        window.closeModal(currentModalId);
        window.stopProgressTracking();
      });
    }

    const cancelBtn = document.getElementById("cancel-progress-btn");
    if (cancelBtn) {
      cancelBtn.addEventListener("click", function () {
        if (confirm("⚠️ Отменить генерацию?")) {
          window.closeModal(currentModalId);
          window.stopProgressTracking();
          if (currentCancelUrl && currentTaskId) {
            const csrf =
              typeof window.getCookie === "function"
                ? window.getCookie("csrftoken")
                : "";
            fetch(currentCancelUrl, {
              method: "POST",
              headers: { "X-CSRFToken": csrf },
            }).catch(() => {});
          }
        }
      });
    }

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        const activeModal = document.querySelector(
          ".modal-overlay:not(.d-none)",
        );
        if (activeModal) {
          window.closeModal(activeModal.id);
          window.stopProgressTracking();
        }
      }
    });
  });
})();
