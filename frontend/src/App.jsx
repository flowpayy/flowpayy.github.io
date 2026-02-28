import React, { useState, useEffect } from 'react';
import { FlowPayAPI } from './api';
import { ArrowRight, Wallet, CheckCircle2, XCircle, RefreshCcw, Activity } from 'lucide-react';

// Hardcoded IDs from the seeding script
const JORDAN_ID = "67c134aa9683f20481ec20f4";
const JORDAN_ACC = "67c134aa9683f20481ec20f5"; // Client/Payer
const ALEX_ACC = "67c134ab9683f20481ec20f7"; // Freelancer/Payee

function App() {
    const [activeTab, setActiveTab] = useState('collect');
    const [collectInbox, setCollectInbox] = useState([]);
    const [activePool, setActivePool] = useState(null);
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
                                        <button className="btn btn-danger" onClick={() => {
                                            FlowPayAPI.api.post(`/pools/${activePool.id}/cancel`).then(() => {
                                                addWebhookLog("webhook: pool.cancelled", "Refunds issued to all participants via Nessie");
                                                fetchPool();
                                            });
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
