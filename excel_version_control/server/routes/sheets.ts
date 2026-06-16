import { Hono } from 'hono';
import { query, get } from '../db/index.js';

const sheetsRouter = new Hono();

sheetsRouter.get('/:spreadsheetId/sheets', async (c) => {
    const userId = c.get('userId');
    if (!userId) return c.json({ error: 'Unauthorized' }, 401);

    const { spreadsheetId } = c.req.param();

    const sheetList = query(
        'SELECT * FROM sheets WHERE spreadsheet_id = ? ORDER BY idx',
        [spreadsheetId]
    );

    return c.json({
        sheets: sheetList.map(s => ({
            id: s.id,
            spreadsheetId: s.spreadsheet_id,
            name: s.name,
            index: s.idx,
        }))
    });
});

sheetsRouter.get('/:spreadsheetId/sheets/:sheetId/cells', async (c) => {
    const userId = c.get('userId');
    if (!userId) return c.json({ error: 'Unauthorized' }, 401);

    const { spreadsheetId, sheetId } = c.req.param();
    const branchName = c.req.query('branch') || 'main';

    const branch = get<any>(
        'SELECT * FROM branches WHERE spreadsheet_id = ? AND name = ?',
        [spreadsheetId, branchName]
    );

    if (!branch) {
        return c.json({ error: 'Branch not found' }, 404);
    }

    const cells = query(
        'SELECT * FROM cell_snapshots WHERE sheet_id = ? AND branch_id = ?',
        [sheetId, branch.id]
    );

    const cellMap: Record<string, { row: number; column: number; value: string | null }> = {};
    for (const cell of cells) {
        cellMap[`${cell.row},${cell.col}`] = {
            row: cell.row,
            column: cell.col,
            value: cell.value,
        };
    }

    return c.json({ cells: Object.values(cellMap), branchId: branch.id });
});

export default sheetsRouter;
