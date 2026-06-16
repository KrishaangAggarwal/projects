import { useState, useEffect } from 'react';
import { api } from '../lib/api';

interface Props {
    spreadsheetId: string;
    branch: string;
}

export default function DiffViewer({ spreadsheetId, branch }: Props) {
    const [commits, setCommits] = useState<any[]>([]);
    const [fromCommit, setFromCommit] = useState('');
    const [toCommit, setToCommit] = useState('');
    const [diff, setDiff] = useState<any | null>(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        loadCommits();
    }, [spreadsheetId, branch]);

    const loadCommits = async () => {
        try {
            const { commits } = await api.commits.list(spreadsheetId, branch);
            setCommits(commits);
            if (commits.length >= 2) {
                setFromCommit(commits[1].id);
                setToCommit(commits[0].id);
            }
        } catch (err) {
            console.error('Failed to load commits:', err);
        }
    };

    const loadDiff = async () => {
        if (!fromCommit || !toCommit) return;
        setLoading(true);
        try {
            const diff = await api.diff.get(spreadsheetId, fromCommit, toCommit);
            setDiff(diff);
        } catch (err: any) {
            alert(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (fromCommit && toCommit) {
            loadDiff();
        }
    }, [fromCommit, toCommit]);

    return (
        <div className="p-4 max-w-6xl mx-auto">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Compare Versions</h2>

            <div className="bg-white rounded-lg shadow p-4 mb-4">
                <div className="flex gap-4 items-end">
                    <div className="flex-1">
                        <label className="block text-sm font-medium text-gray-700 mb-1">From</label>
                        <select
                            value={fromCommit}
                            onChange={(e) => setFromCommit(e.target.value)}
                            className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500"
                        >
                            <option value="">Select commit...</option>
                            {commits.map((c) => (
                                <option key={c.id} value={c.id}>
                                    {c.message} ({c.hash.slice(0, 7)})
                                </option>
                            ))}
                        </select>
                    </div>
                    <div className="flex-1">
                        <label className="block text-sm font-medium text-gray-700 mb-1">To</label>
                        <select
                            value={toCommit}
                            onChange={(e) => setToCommit(e.target.value)}
                            className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary-500"
                        >
                            <option value="">Select commit...</option>
                            {commits.map((c) => (
                                <option key={c.id} value={c.id}>
                                    {c.message} ({c.hash.slice(0, 7)})
                                </option>
                            ))}
                        </select>
                    </div>
                </div>
            </div>

            {loading && (
                <div className="flex items-center justify-center h-32">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
                </div>
            )}

            {diff && !loading && (
                <div className="bg-white rounded-lg shadow">
                    <div className="p-4 border-b">
                        <div className="flex justify-between items-center">
                            <div>
                                <span className="text-sm text-gray-500">Comparing:</span>
                                <span className="ml-2 font-medium">{diff.from.message}</span>
                                <span className="mx-2 text-gray-400">→</span>
                                <span className="font-medium">{diff.to.message}</span>
                            </div>
                            <div className="flex gap-4 text-sm">
                                <span className="text-green-600">+{diff.summary.added} added</span>
                                <span className="text-red-600">-{diff.summary.removed} removed</span>
                                <span className="text-yellow-600">~{diff.summary.changed} changed</span>
                            </div>
                        </div>
                    </div>

                    {diff.diffs.length === 0 ? (
                        <div className="p-8 text-center text-gray-500">No differences found</div>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="min-w-full divide-y divide-gray-200">
                                <thead className="bg-gray-50">
                                    <tr>
                                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Sheet</th>
                                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Cell</th>
                                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Old Value</th>
                                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">New Value</th>
                                    </tr>
                                </thead>
                                <tbody className="bg-white divide-y divide-gray-200">
                                    {diff.diffs.map((d: any, i: number) => (
                                        <tr
                                            key={i}
                                            className={
                                                d.type === 'added'
                                                    ? 'bg-green-50'
                                                    : d.type === 'removed'
                                                        ? 'bg-red-50'
                                                        : 'bg-yellow-50'
                                            }
                                        >
                                            <td className="px-4 py-2 text-sm text-gray-600">{d.sheetName}</td>
                                            <td className="px-4 py-2 text-sm font-mono text-gray-900">{d.cell}</td>
                                            <td className="px-4 py-2 text-sm">
                                                <span
                                                    className={`px-2 py-0.5 rounded text-xs font-medium ${d.type === 'added'
                                                            ? 'bg-green-100 text-green-800'
                                                            : d.type === 'removed'
                                                                ? 'bg-red-100 text-red-800'
                                                                : 'bg-yellow-100 text-yellow-800'
                                                        }`}
                                                >
                                                    {d.type}
                                                </span>
                                            </td>
                                            <td className="px-4 py-2 text-sm text-red-600 max-w-xs truncate">
                                                {d.oldValue || '(empty)'}
                                            </td>
                                            <td className="px-4 py-2 text-sm text-green-600 max-w-xs truncate">
                                                {d.newValue || '(empty)'}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
