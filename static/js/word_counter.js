document.addEventListener('DOMContentLoaded', function() {
    // 1. Ищем ВСЕ элементы, у которых ID начинается со слова "block-"
    // Это найдет и #block-ru, и #block-en, и любые другие
    const blocks = document.querySelectorAll('[id^="block-"]');

    blocks.forEach(block => {
        // 2. Внутри КАЖДОГО найденного блока ищем элементы
        // Теперь поиск идет строго внутри конкретного block
        const textarea = block.querySelector('textarea[name="content"]');
        const wordsEl = block.querySelector('.wc-words');
        const charsEl = block.querySelector('.wc-chars');

        // 3. Если всё найдено — вешаем логику
        if (textarea && wordsEl && charsEl) {
            
            const updateCounts = () => {
                const text = textarea.value;
                // Считаем слова
                const words = text.trim().split(/\s+/).filter(w => w.length > 0).length;
                // Считаем символы
                const chars = text.length;
                
                // Обновляем цифры ТОЛЬКО в этом блоке
                wordsEl.innerText = words;
                charsEl.innerText = chars;
            };

            // Слушаем ввод
            textarea.addEventListener('input', updateCounts);
        }
    });
});