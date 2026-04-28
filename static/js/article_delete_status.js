// document.addEventListener('DOMContentLoaded', function() {
//         // Получаем элементы по точным ID из твоего HTML
//         const selectAll = document.getElementById('select-all');
//         const checkboxes = document.querySelectorAll('.idea-checkbox');
//         const rows = document.querySelectorAll('.idea-row');
        
//         // Кнопки и селекты
//         const btnDelete = document.getElementById('btn-delete');
//         const btnStatus = document.getElementById('btn-status');
//         const statusSelect = document.getElementById('status-select');
        
//         // Счетчик (если есть в HTML)
//         const countLabel = document.getElementById('selection-count');
//         const countVal = document.getElementById('count-val');

//         // Функция обновления состояния кнопок
//         function updateControls() {
//             // Считаем сколько галочек стоит
//             let checkedCount = 0;
//             checkboxes.forEach(cb => {
//                 if (cb.checked) checkedCount++;
//             });
            
//             const hasSelection = checkedCount > 0;

//             // Включаем/выключаем кнопки в зависимости от выбора
//             if (btnDelete) btnDelete.disabled = !hasSelection;
//             if (btnStatus) btnStatus.disabled = !hasSelection;
//             if (statusSelect) statusSelect.disabled = !hasSelection;

//             // Показываем счетчик
//             if (countLabel && countVal) {
//                 if (hasSelection) {
//                     countLabel.style.display = 'inline';
//                     countVal.textContent = checkedCount;
//                 } else {
//                     countLabel.style.display = 'none';
//                 }
//             }

//             // Подсветка строк
//             checkboxes.forEach((cb, index) => {
//                 if (rows[index]) {
//                     if (cb.checked) {
//                         rows[index].style.backgroundColor = 'rgba(0, 123, 255, 0.05)'; // Легкая подсветка
//                     } else {
//                         rows[index].style.backgroundColor = ''; // Сброс фона
//                         // Возвращаем прозрачность для пустых строк, если нужно
//                         const titleCell = rows[index].querySelector('.text-bold span');
//                         if (titleCell && titleCell.textContent.includes('Нет данных')) {
//                             rows[index].style.opacity = '0.6';
//                         } else {
//                             rows[index].style.opacity = '1';
//                         }
//                     }
//                 }
//             });
//         }

//         // Слушатель на "Выбрать все"
//         if (selectAll) {
//             selectAll.addEventListener('change', function() {
//                 checkboxes.forEach(cb => {
//                     cb.checked = selectAll.checked;
//                 });
//                 updateControls();
//             });
//         }

//         // Слушатели на отдельные чекбоксы
//         checkboxes.forEach((cb) => {
//             cb.addEventListener('change', function() {
//                 // Если сняли галочку с одного, снимаем с "Выбрать все"
//                 if (!cb.checked && selectAll) {
//                     selectAll.checked = false;
//                 }
//                 // Если выбрали все вручную, ставим галочку на "Выбрать все"
//                 if (selectAll) {
//                     const allChecked = Array.from(checkboxes).every(c => c.checked);
//                     selectAll.checked = allChecked;
//                 }
//                 updateControls();
//             });
//         });
        
//         // Запуск при загрузке, чтобы заблокировать кнопки сразу
//         updateControls();
//     });

    document.addEventListener('DOMContentLoaded', function() {
        const selectAll = document.getElementById('select-all');
        // Ищем чекбоксы внутри формы (класс idea-checkbox или имя selected_ideas)
        const checkboxes = document.querySelectorAll('input[name="selected_ideas"]'); 
        const rows = document.querySelectorAll('.idea-row');
        
        const btnDelete = document.getElementById('btn-delete');
        const btnStatus = document.getElementById('btn-status');
        const statusSelect = document.getElementById('status-select');
        const countLabel = document.getElementById('selection-count');
        const countVal = document.getElementById('count-val');

        function updateControls() {
            let checkedCount = 0;
            checkboxes.forEach(cb => { if (cb.checked) checkedCount++; });
            
            const hasSelection = checkedCount > 0;

            if (btnDelete) btnDelete.disabled = !hasSelection;
            if (btnStatus) btnStatus.disabled = !hasSelection;
            if (statusSelect) statusSelect.disabled = !hasSelection;

            if (countLabel && countVal) {
                if (hasSelection) {
                    countLabel.style.display = 'inline';
                    countVal.textContent = checkedCount;
                } else {
                    countLabel.style.display = 'none';
                }
            }

            // Подсветка строк
            checkboxes.forEach((cb, index) => {
                if (rows[index]) {
                    rows[index].style.backgroundColor = cb.checked ? 'rgba(0, 123, 255, 0.05)' : '';
                }
            });
        }

        if (selectAll) {
            selectAll.addEventListener('change', function() {
                checkboxes.forEach(cb => { cb.checked = selectAll.checked; });
                updateControls();
            });
        }

        checkboxes.forEach(cb => {
            cb.addEventListener('change', function() {
                if (!cb.checked && selectAll) selectAll.checked = false;
                if (selectAll) {
                    selectAll.checked = Array.from(checkboxes).every(c => c.checked);
                }
                updateControls();
            });
        });
        
        updateControls();
    });
