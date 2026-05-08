/**
 * LifetimeSavingsCard
 * ───────────────────
 * The £-savings calculator at the top of /admin/seo. Quantifies how
 * much money the autopilot stack has saved vs equivalent UK SEO/
 * marketing agency rates.
 *
 * Conservative rates so the headline number is defensible:
 *   • Article: £600  • City page: £200  • Banner: £150  • Video: £400
 *   • Stealth-keyword promotion: £75  • Per-product meta: £15
 *
 * Single API call to /api/admin/seo/stealth-keywords/lifetime-savings
 * returns the breakdown. No autorefresh — admin clicks Refresh when
 * they want fresh numbers.
 */
import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Loader2, RefreshCw, PoundSterling, TrendingUp, ChevronDown, ChevronUp, Calendar } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const token = () => localStorage.getItem('token') || localStorage.getItem('access_token') || '';

const fmtMoney = (n, decimals = 0) =>
  n == null
    ? '—'
    : `£${Number(n).toLocaleString('en-GB', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })}`;

const fmtNum = (n) => (n == null ? '—' : Number(n).toLocaleString('en-GB'));

const LifetimeSavingsCard = () => {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const load = useCallback(async (force = false) => {
    setRefreshing(force);
    try {
      const r = await axios.get(
        `${API_URL}/api/admin/seo/stealth-keywords/lifetime-savings`,
        { headers: { Authorization: `Bearer ${token()}` }, timeout: 30000 },
      );
      setReport(r.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not load savings report');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load(false);
  }, [load]);

  if (loading) {
    return (
      <Card className="p-5 flex items-center gap-2 text-slate-500" data-testid="lifetime-savings-loading">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading lifetime savings…
      </Card>
    );
  }
  if (!report) return null;

  const totals = report.totals || {};
  const breakdown = report.breakdown || [];

  return (
    <Card
      className="overflow-hidden border-emerald-200 shadow-md"
      data-testid="lifetime-savings-card"
    >
      <div className="bg-gradient-to-br from-emerald-700 via-emerald-800 to-teal-900 text-white px-6 py-5">
        <div className="flex items-start justify-between flex-wrap gap-3">
          <div className="min-w-0">
            <div className="text-[10px] uppercase tracking-widest text-emerald-200 font-semibold">
              Lifetime savings · agency vs autopilot
            </div>
            <h2 className="text-2xl font-bold mt-1 flex items-center gap-2">
              <PoundSterling className="w-6 h-6 text-yellow-300" />
              <span data-testid="lifetime-savings-net">{fmtMoney(totals.net_savings_gbp)}</span>
              <span className="text-sm text-emerald-200/90 font-normal">net saved so far</span>
            </h2>
            <div className="text-xs text-emerald-100/80 mt-1.5 flex flex-wrap gap-x-3 gap-y-1">
              <span>
                <Calendar className="w-3 h-3 inline mr-1" />
                <strong>{totals.days_running}</strong> days running
              </span>
              <span>
                ≈ <strong>{fmtMoney(totals.per_day_savings_gbp, 2)}</strong>/day
              </span>
              <span>
                <TrendingUp className="w-3 h-3 inline mr-0.5" />
                <strong>{fmtMoney(totals.monthly_run_rate_gbp)}</strong>/month run-rate
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setExpanded((v) => !v)}
              className="text-white hover:bg-white/10"
              data-testid="lifetime-savings-toggle"
            >
              {expanded ? (
                <>
                  <ChevronUp className="w-4 h-4 mr-1" /> Hide breakdown
                </>
              ) : (
                <>
                  <ChevronDown className="w-4 h-4 mr-1" /> Show breakdown
                </>
              )}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => load(true)}
              disabled={refreshing}
              className="text-white hover:bg-white/10"
              data-testid="lifetime-savings-refresh"
            >
              {refreshing ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4" />
              )}
            </Button>
          </div>
        </div>
      </div>

      {/* Headline tiles */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-px bg-emerald-100">
        <Tile
          label="Agency-equivalent value"
          value={fmtMoney(totals.agency_equivalent_gbp)}
          tone="emerald"
          testid="tile-agency-value"
        />
        <Tile
          label="Actual AI spend"
          value={fmtMoney(totals.actual_ai_spend_gbp, 2)}
          tone="amber"
          testid="tile-ai-spend"
          subtext="Real cost of LLM + image + video calls"
        />
        <Tile
          label="Net savings"
          value={fmtMoney(totals.net_savings_gbp)}
          tone="violet"
          testid="tile-net-savings"
          subtext="Agency-equivalent minus actual AI spend"
        />
      </div>

      {/* Breakdown table — collapsed by default */}
      {expanded && (
        <div className="p-5 space-y-3 bg-white" data-testid="lifetime-savings-breakdown">
          <div className="text-xs text-slate-500 italic">
            Based on conservative UK agency rates (low end of typical quotes).
            Numbers update live as the autopilot publishes more content.
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-[11px] uppercase tracking-wide text-slate-500 border-b">
                  <th className="text-left py-2 pr-3">Output</th>
                  <th className="text-right pr-3">Count</th>
                  <th className="text-right pr-3">Rate</th>
                  <th className="text-right">Saved</th>
                </tr>
              </thead>
              <tbody>
                {breakdown.map((row) => (
                  <tr
                    key={row.key}
                    className="border-b last:border-b-0 hover:bg-slate-50 transition"
                    data-testid={`savings-row-${row.key}`}
                  >
                    <td className="py-2 pr-3">
                      <div className="font-semibold text-slate-900">{row.label}</div>
                      <div className="text-[11px] text-slate-500">{row.explainer}</div>
                    </td>
                    <td className="text-right pr-3 font-mono font-bold text-slate-900">
                      {fmtNum(row.count)}
                    </td>
                    <td className="text-right pr-3 font-mono text-slate-600">
                      {fmtMoney(row.rate_gbp)}
                    </td>
                    <td className="text-right font-mono font-bold text-emerald-700">
                      {fmtMoney(row.value_gbp)}
                    </td>
                  </tr>
                ))}
                <tr className="bg-emerald-50">
                  <td className="py-2 pr-3 font-bold text-emerald-900">Total agency-equivalent value</td>
                  <td colSpan={2} />
                  <td className="text-right font-mono font-bold text-emerald-900">
                    {fmtMoney(totals.agency_equivalent_gbp)}
                  </td>
                </tr>
                <tr>
                  <td className="py-2 pr-3 italic text-slate-700">Less: actual AI spend</td>
                  <td colSpan={2} />
                  <td className="text-right font-mono italic text-amber-700">
                    −{fmtMoney(totals.actual_ai_spend_gbp, 2)}
                  </td>
                </tr>
                <tr className="border-t-2 border-emerald-700 bg-emerald-100">
                  <td className="py-2 pr-3 font-bold text-emerald-950">Net savings</td>
                  <td colSpan={2} />
                  <td className="text-right font-mono font-bold text-emerald-950 text-base">
                    {fmtMoney(totals.net_savings_gbp)}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Card>
  );
};

const Tile = ({ label, value, tone = 'emerald', subtext, testid }) => {
  const tones = {
    emerald: 'bg-emerald-50 text-emerald-900',
    amber: 'bg-amber-50 text-amber-900',
    violet: 'bg-violet-50 text-violet-900',
  };
  return (
    <div className={`p-4 ${tones[tone]}`} data-testid={testid}>
      <div className="text-[10px] uppercase tracking-wide font-semibold opacity-80">{label}</div>
      <div className="text-2xl font-bold font-mono mt-1">{value}</div>
      {subtext && <div className="text-[10px] opacity-70 mt-0.5">{subtext}</div>}
    </div>
  );
};

export default LifetimeSavingsCard;
