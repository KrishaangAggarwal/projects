import { useState } from 'react';

interface Props {
    branches: any[];
    activeBranch: string;
    onBranchChange: (branch: string) => void;
    onCreateBranch: (name: string) => void;
    onMerge: (source: string, target: string) => void;
}

export default function BranchSelector({
    branches,
    activeBranch,
    onBranchChange,
    onCreateBranch,
    onMerge,
}: Props) {
    const [showCreate, setShowCreate] = useState(false);
    const [showMerge, setShowMerge] = useState(false);
    const [newBranchName, setNewBranchName] = useState('');
    const [mergeSource, setMergeSource] = useState('');
    const [mergeTarget, setMergeTarget] = useState('main');

    const handleCreate = () => {
        if (!newBranchName.trim()) return;
        onCreateBranch(newBranchName.trim());
        setNewBranchName('');
        setShowCreate(false);
    };

    const handleMerge = () => {
        if (!mergeSource || !mergeTarget) return;
        onMerge(mergeSource, mergeTarget);
        setShowMerge(false);
    };

    return (
        <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
                <svg className="w-4 h-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                <select
                    value={activeBranch}
                    onChange={(e) => onBranchChange(e.target.value)}
                    className="border rounded px-3 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500"
                >
                    {branches.map((b) => (
                        <option key={b.id} value={b.name}>
                            {b.name}
                        </option>
                    ))}
                </select>
            </div>

            <div className="relative">
                <button
                    onClick={() => setShowCreate(!showCreate)}
                    className="px-3 py-1 text-sm text-gray-600 border rounded hover:bg-gray-50"
                >
                    New Branch
                </button>
                {showCreate && (
                    <div className="absolute right-0 mt-2 w-64 bg-white rounded-lg shadow-lg border p-3 z-20">
                        <input
                            type="text"
                            placeholder="Branch name..."
                            value={newBranchName}
                            onChange={(e) => setNewBranchName(e.target.value)}
                            className="w-full border rounded px-3 py-1 text-sm mb-2 focus:outline-none focus:ring-1 focus:ring-primary-500"
                            autoFocus
                        />
                        <div className="flex justify-end gap-2">
                            <button
                                onClick={() => setShowCreate(false)}
                                className="px-3 py-1 text-sm text-gray-500 hover:text-gray-700"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleCreate}
                                disabled={!newBranchName.trim()}
                                className="px-3 py-1 text-sm bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
                            >
                                Create
                            </button>
                        </div>
                    </div>
                )}
            </div>

            {branches.length > 1 && (
                <div className="relative">
                    <button
                        onClick={() => setShowMerge(!showMerge)}
                        className="px-3 py-1 text-sm text-gray-600 border rounded hover:bg-gray-50"
                    >
                        Merge
                    </button>
                    {showMerge && (
                        <div className="absolute right-0 mt-2 w-72 bg-white rounded-lg shadow-lg border p-3 z-20">
                            <div className="mb-3">
                                <label className="block text-xs text-gray-500 mb-1">Merge from</label>
                                <select
                                    value={mergeSource}
                                    onChange={(e) => setMergeSource(e.target.value)}
                                    className="w-full border rounded px-3 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500"
                                >
                                    <option value="">Select branch...</option>
                                    {branches.filter(b => b.name !== mergeTarget).map((b) => (
                                        <option key={b.id} value={b.name}>
                                            {b.name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div className="mb-3">
                                <label className="block text-xs text-gray-500 mb-1">Into</label>
                                <select
                                    value={mergeTarget}
                                    onChange={(e) => setMergeTarget(e.target.value)}
                                    className="w-full border rounded px-3 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500"
                                >
                                    {branches.filter(b => b.name !== mergeSource).map((b) => (
                                        <option key={b.id} value={b.name}>
                                            {b.name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div className="flex justify-end gap-2">
                                <button
                                    onClick={() => setShowMerge(false)}
                                    className="px-3 py-1 text-sm text-gray-500 hover:text-gray-700"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleMerge}
                                    disabled={!mergeSource || !mergeTarget}
                                    className="px-3 py-1 text-sm bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
                                >
                                    Merge
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
