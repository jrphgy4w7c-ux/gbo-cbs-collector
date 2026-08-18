(() => {
  const REQUEST = "GBO_PUBLISH_SNAPSHOT";
  const RESPONSE = "GBO_PUBLISH_RESULT";

  window.addEventListener("message", async event => {
    if (event.source !== window || event.data?.type !== REQUEST) return;
    const requestId = event.data.requestId;
    try {
      const response = await chrome.runtime.sendMessage({
        type: REQUEST,
        requestId,
        filename: event.data.filename,
        json: event.data.json
      });
      window.postMessage({ type: RESPONSE, requestId, ...response }, "*");
    } catch (error) {
      window.postMessage({
        type: RESPONSE,
        requestId,
        ok: false,
        error: error?.message || String(error)
      }, "*");
    }
  });

  window.postMessage({ type: "GBO_PUBLISH_BRIDGE_READY" }, "*");
})();
