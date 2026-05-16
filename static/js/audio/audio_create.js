/**
 * Скрипт управления формой создания озвучки.
 */

// Функция переключения расширенных настроек (вынесена из HTML)
function toggleVoiceSettings(show) {
  const block = document.getElementById("voice-settings-block");
  if (block) {
    show ? block.classList.remove("d-none") : block.classList.add("d-none");
  }
}
document.addEventListener("DOMContentLoaded", function () {
  const articleSel = document.getElementById("article_select");
  const langSel = document.getElementById("language_select");
  const voiceSel = document.getElementById("voice_select");
  const statsEl = document.getElementById("article-stats");
  const form = document.querySelector("form");

  const langMap = { ru: "ru-RU", en: "en-US", de: "de-DE", fr: "fr-FR" };

  const voicesDataNode = document.getElementById("voices-data");
  const voicesData = voicesDataNode
    ? JSON.parse(voicesDataNode.textContent)
    : {};

  // --- Логика выбора статьи (Оптимизирована) ---
  articleSel?.addEventListener("change", function () {
    const selectedOpt = this.options[this.selectedIndex];
    if (!selectedOpt || !selectedOpt.value) return;
    try {
      const transData = JSON.parse(selectedOpt.dataset.translations);
      langSel.disabled = false;
      langSel.innerHTML =
        '<option value="" disabled selected>-- Выберите язык --</option>';

      let statsText = "Доступно: ";
      transData.forEach((tr) => {
        const opt = document.createElement("option");
        opt.value = tr.language;
        opt.textContent = `${tr.language.toUpperCase()} (${tr.words} слов)`;
        if (tr.language === "ru") opt.selected = true;
        langSel.appendChild(opt);
        statsText += `${tr.language.toUpperCase()} (${tr.words} сл.) | `;
      });

      if (statsEl) statsEl.textContent = statsText.slice(0, -3);
      if (langSel.value) updateVoices(langSel.value);
    } catch (e) {
      console.error("Ошибка парсинга данных статьи:", e);
    }
  });

  langSel?.addEventListener("change", function () {
    updateVoices(this.value);
  });

  function updateVoices(langCode) {
    if (!voiceSel) return;
    voiceSel.innerHTML = "";
    const cleanLang = langCode.trim().toLowerCase();

    const matchingKey = Object.keys(voicesData).find((key) => {
      const cleanKey = key.trim().toLowerCase();
      return cleanKey.includes(cleanLang) || cleanLang.includes(cleanKey);
    });

    const voicesToDisplay = matchingKey ? voicesData[matchingKey] : [];

    if (voicesToDisplay.length > 0) {
      voiceSel.innerHTML =
        "<option disabled selected>-- Выберите голос --</option>";
      voicesToDisplay.forEach((voice) => {
        const opt = document.createElement("option");
        opt.value = voice.id;
        opt.textContent = voice.name;
        voiceSel.appendChild(opt);
      });
      voiceSel.disabled = false;
    } else {
      voiceSel.innerHTML = `<option>Голоса не найдены</option>`;
      voiceSel.disabled = true;
    }
  }

  // --- ФИНАЛЬНАЯ ОТПРАВКА (Сначала модалка, потом процесс) ---
  form.addEventListener("submit", function (event) {
    event.preventDefault();
    // Показываем модалку (пустую или с лоадером) до запроса
    if (typeof openModal === "function") {
      openModal("progress-modal");
    }
    const formData = new FormData(form);
    const rawLang = formData.get("language");

    // Минимальный Payload. Сервер сам достанет текст по article_id
    const payload = {
      article_id: formData.get("article_id"),
      provider_id: formData.get("provider"),
      voice_id: formData.get("voice_id"),
      language: langMap[rawLang] || rawLang,
      speaking_rate: parseFloat(formData.get("speaking_rate")) || 1.0,
      stability: parseFloat(formData.get("stability")) || 0.5,
    };

    // ШАГ 1: Быстрый POST на создание задачи
    // ВАЖНО: адрес начинается с /audio/
    fetch("/audio/create/", {
      method: "POST",
      body: JSON.stringify(payload),
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": getCookie("csrftoken"),
      },
    })
      .then((res) => {
        if (!res.ok) throw new Error(`Ошибка сервера: ${res.status}`);
        return res.json();
      })
      .then((result) => {
        // ШАГ 2: Если получили task_id — МГНОВЕННО запускаем модалку
        if (result.success && result.task_id) {
          // --- ЛОГИРОВАНИЕ ОТВЕТА ---
          console.log("🆔 Задача запущена. ID:", result.task_id);
          console.group("📥 ОТВЕТ ОТ СЕРВЕРА");
          console.log("Результат:", result);
          console.groupEnd();

          if (typeof window.startProgressTracking === "function") {
            window.startProgressTracking(
              "/audio/api/generation-stream/", // Путь к стриму логов
              result.task_id,
              "progress-modal",
            );
            // --- НОВЫЙ БЛОК: ЗАДЕРЖКА ПЕРЕД ФИНАЛОМ ---
            // Мы перехватываем момент завершения, чтобы окно не схлопнулось
            const originalFinish = window.finishProgress; // Если у тебя есть такая функция
            if (typeof originalFinish === "function") {
              window.finishProgress = function () {
                console.log(
                  "⏳ Процесс завершен. Ждем 3 секунды перед закрытием...",
                );
                setTimeout(() => {
                  originalFinish();
                }, 3000); // Задержка 3000 мс (3 секунды)
              };
            }
          }
        } else {
          throw new Error(result.error || "Не удалось запустить задачу");
        }
      })
      .then((response) => {
        if (!response.ok) throw new Error("Ошибка сервера " + response.status);
        return response.json();
      })
      .catch((err) => {
        console.error("Ошибка:", err);
        if (typeof showToast === "function") showToast(err.message, "error");
      });
  });
});

// Вспомогательная функция для CSRF
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === name + "=") {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

// document.addEventListener("DOMContentLoaded", function () {
//   const articleSel = document.getElementById("article_select");
//   const langSel = document.getElementById("language_select");
//   const voiceSel = document.getElementById("voice_select");
//   const statsEl = document.getElementById("article-stats");
//   const form = document.querySelector("form");

//   // Маппинг кодов (чтобы не менять логику твоих селектов)
//   const langMap = { ru: "ru-RU", en: "en-US", de: "de-DE", fr: "fr-FR" };

//   const voicesDataNode = document.getElementById("voices-data");
//   const voicesData = voicesDataNode
//     ? JSON.parse(voicesDataNode.textContent)
//     : {};

//   // --- Твоя логика выбора статьи (не трогаем) ---
//   articleSel?.addEventListener("change", function () {
//     const selectedOpt = this.options[this.selectedIndex];
//     if (!selectedOpt || !selectedOpt.value) return;
//     try {
//       const transData = JSON.parse(selectedOpt.dataset.translations);
//       langSel.disabled = false;
//       langSel.innerHTML =
//         '<option value="" disabled selected>-- Выберите язык --</option>';
//       let statsText = "Доступно: ";
//       transData.forEach((tr) => {
//         const opt = document.createElement("option");
//         opt.value = tr.language;
//         opt.textContent = `${tr.language.toUpperCase()} (${tr.words} слов)`;
//         if (tr.language === "ru") opt.selected = true;
//         langSel.appendChild(opt);
//         statsText += `${tr.language.toUpperCase()} (${tr.words} сл.) | `;
//       });
//       if (statsEl) statsEl.textContent = statsText.slice(0, -3);
//       if (langSel.value) updateVoices(langSel.value);
//     } catch (e) {
//       console.error("Ошибка перевода:", e);
//     }
//   });

//   langSel?.addEventListener("change", function () {
//     updateVoices(this.value);
//   });

//   function updateVoices(langCode) {
//     if (!voiceSel) return;
//     voiceSel.innerHTML = "";
//     const matchingKey = Object.keys(voicesData).find((key) => {
//       const cleanKey = key.trim().toLowerCase();
//       const cleanLang = langCode.trim().toLowerCase();
//       return cleanKey.includes(cleanLang) || cleanLang.includes(cleanKey);
//     });
//     const voicesToDisplay = matchingKey ? voicesData[matchingKey] : [];
//     if (voicesToDisplay.length > 0) {
//       const placeholder = document.createElement("option");
//       placeholder.textContent = "-- Выберите голос --";
//       placeholder.disabled = true;
//       placeholder.selected = true;
//       voiceSel.appendChild(placeholder);
//       voicesToDisplay.forEach((voice) => {
//         const opt = document.createElement("option");
//         opt.value = voice.id;
//         opt.textContent = voice.name;
//         voiceSel.appendChild(opt);
//       });
//       voiceSel.disabled = false;
//     } else {
//       voiceSel.innerHTML = `<option>Голоса не найдены для ${langCode}</option>`;
//       voiceSel.disabled = true;
//     }
//   }

//   // --- МОДЕРНИЗИРОВАННАЯ ОТПРАВКА (Реальный сервер) ---
//   form.addEventListener("submit", function (event) {
//     event.preventDefault();
//     const formData = new FormData(form);
//     const rawLang = formData.get("language");
//     const articleId = formData.get("article_id");

//     // Формируем имя папки из заголовка статьи (как ты просил)
//     const folderName = articleSel.options[articleSel.selectedIndex].text
//       .replace(/[/\\?%*:|"<>]/g, "-")
//       .trim();

//     // ШАГ 1: Реальный запрос за 10 словами
//     fetch(`?action=get_text&cluster_id=${articleId}&lang=${rawLang}`, {
//       headers: { "X-Requested-With": "XMLHttpRequest" },
//     })
//       .then((response) => response.json())
//       .then((data) => {
//         if (!data.success) throw new Error(data.error);

//         // ШАГ 2: Собираем финальный Payload для Inworld
//         const payload = {
//           article_id: formData.get("article_id"), // ID статьи
//           provider_id: formData.get("provider"), // ID провайдера из формы
//           voice_id: formData.get("voice_id"), // Выбранный голос
//           language: langMap[rawLang] || rawLang, // ru-RU
//           text: data.text, // Те самые 10 слов
//           audio_config: {
//             speaking_rate: parseFloat(formData.get("speaking_rate")) || 1.0,
//           },
//         };

//         // ШАГ 3: Реальный POST на сервер
//         return fetch(window.location.href, {
//           method: "POST",
//           body: JSON.stringify(payload),
//           headers: {
//             "Content-Type": "application/json",
//             "X-Requested-With": "XMLHttpRequest",
//             "X-CSRFToken": getCookie("csrftoken"),
//           },
//         });
//       })
//       .then((response) => response.json())
//       .then((result) => {
//         if (result.success && result.task_id) {
//           // ШАГ 4: Запуск прогресс-бара с реальным URL и ID
//           if (typeof window.startProgressTracking === "function") {
//             window.startProgressTracking(
//               "/audio/api/generation-stream/",
//               result.task_id,
//               "progress-modal",
//             );
//           }
//         } else {
//           throw new Error(result.error || "Ошибка сервера");
//         }
//       })
//       .catch((err) => {
//         console.error("Ошибка:", err);
//         if (typeof showToast === "function") showToast(err.message, "error");
//       });
//   });
// });
