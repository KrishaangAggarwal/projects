import { Hono } from 'hono';
import { zValidator } from '@hono/zod-validator';
import { z } from 'zod';
import { query, run, get } from '../db/index.js';
import { generateId, generateHash } from '../lib/auth.js';

const branchesRouter = new Hono();

const createBranchSchema = z.object({
    name: z.string().min(1),
    fromBranch: z.string().optional(),
});

branchesRouter.get('/:spreadsheetId/branches', async (c) => {
    const userId = c.get('userId');
    if (!userId) return c.json({ error: 'Unauthorized' }, 401);

    const { spreadsheetId } = c.req.param();

    const branchList = query(
        'SELECT * FROM branches WHERE spreadsheet_id = ?',
        [spreadsheetId]
    );

    return c.json({
        branches: branchList.map(b => ({
            id: b.id,
            spreadsheetId: b.spreadsheet_id,
            name: b.name,
            headCommitId: b.head_commit_id,
            createdAt: new Date(b.created_at),
        }))
    });
});

branchesRouter.post('/:spreadsheetId/branches', zValidator('json', createBranchSchema), async (c) => {
    const userId = c.get('userId');
    if (!userId) return c.json({ error: 'Unauthorized' }, 401);

    const { spreadsheetId } = c.req.param();
    const { name, fromBranch = 'main' } = c.req.valid('json');

    const sourceBranch = get<any>(
        'SELECT * FROM branches WHERE spreadsheet_id = ? AND name = ?',
        [spreadsheetId, fromBranch]
    );

    if (!sourceBranch) {
        return c.json({ error: 'Source branch not found' }, 404);
    }

    const existing = get<any>(
        'SELECT * FROM branches WHERE spreadsheet_id = ? AND name = ?',
        [spreadsheetId, name]
    );

    if (existing) {
        return c.json({ error: 'Branch already exists' }, 400);
    }

    const branchId = generateId();
    const now = Date.now();

    run(
        'INSERT INTO branches (id, spreadsheet_id, name, head_commit_id, created_at, created_by_id) VALUES (?, ?, ?, ?, ?, ?)',
        [branchId, spreadsheetId, name, sourceBranch.head_commit_id, now, userId]
    );

    const sourceCells = query(
        'SELECT * FROM cell_snapshots WHERE branch_id = ?',
        [sourceBranch.id]
    );

    for (const cell of sourceCells) {
        run(
            'INSERT INTO cell_snapshots (id, sheet_id, branch_id, row, col, value) VALUES (?, ?, ?, ?, ?, ?)',
            [generateId(), cell.sheet_id, branchId, cell.row, cell.col, cell.value]
        );
    }

    return c.json({ branch: { id: branchId, name } });
});

const mergeSchema = z.object({
    sourceBranch: z.string(),
    targetBranch: z.string(),
    message: z.string().optional(),
});

branchesRouter.post('/:spreadsheetId/merge', zValidator('json', mergeSchema), async (c) => {
    const userId = c.get('userId');
    if (!userId) return c.json({ error: 'Unauthorized' }, 401);

    const { spreadsheetId } = c.req.param();
    const { sourceBranch: sourceName, targetBranch: targetName, message } = c.req.valid('json');

    const source = get<any>(
        'SELECT * FROM branches WHERE spreadsheet_id = ? AND name = ?',
        [spreadsheetId, sourceName]
    );

    const target = get<any>(
        'SELECT * FROM branches WHERE spreadsheet_id = ? AND name = ?',
        [spreadsheetId, targetName]
    );

    if (!source || !target) {
        return c.json({ error: 'Branch not found' }, 404);
    }

    const sourceCells = query('SELECT * FROM cell_snapshots WHERE branch_id = ?', [source.id]);
    const targetCells = query('SELECT * FROM cell_snapshots WHERE branch_id = ?', [target.id]);

    const sourceMap = new Map(sourceCells.map(c => [`${c.sheet_id},${c.row},${c.col}`, c]));
    const targetMap = new Map(targetCells.map(c => [`${c.sheet_id},${c.row},${c.col}`, c]));

    const conflicts: any[] = [];
    const changes: any[] = [];

    for (const [key, sourceCell] of sourceMap) {
        const targetCell = targetMap.get(key);
        if (targetCell && targetCell.value !== sourceCell.value) {
            conflicts.push({
                sheetId: sourceCell.sheet_id,
                row: sourceCell.row,
                column: sourceCell.col,
                sourceValue: sourceCell.value,
                targetValue: targetCell.value,
            });
        } else if (!targetCell) {
            changes.push({
                sheetId: sourceCell.sheet_id,
                row: sourceCell.row,
                column: sourceCell.col,
                oldValue: null,
                newValue: sourceCell.value,
            });
        }
    }

    if (conflicts.length > 0) {
        return c.json({ conflicts, hasConflicts: true });
    }

    if (changes.length === 0) {
        return c.json({ message: 'Nothing to merge', hasConflicts: false });
    }

    const commitId = generateId();
    const now = Date.now();

    run(
        'INSERT INTO commits (id, spreadsheet_id, branch_id, parent_commit_id, author_id, message, hash, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        [commitId, spreadsheetId, target.id, target.head_commit_id, userId, message || `Merge ${sourceName} into ${targetName}`, generateHash(JSON.stringify(changes)), now]
    );

    for (const change of changes) {
        run(
            'INSERT INTO cell_changes (id, commit_id, sheet_id, row, col, old_value, new_value) VALUES (?, ?, ?, ?, ?, ?, ?)',
            [generateId(), commitId, change.sheetId, change.row, change.column, change.oldValue, change.newValue]
        );

        run(
            'INSERT INTO cell_snapshots (id, sheet_id, branch_id, row, col, value) VALUES (?, ?, ?, ?, ?, ?)',
            [generateId(), change.sheetId, target.id, change.row, change.column, change.newValue]
        );
    }

    run('UPDATE branches SET head_commit_id = ? WHERE id = ?', [commitId, target.id]);

    return c.json({ merged: true, changesCount: changes.length, hasConflicts: false });
});

export default branchesRouter;
