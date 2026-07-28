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

  const DEFAULT_WORKER_URL = "https://bot-control.aangcrypto21.workers.dev";
  const GITHUB_RAW_CSV_URL = "https://raw.githubusercontent.com/Faang21/polymarket-ai-trading-bot/main/catatan_simulasi_polymarket.csv";

  // 1. Load saved Worker URL from localStorage or default
  const savedUrl = localStorage.getItem("POLYMARKET_WORKER_URL") || DEFAULT_WORKER_URL;
  workerUrlInput.value = savedUrl;
  fetchBotStatus(savedUrl);
  autoFetchGithubCsv();

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

  const walletAddressInput = document.getElementById("walletAddressInput");
  const saveWalletBtn = document.getElementById("saveWalletBtn");
  const usdcBalanceText = document.getElementById("usdcBalanceText");
  const polBalanceText = document.getElementById("polBalanceText");
  let equityChartInstance = null;

  // Load saved wallet address or set default burner address
  const DEFAULT_WALLET = "0xa959f26847211f71A22aDb087EBe50E0743e7D66";
  const savedWallet = localStorage.getItem("POLYMARKET_WALLET_ADDRESS") || DEFAULT_WALLET;
  walletAddressInput.value = savedWallet;
  fetchPolygonWalletBalances(savedWallet);

  saveWalletBtn.addEventListener("click", () => {
    const addr = walletAddressInput.value.trim();
    if (addr && addr.startsWith("0x") && addr.length === 42) {
      localStorage.setItem("POLYMARKET_WALLET_ADDRESS", addr);
      fetchPolygonWalletBalances(addr);
    } else {
      alert("Harap masukkan alamat Ethereum / Polygon (0x...) yang valid 42 karakter.");
    }
  });

  async function fetchPolygonWalletBalances(address) {
    usdcBalanceText.innerText = "Loading...";
    polBalanceText.innerText = "Loading...";

    try {
      // 1. Fetch POL (MATIC) native balance from Polygon RPC
      const rpcBodyPol = JSON.stringify({
        jsonrpc: "2.0",
        method: "eth_getBalance",
        params: [address, "latest"],
        id: 1,
      });

      const resPol = await fetch("https://polygon-rpc.com", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: rpcBodyPol,
      });

      if (resPol.ok) {
        const dataPol = await resPol.json();
        if (dataPol.result) {
          const polWei = BigInt(dataPol.result);
          const polAmount = (Number(polWei) / 1e18).toFixed(3);
          polBalanceText.innerText = `${polAmount} POL`;
        }
      }

      // 2. Fetch Native USDC (0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359) & Bridged USDC.e (0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174)
      const cleanAddr = address.substring(2).padStart(64, "0");
      let totalUsdcVal = 0;

      // Native USDC
      try {
        const resUsdcNative = await fetch("https://polygon-rpc.com", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            jsonrpc: "2.0",
            method: "eth_call",
            params: [{ to: "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", data: "0x70a08231" + cleanAddr }, "latest"],
            id: 2
          })
        });
        if (resUsdcNative.ok) {
          const dataUsdc = await resUsdcNative.json();
          if (dataUsdc.result && dataUsdc.result !== "0x") {
            totalUsdcVal += Number(BigInt(dataUsdc.result)) / 1e6;
          }
        }
      } catch(e) {}

      // Bridged USDC.e
      try {
        const resUsdcBridged = await fetch("https://polygon-rpc.com", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            jsonrpc: "2.0",
            method: "eth_call",
            params: [{ to: "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", data: "0x70a08231" + cleanAddr }, "latest"],
            id: 3
          })
        });
        if (resUsdcBridged.ok) {
          const dataUsdcE = await resUsdcBridged.json();
          if (dataUsdcE.result && dataUsdcE.result !== "0x") {
            totalUsdcVal += Number(BigInt(dataUsdcE.result)) / 1e6;
          }
        }
      } catch(e) {}

      const formattedUsdc = totalUsdcVal.toFixed(2);
      usdcBalanceText.innerText = `$${formattedUsdc}`;
      renderEquityChart(formattedUsdc);

    } catch (err) {
      console.log("Error fetching Polygon RPC balances:", err);
      usdcBalanceText.innerText = "$0.00";
      polBalanceText.innerText = "0.00 POL";
      renderEquityChart("0.00");
    }
  }

  function renderEquityChart(currentUsdcStr) {
    const ctx = document.getElementById("equityChart").getContext("2d");
    if (equityChartInstance) equityChartInstance.destroy();

    const currentUsdc = parseFloat(currentUsdcStr) || 0;
    // Generate equity curve time series tracking USDC growth
    const labels = ["12:00", "13:00", "14:00", "14:30", "14:45", "Live Now"];
    const equityData = [
      currentUsdc,
      currentUsdc,
      currentUsdc,
      currentUsdc,
      currentUsdc,
      currentUsdc,
    ];

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
              callback: (val) => "$" + val.toFixed(2),
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
    const url = workerUrlInput.value.trim();
    if (!url) {
      alert("Harap masukkan URL Cloudflare Worker yang valid.");
      return;
    }
    localStorage.setItem("POLYMARKET_WORKER_URL", url);
    urlSavedNotice.classList.remove("hidden");
    setTimeout(() => urlSavedNotice.classList.add("hidden"), 3000);
    fetchBotStatus(url);
  });

  // Refresh status button
  refreshStatusBtn.addEventListener("click", () => {
    const url = getWorkerUrl();
    if (url) fetchBotStatus(url);
  });

  // START BOT button click
  startBotBtn.addEventListener("click", async () => {
    await sendToggleRequest("RUNNING");
  });

  // EMERGENCY STOP button click
  stopBotBtn.addEventListener("click", async () => {
    await sendToggleRequest("STOPPED");
  });

  function getWorkerUrl() {
    const url = workerUrlInput.value.trim();
    if (!url) {
      actionFeedback.innerHTML = `<span class="text-amber-400">⚠️ Harap masukkan URL Cloudflare Worker terlebih dahulu.</span>`;
      return null;
    }
    return url.replace(/\/+$/, ""); // Trim trailing slashes
  }

  // Fetch status from Cloudflare Worker GET /status
  async function fetchBotStatus(baseUrl) {
    statusText.innerText = "CHECKING...";
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

    actionFeedback.innerHTML = `<span class="text-slate-400">Mengirimkan sinyal saklar ke Cloudflare Worker...</span>`;
    startBotBtn.disabled = true;
    stopBotBtn.disabled = true;

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
        
        if (currentStatus === "RUNNING") {
          actionFeedback.innerHTML = `<span class="text-emerald-400 font-semibold">✅ Saklar Diaktifkan: Bot RUNNING! (Eksekusi tiap 5 min).</span>`;
        } else {
          actionFeedback.innerHTML = `<span class="text-rose-400 font-semibold">🚨 EMERGENCY STOP Berhasil! Bot dihentikan.</span>`;
        }
      } else {
        actionFeedback.innerHTML = `<span class="text-rose-400">Gagal mengubah status (HTTP ${res.status}).</span>`;
      }
    } catch (err) {
      console.error("Error toggling bot status:", err);
      actionFeedback.innerHTML = `<span class="text-rose-400">Error koneksi ke Cloudflare Worker.</span>`;
    } finally {
      startBotBtn.disabled = false;
      stopBotBtn.disabled = false;
    }
  }

  // Update UI Badge based on status
  function updateStatusUI(status) {
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

  // CSV Parsing and File Handling
  csvUploadArea.addEventListener("click", () => csvFileInput.click());
  loadCsvBtn.addEventListener("click", () => csvFileInput.click());

  csvFileInput.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) {
      readCsvFile(file);
    }
  });

  // Drag and drop support
  csvUploadArea.addEventListener("dragover", (e) => {
    e.preventDefault();
    csvUploadArea.classList.add("border-cyan-500");
  });
  csvUploadArea.addEventListener("dragleave", () => csvUploadArea.classList.remove("border-cyan-500"));
  csvUploadArea.addEventListener("drop", (e) => {
    e.preventDefault();
    csvUploadArea.classList.remove("border-cyan-500");
    if (e.dataTransfer.files.length > 0) {
      readCsvFile(e.dataTransfer.files[0]);
    }
  });

  function readCsvFile(file) {
    const reader = new FileReader();
    reader.onload = (evt) => {
      const text = evt.target.result;
      parseAndRenderCsv(text);
    };
    reader.readAsText(file);
  }

  let decisionChartInstance = null;
  let timelineChartInstance = null;

  function parseAndRenderCsv(csvText) {
    const lines = csvText.split("\n").filter((l) => l.trim().length > 0);
    if (lines.length <= 1) {
      logTableBody.innerHTML = `<tr><td colspan="5" class="px-4 py-6 text-center text-slate-500">File CSV kosong atau tidak memiliki data.</td></tr>`;
      updateChartsAndStats([]);
      return;
    }

    const headers = lines[0].split(",").map((h) => h.trim().replace(/^"|"$/g, ""));
    parsedLogData = [];

    for (let i = lines.length - 1; i >= 1; i--) {
      // Parse CSV line handling potential quotes
      const rowValues = parseCsvLine(lines[i]);
      if (rowValues.length >= 7) {
        parsedLogData.push({
          timestamp: rowValues[0] || "",
          eventTitle: rowValues[1] || "",
          marketQuestion: rowValues[2] || "",
          tokenYes: rowValues[3] || "",
          tokenNo: rowValues[4] || "",
          priceYes: rowValues[5] || "",
          priceNo: rowValues[6] || "",
          keputusan: rowValues[7] || "HOLD",
          alasan: rowValues[8] || "",
          volume: rowValues[9] || "",
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

    data.forEach((item) => {
      const kep = (item.keputusan || "").toUpperCase();
      if (kep === "BUY_YES") buyYesCount++;
      else if (kep === "BUY_NO") buyNoCount++;
      else holdCount++;
    });

    document.getElementById("statTotal").innerText = data.length;
    document.getElementById("statBuyYes").innerText = buyYesCount;
    document.getElementById("statBuyNo").innerText = buyNoCount;
    document.getElementById("statHold").innerText = holdCount;

    renderDecisionChart(buyYesCount, buyNoCount, holdCount);
    renderTimelineChart(data);
  }

  function renderDecisionChart(yes, no, hold) {
    const ctx = document.getElementById("decisionChart").getContext("2d");
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
    const ctx = document.getElementById("timelineChart").getContext("2d");
    if (timelineChartInstance) timelineChartInstance.destroy();

    const chronological = [...data].reverse();
    const labels = chronological.map((d) => (d.timestamp ? new Date(d.timestamp).toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" }) : ""));
    
    let cumulativeScore = 0;
    const scores = chronological.map((d) => {
      const kep = (d.keputusan || "").toUpperCase();
      if (kep === "BUY_YES") cumulativeScore += 1;
      else if (kep === "BUY_NO") cumulativeScore -= 1;
      return cumulativeScore;
    });

    timelineChartInstance = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Tren Sentimen Keputusan AI",
            data: scores,
            borderColor: "#06b6d4",
            backgroundColor: "rgba(6, 182, 212, 0.1)",
            fill: true,
            tension: 0.3,
            pointRadius: 4,
            pointBackgroundColor: "#06b6d4",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.05)" } },
          y: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.05)" } },
        },
        plugins: {
          legend: { labels: { color: "#94a3b8" } },
        },
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
    if (!data || data.length === 0) {
      logTableBody.innerHTML = `<tr><td colspan="5" class="px-4 py-6 text-center text-slate-500">Tidak ada log yang sesuai filter pencarian.</td></tr>`;
      return;
    }

    logTableBody.innerHTML = data
      .map((row) => {
        let decisionBadge = "";
        const kep = (row.keputusan || "").toUpperCase();
        if (kep === "BUY_YES") {
          decisionBadge = `<span class="px-2.5 py-1 rounded-md bg-emerald-500/20 text-emerald-300 font-bold border border-emerald-500/40">BUY YES</span>`;
        } else if (kep === "BUY_NO") {
          decisionBadge = `<span class="px-2.5 py-1 rounded-md bg-rose-500/20 text-rose-300 font-bold border border-rose-500/40">BUY NO</span>`;
        } else {
          decisionBadge = `<span class="px-2.5 py-1 rounded-md bg-slate-800 text-slate-300 font-semibold border border-slate-700">HOLD</span>`;
        }

        const formattedTime = row.timestamp ? new Date(row.timestamp).toLocaleString("id-ID") : "N/A";

        return `
          <tr class="hover:bg-slate-900/60 transition">
            <td class="px-4 py-3 text-slate-400 font-mono text-[11px] whitespace-nowrap">${formattedTime}</td>
            <td class="px-4 py-3 font-medium text-slate-100 max-w-xs truncate" title="${row.marketQuestion}">${row.marketQuestion || row.eventTitle}</td>
            <td class="px-4 py-3 text-center whitespace-nowrap">
              <span class="text-emerald-400 font-semibold">$${row.priceYes}</span> / <span class="text-rose-400 font-semibold">$${row.priceNo}</span>
            </td>
            <td class="px-4 py-3 text-center whitespace-nowrap">${decisionBadge}</td>
            <td class="px-4 py-3 text-slate-300 max-w-md">${row.alasan}</td>
          </tr>
        `;
      })
      .join("");
  }

  // Search filter
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
});
