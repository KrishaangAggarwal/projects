import { Hono } from 'hono';
import { zValidator } from '@hono/zod-validator';
import { z } from 'zod';
import { query, run, get } from '../db/index.js';
import { generateId, generateHash } from '../lib/auth.js';

const revertRouter = new Hono();

const revertSchema = z.object({
    commitId: z.string(),
    branchId: z.string(),
});

revertRouter.post('/:spreadsheetId/revert', zValidator('json', revertSchema), async (c) => {
    const userId = c.get('userId');
    if (!userId) return c.json({ error: 'Unauthorized' }, 401);

    const { spreadsheetId } = c.req.param();
    const { commitId, branchId } = c.req.valid('json');

    const targetCommit = get<any>('SELECT * FROM commits WHERE id = ?', [commitId]);
    if (!targetCommit) {
        return c.json({ error: 'Commit not found' }, 404);
    }

    const changes = query('SELECT * FROM cell_changes WHERE commit_id = ?', [commitId]);

    const reverseChanges = changes.map(change => ({
        sheetId: change.sheet_id,
        row: change.row,
        column: change.col,
        oldValue: change.new_value,
        newValue: change.old_value,
    }));

    const branch = get<any>('SELECT * FROM branches WHERE id = ?', [branchId]);
    if (!branch) {
        return c.json({ error: 'Branch not found' }, 404);
    }

    const newCommitId = generateId();
    const now = Date.now();

    run(
        'INSERT INTO commits (id, spreadsheet_id, branch_id, parent_commit_id, author_id, message, hash, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        [newCommitId, spreadsheetId, branchId, branch.head_commit_id, userId, `Revert "${targetCommit.message}"`, generateHash(JSON.stringify(reverseChanges)), now]
    );

    for (const change of reverseChanges) {
        run(
            'INSERT INTO cell_changes (id, commit_id, sheet_id, row, col, old_value, new_value) VALUES (?, ?, ?, ?, ?, ?, ?)',
            [generateId(), newCommitId, change.sheetId, change.row, change.column, change.oldValue, change.newValue]
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

    run('UPDATE branches SET head_commit_id = ? WHERE id = ?', [newCommitId, branchId]);

    return c.json({ reverted: true, commitId: newCommitId });
});

const restoreSchema = z.object({
    commitId: z.string(),
    branchId: z.string(),
});

revertRouter.post('/:spreadsheetId/restore', zValidator('json', restoreSchema), async (c) => {
    const userId = c.get('userId');
    if (!userId) return c.json({ error: 'Unauthorized' }, 401);

    const { spreadsheetId } = c.req.param();
    const { commitId, branchId } = c.req.valid('json');

    const targetCommit = get<any>('SELECT * FROM commits WHERE id = ?', [commitId]);
    if (!targetCommit) {
        return c.json({ error: 'Commit not found' }, 404);
    }

    const commitsToReplay = query(
        'SELECT * FROM commits WHERE branch_id = ? AND timestamp <= ? ORDER BY timestamp',
        [branchId, targetCommit.timestamp]
    );

    const cellState = new Map<string, string | null>();

    for (const commit of commitsToReplay) {
        const changes = query('SELECT * FROM cell_changes WHERE commit_id = ?', [commit.id]);
        for (const change of changes) {
            const key = `${change.sheet_id},${change.row},${change.col}`;
            cellState.set(key, change.new_value);
        }
    }

    const currentCells = query('SELECT * FROM cell_snapshots WHERE branch_id = ?', [branchId]);
    const currentState = new Map(currentCells.map(c => [`${c.sheet_id},${c.row},${c.col}`, c]));

    const changes: any[] = [];

    for (const [key, newValue] of cellState) {
        const [sheetId, row, column] = key.split(',');
        const current = currentState.get(key);
        const oldValue = current?.value ?? null;
        if (oldValue !== newValue) {
            changes.push({ sheetId, row: parseInt(row), column: parseInt(column), oldValue, newValue });
        }
    }

    for (const [key, current] of currentState) {
        if (!cellState.has(key)) {
            const [sheetId, row, column] = key.split(',');
            changes.push({ sheetId, row: parseInt(row), column: parseInt(column), oldValue: current.value, newValue: null });
        }
    }

    if (changes.length === 0) {
        return c.json({ message: 'Already at this state' });
    }

    const branch = get<any>('SELECT * FROM branches WHERE id = ?', [branchId]);
    const newCommitId = generateId();
    const now = Date.now();

    run(
        'INSERT INTO commits (id, spreadsheet_id, branch_id, parent_commit_id, author_id, message, hash, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        [newCommitId, spreadsheetId, branchId, branch?.head_commit_id, userId, `Restore to "${targetCommit.message}"`, generateHash(JSON.stringify(changes)), now]
    );

    for (const change of changes) {
        run(
            'INSERT INTO cell_changes (id, commit_id, sheet_id, row, col, old_value, new_value) VALUES (?, ?, ?, ?, ?, ?, ?)',
            [generateId(), newCommitId, change.sheetId, change.row, change.column, change.oldValue, change.newValue]
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

    run('UPDATE branches SET head_commit_id = ? WHERE id = ?', [newCommitId, branchId]);

    return c.json({ restored: true, commitId: newCommitId, changesCount: changes.length });
});

export default revertRouter;
