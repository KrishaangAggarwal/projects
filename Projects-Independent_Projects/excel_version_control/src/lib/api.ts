const API_BASE = '/api';

function getToken(): string | null {
    return localStorage.getItem('token');
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const token = getToken();
    const headers: Record<string, string> = {
        ...(options.headers as Record<string, string>),
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    if (!(options.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
    }

    const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

    if (!res.ok) {
        const error = await res.json().catch(() => ({ error: 'Request failed' }));
        throw new Error(error.error || 'Request failed');
    }

    return res.json();
}

export const api = {
    auth: {
        login: (email: string, password: string) =>
            request<{ token: string; user: { id: string; email: string; name: string } }>('/auth/login', {
                method: 'POST',
                body: JSON.stringify({ email, password }),
            }),
        register: (email: string, password: string, name: string) =>
            request<{ token: string; user: { id: string; email: string; name: string } }>('/auth/register', {
                method: 'POST',
                body: JSON.stringify({ email, password, name }),
            }),
        me: () => request<{ user: { id: string; email: string; name: string } }>('/auth/me'),
    },
    spreadsheets: {
        list: () => request<{ spreadsheets: any[] }>('/spreadsheets'),
        upload: (file: File, name?: string) => {
            const formData = new FormData();
            formData.append('file', file);
            if (name) formData.append('name', name);
            return request<{ spreadsheet: { id: string; name: string } }>('/spreadsheets/upload', {
                method: 'POST',
                body: formData,
            });
        },
    },
    sheets: {
        list: (spreadsheetId: string) => request<{ sheets: any[] }>(`/spreadsheets/${spreadsheetId}/sheets`),
        getCells: (spreadsheetId: string, sheetId: string, branch?: string) =>
            request<{ cells: any[]; branchId: string }>(`/spreadsheets/${spreadsheetId}/sheets/${sheetId}/cells${branch ? `?branch=${branch}` : ''}`),
    },
    commits: {
        list: (spreadsheetId: string, branch?: string) =>
            request<{ commits: any[] }>(`/spreadsheets/${spreadsheetId}/commits${branch ? `?branch=${branch}` : ''}`),
        create: (spreadsheetId: string, branchId: string, message: string, changes: any[]) =>
            request<{ commit: any }>(`/spreadsheets/${spreadsheetId}/commits`, {
                method: 'POST',
                body: JSON.stringify({ branchId, message, changes }),
            }),
        getChanges: (spreadsheetId: string, commitId: string) =>
            request<{ changes: any[] }>(`/spreadsheets/${spreadsheetId}/commits/${commitId}/changes`),
    },
    branches: {
        list: (spreadsheetId: string) => request<{ branches: any[] }>(`/spreadsheets/${spreadsheetId}/branches`),
        create: (spreadsheetId: string, name: string, fromBranch?: string) =>
            request<{ branch: any }>(`/spreadsheets/${spreadsheetId}/branches`, {
                method: 'POST',
                body: JSON.stringify({ name, fromBranch }),
            }),
        merge: (spreadsheetId: string, sourceBranch: string, targetBranch: string, message?: string) =>
            request<{ merged?: boolean; conflicts?: any[]; hasConflicts: boolean }>(`/spreadsheets/${spreadsheetId}/merge`, {
                method: 'POST',
                body: JSON.stringify({ sourceBranch, targetBranch, message }),
            }),
    },
    audit: {
        get: (spreadsheetId: string) => request<{ audit: any[] }>(`/spreadsheets/${spreadsheetId}/audit`),
        export: (spreadsheetId: string, format: 'csv' | 'json' = 'csv') =>
            `${API_BASE}/spreadsheets/${spreadsheetId}/audit/export?format=${format}`,
    },
    diff: {
        get: (spreadsheetId: string, fromCommitId: string, toCommitId: string) =>
            request<{ from: any; to: any; diffs: any[]; summary: any }>(`/spreadsheets/${spreadsheetId}/diff?from=${fromCommitId}&to=${toCommitId}`),
    },
    revert: {
        revert: (spreadsheetId: string, commitId: string, branchId: string) =>
            request<{ reverted: boolean; commitId: string }>(`/spreadsheets/${spreadsheetId}/revert`, {
                method: 'POST',
                body: JSON.stringify({ commitId, branchId }),
            }),
        restore: (spreadsheetId: string, commitId: string, branchId: string) =>
            request<{ restored: boolean; commitId: string }>(`/spreadsheets/${spreadsheetId}/restore`, {
                method: 'POST',
                body: JSON.stringify({ commitId, branchId }),
            }),
    },
};
