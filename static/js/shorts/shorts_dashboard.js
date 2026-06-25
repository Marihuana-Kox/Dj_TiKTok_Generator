document.addEventListener('DOMContentLoaded', function() {
    const selectAll = document.getElementById('select-all');
    const checkboxes = document.querySelectorAll('.row-checkbox');
    const btnDelete = document.getElementById('btn-delete');
    const statusSelect = document.getElementById('status-select');
    const btnStatus = document.getElementById('btn-status');
    const form = document.getElementById('bulk-action-form');

    // Функция обновления состояния кнопок
    function updateButtons() {
        const checkedCount = document.querySelectorAll('.row-checkbox:checked').length;
        const hasChecked = checkedCount > 0;
        const hasStatus = statusSelect && statusSelect.value !== "";

        // Включаем/выключаем кнопки в зависимости от выбора
        if (btnDelete) btnDelete.disabled = !hasChecked;
        if (statusSelect) statusSelect.disabled = !hasChecked;
        if (btnStatus) btnStatus.disabled = !(hasChecked && hasStatus);
    }

    // Обработчик "Выбрать все"
    if (selectAll) {
        selectAll.addEventListener('change', function() {
            checkboxes.forEach(cb => {
                cb.checked = selectAll.checked;
            });
            updateButtons();
        });
    }

    // Обработчик отдельных чекбоксов
    checkboxes.forEach(cb => {
        cb.addEventListener('change', function() {
            // Если сняли галочку с одного, снимаем и с "Выбрать все"
            if (!this.checked && selectAll) {
                selectAll.checked = false;
            }
            // Если выбрали все вручную, ставим галочку на "Выбрать все"
            const allChecked = Array.from(checkboxes).every(c => c.checked);
            if (allChecked && selectAll && checkboxes.length > 0) {
                selectAll.checked = true;
            }
            updateButtons();
        });
    });

    // Обработчик изменения статуса в селекте
    if (statusSelect) {
        statusSelect.addEventListener('change', updateButtons);
    }

    // Инициализация при загрузке страницы
    updateButtons();

    // Дополнительная защита от случайного удаления при отправке формы
    if (form) {
        form.addEventListener('submit', function(e) {
            const activeElement = document.activeElement;
            if (activeElement && activeElement.name === 'action' && activeElement.value === 'delete_selected') {
                if (!confirm('⚠️ Вы уверены? Это действие нельзя отменить.\nВыбрано записей: ' + document.querySelectorAll('.row-checkbox:checked').length)) {
                    e.preventDefault();
                }
            }
        });
    }
});