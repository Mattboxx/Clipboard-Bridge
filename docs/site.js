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
