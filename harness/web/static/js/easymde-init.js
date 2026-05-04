(function () {
  function initEditors(root) {
    if (!window.EasyMDE) return;
    const scope = root || document;
    const nodes = scope.querySelectorAll("textarea[data-easymde]");
    nodes.forEach((node) => {
      if (node.dataset.easymdeReady === "1") return;
      const mde = new window.EasyMDE({
        element: node,
        spellChecker: false,
        status: false,
        toolbar: [
          "bold",
          "italic",
          "heading",
          "|",
          "quote",
          "unordered-list",
          "ordered-list",
          "|",
          "preview",
          "side-by-side",
          "fullscreen",
          "|",
          "guide",
        ],
      });
      const cm = mde.codemirror;
      cm.on("keydown", function (_cm, evt) {
        if ((evt.metaKey || evt.ctrlKey) && evt.key === "Enter") {
          evt.preventDefault();
          const form = node.closest("form");
          if (form) form.requestSubmit();
        }
      });
      node.dataset.easymdeReady = "1";
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initEditors(document);
  });
  document.body.addEventListener("htmx:afterSwap", function (evt) {
    initEditors(evt.target);
  });
})();
