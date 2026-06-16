import { Hono } from 'hono';
import { query } from '../db/index.js';
import { columnToLetter } from '../lib/excel.js';

const auditRouter = new Hono();

auditRouter.get('/:spreadsheetId/audit', async (c) => {
    const userId = c.get('userId');
    if (!userId) return c.json({ error: 'Unauthorized' }, 401);

    const { spreadsheetId } = c.req.param();

    const commitList = query(
        `SELECT c.*, u.name as author_name, u.email as author_email 
     FROM commits c 
     LEFT JOIN users u ON c.author_id = u.id 
     WHERE c.spreadsheet_id = ? 
     ORDER BY c.timestamp DESC`,
        [spreadsheetId]
    );

    const auditEntries = [];

    for (const commit of commitList) {
        const changes = query(
            `SELECT cc.*, s.name as sheet_name 
       FROM cell_changes cc 
       LEFT JOIN sheets s ON cc.sheet_id = s.id 
       WHERE cc.commit_id = ?`,
            [commit.id]
        );

        for (const change of changes) {
            auditEntries.push({
                timestamp: new Date(commit.timestamp),
                author: commit.author_name,
                email: commit.author_email,
                message: commit.message,
                hash: commit.hash,
                sheet: change.sheet_name,
                cell: `${columnToLetter(change.col)}${change.row + 1}`,
                row: change.row,
                column: change.col,
                oldValue: change.old_value,
                newValue: change.new_value,
            });
        }
    }

    return c.json({ audit: auditEntries });
});

auditRouter.get('/:spreadsheetId/audit/export', async (c) => {
    const userId = c.get('userId');
    if (!userId) return c.json({ error: 'Unauthorized' }, 401);

    const { spreadsheetId } = c.req.param();
    const format = c.req.query('format') || 'csv';

    const commitList = query(
        `SELECT c.*, u.name as author_name, u.email as author_email 
     FROM commits c 
     LEFT JOIN users u ON c.author_id = u.id 
     WHERE c.spreadsheet_id = ? 
     ORDER BY c.timestamp DESC`,
        [spreadsheetId]
    );

    const rows: string[][] = [['Timestamp', 'Author', 'Email', 'Message', 'Hash', 'Sheet', 'Cell', 'Old Value', 'New Value']];

    for (const commit of commitList) {
        const changes = query(
            `SELECT cc.*, s.name as sheet_name 
       FROM cell_changes cc 
       LEFT JOIN sheets s ON cc.sheet_id = s.id 
       WHERE cc.commit_id = ?`,
            [commit.id]
        );

        for (const change of changes) {
            rows.push([
                new Date(commit.timestamp).toISOString(),
                commit.author_name || '',
                commit.author_email || '',
                commit.message,
                commit.hash,
                change.sheet_name || '',
                `${columnToLetter(change.col)}${change.row + 1}`,
                change.old_value || '',
                change.new_value || '',
            ]);
        }
    }

    if (format === 'csv') {
        const csv = rows.map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',')).join('\n');
        c.header('Content-Type', 'text/csv');
        c.header('Content-Disposition', 'attachment; filename="audit-log.csv"');
        return c.body(csv);
    }

    return c.json({ rows });
});

export default auditRouter;
