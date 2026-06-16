import { Hono } from 'hono';
import { query, run, get } from '../db/index.js';
import { generateId, generateHash } from '../lib/auth.js';
import { parseExcelBuffer } from '../lib/excel.js';

const spreadsheetsRouter = new Hono();

spreadsheetsRouter.get('/', async (c) => {
    const userId = c.get('userId');
    if (!userId) return c.json({ error: 'Unauthorized' }, 401);

    const spreadsheets = query(
        'SELECT * FROM spreadsheets WHERE owner_id = ? ORDER BY updated_at DESC',
        [userId]
    );

    return c.json({
        spreadsheets: spreadsheets.map(s => ({
            id: s.id,
            name: s.name,
            sourceType: s.source_type,
            createdAt: new Date(s.created_at),
            updatedAt: new Date(s.updated_at),
        }))
    });
});

spreadsheetsRouter.post('/upload', async (c) => {
    const userId = c.get('userId');
    if (!userId) return c.json({ error: 'Unauthorized' }, 401);

    const formData = await c.req.formData();
    const file = formData.get('file') as File;
    const name = (formData.get('name') as string) || file.name;

    if (!file) {
        return c.json({ error: 'No file provided' }, 400);
    }

    const buffer = Buffer.from(await file.arrayBuffer());
    const parsed = parseExcelBuffer(buffer);

    const spreadsheetId = generateId();
    const branchId = generateId();
    const commitId = generateId();
    const now = Date.now();

    run(
        'INSERT INTO spreadsheets (id, name, source_type, owner_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
        [spreadsheetId, name, 'excel', userId, now, now]
    );

    run(
        'INSERT INTO branches (id, spreadsheet_id, name, created_at, created_by_id) VALUES (?, ?, ?, ?, ?)',
        [branchId, spreadsheetId, 'main', now, userId]
    );

    const sheetIds: string[] = [];
    for (let i = 0; i < parsed.sheets.length; i++) {
        const sheetId = generateId();
        sheetIds.push(sheetId);
        run(
            'INSERT INTO sheets (id, spreadsheet_id, name, idx) VALUES (?, ?, ?, ?)',
            [sheetId, spreadsheetId, parsed.sheets[i].name, i]
        );
    }

    const allChanges: { sheetId: string; row: number; column: number; value: string }[] = [];
    for (let i = 0; i < parsed.sheets.length; i++) {
        for (const cell of parsed.sheets[i].cells) {
            allChanges.push({ sheetId: sheetIds[i], ...cell });
        }
    }

    const hashData = JSON.stringify(allChanges);
    run(
        'INSERT INTO commits (id, spreadsheet_id, branch_id, author_id, message, hash, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)',
        [commitId, spreadsheetId, branchId, userId, 'Initial import', generateHash(hashData), now]
    );

    run('UPDATE branches SET head_commit_id = ? WHERE id = ?', [commitId, branchId]);

    for (const change of allChanges) {
        run(
            'INSERT INTO cell_changes (id, commit_id, sheet_id, row, col, old_value, new_value) VALUES (?, ?, ?, ?, ?, ?, ?)',
            [generateId(), commitId, change.sheetId, change.row, change.column, null, change.value]
        );

        run(
            'INSERT INTO cell_snapshots (id, sheet_id, branch_id, row, col, value) VALUES (?, ?, ?, ?, ?, ?)',
            [generateId(), change.sheetId, branchId, change.row, change.column, change.value]
        );
    }

    run(
        'INSERT INTO permissions (id, spreadsheet_id, user_id, role) VALUES (?, ?, ?, ?)',
        [generateId(), spreadsheetId, userId, 'owner']
    );

    return c.json({ spreadsheet: { id: spreadsheetId, name } });
});

export default spreadsheetsRouter;
