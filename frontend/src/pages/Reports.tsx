// Multi-chart analytics page with AI-generated financial report and smart action recommendations
import { useState, useMemo, useEffect } from "react";
import { Bot, RefreshCw, CalendarIcon, TrendingUp, TrendingDown, AlertTriangle, CreditCard, Banknote, Smartphone, Building2, Lightbulb, Download } from "lucide-react";
import { BarChart, Bar, LineChart, Line, AreaChart, Area, PieChart, Pie, Cell, XAxis, YAxis, ResponsiveContainer, Tooltip, Legend } from "recharts";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Calendar } from "@/components/ui/calendar";
import { cn } from "@/lib/utils";
import { useChartTheme } from "@/hooks/useChartTheme";
import { formatCurrency } from "@/lib/format";
import { format } from "date-fns";
import { toast } from "sonner";
import { API_BASE_URL } from "@/config/api";

const periods = ["This Month", "Last 3 Months", "Last 6 Months", "This Year"];
const categoryColors: Record<string, string> = {
  "Food & Dining": "#10b981", Transport: "#8b5cf6", Entertainment: "#f59e0b",
  "Bills & Utilities": "#3b82f6", Shopping: "#f43f5e", Other: "#64748b",
};

const priorityStyles: Record<string, string> = {
  high: "border-l-destructive bg-destructive/5",
  medium: "border-l-warning bg-warning/5",
  low: "border-l-primary bg-primary/5",
};

// Backend returns just the icon name; map to lucide components at render time
const paymentIconMap: Record<string, any> = {
  "Credit Card": CreditCard, "Debit Card": Banknote, "UPI": Smartphone, "Bank Transfer": Building2, "Cash": Banknote,
};

const smartActionIcons: Record<string, any> = {
  AlertTriangle, CreditCard, TrendingUp, TrendingDown, Lightbulb,
};

export default function Reports() {
  const [period, setPeriod] = useState("Last 6 Months");
  const [generating, setGenerating] = useState(false);
  const [dateFrom, setDateFrom] = useState<Date | undefined>();
  const [dateTo, setDateTo] = useState<Date | undefined>();
  const [aiReportText, setAiReportText] = useState("");
  const chart = useChartTheme();

  const [monthlyData, setMonthlyData] = useState<any[]>([]);
  const [trendsData, setTrendsData] = useState<any[]>([]);
  const [categoryData, setCategoryData] = useState<any[]>([]);
  const [paymentMethods, setPaymentMethods] = useState<any[]>([]);
  const [loansData, setLoansData] = useState<any[]>([]);
  const [smartActions, setSmartActions] = useState<any[]>([]);

  useEffect(() => {
    (async () => {
      try {
        const [reports, payments, loans, actions] = await Promise.all([
          fetch(`${API_BASE_URL}/reports/`).then(r => r.ok ? r.json() : null),
          fetch(`${API_BASE_URL}/reports/payment-methods`).then(r => r.ok ? r.json() : []),
          fetch(`${API_BASE_URL}/reports/loans-summary`).then(r => r.ok ? r.json() : []),
          fetch(`${API_BASE_URL}/reports/smart-actions`).then(r => r.ok ? r.json() : []),
        ]);
        if (reports) {
          setMonthlyData(reports.monthly || []);
          setTrendsData(reports.trends || []);
          setCategoryData(reports.categories || []);
        }
        setPaymentMethods(payments);
        setLoansData(loans);
        setSmartActions(actions);
      } catch {
        // Keep empty arrays — UI will show empty states
      }
    })();
  }, []);

  const horizontalData = useMemo(
    () => [...categoryData].sort((a, b) => b.value - a.value),
    [categoryData]
  );

  const totalPayments = paymentMethods.reduce((s: number, p: any) => s + p.value, 0);
  const totalEMI = loansData.reduce((s: number, l: any) => s + l.emi, 0);

  const generateAiReport = async () => {
    setGenerating(true);
    try {
      const response = await fetch(`${API_BASE_URL}/chat/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ period }),
      });
      if (!response.ok) throw new Error("Failed to generate report");
      const data = await response.json();
      
      let reportText = "";
      if (data.budget_analysis?.status_summary) {
        reportText += `**Budget Health:** ${data.budget_analysis.status_summary}\n\n`;
      }
      if (data.report?.summary) {
        reportText += `**Analysis:** ${data.report.summary}\n\n`;
      }
      if (data.report?.recommendations?.length) {
        reportText += `**Recommendations:**\n${data.report.recommendations.map((r: string) => `- ${r}`).join("\n")}\n\n`;
      }
      if (data.council?.consensus) {
        reportText += `**Budget Council Consensus:** ${data.council.consensus}\n\n`;
      }
      if (data.council?.estimated_savings) {
        reportText += `**Estimated Monthly Savings:** $${data.council.estimated_savings.toFixed(2)}`;
      }
      
      setAiReportText(reportText || "Report generated successfully. Check the charts above for visual insights.");
      toast.success("AI report generated");
    } catch {
      toast.error("Failed to generate AI report — showing cached data");
    } finally {
      setGenerating(false);
    }
  };

  const handleDownloadPdf = () => {
    window.print();
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Print-specific CSS — hides sidebar/topbar, isolates report section */}
      <style>{`
        @media print {
          nav, aside, header, [data-sidebar], .no-print { display: none !important; }
          main { padding: 0 !important; margin: 0 !important; }
          .print-report { break-inside: avoid; }
          .print-report * { color: #000 !important; }
          body { background: #fff !important; }
        }
      `}</style>

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 no-print">
        <h1 className="text-lg font-semibold text-foreground">Reports</h1>
        <div className="flex gap-2">
          <Button onClick={handleDownloadPdf} variant="outline" size="sm" className="w-fit text-xs">
            <Download className="w-4 h-4 mr-2" />Download Report (PDF)
          </Button>
          <Button onClick={generateAiReport} disabled={generating} size="sm" className="bg-secondary hover:bg-secondary/90 text-secondary-foreground w-fit">
            {generating ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Bot className="w-4 h-4 mr-2" />}
            {generating ? "Generating..." : "AI Report"}
          </Button>
        </div>
      </div>

      {/* Period selector + date range filter */}
      <div className="flex flex-wrap items-center gap-2 no-print">
        {periods.map(p => (
          <button key={p} onClick={() => { setPeriod(p); setDateFrom(undefined); setDateTo(undefined); }} className={cn("px-3 py-1.5 rounded-lg text-xs font-medium transition-colors", period === p && !dateFrom ? "bg-primary/10 text-primary" : "bg-card text-muted-foreground hover:bg-muted")}>{p}</button>
        ))}
        <div className="flex items-center gap-1.5 ml-auto">
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="outline" size="sm" className={cn("text-xs h-8", dateFrom && "text-primary border-primary/50")}>
                <CalendarIcon className="w-3.5 h-3.5 mr-1.5" />
                {dateFrom ? format(dateFrom, "MMM d") : "From"}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0" align="end">
              <Calendar mode="single" selected={dateFrom} onSelect={(d) => { setDateFrom(d); setPeriod(""); }} className="p-3 pointer-events-auto" />
            </PopoverContent>
          </Popover>
          <span className="text-xs text-muted-foreground">–</span>
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="outline" size="sm" className={cn("text-xs h-8", dateTo && "text-primary border-primary/50")}>
                <CalendarIcon className="w-3.5 h-3.5 mr-1.5" />
                {dateTo ? format(dateTo, "MMM d") : "To"}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0" align="end">
              <Calendar mode="single" selected={dateTo} onSelect={(d) => { setDateTo(d); setPeriod(""); }} className="p-3 pointer-events-auto" />
            </PopoverContent>
          </Popover>
        </div>
      </div>

      {/* Smart Action Items */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Lightbulb className="w-4 h-4 text-primary" />
          Recommended Actions
        </h2>
        {smartActions.length === 0 ? (
          <div className="bg-card rounded-xl p-6 border border-border/50 text-center">
            <p className="text-sm text-muted-foreground">No recommendations yet — log a few expenses and set budgets to see tailored advice.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {smartActions.map((action, i) => {
              const Icon = smartActionIcons[action.icon] || Lightbulb;
              return (
                <div key={i} className={cn("rounded-xl p-4 border-l-4 border border-border/50", priorityStyles[action.priority])}>
                  <div className="flex items-start gap-3">
                    <Icon className="w-4 h-4 mt-0.5 shrink-0 text-foreground" />
                    <div>
                      <p className="text-sm font-medium text-foreground">{action.title}</p>
                      <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{action.desc}</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Payment Method Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-card rounded-xl p-5 border border-border/50">
          <h3 className="text-sm font-semibold text-foreground mb-4">Payment Methods</h3>
          {paymentMethods.length === 0 ? (
            <div className="h-52 flex items-center justify-center">
              <p className="text-xs text-muted-foreground">No payment data this month yet.</p>
            </div>
          ) : (
            <>
              <div className="h-52">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={paymentMethods} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value" paddingAngle={3}>
                      {paymentMethods.map((entry, i) => (
                        <Cell key={i} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={chart.tooltipStyle} formatter={(val: number) => formatCurrency(val)} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="space-y-2 mt-2">
                {paymentMethods.map(p => {
                  const Icon = paymentIconMap[p.name] || Banknote;
                  return (
                    <div key={p.name} className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <Icon className="w-3 h-3 text-muted-foreground" />
                        <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: p.color }} />
                        <span className="text-muted-foreground">{p.name}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-foreground font-medium">{formatCurrency(p.value)}</span>
                        <span className="text-muted-foreground">({totalPayments > 0 ? Math.round(p.value / totalPayments * 100) : 0}%)</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>

        {/* Loans & EMIs */}
        <div className="bg-card rounded-xl p-5 border border-border/50">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-foreground">Loans & EMIs</h3>
            <span className="text-xs text-muted-foreground">Total EMI: <span className="text-foreground font-medium">{formatCurrency(totalEMI)}/mo</span></span>
          </div>
          {loansData.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-6">No loans on record.</p>
          ) : (
            <div className="space-y-4">
              {loansData.map((loan, i) => (
                <div key={i} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-foreground">{loan.type}</span>
                    <span className="text-xs text-muted-foreground">{loan.rate} APR</span>
                  </div>
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>EMI: {formatCurrency(loan.emi)}/mo</span>
                    <span>Remaining: {formatCurrency(loan.remaining)}</span>
                  </div>
                  <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
                    <div className="h-full bg-primary rounded-full" style={{ width: `${Math.min(100, 100 - (loan.remaining / (loan.emi * 240)) * 100)}%` }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-card rounded-xl p-5 border border-border/50">
          <h3 className="text-sm font-semibold text-foreground mb-4">Monthly Comparison</h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={monthlyData}>
                <XAxis dataKey="month" tick={{ fontSize: 10, fill: chart.tickFill }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: chart.tickFill }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={chart.tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="income" name="Income" fill="#10b981" radius={[4, 4, 0, 0]} />
                <Bar dataKey="expenses" name="Expenses" fill="#f43f5e" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-card rounded-xl p-5 border border-border/50">
          <h3 className="text-sm font-semibold text-foreground mb-4">Category Trends</h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trendsData}>
                <XAxis dataKey="month" tick={{ fontSize: 10, fill: chart.tickFill }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: chart.tickFill }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={chart.tooltipStyle} />
                {Object.keys(categoryColors).map(cat => (
                  <Line key={cat} type="monotone" dataKey={cat} stroke={categoryColors[cat]} strokeWidth={2} dot={false} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-card rounded-xl p-5 border border-border/50">
          <h3 className="text-sm font-semibold text-foreground mb-4">Savings Over Time</h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={monthlyData}>
                <XAxis dataKey="month" tick={{ fontSize: 10, fill: chart.tickFill }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: chart.tickFill }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={chart.tooltipStyle} />
                <Area type="monotone" dataKey="savings" fill="#10b981" fillOpacity={0.2} stroke="#10b981" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-card rounded-xl p-5 border border-border/50">
          <h3 className="text-sm font-semibold text-foreground mb-4">Top Spending Categories</h3>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={horizontalData} layout="vertical">
                <XAxis type="number" tick={{ fontSize: 10, fill: chart.tickFill }} axisLine={false} tickLine={false} />
                <YAxis dataKey="name" type="category" tick={{ fontSize: 10, fill: chart.tickFill }} axisLine={false} tickLine={false} width={100} />
                <Tooltip contentStyle={chart.tooltipStyle} />
                <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                  {horizontalData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* AI Report */}
      <div className="bg-card rounded-xl p-5 border-l-4 border-l-secondary border border-border/50 print-report">
        <div className="flex items-center gap-2 mb-4">
          <Bot className="w-4 h-4 text-secondary" />
          <h3 className="text-sm font-semibold text-foreground">AI Financial Report</h3>
          <span className="text-xs text-muted-foreground ml-auto">{format(new Date(), "MMM d, yyyy")}</span>
        </div>
        {aiReportText ? (
          <div className="space-y-3 text-xs text-muted-foreground leading-relaxed whitespace-pre-wrap">
            {aiReportText}
          </div>
        ) : (
          <div className="text-center py-8">
            <p className="text-sm text-muted-foreground mb-3">No AI report generated yet.</p>
            <Button size="sm" onClick={generateAiReport} disabled={generating}>
              {generating ? <RefreshCw className="w-3 h-3 mr-1.5 animate-spin" /> : <Bot className="w-3 h-3 mr-1.5" />}
              {generating ? "Generating..." : "Generate AI Report Now"}
            </Button>
          </div>
        )}
        {aiReportText && (
          <div className="mt-4">
            <Button variant="outline" size="sm" className="border-secondary text-secondary hover:bg-secondary/10 text-xs" onClick={generateAiReport} disabled={generating}>
              <RefreshCw className="w-3 h-3 mr-1.5" />Regenerate
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
