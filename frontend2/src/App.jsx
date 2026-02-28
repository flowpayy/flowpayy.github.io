import React, { useState, useEffect } from 'react';
import { FlowPayAPI } from './api';
import { ArrowRight, Wallet, CheckCircle2, XCircle, RefreshCcw, Activity, Globe } from 'lucide-react';

// Hardcoded IDs from the seeding script
const JORDAN_ID = "69a268d595150878eaffa3bb"; // Generated customer ID usually +1, but not strictly needed for API calls that take acc
const JORDAN_ACC = "69a268d595150878eaffa3bc"; // Client/Payer
const ALEX_ACC = "69a268d595150878eaffa3ba"; // Freelancer/Payee

function App() {
    const [activeTab, setActiveTab] = useState('collect');
    const [collectInbox, setCollectInbox] = useState([]);
    const [activePool, setActivePool] = useState(null);
    const [activeCorridor, setActiveCorridor] = useState(null);
    const [activeFXPool, setActiveFXPool] = useState(null);
    const [webhookLogs, setWebhookLogs] = useState([]);
    const [loading, setLoading] = useState(false);

    // Poll for collect inbox (simple hackathon setup)
    useEffect(() => {
        let interval;
        if (activeTab === 'collect') {
            fetchCollects();
            interval = setInterval(fetchCollects, 3000);
        }
        return () => clearInterval(interval);
    }, [activeTab]);

    useEffect(() => {
        let interval;
        if (activeTab === 'pool' && activePool) {
            fetchPool();
            interval = setInterval(fetchPool, 2000);
        }
        return () => clearInterval(interval);
    }, [activeTab, activePool?.id]);

    const fetchCollects = async () => {
        try {
            const data = await FlowPayAPI.getCollectsByPayer(JORDAN_ACC);
            setCollectInbox(data);
        } catch (e) {
            console.error(e);
        }
    };

    const fetchPool = async () => {
        if (!activePool) return;
        try {
            const data = await FlowPayAPI.getPool(activePool.id);
            setActivePool(data);
        } catch (e) {
            console.error(e);
        }
    };

    const createDemoCollect = async () => {
        setLoading(true);
        try {
            await FlowPayAPI.createCollect({
                payee_account_id: ALEX_ACC,
                payer_account_id: JORDAN_ACC,
                amount: 4900, // $49.00
                description: "Logo design project — Phase 1",
                expires_at: new Date(Date.now() + 86400000).toISOString()
            });
            addWebhookLog("System", "Payee sent Collect request to Payer");
            fetchCollects();
        } catch (e) {
            console.error(e);
        }
        setLoading(false);
    };

    const approveCollect = async (id) => {
        try {
            await FlowPayAPI.approveCollect(id);
            addWebhookLog("webhook: collect.approved", `Nessie transfer initiated for ${id}`);
            fetchCollects();
        } catch (e) {
            console.error(e);
            alert(e.response?.data?.error?.message || "Failed to approve");
        }
    };

    const createDemoPool = async () => {
        setLoading(true);
        try {
            const pool = await FlowPayAPI.createPool({
                goal_amount: 20000, // $200.00
                description: "Dinner at Au Cheval",
                organizer_account_id: ALEX_ACC,
                payee_account_id: ALEX_ACC,
                deadline: new Date(Date.now() + 60000).toISOString() // 1 minute
            });
            setActivePool(pool);
            addWebhookLog("System", "Organizer created a $200.00 Pool");
        } catch (e) {
            console.error(e);
        }
        setLoading(false);
    };

    const contributeToPool = async () => {
        if (!activePool) return;
        try {
            await FlowPayAPI.contributeToPool(activePool.id, {
                payer_account_id: JORDAN_ACC,
                amount: 5000 // $50.00
            });
            addWebhookLog("webhook: pool.contribution_received", "$50.00 transferred via Nessie");
            fetchPool();
        } catch (e) {
            console.error(e);
        }
    }

    const addWebhookLog = (event, msg) => {
        setWebhookLogs(prev => [...prev, { time: new Date().toLocaleTimeString(), event, msg }]);
    };

    // FlowBridge: Corridor
    const createCorridor = async () => {
        setLoading(true);
        try {
            const res = await fetch('http://localhost:8000/v1/corridors/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    source_currency: 'inr',
                    target_currency: 'usd',
                    source_account_id: JORDAN_ACC,
                    target_account_id: ALEX_ACC,
                    amount_target: 4900,
                    description: 'Freelancer payment: India → USA',
                    lock_duration_minutes: 30,
                    max_rate_drift_pct: 2.0
                })
            });
            const data = await res.json();
            setActiveCorridor(data);
            const rate = data.rate_lock?.rate?.toFixed(4);
            addWebhookLog('corridor.rate_locked', `1 INR = ${rate} USD · Lock expires in 30 min`);
        } catch (e) { console.error(e); }
        setLoading(false);
    };

    const remitCorridor = async () => {
        if (!activeCorridor) return;
        try {
            const res = await fetch(`http://localhost:8000/v1/corridors/${activeCorridor.id}/remit`, { method: 'POST' });
            const data = await res.json();
            if (data.status === 'remitted') {
                setActiveCorridor(data);
                addWebhookLog('corridor.settled', `Nessie tx: ${data.nessie_transfer_id} · ₹${(activeCorridor.amount_source_cents / 100).toFixed(2)} → $${(activeCorridor.amount_target_cents / 100).toFixed(2)}`);
            } else {
                addWebhookLog('corridor.drift_cancelled', 'Rate drifted too far — Corridor auto-cancelled!');
                setActiveCorridor(data);
            }
        } catch (e) { console.error(e); }
    };

    // FlowBridge: FX Pool
    const createFXPool = async () => {
        setLoading(true);
        try {
            const res = await fetch('http://localhost:8000/v1/fxpools/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    goal_amount_usd: 20000,
                    organizer_account_id: ALEX_ACC,
                    payee_account_id: ALEX_ACC,
                    description: 'Global team dinner split',
                    deadline: new Date(Date.now() + 120000).toISOString(),
                    max_rate_drift_pct: 3.0
                })
            });
            const data = await res.json();
            setActiveFXPool(data);
            addWebhookLog('System', 'FX Pool created — Goal $200 USD');
        } catch (e) { console.error(e); }
        setLoading(false);
    };

    const contributeToFXPool = async (currency, amount_local) => {
        if (!activeFXPool) return;
        try {
            const res = await fetch(`http://localhost:8000/v1/fxpools/${activeFXPool.id}/contribute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ payer_account_id: JORDAN_ACC, currency, amount_local })
            });
            const data = await res.json();
            setActiveFXPool(data);
            addWebhookLog('fxpool.contribution_received', `${currency.toUpperCase()} ${(amount_local / 100).toFixed(2)} → $${(data.collected_usd / 100).toFixed(2)} USD collected`);
        } catch (e) { console.error(e); }
    };

    const forceDriftFXPool = async () => {
        if (!activeFXPool) return;
        try {
            const res = await fetch(`http://localhost:8000/v1/fxpools/${activeFXPool.id}/force-drift`, { method: 'POST' });
            const data = await res.json();
            setActiveFXPool(data);
            addWebhookLog('fxpool.rate_drifted', '⚡ FX drift exceeded 3%! All contributors auto-refunded in original currency.');
        } catch (e) { console.error(e); }
    };


    return (
        <div className="app-container">
            {/* SIDEBAR */}
            <aside className="sidebar">
                <div>
                    <h1 className="header-accent" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Activity size={28} /> FlowPay
                    </h1>
                    <p className="text-muted" style={{ marginTop: '0.5rem' }}>The Primitive Stripe Doesn't Have</p>
                </div>

                <nav style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '1rem' }}>
                    <button
                        className={`btn ${activeTab === 'collect' ? 'btn-primary' : 'btn-outline'}`}
                        onClick={() => setActiveTab('collect')}
                    >
                        <Wallet size={16} /> Scenario 1: Pull Collect
                    </button>
                    <button
                        className={`btn ${activeTab === 'pool' ? 'btn-primary' : 'btn-outline'}`}
                        onClick={() => setActiveTab('pool')}
                    >
                        <RefreshCcw size={16} /> Scenario 2/3: Group Pool
                    </button>
                    <button
                        className={`btn ${activeTab === 'flowbridge' ? 'btn-primary' : 'btn-outline'}`}
                        onClick={() => setActiveTab('flowbridge')}
                        style={{ background: activeTab === 'flowbridge' ? 'linear-gradient(135deg,#5b21b6,#1d4ed8)' : undefined }}
                    >
                        <Globe size={16} /> 🌏 FlowBridge: Cross-Border
                    </button>
                </nav>

                <div style={{ marginTop: 'auto' }}>
                    <div className="card">
                        <h3 style={{ fontSize: '0.875rem' }}>Payer Context</h3>
                        <p className="text-muted">Jordan's iPhone</p>
                        <p className="text-muted" style={{ fontSize: '10px' }}>{JORDAN_ACC}</p>
                    </div>
                </div>
            </aside>

            {/* MAIN CONTENT */}
            <main className="main-content">

                {activeTab === 'flowbridge' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>

                        {/* CORRIDOR */}
                        <div className="card" style={{ border: '1px solid rgba(147,51,234,0.3)' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                                <div>
                                    <h2 style={{ color: '#a78bfa' }}>🌏 FlowBridge: FX Corridor</h2>
                                    <p className="text-muted" style={{ fontSize: '.8rem', marginTop: '.25rem' }}>India (INR) → USA (USD) · Rate-locked cross-border pull payment</p>
                                </div>
                                {!activeCorridor && (
                                    <button className="btn btn-primary" onClick={createCorridor} disabled={loading}>
                                        Lock INR→USD Rate &amp; Create Corridor
                                    </button>
                                )}
                            </div>

                            {activeCorridor && (
                                <div>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
                                        <div className="card" style={{ textAlign: 'center' }}>
                                            <p className="text-muted" style={{ fontSize: '.7rem' }}>LOCKED RATE</p>
                                            <p style={{ fontSize: '1.25rem', fontWeight: 700, color: '#a78bfa', fontFamily: 'monospace' }}>1 INR = {activeCorridor.rate_lock?.rate?.toFixed(4)} USD</p>
                                        </div>
                                        <div className="card" style={{ textAlign: 'center' }}>
                                            <p className="text-muted" style={{ fontSize: '.7rem' }}>PAYER PAYS</p>
                                            <p style={{ fontSize: '1.25rem', fontWeight: 700 }}>₹{(activeCorridor.amount_source_cents / 100).toFixed(2)}</p>
                                        </div>
                                        <div className="card" style={{ textAlign: 'center' }}>
                                            <p className="text-muted" style={{ fontSize: '.7rem' }}>PAYEE RECEIVES</p>
                                            <p style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--accent-green)' }}>${(activeCorridor.amount_target_cents / 100).toFixed(2)}</p>
                                        </div>
                                    </div>
                                    <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                                        <span className={`badge badge-${activeCorridor.status === 'remitted' ? 'approved' : activeCorridor.status === 'rate_locked' ? 'pending' : 'declined'}`}>{activeCorridor.status}</span>
                                        {activeCorridor.status === 'rate_locked' && (
                                            <button className="btn btn-success" onClick={remitCorridor}>Execute Cross-Border Transfer →</button>
                                        )}
                                        {activeCorridor.nessie_transfer_id && (
                                            <p className="text-muted" style={{ fontFamily: 'monospace', fontSize: '.75rem' }}>nessie: {activeCorridor.nessie_transfer_id}</p>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* FX POOL */}
                        <div className="card" style={{ border: '1px solid rgba(59,130,246,0.3)' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                                <div>
                                    <h2 style={{ color: '#60a5fa' }}>💸 FlowBridge: Multi-Currency Pool</h2>
                                    <p className="text-muted" style={{ fontSize: '.8rem', marginTop: '.25rem' }}>4 friends, 4 countries, 4 currencies → $200 USD · Auto-refund on FX drift</p>
                                </div>
                                {!activeFXPool && (
                                    <button className="btn btn-primary" onClick={createFXPool} disabled={loading}>Create $200 Global Pool</button>
                                )}
                            </div>

                            {activeFXPool && (
                                <div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '.5rem' }}>
                                        <span className="text-muted">${(activeFXPool.collected_usd / 100).toFixed(2)} collected</span>
                                        <span className="text-muted">Goal: ${(activeFXPool.goal_amount_usd / 100).toFixed(2)} USD</span>
                                    </div>
                                    <div className="progress-container">
                                        <div className="progress-bar" style={{
                                            width: `${Math.min(100, (activeFXPool.collected_usd / activeFXPool.goal_amount_usd) * 100)}%`,
                                            background: activeFXPool.status === 'funded' ? 'var(--accent-green)' : 'linear-gradient(90deg,#5b21b6,#1d4ed8)'
                                        }} />
                                    </div>
                                    <p className="text-muted" style={{ fontSize: '.75rem', marginTop: '.5rem' }}>
                                        Currencies collected: {activeFXPool.currencies_collected?.join(', ').toUpperCase() || 'none yet'}
                                    </p>

                                    {activeFXPool.status === 'collecting' && (
                                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.75rem', marginTop: '1rem' }}>
                                            <button className="btn btn-outline" style={{ fontSize: '.75rem' }} onClick={() => contributeToFXPool('inr', 4100)}>🇮🇳 Ravi pays ₹41.00</button>
                                            <button className="btn btn-outline" style={{ fontSize: '.75rem' }} onClick={() => contributeToFXPool('eur', 4500)}>🇩🇪 Emma pays €45.00</button>
                                            <button className="btn btn-outline" style={{ fontSize: '.75rem' }} onClick={() => contributeToFXPool('gbp', 3900)}>🇬🇧 Liam pays £39.00</button>
                                            <button className="btn btn-outline" style={{ fontSize: '.75rem' }} onClick={() => contributeToFXPool('usd', 5000)}>🇺🇸 Jordan pays $50.00</button>
                                            <button className="btn btn-danger" style={{ fontSize: '.75rem' }} onClick={forceDriftFXPool}>⚡ Simulate FX Rate Drift → Auto-Refund</button>
                                        </div>
                                    )}
                                    {activeFXPool.status === 'funded' && (
                                        <p style={{ color: 'var(--accent-green)', marginTop: '1rem' }}><CheckCircle2 size={16} style={{ display: 'inline' }} /> Pool settled! ${(activeFXPool.collected_usd / 100).toFixed(2)} USD transferred to organizer via Nessie.</p>
                                    )}
                                    {(activeFXPool.status === 'drift_refunded' || activeFXPool.status === 'cancelled') && (
                                        <p style={{ color: 'var(--accent-red)', marginTop: '1rem' }}><XCircle size={16} style={{ display: 'inline' }} /> {activeFXPool.status === 'drift_refunded' ? 'FX rate drifted — everyone refunded in their original currency!' : 'Pool cancelled — all refunded.'}</p>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {activeTab === 'collect' && (
                    <div className="card">
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                            <h2>Jordan's Inbox (Payer)</h2>
                            <button className="btn btn-outline" onClick={createDemoCollect} disabled={loading}>
                                Simulate: Freelancer Requests $49
                            </button>
                        </div>

                        {collectInbox.length === 0 ? (
                            <p className="text-muted text-center" style={{ padding: '2rem' }}>No pending payment requests.</p>
                        ) : (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                                {collectInbox.map(c => (
                                    <div key={c.id} className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                        <div>
                                            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                                                <h3>${(c.amount / 100).toFixed(2)}</h3>
                                                <span className={`badge badge-${c.status}`}>{c.status}</span>
                                            </div>
                                            <p className="text-muted">{c.description}</p>
                                        </div>

                                        {c.status === 'pending' && (
                                            <div style={{ display: 'flex', gap: '0.5rem' }}>
                                                <button className="btn btn-danger" onClick={() => {/* decline logic */ }}>
                                                    <XCircle size={16} /> Decline
                                                </button>
                                                <button className="btn btn-success" onClick={() => approveCollect(c.id)}>
                                                    <CheckCircle2 size={16} /> Approve
                                                </button>
                                            </div>
                                        )}
                                        {c.status === 'approved' && (
                                            <p className="text-muted" style={{ fontFamily: 'monospace' }}>txn: {c.nessie_transfer_id}</p>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {activeTab === 'pool' && (
                    <div className="card">
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                            <h2>Active Group Pools</h2>
                            {!activePool && (
                                <button className="btn btn-primary" onClick={createDemoPool} disabled={loading}>
                                    Simulate: Create $200 Dinner Split
                                </button>
                            )}
                        </div>

                        {activePool ? (
                            <div className="card" style={{ border: '1px solid var(--accent-blue)' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                    <h3>{activePool.description}</h3>
                                    <span className={`badge badge-${activePool.status}`}>{activePool.status}</span>
                                </div>

                                <div style={{ marginTop: '1.5rem' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                        <span className="text-muted">${(activePool.collected_amount / 100).toFixed(2)} collected</span>
                                        <span className="text-muted">Goal: ${(activePool.goal_amount / 100).toFixed(2)}</span>
                                    </div>
                                    <div className="progress-container">
                                        <div
                                            className="progress-bar"
                                            style={{
                                                width: `${Math.min(100, (activePool.collected_amount / activePool.goal_amount) * 100)}%`,
                                                background: activePool.status === 'funded' ? 'var(--accent-green)' : 'var(--accent-blue)'
                                            }}
                                        />
                                    </div>
                                </div>

                                {activePool.status === 'collecting' && (
                                    <div style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem' }}>
                                        <button className="btn btn-outline" onClick={contributeToPool}>
                                            Simulate Participant Paying $50
                                        </button>
                                        <button className="btn btn-danger" onClick={async () => {
                                            try {
                                                await fetch(`http://localhost:8000/v1/pools/${activePool.id}/cancel`, { method: "POST" });
                                                addWebhookLog("webhook: pool.cancelled", "Refunds issued to all participants via Nessie");
                                                fetchPool();
                                            } catch (e) {
                                                console.error(e);
                                            }
                                        }}>
                                            Force Cancel (Trigger Refunds)
                                        </button>
                                    </div>
                                )}
                                {activePool.status === 'funded' && (
                                    <p style={{ color: 'var(--accent-green)', marginTop: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                        <CheckCircle2 size={18} /> Pool Goal Reached! Nessie Settlement Transfer executed.
                                    </p>
                                )}
                                {activePool.status === 'cancelled' && (
                                    <div style={{ marginTop: '1rem' }}>
                                        <p style={{ color: 'var(--accent-red)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                            <XCircle size={18} /> Pool Cancelled. All contributions refunded via reverse transfer.
                                        </p>
                                        <p className="text-muted" style={{ fontSize: '12px', marginTop: '0.5rem' }}>Refund Nessie Txs: {activePool.refund_ids?.join(', ')}</p>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <p className="text-muted text-center" style={{ padding: '2rem' }}>No active group pools.</p>
                        )}
                    </div>
                )}

                {/* WEBHOOK TERMINAL FEED */}
                <div style={{ marginTop: 'auto' }}>
                    <h2>Live Sandbox Events</h2>
                    <div className="webhook-feed">
                        {webhookLogs.length === 0 && <span style={{ color: '#666' }}>Waiting for events...</span>}
                        {webhookLogs.map((log, i) => (
                            <div key={i} className="webhook-item">
                                <span style={{ color: '#888' }}>== [{log.time}] == </span><br />
                                <span style={{ color: '#fff' }}>{log.event}</span><br />
                                <span style={{ color: 'var(--text-secondary)' }}>{log.msg}</span>
                            </div>
                        ))}
                        {/* Simple autoscroll hack would go here, omitting for brevity */}
                    </div>
                </div>

            </main>
        </div>
    );
}

export default App;
