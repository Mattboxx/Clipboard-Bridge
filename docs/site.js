"use strict";

document.querySelectorAll("[data-apple-image]").forEach((image) => {
  const showFallback = () => {
    image.hidden = true;
    image.closest(".apple-shot").querySelector(".apple-image-fallback").hidden = false;
  };
  image.addEventListener("error", showFallback, { once: true });
  if (image.complete && !image.naturalWidth) showFallback();
});

document.querySelectorAll("[data-copy]").forEach((button) => {
  button.addEventListener("click", async () => {
    const command = document.getElementById(button.dataset.copy);
    const status = button.closest(".server-install").querySelector(".copy-status");
    button.disabled = true;
    try {
      await navigator.clipboard.writeText(command.textContent.trim());
      status.textContent = "Copied";
    } catch {
      const range = document.createRange();
      range.selectNodeContents(command);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      status.textContent = "Command selected. Copy it to continue.";
    } finally {
      button.disabled = false;
    }
  });
});
