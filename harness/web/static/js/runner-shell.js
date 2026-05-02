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
    viewingTurn: opts.viewingTurn != null ? opts.viewingTurn : null,
    liveTurn: curTurn,
    inspectorOpen: false,
    devPanelOpen: false,
    advanceBusy: false,
    channelAttention: seedAttention,
    progressText: "idle",
    get isReplay() {
      return this.viewingTurn != null && this.viewingTurn !== this.liveTurn;
    },
    setView(name) {
      this.currentView = name;
    },
    setChannel(name) {
      if (!name) return;
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
  };
}

document.body.addEventListener("htmx:sseMessage", (evt) => {
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
