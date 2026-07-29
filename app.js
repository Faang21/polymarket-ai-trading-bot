// Polymarket AI Bot - Control Center Frontend Logic

document.addEventListener("DOMContentLoaded", () => {
  const workerUrlInput = document.getElementById("workerUrlInput");
  const saveUrlBtn = document.getElementById("saveUrlBtn");
  const urlSavedNotice = document.getElementById("urlSavedNotice");
  const statusBadge = document.getElementById("statusBadge");
  const statusText = document.getElementById("statusText");
  const startBotBtn = document.getElementById("startBotBtn");
  const stopBotBtn = document.getElementById("stopBotBtn");
  const refreshStatusBtn = document.getElementById("refreshStatusBtn");
  const actionFeedback = document.getElementById("actionFeedback");

  const csvUploadArea = document.getElementById("csvUploadArea");
  const csvFileInput = document.getElementById("csvFileInput");
  const loadCsvBtn = document.getElementById("loadCsvBtn");
  const logTableBody = document.getElementById("logTableBody");
  const searchLogInput = document.getElementById("searchLogInput");

  let parsedLogData = [];
  let decisionChartInstance = null;
  let timelineChartInstance = null;
  let equityChartInstance = null;

  const DEFAULT_WORKER_URL = "https://bot-control.aangcrypto21.workers.dev";
  const GITHUB_RAW_CSV_URL = "https://raw.githubusercontent.com/Faang21/polymarket-ai-trading-bot/main/catatan_trading_real.csv";
  const DEFAULT_WALLET = "0x65f465f0cd1c08e6740bd2e0b512c675668e51dd";

  // 1. Initial Setup: Load Saved URLs and Wallet
  const savedUrl = localStorage.getItem("POLYMARKET_WORKER_URL") || DEFAULT_WORKER_URL;
  if (workerUrlInput) workerUrlInput.value = savedUrl;
  fetchBotStatus(savedUrl);
  autoFetchGithubCsv();

  // Auto-refresh CSV log every 10 seconds for real-time live feed from VPS
  setInterval(autoFetchGithubCsv, 10000);

  async function autoFetchGithubCsv() {
    try {
      const cacheBustUrl = GITHUB_RAW_CSV_URL + "?t=" + Date.now();
      const res = await fetch(cacheBustUrl, { cache: "no-store" });
      if (res.ok) {
        const text = await res.text();
        parseAndRenderCsv(text);
      }
    } catch (err) {
      console.log("Auto-fetch CSV skipped or file not generated yet.");
    }
  }

  const walletAddressInput = document.getElementById("walletAddressInput");
  const saveWalletBtn = document.getElementById("saveWalletBtn");
  const usdcBalanceText = document.getElementById("usdcBalanceText");
  const polBalanceText = document.getElementById("polBalanceText");

  const savedWallet = localStorage.getItem("POLYMARKET_WALLET_ADDRESS") || DEFAULT_WALLET;
  if (walletAddressInput) walletAddressInput.value = savedWallet;
  fetchPolygonWalletBalances(savedWallet);

  // Event Listeners for Configuration
  if (saveUrlBtn) {
    saveUrlBtn.addEventListener("click", () => {
      const url = workerUrlInput.value.trim();
      if (!url) {
        alert("Harap masukkan URL Cloudflare Worker yang valid.");
        return;
      }
      localStorage.setItem("POLYMARKET_WORKER_URL", url);
      if (urlSavedNotice) {
        urlSavedNotice.classList.remove("hidden");
        setTimeout(() => urlSavedNotice.classList.add("hidden"), 3000);
      }
      fetchBotStatus(url);
    });
  }

  if (saveWalletBtn) {
    saveWalletBtn.addEventListener("click", () => {
      const addr = walletAddressInput.value.trim();
      if (addr && addr.startsWith("0x") && addr.length === 42) {
        localStorage.setItem("POLYMARKET_WALLET_ADDRESS", addr);
        fetchPolygonWalletBalances(addr);
      } else {
        alert("Harap masukkan alamat Ethereum / Polygon (0x...) yang valid 42 karakter.");
      }
    });
  }

  if (refreshStatusBtn) {
    refreshStatusBtn.addEventListener("click", () => {
      const url = getWorkerUrl();
      if (url) fetchBotStatus(url);
    });
  }

  if (startBotBtn) {
    startBotBtn.addEventListener("click", async () => {
      await sendToggleRequest("RUNNING");
    });
  }

  if (stopBotBtn) {
    stopBotBtn.addEventListener("click", async () => {
      await sendToggleRequest("STOPPED");
    });
  }

  function getWorkerUrl() {
    const url = workerUrlInput ? workerUrlInput.value.trim() : DEFAULT_WORKER_URL;
    if (!url) {
      if (actionFeedback) actionFeedback.innerHTML = `<span class="text-amber-400">⚠️ Harap masukkan URL Cloudflare Worker terlebih dahulu.</span>`;
      return null;
    }
    return url.replace(/\/+$/, "");
  }

  // Fetch status from Cloudflare Worker GET /status
  async function fetchBotStatus(baseUrl) {
    if (statusText) statusText.innerText = "CHECKING...";
    try {
      const endpoint = `${baseUrl}/status`;
      const res = await fetch(endpoint);
      if (res.ok) {
        const data = await res.json();
        updateStatusUI(data.status || data.bot_status);
      } else {
        updateStatusUI("ERROR");
      }
    } catch (err) {
      console.error("Error fetching bot status:", err);
      updateStatusUI("OFFLINE");
    }
  }

  // Send status change request POST /toggle
  async function sendToggleRequest(targetStatus) {
    const baseUrl = getWorkerUrl();
    if (!baseUrl) return;

    if (actionFeedback) actionFeedback.innerHTML = `<span class="text-slate-400">Mengirimkan sinyal saklar ke Cloudflare Worker...</span>`;
    if (startBotBtn) startBotBtn.disabled = true;
    if (stopBotBtn) stopBotBtn.disabled = true;

    try {
      const endpoint = `${baseUrl}/toggle`;
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: targetStatus }),
      });

      if (res.ok) {
        const data = await res.json();
        const currentStatus = data.status || targetStatus;
        updateStatusUI(currentStatus);

        if (actionFeedback) {
          if (currentStatus === "RUNNING") {
            actionFeedback.innerHTML = `<span class="text-emerald-400 font-semibold">✅ Saklar Diaktifkan: Bot RUNNING! (Eksekusi tiap 5 min).</span>`;
          } else {
            actionFeedback.innerHTML = `<span class="text-rose-400 font-semibold">🚨 EMERGENCY STOP Berhasil! Bot dihentikan.</span>`;
          }
        }
      } else {
        if (actionFeedback) actionFeedback.innerHTML = `<span class="text-rose-400">Gagal mengubah status (HTTP ${res.status}).</span>`;
      }
    } catch (err) {
      console.error("Error toggling bot status:", err);
      if (actionFeedback) actionFeedback.innerHTML = `<span class="text-rose-400">Error koneksi ke Cloudflare Worker.</span>`;
    } finally {
      if (startBotBtn) startBotBtn.disabled = false;
      if (stopBotBtn) stopBotBtn.disabled = false;
    }
  }

  // Update UI Badge based on status
  function updateStatusUI(status) {
    if (!statusBadge) return;
    const upper = (status || "").toUpperCase();
    if (upper === "RUNNING") {
      statusBadge.className = "flex items-center space-x-2 px-4 py-2 rounded-full glass-card border border-emerald-500/50 bg-emerald-950/40 text-emerald-300";
      statusBadge.innerHTML = `<span class="w-3 h-3 rounded-full bg-emerald-400 animate-pulse"></span> <span class="text-sm font-bold tracking-wider">LIVE: RUNNING</span>`;
    } else if (upper === "STOPPED") {
      statusBadge.className = "flex items-center space-x-2 px-4 py-2 rounded-full glass-card border border-rose-500/50 bg-rose-950/40 text-rose-300";
      statusBadge.innerHTML = `<span class="w-3 h-3 rounded-full bg-rose-500"></span> <span class="text-sm font-bold tracking-wider">OFF: STOPPED</span>`;
    } else {
      statusBadge.className = "flex items-center space-x-2 px-4 py-2 rounded-full glass-card border border-slate-700 text-slate-400";
      statusBadge.innerHTML = `<span class="w-3 h-3 rounded-full bg-amber-400"></span> <span class="text-sm font-semibold">${upper}</span>`;
    }
  }

  // Web3 Polygon RPC Balances with Multi-RPC Fallback & Polymarket Vault Detection
  const POLYGON_RPC_ENDPOINTS = [
    "https://polygon-bor-rpc.publicnode.com",
    "https://1rpc.io/matic",
    "https://rpc.ankr.com/polygon",
    "https://polygon.llamarpc.com"
  ];

  async function callPolygonRpc(bodyObj) {
    for (const rpcUrl of POLYGON_RPC_ENDPOINTS) {
      try {
        const res = await fetch(rpcUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(bodyObj),
        });
        if (res.ok) {
          const data = await res.json();
          if (data && data.result) return data.result;
        }
      } catch (e) {}
    }
    return null;
  }

  async function fetchPolygonWalletBalances(address) {
    if (usdcBalanceText) usdcBalanceText.innerText = "Loading...";
    if (polBalanceText) polBalanceText.innerText = "Loading...";

    const POLYMARKET_DEPOSIT = "0x998DAe6C3Eb18ecDD9C985CA4975051046F18EF0";
    const USDC_CONTRACT = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359";

    try {
      // 1. Fetch POL (MATIC) native balance from EOA wallet
      let totalPol = 0;
      const hexPolEOA = await callPolygonRpc({
        jsonrpc: "2.0", method: "eth_getBalance", params: [address, "latest"], id: 1
      });
      if (hexPolEOA && hexPolEOA !== "0x0") totalPol += Number(BigInt(hexPolEOA)) / 1e18;

      const hexPolDeposit = await callPolygonRpc({
        jsonrpc: "2.0", method: "eth_getBalance", params: [POLYMARKET_DEPOSIT, "latest"], id: 2
      });
      if (hexPolDeposit && hexPolDeposit !== "0x0") totalPol += Number(BigInt(hexPolDeposit)) / 1e18;

      if (polBalanceText) polBalanceText.innerText = `${totalPol.toFixed(4)} POL`;

      // 2. Fetch USDC balance from EOA & Polymarket Deposit Address
      const cleanAddrEOA = address.substring(2).padStart(64, "0");
      const cleanAddrDeposit = POLYMARKET_DEPOSIT.substring(2).padStart(64, "0");
      let totalUsdcVal = 0;

      // USDC on EOA wallet
      const hexUsdcEOA = await callPolygonRpc({
        jsonrpc: "2.0", method: "eth_call",
        params: [{ to: USDC_CONTRACT, data: "0x70a08231" + cleanAddrEOA }, "latest"], id: 3
      });
      if (hexUsdcEOA && hexUsdcEOA !== "0x") totalUsdcVal += Number(BigInt(hexUsdcEOA)) / 1e6;

      // USDC on Polymarket Deposit Address
      const hexUsdcDeposit = await callPolygonRpc({
        jsonrpc: "2.0", method: "eth_call",
        params: [{ to: USDC_CONTRACT, data: "0x70a08231" + cleanAddrDeposit }, "latest"], id: 4
      });
      if (hexUsdcDeposit && hexUsdcDeposit !== "0x") totalUsdcVal += Number(BigInt(hexUsdcDeposit)) / 1e6;

      const formattedUsdc = totalUsdcVal.toFixed(2);
      if (usdcBalanceText) usdcBalanceText.innerText = `$${formattedUsdc}`;
      renderEquityChart(formattedUsdc);

    } catch (err) {
      console.log("Error fetching Polygon RPC balances:", err);
      if (usdcBalanceText) usdcBalanceText.innerText = "$0.00";
      if (polBalanceText) polBalanceText.innerText = "0.0000 POL";
      renderEquityChart("0");
    }
  }

  function renderEquityChart(currentUsdcStr) {
    const ctxElement = document.getElementById("equityChart");
    if (!ctxElement) return;
    const ctx = ctxElement.getContext("2d");
    if (equityChartInstance) equityChartInstance.destroy();

    const currentUsdc = parseFloat(currentUsdcStr) || 0;
    const labels = ["12:00", "13:00", "14:00", "14:30", "14:45", "Live Now"];
    const equityData = [currentUsdc, currentUsdc, currentUsdc, currentUsdc, currentUsdc, currentUsdc];

    equityChartInstance = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "USDC Portfolio Value ($)",
            data: equityData,
            borderColor: "#10b981",
            backgroundColor: "rgba(16, 185, 129, 0.15)",
            fill: true,
            tension: 0.4,
            pointRadius: 5,
            pointBackgroundColor: "#10b981",
            pointBorderColor: "#ffffff",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.05)" } },
          y: {
            ticks: {
              color: "#64748b",
              callback: (val) => "$" + Number(val).toFixed(2),
            },
            grid: { color: "rgba(255,255,255,0.05)" },
          },
        },
        plugins: {
          legend: { labels: { color: "#94a3b8" } },
        },
      },
    });
  }

  // CSV Parsing and File Handling
  if (csvUploadArea) csvUploadArea.addEventListener("click", () => csvFileInput && csvFileInput.click());
  if (loadCsvBtn) loadCsvBtn.addEventListener("click", () => csvFileInput && csvFileInput.click());

  if (csvFileInput) {
    csvFileInput.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (file) readCsvFile(file);
    });
  }

  if (csvUploadArea) {
    csvUploadArea.addEventListener("dragover", (e) => {
      e.preventDefault();
      csvUploadArea.classList.add("border-cyan-500");
    });
    csvUploadArea.addEventListener("dragleave", () => csvUploadArea.classList.remove("border-cyan-500"));
    csvUploadArea.addEventListener("drop", (e) => {
      e.preventDefault();
      csvUploadArea.classList.remove("border-cyan-500");
      if (e.dataTransfer.files.length > 0) readCsvFile(e.dataTransfer.files[0]);
    });
  }

  async function autoFetchGithubCsv() {
    try {
      const res = await fetch(GITHUB_RAW_CSV_URL);
      if (res.ok) {
        const text = await res.text();
        parseAndRenderCsv(text);
      }
    } catch (err) {
      console.log("Auto-fetch CSV skipped or file not generated yet.");
    }
  }

  function readCsvFile(file) {
    const reader = new FileReader();
    reader.onload = (evt) => parseAndRenderCsv(evt.target.result);
    reader.readAsText(file);
  }

  function parseAndRenderCsv(csvText) {
    const lines = csvText.split("\n").filter((l) => l.trim().length > 0);
    if (lines.length <= 1) {
      if (logTableBody) logTableBody.innerHTML = `<tr><td colspan="6" class="px-4 py-6 text-center text-slate-500">Belum ada data trading. Bot belum dijalankan di VPS.</td></tr>`;
      updateChartsAndStats([]);
      return;
    }

    parsedLogData = [];
    // New CSV format: Timestamp,Market,TokenID,Price,Side,BetUSD,OrderID,Alasan
    for (let i = lines.length - 1; i >= 1; i--) {
      const rowValues = parseCsvLine(lines[i]);
      if (rowValues.length >= 5) {
        parsedLogData.push({
          timestamp:  rowValues[0] || "",
          market:     rowValues[1] || "",
          tokenId:    rowValues[2] || "",
          price:      rowValues[3] || "",
          side:       rowValues[4] || "HOLD",
          betUsd:     rowValues[5] || "0",
          orderId:    rowValues[6] || "",
          alasan:     rowValues[7] || "",
        });
      }
    }

    renderTableRows(parsedLogData);
    updateChartsAndStats(parsedLogData);
  }

  function updateChartsAndStats(data) {
    let buyYesCount = 0;
    let buyNoCount = 0;
    let holdCount = 0;
    let totalBetUsd = 0;
    let estimatedPnl = 0;

    data.forEach((item) => {
      const side = (item.side || "").toUpperCase();
      const price = parseFloat(item.price) || 0.5;
      const bet = parseFloat(item.betUsd) || 0;

      if (side === "BUY_YES") {
        buyYesCount++;
        totalBetUsd += bet;
        if (price > 0 && price < 1) estimatedPnl += (1.0 / price - 1.0) * bet * 0.4;
      } else if (side === "BUY_NO") {
        buyNoCount++;
        totalBetUsd += bet;
        if (price > 0 && price < 1) estimatedPnl += (1.0 / price - 1.0) * bet * 0.4;
      } else {
        holdCount++;
      }
    });

    const elTotal = document.getElementById("statTotal");
    const elYes   = document.getElementById("statBuyYes");
    const elNo    = document.getElementById("statBuyNo");
    const elHold  = document.getElementById("statHold");
    const elPnl   = document.getElementById("statPnl");

    if (elTotal) elTotal.innerText = data.length;
    if (elYes)   elYes.innerText   = buyYesCount;
    if (elNo)    elNo.innerText    = buyNoCount;
    if (elHold)  elHold.innerText  = holdCount;
    if (elPnl) {
      const sign = estimatedPnl >= 0 ? "+" : "";
      elPnl.innerText = `${sign}$${estimatedPnl.toFixed(2)}`;
      elPnl.className = estimatedPnl >= 0
        ? "text-xl font-black text-emerald-400 mt-1"
        : "text-xl font-black text-rose-400 mt-1";
    }

    renderDecisionChart(buyYesCount, buyNoCount, holdCount);
    renderTimelineChart(data);
  }

  function renderDecisionChart(yes, no, hold) {
    const ctxElement = document.getElementById("decisionChart");
    if (!ctxElement) return;
    const ctx = ctxElement.getContext("2d");
    if (decisionChartInstance) decisionChartInstance.destroy();

    decisionChartInstance = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: ["BUY YES", "BUY NO", "HOLD"],
        datasets: [
          {
            data: [yes, no, hold],
            backgroundColor: ["#10b981", "#f43f5e", "#64748b"],
            borderColor: "#0f172a",
            borderWidth: 3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "bottom",
            labels: { color: "#94a3b8", font: { family: "Plus Jakarta Sans" } },
          },
        },
      },
    });
  }

  function renderTimelineChart(data) {
    const ctxElement = document.getElementById("timelineChart");
    if (!ctxElement) return;
    const ctx = ctxElement.getContext("2d");
    if (timelineChartInstance) timelineChartInstance.destroy();

    const chronological = [...data].reverse();
    const labels = chronological.map((d) => d.timestamp ? new Date(d.timestamp).toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" }) : "");

    let cumulativeScore = 0;
    const scores = chronological.map((d) => {
      const side = (d.side || "").toUpperCase();
      if (side === "BUY_YES") cumulativeScore += 1;
      else if (side === "BUY_NO") cumulativeScore -= 1;
      return cumulativeScore;
    });

    timelineChartInstance = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [{
          label: "Tren Keputusan AI (Real Trade)",
          data: scores,
          borderColor: "#06b6d4",
          backgroundColor: "rgba(6, 182, 212, 0.1)",
          fill: true,
          tension: 0.3,
          pointRadius: 4,
          pointBackgroundColor: "#06b6d4",
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.05)" } },
          y: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.05)" } },
        },
        plugins: { legend: { labels: { color: "#94a3b8" } } },
      },
    });
  }

  function parseCsvLine(text) {
    const regex = /(?:,|\n|^)("(?:(?:"")*[^"]*)*"|[^",\n]*)/g;
    const matches = [];
    let match = null;
    while ((match = regex.exec(text)) !== null) {
      let val = match[1];
      if (val.startsWith('"') && val.endsWith('"')) {
        val = val.substring(1, val.length - 1).replace(/""/g, '"');
      }
      matches.push(val);
    }
    return matches;
  }

  function renderTableRows(data) {
    if (!logTableBody) return;
    if (!data || data.length === 0) {
      logTableBody.innerHTML = `<tr><td colspan="6" class="px-4 py-6 text-center text-slate-500">Belum ada data trading real. Jalankan bot di VPS terlebih dahulu.</td></tr>`;
      return;
    }

    logTableBody.innerHTML = data.map((row) => {
      const side = (row.side || "").toUpperCase();
      let sideBadge = "";
      if (side === "BUY_YES") {
        sideBadge = `<span class="px-2.5 py-1 rounded-md bg-emerald-500/20 text-emerald-300 font-bold border border-emerald-500/40">BUY YES</span>`;
      } else if (side === "BUY_NO") {
        sideBadge = `<span class="px-2.5 py-1 rounded-md bg-rose-500/20 text-rose-300 font-bold border border-rose-500/40">BUY NO</span>`;
      } else {
        sideBadge = `<span class="px-2.5 py-1 rounded-md bg-slate-800 text-slate-300 font-semibold border border-slate-700">HOLD</span>`;
      }

      const isRealOrder = row.orderId && row.orderId !== "HOLD" && row.orderId !== "SIMULATED" && !row.orderId.startsWith("ERROR");
      const orderBadge = isRealOrder
        ? `<span class="text-xs font-mono text-emerald-400" title="${row.orderId}">✅ ${row.orderId.substring(0, 10)}...</span>`
        : `<span class="text-xs text-slate-500">${row.orderId || "-"}</span>`;

      const formattedTime = row.timestamp ? new Date(row.timestamp).toLocaleString("id-ID") : "N/A";
      const bet = parseFloat(row.betUsd) || 0;

      return `
        <tr class="hover:bg-slate-900/60 transition">
          <td class="px-4 py-3 text-slate-400 font-mono text-[11px] whitespace-nowrap">${formattedTime}</td>
          <td class="px-4 py-3 font-medium text-slate-100 max-w-xs truncate" title="${row.market}">${row.market}</td>
          <td class="px-4 py-3 text-center font-mono text-cyan-400">${parseFloat(row.price || 0).toFixed(4)}</td>
          <td class="px-4 py-3 text-center whitespace-nowrap">${sideBadge}</td>
          <td class="px-4 py-3 text-center text-amber-300 font-bold">${bet > 0 ? "$" + bet.toFixed(2) : "-"}</td>
          <td class="px-4 py-3 text-center">${orderBadge}</td>
        </tr>
      `;
    }).join("");
  }

  // Search filter
  if (searchLogInput) {
    searchLogInput.addEventListener("input", (e) => {
      const q = e.target.value.toLowerCase().trim();
      if (!q) {
        renderTableRows(parsedLogData);
        return;
      }
      const filtered = parsedLogData.filter((item) => {
        return (
          item.marketQuestion.toLowerCase().includes(q) ||
          item.eventTitle.toLowerCase().includes(q) ||
          item.keputusan.toLowerCase().includes(q) ||
          item.alasan.toLowerCase().includes(q)
        );
      });
      renderTableRows(filtered);
    });
  }
});
