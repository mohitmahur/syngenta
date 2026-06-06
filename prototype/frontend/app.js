/* ══════════════════════════════════════════════════════
   KrishiConnect AI — Frontend Application
   ══════════════════════════════════════════════════════ */

const API =
    window.location.hostname === 'localhost'
        ? 'http://127.0.0.1:8000'
        : 'https://syngenta-a6jk.onrender.com';

// ─── Tab Navigation ───
document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById('panel-' + tab.dataset.tab).classList.add('active');
    });
});

// ─── Helpers ───
function $(id) { return document.getElementById(id); }
function fmt(n) { return n >= 1000 ? (n / 1000).toFixed(1) + 'K' : n; }
function pct(n) { return (n * 100).toFixed(1) + '%'; }

function metricCard(label, value, detail, color = 'green') {
    return `<div class="metric-card"><div class="metric-label">${label}</div><div class="metric-value ${color}">${value}</div><div class="metric-detail">${detail}</div></div>`;
}

function barChart(items, maxVal, colorCycle) {
    const colors = colorCycle || ['green', 'blue', 'amber', 'purple', 'teal', 'red'];
    return '<div class="bar-chart">' + items.map((item, i) => {
        const w = Math.max(5, (item.value / maxVal) * 100);
        const c = colors[i % colors.length];
        return `<div class="bar-row"><div class="bar-label">${item.label}</div><div class="bar-track"><div class="bar-fill ${c}" style="width:${w}%">${item.display || item.value}</div></div></div>`;
    }).join('') + '</div>';
}

function kvList(items) {
    return '<div class="kv-list">' + items.map(i => `<div class="kv-item"><span class="kv-key">${i.k}</span><span class="kv-value">${i.v}</span></div>`).join('') + '</div>';
}

async function api(path) {
    const r = await fetch(API + path);
    if (!r.ok) throw new Error(r.statusText);
    return r.json();
}

// ─── Boot ───
async function boot() {
    try {
        const data = await api('/api/data/overview');
        $('status-dot').classList.add('online');
        $('status-text').innerHTML = `<span class="blinking-dot" id="status-dot" style="background-color: var(--toxic-green)"></span>SYS.BOOT COMPLETE // ${data.growers} GROWERS LOADED`;
        renderDashboard(data);
        populateFilters(data);
    } catch (e) {
        $('status-text').textContent = 'Connection failed';
        console.error(e);
    }
}

function renderDashboard(d) {
    $('overview-metrics').innerHTML =
        metricCard('Growers', fmt(d.growers), '6 languages, 10 states', 'green') +
        metricCard('Retailers', fmt(d.retailers), 'Across all territories', 'blue') +
        metricCard('POS Txns', fmt(d.pos_transactions), 'Rabi 2025-26 season', 'amber') +
        metricCard('WhatsApp Msgs', fmt(d.whatsapp_messages), 'Campaign messages sent', 'purple') +
        metricCard('Inventory Records', fmt(d.inventory_records), 'Weekly SKU snapshots', 'teal') +
        metricCard('Field Visits', fmt(d.visit_logs), 'Rep visit logs', 'blue');

    // Crop distribution — we load segments summary
    api('/api/segments/summary').then(s => {
        const crops = Object.entries(s.by_crop).sort((a, b) => b[1] - a[1]);
        const maxC = crops[0][1];
        $('crop-distribution').innerHTML = barChart(crops.map(([k, v]) => ({ label: k, value: v, display: v })), maxC);

        const ch = Object.entries(s.by_channel).sort((a, b) => b[1] - a[1]);
        const maxCh = ch[0][1];
        $('channel-distribution').innerHTML = barChart(ch.map(([k, v]) => ({ label: k, value: v, display: v })), maxCh, ['green', 'blue', 'purple']);

        $('segment-summary-metrics').innerHTML =
            metricCard('Total Segments', s.total_segments, 'Unique micro-segments', 'green') +
            metricCard('Total Growers', fmt(s.total_growers), 'Across all segments', 'blue');
    });

    // State distribution
    const states = d.states || [];
    if (states.length) {
        api('/api/segments/summary').then(s => {
            $('state-distribution').innerHTML = '<div class="bar-chart">' + states.map(st =>
                `<div class="bar-row"><div class="bar-label">${st}</div><div class="bar-track"><div class="bar-fill teal" style="width:${Math.random() * 60 + 20}%"></div></div></div>`
            ).join('') + '</div>';
        });
    }
}

function populateFilters(d) {
    const cropSel = $('seg-filter-crop');
    d.crops.forEach(c => { if (c && c !== 'unknown') cropSel.innerHTML += `<option value="${c}">${c}</option>`; });
    const stateSel = $('seg-filter-state');
    d.states.forEach(s => { stateSel.innerHTML += `<option value="${s}">${s}</option>`; });
}

// ─── Segments ───
$('seg-load-btn').addEventListener('click', async () => {
    const crop = $('seg-filter-crop').value;
    const state = $('seg-filter-state').value;
    let url = '/api/segments/list?limit=100';
    if (crop) url += '&crop=' + crop;
    if (state) url += '&state=' + state;

    try {
        const data = await api(url);
        const tbody = $('segments-tbody');
        tbody.innerHTML = data.segments.map(s => `<tr>
            <td style="color:var(--text-primary);font-weight:600;font-size:11px">${s.segment_id.substring(0, 30)}…</td>
            <td><span class="tag tag-green">${s.crop}</span></td>
            <td><span class="tag tag-blue">${s.stage}</span></td>
            <td>${s.state}</td>
            <td><span class="tag tag-purple">${s.language}</span></td>
            <td><span class="tag ${s.device_type === 'smartphone' ? 'tag-green' : 'tag-amber'}">${s.device_type}</span></td>
            <td style="color:var(--text-primary);font-weight:700">${s.grower_count}</td>
            <td>${s.avg_farm_size} ac</td>
            <td style="font-size:11px">${s.threat || '—'}</td>
            <td style="font-size:11px">${(s.recommended_products || []).join(', ')}</td>
        </tr>`).join('');
    } catch (e) { console.error(e); }
});

// ─── Grower Lookup ───
$('grower-load-btn').addEventListener('click', async () => {
    const gid = $('grower-id-input').value.trim();
    if (!gid) return;
    try {
        const ctx = await api(`/api/grower/${gid}`);
        $('grower-profile-area').style.display = 'grid';

        $('grower-info').innerHTML = kvList([
            { k: 'ID', v: ctx.grower_id }, { k: 'State', v: ctx.state }, { k: 'District', v: ctx.district },
            { k: 'Tehsil', v: ctx.tehsil }, { k: 'Language', v: `<span class="tag tag-purple">${ctx.language}</span>` },
            { k: 'Device', v: `<span class="tag ${ctx.device_type === 'smartphone' ? 'tag-green' : 'tag-amber'}">${ctx.device_type}</span>` },
            { k: 'Age', v: ctx.age }, { k: 'Gender', v: ctx.gender }, { k: 'Farm Size', v: ctx.farm_size_acres + ' acres' },
        ]);

        $('grower-context').innerHTML = kvList([
            { k: 'Crop', v: `<span class="tag tag-green">${ctx.crop}</span>` },
            { k: 'Current Stage', v: `<span class="tag tag-blue">${ctx.current_stage}</span>` },
            { k: 'Active Threat', v: `<span class="tag tag-red">${ctx.threat || 'None'}</span>` },
            { k: 'Recommended Channel', v: `<span class="tag tag-green">${ctx.recommended_channel}</span>` },
            { k: 'Product Scanned', v: ctx.product_scanned ? '✅ Yes' : '❌ No' },
            { k: 'Offline Campaign', v: ctx.offline_attended ? '✅ Attended' : '❌ Not attended' },
        ]);

        $('grower-products').innerHTML = '<div class="kv-list">' + (ctx.recommended_products || []).map(p =>
            `<div class="kv-item"><span class="kv-key">${p.product}</span><span class="kv-value">${p.in_stock ? '<span class="tag tag-green">In Stock (' + p.local_stock + ')</span>' : '<span class="tag tag-red">Out of Stock</span>'}</span></div>`
        ).join('') + '</div>';

        const wa = ctx.whatsapp_history || {};
        $('grower-engagement').innerHTML = kvList([
            { k: 'Messages Sent', v: wa.total_messages || 0 }, { k: 'Delivered', v: wa.delivered || 0 },
            { k: 'Opened', v: wa.opened || 0 }, { k: 'Clicked', v: wa.clicked || 0 },
        ]);
    } catch (e) { $('grower-profile-area').style.display = 'none'; console.error(e); }
});

// ─── Content Generation ───
$('content-generate-btn').addEventListener('click', async () => {
    const gid = $('content-grower-input').value.trim();
    const fmt_type = $('content-format').value;
    if (!gid) return;
    $('content-result-card').style.display = 'block';
    $('content-meta').innerHTML = '<div class="loading-spinner">Generating content…</div>';
    $('content-outputs').innerHTML = '';

    try {
        const result = await api(`/api/generate/${gid}?format=${fmt_type}`);
        $('content-meta').innerHTML = `<div class="content-meta-grid">
            <div class="content-meta-item"><span class="label">Grower</span><span class="value">${result.grower_id}</span></div>
            <div class="content-meta-item"><span class="label">Language</span><span class="value">${result.language}</span></div>
            <div class="content-meta-item"><span class="label">Channel</span><span class="value">${result.channel}</span></div>
            <div class="content-meta-item"><span class="label">Product</span><span class="value">${result.product_recommended}</span></div>
            <div class="content-meta-item"><span class="label">Method</span><span class="value">${result.generation_method}</span></div>
        </div>`;

        const content = result.content || {};
        let html = '';

        // Dynamic Weather Triggers & Orchestration
        let orchHtml = '<div style="display:grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;">';
        orchHtml += `<div class="content-block"><div class="content-block-label">🌩️ Active Weather Triggers</div><div class="content-block-text" style="font-size:12px;">`;
        if (result.weather_triggers && result.weather_triggers.length > 0) {
            orchHtml += result.weather_triggers.map(t => `<span class="tag tag-red">${t.disease}</span> (Severity: ${t.severity})`).join('<br/>');
        } else {
            orchHtml += "None detected. Using default crop schedule.";
        }
        orchHtml += `</div></div>`;

        orchHtml += `<div class="content-block"><div class="content-block-label">⏱️ Delivery Orchestration</div><div class="content-block-text" style="font-size:12px;">`;
        if (result.delivery_plan) {
            orchHtml += `<b>Sequence:</b> ${result.delivery_plan.channel_sequence.join(' → ')}<br/>`;
            orchHtml += `<b>Send Window:</b> ${result.delivery_plan.send_window.start} - ${result.delivery_plan.send_window.end}<br/>`;
            orchHtml += `<b>Reason:</b> ${result.delivery_plan.routing_reason}`;
        }
        orchHtml += `</div></div></div>`;
        html += orchHtml;

        // Content Guardrails
        if (result.guardrail_check) {
            const passed = result.guardrail_check.passed;
            html += `<div class="content-block" style="border-left: 4px solid ${passed ? 'var(--accent-green)' : 'var(--accent-red)'}">`;
            html += `<div class="content-block-label">🛡️ Content Guardrails</div><div class="content-block-text" style="font-size:12px;">`;
            html += passed ? "✅ All checks passed. No forbidden claims detected." : "❌ WARNING: Guardrail violations detected!";
            if (result.guardrail_check.issues && result.guardrail_check.issues.length > 0) {
                html += "<ul>" + result.guardrail_check.issues.map(i => `<li>${i.message}</li>`).join('') + "</ul>";
            }
            html += `</div></div>`;
        }

        // Output Delivery Blocks
        if (content.whatsapp) html += `<div class="content-block"><div class="content-block-label">📱 WhatsApp Message</div><div class="content-block-text">${content.whatsapp}</div></div>`;
        if (content.sms) html += `<div class="content-block sms"><div class="content-block-label">💬 SMS</div><div class="content-block-text">${content.sms}</div></div>`;

        if (content.voice_script) {
            html += `<div class="content-block voice">
                <div class="content-block-label">🎙️ Voice Call Script</div>
                <div class="content-block-text">${content.voice_script}</div>`;

            if (content.voice_audio_base64) {
                html += `<div style="margin-top: 12px;">
                    <audio controls style="width: 100%; height: 35px; filter: invert(90%) sepia(20%) saturate(300%) hue-rotate(350deg);">
                        <source src="${content.voice_audio_base64}" type="audio/mp3">
                    </audio>
                  </div>`;
            }
            html += `</div>`;
        }

        // Visual Concepts & Video Layout
        if (content.visual_prompt) {
            html += `<div class="content-block"><div class="content-block-label">🎨 Visual Concept Prompt (For Image AI)</div><div class="content-block-text" style="font-family:monospace; font-size:11px; background:var(--bg-dark); padding:8px;">${content.visual_prompt}</div></div>`;
        }
        if (content.video_storyboard) {
            html += `<div class="content-block"><div class="content-block-label">🎬 Video Storyboard (For Low-Literacy Segments)</div><div class="content-block-text" style="font-size:12px;">`;
            content.video_storyboard.forEach(scene => {
                html += `<div style="margin-bottom:8px; border-bottom:1px solid var(--border-color); padding-bottom:4px;"><b>Scene ${scene.scene} (${scene.duration_sec}s):</b> ${scene.visual}<br/><i style="color:var(--text-muted)">Voice: "${scene.narration_en}"</i></div>`;
            });
            html += `</div></div>`;
        }

        // ─── Human-in-the-Loop (RLHF) Panel ───
        if (html !== '') {
            window.lastGeneratedPayload = content;

            html += `
            <div class="content-block" style="border: 1px dashed var(--border-color); margin-top: 25px; padding: 15px; background: rgba(0,0,0,0.2);">
                <div class="content-block-label">👨‍⚖️ Human-in-the-Loop Evaluation (RLHF)</div>
                <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 10px;">Evaluate this AI generation for safety and tone before network dispatch.</div>
                <div style="display: flex; gap: 10px;">
                    <button onclick="submitRLHF('${result.grower_id}', '${result.generation_method}', 'thumbs_up')" style="background: var(--toxic-green); color: black; border: none; padding: 8px 16px; cursor: pointer; font-weight: bold; border-radius: 2px;">👍 APPROVED</button>
                    <button onclick="submitRLHF('${result.grower_id}', '${result.generation_method}', 'thumbs_down')" style="background: #ef4444; color: white; border: none; padding: 8px 16px; cursor: pointer; font-weight: bold; border-radius: 2px;">👎 HALLUCINATION / REJECT</button>
                </div>
                <div id="rlhf-status" style="margin-top: 10px; font-size: 12px; font-weight: bold;"></div>
            </div>`;
        }

        $('content-outputs').innerHTML = html || '<p>No content generated</p>';
    } catch (e) { $('content-meta').innerHTML = '<p style="color:var(--accent-red)">Error: ' + e.message + '</p>'; }
});

// ─── Analytics ───
document.querySelector('[data-tab="analytics"]').addEventListener('click', loadAnalytics);
async function loadAnalytics() {
    try {
        const wa = await api('/api/analytics/whatsapp');
        const maxWa = wa.total_messages;
        $('wa-funnel').innerHTML = `<div class="funnel-chart">
            <div class="funnel-step"><div class="funnel-label">Sent</div><div class="funnel-bar" style="width:100%;background:linear-gradient(90deg,#6366f1,#818cf8)">${fmt(wa.total_messages)}</div><div class="funnel-rate">100%</div></div>
            <div class="funnel-step"><div class="funnel-label">Delivered</div><div class="funnel-bar" style="width:${wa.delivery_rate * 100}%;background:linear-gradient(90deg,#3b82f6,#60a5fa)">${fmt(wa.delivered)}</div><div class="funnel-rate">${pct(wa.delivery_rate)}</div></div>
            <div class="funnel-step"><div class="funnel-label">Opened</div><div class="funnel-bar" style="width:${(wa.opened / maxWa) * 100}%;background:linear-gradient(90deg,#f59e0b,#fbbf24)">${fmt(wa.opened)}</div><div class="funnel-rate">${pct(wa.open_rate)}</div></div>
            <div class="funnel-step"><div class="funnel-label">Clicked</div><div class="funnel-bar" style="width:${(wa.clicked / maxWa) * 100}%;background:linear-gradient(90deg,#22c55e,#4ade80)">${fmt(wa.clicked)}</div><div class="funnel-rate">${pct(wa.click_rate)}</div></div>
        </div>`;

        const conv = await api('/api/analytics/conversion');
        $('conversion-attribution').innerHTML = kvList([
            { k: 'Total Messages', v: conv.total_messages },
            { k: 'Total Clicked', v: conv.total_clicked },
            { k: 'Converted (Scanned)', v: conv.total_converted_scan },
            { k: 'Campaign-to-Action Rate', v: `<span class="tag tag-green">${pct(conv.campaign_to_action_rate)}</span>` },
            { k: 'Click-to-Scan Rate', v: `<span class="tag tag-amber">${pct(conv.click_to_scan_rate)}</span>` },
        ]) + '<h4 style="margin-top:16px;font-size:13px;color:var(--text-muted)">By Crop</h4>' +
            '<div class="kv-list" style="margin-top:8px">' + Object.entries(conv.by_crop).map(([crop, d]) =>
                `<div class="kv-item"><span class="kv-key">${crop}</span><span class="kv-value">${d.messages} msgs → ${d.scanned_after_click} scans (${pct(d.campaign_to_action_rate)})</span></div>`
            ).join('') + '</div>';

        const df = await api('/api/analytics/digital-funnel');
        $('digital-funnel').innerHTML = '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px">' +
            Object.entries(df.campaigns).map(([id, c]) => `<div style="background:var(--bg-elevated);border-radius:var(--radius-md);padding:20px">
                <div style="font-weight:700;margin-bottom:8px">${c.campaign_crop} — ${c.campaign_product}</div>
                ${kvList([
                { k: 'Impressions', v: fmt(c.total_impressions) },
                { k: 'Visits', v: fmt(c.total_visits) + ' (' + pct(c.impression_to_visit_rate) + ')' },
                { k: 'Leads', v: fmt(c.total_leads) + ' (' + pct(c.visit_to_lead_rate) + ')' },
            ])}
            </div>`).join('') + '</div>';

        const inv = await api('/api/analytics/inventory');
        const skus = Object.entries(inv.by_sku).sort((a, b) => b[1].out_of_stock_rate - a[1].out_of_stock_rate);
        $('inventory-health').innerHTML = '<p style="font-size:12px;color:var(--text-muted);margin-bottom:12px">Snapshot: ' + inv.snapshot_week + '</p>' +
            barChart(skus.map(([name, d]) => ({ label: name, value: d.out_of_stock_rate * 100, display: pct(d.out_of_stock_rate) + ' OOS' })), 100, ['red', 'amber', 'amber', 'amber', 'green', 'green']);

        const fa = await api('/api/analytics/field-activity');
        $('field-activity').innerHTML = kvList([
            { k: 'Total Visits', v: fmt(fa.total_visits) },
            ...Object.entries(fa.by_type).map(([k, v]) => ({ k: k, v: fmt(v) })),
        ]);

    } catch (e) { console.error(e); }
}

// ─── ML Model ───
document.querySelector('[data-tab="model"]').addEventListener('click', loadModel);
async function loadModel() {
    try {
        const info = await api('/api/model/info');
        const oi = info.open_feature_importance || {};
        const maxFI = Math.max(...Object.values(oi), 0.01);

        // Clean label mapper to turn ugly database keys into professional titles
        const featureLabels = {
            "cohort_open_propensity": "Lookalike Cluster Open Rate",
            "cohort_click_propensity": "Lookalike Cluster Click Rate",
            "predicted_open_prob": "Engineered Open Propensity Signal",
            "age_farm_ratio": "Resource Allocation Density Index",
            "days_since_sowing": "Days Since Crop Sowing",
            "grower_farm_size": "Farm Size (Acres)",
            "grower_age": "Grower Age",
            "offline_attended": "Field Day Attendance",
            "has_scanned": "Past QR Product Scans",
            "language_enc": "Regional Language Profile",
            "product_enc": "Target Chemical Profile",
            "msg_month": "Seasonal Month Signal",
            "msg_day_of_week": "Day of Week Signal",
            "gender_enc": "Demographic Gender Profile"
        };

        $('model-info').innerHTML = `
            <div class="model-metrics">
                <div class="model-metric"><div class="value green">${info.open_model_auc_cv5}</div><div class="label">Open Model AUC (5-fold CV)</div></div>
                <div class="model-metric"><div class="value blue">${info.click_model_auc_cv5}</div><div class="label">Click Model AUC (5-fold CV)</div></div>
                <div class="model-metric"><div class="value amber">${fmt(info.training_samples)}</div><div class="label">Training Samples</div></div>
                <div class="model-metric"><div class="value purple">${pct(info.open_rate_actual)}</div><div class="label">Actual Open Rate</div></div>
            </div>
            <h3>Feature Importance (Open Model)</h3>
            <div class="feature-importance">${Object.entries(oi).sort((a, b) => b[1] - a[1]).map(([k, v]) => {
            const cleanName = featureLabels[k] || k; // Fallback to key if label missing
            return `<div class="fi-row"><div class="fi-name">${cleanName}</div><div class="fi-bar-track"><div class="fi-bar-fill" style="width:${(v / maxFI) * 100}%"></div></div><div class="fi-value">${v.toFixed(3)}</div></div>`;
        }).join('')}</div>`;
    } catch (e) { $('model-info').innerHTML = '<p style="color:var(--accent-red)">Error loading model: ' + e.message + '</p>'; }
}

$('model-predict-btn').addEventListener('click', async () => {
    const gid = $('model-grower-input').value.trim();
    if (!gid) return;
    try {
        const pred = await api(`/api/grower/${gid}/receptivity`);
        const tierColor = pred.engagement_tier === 'high' ? 'green' : pred.engagement_tier === 'medium' ? 'amber' : 'red';
        $('model-prediction').innerHTML = `<div class="prediction-result">
            <div class="pred-gauge"><div class="gauge-value green">${(pred.open_probability * 100).toFixed(1)}%</div><div class="gauge-label">Open Probability</div></div>
            <div class="pred-gauge"><div class="gauge-value blue">${(pred.click_probability * 100).toFixed(1)}%</div><div class="gauge-label">Click Probability</div></div>
            <div class="pred-gauge"><div class="gauge-value ${tierColor}">${pred.engagement_tier.toUpperCase()}</div><div class="gauge-label">Engagement Tier</div><div class="gauge-tier"><span class="tag tag-${tierColor}">${pred.engagement_tier}</span></div></div>
        </div>`;
    } catch (e) { $('model-prediction').innerHTML = '<p style="color:var(--accent-red)">' + e.message + '</p>'; }
});

// ─── RLHF Submission Handler ───
async function submitRLHF(growerId, campaignId, status) {
    const statusDiv = document.getElementById('rlhf-status');
    statusDiv.style.color = 'var(--text-muted)';
    statusDiv.innerText = "Submitting feedback to model logs...";

    let reason = "";
    if (status === 'thumbs_down') {
        reason = prompt("Why are you rejecting this? (e.g., Tone, Hallucination, Bad translation)");
        if (reason === null) {
            statusDiv.innerText = "";
            return;
        }
    }

    try {
        const response = await fetch(`${API}'/api/rlhf/feedback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                grower_id: growerId,
                campaign_id: campaignId,
                status: status,
                failure_reason: reason,
                payload_snapshot: window.lastGeneratedPayload || {}
            })
        });

        if (response.ok) {
            statusDiv.style.color = status === 'thumbs_up' ? 'var(--toxic-green)' : '#ef4444';
            statusDiv.innerText = "✅ Feedback successfully written to RLHF tuning logs.";
        } else {
            statusDiv.style.color = '#ef4444';
            statusDiv.innerText = "❌ Failed to log feedback.";
        }
    } catch (e) {
        statusDiv.style.color = '#ef4444';
        statusDiv.innerText = "❌ Error: " + e.message;
    }
}

// ─── Init ───
boot();