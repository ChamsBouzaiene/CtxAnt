(function () {
  const page = document.body.dataset.page || "";
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
    morning_digest: `<symbol id="icon-morning_digest" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M5 16a7 7 0 0 1 14 0"></path><path d="M3.5 16h17"></path><path d="M12 5v3"></path><path d="m7.8 7.2 1.7 1.7"></path><path d="m16.2 7.2-1.7 1.7"></path></symbol>`
  };

  function esc(value) {
    if (value == null) return "";
    const div = document.createElement("div");
    div.textContent = String(value);
    return div.innerHTML;
  }

  function renderSprite() {
    if (document.getElementById("ctxant-dashboard-icons")) return;
    const wrapper = document.createElement("div");
    wrapper.innerHTML = `<svg id="ctxant-dashboard-icons" xmlns="http://www.w3.org/2000/svg" style="position:absolute;width:0;height:0;overflow:hidden" aria-hidden="true">${Object.values(iconSymbols).join("")}</svg>`;
    document.body.prepend(wrapper.firstElementChild);
  }

  function renderIcon(icon, emoji, label) {
    if (icon && iconSymbols[icon]) {
      return `<span class="agent-icon" aria-label="${esc(label)}"><svg viewBox="0 0 24 24" role="img"><use href="#icon-${icon}"></use></svg></span>`;
    }
    return `<span class="agent-icon fallback" aria-hidden="true">${esc(emoji || "🤖")}</span>`;
  }

  function renderItems(items) {
    if (!items || !items.length) {
      return `<p class="detail-note">Nothing added here yet.</p>`;
    }
    return `<div class="detail-list">${items.map((item) => `<div class="detail-item"><div>${esc(item)}</div></div>`).join("")}</div>`;
  }

  function renderCommands(commands) {
    if (!commands || !commands.length) {
      return `<p class="detail-note">No command guidance yet.</p>`;
    }
    return `<div class="command-list">${commands.map((item) => `
      <div class="command-card">
        <strong><code>${esc(item.cmd)}</code></strong>
        <div class="detail-note">${esc(item.description)}</div>
      </div>
    `).join("")}</div>`;
  }

  function renderExamples(examples) {
    if (!examples || !examples.length) {
      return `<div class="empty-state compact">No examples yet.</div>`;
    }
    return `<div class="examples-grid">${examples.map((example) => `
      <article class="example-card">
        <h3>${esc(example.title)}</h3>
        <p>${esc(example.what || "")}</p>
        <div class="example-block">
          <strong>How to use it</strong>
          ${renderItems(example.setup || [])}
        </div>
        ${example.prompt ? `<div class="example-block"><strong>Example message</strong><code>${esc(example.prompt)}</code></div>` : ""}
        ${example.schedule ? `<div class="example-block"><strong>Schedule</strong><code>${esc(example.schedule)}</code></div>` : ""}
        ${example.result ? `<div class="example-block"><strong>Expected result</strong><p>${esc(example.result)}</p></div>` : ""}
      </article>
    `).join("")}</div>`;
  }

  function setHubActions(state) {
    const hubInfo = document.getElementById("hubInfo");
    const hubAction = document.getElementById("hubAction");
    if (!hubInfo || !hubAction) return;
    const username = state.hub && state.hub.username ? state.hub.username : "";
    if (username) {
      hubInfo.innerHTML = `Hub ready at <a href="https://t.me/${esc(username)}" target="_blank" rel="noopener">@${esc(username)}</a>`;
      hubAction.href = `https://t.me/${username}`;
      hubAction.removeAttribute("aria-disabled");
    } else {
      hubInfo.textContent = "Hub bot is still being prepared on this machine.";
      hubAction.href = "#";
      hubAction.setAttribute("aria-disabled", "true");
    }
  }

  function renderSummary(summary) {
    const root = document.getElementById("summaryStrip");
    if (!root) return;
    root.innerHTML = `
      <div class="summary-card">
        <span class="label">Deployed</span>
        <strong>${esc(summary.deployed_count || 0)}</strong>
        <p>Agents currently live in Telegram.</p>
      </div>
      <div class="summary-card">
        <span class="label">Scheduled</span>
        <strong>${esc(summary.scheduled_count || 0)}</strong>
        <p>Recurring jobs already running from this Mac.</p>
      </div>
      <div class="summary-card">
        <span class="label">Hub readiness</span>
        <strong>${summary.hub_ready ? "Ready" : "Pending"}</strong>
        <p>${summary.hub_ready ? "Starter agents can be deployed immediately." : "The control bot still needs a username."}</p>
      </div>
      <div class="summary-card">
        <span class="label">Browser session</span>
        <strong>${summary.browser_connected ? "Connected" : "Waiting"}</strong>
        <p>${esc(summary.browser_message || "No browser session connected.")}</p>
      </div>
    `;
  }

  function renderDeployed(list) {
    const root = document.getElementById("deployedList");
    if (!root) return;
    if (!list || !list.length) {
      root.innerHTML = `<div class="empty-state"><strong>No agents deployed yet.</strong><p>Use the quick deploy rail to launch a starter agent, then come back here to monitor schedules and live bot links.</p></div>`;
      return;
    }
    root.innerHTML = `<div class="stack">${list.map((agent) => {
      const tgUrl = agent.username ? `https://t.me/${encodeURIComponent(agent.username)}` : "";
      const statusClass = agent.status === "scheduled" ? "is-scheduled" : "is-ready";
      const schedules = (agent.schedules || []).length
        ? `<div class="schedule-list">${agent.schedules.slice(0, 3).map((schedule) => `
            <div class="schedule-row">
              <span><code>${esc(schedule.cron)}</code></span>
              <span>${schedule.id ? `#${esc(schedule.id)}` : ""}</span>
            </div>
          `).join("")}${agent.schedule_count > 3 ? `<div class="detail-note">+${esc(agent.schedule_count - 3)} more schedules</div>` : ""}</div>`
        : `<div class="detail-note">No schedules yet. Add one with <code>/schedule &lt;when&gt;</code> in the agent chat.</div>`;
      return `
        <article class="agent-card">
          <div class="agent-card-header">
            <div class="agent-main">
              ${renderIcon(agent.icon, agent.emoji, agent.display_name)}
              <div class="agent-title-block">
                <h3>${esc(agent.display_name)}</h3>
                <div class="agent-subline">${agent.username ? `@${esc(agent.username)}` : "Telegram username not set yet"} · <code>${esc(agent.slug)}</code></div>
                ${agent.description ? `<p class="detail-note">${esc(agent.description)}</p>` : ""}
                <div class="meta-row">
                  <span class="chip">${agent.custom ? "Custom agent" : "Starter agent"}</span>
                  <span class="chip">${esc(agent.schedule_count || 0)} schedules</span>
                  <span class="chip">${esc(agent.schedule_preview || "No schedules yet")}</span>
                </div>
              </div>
            </div>
            <span class="status-pill ${statusClass}">${esc(agent.status_label || "Ready")}</span>
          </div>
          ${schedules}
          <div class="agent-actions">
            <a class="btn btn-primary" href="/dashboard/agent/${encodeURIComponent(agent.slug)}">View details</a>
            ${tgUrl ? `<a class="btn btn-secondary" href="${tgUrl}" target="_blank" rel="noopener">Open Telegram</a>` : `<span class="btn btn-secondary is-disabled" aria-disabled="true">Open Telegram</span>`}
          </div>
        </article>
      `;
    }).join("")}</div>`;
  }

  function renderDeployable(state) {
    const root = document.getElementById("deployableList");
    if (!root) return;
    const list = state.deployable || [];
    if (!list.length) {
      root.innerHTML = `<div class="empty-state compact">All starter agents are already deployed on this machine.</div>`;
      return;
    }
    const hubUsername = state.hub && state.hub.username ? state.hub.username : "";
    root.innerHTML = `<div class="stack">${list.map((agent) => {
      const deployUrl = hubUsername ? `https://t.me/${hubUsername}?start=deploy_${encodeURIComponent(agent.slug)}` : "";
      return `
        <article class="rail-card">
          <div class="rail-card-header">
            <div class="agent-main">
              ${renderIcon(agent.icon, agent.emoji, agent.display_name)}
              <div class="agent-title-block">
                <h3>${esc(agent.display_name)}</h3>
                <p class="detail-note">${esc(agent.description || "Starter agent ready to deploy.")}</p>
              </div>
            </div>
          </div>
          <div class="rail-card-actions">
            <a class="btn btn-secondary" href="/dashboard/agent/${encodeURIComponent(agent.slug)}">Details</a>
            ${deployUrl ? `<a class="btn btn-primary" href="${deployUrl}" target="_blank" rel="noopener">Deploy</a>` : `<span class="btn btn-primary is-disabled" aria-disabled="true">Deploy</span>`}
          </div>
        </article>
      `;
    }).join("")}</div>`;
  }

  async function refreshDashboard() {
    const updated = document.getElementById("updatedAt");
    try {
      const response = await fetch("/api/state");
      if (!response.ok) throw new Error("bad response");
      const state = await response.json();
      setHubActions(state);
      renderSummary(state.summary || {});
      renderDeployed(state.deployed || []);
      renderDeployable(state);
      if (updated) {
        updated.textContent = `Last refreshed ${new Date().toLocaleTimeString()}`;
      }
    } catch (_error) {
      if (updated) {
        updated.textContent = "Could not refresh dashboard state. Check that the backend is still running.";
      }
    }
  }

  async function renderAgentDetailPage() {
    const slug = document.body.dataset.slug;
    const root = document.getElementById("agentDetailApp");
    if (!slug || !root) return;
    try {
      const response = await fetch(`/api/agent/${encodeURIComponent(slug)}`);
      if (!response.ok) throw new Error("bad response");
      const agent = await response.json();
      const tgUrl = agent.username ? `https://t.me/${agent.username}` : "";
      const deployUrl = agent.deploy_url || "";
      const schedules = agent.schedules || [];
      root.className = "";
      root.innerHTML = `
        <section class="detail-hero">
          <article class="detail-panel detail-main">
            <div class="detail-main-head">
              <div class="detail-identity">
                ${renderIcon(agent.icon, agent.emoji, agent.name || slug)}
                <div class="detail-text-block">
                  <div class="eyebrow">${agent.custom ? "Custom agent" : "Starter agent"}</div>
                  <h1>${esc(agent.name || slug)}</h1>
                  <p class="lede">${esc(agent.long_description || agent.tagline || "")}</p>
                  <div class="chip-row">
                    ${(agent.chips || []).map((chip) => `<span class="chip">${esc(chip)}</span>`).join("")}
                    <span class="chip">${agent.deployed ? "Deployed" : "Not deployed"}</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="detail-actions">
              ${tgUrl ? `<a class="btn btn-primary" href="${tgUrl}" target="_blank" rel="noopener">Open in Telegram</a>` : ""}
              ${deployUrl ? `<a class="btn btn-primary" href="${deployUrl}" target="_blank" rel="noopener">Deploy from hub</a>` : ""}
              <a class="btn btn-secondary" href="/dashboard">Back to dashboard</a>
            </div>
            ${agent.task ? `<div class="example-block"><strong>Standing task</strong><code>${esc(agent.task)}</code></div>` : ""}
            ${agent.preferences ? `<div class="example-block"><strong>Standing preferences</strong><code>${esc(agent.preferences)}</code></div>` : ""}
          </article>
          <article class="detail-panel detail-side">
            <h2>Schedules</h2>
            ${schedules.length ? `<div class="schedule-list">${schedules.map((schedule) => `
              <div class="schedule-row">
                <span><code>${esc(schedule.cron || schedule)}</code></span>
                <span>${schedule.id ? `#${esc(schedule.id)}` : ""}</span>
              </div>
            `).join("")}</div>` : `<p>No schedules yet. Add one in chat with <code>/schedule &lt;when&gt;</code>.</p>`}
          </article>
        </section>

        <section class="detail-grid">
          <article class="detail-panel">
            <h2>What it does</h2>
            ${renderItems(agent.what_it_does || [])}
          </article>
          <article class="detail-panel">
            <h2>How to use it</h2>
            ${renderItems(agent.how_to_use || [])}
          </article>
        </section>

        <section class="detail-panel stack-gap">
          <h2>Commands</h2>
          ${renderCommands(agent.commands || [])}
        </section>

        <section class="detail-panel stack-gap">
          <h2>Examples</h2>
          ${renderExamples(agent.examples || [])}
        </section>

        <section class="detail-two-up stack-gap">
          <article class="detail-panel">
            <h2>Tips</h2>
            ${renderItems(agent.tips || [])}
          </article>
          <article class="detail-panel">
            <h2>Limitations</h2>
            ${renderItems(agent.limitations || [])}
          </article>
        </section>
      `;
    } catch (_error) {
      root.className = "empty-state";
      root.textContent = "Failed to load this agent detail page.";
    }
  }

  renderSprite();

  if (page === "dashboard") {
    refreshDashboard();
    setInterval(refreshDashboard, 5000);
  }

  if (page === "agent-detail") {
    renderAgentDetailPage();
  }
})();
