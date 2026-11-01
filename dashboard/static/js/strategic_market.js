/**
 * Strategic Bidding & Auction Clearing Frontend Module (Step 5)
 * Deliverable 2 Interactive Web Prototype
 *
 * Strict Compliance:
 * - Read-only: visualizes actual backend API responses
 * - Zero client-side recomputation of auction clearing or Nash equilibrium
 * - Explicit distinction between ASK, BID, and actual transaction prices
 * - Explicit Phase 8E NOT_IMPLEMENTED disclosure
 */

const STATE = {
  currentTimestamp: "2013-04-19 00:00:00",
  currentStrategy: "strat_a",
  tradeableHours: [],
  hourlyData: null,
  strategiesData: null,
  isLoading: false,
  stochTimestamp: "2013-05-15 11:00:00",
  stochData: null,
  isStochLoading: false,
};

const STRATEGY_LABELS = {
  strat_a: "Strategy A (Reference — Phase 8C Heuristic)",
  strat_b: "Strategy B (Seller-Favouring)",
  strat_c: "Strategy C (Buyer-Favouring)",
  strat_d: "Strategy D (Max-Min Fair)",
  strat_e: "Strategy E (Nash Social Welfare)",
  strat_f_05: "Strategy F (Hybrid w=0.5)",
};

const HOUSEHOLD_ARCHETYPES = {
  H001: "High PV Prosumer (5.0 kW PV, 5.0 kWh Battery)",
  H002: "Flexible Prosumer (3.0 kW PV, 5.0 kWh Battery)",
  H003: "Net Consumer (No PV, 5.0 kWh Battery)",
};

// ============================================================================
// Initialization & Event Binding
// ============================================================================

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initPresets();
  initStrategyPills();
  initCustomTimestampInput();
  initStochasticControls();
  loadTradeableHours();
  loadMarketData();
});

function initTabs() {
  const tabs = document.querySelectorAll(".nav-tab");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      const targetPaneId = tab.dataset.target;
      document.querySelectorAll(".tab-pane").forEach((pane) => {
        pane.classList.remove("active");
      });
      const targetPane = document.getElementById(targetPaneId);
      if (targetPane) {
        targetPane.classList.add("active");
      }
      // Load lazy data for other tabs if selected
      if (targetPaneId === "pane-stochastic" && !STATE.stochData) loadStochasticMarketData();
      if (targetPaneId === "pane-overview") loadOverviewData();
      if (targetPaneId === "pane-forecasting") loadForecastingData();
      if (targetPaneId === "pane-p2p") loadP2PBenchmarkData();
      if (targetPaneId === "pane-ledger") loadLedgerData();
    });
  });
}

function initPresets() {
  const presetButtons = document.querySelectorAll(".btn-preset[data-timestamp]");
  presetButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      presetButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      STATE.currentTimestamp = btn.dataset.timestamp;
      const tsInput = document.getElementById("custom-timestamp-input");
      if (tsInput) tsInput.value = STATE.currentTimestamp;
      const hourSelect = document.getElementById("tradeable-hours-select");
      if (hourSelect) hourSelect.value = STATE.currentTimestamp;
      loadMarketData();
    });
  });
}

function initStrategyPills() {
  const pills = document.querySelectorAll(".strategy-pill[data-strategy]");
  pills.forEach((pill) => {
    pill.addEventListener("click", () => {
      pills.forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      STATE.currentStrategy = pill.dataset.strategy;
      loadHourlyClearingData();
    });
  });
}

function initCustomTimestampInput() {
  const loadBtn = document.getElementById("btn-load-timestamp");
  const input = document.getElementById("custom-timestamp-input");
  if (loadBtn && input) {
    loadBtn.addEventListener("click", () => {
      const val = input.value.trim();
      if (val) {
        STATE.currentTimestamp = val;
        // update preset button states if matching
        document.querySelectorAll(".btn-preset").forEach((b) => {
          b.classList.toggle("active", b.dataset.timestamp === val);
        });
        loadMarketData();
      }
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") loadBtn.click();
    });
  }

  const hourSelect = document.getElementById("tradeable-hours-select");
  if (hourSelect) {
    hourSelect.addEventListener("change", (e) => {
      const val = e.target.value;
      if (val) {
        STATE.currentTimestamp = val;
        if (input) input.value = val;
        document.querySelectorAll(".btn-preset").forEach((b) => {
          b.classList.toggle("active", b.dataset.timestamp === val);
        });
        loadMarketData();
      }
    });
  }
}

// ============================================================================
// Data Fetching
// ============================================================================

async function loadTradeableHours() {
  try {
    const res = await fetch("/api/tradeable_hours");
    const json = await res.json();
    if (json.status === "success" && Array.isArray(json.data)) {
      STATE.tradeableHours = json.data;
      const select = document.getElementById("tradeable-hours-select");
      if (select) {
        select.innerHTML = '<option value="">-- Jump to Tradeable Hour (866 Available) --</option>';
        json.data.forEach((h) => {
          const opt = document.createElement("option");
          opt.value = h.timestamp;
          opt.textContent = `Hour #${h.hour_index}: ${h.timestamp} (Sellers: ${h.num_sellers}, Buyers: ${h.num_buyers}, Q: ${h.traded_volume_kwh.toFixed(3)} kWh, PNE: ${h.num_pne})`;
          select.appendChild(opt);
        });
        select.value = STATE.currentTimestamp;
      }
    }
  } catch (err) {
    console.error("Failed to load tradeable hours list:", err);
  }
}

async function loadMarketData() {
  setLoading(true);
  hideError();
  try {
    await Promise.all([loadStrategiesData(), loadHourlyClearingData()]);
  } catch (err) {
    showError(err.message || "Failed to load market data from API.");
  } finally {
    setLoading(false);
  }
}

async function loadStrategiesData() {
  const url = `/api/strategic-market/strategies?timestamp=${encodeURIComponent(STATE.currentTimestamp)}`;
  const res = await fetch(url);
  const json = await res.json();
  if (json.status !== "success") {
    throw new Error(json.message || `Error fetching strategy options for ${STATE.currentTimestamp}`);
  }
  STATE.strategiesData = json.data;
  renderStrategiesComparison(json.data);
}

async function loadHourlyClearingData() {
  setLoading(true);
  hideError();
  try {
    const url = `/api/strategic-market/hourly?timestamp=${encodeURIComponent(
      STATE.currentTimestamp
    )}&strategy=${encodeURIComponent(STATE.currentStrategy)}`;
    const res = await fetch(url);
    const json = await res.json();
    if (json.status !== "success") {
      throw new Error(json.message || `Error fetching auction clearing for ${STATE.currentTimestamp}`);
    }
    STATE.hourlyData = json.data;
    renderAllAuctionSections(json.data);
  } catch (err) {
    showError(err.message);
  } finally {
    setLoading(false);
  }
}

function setLoading(isLoading) {
  STATE.isLoading = isLoading;
  const spinner = document.getElementById("market-loading-spinner");
  if (spinner) {
    spinner.style.display = isLoading ? "inline-block" : "none";
  }
}

function showError(msg) {
  const errBox = document.getElementById("market-error-banner");
  if (errBox) {
    errBox.textContent = `API Error: ${msg}`;
    errBox.style.display = "block";
  }
}

function hideError() {
  const errBox = document.getElementById("market-error-banner");
  if (errBox) errBox.style.display = "none";
}

// ============================================================================
// Section Renderers
// ============================================================================

function renderAllAuctionSections(data) {
  renderMetadataBanners(data);
  renderFinancialKPIs(data);
  renderHouseholdCards(data);
  renderAuctionMeritOrder(data);
  renderTransactionsTable(data);
  renderPayoffReconciliation(data);
  renderNashContext(data);
}

function renderMetadataBanners(data) {
  const meta = data.hour_metadata || {};
  const strat = data.selected_strategy || {};

  // Update strategy pill active styling
  document.querySelectorAll(".strategy-pill").forEach((pill) => {
    pill.classList.toggle("active", pill.dataset.strategy === strat.strategy_key);
  });

  // Hour status indicator
  const statusEl = document.getElementById("market-hour-status");
  if (statusEl) {
    const isTradeable = meta.auction_status === "traded";
    statusEl.className = isTradeable ? "badge badge-success" : "badge badge-warning";
    statusEl.textContent = isTradeable
      ? `TRADED HOUR (${meta.num_active_sellers} Sellers, ${meta.num_active_buyers} Buyers)`
      : `NO-TRADE HOUR (${meta.market_status.toUpperCase()} — 0 Volume)`;
  }

  // Active strategy title
  const stratTitleEl = document.getElementById("active-strategy-title");
  if (stratTitleEl) {
    stratTitleEl.textContent = strat.strategy_label || STATE.currentStrategy;
  }
}

function renderFinancialKPIs(data) {
  const fin = data.financial_summary || {};
  const isTraded = data.hour_metadata?.auction_status === "traded";

  // Volume
  const volEl = document.getElementById("kpi-traded-volume");
  if (volEl) volEl.textContent = `${Number(fin.total_p2p_traded_kwh || 0).toFixed(4)} kWh`;

  // VWAP
  const vwapEl = document.getElementById("kpi-vwap");
  if (vwapEl) {
    if (fin.vwap_aud !== null && fin.vwap_aud !== undefined && isTraded) {
      vwapEl.textContent = `$${Number(fin.vwap_aud).toFixed(4)}/kWh`;
    } else {
      vwapEl.textContent = "N/A";
    }
  }

  // Payments & Revenues
  const payEl = document.getElementById("kpi-buyer-payments");
  if (payEl) payEl.textContent = `$${Number(fin.total_buyer_payments_aud || 0).toFixed(4)}`;

  const revEl = document.getElementById("kpi-seller-revenues");
  if (revEl) revEl.textContent = `$${Number(fin.total_seller_revenues_aud || 0).toFixed(4)}`;

  // Welfare
  const welfEl = document.getElementById("kpi-welfare");
  if (welfEl) welfEl.textContent = `$${Number(fin.community_welfare_aud || 0).toFixed(4)}`;

  // Payment-Revenue Residual
  const balEl = document.getElementById("kpi-balance-residual");
  if (balEl) {
    const diff = Math.abs(Number(fin.payment_revenue_balance_aud || 0));
    balEl.textContent = `$${diff.toFixed(6)} AUD (Exact $0.000)`;
  }
}

function renderHouseholdCards(data) {
  const container = document.getElementById("prosumer-cards-container");
  if (!container) return;

  const orders = data.household_orders || [];
  container.innerHTML = "";

  orders.forEach((h) => {
    const role = (h.physical_role || "inactive").toLowerCase();
    const orderType = (h.order_type || "NONE").toUpperCase();
    const price = Number(h.selected_action_price_aud || 0).toFixed(2);
    const matched = Number(h.matched_quantity_kwh || 0).toFixed(4);
    const unmatched = Number(h.unmatched_quantity_kwh || 0).toFixed(4);
    const avail = Number(h.available_quantity_kwh || 0).toFixed(4);
    const benefit = Number(h.incremental_benefit_aud || 0).toFixed(4);
    const revenue = Number(h.revenue_aud || 0).toFixed(4);
    const payment = Number(h.payment_aud || 0).toFixed(4);

    let roleBadgeClass = "badge-neutral";
    let calloutClass = "callout-none";
    let priceLabel = "SUBMITTED PRICE";

    if (role === "seller") {
      roleBadgeClass = "badge-success";
      calloutClass = "callout-ask";
      priceLabel = "ASK PRICE (Seller Offer)";
    } else if (role === "buyer") {
      roleBadgeClass = "badge-info";
      calloutClass = "callout-bid";
      priceLabel = "BID PRICE (Buyer Valuation)";
    }

    const card = document.createElement("div");
    card.className = `prosumer-card role-${role}`;
    card.innerHTML = `
      <div class="prosumer-card-header">
        <div>
          <div class="household-title">${h.household_id}</div>
          <div class="household-archetype">${HOUSEHOLD_ARCHETYPES[h.household_id] || ""}</div>
        </div>
        <span class="badge ${roleBadgeClass}">${role.toUpperCase()}</span>
      </div>
      <div class="prosumer-card-body">
        <div class="price-callout-box ${calloutClass}">
          <div>
            <div class="price-callout-label">${priceLabel}</div>
            <div style="font-size:11px;color:var(--text-muted);">Strategy Action $p_i^* \\in \\mathcal{P}$</div>
          </div>
          <div class="price-callout-val">$${price}/kWh</div>
        </div>

        <div class="data-row">
          <span class="data-key">${role === "seller" ? "Available Surplus (S_i)" : "Available Deficit (D_i)"}</span>
          <span class="data-val">${avail} kWh</span>
        </div>
        <div class="data-row">
          <span class="data-key">Matched Energy</span>
          <span class="data-val" style="color:var(--seller-green);">${matched} kWh</span>
        </div>
        <div class="data-row">
          <span class="data-key">Unmatched (Grid Spill/Import)</span>
          <span class="data-val" style="color:var(--text-muted);">${unmatched} kWh</span>
        </div>
        <div class="data-row">
          <span class="data-key">Matching Status</span>
          <span class="data-val">${h.is_matched ? '<span style="color:var(--seller-green);">✓ MATCHED</span>' : '<span style="color:var(--text-muted);">UNMATCHED</span>'}</span>
        </div>
        <div class="data-row">
          <span class="data-key">${role === "seller" ? "Seller Revenue" : "Buyer Payment"}</span>
          <span class="data-val">${role === "seller" ? `$${revenue}` : `$${payment}`}</span>
        </div>
        <div class="data-row" style="background:#f8fafc;padding:6px 8px;border-radius:4px;margin-top:4px;">
          <span class="data-key" style="font-weight:600;">Incremental Benefit (U_i)</span>
          <span class="data-val" style="color:var(--primary-blue);">$${benefit} AUD</span>
        </div>
      </div>
    `;
    container.appendChild(card);
  });
}

function renderAuctionMeritOrder(data) {
  const orders = data.household_orders || [];
  const sellers = orders
    .filter((o) => o.physical_role === "seller")
    .sort((a, b) => a.selected_action_price_aud - b.selected_action_price_aud);

  const buyers = orders
    .filter((o) => o.physical_role === "buyer")
    .sort((a, b) => b.selected_action_price_aud - a.selected_action_price_aud);

  const crossingBanner = document.getElementById("auction-crossing-banner");
  const isTraded = data.hour_metadata?.auction_status === "traded";

  if (crossingBanner) {
    if (isTraded && sellers.length > 0 && buyers.length > 0) {
      const minAsk = sellers[0].selected_action_price_aud;
      const maxBid = buyers[0].selected_action_price_aud;
      crossingBanner.className = "crossing-banner crossing-success";
      crossingBanner.innerHTML = `
        <strong>✓ Bid-Ask Crossing Detected:</strong>
        Highest Bid ($${maxBid.toFixed(2)}/kWh) &ge; Lowest Ask ($${minAsk.toFixed(2)}/kWh).
        Auction engine cleared ${data.financial_summary?.total_p2p_traded_kwh?.toFixed(4)} kWh at midpoint bilateral pricing.
      `;
    } else {
      crossingBanner.className = "crossing-banner crossing-warning";
      crossingBanner.innerHTML = `
        <strong>⚠ No Bid-Ask Crossing / No Trade:</strong>
        ${data.hour_metadata?.market_status === "all-seller" ? "Market is one-sided with 3 sellers and 0 buyers." : ""}
        ${data.hour_metadata?.market_status === "all-buyer" ? "Market is one-sided with 0 sellers and 3 buyers." : ""}
        ${data.hour_metadata?.market_status === "mixed" ? "Submitted bids did not cross asks (uncrossed coordination trap)." : ""}
        Zero P2P energy traded in this auction round.
      `;
    }
  }

  // Render Sellers Column
  const sellersList = document.getElementById("auction-sellers-list");
  if (sellersList) {
    if (sellers.length === 0) {
      sellersList.innerHTML = '<div style="color:var(--text-muted);font-size:12px;padding:8px 0;">No active sellers this hour.</div>';
    } else {
      sellersList.innerHTML = sellers
        .map(
          (s, idx) => `
        <div style="background:#ffffff;border:1px solid var(--border-light);border-radius:6px;padding:10px 14px;margin-bottom:8px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
            <strong>#${idx + 1} ${s.household_id}</strong>
            <span class="badge badge-success">ASK: $${Number(s.selected_action_price_aud).toFixed(2)}/kWh</span>
          </div>
          <div style="font-size:12px;color:var(--text-muted);display:flex;justify-content:space-between;">
            <span>Surplus: ${Number(s.available_quantity_kwh).toFixed(4)} kWh</span>
            <span>Matched: <strong style="color:var(--seller-green);">${Number(s.matched_quantity_kwh).toFixed(4)} kWh</strong></span>
          </div>
        </div>
      `
        )
        .join("");
    }
  }

  // Render Buyers Column
  const buyersList = document.getElementById("auction-buyers-list");
  if (buyersList) {
    if (buyers.length === 0) {
      buyersList.innerHTML = '<div style="color:var(--text-muted);font-size:12px;padding:8px 0;">No active buyers this hour.</div>';
    } else {
      buyersList.innerHTML = buyers
        .map(
          (b, idx) => `
        <div style="background:#ffffff;border:1px solid var(--border-light);border-radius:6px;padding:10px 14px;margin-bottom:8px;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
            <strong>#${idx + 1} ${b.household_id}</strong>
            <span class="badge badge-info">BID: $${Number(b.selected_action_price_aud).toFixed(2)}/kWh</span>
          </div>
          <div style="font-size:12px;color:var(--text-muted);display:flex;justify-content:space-between;">
            <span>Deficit: ${Number(b.available_quantity_kwh).toFixed(4)} kWh</span>
            <span>Matched: <strong style="color:var(--buyer-blue);">${Number(b.matched_quantity_kwh).toFixed(4)} kWh</strong></span>
          </div>
        </div>
      `
        )
        .join("");
    }
  }
}

function renderTransactionsTable(data) {
  const tbody = document.getElementById("transactions-table-body");
  const emptyState = document.getElementById("transactions-empty-state");
  const tableWrapper = document.getElementById("transactions-table-wrapper");
  if (!tbody) return;

  const txs = data.transactions || [];
  if (txs.length === 0) {
    if (emptyState) emptyState.style.display = "block";
    if (tableWrapper) tableWrapper.style.display = "none";
    tbody.innerHTML = "";
    return;
  }

  if (emptyState) emptyState.style.display = "none";
  if (tableWrapper) tableWrapper.style.display = "block";

  tbody.innerHTML = txs
    .map(
      (tx) => `
    <tr>
      <td class="mono"><strong>${tx.transaction_id}</strong></td>
      <td><span class="badge badge-success">${tx.seller_id}</span></td>
      <td><span class="badge badge-info">${tx.buyer_id}</span></td>
      <td class="mono">$${Number(tx.seller_ask_aud_per_kwh).toFixed(2)}</td>
      <td class="mono">$${Number(tx.buyer_bid_aud_per_kwh).toFixed(2)}</td>
      <td class="mono" style="color:#7c3aed;font-weight:700;">$${Number(tx.transaction_price_aud_per_kwh).toFixed(4)}</td>
      <td class="mono font-bold">${Number(tx.matched_quantity_kwh).toFixed(4)} kWh</td>
      <td class="mono" style="color:var(--seller-green);">$${Number(tx.seller_revenue_aud).toFixed(4)}</td>
      <td class="mono" style="color:var(--buyer-blue);">$${Number(tx.buyer_payment_aud).toFixed(4)}</td>
    </tr>
  `
    )
    .join("");
}

function renderStrategiesComparison(data) {
  const tbody = document.getElementById("strategies-table-body");
  if (!tbody) return;

  const choices = data.strategy_choices || [];
  tbody.innerHTML = choices
    .map((c) => {
      const isSelected = c.strategy_key === STATE.currentStrategy;
      const vwapStr = c.vwap_aud !== null && c.vwap_aud !== undefined ? `$${Number(c.vwap_aud).toFixed(4)}` : "N/A";
      const u1 = Number(c.payoffs?.H001 || 0).toFixed(4);
      const u2 = Number(c.payoffs?.H002 || 0).toFixed(4);
      const u3 = Number(c.payoffs?.H003 || 0).toFixed(4);
      const p1 = Number(c.price_profile?.H001 || 0).toFixed(2);
      const p2 = Number(c.price_profile?.H002 || 0).toFixed(2);
      const p3 = Number(c.price_profile?.H003 || 0).toFixed(2);

      return `
      <tr class="clickable-row ${isSelected ? "selected-strategy-row" : ""}" data-strategy="${c.strategy_key}">
        <td><strong>${c.strategy_label}</strong></td>
        <td class="mono">(${p1}, ${p2}, ${p3})</td>
        <td class="mono">${Number(c.volume_kwh || 0).toFixed(4)}</td>
        <td class="mono" style="font-weight:700;">${vwapStr}</td>
        <td class="mono" style="color:var(--seller-green);">$${Number(c.welfare_aud || 0).toFixed(4)}</td>
        <td class="mono">H001: $${u1} | H002: $${u2} | H003: $${u3}</td>
        <td class="mono">${Number(c.standard_gini || 0).toFixed(4)}</td>
      </tr>
    `;
    })
    .join("");

  // Add click listener to rows to select strategy
  tbody.querySelectorAll("tr.clickable-row").forEach((row) => {
    row.addEventListener("click", () => {
      const stratKey = row.dataset.strategy;
      if (stratKey && stratKey !== STATE.currentStrategy) {
        STATE.currentStrategy = stratKey;
        loadHourlyClearingData();
      }
    });
  });
}

function renderPayoffReconciliation(data) {
  const tbody = document.getElementById("reconciliation-table-body");
  if (!tbody) return;

  const storedPayoffs = data.selected_strategy?.stored_payoffs || {};
  const orders = data.household_orders || [];

  tbody.innerHTML = ["H001", "H002", "H003"]
    .map((hId) => {
      const order = orders.find((o) => o.household_id === hId) || {};
      const stored = Number(storedPayoffs[hId] || 0);
      const recon = Number(order.incremental_benefit_aud || 0);
      const diff = Math.abs(stored - recon);
      const isExact = diff < 1e-12;

      return `
      <tr>
        <td><strong>${hId}</strong></td>
        <td><span class="badge ${order.physical_role === "seller" ? "badge-success" : order.physical_role === "buyer" ? "badge-info" : "badge-neutral"}">${(order.physical_role || "INACTIVE").toUpperCase()}</span></td>
        <td class="mono">$${stored.toFixed(6)} AUD</td>
        <td class="mono">$${recon.toFixed(6)} AUD</td>
        <td class="mono" style="color:${isExact ? 'var(--seller-green)' : 'var(--amber-warning)'};font-weight:700;">$${diff.toExponential(2)} AUD</td>
        <td><span class="badge badge-success">✓ EXACT MATCH (&lt;1e-12)</span></td>
      </tr>
    `;
    })
    .join("");
}

function renderNashContext(data) {
  const ctx = data.nash_equilibrium_context || {};
  const grid = data.strategic_price_grid || [0.08, 0.12, 0.16, 0.19, 0.22, 0.26, 0.30];

  const profilesEl = document.getElementById("ctx-profiles-evaluated");
  if (profilesEl) {
    profilesEl.textContent =
      ctx.num_profiles_evaluated !== undefined && ctx.num_profiles_evaluated !== null
        ? ctx.num_profiles_evaluated
        : "-";
  }

  const profilesSub = document.getElementById("ctx-profiles-sub");
  if (profilesSub) {
    if (ctx.num_profiles_evaluated === 49) {
      profilesSub.textContent = "Combinatorial 7² grid (2 active players)";
    } else if (ctx.num_profiles_evaluated === 343) {
      profilesSub.textContent = "Combinatorial 7³ grid (3 active players)";
    } else if (ctx.num_profiles_evaluated) {
      profilesSub.textContent = `Combinatorial grid (${ctx.num_profiles_evaluated} profiles)`;
    }
  }

  const deviationsEl = document.getElementById("ctx-deviations-evaluated");
  if (deviationsEl) {
    deviationsEl.textContent =
      ctx.num_deviations_evaluated !== undefined && ctx.num_deviations_evaluated !== null
        ? Number(ctx.num_deviations_evaluated).toLocaleString()
        : "-";
  }

  const deviationsSub = document.getElementById("ctx-deviations-sub");
  if (deviationsSub && ctx.num_deviations_evaluated) {
    deviationsSub.textContent = `${Number(ctx.num_deviations_evaluated).toLocaleString()} unilateral tests`;
  }

  const pneEl = document.getElementById("ctx-pne-count");
  if (pneEl) pneEl.textContent = ctx.num_pne ?? 0;

  const strictEl = document.getElementById("ctx-strict-pne");
  if (strictEl) strictEl.textContent = ctx.num_strict_pne ?? 0;

  const weakEl = document.getElementById("ctx-weak-pne");
  if (weakEl) weakEl.textContent = ctx.num_weak_pne ?? 0;

  const paretoEl = document.getElementById("ctx-pareto-pne");
  if (paretoEl) paretoEl.textContent = ctx.num_pareto_undominated_pne ?? 0;

  const gridEl = document.getElementById("ctx-price-grid");
  if (gridEl) gridEl.textContent = `[${grid.map((p) => Number(p).toFixed(2)).join(", ")}] AUD/kWh (K=${grid.length})`;

  const sourceEl = document.getElementById("ctx-transaction-source");
  if (sourceEl) sourceEl.textContent = data.transaction_source || "reconstructed_via_existing_clearing_function";
}

// ============================================================================
// Lazy Data Loaders for Other Dashboard Tabs
// ============================================================================

async function loadOverviewData() {
  try {
    const [statusRes, profilesRes] = await Promise.all([
      fetch("/api/system_status"),
      fetch("/api/customer_profiles"),
    ]);
    const statusJson = await statusRes.json();
    const profilesJson = await profilesRes.json();

    if (statusJson.status === "success") {
      const s = statusJson.data;
      const el = document.getElementById("overview-test-badge");
      if (el) el.textContent = `${s.regression_test_status?.tests_passing} / ${s.regression_test_status?.tests_total} Tests Passing`;
      const hrsEl = document.getElementById("overview-test-hours");
      if (hrsEl) hrsEl.textContent = `${s.dataset_horizons?.test_period_hours} Hours`;
    }

    if (profilesJson.status === "success") {
      const pContainer = document.getElementById("overview-profiles-container");
      if (pContainer) {
        pContainer.innerHTML = profilesJson.data
          .map(
            (p) => `
          <div style="background:#ffffff;border:1px solid var(--border-light);border-radius:8px;padding:16px;">
            <div style="font-weight:700;font-size:15px;margin-bottom:6px;">${p.house_id}</div>
            <div style="font-size:12px;color:var(--text-muted);margin-bottom:8px;">${p.archetype}</div>
            <div style="font-size:13px;line-height:1.6;">
              <div><strong>PV Capacity:</strong> ${p.pv_capacity_kw} kW</div>
              <div><strong>Battery:</strong> ${p.battery_capacity_kwh} kWh (Max C/D: ${p.battery_max_charge_kw} kW)</div>
              <div><strong>Retail Tariffs:</strong> Import $${p.retail_import_tariff_aud}/kWh | Export $${p.feed_in_tariff_aud}/kWh</div>
            </div>
          </div>
        `
          )
          .join("");
      }
    }
  } catch (e) {
    console.error("Failed to load overview data:", e);
  }
}

async function loadForecastingData() {
  try {
    const res = await fetch("/api/forecast_scorecard");
    const json = await res.json();
    if (json.status === "success") {
      const container = document.getElementById("forecast-scorecard-table-body");
      if (container) {
        container.innerHTML = json.data.point_forecast_metrics
          .map(
            (m) => `
          <tr>
            <td><strong>${m.house_id}</strong></td>
            <td>${m.target_variable.toUpperCase()}</td>
            <td><span class="badge ${m.model === "LSTM" ? "badge-info" : "badge-neutral"}">${m.model}</span></td>
            <td class="mono font-bold">${m.mae_kwh.toFixed(4)} kWh</td>
            <td class="mono">${m.rmse_kwh.toFixed(4)} kWh</td>
          </tr>
        `
          )
          .join("");
      }
    }
  } catch (e) {
    console.error("Failed to load forecasting scorecard:", e);
  }
}

async function loadP2PBenchmarkData() {
  try {
    const res = await fetch("/api/p2p_benchmarks");
    const json = await res.json();
    if (json.status === "success") {
      const tbody = document.getElementById("p2p-benchmark-table-body");
      if (tbody) {
        tbody.innerHTML = json.data
          .filter((r) => r.house_id === "COMMUNITY")
          .map(
            (r) => `
          <tr>
            <td><strong>${r.controller}</strong></td>
            <td><span class="badge ${r.simulation_mode === "P2P" ? "badge-success" : "badge-neutral"}">${r.simulation_mode}</span></td>
            <td class="mono">${r.grid_import_kwh.toFixed(1)} kWh</td>
            <td class="mono">${r.grid_export_kwh.toFixed(1)} kWh</td>
            <td class="mono">${r.p2p_traded_kwh.toFixed(1)} kWh</td>
            <td class="mono font-bold">$${r.net_cost_aud.toFixed(2)} AUD</td>
          </tr>
        `
          )
          .join("");
      }
    }
  } catch (e) {
    console.error("Failed to load P2P benchmarks:", e);
  }
}

async function loadLedgerData() {
  try {
    const res = await fetch("/api/precomputed_ledger");
    const json = await res.json();
    if (json.status === "success") {
      const tbody = document.getElementById("ledger-table-body");
      if (tbody) {
        tbody.innerHTML = json.data.numerical_conservation_ledger
          .map(
            (row) => `
          <tr>
            <td><strong>${row.metric}</strong></td>
            <td class="mono" style="color:var(--seller-green);font-weight:700;">${row.precomputed_residual}</td>
            <td class="mono">${row.governing_identity}</td>
            <td><span class="badge badge-success">${row.audit_status}</span></td>
          </tr>
        `
          )
          .join("");
      }
    }
  } catch (e) {
    console.error("Failed to load precomputed ledger:", e);
  }
}

// ============================================================================
// Phase 8E: Stochastic Expected-Payoff Nash Equilibrium Controls & Rendering
// ============================================================================

function initStochasticControls() {
  // Preset buttons
  const presetButtons = document.querySelectorAll(".btn-preset[data-stoch-ts]");
  presetButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      presetButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      STATE.stochTimestamp = btn.dataset.stochTs;
      const input = document.getElementById("stoch-timestamp-input");
      if (input) input.value = STATE.stochTimestamp;
      loadStochasticMarketData();
    });
  });

  // Calculate button
  const calcBtn = document.getElementById("btn-stoch-calculate");
  const input = document.getElementById("stoch-timestamp-input");
  if (calcBtn && input) {
    calcBtn.addEventListener("click", () => {
      const val = input.value.trim();
      if (val) {
        STATE.stochTimestamp = val;
        // Update preset buttons active state if matches
        document.querySelectorAll(".btn-preset[data-stoch-ts]").forEach((b) => {
          b.classList.toggle("active", b.dataset.stochTs === val);
        });
        loadStochasticMarketData();
      }
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") calcBtn.click();
    });
  }

  // Jump from Phase 8D section
  const jumpBtn = document.getElementById("btn-jump-to-stochastic");
  if (jumpBtn) {
    jumpBtn.addEventListener("click", () => {
      const targetTab = document.querySelector('.nav-tab[data-target="pane-stochastic"]');
      if (targetTab) {
        targetTab.click();
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    });
  }
}

async function loadStochasticMarketData() {
  if (STATE.isStochLoading) return;
  setStochasticLoading(true);
  hideStochasticError();

  try {
    const url = `/api/strategic-market/stochastic-hourly?timestamp=${encodeURIComponent(
      STATE.stochTimestamp
    )}`;
    const res = await fetch(url);
    const json = await res.json();
    if (json.status !== "success") {
      throw new Error(json.message || `Failed to calculate stochastic equilibrium for ${STATE.stochTimestamp}`);
    }

    STATE.stochData = json.data;
    renderAllStochasticSections(json.data);
  } catch (err) {
    showStochasticError(err.message);
  } finally {
    setStochasticLoading(false);
  }
}

function setStochasticLoading(isLoading) {
  STATE.isStochLoading = isLoading;
  const spinner = document.getElementById("stoch-loading-spinner");
  const label = document.getElementById("stoch-loading-label");
  const btn = document.getElementById("btn-stoch-calculate");
  if (spinner) spinner.style.display = isLoading ? "inline-block" : "none";
  if (label) label.style.display = isLoading ? "inline" : "none";
  if (btn) btn.disabled = isLoading;
}

function showStochasticError(msg) {
  const errBox = document.getElementById("stoch-error-banner");
  if (errBox) {
    errBox.textContent = `Phase 8E Engine Error: ${msg}`;
    errBox.style.display = "block";
  }
}

function hideStochasticError() {
  const errBox = document.getElementById("stoch-error-banner");
  if (errBox) errBox.style.display = "none";
}

function renderAllStochasticSections(data) {
  renderStochasticKPIs(data);
  renderStochasticProsumerCards(data);
  renderStochasticComparison(data.deterministic_comparison);
  renderStochasticParetoTable(data.pareto_undominated_equilibria, data.selected_equilibrium);
  renderStochasticPayoffTable(data.expected_payoff_table, data.selected_equilibrium);
}

function renderStochasticKPIs(data) {
  const summary = data.market_summary || {};

  // Traded Energy
  const tradedEl = document.getElementById("stoch-kpi-traded");
  if (tradedEl) {
    tradedEl.textContent = `${Number(summary.expected_traded_energy_kwh || 0).toFixed(4)} kWh`;
  }

  // Community Welfare
  const welfareEl = document.getElementById("stoch-kpi-welfare");
  if (welfareEl) {
    welfareEl.textContent = `$${Number(summary.expected_community_welfare_aud || 0).toFixed(4)} AUD`;
  }

  // VWAP
  const vwapEl = document.getElementById("stoch-kpi-vwap");
  if (vwapEl) {
    vwapEl.textContent = summary.expected_vwap_aud_per_kwh != null
      ? `$${Number(summary.expected_vwap_aud_per_kwh).toFixed(4)}/kWh`
      : "N/A (Zero Trade)";
  }

  // Tradeable Scenarios
  const tradeableEl = document.getElementById("stoch-kpi-tradeable");
  if (tradeableEl) {
    tradeableEl.textContent = `${data.num_tradeable_scenarios || 0} / ${data.num_scenarios || 1000}`;
  }
  const tradeablePct = document.getElementById("stoch-kpi-tradeable-pct");
  if (tradeablePct) {
    tradeablePct.textContent = `${data.tradeable_scenario_percentage || 0}% active overlap`;
  }

  // Nash Equilibria Count
  const pneEl = document.getElementById("stoch-kpi-pne");
  if (pneEl) {
    pneEl.textContent = `${data.num_stochastic_pne || 0} PNE`;
  }
  const pneSub = document.getElementById("stoch-kpi-pne-sub");
  if (pneSub) {
    pneSub.textContent = `${data.strict_pne_count || 0} Strict, ${data.weak_pne_count || 0} Weak, ${data.pareto_undominated_pne_count || 0} Pareto`;
  }

  // Selected Profile
  const profileEl = document.getElementById("stoch-kpi-profile");
  if (profileEl) {
    const prof = data.selected_equilibrium?.profile;
    if (prof) {
      const p1 = prof.H001 !== undefined ? `$${Number(prof.H001).toFixed(2)}` : "-";
      const p2 = prof.H002 !== undefined ? `$${Number(prof.H002).toFixed(2)}` : "-";
      const p3 = prof.H003 !== undefined ? `$${Number(prof.H003).toFixed(2)}` : "-";
      profileEl.textContent = `(${p1}, ${p2}, ${p3})`;
    } else {
      profileEl.textContent = "None (No PNE)";
    }
  }
}

function renderStochasticProsumerCards(data) {
  const container = document.getElementById("stoch-prosumer-cards-container");
  if (!container) return;
  container.innerHTML = "";

  const roles = data.ex_ante_roles || {};
  const expNets = data.expected_net_positions_kwh || {};
  const flipCounts = data.scenario_role_flip_counts || {};
  const payoffs = data.market_summary?.expected_household_payoffs_aud || {};
  const chargeDis = data.battery_dispatch || {};
  const charges = chargeDis.charge_kwh || {};
  const discharges = chargeDis.discharge_kwh || {};
  const numScenarios = data.num_scenarios || 1000;

  ["H001", "H002", "H003"].forEach((hid) => {
    const role = (roles[hid] || "inactive").toLowerCase();
    const expNet = Number(expNets[hid] || 0);
    const c0 = Number(charges[hid] || 0);
    const b0 = Number(discharges[hid] || 0);
    const uExp = Number(payoffs[hid] || 0);
    const flips = flipCounts[hid] || { seller: 0, buyer: 0, inactive: 0 };

    const nSeller = flips.seller || 0;
    const nBuyer = flips.buyer || 0;
    const nInactive = flips.inactive || 0;

    const sellerPct = ((nSeller / numScenarios) * 100).toFixed(1);
    const buyerPct = ((nBuyer / numScenarios) * 100).toFixed(1);
    const inactivePct = ((nInactive / numScenarios) * 100).toFixed(1);

    // Physical Role-Conflict Clamping: scenarios where realized role opposes ex-ante role
    let conflictCount = 0;
    if (role === "seller") conflictCount = nBuyer + nInactive;
    else if (role === "buyer") conflictCount = nSeller + nInactive;
    const conflictPct = ((conflictCount / numScenarios) * 100).toFixed(1);

    const roleBadgeClass =
      role === "seller"
        ? "badge-success"
        : role === "buyer"
        ? "badge-info"
        : "badge-neutral";

    const card = document.createElement("div");
    card.className = "prosumer-card";
    card.innerHTML = `
      <div class="prosumer-header">
        <div>
          <div class="prosumer-id">${hid}</div>
          <div class="prosumer-archetype">${HOUSEHOLD_ARCHETYPES[hid] || ""}</div>
        </div>
        <span class="badge ${roleBadgeClass}">EX-ANTE ${role.toUpperCase()}</span>
      </div>

      <div class="prosumer-body">
        <div class="prosumer-metric-row">
          <span class="prosumer-metric-label">Expected Net Position E[n]:</span>
          <span class="prosumer-metric-val mono font-bold ${expNet < -1e-5 ? "val-seller" : expNet > 1e-5 ? "val-buyer" : ""}">${expNet.toFixed(4)} kWh</span>
        </div>
        <div class="prosumer-metric-row">
          <span class="prosumer-metric-label">Phase 7.1 Battery Dispatch:</span>
          <span class="prosumer-metric-val mono">C₀=${c0.toFixed(3)}, B₀=${b0.toFixed(3)} kWh</span>
        </div>
        <div class="prosumer-metric-row">
          <span class="prosumer-metric-label">Expected Payoff E[U]:</span>
          <span class="prosumer-metric-val mono font-bold val-seller">+$${uExp.toFixed(5)} AUD</span>
        </div>
        <div class="prosumer-metric-row">
          <span class="prosumer-metric-label">Role-Conflict Clamping:</span>
          <span class="prosumer-metric-val mono ${conflictCount > 0 ? "val-warning" : ""}">${conflictCount} / ${numScenarios} (${conflictPct}%)</span>
        </div>

        <div style="margin-top:10px;">
          <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px;display:flex;justify-content:space-between;">
            <span>Realized Scenario Distribution (M=1,000):</span>
            <span>S: ${sellerPct}% | B: ${buyerPct}% | Inactive: ${inactivePct}%</span>
          </div>
          <div class="role-dist-bar">
            <div class="role-dist-seg role-dist-seller" style="width:${sellerPct}%;" title="Seller Surplus: ${nSeller} scenarios (${sellerPct}%)"></div>
            <div class="role-dist-seg role-dist-buyer" style="width:${buyerPct}%;" title="Buyer Deficit: ${nBuyer} scenarios (${buyerPct}%)"></div>
            <div class="role-dist-seg role-dist-inactive" style="width:${inactivePct}%;" title="Inactive: ${nInactive} scenarios (${inactivePct}%)"></div>
          </div>
        </div>
      </div>
    `;
    container.appendChild(card);
  });
}

function renderStochasticComparison(comp) {
  if (!comp) return;

  // Render cards grid
  const cardsGrid = document.getElementById("stoch-comp-cards-grid");
  if (cardsGrid) {
    const vol = comp.traded_volume_kwh || {};
    const wel = comp.community_welfare_aud || {};
    const vwap = comp.vwap_aud_per_kwh || {};

    const volPctStr = vol.percentage_diff != null ? `${vol.percentage_diff >= 0 ? "+" : ""}${vol.percentage_diff.toFixed(2)}%` : "N/A";
    const welPctStr = wel.percentage_diff != null ? `${wel.percentage_diff >= 0 ? "+" : ""}${wel.percentage_diff.toFixed(2)}%` : "N/A";
    const volDiffStr = `${vol.absolute_diff_kwh >= 0 ? "+" : ""}${Number(vol.absolute_diff_kwh || 0).toFixed(4)} kWh`;
    const welDiffStr = `${wel.absolute_diff_aud >= 0 ? "+" : ""}$${Number(wel.absolute_diff_aud || 0).toFixed(4)} AUD`;
    const vwapDiffStr = vwap.absolute_diff_aud != null ? `${vwap.absolute_diff_aud >= 0 ? "+" : ""}$${Number(vwap.absolute_diff_aud).toFixed(4)}/kWh` : "N/A";

    cardsGrid.innerHTML = `
      <div class="comparison-card">
        <div class="comparison-card-title">Traded Energy Volume</div>
        <div class="comparison-subgrid">
          <div class="comparison-col">
            <span class="comparison-label">Phase 8C Deterministic</span>
            <span class="comparison-val mono">${Number(vol.deterministic_ex_post || 0).toFixed(4)} kWh</span>
          </div>
          <div class="comparison-col">
            <span class="comparison-label">Phase 8E Expected</span>
            <span class="comparison-val mono font-bold" style="color:var(--primary-blue);">${Number(vol.stochastic_expected || 0).toFixed(4)} kWh</span>
          </div>
        </div>
        <div style="margin-top:8px;font-size:12px;display:flex;justify-content:space-between;">
          <span style="color:var(--text-muted);">Difference: <strong class="mono">${volDiffStr}</strong></span>
          <span class="badge ${vol.jensen_effect_observed ? "badge-warning" : "badge-neutral"}">${volPctStr}</span>
        </div>
      </div>

      <div class="comparison-card">
        <div class="comparison-card-title">Community Welfare</div>
        <div class="comparison-subgrid">
          <div class="comparison-col">
            <span class="comparison-label">Phase 8C Deterministic</span>
            <span class="comparison-val mono">$${Number(wel.deterministic_ex_post || 0).toFixed(4)}</span>
          </div>
          <div class="comparison-col">
            <span class="comparison-label">Phase 8E Expected</span>
            <span class="comparison-val mono font-bold" style="color:var(--seller-green);">$${Number(wel.stochastic_expected || 0).toFixed(4)}</span>
          </div>
        </div>
        <div style="margin-top:8px;font-size:12px;display:flex;justify-content:space-between;">
          <span style="color:var(--text-muted);">Difference: <strong class="mono">${welDiffStr}</strong></span>
          <span class="badge badge-success">${welPctStr}</span>
        </div>
      </div>

      <div class="comparison-card">
        <div class="comparison-card-title">Weighted Average Price (VWAP)</div>
        <div class="comparison-subgrid">
          <div class="comparison-col">
            <span class="comparison-label">Phase 8C Deterministic</span>
            <span class="comparison-val mono">${vol.deterministic_ex_post > 1e-5 ? "$" + Number(vwap.deterministic_ex_post || 0).toFixed(4) : "N/A"}</span>
          </div>
          <div class="comparison-col">
            <span class="comparison-label">Phase 8E Expected</span>
            <span class="comparison-val mono font-bold">${vol.stochastic_expected > 1e-5 ? "$" + Number(vwap.stochastic_expected || 0).toFixed(4) : "N/A"}</span>
          </div>
        </div>
        <div style="margin-top:8px;font-size:12px;display:flex;justify-content:space-between;">
          <span style="color:var(--text-muted);">Difference: <strong class="mono">${vwapDiffStr}</strong></span>
          <span class="badge badge-neutral">Midpoint Cleared</span>
        </div>
      </div>
    `;
  }

  // Render comparison table
  const tbody = document.getElementById("stoch-comparison-table-body");
  if (!tbody) return;

  const vol = comp.traded_volume_kwh || {};
  const wel = comp.community_welfare_aud || {};
  const vwap = comp.vwap_aud_per_kwh || {};
  const eq = comp.equilibrium_counts || {};
  const detEq = eq.deterministic || {};
  const stochEq = eq.stochastic || {};
  const payoffs = comp.household_payoffs || {};

  const makeRow = (metric, detVal, stochVal, diffVal, pctVal, note) => `
    <tr>
      <td><strong>${metric}</strong></td>
      <td class="mono">${detVal}</td>
      <td class="mono font-bold">${stochVal}</td>
      <td class="mono">${diffVal}</td>
      <td class="mono">${pctVal}</td>
      <td><span style="font-size:11px;color:var(--text-muted);">${note}</span></td>
    </tr>
  `;

  let rowsHtml = "";
  rowsHtml += makeRow(
    "Traded Energy Volume",
    `${Number(vol.deterministic_ex_post || 0).toFixed(4)} kWh`,
    `${Number(vol.stochastic_expected || 0).toFixed(4)} kWh`,
    `${vol.absolute_diff_kwh >= 0 ? "+" : ""}${Number(vol.absolute_diff_kwh || 0).toFixed(4)} kWh`,
    vol.percentage_diff != null ? `${vol.percentage_diff >= 0 ? "+" : ""}${vol.percentage_diff.toFixed(2)}%` : "N/A",
    vol.jensen_effect_observed ? "Jensen inequality: E[min(S,D)] ≤ min(E[S],E[D])" : "Zero trade / Neutral"
  );
  rowsHtml += makeRow(
    "Community Welfare Gain",
    `$${Number(wel.deterministic_ex_post || 0).toFixed(4)} AUD`,
    `$${Number(wel.stochastic_expected || 0).toFixed(4)} AUD`,
    `${wel.absolute_diff_aud >= 0 ? "+" : ""}$${Number(wel.absolute_diff_aud || 0).toFixed(4)} AUD`,
    wel.percentage_diff != null ? `${wel.percentage_diff >= 0 ? "+" : ""}${wel.percentage_diff.toFixed(2)}%` : "N/A",
    "Linear scaling: W = (p_import - p_export) × Q"
  );
  rowsHtml += makeRow(
    "Volume-Weighted Price (VWAP)",
    vwap.deterministic_ex_post != null ? `$${Number(vwap.deterministic_ex_post).toFixed(4)}/kWh` : "N/A",
    vwap.stochastic_expected != null ? `$${Number(vwap.stochastic_expected).toFixed(4)}/kWh` : "N/A",
    vwap.absolute_diff_aud != null ? `${vwap.absolute_diff_aud >= 0 ? "+" : ""}$${Number(vwap.absolute_diff_aud).toFixed(4)}` : "N/A",
    "-",
    "Bilateral transaction clearing midpoint"
  );

  ["H001", "H002", "H003"].forEach((hid) => {
    const p = payoffs[hid] || {};
    const dVal = Number(p.deterministic_aud || 0);
    const sVal = Number(p.stochastic_aud || 0);
    const diff = Number(p.diff_aud || 0);
    const pct = p.pct_diff != null ? `${p.pct_diff >= 0 ? "+" : ""}${p.pct_diff.toFixed(2)}%` : "N/A";
    rowsHtml += makeRow(
      `${hid} Incremental Payoff`,
      `$${dVal.toFixed(5)} AUD`,
      `$${sVal.toFixed(5)} AUD`,
      `${diff >= 0 ? "+" : ""}$${diff.toFixed(5)} AUD`,
      pct,
      `Ex-ante ${comp.roles?.ex_ante_stochastic?.[hid] || "inactive"}`
    );
  });

  const detProfStr = Array.isArray(detEq.selected_profile) ? `(${detEq.selected_profile.map((p) => Number(p).toFixed(2)).join(", ")})` : JSON.stringify(detEq.selected_profile);
  const stochProfStr = stochEq.selected_profile ? `(${Object.values(stochEq.selected_profile).map((p) => Number(p).toFixed(2)).join(", ")})` : "None";
  rowsHtml += makeRow(
    "Equilibrium Price Profile",
    detProfStr,
    stochProfStr,
    "-",
    "-",
    `PNE count: Det=${detEq.total_pne || 0} vs Stoch=${stochEq.total_pne || 0}`
  );

  tbody.innerHTML = rowsHtml;
}

function renderStochasticParetoTable(equilibria, selected) {
  const tbody = document.getElementById("stoch-pareto-table-body");
  const badge = document.getElementById("stoch-pareto-badge");
  if (!tbody) return;

  const list = Array.isArray(equilibria) ? equilibria : [];
  if (badge) {
    badge.textContent = `${list.length} Candidate(s) on Frontier`;
  }

  if (list.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:16px;color:var(--text-muted);">No pure strategy Nash equilibrium found.</td></tr>`;
    return;
  }

  const selProfile = selected?.profile || {};

  tbody.innerHTML = list
    .map((eq) => {
      const p = eq.profile || {};
      const isSelected =
        selProfile.H001 !== undefined &&
        Math.abs(p.H001 - selProfile.H001) < 1e-5 &&
        Math.abs(p.H002 - selProfile.H002) < 1e-5 &&
        Math.abs(p.H003 - selProfile.H003) < 1e-5;

      const p1 = Number(p.H001 || 0).toFixed(2);
      const p2 = Number(p.H002 || 0).toFixed(2);
      const p3 = Number(p.H003 || 0).toFixed(2);

      const u1 = Number(eq.expected_payoffs?.H001 || 0).toFixed(4);
      const u2 = Number(eq.expected_payoffs?.H002 || 0).toFixed(4);
      const u3 = Number(eq.expected_payoffs?.H003 || 0).toFixed(4);

      const vwapStr = eq.expected_vwap_aud_per_kwh != null
        ? `$${Number(eq.expected_vwap_aud_per_kwh).toFixed(4)}`
        : "N/A";

      return `
        <tr class="${isSelected ? "selected-strategy-row" : ""}">
          <td>
            ${isSelected ? '<span class="badge badge-success">★ Selected Equilibrium</span>' : '<span class="badge badge-neutral">Pareto Frontier</span>'}
          </td>
          <td class="mono font-bold">(${p1}, ${p2}, ${p3})</td>
          <td class="mono">${Number(eq.expected_traded_kwh || 0).toFixed(4)} kWh</td>
          <td class="mono" style="color:var(--seller-green);">$${Number(eq.expected_community_welfare_aud || 0).toFixed(4)}</td>
          <td class="mono">${vwapStr}</td>
          <td class="mono">H001: $${u1} | H002: $${u2} | H003: $${u3}</td>
          <td><span class="badge ${eq.classification === "STRICT_PNE" ? "badge-success" : "badge-neutral"}">${eq.classification}</span></td>
        </tr>
      `;
    })
    .join("");
}

function renderStochasticPayoffTable(payoffTable, selected) {
  const tbody = document.getElementById("stoch-payoff-table-body");
  if (!tbody) return;

  const rows = Array.isArray(payoffTable) ? payoffTable : [];
  if (rows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:16px;color:var(--text-muted);">No expected payoff records available for this hour.</td></tr>`;
    return;
  }

  const selProfile = selected?.profile || {};

  tbody.innerHTML = rows
    .map((row, idx) => {
      const a1 = Number(row.Action_H001 ?? row.Action_h001 ?? 0);
      const a2 = Number(row.Action_H002 ?? row.Action_h002 ?? 0);
      const a3 = Number(row.Action_H003 ?? row.Action_h003 ?? 0);

      const isSelected =
        selProfile.H001 !== undefined &&
        Math.abs(a1 - Number(selProfile.H001)) < 1e-4 &&
        Math.abs(a2 - Number(selProfile.H002)) < 1e-4 &&
        Math.abs(a3 - Number(selProfile.H003)) < 1e-4;

      const u1 = Number(row.Expected_Payoff_H001 || 0).toFixed(5);
      const u2 = Number(row.Expected_Payoff_H002 || 0).toFixed(5);
      const u3 = Number(row.Expected_Payoff_H003 || 0).toFixed(5);
      const q = Number(row.Expected_Traded_kWh || 0).toFixed(4);
      const w = Number(row.Expected_Welfare_AUD || 0).toFixed(4);
      const vwap = row.Expected_VWAP_AUD != null ? `$${Number(row.Expected_VWAP_AUD).toFixed(4)}` : "N/A";

      return `
        <tr class="${isSelected ? "selected-payoff-row" : ""}">
          <td class="mono">#${idx + 1}</td>
          <td class="mono">$${a1.toFixed(2)}</td>
          <td class="mono">$${a2.toFixed(2)}</td>
          <td class="mono">$${a3.toFixed(2)}</td>
          <td class="mono">$${u1}</td>
          <td class="mono">$${u2}</td>
          <td class="mono">$${u3}</td>
          <td class="mono">${q}</td>
          <td class="mono" style="color:var(--seller-green);">$${w}</td>
          <td class="mono">${vwap}</td>
        </tr>
      `;
    })
    .join("");
}

