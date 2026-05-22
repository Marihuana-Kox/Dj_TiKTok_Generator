document.addEventListener("DOMContentLoaded", function () {
  // 1. Ищем элементы по твоим точным ID и классам
  const selectAllCheckbox = document.getElementById("select-all"); // Главный чекбокс
  const projectCheckboxes = document.querySelectorAll(".idea-checkbox"); // Остальные чекбоксы
  const deleteBtn = document.getElementById("btn-delete"); // Кнопка удаления
  const regenBtn = document.getElementById("btn-regen"); // Кнопка перегенерации ошибок
  const massForm = document.getElementById("dashboard-form"); // Твоя форма (проверь её ID в HTML)

  // 2. Функция управления состоянием кнопок
  function toggleActionComponents() {
    // Проверяем, выбран ли ХОТЯ БЫ ОДИН чекбокс в таблице
    const anyChecked = Array.from(projectCheckboxes).some((cb) => cb.checked);

    // Включаем или выключаем кнопки напрямую через свойство disabled
    if (deleteBtn) {
      deleteBtn.disabled = !anyChecked;
    }
    if (regenBtn) {
      regenBtn.disabled = !anyChecked;
    }
  }

  // 3. Логика главного чекбокса "Выбрать все"
  if (selectAllCheckbox && projectCheckboxes.length > 0) {
    selectAllCheckbox.addEventListener("change", function () {
      projectCheckboxes.forEach((cb) => {
        cb.checked = selectAllCheckbox.checked;
      });
      toggleActionComponents();
    });
  }

  // 4. Логика одиночных чекбоксов в строках таблицы
  if (selectAllCheckbox && projectCheckboxes.length > 0) {
    projectCheckboxes.forEach((cb) => {
      cb.addEventListener("change", function () {
        if (!cb.checked) {
          selectAllCheckbox.checked = false;
        } else {
          const allChecked = Array.from(projectCheckboxes).every(
            (item) => item.checked,
          );
          selectAllCheckbox.checked = allChecked;
        }
        toggleActionComponents();
      });
    });
  }

  // 5. Безопасный перехват отправки формы (подтверждение для удаления)
  if (massForm) {
    massForm.addEventListener("submit", function (e) {
      // Кликнули на кнопку удаления? (Проверяем по нажатому элементу или значению)
      const submitter = e.submitter;
      if (submitter && submitter.value === "delete_selected") {
        if (
          !confirm(
            "⚠️ Вы уверены, что хотите безвозвратно удалить выбранные проекты? Все файлы и треки внутри них будут удалены.",
          )
        ) {
          e.preventDefault(); // Отменяем отправку, если пользователь нажал "Отмена"
        }
      }
    });
  }
});
