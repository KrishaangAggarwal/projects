import { serve } from '@hono/node-server';
import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { logger } from 'hono/logger';
import { initDb } from './db/index.js';
import { verifyToken } from './lib/auth.js';
import authRoutes from './routes/auth.js';
import spreadsheetsRoutes from './routes/spreadsheets.js';
import sheetsRoutes from './routes/sheets.js';
import commitsRoutes from './routes/commits.js';
import branchesRoutes from './routes/branches.js';
import auditRoutes from './routes/audit.js';
import revertRoutes from './routes/revert.js';
import diffRoutes from './routes/diff.js';

const app = new Hono();

app.use('*', cors());
app.use('*', logger());

app.use('/api/*', async (c, next) => {
    const path = c.req.path;
    if (path === '/api/auth/login' || path === '/api/auth/register') {
        return next();
    }

    const authHeader = c.req.header('Authorization');
    if (!authHeader?.startsWith('Bearer ')) {
        return c.json({ error: 'Unauthorized' }, 401);
    }

    const token = authHeader.slice(7);
    const payload = await verifyToken(token);

    if (!payload) {
        return c.json({ error: 'Invalid token' }, 401);
    }

    c.set('userId', payload.userId);
    return next();
});

app.route('/api/auth', authRoutes);
app.route('/api/spreadsheets', spreadsheetsRoutes);
app.route('/api/spreadsheets', sheetsRoutes);
app.route('/api/spreadsheets', commitsRoutes);
app.route('/api/spreadsheets', branchesRoutes);
app.route('/api/spreadsheets', auditRoutes);
app.route('/api/spreadsheets', revertRoutes);
app.route('/api/spreadsheets', diffRoutes);

app.get('/api/health', (c) => c.json({ status: 'ok' }));

async function start() {
    await initDb();

    const port = parseInt(process.env.PORT || '3000');
    console.log(`Server running on http://localhost:${port}`);

    serve({ fetch: app.fetch, port });
}

start();
