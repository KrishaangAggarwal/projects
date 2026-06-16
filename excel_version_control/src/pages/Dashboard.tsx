import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../lib/auth';
import { api } from '../lib/api';

export default function Dashboard() {
    const { user, logout } = useAuth();
    const [spreadsheets, setSpreadsheets] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        loadSpreadsheets();
    }, []);

    const loadSpreadsheets = async () => {
        try {
            const { spreadsheets } = await api.spreadsheets.list();
            setSpreadsheets(spreadsheets);
        } catch (err) {
            console.error('Failed to load spreadsheets:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setUploading(true);
        try {
            await api.spreadsheets.upload(file);
            await loadSpreadsheets();
        } catch (err: any) {
            alert(err.message);
        } finally {
            setUploading(false);
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    return (
        <div className="min-h-screen bg-gray-50">
            <header className="bg-white shadow-sm">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
                    <h1 className="text-xl font-semibold text-gray-900">SheetVC</h1>
                    <div className="flex items-center gap-4">
                        <span className="text-sm text-gray-600">{user?.name}</span>
                        <button
                            onClick={logout}
                            className="text-sm text-gray-500 hover:text-gray-700"
                        >
                            Sign out
                        </button>
                    </div>
                </div>
            </header>

            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <div className="flex justify-between items-center mb-6">
                    <h2 className="text-lg font-medium text-gray-900">Your Spreadsheets</h2>
                    <div>
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept=".xlsx,.xls"
                            onChange={handleUpload}
                            className="hidden"
                            id="file-upload"
                        />
                        <label
                            htmlFor="file-upload"
                            className="cursor-pointer inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700"
                        >
                            {uploading ? 'Uploading...' : 'Upload Excel File'}
                        </label>
                    </div>
                </div>

                {loading ? (
                    <div className="text-center py-12">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto"></div>
                    </div>
                ) : spreadsheets.length === 0 ? (
                    <div className="text-center py-12 bg-white rounded-lg shadow">
                        <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        <h3 className="mt-2 text-sm font-medium text-gray-900">No spreadsheets</h3>
                        <p className="mt-1 text-sm text-gray-500">Upload an Excel file to get started.</p>
                    </div>
                ) : (
                    <div className="bg-white shadow overflow-hidden sm:rounded-md">
                        <ul className="divide-y divide-gray-200">
                            {spreadsheets.map((sheet) => (
                                <li key={sheet.id}>
                                    <Link
                                        to={`/spreadsheet/${sheet.id}`}
                                        className="block hover:bg-gray-50 px-4 py-4 sm:px-6"
                                    >
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center">
                                                <svg className="h-5 w-5 text-green-500 mr-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                                </svg>
                                                <p className="text-sm font-medium text-primary-600 truncate">{sheet.name}</p>
                                            </div>
                                            <div className="flex items-center text-sm text-gray-500">
                                                <span className="px-2 py-1 text-xs rounded-full bg-gray-100">
                                                    {sheet.sourceType === 'excel' ? 'Excel' : 'Google Sheets'}
                                                </span>
                                            </div>
                                        </div>
                                        <div className="mt-2 text-sm text-gray-500">
                                            Updated {new Date(sheet.updatedAt).toLocaleDateString()}
                                        </div>
                                    </Link>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </main>
        </div>
    );
}
