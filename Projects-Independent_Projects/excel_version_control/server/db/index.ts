import initSqlJs, { type Database } from 'sql.js';
import { mkdirSync, existsSync, readFileSync, writeFileSync } from 'node:fs';

let db: Database;
const DB_PATH = './data/spreadsheet-vc.db';

export async function initDb(): Promise<Database> {
    if (db) return db;

    if (!existsSync('./data')) {
        mkdirSync('./data', { recursive: true });
    }

    const SQL = await initSqlJs();

    if (existsSync(DB_PATH)) {
        const buffer = readFileSync(DB_PATH);
        db = new SQL.Database(buffer);
    } else {
        db = new SQL.Database();
    }

    db.run(`
    CREATE TABLE IF NOT EXISTS users (
      id TEXT PRIMARY KEY,
      email TEXT NOT NULL UNIQUE,
      name TEXT NOT NULL,
      password_hash TEXT,
      google_id TEXT,
      created_at INTEGER NOT NULL
    )
  `);

    db.run(`
    CREATE TABLE IF NOT EXISTS spreadsheets (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      source_type TEXT NOT NULL,
      google_sheet_id TEXT,
      owner_id TEXT NOT NULL,
      created_at INTEGER NOT NULL,
      updated_at INTEGER NOT NULL
    )
  `);

    db.run(`
    CREATE TABLE IF NOT EXISTS sheets (
      id TEXT PRIMARY KEY,
      spreadsheet_id TEXT NOT NULL,
      name TEXT NOT NULL,
      idx INTEGER NOT NULL
    )
  `);

    db.run(`
    CREATE TABLE IF NOT EXISTS branches (
      id TEXT PRIMARY KEY,
      spreadsheet_id TEXT NOT NULL,
      name TEXT NOT NULL,
      head_commit_id TEXT,
      created_at INTEGER NOT NULL,
      created_by_id TEXT NOT NULL
    )
  `);

    db.run(`
    CREATE TABLE IF NOT EXISTS commits (
      id TEXT PRIMARY KEY,
      spreadsheet_id TEXT NOT NULL,
      branch_id TEXT NOT NULL,
      parent_commit_id TEXT,
      author_id TEXT NOT NULL,
      message TEXT NOT NULL,
      hash TEXT NOT NULL,
      timestamp INTEGER NOT NULL
    )
  `);

    db.run(`
    CREATE TABLE IF NOT EXISTS cell_changes (
      id TEXT PRIMARY KEY,
      commit_id TEXT NOT NULL,
      sheet_id TEXT NOT NULL,
      row INTEGER NOT NULL,
      col INTEGER NOT NULL,
      old_value TEXT,
      new_value TEXT
    )
  `);

    db.run(`
    CREATE TABLE IF NOT EXISTS cell_snapshots (
      id TEXT PRIMARY KEY,
      sheet_id TEXT NOT NULL,
      branch_id TEXT NOT NULL,
      row INTEGER NOT NULL,
      col INTEGER NOT NULL,
      value TEXT
    )
  `);

    db.run(`
    CREATE TABLE IF NOT EXISTS permissions (
      id TEXT PRIMARY KEY,
      spreadsheet_id TEXT NOT NULL,
      user_id TEXT NOT NULL,
      role TEXT NOT NULL
    )
  `);

    saveDb();
    return db;
}

export function getDb(): Database {
    if (!db) throw new Error('Database not initialized');
    return db;
}

export function saveDb() {
    if (db) {
        const data = db.export();
        const buffer = Buffer.from(data);
        writeFileSync(DB_PATH, buffer);
    }
}

export function query<T = any>(sql: string, params: any[] = []): T[] {
    const stmt = db.prepare(sql);
    stmt.bind(params);
    const results: T[] = [];
    while (stmt.step()) {
        results.push(stmt.getAsObject() as T);
    }
    stmt.free();
    return results;
}

export function run(sql: string, params: any[] = []) {
    db.run(sql, params);
    saveDb();
}

export function get<T = any>(sql: string, params: any[] = []): T | undefined {
    const results = query<T>(sql, params);
    return results[0];
}
