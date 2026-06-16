import { useState, useEffect } from 'react';
import { api } from '../lib/api';

interface Props {
    spreadsheetId: string;
}

export default function AuditLog({ spreadsheetId }: Props) {
    const [audit, setAudit] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('');

    useEffect(() => {
        loadAudit();
    }, [spreadsheetId]);

    const loadAudit = async () => {
        try {
            const { audit } = await api.audit.get(spreadsheetId);
            setAudit(audit);
        } catch (err) {
            console.error('Failed to load audit:', err);
        } finally {
            setLoading(false);
        }
    };

    const filteredAudit = audit.filter(entry => {
        if (!filter) return true;
        const searchLower = filter.toLowerCase();
        return (
            entry.author?.toLowerCase().includes(searchLower) ||
            entry.message?.toLowerCase().includes(searchLower) ||
            entry.cell?.toLowerCase().includes(searchLower) ||
            entry.sheet?.toLowerCase().includes(searchLower)
        );
    });

    const handleExport = () => {
        const token = localStorage.getItem('token');
        window.open(`${api.audit.export(spreadsheetId)}&token=${token}`, '_blank');
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
            </div>
        );
    }

    return (
        <div className="p-4">
            <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-medium text-gray-900">Audit Log</h2>
                <div className="flex gap-3">
                    <input
                        type="text"
                        placeholder="Filter by author, message, cell..."
                        value={filter}
                        onChange={(e) => setFilter(e.target.value)}
                        className="px-3 py-1 text-sm border rounded focus:outline-none focus:ring-1 focus:ring-primary-500"
                    />
                    <button
                        onClick={handleExport}
                        className="px-4 py-1 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
                    >
                        Export CSV
                    </button>
                </div>
            </div>

            {filteredAudit.length === 0 ? (
                <p className="text-gray-500">No audit entries found.</p>
            ) : (
                <div className="bg-white rounded-lg shadow overflow-hidden">
                    <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-gray-200">
                            <thead className="bg-gray-50">
                                <tr>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Timestamp</th>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Author</th>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Message</th>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Sheet</th>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Cell</th>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Old Value</th>
                                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">New Value</th>
                                </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-gray-200">
                                {filteredAudit.slice(0, 100).map((entry, i) => (
                                    <tr key={i} className="hover:bg-gray-50">
                                        <td className="px-4 py-2 text-sm text-gray-500 whitespace-nowrap">
                                            {new Date(entry.timestamp).toLocaleString()}
                                        </td>
                                        <td className="px-4 py-2 text-sm text-gray-900">{entry.author}</td>
                                        <td className="px-4 py-2 text-sm text-gray-600 max-w-xs truncate">{entry.message}</td>
                                        <td className="px-4 py-2 text-sm text-gray-600">{entry.sheet}</td>
                                        <td className="px-4 py-2 text-sm font-mono text-gray-900">{entry.cell}</td>
                                        <td className="px-4 py-2 text-sm text-red-600 max-w-xs truncate">
                                            {entry.oldValue || '(empty)'}
                                        </td>
                                        <td className="px-4 py-2 text-sm text-green-600 max-w-xs truncate">
                                            {entry.newValue || '(empty)'}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    {filteredAudit.length > 100 && (
                        <div className="px-4 py-2 bg-gray-50 text-sm text-gray-500">
                            Showing 100 of {filteredAudit.length} entries
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
