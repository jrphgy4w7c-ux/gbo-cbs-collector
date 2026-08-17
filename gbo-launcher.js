(async () => {
  const VERSION = "GBO-LAUNCHER-2.0.0";
  const REPOSITORY_ID = 1337389940;
  const BRANCH = "main";
  const COLLECTOR_PATH = "collector.js";

  if (!/\.baseball\.cbssports\.com$/i.test(location.hostname)) {
    alert("Open your CBS Fantasy Baseball league first.");
    return;
  }

  function decodeBase64Utf8(value) {
    const clean = String(value || "").replace(/\s+/g, "");
    const bytes = Uint8Array.from(atob(clean), c => c.charCodeAt(0));
    return new TextDecoder("utf-8").decode(bytes);
  }

  async function loadRepositoryFile(path) {
    const encodedPath = path.split("/").map(encodeURIComponent).join("/");
    const url = `https://api.github.com/repositories/${REPOSITORY_ID}/contents/${encodedPath}?ref=${encodeURIComponent(BRANCH)}`;
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) throw new Error(`GitHub API HTTP ${response.status}`);
    const payload = await response.json();
    if (!payload || payload.type !== "file" || !payload.content) throw new Error("Unexpected GitHub API response");
    return decodeBase64Utf8(payload.content);
  }

  try {
    console.log(`${VERSION}: loading GBO collector from immutable repository ID ${REPOSITORY_ID}...`);
    const source = await loadRepositoryFile(COLLECTOR_PATH);
    if (!source.includes("GBO-CBS-")) throw new Error("Unexpected collector content");
    (0, eval)(source);
  } catch (error) {
    console.error(`${VERSION}:`, error);
    alert(`GBO Refresh could not load the collector. ${error && error.message ? error.message : "Unknown error"}`);
  }
})();
