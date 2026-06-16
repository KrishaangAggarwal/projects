import { Hono } from 'hono';
import { zValidator } from '@hono/zod-validator';
import { z } from 'zod';
import { query, run, get } from '../db/index.js';
import { hashPassword, verifyPassword, createToken, generateId } from '../lib/auth.js';

const auth = new Hono();

const registerSchema = z.object({
    email: z.string().email(),
    password: z.string().min(6),
    name: z.string().min(1),
});

const loginSchema = z.object({
    email: z.string().email(),
    password: z.string(),
});

auth.post('/register', zValidator('json', registerSchema), async (c) => {
    const { email, password, name } = c.req.valid('json');

    const existing = get('SELECT * FROM users WHERE email = ?', [email]);
    if (existing) {
        return c.json({ error: 'Email already registered' }, 400);
    }

    const passwordHash = await hashPassword(password);
    const id = generateId();
    const now = Date.now();

    run(
        'INSERT INTO users (id, email, name, password_hash, created_at) VALUES (?, ?, ?, ?, ?)',
        [id, email, name, passwordHash, now]
    );

    const token = await createToken(id);
    return c.json({ token, user: { id, email, name } });
});

auth.post('/login', zValidator('json', loginSchema), async (c) => {
    const { email, password } = c.req.valid('json');

    const user = get<any>('SELECT * FROM users WHERE email = ?', [email]);
    if (!user || !user.password_hash) {
        return c.json({ error: 'Invalid credentials' }, 401);
    }

    const valid = await verifyPassword(password, user.password_hash);
    if (!valid) {
        return c.json({ error: 'Invalid credentials' }, 401);
    }

    const token = await createToken(user.id);
    return c.json({ token, user: { id: user.id, email: user.email, name: user.name } });
});

auth.get('/me', async (c) => {
    const userId = c.get('userId');
    if (!userId) {
        return c.json({ error: 'Unauthorized' }, 401);
    }

    const user = get<any>('SELECT * FROM users WHERE id = ?', [userId]);
    if (!user) {
        return c.json({ error: 'User not found' }, 404);
    }

    return c.json({ user: { id: user.id, email: user.email, name: user.name } });
});

export default auth;
