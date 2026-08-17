(async () => {
  const VERSION = "GBO-CBS-1.2.0";
  const GBO_TEAM_ID = "3";
  const startedAt = new Date();
  const leagueOrigin = location.origin;
  const secret = window.CBSi?.token;

  if (!/\.baseball\.cbssports\.com$/i.test(location.hostname)) {
    console.error("GBO COLLECTOR: Run this from your CBS Fantasy Baseball league.");
    return;
  }

  if (!secret) {
    console.error("GBO COLLECTOR: CBS authentication token not found. Make sure you are logged in.");
    return;
  }

  const warnings = [];
  const errors = [];
  const sensitiveKey = /token|access.?token|authorization|cookie|session|password|credential|secret|csrf/i;
  const privateSettingLabel = /password|league e-?mail|e-?mail address|commish message|paypal|venmo|mailing address|phone/i;
  const emailPattern = /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i;

  function sanitize(value) {
    if (Array.isArray(value)) return value.map(sanitize);
    if (value && typeof value === "object") {
      const out = {};
      for (const [key, val] of Object.entries(value)) {
        if (sensitiveKey.test(key)) out[key] = "[REDACTED]";
        else out[key] = sanitize(val);
      }
      return out;
    }
    if (typeof value === "string" && secret && value.includes(secret)) {
      return value.split(secret).join("[REDACTED]");
    }
    return value;
  }

  function safeError(err) {
    let msg = err?.message || String(err);
    if (secret && msg.includes(secret)) msg = msg.split(secret).join("[REDACTED]");
    return msg;
  }

  function normalizeText(value) {
    return (value || "").replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();
  }

  async function fetchJson(label, url, warnOnFailure = true) {
    try {
      const response = await fetch(url, { credentials: "include" });
      const text = await response.text();
      if (!response.ok) {
        if (warnOnFailure) warnings.push(`${label}: HTTP ${response.status}`);
        return { ok: false, status: response.status, error: `HTTP ${response.status}` };
      }
      let parsed;
      try { parsed = JSON.parse(text); }
      catch {
        if (warnOnFailure) warnings.push(`${label}: response was not valid JSON`);
        return { ok: false, status: response.status, error: "Invalid JSON" };
      }
      return { ok: true, status: response.status, data: sanitize(parsed) };
    } catch (err) {
      const msg = safeError(err);
      if (warnOnFailure) warnings.push(`${label}: ${msg}`);
      return { ok: false, error: msg };
    }
  }

  async function fetchLeagueDocument(path, warnOnFailure = true) {
    try {
      const url = new URL(path, leagueOrigin);
      if (url.origin !== leagueOrigin) throw new Error("Blocked non-league origin");
      const response = await fetch(url.href, { credentials: "include" });
      if (!response.ok) {
        if (warnOnFailure) warnings.push(`${url.pathname}: HTTP ${response.status}`);
        return { ok: false, status: response.status, path: url.pathname + url.search, error: `HTTP ${response.status}` };
      }
      const html = await response.text();
      return { ok: true, status: response.status, path: url.pathname + url.search, document: new DOMParser().parseFromString(html, "text/html") };
    } catch (err) {
      const msg = safeError(err);
      if (warnOnFailure) warnings.push(`${path}: ${msg}`);
      return { ok: false, error: msg };
    }
  }

  function parseTable(table) {
    const trs = [...table.querySelectorAll("tr")];
    if (!trs.length) return { headers: [], rows: [] };
    const firstCells = [...trs[0].querySelectorAll("th,td")];
    const firstHasTH = trs[0].querySelectorAll("th").length > 0;
    const headers = firstHasTH ? firstCells.map(x => normalizeText(x.innerText)) : [];
    const start = firstHasTH ? 1 : 0;
    const rows = trs.slice(start).map(row => [...row.querySelectorAll("th,td")].map(cell => normalizeText(cell.innerText))).filter(row => row.some(Boolean));
    return { headers, rows };
  }

  function sanitizeTable(table) {
    const parsed = parseTable(table);
    const rows = parsed.rows.filter(row => {
      const joined = row.join(" ");
      if (privateSettingLabel.test(joined)) return false;
      if (emailPattern.test(joined)) return false;
      return true;
    });
    return { headers: parsed.headers, rows };
  }

  function parseSafeTables(doc) {
    return [...doc.querySelectorAll("table")].map(sanitizeTable).filter(t => t.headers.length || t.rows.length);
  }

  function extractMyHeaderState(doc) {
    const text = normalizeText(doc.body?.innerText || "");
    const budgetMatch = text.match(/\$(\d+)\s+Budget\s*\(\s*(\d+)\s*\/\s*(\d+)\s*\)/i);
    if (!budgetMatch) return { found: false };
    return { found: true, fab_remaining: Number(budgetMatch[1]), waiver_position: Number(budgetMatch[2]), waiver_position_denominator: Number(budgetMatch[3]) };
  }

  async function captureSafePage(label, path, warnOnFailure = true) {
    const result = await fetchLeagueDocument(path, warnOnFailure);
    if (!result.ok) {
      if (warnOnFailure) warnings.push(`${label}: ${result.error}`);
      return { ok: false, path, error: result.error };
    }
    const tables = parseSafeTables(result.document);
    return { ok: true, path, data_present: tables.length > 0, header_state: extractMyHeaderState(result.document), tables };
  }

  function findTransactionTable(doc) {
    for (const table of doc.querySelectorAll("table")) {
      const parsed = parseTable(table);
      const h = parsed.headers.map(x => x.toLowerCase());
      if (h.includes("date") && h.includes("team") && h.includes("players") && h.includes("effective")) return parsed;
    }
    return null;
  }

  function isTransactionDataRow(row) {
    if (!Array.isArray(row) || row.length !== 4) return false;
    return /^\d{1,2}\/\d{1,2}\/\d{2}\s+\d{1,2}:\d{2}\s+(AM|PM)\s+ET$/i.test(normalizeText(row[0]));
  }

  function deriveTransactionPageCount(doc) {
    const starts = new Set([1]);
    for (const a of doc.querySelectorAll("a[href]")) {
      try {
        const u = new URL(a.href, leagueOrigin);
        if (u.origin !== leagueOrigin || u.pathname !== "/transactions") continue;
        const keys = [...u.searchParams.keys()];
        if (keys.some(k => /sort_col|sort_dir/i.test(k))) continue;
        const raw = u.searchParams.get("start_row");
        if (!raw) continue;
        const n = Number(raw);
        if (Number.isFinite(n) && n >= 1) starts.add(n);
      } catch {}
    }
    const maxStart = Math.max(...starts);
    const maxPage = Math.max(1, Math.floor((maxStart - 1) / 30) + 1);
    return { max_page: maxPage, max_start_row: maxStart, discovered_start_rows: [...starts].sort((a, b) => a - b) };
  }

  async function collectTransactions() {
    const PAGE_SIZE = 30, MAX_PAGES = 100;
    const first = await fetchLeagueDocument("/transactions?start_row=1");
    if (!first.ok) return { ok: false, complete: false, stop_reason: "first_page_fetch_error", headers: [], rows: [], unique_transaction_rows: 0, pages_read: 0, pages_expected: null, pages: [] };
    const pageInfo = deriveTransactionPageCount(first.document);
    const expectedPages = Math.min(pageInfo.max_page, MAX_PAGES);
    if (pageInfo.max_page > MAX_PAGES) warnings.push(`transactions: discovered ${pageInfo.max_page} pages; capped at ${MAX_PAGES}`);
    const allRows = [], seen = new Set(), pages = [];
    let headers = [], complete = true;
    for (let page = 1; page <= expectedPages; page++) {
      const startRow = 1 + (page - 1) * PAGE_SIZE;
      const result = page === 1 ? first : await fetchLeagueDocument(`/transactions?start_row=${startRow}`);
      if (!result.ok) { complete = false; pages.push({ page, start_row: startRow, ok: false, error: result.error }); continue; }
      const table = findTransactionTable(result.document);
      if (!table) { complete = false; pages.push({ page, start_row: startRow, ok: true, table_found: false }); continue; }
      if (!headers.length) headers = table.headers;
      const dataRows = table.rows.filter(isTransactionDataRow);
      let newRows = 0;
      for (const row of dataRows) {
        const key = JSON.stringify(row);
        if (!seen.has(key)) { seen.add(key); allRows.push(row); newRows++; }
      }
      pages.push({ page, start_row: startRow, ok: true, table_found: true, data_rows_found: dataRows.length, new_unique_rows: newRows });
    }
    if (pageInfo.max_page > MAX_PAGES) complete = false;
    return { ok: true, headers, rows: allRows, unique_transaction_rows: allRows.length, pages_read: pages.filter(p => p.ok).length, pages_expected: pageInfo.max_page, complete, stop_reason: complete ? "all_discovered_pages_read" : "incomplete_page_set", pagination: pageInfo, pages };
  }

  const rosterUrl = "https://api.cbssports.com/fantasy/league/rosters?version=3.0&team_id=all&response_format=JSON&access_token=" + encodeURIComponent(secret);
  const playerUrl = "https://api.cbssports.com/fantasy/players/search?SPORT=baseball&version=3.0&response_format=JSON&access_token=" + encodeURIComponent(secret);
  const statsUrl = "https://api.cbssports.com/fantasy/stats?version=3.0&timeframe=2026&period=ytd&SPORT=baseball&response_format=JSON";

  console.log("GBO COLLECTOR: collecting live CBS state...");

  const [rosters, players, stats, transactions, leagueDetails, standings, waiverReport] = await Promise.all([
    fetchJson("rosters API", rosterUrl),
    fetchJson("players API", playerUrl),
    fetchJson("stats API", statsUrl),
    collectTransactions(),
    captureSafePage("league details", "/rules"),
    captureSafePage("standings", "/standings/overall"),
    captureSafePage("waiver report", "/transactions/waivers-report", false)
  ]);

  const rosterTeams = rosters?.data?.body?.rosters?.teams ?? [];
  const playerList = players?.data?.body?.players ?? [];
  const playerStatsMap = stats?.data?.body?.player_stats ?? {};
  const statIds = playerStatsMap && typeof playerStatsMap === "object" ? Object.keys(playerStatsMap) : [];
  const playerIdSet = new Set(playerList.map(p => String(p.id)));
  const matchedStatIds = statIds.filter(id => playerIdSet.has(String(id)));
  const unmatchedStatIds = statIds.filter(id => !playerIdSet.has(String(id)));
  const inPlayerPool = playerList.filter(p => Number(p.in_player_pool) === 1);
  const freeAgentsInPool = inPlayerPool.filter(p => Number(p.free_agent) === 1);
  const waiversInPool = inPlayerPool.filter(p => Number(p.on_waivers) === 1);

  let currentHeaderState = extractMyHeaderState(document);
  if (!currentHeaderState.found && leagueDetails?.header_state?.found) currentHeaderState = leagueDetails.header_state;
  if (!currentHeaderState.found && standings?.header_state?.found) currentHeaderState = standings.header_state;

  const myTeam = rosterTeams.find(t => String(t.id) === GBO_TEAM_ID) || null;
  const myRosterCounts = myTeam ? myTeam.players.reduce((acc, p) => {
    const s = String(p.roster_status || "UNKNOWN");
    acc[s] = (acc[s] || 0) + 1;
    return acc;
  }, {}) : {};
  const myRosterSummary = myTeam ? {
    team_id: String(myTeam.id),
    team_name: myTeam.long_abbr || myTeam.short_name || myTeam.abbr,
    active_roster_salary: myTeam.active_roster_salary,
    total_roster_salary: myTeam.total_roster_salary,
    player_count: myTeam.players.length,
    roster_status_counts: myRosterCounts
  } : { found: false };

  const snapshot = sanitize({
    meta: { collector: VERSION, generated_at: new Date().toISOString(), started_at: startedAt.toISOString(), league_origin: leagueOrigin, current_path: location.pathname, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone, warnings, errors },
    source_health: {
      rosters_api: { ok: !!rosters.ok, status: rosters.status ?? null },
      players_api: { ok: !!players.ok, status: players.status ?? null },
      stats_api: { ok: !!stats.ok, status: stats.status ?? null },
      transactions: { ok: !!transactions.ok, complete: !!transactions.complete, stop_reason: transactions.stop_reason, pages_read: transactions.pages_read, pages_expected: transactions.pages_expected, unique_rows: transactions.unique_transaction_rows },
      league_details: { ok: !!leagueDetails.ok, data_present: !!leagueDetails.data_present },
      standings: { ok: !!standings.ok, data_present: !!standings.data_present },
      waiver_report: { ok: !!waiverReport.ok, data_present: !!waiverReport.data_present }
    },
    validation: {
      roster_team_count: rosterTeams.length,
      player_record_count: playerList.length,
      player_stat_record_count: statIds.length,
      player_stat_ids_matching_player_records: matchedStatIds.length,
      unmatched_player_stat_ids: unmatchedStatIds,
      in_player_pool_count: inPlayerPool.length,
      free_agents_in_player_pool: freeAgentsInPool.length,
      players_on_waivers_in_pool: waiversInPool.length
    },
    my_cbs_state: currentHeaderState,
    my_roster_summary: myRosterSummary,
    sources: { rosters, players, stats, transactions, reference: { league_details: leagueDetails, standings, waiver_report: waiverReport } }
  });

  const json = JSON.stringify(snapshot, null, 2);
  if (secret && json.includes(secret)) { console.error("GBO COLLECTOR ABORTED: CBS authentication token detected in output."); return; }
  if (/league password/i.test(json)) { console.error("GBO COLLECTOR ABORTED: league-password field detected in output."); return; }
  if (emailPattern.test(json)) { console.error("GBO COLLECTOR ABORTED: e-mail address detected in output."); return; }

  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const filename = `GBO_CBS_Snapshot_${VERSION}_${stamp}.json`;
  const blob = new Blob([json], { type: "application/json" });
  const downloadUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = downloadUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(downloadUrl), 1000);

  console.log("===== GBO COLLECTOR COMPLETE =====");
  console.log("COLLECTOR:", VERSION);
  console.log("FILE:", filename);
  console.log("ROSTER TEAMS:", rosterTeams.length);
  console.log("PLAYER RECORDS:", playerList.length);
  console.log("PLAYER STAT RECORDS:", statIds.length);
  console.log("MATCHED STAT IDS:", matchedStatIds.length);
  console.log("IN PLAYER POOL:", inPlayerPool.length);
  console.log("FREE AGENTS IN POOL:", freeAgentsInPool.length);
  console.log("ON WAIVERS IN POOL:", waiversInPool.length);
  console.log("TRANSACTIONS:", transactions.unique_transaction_rows, `(${transactions.pages_read}/${transactions.pages_expected} pages)`);
  console.log("TRANSACTIONS COMPLETE:", transactions.complete);
  console.log("FAB / WAIVER STATE:", currentHeaderState);
  console.log("MY ROSTER:", myRosterSummary);
  console.log("WAIVER REPORT DATA:", !!waiverReport.data_present);
  console.log("WARNINGS:", warnings.length);
  if (warnings.length) console.log("SAFE WARNINGS:", warnings);
})();