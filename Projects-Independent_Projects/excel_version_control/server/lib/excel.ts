import * as XLSX from 'xlsx';

export interface ParsedSheet {
    name: string;
    cells: { row: number; column: number; value: string }[];
}

export interface ParsedWorkbook {
    sheets: ParsedSheet[];
}

export function parseExcelBuffer(buffer: Buffer): ParsedWorkbook {
    const workbook = XLSX.read(buffer, { type: 'buffer' });
    const sheets: ParsedSheet[] = [];

    for (const sheetName of workbook.SheetNames) {
        const worksheet = workbook.Sheets[sheetName];
        const cells: { row: number; column: number; value: string }[] = [];

        const range = XLSX.utils.decode_range(worksheet['!ref'] || 'A1');

        for (let row = range.s.r; row <= range.e.r; row++) {
            for (let col = range.s.c; col <= range.e.c; col++) {
                const cellAddress = XLSX.utils.encode_cell({ r: row, c: col });
                const cell = worksheet[cellAddress];

                if (cell !== undefined) {
                    const value = cell.f ? `=${cell.f}` : String(cell.v ?? '');
                    cells.push({ row, column: col, value });
                }
            }
        }

        sheets.push({ name: sheetName, cells });
    }

    return { sheets };
}

export function columnToLetter(column: number): string {
    let result = '';
    let temp = column;
    while (temp >= 0) {
        result = String.fromCharCode((temp % 26) + 65) + result;
        temp = Math.floor(temp / 26) - 1;
    }
    return result;
}

export function letterToColumn(letter: string): number {
    let column = 0;
    for (let i = 0; i < letter.length; i++) {
        column = column * 26 + (letter.charCodeAt(i) - 64);
    }
    return column - 1;
}
