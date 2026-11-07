import { cp, mkdir, rm } from 'node:fs/promises';
import { resolve } from 'node:path';

const source = resolve('modules/finanzas/frontend/dist');
const target = resolve('public/modules/finanzas');
await rm(target, { recursive: true, force: true });
await mkdir(target, { recursive: true });
await cp(source, target, { recursive: true });
console.log('Finanzas copiado a public/modules/finanzas');
