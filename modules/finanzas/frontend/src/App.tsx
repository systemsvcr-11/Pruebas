
import { useEffect, useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid
} from 'recharts';
import {
  LayoutDashboard, BellRing, GitCompare, RefreshCw,
  AlertTriangle, Search, Landmark, ChevronDown, ChevronRight
} from 'lucide-react';

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

const money = (v: number) =>
  new Intl.NumberFormat('es-PE', {
    style: 'currency',
    currency: 'PEN'
  }).format(v || 0);

type Alert = {
  id: string;
  type: string;
  severity: string;
  product: string;
  supplier: string;
  message: string;
  amount: number;
  status: string;
  date: string;
};

type InvoiceDetail = {
  id: number | string;
  fecha: string;
  factura: string;
  proveedor: string;
  cantidad: number;
  precio_unitario: number;
  total_linea: number;
};

type Row = {
  id: string;
  empresa: string;
  anio: number;
  semana: number;
  periodo: string;
  producto: string;
  producto_codigo: string;
  unidad: string;
  cantidad_facturada: number;
  cantidad_recibida: number;
  diferencia: number;
  total_facturado: number;
  importe_diferencia: number;
  facturas: InvoiceDetail[];
};

export default function App() {
  const [page, setPage] = useState('dashboard');
  const [summary, setSummary] = useState<any>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [rows, setRows] = useState<Row[]>([]);
  const [query, setQuery] = useState('');
  const [empresa, setEmpresa] = useState('');
  const [periodo, setPeriodo] = useState('');
  const [expanded, setExpanded] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setError('');

    try {
      const [s, a, c] = await Promise.all([
        fetch(`${API}/api/dashboard/resumen`),
        fetch(`${API}/api/alertas`),
        fetch(`${API}/api/conciliaciones`)
      ]);

      if (!s.ok || !a.ok || !c.ok) {
        throw new Error('Error al consultar la API');
      }

      setSummary(await s.json());
      setAlerts(await a.json());
      setRows(await c.json());
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'No se pudo conectar con el backend'
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function changeStatus(a: Alert, status: string) {
    try {
      const r = await fetch(
        `${API}/api/alertas/${encodeURIComponent(a.id)}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status })
        }
      );

      const d = await r.json();

      if (!r.ok) {
        window.alert(
          d.detail || 'No se pudo actualizar el estado'
        );
        return;
      }

      await load();
    } catch {
      window.alert('No se pudo conectar con el backend');
    }
  }

  const empresas = [...new Set(rows.map(r => r.empresa))]
    .filter(Boolean)
    .sort();

  const periodos = [...new Set(rows.map(r => r.periodo))]
    .filter(Boolean)
    .sort()
    .reverse();

  const filteredRows = rows.filter(r => {
    const text = `${r.producto} ${r.producto_codigo} ${r.empresa}`
      .toLowerCase();

    return (
      (!empresa || r.empresa === empresa) &&
      (!periodo || r.periodo === periodo) &&
      text.includes(query.toLowerCase())
    );
  });

  const filteredAlerts = alerts.filter(a =>
    `${a.product} ${a.supplier} ${a.type}`
      .toLowerCase()
      .includes(query.toLowerCase())
  );

  const chart = Object.values(
    rows.reduce((acc: Record<string, any>, r) => {
      if (!acc[r.periodo]) {
        acc[r.periodo] = {
          periodo: r.periodo,
          total: 0
        };
      }

      acc[r.periodo].total += r.total_facturado || 0;
      return acc;
    }, {})
  ).sort((a: any, b: any) =>
    a.periodo.localeCompare(b.periodo)
  );

  function toggleDetails(id: string) {
    setExpanded(previous =>
      previous.includes(id)
        ? previous.filter(x => x !== id)
        : [...previous, id]
    );
  }

  const filasConDiferencia = filteredRows.filter(
    r => Math.abs(r.diferencia) > 0.0001
  ).length;

  return (
    <div className="layout">
      <aside>
        <div className="brand">
          <Landmark />
          <b>Control de Compras</b>
        </div>

        <button onClick={() => setPage('dashboard')}>
          <LayoutDashboard /> Dashboard
        </button>

        <button onClick={() => setPage('conciliacion')}>
          <GitCompare /> Conciliación semanal
        </button>

        <button onClick={() => setPage('alertas')}>
          <BellRing /> Alertas
        </button>

        <small>Facturas · Recepciones · Precios</small>
      </aside>

      <main>
        <header>
          <div>
            <span>CONTROL DE COMPRAS</span>
            <h1>
              {page === 'dashboard'
                ? 'Dashboard general'
                : page === 'alertas'
                  ? 'Centro de alertas'
                  : 'Conciliación semanal'}
            </h1>
            <p>
              Compara cantidades facturadas y recibidas por empresa,
              producto y semana.
            </p>
          </div>

          <button className="refresh" onClick={() => void load()}>
            <RefreshCw /> Actualizar
          </button>
        </header>

        {error && (
          <div className="error">
            {error}. Verifica que FastAPI esté activo en {API}.
          </div>
        )}

        {loading && <p>Cargando datos…</p>}

        {!loading && page === 'dashboard' && summary && (
          <>
            <section className="kpis">
              <Kpi
                title="Total facturado"
                value={money(summary.total_facturado)}
              />
              <Kpi
                title="Importe observado"
                value={money(summary.importe_observado)}
              />
              <Kpi
                title="Alertas pendientes"
                value={String(summary.alertas_pendientes)}
              />
              <Kpi
                title="Grupos con diferencias"
                value={String(
                  rows.filter(r => Math.abs(r.diferencia) > 0.0001).length
                )}
              />
            </section>

            <section className="panel">
              <h2>Facturación semanal</h2>
              <p>Importe total facturado por semana ISO.</p>

              <div className="chart">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chart}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="periodo" />
                    <YAxis />
                    <Tooltip
                      formatter={(value: any) => money(Number(value))}
                    />
                    <Bar dataKey="total" name="Total facturado" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>

            <section className="panel">
              <h2>Alertas prioritarias</h2>
              <AlertList
                alerts={alerts.slice(0, 5)}
                changeStatus={changeStatus}
              />
            </section>
          </>
        )}

        {!loading && page === 'conciliacion' && (
          <section className="panel">
            <h2>Factura vs. recepción semanal</h2>

            <p>
              La recepción se asigna a la semana de entrega esperada.
              Las diferencias negativas indican que lo recibido supera
              lo facturado.
            </p>

            <div className="filters">
              <label>
                Empresa
                <select
                  value={empresa}
                  onChange={e => setEmpresa(e.target.value)}
                >
                  <option value="">Todas las empresas</option>
                  {empresas.map(e => (
                    <option key={e} value={e}>{e}</option>
                  ))}
                </select>
              </label>

              <label>
                Semana
                <select
                  value={periodo}
                  onChange={e => setPeriodo(e.target.value)}
                >
                  <option value="">Todas las semanas</option>
                  {periodos.map(p => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </label>

              <label>
                Buscar producto
                <div className="search">
                  <Search />
                  <input
                    placeholder="Nombre o código"
                    value={query}
                    onChange={e => setQuery(e.target.value)}
                  />
                </div>
              </label>
            </div>

            <div className="kpis">
              <Kpi
                title="Grupos encontrados"
                value={String(filteredRows.length)}
              />
              <Kpi
                title="Con diferencias"
                value={String(filasConDiferencia)}
              />
              <Kpi
                title="Importe estimado por revisar"
                value={money(
                  filteredRows.reduce(
                    (sum, r) => sum + r.importe_diferencia,
                    0
                  )
                )}
              />
            </div>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th></th>
                    <th>Semana</th>
                    <th>Empresa</th>
                    <th>Producto</th>
                    <th>Facturado</th>
                    <th>Recibido</th>
                    <th>Diferencia</th>
                    <th>Importe estimado</th>
                  </tr>
                </thead>

                <tbody>
                  {filteredRows.map(r => {
                    const isExpanded = expanded.includes(r.id);

                    return (
                      <>
                        <tr key={r.id}>
                          <td>
                            <button
                              title="Ver detalle de facturas"
                              onClick={() => toggleDetails(r.id)}
                            >
                              {isExpanded
                                ? <ChevronDown size={18} />
                                : <ChevronRight size={18} />}
                            </button>
                          </td>

                          <td>{r.periodo}</td>
                          <td>{r.empresa}</td>
                          <td>
                            <b>{r.producto}</b>
                            <br />
                            <small>{r.unidad}</small>
                          </td>
                          <td>
                            {r.cantidad_facturada.toLocaleString('es-PE')}
                          </td>
                          <td>
                            {r.cantidad_recibida.toLocaleString('es-PE')}
                          </td>
                          <td className={Math.abs(r.diferencia) < 0.0001
                            ? 'good'
                            : 'bad'}>
                            {r.diferencia.toLocaleString('es-PE')}
                          </td>
                          <td>{money(r.importe_diferencia)}</td>
                        </tr>

                        {isExpanded && (
                          <tr key={`${r.id}-detalle`}>
                            <td colSpan={8}>
                              <div className="panel">
                                <h3>
                                  Detalle de facturas — {r.producto}
                                </h3>

                                {!r.facturas.length ? (
                                  <p>
                                    No hay líneas de factura para este grupo.
                                    Puede corresponder a una recepción sin
                                    facturación en esa semana.
                                  </p>
                                ) : (
                                  <div className="table-wrap">
                                    <table>
                                      <thead>
                                        <tr>
                                          <th>Fecha</th>
                                          <th>N.º factura</th>
                                          <th>Proveedor</th>
                                          <th>Cantidad</th>
                                          <th>Precio unitario</th>
                                          <th>Total línea</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {r.facturas.map((f, i) => (
                                          <tr key={`${f.id}-${i}`}>
                                            <td>{f.fecha}</td>
                                            <td>{f.factura}</td>
                                            <td>{f.proveedor}</td>
                                            <td>{f.cantidad}</td>
                                            <td>{money(f.precio_unitario)}</td>
                                            <td>{money(f.total_linea)}</td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  </div>
                                )}
                              </div>
                            </td>
                          </tr>
                        )}
                      </>
                    );
                  })}
                </tbody>
              </table>

              {!filteredRows.length && (
                <p>No se encontraron grupos con esos filtros.</p>
              )}
            </div>
          </section>
        )}

        {!loading && page === 'alertas' && (
          <section className="panel">
            <h2>Centro de alertas</h2>

            <div className="search">
              <Search />
              <input
                placeholder="Buscar producto o proveedor"
                value={query}
                onChange={e => setQuery(e.target.value)}
              />
            </div>

            <AlertList
              alerts={filteredAlerts}
              changeStatus={changeStatus}
            />
          </section>
        )}

        <footer>
          Conciliación por empresa, semana ISO, producto y unidad.
          Recepciones agrupadas por entrega esperada.
        </footer>
      </main>
    </div>
  );
}

function Kpi({ title, value }: { title: string; value: string }) {
  return (
    <div className="kpi">
      <span>{title}</span>
      <strong>{value}</strong>
    </div>
  );
}

function AlertList({
  alerts,
  changeStatus
}: {
  alerts: Alert[];
  changeStatus: (a: Alert, s: string) => void;
}) {
  return (
    <div>
      {alerts.map(a => (
        <div className="alert" key={a.id}>
          <AlertTriangle />

          <div className="alert-body">
            <b>{a.type} — {a.product}</b>
            <p>{a.supplier} · {a.message}</p>
            <small>
              {a.date} · Importe estimado: {money(a.amount)}
            </small>
          </div>

          <select
            value={a.status}
            onChange={e => void changeStatus(a, e.target.value)}
          >
            <option>Pendiente</option>
            <option>En revisión</option>
            <option>Justificada</option>
            <option>Reclamo enviado</option>
            <option>Resuelta</option>
          </select>
        </div>
      ))}

      {!alerts.length && <p>No hay alertas.</p>}
    </div>
  );
}
