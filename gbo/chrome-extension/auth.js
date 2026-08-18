(() => {
  const params = new URLSearchParams(location.search);
  const code = params.get("code") || "";
  const verificationUri = params.get("verification_uri") || "https://github.com/login/device";
  document.getElementById("code").textContent = code;
  document.getElementById("open").addEventListener("click", () => {
    chrome.tabs.create({ url: verificationUri });
  });
})();
