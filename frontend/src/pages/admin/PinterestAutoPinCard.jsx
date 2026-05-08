/**
 * PinterestAutoPinCard
 *
 * Admin card on /admin/seo for the Pinterest auto-publish integration
 * driven by the Editorial Autopilot.
 *
 * State machine:
 *   1. App credentials NOT set → big amber "Setup needed" panel with
 *      step-by-step copy-paste-ready instructions for the user to
 *      create a Pinterest dev app and add 2 env vars on Railway.
 *   2. App credentials set, NOT connected → green "Connect Pinterest"
 *      button that pops the Pinterest authorize URL in a new tab.
 *   3. Connected, no board → board picker dropdown.
 *   4. Connected + board → green "ACTIVE" status, every Editorial
 *      Autopilot article auto-pins. Disconnect button to revoke.
 *
 * Listens for the OAuth callback's `?pinterest=connected` URL param
 * and refreshes itself when it sees one.
 */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useSearchParams } from 'react-router-dom';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import {
  Loader2, RefreshCw, ExternalLink, AlertTriangle, Copy,
  CheckCircle2, Image as ImageIcon, Unplug,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const tok = () => `Bearer ${localStorage.getItem('token') || localStorage.getItem('access_token') || ''}`;


const CopyableField = ({ label, value, testid }) => {
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      toast.success(`${label} copied`);
    } catch (_e) { toast.error('Copy failed'); }
  };
  return (
    <div className="flex items-center gap-2 bg-slate-100 rounded p-2 border border-slate-200">
      <div className="flex-1 min-w-0">
        <div className="text-[10px] uppercase tracking-widest text-slate-500 font-bold">{label}</div>
        <div className="font-mono text-xs text-slate-900 truncate" data-testid={testid}>{value}</div>
      </div>
      <button
        type="button"
        onClick={copy}
        className="text-slate-500 hover:text-slate-900 px-1.5 py-1 rounded hover:bg-slate-200"
        title="Copy"
      >
        <Copy className="w-3.5 h-3.5" />
      </button>
    </div>
  );
};


const PinterestAutoPinCard = () => {
  const [params, setParams] = useSearchParams();
  const [status, setStatus] = useState(null);
  const [boards, setBoards] = useState([]);
  const [busy, setBusy] = useState(false);
  const [boardChoice, setBoardChoice] = useState('');

  const load = async (silent = false) => {
    try {
      const r = await axios.get(`${API_URL}/api/admin/pinterest/status`, {
        headers: { Authorization: tok() },
      });
      setStatus(r.data);
      if (r.data.connected && !r.data.board_id) {
        // Pre-fetch boards so the dropdown is populated immediately
        const b = await axios.get(`${API_URL}/api/admin/pinterest/boards`, {
          headers: { Authorization: tok() },
        });
        setBoards(b.data?.boards || []);
      }
    } catch (e) {
      if (!silent) toast.error(e?.response?.data?.detail || 'Could not load Pinterest status');
    }
  };

  useEffect(() => { load(); }, []);

  // Detect OAuth callback redirect
  useEffect(() => {
    const flag = params.get('pinterest');
    if (!flag) return;
    if (flag === 'connected') {
      toast.success('Pinterest connected — pick a board below');
      load();
    } else if (flag === 'denied') {
      toast.error('Pinterest authorisation cancelled');
    } else if (flag === 'failed') {
      const detail = params.get('detail') || '';
      toast.error(`Pinterest connect failed: ${detail.slice(0, 160)}`);
    }
    // Clean the URL so we don't re-fire on next render
    params.delete('pinterest');
    params.delete('error');
    params.delete('detail');
    setParams(params, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const startConnect = async () => {
    setBusy(true);
    try {
      const r = await axios.get(`${API_URL}/api/admin/pinterest/authorize-url`, {
        headers: { Authorization: tok() },
      });
      window.open(r.data.url, '_self');  // Pinterest will redirect us back
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not start Pinterest connection');
      setBusy(false);
    }
  };

  const saveBoard = async () => {
    if (!boardChoice) {
      toast.error('Pick a board first');
      return;
    }
    setBusy(true);
    try {
      const board = boards.find((b) => b.id === boardChoice);
      await axios.post(`${API_URL}/api/admin/pinterest/board`,
        { board_id: boardChoice, board_name: board?.name },
        { headers: { Authorization: tok() } });
      toast.success(`Pinning to "${board?.name || boardChoice}" — every new article auto-pins from now on`);
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not save board');
    } finally { setBusy(false); }
  };

  const disconnect = async () => {
    if (!window.confirm(
      'Disconnect Pinterest?\n\n'
      + 'New articles will stop auto-pinning. You can reconnect any time '
      + 'with one click — your dev-app credentials stay configured.',
    )) return;
    setBusy(true);
    try {
      await axios.post(`${API_URL}/api/admin/pinterest/disconnect`, {},
        { headers: { Authorization: tok() } });
      toast.success('Pinterest disconnected');
      setBoards([]);
      setBoardChoice('');
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not disconnect');
    } finally { setBusy(false); }
  };

  if (!status) {
    return (
      <Card className="p-6 flex items-center gap-2 text-slate-500" data-testid="pinterest-card-loading">
        <Loader2 className="w-5 h-5 animate-spin" /> Loading Pinterest status…
      </Card>
    );
  }

  const isReady = status.connected && status.board_id;

  return (
    <Card
      className={`overflow-hidden border-2 ${isReady ? 'border-rose-300' : 'border-slate-200'}`}
      data-testid="pinterest-autopin-card"
    >
      <div className="bg-gradient-to-r from-rose-700 to-red-700 text-white px-5 py-4">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <ImageIcon className="w-6 h-6 text-rose-100" />
            <div>
              <div className="text-xs uppercase tracking-widest opacity-80 font-semibold">Pinterest Auto-Pin</div>
              <div className="text-lg font-bold">
                {isReady ? 'ACTIVE — every new article auto-pins to TileStation' : 'Connect Pinterest to compound your blog reach'}
              </div>
            </div>
          </div>
          {status.connected && (
            <Button size="sm" variant="ghost" onClick={() => load()} className="text-white hover:bg-white/10" data-testid="pinterest-refresh-btn">
              <RefreshCw className="w-4 h-4" />
            </Button>
          )}
        </div>
      </div>

      <div className="p-5 space-y-4">
        {/* Step 1 — App credentials missing */}
        {!status.app_credentials_set && (
          <div data-testid="pinterest-setup-needed">
            <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded mb-4">
              <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-amber-900">
                <div className="font-bold">One-time Pinterest dev-app setup needed (~5 min)</div>
                <div className="text-xs mt-0.5">After this, every new blog article auto-pins forever — no further setup needed.</div>
              </div>
            </div>

            <ol className="space-y-3 text-sm text-slate-800">
              <li className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-rose-600 text-white font-bold text-xs flex items-center justify-center">1</span>
                <div>
                  Go to <a className="font-semibold text-rose-700 underline" href="https://developers.pinterest.com/apps/" target="_blank" rel="noreferrer">developers.pinterest.com/apps</a>
                  <span className="text-slate-500"> · log in with the same Pinterest account that owns the board you want to pin to · click <strong>"Connect app"</strong>.</span>
                </div>
              </li>
              <li className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-rose-600 text-white font-bold text-xs flex items-center justify-center">2</span>
                <div>
                  In the form:
                  <ul className="text-xs text-slate-600 mt-1 ml-3 list-disc space-y-0.5">
                    <li>App name: <strong>TileStation Auto-Pinner</strong></li>
                    <li>Description: <em>"Auto-publish blog articles from tilestation.co.uk to a TileStation Pinterest board."</em></li>
                    <li>Website URL: <strong>https://tilestation.co.uk</strong></li>
                    <li>App use case: <strong>"I'm building my own tool or service"</strong></li>
                  </ul>
                  <div className="text-xs text-slate-500 mt-1">Submit. Trial Access is approved instantly for personal accounts.</div>
                </div>
              </li>
              <li className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-rose-600 text-white font-bold text-xs flex items-center justify-center">3</span>
                <div>
                  Open your new app → click <strong>"Configure"</strong> → in <strong>Redirect URIs</strong>, paste exactly the URI below and click <strong>"Save"</strong>:
                  <div className="mt-1.5">
                    <CopyableField label="Redirect URI" value={status.redirect_uri} testid="pinterest-redirect-uri" />
                  </div>
                </div>
              </li>
              <li className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-rose-600 text-white font-bold text-xs flex items-center justify-center">4</span>
                <div>
                  Stay on the app page. You'll see your <strong>App ID</strong> (a 16-digit number) and <strong>App Secret</strong> (a long random string). Copy both.
                </div>
              </li>
              <li className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-rose-600 text-white font-bold text-xs flex items-center justify-center">5</span>
                <div>
                  Add these to Railway → backend service → <strong>Variables</strong>:
                  <div className="mt-1.5 space-y-1.5">
                    <CopyableField label="Variable 1 name" value="PINTEREST_APP_ID" />
                    <CopyableField label="Variable 2 name" value="PINTEREST_APP_SECRET" />
                  </div>
                  <div className="text-xs text-slate-500 mt-1">Click "Deploy" on Railway. Once the backend redeploys, refresh this page and the "Connect Pinterest" button will appear.</div>
                </div>
              </li>
            </ol>

            <div className="text-xs text-slate-500 mt-4 pt-3 border-t border-slate-200">
              That's all the manual work — after these 5 minutes everything else (token refresh, board picking, pin creation) is fully automatic.
            </div>
          </div>
        )}

        {/* Step 2 — App creds set, not connected */}
        {status.app_credentials_set && !status.connected && (
          <div className="text-center py-6" data-testid="pinterest-connect-state">
            <ImageIcon className="w-12 h-12 text-rose-300 mx-auto mb-3" />
            <div className="text-base font-bold text-slate-900 mb-1">App credentials configured ✓</div>
            <div className="text-sm text-slate-600 mb-4">
              One click to connect your Pinterest account. You'll pop over to Pinterest, click <strong>Allow</strong>, and come straight back.
            </div>
            <Button
              onClick={startConnect}
              disabled={busy}
              className="bg-rose-600 hover:bg-rose-700 text-white font-bold"
              data-testid="pinterest-connect-btn"
            >
              {busy ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <ExternalLink className="w-4 h-4 mr-1.5" />}
              Connect Pinterest
            </Button>
          </div>
        )}

        {/* Step 3 — Connected, no board picked */}
        {status.connected && !status.board_id && (
          <div data-testid="pinterest-pick-board">
            <div className="flex items-center gap-2 p-3 bg-emerald-50 border border-emerald-200 rounded mb-4">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
              <div className="text-sm text-emerald-900 flex-1">
                <div className="font-bold">Connected as {status.user_id || 'your Pinterest account'}</div>
                <div className="text-xs">Now pick which board new articles will be pinned to.</div>
              </div>
            </div>
            {boards.length === 0 ? (
              <div className="text-sm text-slate-500 italic">
                No boards found on your account.{' '}
                <a href="https://www.pinterest.com/board/create/" target="_blank" rel="noreferrer" className="text-rose-700 underline font-semibold">
                  Create a board on Pinterest
                </a>{' '}then click "Refresh".
              </div>
            ) : (
              <div className="space-y-3">
                <select
                  value={boardChoice}
                  onChange={(e) => setBoardChoice(e.target.value)}
                  className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:ring-2 focus:ring-rose-500 focus:border-transparent"
                  data-testid="pinterest-board-select"
                >
                  <option value="">— Select a board —</option>
                  {boards.map((b) => (
                    <option key={b.id} value={b.id}>{b.name || b.id}</option>
                  ))}
                </select>
                <div className="flex gap-2 justify-end">
                  <Button variant="ghost" onClick={() => load()} disabled={busy}>
                    <RefreshCw className="w-4 h-4 mr-1" /> Refresh
                  </Button>
                  <Button
                    onClick={saveBoard}
                    disabled={busy || !boardChoice}
                    className="bg-rose-600 hover:bg-rose-700 text-white font-bold"
                    data-testid="pinterest-board-save-btn"
                  >
                    {busy ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <CheckCircle2 className="w-4 h-4 mr-1.5" />}
                    Use this board
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Step 4 — fully active */}
        {isReady && (
          <div data-testid="pinterest-active-state">
            <div className="flex items-center gap-3 p-3 bg-emerald-50 border border-emerald-200 rounded">
              <CheckCircle2 className="w-6 h-6 text-emerald-600 flex-shrink-0" />
              <div className="flex-1 text-sm">
                <div className="font-bold text-emerald-900">Pinning to {status.board_name || status.board_id}</div>
                <div className="text-xs text-slate-700 mt-0.5">
                  Every new Editorial Autopilot article auto-creates a Pin · token auto-refreshes ~5 days before expiry · failures are logged but never block article publishing.
                </div>
                {status.token_expires_at && (
                  <div className="text-[11px] text-slate-500 mt-1 font-mono">
                    Token valid until {new Date(status.token_expires_at).toLocaleDateString('en-GB')}
                  </div>
                )}
              </div>
              <Button variant="ghost" onClick={disconnect} disabled={busy} className="text-slate-500 hover:text-red-700" data-testid="pinterest-disconnect-btn">
                <Unplug className="w-4 h-4 mr-1" /> Disconnect
              </Button>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
};

export default PinterestAutoPinCard;
