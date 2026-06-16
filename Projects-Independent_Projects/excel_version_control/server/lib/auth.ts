import { SignJWT, jwtVerify } from 'jose';
import bcrypt from 'bcryptjs';

const JWT_SECRET = new TextEncoder().encode(
    process.env.JWT_SECRET || 'spreadsheet-vc-secret-key-change-in-production'
);

export async function hashPassword(password: string): Promise<string> {
    return bcrypt.hash(password, 10);
}

export async function verifyPassword(password: string, hash: string): Promise<boolean> {
    return bcrypt.compare(password, hash);
}

export async function createToken(userId: string): Promise<string> {
    return new SignJWT({ userId })
        .setProtectedHeader({ alg: 'HS256' })
        .setIssuedAt()
        .setExpirationTime('7d')
        .sign(JWT_SECRET);
}

export async function verifyToken(token: string): Promise<{ userId: string } | null> {
    try {
        const { payload } = await jwtVerify(token, JWT_SECRET);
        return { userId: payload.userId as string };
    } catch {
        return null;
    }
}

export function generateId(): string {
    return crypto.randomUUID();
}

export function generateHash(data: string): string {
    const encoder = new TextEncoder();
    const dataBuffer = encoder.encode(data);
    let hash = 0;
    for (let i = 0; i < dataBuffer.length; i++) {
        const char = dataBuffer[i];
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash;
    }
    return Math.abs(hash).toString(16).padStart(8, '0');
}
