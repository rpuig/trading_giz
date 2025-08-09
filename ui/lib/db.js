import Database from 'better-sqlite3';
import path from 'node:path';

let db;
export function getDB() {
  if (!db) {
    const dbPath = process.env.DB_PATH || path.resolve(process.cwd(), '../market_data.sqlite');
    db = new Database(dbPath, { readonly: true, fileMustExist: true });
  }
  return db;
}
