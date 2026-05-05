document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('form[method="post"]');
    const submitBtn = document.querySelector('button[type="submit"]');
    
    if (form) {
        console.log('✅ Форма найдена');
        
        form.addEventListener('submit', function(e) {
            console.log('🚀 ФОРМА ОТПРАВЛЯЕТСЯ!');
            console.log('Provider:', document.querySelector('[name="provider"]')?.value);
            console.log('Article:', document.querySelector('[name="article_id"]')?.value);
            console.log('Gen Mode:', document.querySelector('[name="gen_mode"]:checked')?.value);
        }, true); // true = capture phase, ловим до других обработчиков
    } else {
        console.error('❌ ФОРМА НЕ НАЙДЕНА!');
    }
    
    if (submitBtn) {
        submitBtn.addEventListener('click', function() {
            console.log('🖱️ Кнопка нажата');
        });
    }
});