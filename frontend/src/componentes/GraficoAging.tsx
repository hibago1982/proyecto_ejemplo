/**
 * Grafico de antiguedad por bucket (§8.1).
 *
 * Los colores llegan del API, no estan escritos aqui: §16 exige que la paleta
 * sea configurable por empresa y que no viva en el codigo. Si manana la empresa
 * cambia el color de un bucket, este grafico lo refleja sin desplegar nada.
 */
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { BarraAging } from "../api/cliente";
import { pesos, pesosCompactos, porcentaje } from "../formato";
import { Superficie } from "./Superficie";

export function GraficoAging({ aging }: { aging: BarraAging[] }) {
  const datos = aging.map((b) => ({
    ...b,
    valor: Number(b.saldo),
    // Con ocho buckets, "Mas de 150 dias" y "121-150 dias" se pisan. Se
    // abrevia solo el eje; el nombre completo sigue en la etiqueta emergente.
    breve: b.etiqueta.replace(/ d[ií]as?$/, "").replace(/^Mas de /, ">"),
  }));

  return (
    <Superficie titulo="Antigüedad de cartera">
      <div style={{ height: 220 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={datos} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
            <XAxis
              dataKey="breve"
              tick={{ fontSize: 10, fill: "#6B7280" }}
              axisLine={{ stroke: "#E8EAED" }}
              tickLine={false}
              interval={0}
            />
            <YAxis
              tick={{ fontSize: 10, fill: "#9CA3AF" }}
              axisLine={false}
              tickLine={false}
              width={56}
              tickFormatter={(v: number) => pesosCompactos(String(v))}
            />
            <Tooltip
              cursor={{ fill: "#F5F6F7" }}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const b = payload[0]!.payload as BarraAging;
                return (
                  <div className="rounded-lg border border-filete bg-white px-3 py-2 text-menor shadow-sm">
                    <p className="font-semibold text-tinta">{b.etiqueta}</p>
                    <p className="tabular-nums text-apagado">{pesos(b.saldo)}</p>
                    <p className="tabular-nums text-tenue">
                      {b.facturas} facturas · {porcentaje(b.pct_sobre_total)}
                    </p>
                  </div>
                );
              }}
            />
            <Bar dataKey="valor" radius={[4, 4, 0, 0]} isAnimationActive={false}>
              {datos.map((b) => (
                <Cell key={b.bucket} fill={b.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Superficie>
  );
}
