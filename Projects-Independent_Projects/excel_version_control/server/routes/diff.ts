import { Hono } from 'hono';
import { query, get } from '../db/index.js';
import { columnToLetter } from '../lib/excel.js';

const diffRouter = new Hono();

diffRouter.get('/:spreadsheetId/diff', async (c) => {
    const userId = c.get('userId');
    if (!userId) return c.json({ error: 'Unauthorized' }, 401);

    const { spreadsheetId } = c.req.param();
    const fromCommitId = c.req.query('from');
    const toCommitId = c.req.query('to');

    if (!fromCommitId || !toCommitId) {
        return c.json({ error: 'Both from and to commit IDs required' }, 400);
    }

    const fromCommit = get<any>('SELECT * FROM commits WHERE id = ?', [fromCommitId]);
    const toCommit = get<any>('SELECT * FROM commits WHERE id = ?', [toCommitId]);

    if (!fromCommit || !toCommit) {
        return c.json({ error: 'Commit not found' }, 404);
    }

    const commitsInRange = query(
        'SELECT * FROM commits WHERE spreadsheet_id = ? AND timestamp >= ? AND timestamp <= ?',
        [spreadsheetId, fromCommit.timestamp, toCommit.timestamp]
    );

    const cellDiffs = new Map<string, any>();

    for (const commit of commitsInRange) {
        if (commit.id === fromCommitId) continue;

        const changes = query(
            `SELECT cc.*, s.name as sheet_name 
       FROM cell_changes cc 
       LEFT JOIN sheets s ON cc.sheet_id = s.id 
       WHERE cc.commit_id = ?`,
            [commit.id]
        );

        for (const change of changes) {
            const key = `${change.sheet_id},${change.row},${change.col}`;
            const existing = cellDiffs.get(key);

            if (existing) {
                existing.newValue = change.new_value;
            } else {
                cellDiffs.set(key, {
                    sheetId: change.sheet_id,
                    row: change.row,
                    column: change.col,
                    oldValue: change.old_value,
                    newValue: change.new_value,
                    sheetName: change.sheet_name,
                });
            }
        }
    }

    const diffs = Array.from(cellDiffs.values()).map(diff => ({
        ...diff,
        cell: `${columnToLetter(diff.column)}${diff.row + 1}`,
        type: diff.oldValue === null ? 'added' : diff.newValue === null ? 'removed' : 'changed',
    }));

    return c.json({
        from: { id: fromCommit.id, message: fromCommit.message, timestamp: new Date(fromCommit.timestamp) },
        to: { id: toCommit.id, message: toCommit.message, timestamp: new Date(toCommit.timestamp) },
        diffs,
        summary: {
            added: diffs.filter(d => d.type === 'added').length,
            removed: diffs.filter(d => d.type === 'removed').length,
            changed: diffs.filter(d => d.type === 'changed').length,
        },
    });
});

export default diffRouter;
