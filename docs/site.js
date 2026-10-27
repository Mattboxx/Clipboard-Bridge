"use strict";

// Native dialog keeps keyboard focus inside; without JavaScript, links still work.
if (typeof HTMLDialogElement !== "undefined" && HTMLDialogElement.prototype.showModal) {
  const italian = document.documentElement.lang === "it";
  const dialog = document.createElement("dialog");
  dialog.id = "support-dialog";
  dialog.className = "support-dialog";
  dialog.setAttribute("aria-labelledby", "support-dialog-title");
  dialog.setAttribute("aria-describedby", "support-dialog-description");

  const head = document.createElement("div");
  head.className = "support-dialog-head";
  const title = document.createElement("h2");
  title.id = "support-dialog-title";
  title.textContent = italian ? "Sostieni Clipboard Bridge" : "Support Clipboard Bridge";
  const close = document.createElement("button");
  close.type = "button";
  close.className = "support-dialog-close";
  close.setAttribute("aria-label", italian ? "Chiudi" : "Close");
  close.textContent = "\u00d7";
  head.append(title, close);

  const description = document.createElement("p");
  description.id = "support-dialog-description";
  description.textContent = italian
    ? "Il tuo sostegno aiuta a mantenere e aggiornare il progetto. Grazie di cuore se scegli di contribuire! Scegli la piattaforma che preferisci."
    : "Your support helps keep the project maintained and updated. Thank you for considering a contribution! Choose the platform you prefer.";
  const providers = document.createElement("div");
  providers.className = "support-providers";
  for (const [name, url, detail] of [
    ["Ko-fi", "https://ko-fi.com/mattboxx", italian ? "Lascia una donazione su Ko-fi" : "Leave a tip on Ko-fi"],
    ["GitHub Sponsors", "https://github.com/sponsors/Mattboxx", italian ? "Sostieni il progetto su GitHub" : "Sponsor the project on GitHub"],
  ]) {
    const link = document.createElement("a");
    link.className = "support-provider";
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    const text = document.createElement("span");
    const label = document.createElement("strong");
    label.textContent = name;
    const note = document.createElement("span");
    note.className = "support-provider-note";
    note.textContent = detail;
    text.append(label, note);
    const arrow = document.createElement("img");
    arrow.src = "assets/icons/arrow-up-right.svg";
    arrow.className = "icon";
    arrow.alt = "";
    link.append(text, arrow);
    providers.append(link);
  }
  const thanks = document.createElement("p");
  thanks.className = "support-dialog-foot";
  thanks.textContent = italian
    ? "Il sostegno \u00e8 facoltativo. Clipboard Bridge resta gratuito e open source."
    : "Support is entirely optional. Clipboard Bridge stays free and open source.";
  dialog.append(head, description, providers, thanks);
  document.body.append(dialog);

  let previousFocus;
  document.querySelectorAll('[data-support-open], .tutorial-end a[href="https://ko-fi.com/mattboxx"]').forEach((trigger) => {
    trigger.setAttribute("aria-haspopup", "dialog");
    trigger.setAttribute("aria-controls", dialog.id);
    trigger.addEventListener("click", (event) => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      if (dialog.open) return;
      previousFocus = trigger;
      dialog.showModal();
      document.body.classList.add("support-dialog-open");
      close.focus();
    });
  });
  document.documentElement.classList.add("support-dialog-ready");
  close.addEventListener("click", () => dialog.close());
  dialog.addEventListener("keydown", (event) => {
    if (event.key !== "Tab" || event.ctrlKey || event.metaKey || event.altKey) return;
    const stops = [...dialog.querySelectorAll('button:not([disabled]), a[href]')];
    event.preventDefault();
    const current = stops.indexOf(document.activeElement);
    const next = (current + (event.shiftKey ? -1 : 1) + stops.length) % stops.length;
    stops[next].focus();
  });
  dialog.addEventListener("click", (event) => {
    if (event.target !== dialog) return;
    const box = dialog.getBoundingClientRect();
    if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) dialog.close();
  });
  dialog.addEventListener("close", () => {
    document.body.classList.remove("support-dialog-open");
    if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true });
  });
}

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

// Motion is progressive enhancement: no script, no hidden content.
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const revealTargets = [...document.querySelectorAll(
  ".section-heading,.grid>.item,.server-layout,.server-gallery figure,.step,.app-figure,.tray-demo,.shortcut-action,.phone-tips>*,.faq-layout details,#support .inner"
)];
if ("IntersectionObserver" in window && !reducedMotion.matches) {
  try {
    const reveal = new IntersectionObserver((entries) => {
      entries.forEach(({ target, isIntersecting }) => {
        if (isIntersecting) {
          target.classList.add("is-visible");
          reveal.unobserve(target);
        }
      });
    }, { threshold: 0.06 });
    revealTargets.forEach((target, index) => {
      target.classList.add("reveal-enter");
      target.style.setProperty("--reveal-delay", `${(index % 3) * 55}ms`);
      reveal.observe(target);
    });
    document.documentElement.classList.add("motion-enabled");
    reducedMotion.addEventListener?.("change", () => {
      if (reducedMotion.matches) {
        document.documentElement.classList.remove("motion-enabled");
        reveal.disconnect();
      }
    });
  } catch {
    document.documentElement.classList.remove("motion-enabled");
  }
}

const readingProgress = document.createElement("div");
readingProgress.className = "reading-progress";
readingProgress.setAttribute("aria-hidden", "true");
document.body.append(readingProgress);
const sectionLinks = [...document.querySelectorAll('.nav-links a[href^="#"]')];
let scrollFrame = 0;
function reflectScroll() {
  scrollFrame = 0;
  const distance = document.documentElement.scrollHeight - innerHeight;
  readingProgress.style.transform = `scaleX(${distance > 0 ? Math.min(1, scrollY / distance) : 0})`;
  let active;
  sectionLinks.forEach((link) => {
    const section = document.getElementById(link.hash.slice(1));
    if (section && section.getBoundingClientRect().top < innerHeight * .45) active = link;
  });
  sectionLinks.forEach((link) => {
    if (link === active) link.setAttribute("aria-current", "location");
    else link.removeAttribute("aria-current");
  });
}
function queueScroll() {
  if (!scrollFrame) scrollFrame = requestAnimationFrame(reflectScroll);
}
addEventListener("scroll", queueScroll, { passive: true });
addEventListener("resize", queueScroll);
queueScroll();

// A request acknowledgement, not a claim that the browser finished downloading.
const feedback = document.createElement("div");
feedback.className = "download-feedback";
feedback.hidden = true;
const downloadMessage = document.createElement("span");
downloadMessage.setAttribute("role", "status");
downloadMessage.setAttribute("aria-live", "polite");
const dismissDownload = document.createElement("button");
dismissDownload.type = "button";
dismissDownload.textContent = "\u00d7";
dismissDownload.setAttribute("aria-label", document.documentElement.lang === "it" ? "Chiudi avviso download" : "Dismiss download notice");
feedback.append(downloadMessage, dismissDownload);
document.body.append(feedback);
dismissDownload.addEventListener("click", () => { feedback.hidden = true; });
document.querySelectorAll('a[href^="https://github.com/Mattboxx/Clipboard-Bridge/releases/download/"]').forEach((link) => {
  link.addEventListener("click", () => {
    const italian = document.documentElement.lang === "it";
    const windows = link.pathname.endsWith(".exe");
    downloadMessage.textContent = italian
      ? (windows ? "Download richiesto. I file Windows non sono firmati: potrebbe essere necessaria un'autorizzazione di Windows." : "Download richiesto. Il browser gestisce il salvataggio del file.")
      : (windows ? "Download requested. Windows files are unsigned; Windows may require your approval." : "Download requested. Your browser handles saving the file.");
    feedback.hidden = false;
  });
});
