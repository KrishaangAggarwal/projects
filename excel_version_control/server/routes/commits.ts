import { Hono } from 'hono';
import { zValidator } from '@hono/zod-validator';
import { z } from 'zod';
import { query, run, get } from '../db/index.js';
import { generateId, generateHash } from '../lib/auth.js';

const commitsRouter = new Hono();

const commitSchema = z.object({
    branchId: z.string(),
    message: z.string().min(1),
    changes: z.array(z.object({
        sheetId: z.string(),
        row: z.number(),
        column: z.number(),
        oldValue: z.string().nullable(),
        newValue: z.string().nullable(),
    })),
});

commitsRouter.get('/:spreadsheetId/commits', async (c) => {
    const userId = c.get('userId');
    if (!userId) return c.json({ error: 'Unauthorized' }, 401);

    const { spreadsheetId } = c.req.param();
    const branchName = c.req.query('branch') || 'main';

    const branch = get<any>(
        'SELECT * FROM branches WHERE spreadsheet_id = ? AND name = ?',
        [spreadsheetId, branchName]
    );

    if (!branch) {
        return c.json({ error: 'Branch not found' }, 404);
    }

    const commitList = query(
        `SELECT c.*, u.name as author_name, u.email as author_email 
     FROM commits c 
     LEFT JOIN users u ON c.author_id = u.id 
     WHERE c.branch_id = ? 
     ORDER BY c.timestamp DESC`,
        [branch.id]
    );

    return c.json({
        commits: commitList.map(c => ({
            id: c.id,
            message: c.message,
            hash: c.hash,
            timestamp: new Date(c.timestamp),
            authorId: c.author_id,
            authorName: c.author_name,
            authorEmail: c.author_email,
        }))
    });
});

commitsRouter.post('/:spreadsheetId/commits', zValidator('json', commitSchema), async (c) => {
    const userId = c.get('userId');
    if (!userId) return c.json({ error: 'Unauthorized' }, 401);

    const { spreadsheetId } = c.req.param();
    const { branchId, message, changes } = c.req.valid('json');

    const branch = get<any>('SELECT * FROM branches WHERE id = ?', [branchId]);
    if (!branch) {
        return c.json({ error: 'Branch not found' }, 404);
    }

    const commitId = generateId();
    const now = Date.now();
    const hashData = JSON.stringify({ changes, timestamp: now });

    run(
        'INSERT INTO commits (id, spreadsheet_id, branch_id, parent_commit_id, author_id, message, hash, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        [commitId, spreadsheetId, branchId, branch.head_commit_id, userId, message, generateHash(hashData), now]
    );

    for (const change of changes) {
        run(
            'INSERT INTO cell_changes (id, commit_id, sheet_id, row, col, old_value, new_value) VALUES (?, ?, ?, ?, ?, ?, ?)',
            [generateId(), commitId, change.sheetId, change.row, change.column, change.oldValue, change.newValue]
        );

        const existing = get<any>(
            'SELECT * FROM cell_snapshots WHERE sheet_id = ? AND branch_id = ? AND row = ? AND col = ?',
            [change.sheetId, branchId, change.row, change.column]
        );

        if (existing) {
            if (change.newValue === null) {
                run('DELETE FROM cell_snapshots WHERE id = ?', [existing.id]);
            } else {
                run('UPDATE cell_snapshots SET value = ? WHERE id = ?', [change.newValue, existing.id]);
            }
        } else if (change.newValue !== null) {
            run(
                'INSERT INTO cell_snapshots (id, sheet_id, branch_id, row, col, value) VALUES (?, ?, ?, ?, ?, ?)',
                [generateId(), change.sheetId, branchId, change.row, change.column, change.newValue]
            );
        }
    }

    run('UPDATE branches SET head_commit_id = ? WHERE id = ?', [commitId, branchId]);

    return c.json({ commit: { id: commitId, message, hash: generateHash(hashData) } });
});

commitsRouter.get('/:spreadsheetId/commits/:commitId/changes', async (c) => {
    const userId = c.get('userId');
    if (!userId) return c.json({ error: 'Unauthorized' }, 401);

    const { commitId } = c.req.param();

    const changes = query('SELECT * FROM cell_changes WHERE commit_id = ?', [commitId]);

    return c.json({
        changes: changes.map(ch => ({
            sheetId: ch.sheet_id,
            row: ch.row,
            column: ch.col,
            oldValue: ch.old_value,
            newValue: ch.new_value,
        }))
    });
});

export default commitsRouter;
