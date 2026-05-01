/** @typedef {{ currentView: string, viewingTurn: number | null, liveTurn: number }} RunnerShellState */

function runnerShell(opts) {
  const curTurn = opts.liveTurn != null ? opts.liveTurn : 1;
  return {
    currentView: opts.defaultView || "channels",
    viewingTurn: opts.viewingTurn != null ? opts.viewingTurn : null,
    liveTurn: curTurn,
    get isReplay() {
      return this.viewingTurn != null && this.viewingTurn !== this.liveTurn;
    },
    setView(name) {
      this.currentView = name;
    },
  };
}
