import * as XLSX from 'xlsx';
import { writeFileSync } from 'fs';
import { mkdirSync, existsSync } from 'fs';

if (!existsSync('./sample-data')) {
  mkdirSync('./sample-data', { recursive: true });
}

// Create a sample financial spreadsheet
const data = [
  ['Q1 2026 Budget', '', '', ''],
  ['', '', '', ''],
  ['Category', 'January', 'February', 'March'],
  ['Revenue', 150000, 165000, 180000],
  ['Cost of Goods', 45000, 49500, 54000],
  ['Gross Profit', '=B4-B5', '=C4-C5', '=D4-D5'],
  ['', '', '', ''],
  ['Operating Expenses', '', '', ''],
  ['Salaries', 35000, 35000, 36000],
  ['Marketing', 12000, 15000, 18000],
  ['Rent', 8000, 8000, 8000],
  ['Utilities', 2500, 2800, 2600],
  ['Total OpEx', '=SUM(B9:B12)', '=SUM(C9:C12)', '=SUM(D9:D12)'],
  ['', '', '', ''],
  ['Net Income', '=B6-B13', '=C6-C13', '=D6-D13'],
];

const wb = XLSX.utils.book_new();
const ws = XLSX.utils.aoa_to_sheet(data);

// Set column widths
ws['!cols'] = [
  { wch: 20 },
  { wch: 12 },
  { wch: 12 },
  { wch: 12 },
];

XLSX.utils.book_append_sheet(wb, ws, 'Budget');

// Add a second sheet
const data2 = [
  ['Employee List', '', ''],
  ['', '', ''],
  ['Name', 'Department', 'Salary'],
  ['John Smith', 'Engineering', 85000],
  ['Jane Doe', 'Marketing', 72000],
  ['Bob Johnson', 'Finance', 78000],
  ['Alice Williams', 'Engineering', 92000],
  ['Charlie Brown', 'Sales', 68000],
];

const ws2 = XLSX.utils.aoa_to_sheet(data2);
ws2['!cols'] = [
  { wch: 18 },
  { wch: 14 },
  { wch: 12 },
];

XLSX.utils.book_append_sheet(wb, ws2, 'Employees');

const buffer = XLSX.write(wb, { type: 'buffer', bookType: 'xlsx' });
writeFileSync('./sample-data/sample-budget.xlsx', buffer);

console.log('Sample Excel file created: sample-data/sample-budget.xlsx');
