function openTab(tabId) {
    document.querySelectorAll(".tab").forEach(tab => tab.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(content => content.classList.remove("active"));

    const tab = document.querySelector(`.tab[onclick="openTab('${tabId}')"]`);
    const content = document.getElementById(tabId);

    if (tab && content) {
        tab.classList.add("active");
        content.classList.add("active");
        // Ensure Chart.js recalculates sizes when a hidden tab becomes visible
        setTimeout(() => { window.dispatchEvent(new Event('resize')); }, 50);
        // Initialize budget charts when budget tab is activated
        if (tabId === 'budget' && typeof initBudgetCharts === 'function') {
            setTimeout(() => initBudgetCharts(), 60);
        }
    }
}

// Initialize budget charts lazily. Expects window._budget_payload to be set by template.
function initBudgetCharts(){
    try {
        if (!window._budget_payload) return;
        if (window._budget_charts_initialized) return;
        const payload = window._budget_payload;

        // Pie chart
        const pieEl = document.getElementById('budgetPieChart');
        if (pieEl && payload.labels && payload.values){
            window._budget_pie = new Chart(pieEl, {
                type: 'pie',
                data: {
                    labels: payload.labels,
                    datasets: [{ data: payload.values, backgroundColor: payload.colors || ["#00bfa6","#36a2eb","#ffce56","#9966ff","#ff9f40"] }]
                },
                options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
            });
        }

        // Semicircle gauge
        const gaugeEl = document.getElementById('budgetGaugeChart');
        if (gaugeEl){
            const totalSpent = Number(payload.total_spent || 0);
            const totalBudget = Number(payload.total_budget || 0);
            const remaining = Math.max(0, totalBudget - totalSpent);
            const over = Math.max(0, totalSpent - totalBudget);
            const shownSpent = Math.min(totalSpent, totalBudget);

            window._budget_gauge = new Chart(gaugeEl, {
                type: 'doughnut',
                data: {
                    datasets: [{
                        data: [shownSpent, remaining, over],
                        backgroundColor: [ totalSpent > totalBudget ? '#e74c3c' : '#00bfa6', '#e5e7eb', '#e74c3c' ],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    rotation: -90,
                    circumference: 180,
                    cutout: '70%',
                    plugins: { legend: { display: false }, tooltip: { enabled: true } }
                }
            });
            // Populate center text: percentage and dollar amount (remaining or over)
            try {
                const pctEl = document.getElementById('gaugePercent');
                const dollarEl = document.getElementById('gaugeDollar');
                const labelEl = document.getElementById('gaugeLabel');
                let percent = 0;
                let dollarText = '$0.00';
                let label = 'Remaining';
                if (totalBudget > 0) {
                    if (totalSpent > totalBudget) {
                        const overAmt = totalSpent - totalBudget;
                        percent = (overAmt / totalBudget) * 100;
                        dollarText = '$' + overAmt.toFixed(2) + ' over';
                        label = 'Over';
                    } else {
                        const remainAmt = totalBudget - totalSpent;
                        percent = (remainAmt / totalBudget) * 100;
                        dollarText = '$' + remainAmt.toFixed(2) + ' left';
                        label = 'Remaining';
                    }
                }
                if (pctEl) pctEl.textContent = percent.toFixed(1) + '%';
                if (dollarEl) dollarEl.textContent = dollarText;
                if (labelEl) labelEl.textContent = label;
            } catch (err) { console.error('gauge center update failed', err); }
        }

        window._budget_charts_initialized = true;
    } catch (err){ console.error('initBudgetCharts error', err); }
}

// If page loads with budget payload and budget tab active, initialize after DOM ready
document.addEventListener('DOMContentLoaded', function(){
    const budgetTab = document.querySelector('.tab[onclick*="budget"]');
    const content = document.getElementById('budget');
    if (content && content.classList.contains('active') && window._budget_payload){
        setTimeout(initBudgetCharts, 80);
    }
});

// AI: call server to run housing+budget recommendations
async function runAiAnalysis(){
    const btn = document.getElementById('aiAnalyzeBtn');
    const resultsEl = document.getElementById('aiResults');
    const actionsEl = document.getElementById('aiActions');
    if (btn) { btn.disabled = true; btn.textContent = 'Analyzing...'; }
    resultsEl.textContent = '';
    actionsEl.innerHTML = '';
    try {
        const resp = await fetch('/api/ai-recommend', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
        const data = await resp.json();
        if (data.error){ resultsEl.textContent = 'Error: ' + data.error; }
        else {
            // Pretty-print results
            resultsEl.textContent = JSON.stringify(data, null, 2);

            // If there are suggested budgets, offer an apply button
            if (data.suggested_budgets && Object.keys(data.suggested_budgets).length > 0){
                const applyBtn = document.createElement('button');
                applyBtn.textContent = 'Apply suggested budget updates';
                applyBtn.onclick = async () => {
                    applyBtn.disabled = true; applyBtn.textContent = 'Applying...';
                    const body = { updates: data.suggested_budgets };
                    const r = await fetch('/api/apply-budget-updates', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
                    const j = await r.json();
                    if (j.success){ applyBtn.textContent = 'Applied'; applyBtn.disabled = true; }
                    else { applyBtn.textContent = 'Failed'; applyBtn.disabled = false; }
                };
                actionsEl.appendChild(applyBtn);
            }
        }
    } catch (err){ resultsEl.textContent = 'Request failed: ' + err; }
    if (btn) { btn.disabled = false; btn.textContent = 'Analyze housing & budgets'; }
}

document.addEventListener('DOMContentLoaded', function(){
    const aiBtn = document.getElementById('aiAnalyzeBtn');
    if (aiBtn) aiBtn.addEventListener('click', runAiAnalysis);
});

// Dashboard pie (ONLY if variables exist)
if (typeof chartLabels !== "undefined" && typeof chartValues !== "undefined") {
    new Chart(document.getElementById("pieChart"), {
        type: "pie",
        data: {
            labels: chartLabels,
            datasets: [{
                data: chartValues,
                backgroundColor: [
                    "#ff6384",
                    "#36a2eb",
                    "#ffce56",
                    "#4bc0c0",
                    "#9966ff"
                ]
            }]
        },
        options: {
            plugins: { legend: { position: "bottom" } }
        }
    });
}
