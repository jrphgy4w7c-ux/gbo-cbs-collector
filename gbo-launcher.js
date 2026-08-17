(async () => {
  const VERSION = "GBO-LAUNCHER-2.2.0";
  const REPOSITORY_ID = 1337389940;
  const BRANCH = "main";
  const COLLECTOR_PATHS = ["gbo/collector.js", "collector.js"];
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
        maxWidth: "360px",
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
    box.style.background = tone === "success" ? "#14532d" : tone === "error" ? "#7f1d1d" : "#1f2937";
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

  try {
    if (!window.CBSi?.token) throw new Error("CBS authentication token not found. Make sure you are logged in.");

    let source = null;
    let selectedPath = null;
    let lastError = null;

    for (let i = 0; i < COLLECTOR_PATHS.length; i++) {
      const path = COLLECTOR_PATHS[i];
      try {
        showStatus(i === 0 ? "GBO Refresh: loading collector…" : "GBO Refresh: trying safe fallback…");
        console.log(`${VERSION}: loading GBO collector from immutable repository ID ${REPOSITORY_ID}: ${path}`);
        const candidate = await loadRepositoryFile(path);
        if (!candidate.includes("GBO-CBS-")) throw new Error(`Unexpected collector content at ${path}`);
        source = candidate;
        selectedPath = path;
        break;
      } catch (error) {
        lastError = error;
        console.warn(`${VERSION}: collector path failed: ${path}`, error);
      }
    }

    if (!source) throw lastError || new Error("No GBO collector path could be loaded.");

    showStatus("GBO Refresh: collecting live CBS data… keep this tab open.");
    console.log(`${VERSION}: running collector from ${selectedPath}`);
    const run = (0, eval)(source);
    if (run && typeof run.then === "function") await run;

    finishStatus("✓ GBO Refresh complete — snapshot downloaded.", "success", 6000);
  } catch (error) {
    console.error(`${VERSION}:`, error);
    finishStatus("GBO Refresh failed — no snapshot downloaded.", "error", 10000);
    alert(`GBO Refresh failed. ${error && error.message ? error.message : "Unknown error"}`);
  } finally {
    window.__GBO_REFRESH_RUNNING__ = false;
  }
})();
