(async () => {
  const VERSION = "GBO-LAUNCHER-2.6.0";
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
      Object.assign(box.style, { position:"fixed", top:"16px", right:"16px", zIndex:"2147483647", maxWidth:"420px", padding:"12px 14px", borderRadius:"10px", background:"#1f2937", color:"#ffffff", font:"600 14px/1.35 system-ui,-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif", boxShadow:"0 8px 28px rgba(0,0,0,.28)", whiteSpace:"normal" });
      document.documentElement.appendChild(box);
    }
    return box;
  }

  function showStatus(message, tone = "running") {
    if (window.__GBO_REFRESH_STATUS_TIMER__) clearTimeout(window.__GBO_REFRESH_STATUS_TIMER__);
    const box = ensureStatusBox();
    box.textContent = message;
    box.style.background = tone === "success" ? "#14532d" : tone === "warning" ? "#92400e" : tone === "error" ? "#7f1d1d" : "#1f2937";
    box.style.display = "block";
    return box;
  }

  function finishStatus(message, tone, ttl = 6000) {
    const box = showStatus(message, tone);
    window.__GBO_REFRESH_STATUS_TIMER__ = setTimeout(() => { if (box?.parentNode) box.remove(); window.__GBO_REFRESH_STATUS_TIMER__ = null; }, ttl);
  }

  function downloadFallback(json, filename) {
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename || `GBO_CBS_Snapshot_fallback_${new Date().toISOString().replace(/[:.]/g,"-")}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  if (window.__GBO_REFRESH_RUNNING__) { showStatus("GBO Refresh is already running — keep this tab open. No need to click again."); return; }
  window.__GBO_REFRESH_RUNNING__ = true;
  showStatus("GBO Refresh starting… keep this tab open.");

  function decodeBase64Utf8(value) {
    const clean = String(value || "").replace(/\s+/g, "");
    const bytes = Uint8Array.from(atob(clean), c => c.charCodeAt(0));
    return new TextDecoder("utf-8").decode(bytes);
  }

  async function loadRepositoryFile(path) {
    const encodedPath = path.split("/").map(encodeURIComponent).join("/");
    const response = await fetch(`https://api.github.com/repositories/${REPOSITORY_ID}/contents/${encodedPath}?ref=${encodeURIComponent(BRANCH)}`, { cache:"no-store" });
    if (!response.ok) throw new Error(`GitHub API HTTP ${response.status} for ${path}`);
    const payload = await response.json();
    if (!payload || payload.type !== "file" || !payload.content) throw new Error(`Unexpected GitHub API response for ${path}`);
    return decodeBase64Utf8(payload.content);
  }

  function bridgeReady() { return document.documentElement?.getAttribute("data-gbo-publish-bridge") === "ready"; }

  function publishViaBridge(json, filename) {
    return new Promise((resolve, reject) => {
      if (!bridgeReady()) return reject(new Error("GBO Chrome publish bridge is not installed or not active."));
      const requestId = `gbo-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      const timeout = setTimeout(() => { window.removeEventListener("message", onMessage); reject(new Error("GBO Chrome publish bridge timed out.")); }, 180000);
      function onMessage(event) {
        if (event.source !== window || event.data?.type !== "GBO_PUBLISH_RESULT" || event.data?.requestId !== requestId) return;
        clearTimeout(timeout); window.removeEventListener("message", onMessage);
        event.data.ok ? resolve(event.data) : reject(new Error(event.data.error || "GBO snapshot publication failed."));
      }
      window.addEventListener("message", onMessage);
      window.postMessage({ type:"GBO_PUBLISH_SNAPSHOT", requestId, filename, json }, "*");
    });
  }

  let json = null, filename = null;
  try {
    if (!window.CBSi?.token) throw new Error("CBS authentication token not found. Make sure you are logged in.");
    showStatus("GBO Refresh: loading collector…");
    const source = await loadRepositoryFile(COLLECTOR_PATH);
    if (!source.includes("GBO-CBS-")) throw new Error(`Unexpected collector content at ${COLLECTOR_PATH}`);

    showStatus("GBO Refresh: collecting live CBS data… keep this tab open.");
    let capturedJsonBlob = null;
    const originalCreateObjectURL = URL.createObjectURL.bind(URL);
    const originalAnchorClick = HTMLAnchorElement.prototype.click;
    URL.createObjectURL = function(value) { if (value instanceof Blob && value.type === "application/json") capturedJsonBlob = value; return originalCreateObjectURL(value); };
    HTMLAnchorElement.prototype.click = function(...args) {
      if (this.download && /^GBO_CBS_Snapshot_.*\.json$/i.test(this.download)) { filename = this.download; return; }
      return originalAnchorClick.apply(this, args);
    };

    let outcome;
    try {
      const run = (0, eval)(source);
      outcome = run && typeof run.then === "function" ? await run : run;
    } finally {
      URL.createObjectURL = originalCreateObjectURL;
      HTMLAnchorElement.prototype.click = originalAnchorClick;
    }

    json = capturedJsonBlob ? await capturedJsonBlob.text() : null;
    filename = filename || outcome?.filename || null;
    const healthy = outcome?.source_health?.transactions?.complete !== false && !(Array.isArray(outcome?.errors) && outcome.errors.length);

    if (!json) throw new Error("Collector completed but sanitized snapshot payload was not captured.");
    if (!healthy) {
      downloadFallback(json, filename);
      finishStatus("⚠ GBO Refresh is incomplete. Prior canonical state preserved; fallback JSON downloaded for diagnosis.", "warning", 12000);
      return;
    }
    if (!bridgeReady()) {
      downloadFallback(json, filename);
      finishStatus("⚠ Automatic GitHub handoff unavailable. Fallback JSON downloaded; enable the GBO Chrome publish bridge.", "warning", 12000);
      return;
    }

    showStatus("GBO Refresh: publishing sanitized snapshot to GitHub…");
    try {
      const published = await publishViaBridge(json, filename);
      console.log(`${VERSION}: GBO snapshot published`, published);
      finishStatus("✓ GBO Refresh complete — snapshot published to GitHub and reconciliation triggered. You’re done.", "success", 9000);
    } catch (publishError) {
      downloadFallback(json, filename);
      throw new Error(`automatic publication failed; fallback JSON downloaded. ${publishError?.message || publishError}`);
    }
  } catch (error) {
    console.error(`${VERSION}:`, error);
    finishStatus(`⚠ GBO Refresh needs attention: ${error?.message || "Unknown error"}`, "warning", 15000);
  } finally {
    window.__GBO_REFRESH_RUNNING__ = false;
  }
})();
