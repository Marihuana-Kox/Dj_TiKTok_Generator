// ============================================================================
// СЧЁТЧИК СЛОВ — только для форм с текстовыми полями
// ============================================================================

document.addEventListener("DOMContentLoaded", function () {
  const blocks = document.querySelectorAll('[id^="block-"]');

  blocks.forEach((block) => {
    const textarea = block.querySelector('textarea[name="content"]');
    const wordsEl = block.querySelector(".wc-words");
    const charsEl = block.querySelector(".wc-chars");

    if (textarea && wordsEl && charsEl) {
      const updateCounts = () => {
        const text = textarea.value;
        const words = text
          .trim()
          .split(/\s+/)
          .filter((w) => w.length > 0).length;
        const chars = text.length;

        wordsEl.innerText = words;
        charsEl.innerText = chars;
      };

      textarea.addEventListener("input", updateCounts);
      updateCounts(); // Initial count
    }
  });
});

// console.log('✅ word_counter.js загружен');
