(async () => {
  const VERSION = "GBO-LAUNCHER-2.5.0";
  const REPOSITORY_ID = 1337389940;
  const BRANCH = "main";
  const COLLECTOR_PATH = "gbo/collector.js";
  const STATUS_ID = "gbo-refresh-status";

  if (!/\.baseball\.cbssports\.com$/i.test(location.hostname)) {
    alert("Open your CBS Fantasy Baseball league first.");
    return;
  }

  function ensureStatusBox() {
    let box = document.getElementById(STATUS_ID);
    if (!box) {
      box = document.createElement("div");
      box.id = STATUS_ID;
      Object.assign(box.style, {
        position: "fixed",
        top: "16px",
        right: "16px",
        zIndex: "2147483647",
        maxWidth: "420px",
        padding: "12px 14px",
        borderRadius: "10px",
        background: "#1f2937",
        color: "#ffffff",
        font: "600 14px/1.35 system-ui,-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif",
        boxShadow: "0 8px 28px rgba(0,0,0,.28)",
        whiteSpace: "normal"
      });
      document.documentElement.appendChild(box);
    }
    return box;
  }

  function showStatus(message, tone = "running") {
    if (window.__GBO_REFRESH_STATUS_TIMER__) {
      clearTimeout(window.__GBO_REFRESH_STATUS_TIMER__);
      window.__GBO_REFRESH_STATUS_TIMER__ = null;
    }
    const box = ensureStatusBox();
    box.textContent = message;
    box.style.background = tone === "success" ? "#14532d" : tone === "warning" ? "#92400e" : tone === "error" ? "#7f1d1d" : "#1f2937";
    box.style.display = "block";
    return box;
  }

  function finishStatus(message, tone, ttl = 6000) {
    const box = showStatus(message, tone);
    window.__GBO_REFRESH_STATUS_TIMER__ = setTimeout(() => {
      if (box && box.parentNode) box.remove();
      window.__GBO_REFRESH_STATUS_TIMER__ = null;
    }, ttl);
  }

  if (window.__GBO_REFRESH_RUNNING__) {
    showStatus("GBO Refresh is already running — keep this tab open. No need to click again.");
    return;
  }

  window.__GBO_REFRESH_RUNNING__ = true;
  showStatus("GBO Refresh starting… keep this tab open.");

  function decodeBase64Utf8(value) {
    const clean = String(value || "").replace(/\s+/g, "");
    const bytes = Uint8Array.from(atob(clean), c => c.charCodeAt(0));
    return new TextDecoder("utf-8").decode(bytes);
  }

  async function loadRepositoryFile(path) {
    const encodedPath = path.split("/").map(encodeURIComponent).join("/");
    const url = `https://api.github.com/repositories/${REPOSITORY_ID}/contents/${encodedPath}?ref=${encodeURIComponent(BRANCH)}`;
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`GitHub API HTTP ${response.status} for ${path}`);
    const payload = await response.json();
    if (!payload || payload.type !== "file" || !payload.content) throw new Error(`Unexpected GitHub API response for ${path}`);
    return decodeBase64Utf8(payload.content);
  }

  function bridgeReady() {
    return document.documentElement?.getAttribute("data-gbo-publish-bridge") === "ready";
  }

  function publishViaBridge(json, filename) {
    return new Promise((resolve, reject) => {
      if (!bridgeReady()) {
        reject(new Error("GBO Chrome publish bridge is not installed or not active."));
        return;
      }
      const requestId = `gbo-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      const timeout = setTimeout(() => {
        window.removeEventListener("message", onMessage);
        reject(new Error("GBO Chrome publish bridge timed out."));
      }, 180000);

      function onMessage(event) {
        if (event.source !== window || event.data?.type !== "GBO_PUBLISH_RESULT" || event.data?.requestId !== requestId) return;
        clearTimeout(timeout);
        window.removeEventListener("message", onMessage);
        if (event.data.ok) resolve(event.data);
        else reject(new Error(event.data.error || "GBO snapshot publication failed."));
      }

      window.addEventListener("message", onMessage);
      window.postMessage({ type: "GBO_PUBLISH_SNAPSHOT", requestId, filename, json }, "*");
    });
  }

  try {
    if (!window.CBSi?.token) throw new Error("CBS authentication token not found. Make sure you are logged in.");

    showStatus("GBO Refresh: loading collector…");
    console.log(`${VERSION}: loading GBO collector from immutable repository ID ${REPOSITORY_ID}: ${COLLECTOR_PATH}`);
    const source = await loadRepositoryFile(COLLECTOR_PATH);
    if (!source.includes("GBO-CBS-")) throw new Error(`Unexpected collector content at ${COLLECTOR_PATH}`);

    showStatus("GBO Refresh: collecting live CBS data… keep this tab open.");
    console.log(`${VERSION}: running collector from ${COLLECTOR_PATH}`);

    let capturedJsonBlob = null;
    const originalCreateObjectURL = URL.createObjectURL.bind(URL);
    URL.createObjectURL = function(value) {
      if (value instanceof Blob && value.type === "application/json") capturedJsonBlob = value;
      return originalCreateObjectURL(value);
    };

    let outcome;
    try {
      const run = (0, eval)(source);
      outcome = run && typeof run.then === "function" ? await run : run;
    } finally {
      URL.createObjectURL = originalCreateObjectURL;
    }

    const json = capturedJsonBlob ? await capturedJsonBlob.text() : null;
    const healthy = outcome?.source_health?.transactions?.complete !== false && !(Array.isArray(outcome?.errors) && outcome.errors.length);

    if (!healthy) {
      if (outcome?.source_health?.transactions?.complete === false) {
        finishStatus("⚠ GBO Refresh downloaded, but transaction history is incomplete. Prior canonical state preserved.", "warning", 12000);
      } else {
        finishStatus("⚠ GBO Refresh downloaded with collector errors. Prior canonical state preserved.", "warning", 12000);
      }
      return;
    }

    if (!json) {
      finishStatus("⚠ GBO Refresh downloaded, but automatic publication could not capture the sanitized JSON. Manual upload fallback remains available.", "warning", 12000);
      return;
    }

    if (!bridgeReady()) {
      finishStatus("✓ GBO Refresh complete — snapshot downloaded. Install/enable the GBO Chrome publish bridge for automatic GitHub handoff.", "warning", 12000);
      return;
    }

    showStatus("GBO Refresh: publishing sanitized snapshot to GitHub… first use may ask for one-time authorization.");
    const published = await publishViaBridge(json, outcome?.filename || null);
    console.log(`${VERSION}: GBO snapshot published`, published);
    finishStatus("✓ GBO Refresh complete — snapshot published to GitHub and reconciliation triggered. You’re done.", "success", 9000);
  } catch (error) {
    console.error(`${VERSION}:`, error);
    finishStatus(`⚠ GBO Refresh collected/downloaded if possible, but automatic publication failed: ${error && error.message ? error.message : "Unknown error"}`, "warning", 15000);
  } finally {
    window.__GBO_REFRESH_RUNNING__ = false;
  }
})();
