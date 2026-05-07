/**
 * handsFreeBridge — wraps the native HandsFree Capacitor plugin (Phase B).
 *
 * On web (preview / vercel), all calls are no-ops and `start()` returns
 * `{ started: false, reason: "web" }`. On native Android the user can flip
 * a toggle (Settings → Always-on hands-free) which calls `startHandsFree()`.
 *
 * Model files (hi_yaar.ppn, porcupine_params.pv, eagle_params.pv) live in
 * the React build output (frontend/public/models/). At runtime we copy them
 * to the app's filesDir so the native side has stable on-disk paths.
 */
import { Capacitor, registerPlugin } from "@capacitor/core";
import { Filesystem, Directory, Encoding } from "@capacitor/filesystem";

const HandsFree = registerPlugin("HandsFree");

export const isNative = () => Capacitor.isNativePlatform();

const MODEL_FILES = [
  "hi_yaar.ppn",
  "porcupine_params.pv",
  "eagle_params.pv",
];

async function copyModel(filename) {
  // Fetch the file from the WebView's hosted assets (Vercel)
  const url = `${window.location.origin}/models/${filename}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Could not fetch ${filename}: ${res.status}`);
  const buf = await res.arrayBuffer();
  // Convert to base64 (Filesystem can't take binary directly)
  let bin = "";
  const bytes = new Uint8Array(buf);
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  const b64 = btoa(bin);

  await Filesystem.writeFile({
    path: filename,
    data: b64,
    directory: Directory.Data,
    recursive: true,
  });
  const { uri } = await Filesystem.getUri({
    path: filename,
    directory: Directory.Data,
  });
  return uri.replace(/^file:\/\//, ""); // native plugins want a plain path
}

let cachedPaths = null;
async function ensureModels() {
  if (cachedPaths) return cachedPaths;
  const out = {};
  for (const f of MODEL_FILES) {
    try {
      out[f] = await copyModel(f);
    } catch (e) {
      console.warn("[HandsFree] model copy failed:", f, e?.message);
    }
  }
  cachedPaths = out;
  return out;
}

/**
 * Start the always-on listening service.
 * @param {{accessKey: string, profileBase64?: string, threshold?: number}} opts
 */
export async function startHandsFree(opts) {
  if (!isNative()) return { started: false, reason: "web" };
  if (!opts?.accessKey) return { started: false, reason: "no-access-key" };

  const paths = await ensureModels();
  if (!paths["hi_yaar.ppn"] || !paths["porcupine_params.pv"]) {
    return { started: false, reason: "missing-models" };
  }

  try {
    const result = await HandsFree.start({
      accessKey: opts.accessKey,
      keywordPath: paths["hi_yaar.ppn"],
      porcupineModelPath: paths["porcupine_params.pv"],
      eagleModelPath: paths["eagle_params.pv"] || null,
      profileBase64: opts.profileBase64 || null,
      threshold: opts.threshold ?? 0.6,
    });
    return { started: !!result?.started };
  } catch (e) {
    return { started: false, reason: e?.message || "unknown" };
  }
}

export async function stopHandsFree() {
  if (!isNative()) return;
  try {
    await HandsFree.stop();
  } catch {}
}

/**
 * Subscribe to native wake events. Callback fires when "Hi Yaar" is detected
 * by the foreground service (and passes voiceprint check if enrolled).
 * Returns an unsubscribe function.
 */
export function onHandsFreeWake(callback) {
  if (!isNative()) return () => {};
  let listener;
  HandsFree.addListener("wake", (ev) => {
    callback(ev || {});
  }).then((l) => { listener = l; });
  return () => {
    try { listener?.remove?.(); } catch {}
  };
}
