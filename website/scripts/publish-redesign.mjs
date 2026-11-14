import { cpSync } from 'node:fs';

cpSync(new URL('../redesign/', import.meta.url), new URL('../out/', import.meta.url), { recursive: true });
