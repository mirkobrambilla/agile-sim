function channelView(_opts) {
  return {
    focusInput() {
      const el = this.$refs.channelInput;
      if (el) el.focus();
    },
  };
}
