(function () {
  const page = document.body.dataset.page || "";
  const shell = document.getElementById("site-shell");
  const footer = document.getElementById("site-footer");
  const iconSymbols = {
    custom_agent: `<symbol id="icon-custom_agent" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="5" width="17" height="12" rx="3"></rect><path d="M8 19.5h8"></path><path d="M9.5 9.5 8 11l1.5 1.5"></path><path d="m14.5 9.5 1.5 1.5-1.5 1.5"></path><path d="m12.8 8.7-1.6 4.6"></path></symbol>`,
    job_hunter: `<symbol id="icon-job_hunter" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M8 7V6a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v1"></path><rect x="4" y="7" width="16" height="11" rx="3"></rect><path d="M4.5 11.5h15"></path><path d="M10 13.5h4"></path></symbol>`,
    deal_finder: `<symbol id="icon-deal_finder" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="m12.5 3.5 7 7-8.5 8.5a2 2 0 0 1-2.8 0l-3.2-3.2a2 2 0 0 1 0-2.8z"></path><circle cx="14.6" cy="8.4" r="1.2"></circle><path d="M7 14h4"></path><path d="M9 12v4"></path></symbol>`,
    inbox_triage: `<symbol id="icon-inbox_triage" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8.5 7.5 5h9L20 8.5V18a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z"></path><path d="M4 12h4l1.5 2h5L16 12h4"></path><path d="M9 9.5h6"></path></symbol>`,
    social_poster: `<symbol id="icon-social_poster" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="m5 17 9-4.5L5 8v4l6 1-6 1z"></path><path d="M14 8.5h3.5a1.5 1.5 0 0 1 0 3H14"></path><path d="M14 15.5h5"></path></symbol>`,
    researcher: `<symbol id="icon-researcher" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="4.5"></circle><path d="m15 15 4 4"></path><path d="M7 11h8"></path><path d="M11 7v8"></path></symbol>`,
    lead_tracker: `<symbol id="icon-lead_tracker" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="5" width="8" height="14" rx="2.5"></rect><path d="M7 9h2"></path><path d="M6.5 12h3"></path><path d="M16 7v10"></path><path d="M13.5 10h5"></path><path d="M13.5 14h5"></path><path d="m17 5 2 2-2 2"></path></symbol>`,
    meeting_prep: `<symbol id="icon-meeting_prep" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="5" width="10" height="13" rx="2.5"></rect><path d="M7 3.5v3"></path><path d="M11 3.5v3"></path><path d="M6.5 10h5"></path><path d="M6.5 13h3.5"></path><path d="M16.5 9.5H20"></path><path d="M16.5 13H20"></path><path d="M16.5 16.5H20"></path></symbol>`,
    support_triage: `<symbol id="icon-support_triage" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M5 7.5A2.5 2.5 0 0 1 7.5 5h9A2.5 2.5 0 0 1 19 7.5v6A2.5 2.5 0 0 1 16.5 16H11l-3.5 3V16h0A2.5 2.5 0 0 1 5 13.5z"></path><path d="M8.5 9.5h7"></path><path d="M8.5 12.5h4.5"></path><path d="m17.5 6.5 1 1 1.5-1.5"></path></symbol>`,
    invoice_collector: `<symbol id="icon-invoice_collector" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M7 4.5h8l3 3V18a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6.5a2 2 0 0 1 2-2z"></path><path d="M15 4.5V8h3"></path><path d="M8.5 11h7"></path><path d="M8.5 14h7"></path><path d="M8.5 17h4"></path></symbol>`,
    marketplace_monitor: `<symbol id="icon-marketplace_monitor" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="6" width="12" height="10" rx="2.5"></rect><path d="M7 10.5h6"></path><path d="M7 13.5h4"></path><circle cx="17.5" cy="16.5" r="2.5"></circle><path d="m19.3 18.3 1.7 1.7"></path></symbol>`,
    morning_digest: `<symbol id="icon-morning_digest" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M5 16a7 7 0 0 1 14 0"></path><path d="M3.5 16h17"></path><path d="M12 5v3"></path><path d="m7.8 7.2 1.7 1.7"></path><path d="m16.2 7.2-1.7 1.7"></path></symbol>`,
    download: `<symbol id="icon-download" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4.5v9"></path><path d="m8.5 10.5 3.5 3.5 3.5-3.5"></path><path d="M5 18.5h14"></path></symbol>`
  };

  const navItems = [
    { href: "/", label: "Home", page: "home" },
    { href: "/agents/", label: "Build Your Own", page: "agents" },
    { href: "/templates/", label: "Agents", page: "catalog" },
    { href: "/changelog/", label: "Changelog", page: "changelog" },
    { href: "/install.html", label: "Install", page: "install" },
    { href: "/privacy.html", label: "Privacy", page: "privacy" }
  ];

  function renderIconSprite() {
    if (document.getElementById("ctxant-icons")) return;
    const sprite = document.createElement("div");
    sprite.innerHTML = `
      <svg id="ctxant-icons" xmlns="http://www.w3.org/2000/svg" style="position:absolute;width:0;height:0;overflow:hidden" aria-hidden="true" focusable="false">
        ${Object.values(iconSymbols).join("")}
      </svg>
    `;
    document.body.prepend(sprite.firstElementChild);
  }

  function renderIcon(name, label, className = "agent-icon") {
    if (!name || !iconSymbols[name]) return "";
    const safeLabel = label ? ` aria-label="${label.replace(/"/g, "&quot;")}"` : ` aria-hidden="true"`;
    return `<span class="${className}"${safeLabel}><svg viewBox="0 0 24 24" role="img"><use href="#icon-${name}"></use></svg></span>`;
  }

  function renderShell() {
    if (!shell) return;
    shell.innerHTML = `
      <div class="site-backdrop" aria-hidden="true">
        <div class="site-glow glow-a"></div>
        <div class="site-glow glow-b"></div>
      </div>
      <header class="site-header" id="site-header">
        <div class="shell header-inner">
          <a class="brand-lockup" href="/">
            <span class="brand-mark" aria-hidden="true"></span>
            <span class="brand-copy">
              <strong>CtxAnt</strong>
              <span>Browser agents for your real Chrome</span>
            </span>
          </a>
          <nav class="header-nav" id="header-nav">
            ${navItems.map(item => `
              <a href="${item.href}" class="${item.page === page ? "is-active" : ""}">${item.label}</a>
            `).join("")}
          </nav>
          <a class="header-download" href="/install.html">
            <span>Download</span>
            ${renderIcon("download", "Download", "header-download-icon")}
          </a>
          <button class="header-menu" id="header-menu" type="button" aria-label="Toggle navigation">Menu</button>
        </div>
      </header>
    `;
  }

  function renderFooter() {
    if (!footer) return;
    footer.innerHTML = `
      <footer class="site-footer">
        <div class="shell footer-inner">
          <div>© 2026 Chams Bouzaiene. Local browser agents for real Chrome.</div>
          <div class="footer-links">
            <a href="/">Home</a>
            <a href="/agents/">Build Your Own</a>
            <a href="/templates/">Agents</a>
            <a href="/changelog/">Changelog</a>
            <a href="/privacy.html">Privacy</a>
            <a href="https://github.com/ChamsBouzaiene/CtxAnt" target="_blank" rel="noopener">GitHub</a>
          </div>
        </div>
      </footer>
    `;
  }

  function attachHeaderBehavior() {
    const header = document.getElementById("site-header");
    const menu = document.getElementById("header-menu");
    const nav = document.getElementById("header-nav");
    if (!header) return;

    const sync = () => header.classList.toggle("is-scrolled", window.scrollY > 16);
    sync();
    window.addEventListener("scroll", sync, { passive: true });

    if (menu && nav) {
      menu.addEventListener("click", () => {
        document.body.classList.toggle("nav-open");
      });
      nav.addEventListener("click", (event) => {
        if (event.target instanceof HTMLElement && event.target.tagName === "A") {
          document.body.classList.remove("nav-open");
        }
      });
    }
  }

  let revealObserver = null;

  function revealNodes(root) {
    const nodes = (root || document).querySelectorAll("[data-reveal]");
    nodes.forEach((node, index) => {
      if (!node.classList.contains("reveal")) {
        node.classList.add("reveal");
        node.style.setProperty("--delay", `${Math.min(index % 8, 6) * 70}ms`);
      }
      if (!revealObserver) {
        node.classList.add("is-visible");
      } else if (!node.classList.contains("is-visible")) {
        revealObserver.observe(node);
      }
    });
  }

  function attachRevealObserver() {
    if ("IntersectionObserver" in window) {
      revealObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            revealObserver.unobserve(entry.target);
          }
        });
      }, { threshold: 0.16 });
    }
    revealNodes(document);
    document.addEventListener("ctxant:refresh-reveal", () => revealNodes(document));
  }

  function attachPointerParallax() {
    const zone = document.querySelector("[data-parallax-zone]");
    const targets = document.querySelectorAll("[data-parallax]");
    if (!zone || !targets.length || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }
    zone.addEventListener("pointermove", (event) => {
      const rect = zone.getBoundingClientRect();
      const x = ((event.clientX - rect.left) / rect.width) - 0.5;
      const y = ((event.clientY - rect.top) / rect.height) - 0.5;
      targets.forEach((target) => {
        const depth = Number(target.getAttribute("data-parallax")) || 1;
        target.style.setProperty("--mx", `${x * depth * 18}`);
        target.style.setProperty("--my", `${y * depth * 18}`);
      });
    });
    zone.addEventListener("pointerleave", () => {
      targets.forEach((target) => {
        target.style.setProperty("--mx", "0");
        target.style.setProperty("--my", "0");
      });
    });
  }

  function wireCopyButtons() {
    document.querySelectorAll(".copy-btn[data-copy-target]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const selector = btn.getAttribute("data-copy-target");
        const target = selector ? document.querySelector(selector) : null;
        if (!target) return;
        const text = target.textContent.trim();
        const done = () => {
          const original = btn.textContent;
          btn.textContent = "Copied";
          btn.classList.add("copied");
          setTimeout(() => {
            btn.textContent = original;
            btn.classList.remove("copied");
          }, 1200);
        };
        try {
          await navigator.clipboard.writeText(text);
          done();
        } catch (_error) {
          const range = document.createRange();
          range.selectNodeContents(target);
          const selection = window.getSelection();
          selection.removeAllRanges();
          selection.addRange(range);
          try {
            document.execCommand("copy");
            done();
          } catch (_execError) {
          }
          selection.removeAllRanges();
        }
      });
    });
  }

  renderShell();
  renderFooter();
  renderIconSprite();
  attachHeaderBehavior();
  attachRevealObserver();
  attachPointerParallax();
  wireCopyButtons();
  window.CtxAntUI = Object.assign(window.CtxAntUI || {}, { renderIcon });
})();
