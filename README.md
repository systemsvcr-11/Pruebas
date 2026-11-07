# Portal Corporativo — proyecto unificado

Este proyecto reúne el portal y los tres módulos recibidos. Recetas CP y Requerimientos siguen como accesos externos.

## Contenido
- `index.html`: portal existente, conservando diseño, iconos, buscador y login Supabase.
- `modules/moolog/index.html`: MooLog! original.
- `modules/sigep/index.html`: Gestión Personal / SIGEP original.
- `modules/finanzas/frontend`: frontend React/Vite original de Control de Compras.
- `backend/finanzas`: backend FastAPI original.
- `originales/`: snapshots sin modificar de Portal, MooLog! y SIGEP.

## Configurar Supabase
Edita `portal/config.js` y coloca tu URL de proyecto y clave publishable/anon. Nunca uses `service_role` en el navegador.

## Ejecutar portal
En la raíz:
1. `npm install`
2. `npm run dev`

## Estado de autenticación — leer antes de publicar
Este paquete es una unificación inicial de carpetas y navegación, no un SSO productivo terminado.
MooLog! y SIGEP conservan temporalmente sus mecanismos de login actuales contra Google Apps Script. Finanzas conserva sus endpoints originales, que no tienen autenticación en el código recibido.

Para completar el único login sin romper procesos, se necesita:
- Modificar cada Apps Script para validar un JWT de Supabase en todas las operaciones de lectura/escritura.
- Mapear el usuario Supabase al usuario/rol que hoy usa cada módulo.
- Proteger cada endpoint de FastAPI de Finanzas validando JWT y permisos.
- Solo después de probar estas validaciones se retiran los logins propios.

No se guarda ni se envía la contraseña de Supabase a los módulos. No volver a usar el SSO anterior que codificaba credenciales en Base64.

## Finanzas
El frontend React/Vite se compila dentro de `public/modules/finanzas/` mediante `npm run build:all`. El backend FastAPI se conserva separado dentro del monorepo. El frontend usa `VITE_API_URL` para apuntar al backend. El backend se despliega como servicio API; no se ejecuta automáticamente dentro del servidor estático del portal.

## Respaldos
Los archivos originales subidos no se modifican; además se incluyen snapshots en `originales/`.
