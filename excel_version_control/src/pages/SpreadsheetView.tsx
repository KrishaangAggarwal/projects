import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../lib/api';
import SpreadsheetGrid from '../components/SpreadsheetGrid';
import CommitHistory from '../components/CommitHistory';
import AuditLog from '../components/AuditLog';
import DiffViewer from '../components/DiffViewer';
import BranchSelector from '../components/BranchSelector';

type Tab = 'editor' | 'history' | 'audit' | 'diff';

export default function SpreadsheetView() {
    const { id } = useParams<{ id: string }>();
    const [sheets, setSheets] = useState<any[]>([]);
    const [activeSheet, setActiveSheet] = useState<string | null>(null);
    const [branches, setBranches] = useState<any[]>([]);
    const [activeBranch, setActiveBranch] = useState('main');
    const [branchId, setBranchId] = useState<string | null>(null);
    const [cells, setCells] = useState<any[]>([]);
    const [pendingChanges, setPendingChanges] = useState<Map<string, any>>(new Map());
    const [activeTab, setActiveTab] = useState<Tab>('editor');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (id) loadData();
    }, [id]);

    useEffect(() => {
        if (id && activeSheet) loadCells();
    }, [activeSheet, activeBranch]);

    const loadData = async () => {
        try {
            const [sheetsRes, branchesRes] = await Promise.all([
                api.sheets.list(id!),
                api.branches.list(id!),
            ]);
            setSheets(sheetsRes.sheets);
            setBranches(branchesRes.branches);
            if (sheetsRes.sheets.length > 0) {
                setActiveSheet(sheetsRes.sheets[0].id);
            }
        } catch (err) {
            console.error('Failed to load data:', err);
        } finally {
            setLoading(false);
        }
    };

    const loadCells = async () => {
        if (!activeSheet) return;
        try {
            const { cells, branchId } = await api.sheets.getCells(id!, activeSheet, activeBranch);
            setCells(cells);
            setBranchId(branchId);
            setPendingChanges(new Map());
        } catch (err) {
            console.error('Failed to load cells:', err);
        }
    };

    const handleCellChange = (row: number, column: number, oldValue: string | null, newValue: string) => {
        const key = `${row},${column}`;
        const change = { sheetId: activeSheet!, row, column, oldValue, newValue };
        setPendingChanges(prev => new Map(prev).set(key, change));
    };

    const handleCommit = async (message: string) => {
        if (!branchId || pendingChanges.size === 0) return;
        try {
            await api.commits.create(id!, branchId, message, Array.from(pendingChanges.values()));
            await loadCells();
        } catch (err: any) {
            alert(err.message);
        }
    };

    const handleBranchChange = (branch: string) => {
        setActiveBranch(branch);
    };

    const handleCreateBranch = async (name: string) => {
        try {
            await api.branches.create(id!, name, activeBranch);
            const { branches } = await api.branches.list(id!);
            setBranches(branches);
            setActiveBranch(name);
        } catch (err: any) {
            alert(err.message);
        }
    };

    const handleMerge = async (sourceBranch: string, targetBranch: string) => {
        try {
            const result = await api.branches.merge(id!, sourceBranch, targetBranch);
            if (result.hasConflicts) {
                alert(`Merge conflicts detected in ${result.conflicts?.length} cells. Manual resolution required.`);
            } else {
                alert('Merge successful!');
                await loadCells();
            }
        } catch (err: any) {
            alert(err.message);
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 flex flex-col">
            <header className="bg-white shadow-sm">
                <div className="max-w-full mx-auto px-4 py-3 flex justify-between items-center">
                    <div className="flex items-center gap-4">
                        <Link to="/" className="text-gray-500 hover:text-gray-700">
                            ← Back
                        </Link>
                        <h1 className="text-lg font-semibold text-gray-900">Spreadsheet Editor</h1>
                    </div>
                    <BranchSelector
                        branches={branches}
                        activeBranch={activeBranch}
                        onBranchChange={handleBranchChange}
                        onCreateBranch={handleCreateBranch}
                        onMerge={handleMerge}
                    />
                </div>
            </header>

            <div className="border-b bg-white">
                <nav className="max-w-full mx-auto px-4 flex gap-4">
                    {(['editor', 'history', 'audit', 'diff'] as Tab[]).map((tab) => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab)}
                            className={`py-3 px-1 border-b-2 text-sm font-medium ${activeTab === tab
                                    ? 'border-primary-500 text-primary-600'
                                    : 'border-transparent text-gray-500 hover:text-gray-700'
                                }`}
                        >
                            {tab.charAt(0).toUpperCase() + tab.slice(1)}
                        </button>
                    ))}
                </nav>
            </div>

            <main className="flex-1 overflow-hidden">
                {activeTab === 'editor' && (
                    <div className="h-full flex flex-col">
                        <div className="bg-white border-b px-4 py-2 flex gap-2">
                            {sheets.map((sheet) => (
                                <button
                                    key={sheet.id}
                                    onClick={() => setActiveSheet(sheet.id)}
                                    className={`px-3 py-1 text-sm rounded ${activeSheet === sheet.id
                                            ? 'bg-primary-100 text-primary-700'
                                            : 'text-gray-600 hover:bg-gray-100'
                                        }`}
                                >
                                    {sheet.name}
                                </button>
                            ))}
                        </div>
                        <SpreadsheetGrid
                            cells={cells}
                            pendingChanges={pendingChanges}
                            onCellChange={handleCellChange}
                            onCommit={handleCommit}
                        />
                    </div>
                )}
                {activeTab === 'history' && (
                    <CommitHistory
                        spreadsheetId={id!}
                        branchId={branchId!}
                        branch={activeBranch}
                        onRevert={loadCells}
                    />
                )}
                {activeTab === 'audit' && <AuditLog spreadsheetId={id!} />}
                {activeTab === 'diff' && <DiffViewer spreadsheetId={id!} branch={activeBranch} />}
            </main>
        </div>
    );
}
