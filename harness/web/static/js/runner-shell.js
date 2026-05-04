/** @typedef {{ currentView: string, viewingTurn: number | null, liveTurn: number }} RunnerShellState */

function runnerShell(opts) {
  const curTurn = opts.liveTurn != null ? opts.liveTurn : 1;
  const channelList = Array.isArray(opts.channels) ? opts.channels : [];
  const seedAttention = {};
  for (const ch of channelList) {
    seedAttention[ch] = !!(opts.attention && opts.attention[ch]);
  }
  if (opts.currentChannel && seedAttention[opts.currentChannel] !== undefined) {
    seedAttention[opts.currentChannel] = false;
  }
  return {
    currentView: opts.defaultView || "channels",
    currentChannel: opts.currentChannel || "",
    viewingTurn: opts.viewingTurn != null ? opts.viewingTurn : null,
    liveTurn: curTurn,
    inspectorOpen: false,
    devPanelOpen: false,
    navMenuOpen: false,
    advanceBusy: false,
    channelAttention: seedAttention,
    progressText: "idle",
    get isReplay() {
      return this.viewingTurn != null && this.viewingTurn !== this.liveTurn;
    },
    setView(name) {
      this.currentView = name;
      this.navMenuOpen = false;
      this.applyCenterStageLayout();
    },
    setChannel(name) {
      if (!name) return;
      this.currentChannel = name;
      this.navMenuOpen = false;
      this.channelAttention[name] = false;
      try {
        localStorage.setItem("runner.lastChannel", name);
      } catch (_) {}
    },
    handleProgress(payload) {
      if (!payload || typeof payload !== "object") return;
      const kind = payload.kind || "";
      if (kind === "agent_start") this.progressText = `agent ${payload.character}...`;
      else if (kind === "coach_start") this.progressText = "coach...";
      else if (kind === "advance_done") this.progressText = `turn ${payload.turn} done`;
      else if (kind === "advance_cancelled") this.progressText = "turn cancelled";
      else if (kind === "advance_stop") this.progressText = `stop: ${payload.stop}`;
    },
    syncFromLocation() {
      const params = new URLSearchParams(window.location.search || "");
      const view = (params.get("view") || "channels").toLowerCase();
      const channel = params.get("channel") || opts.currentChannel || "";
      this.currentView = view;
      this.currentChannel = channel;
      if (view === "channels" && channel) {
        this.setChannel(channel);
      }
      this.applyCenterStageLayout();
    },
    loadFromUrl() {
      const params = new URLSearchParams(window.location.search || "");
      const view = (params.get("view") || "channels").toLowerCase();
      const channel = params.get("channel") || opts.currentChannel || "";
      const turn = this.viewingTurn != null ? String(this.viewingTurn) : String(this.liveTurn || 1);
      let url = "";
      if (view === "kanban") url = `/partials/run/${opts.runPath}/kanban?turn=${encodeURIComponent(turn)}&view=kanban&channel=${encodeURIComponent(channel)}`;
      else if (view === "roster") url = `/partials/run/${opts.runPath}/roster?turn=${encodeURIComponent(turn)}&view=roster&channel=${encodeURIComponent(channel)}`;
      else if (view === "timeline") url = `/partials/run/${opts.runPath}/timeline?turn=${encodeURIComponent(turn)}&view=timeline&channel=${encodeURIComponent(channel)}`;
      else if (view === "summary") url = `/partials/run/${opts.runPath}/summary?view=summary&channel=${encodeURIComponent(channel)}`;
      else url = `/partials/run/${opts.runPath}/channel?channel=${encodeURIComponent(channel || opts.currentChannel || "")}&turn=${encodeURIComponent(turn)}&view=channels`;
      if (window.htmx && typeof window.htmx.ajax === "function") {
        window.htmx.ajax("GET", url, "#center-stage");
      }
      this.syncFromLocation();
    },
    applyCenterStageLayout() {
      const center = document.getElementById("center-stage");
      if (!center) return;
      center.classList.remove("center-stage-shell", "overflow-y-auto");
      if (this.currentView === "channels") center.classList.add("center-stage-shell");
      else center.classList.add("overflow-y-auto");
    },
  };
}

if (typeof document !== "undefined" && document && document.addEventListener) {
  window.addEventListener("popstate", () => {
    const host = document.querySelector("[x-data]");
    if (!host || !host.__x || !host.__x.$data) return;
    const state = host.__x.$data;
    if (typeof state.loadFromUrl === "function") state.loadFromUrl();
  });

  document.addEventListener("htmx:sseMessage", (evt) => {
    const target = evt.target;
    const root = target && target.closest ? target.closest("[x-data]") : null;
    if (!root || !root.__x) return;
    let payload = null;
    try {
      payload = JSON.parse(evt.detail.data || "{}");
    } catch (_) {
      return;
    }
    if (root.__x.$data && typeof root.__x.$data.handleProgress === "function") {
      root.__x.$data.handleProgress(payload);
    }
  });

  document.addEventListener("htmx:afterSwap", () => {
    const host = document.querySelector("[x-data]");
    if (!host || !host.__x || !host.__x.$data) return;
    const state = host.__x.$data;
    if (typeof state.syncFromLocation === "function") state.syncFromLocation();
  });
}
