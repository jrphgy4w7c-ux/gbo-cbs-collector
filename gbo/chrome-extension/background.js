const CLIENT_ID = "Iv23liOQBr1O0PksufDG";
const REPOSITORY_ID = "1337389940";
const API_VERSION = "2022-11-28";
const INBOX_PATH = "gbo/inbox/latest.json";
const TOKEN_KEY = "gboGithubToken";

function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }

function encodeBase64Utf8(text) {
  const bytes = new TextEncoder().encode(text);
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary);
}

async function postForm(url, fields) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Accept": "application/json",
      "Content-Type": "application/x-www-form-urlencoded"
    },
    body: new URLSearchParams(fields)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data?.error_description || data?.message || `HTTP ${response.status}`);
  return data;
}

async function loadToken() {
  const stored = await chrome.storage.local.get(TOKEN_KEY);
  return stored[TOKEN_KEY] || null;
}

async function saveToken(data) {
  const now = Date.now();
  const token = {
    access_token: data.access_token,
    expires_at: data.expires_in ? now + Number(data.expires_in) * 1000 : null,
    refresh_token: data.refresh_token || null,
    refresh_expires_at: data.refresh_token_expires_in ? now + Number(data.refresh_token_expires_in) * 1000 : null
  };
  await chrome.storage.local.set({ [TOKEN_KEY]: token });
  return token;
}

function tokenIsFresh(token) {
  return !!token?.access_token && (!token.expires_at || token.expires_at > Date.now() + 60000);
}

async function refreshToken(token) {
  if (!token?.refresh_token || (token.refresh_expires_at && token.refresh_expires_at <= Date.now() + 60000)) return null;
  try {
    const data = await postForm("https://github.com/login/oauth/access_token", {
      client_id: CLIENT_ID,
      grant_type: "refresh_token",
      refresh_token: token.refresh_token,
      repository_id: REPOSITORY_ID
    });
    if (!data.access_token) return null;
    return await saveToken(data);
  } catch {
    return null;
  }
}

async function authorizeDeviceFlow() {
  const device = await postForm("https://github.com/login/device/code", {
    client_id: CLIENT_ID
  });
  if (!device.device_code || !device.user_code) throw new Error("GitHub did not return a device authorization code.");

  const authUrl = chrome.runtime.getURL(
    `auth.html?code=${encodeURIComponent(device.user_code)}&verification_uri=${encodeURIComponent(device.verification_uri || "https://github.com/login/device")}`
  );
  await chrome.tabs.create({ url: authUrl });

  let interval = Math.max(5, Number(device.interval || 5));
  const deadline = Date.now() + Number(device.expires_in || 900) * 1000;
  while (Date.now() < deadline) {
    await sleep(interval * 1000);
    const data = await postForm("https://github.com/login/oauth/access_token", {
      client_id: CLIENT_ID,
      device_code: device.device_code,
      grant_type: "urn:ietf:params:oauth:grant-type:device_code",
      repository_id: REPOSITORY_ID
    });
    if (data.access_token) return await saveToken(data);
    if (data.error === "authorization_pending") continue;
    if (data.error === "slow_down") {
      interval += 5;
      continue;
    }
    if (data.error === "access_denied") throw new Error("GitHub authorization was denied.");
    if (data.error === "expired_token") throw new Error("GitHub authorization code expired. Run GBO Refresh again.");
    if (data.error) throw new Error(data.error_description || data.error);
  }
  throw new Error("GitHub authorization timed out. Run GBO Refresh again.");
}

async function getAccessToken() {
  let token = await loadToken();
  if (tokenIsFresh(token)) return token.access_token;
  token = await refreshToken(token);
  if (tokenIsFresh(token)) return token.access_token;
  token = await authorizeDeviceFlow();
  if (!tokenIsFresh(token)) throw new Error("GitHub authorization did not produce a usable token.");
  return token.access_token;
}

async function githubApi(path, token, options = {}) {
  const response = await fetch(`https://api.github.com${path}`, {
    ...options,
    headers: {
      "Accept": "application/vnd.github+json",
      "Authorization": `Bearer ${token}`,
      "X-GitHub-Api-Version": API_VERSION,
      ...(options.headers || {})
    }
  });
  let data = null;
  const text = await response.text();
  if (text) {
    try { data = JSON.parse(text); } catch { data = { raw: text }; }
  }
  if (!response.ok) {
    const error = new Error(data?.message || `GitHub API HTTP ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return data;
}

async function publishSnapshot(json, filename) {
  JSON.parse(json);
  const token = await getAccessToken();
  let sha = null;
  try {
    const existing = await githubApi(`/repositories/${REPOSITORY_ID}/contents/${INBOX_PATH}?ref=main`, token);
    sha = existing?.sha || null;
  } catch (error) {
    if (error.status !== 404) throw error;
  }

  const payload = {
    message: `GBO browser refresh ${new Date().toISOString()}`,
    content: encodeBase64Utf8(json),
    branch: "main"
  };
  if (sha) payload.sha = sha;

  const result = await githubApi(`/repositories/${REPOSITORY_ID}/contents/${INBOX_PATH}`, token, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return {
    ok: true,
    path: INBOX_PATH,
    filename,
    commit_sha: result?.commit?.sha || null
  };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== "GBO_PUBLISH_SNAPSHOT") return;
  (async () => {
    try {
      if (typeof message.json !== "string" || !message.json.length) throw new Error("No GBO snapshot payload received.");
      const result = await publishSnapshot(message.json, message.filename || null);
      sendResponse(result);
    } catch (error) {
      sendResponse({ ok: false, error: error?.message || String(error) });
    }
  })();
  return true;
});
