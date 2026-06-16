import { useState, useMemo } from 'react';

interface Cell {
    row: number;
    column: number;
    value: string | null;
}

interface Props {
    cells: Cell[];
    pendingChanges: Map<string, any>;
    onCellChange: (row: number, column: number, oldValue: string | null, newValue: string) => void;
    onCommit: (message: string) => void;
}

function columnToLetter(column: number): string {
    let result = '';
    let temp = column;
    while (temp >= 0) {
        result = String.fromCharCode((temp % 26) + 65) + result;
        temp = Math.floor(temp / 26) - 1;
    }
    return result;
}

export default function SpreadsheetGrid({ cells, pendingChanges, onCellChange, onCommit }: Props) {
    const [commitMessage, setCommitMessage] = useState('');
    const [editingCell, setEditingCell] = useState<string | null>(null);
    const [editValue, setEditValue] = useState('');

    const { maxRow, maxCol, cellMap } = useMemo(() => {
        let maxRow = 20;
        let maxCol = 10;
        const cellMap = new Map<string, string>();

        for (const cell of cells) {
            maxRow = Math.max(maxRow, cell.row + 5);
            maxCol = Math.max(maxCol, cell.column + 3);
            cellMap.set(`${cell.row},${cell.column}`, cell.value || '');
        }

        for (const [key, change] of pendingChanges) {
            cellMap.set(key, change.newValue || '');
        }

        return { maxRow, maxCol, cellMap };
    }, [cells, pendingChanges]);

    const getCellValue = (row: number, col: number): string => {
        return cellMap.get(`${row},${col}`) || '';
    };

    const handleCellClick = (row: number, col: number) => {
        const key = `${row},${col}`;
        setEditingCell(key);
        setEditValue(getCellValue(row, col));
    };

    const handleCellBlur = (row: number, col: number) => {
        const oldValue = cells.find(c => c.row === row && c.column === col)?.value || null;
        if (editValue !== (oldValue || '')) {
            onCellChange(row, col, oldValue, editValue);
        }
        setEditingCell(null);
    };

    const handleKeyDown = (e: React.KeyboardEvent, row: number, col: number) => {
        if (e.key === 'Enter') {
            handleCellBlur(row, col);
        } else if (e.key === 'Escape') {
            setEditingCell(null);
        }
    };

    const handleCommit = () => {
        if (!commitMessage.trim() || pendingChanges.size === 0) return;
        onCommit(commitMessage);
        setCommitMessage('');
    };

    return (
        <div className="flex-1 flex flex-col overflow-hidden">
            {pendingChanges.size > 0 && (
                <div className="bg-yellow-50 border-b border-yellow-200 px-4 py-2 flex items-center gap-4">
                    <span className="text-sm text-yellow-800">
                        {pendingChanges.size} unsaved change{pendingChanges.size > 1 ? 's' : ''}
                    </span>
                    <input
                        type="text"
                        placeholder="Commit message..."
                        value={commitMessage}
                        onChange={(e) => setCommitMessage(e.target.value)}
                        className="flex-1 max-w-md px-3 py-1 text-sm border rounded focus:outline-none focus:ring-1 focus:ring-primary-500"
                    />
                    <button
                        onClick={handleCommit}
                        disabled={!commitMessage.trim()}
                        className="px-4 py-1 text-sm bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
                    >
                        Commit
                    </button>
                </div>
            )}

            <div className="flex-1 overflow-auto">
                <table className="border-collapse min-w-full">
                    <thead className="sticky top-0 z-10">
                        <tr>
                            <th className="w-12 bg-gray-100 border border-gray-300 text-xs text-gray-500 font-normal"></th>
                            {Array.from({ length: maxCol }, (_, i) => (
                                <th
                                    key={i}
                                    className="min-w-24 bg-gray-100 border border-gray-300 px-2 py-1 text-xs text-gray-600 font-medium"
                                >
                                    {columnToLetter(i)}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {Array.from({ length: maxRow }, (_, row) => (
                            <tr key={row}>
                                <td className="bg-gray-100 border border-gray-300 px-2 py-1 text-xs text-gray-600 text-center font-medium">
                                    {row + 1}
                                </td>
                                {Array.from({ length: maxCol }, (_, col) => {
                                    const key = `${row},${col}`;
                                    const isEditing = editingCell === key;
                                    const isPending = pendingChanges.has(key);
                                    const value = getCellValue(row, col);

                                    return (
                                        <td
                                            key={col}
                                            className={`border border-gray-200 p-0 ${isPending ? 'bg-yellow-50' : 'bg-white'}`}
                                            onClick={() => handleCellClick(row, col)}
                                        >
                                            {isEditing ? (
                                                <input
                                                    type="text"
                                                    value={editValue}
                                                    onChange={(e) => setEditValue(e.target.value)}
                                                    onBlur={() => handleCellBlur(row, col)}
                                                    onKeyDown={(e) => handleKeyDown(e, row, col)}
                                                    autoFocus
                                                    className="w-full h-full px-2 py-1 text-sm outline-none border-2 border-primary-500"
                                                />
                                            ) : (
                                                <div className="px-2 py-1 text-sm min-h-[28px] cursor-cell truncate">
                                                    {value}
                                                </div>
                                            )}
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
