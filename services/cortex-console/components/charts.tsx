"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

export function TrustDistributionChart() {
  const data = [
    { bucket: "0-20", count: 3 },
    { bucket: "21-40", count: 9 },
    { bucket: "41-60", count: 17 },
    { bucket: "61-80", count: 42 },
    { bucket: "81-100", count: 66 }
  ];

  return (
    <div className="rounded-2xl border bg-panel/80 p-4 shadow-panel">
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-[0.2em] text-muted">
        Trust Score Distribution
      </h2>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid stroke="#17304f" strokeDasharray="3 3" />
            <XAxis dataKey="bucket" stroke="#8ba3c0" />
            <YAxis stroke="#8ba3c0" />
            <Tooltip />
            <Bar dataKey="count" fill="#4cc9f0" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function AgentActivityChart() {
  const data = [
    { minute: "00", tasks: 7 },
    { minute: "10", tasks: 9 },
    { minute: "20", tasks: 12 },
    { minute: "30", tasks: 8 },
    { minute: "40", tasks: 15 },
    { minute: "50", tasks: 11 }
  ];

  return (
    <div className="rounded-2xl border bg-panel/80 p-4 shadow-panel">
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-[0.2em] text-muted">
        Agent Activity
      </h2>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <CartesianGrid stroke="#17304f" strokeDasharray="3 3" />
            <XAxis dataKey="minute" stroke="#8ba3c0" />
            <YAxis stroke="#8ba3c0" />
            <Tooltip />
            <Area dataKey="tasks" stroke="#1D9E75" fill="#1D9E75" fillOpacity={0.28} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
