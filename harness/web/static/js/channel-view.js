function _scrollChannelMessagesToBottom(root) {
  const scope = root || document;
  const el = scope.querySelector("[data-channel-messages='true']");
  if (!el) return;
  el.scrollTop = el.scrollHeight;
}

function channelView(_opts) {
  return {
    focusInput() {
      const el = this.$refs.channelInput;
      if (el) el.focus();
    },
  };
}

document.addEventListener("DOMContentLoaded", () => {
  _scrollChannelMessagesToBottom(document);
});

document.body.addEventListener("htmx:afterSwap", (evt) => {
  const target = evt.detail && evt.detail.target;
  if (!target) return;
  if (target.id === "center-stage" || target.querySelector("[data-channel-messages='true']")) {
    _scrollChannelMessagesToBottom(target);
  }
});
