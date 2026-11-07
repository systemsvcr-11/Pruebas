# Ejecutar desde la raíz del proyecto
npm install
npm --prefix modules/finanzas/frontend install
npm --prefix modules/finanzas/frontend run build
node scripts/copy-finanzas.mjs
npm run build
