import { useState, useEffect } from 'react';
import { api } from '../lib/api';

interface Props {
    spreadsheetId: string;
    branchId: string;
    branch: string;
    onRevert: () => void;
}

export default function CommitHistory({ spreadsheetId, branchId, branch, onRevert }: Props) {
    const [commits, setCommits] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [expandedCommit, setExpandedCommit] = useState<string | null>(null);
    const [changes, setChanges] = useState<any[]>([]);

    useEffect(() => {
        loadCommits();
    }, [spreadsheetId, branch]);

    const loadCommits = async () => {
        try {
            const { commits } = await api.commits.list(spreadsheetId, branch);
            setCommits(commits);
        } catch (err) {
            console.error('Failed to load commits:', err);
        } finally {
            setLoading(false);
        }
    };

    const loadChanges = async (commitId: string) => {
        if (expandedCommit === commitId) {
            setExpandedCommit(null);
            return;
        }
        try {
            const { changes } = await api.commits.getChanges(spreadsheetId, commitId);
            setChanges(changes);
            setExpandedCommit(commitId);
        } catch (err) {
            console.error('Failed to load changes:', err);
        }
    };

    const handleRevert = async (commitId: string) => {
        if (!confirm('Are you sure you want to revert this commit?')) return;
        try {
            await api.revert.revert(spreadsheetId, commitId, branchId);
            await loadCommits();
            onRevert();
        } catch (err: any) {
            alert(err.message);
        }
    };

    const handleRestore = async (commitId: string) => {
        if (!confirm('Are you sure you want to restore to this version?')) return;
        try {
            await api.revert.restore(spreadsheetId, commitId, branchId);
            await loadCommits();
            onRevert();
        } catch (err: any) {
            alert(err.message);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
            </div>
        );
    }

    return (
        <div className="p-4 max-w-4xl mx-auto">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Commit History</h2>

            {commits.length === 0 ? (
                <p className="text-gray-500">No commits yet.</p>
            ) : (
                <div className="space-y-3">
                    {commits.map((commit, index) => (
                        <div key={commit.id} className="bg-white rounded-lg shadow border">
                            <div
                                className="p-4 cursor-pointer hover:bg-gray-50"
                                onClick={() => loadChanges(commit.id)}
                            >
                                <div className="flex items-start justify-between">
                                    <div className="flex-1">
                                        <p className="font-medium text-gray-900">{commit.message}</p>
                                        <div className="mt-1 flex items-center gap-3 text-sm text-gray-500">
                                            <span>{commit.authorName}</span>
                                            <span>•</span>
                                            <span>{new Date(commit.timestamp).toLocaleString()}</span>
                                            <span>•</span>
                                            <code className="text-xs bg-gray-100 px-1 rounded">{commit.hash.slice(0, 7)}</code>
                                        </div>
                                    </div>
                                    <div className="flex gap-2">
                                        {index > 0 && (
                                            <>
                                                <button
                                                    onClick={(e) => { e.stopPropagation(); handleRevert(commit.id); }}
                                                    className="px-3 py-1 text-xs text-red-600 border border-red-200 rounded hover:bg-red-50"
                                                >
                                                    Revert
                                                </button>
                                                <button
                                                    onClick={(e) => { e.stopPropagation(); handleRestore(commit.id); }}
                                                    className="px-3 py-1 text-xs text-primary-600 border border-primary-200 rounded hover:bg-primary-50"
                                                >
                                                    Restore
                                                </button>
                                            </>
                                        )}
                                    </div>
                                </div>
                            </div>

                            {expandedCommit === commit.id && (
                                <div className="border-t px-4 py-3 bg-gray-50">
                                    <p className="text-sm font-medium text-gray-700 mb-2">Changes ({changes.length})</p>
                                    <div className="max-h-64 overflow-auto">
                                        <table className="w-full text-sm">
                                            <thead>
                                                <tr className="text-left text-gray-500">
                                                    <th className="pb-2">Cell</th>
                                                    <th className="pb-2">Old Value</th>
                                                    <th className="pb-2">New Value</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {changes.slice(0, 50).map((change, i) => (
                                                    <tr key={i} className="border-t border-gray-200">
                                                        <td className="py-1 font-mono text-xs">
                                                            {String.fromCharCode(65 + change.column)}{change.row + 1}
                                                        </td>
                                                        <td className="py-1 text-red-600">{change.oldValue || '(empty)'}</td>
                                                        <td className="py-1 text-green-600">{change.newValue || '(empty)'}</td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                        {changes.length > 50 && (
                                            <p className="text-xs text-gray-500 mt-2">
                                                Showing 50 of {changes.length} changes
                                            </p>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
