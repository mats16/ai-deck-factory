// Google Vids の内部 API のクライアント（../internal_api.md）。docs.google.com のタブの中で動かす。
// 認証は、そのタブの Cookie（docs.google.com の呼び出し）と、Cookie から作る SAPISIDHASH（genai の呼び出し）。
// token・Cookie・署名は、このタブの外へ返さない（戻り値は ID・件数・長さだけ）。
// vids.py が Runtime.evaluate で読み込み、VidsClient.createFromSlides(...) を呼ぶ。
(() => {
  const GENAI = "https://appsgenaiserver-pa.clients6.google.com/v1/genai/";

  const md5b64 = (() => { // 台本の MD5（Base64）。音声の要素の 194 に入れる（台本と音声が合っているかの印。違うと Voiceover outdated）
    const K = Array.from({ length: 64 }, (_, i) => Math.floor(Math.abs(Math.sin(i + 1)) * 2 ** 32) >>> 0);
    const S = [7, 12, 17, 22, 5, 9, 14, 20, 4, 11, 16, 23, 6, 10, 15, 21];
    return (str) => {
      const msg = new TextEncoder().encode(str), n = ((msg.length + 8 >> 6) + 1) * 64, b = new Uint8Array(n);
      b.set(msg); b[msg.length] = 0x80;
      const dv = new DataView(b.buffer); dv.setUint32(n - 8, msg.length * 8, true); dv.setUint32(n - 4, Math.floor(msg.length / 2 ** 29), true);
      let [a0, b0, c0, d0] = [0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476];
      for (let o = 0; o < n; o += 64) {
        let [A, B, C, D] = [a0, b0, c0, d0];
        for (let i = 0; i < 64; i++) {
          const r = i >> 4; let F, g;
          if (r === 0) { F = (B & C) | (~B & D); g = i; } else if (r === 1) { F = (D & B) | (~D & C); g = (5 * i + 1) % 16; }
          else if (r === 2) { F = B ^ C ^ D; g = (3 * i + 5) % 16; } else { F = C ^ (B | ~D); g = (7 * i) % 16; }
          F = (F + A + K[i] + dv.getUint32(o + g * 4, true)) >>> 0; A = D; D = C; C = B;
          const s = S[r * 4 + (i & 3)]; B = (B + ((F << s) | (F >>> (32 - s)))) >>> 0;
        }
        a0 = (a0 + A) >>> 0; b0 = (b0 + B) >>> 0; c0 = (c0 + C) >>> 0; d0 = (d0 + D) >>> 0;
      }
      const out = new Uint8Array(16), ov = new DataView(out.buffer);
      [a0, b0, c0, d0].forEach((v, i) => ov.setUint32(i * 4, v, true));
      return btoa(String.fromCharCode(...out));
    };
  })();

  async function authorization() { // ブラウザーが genai に付けるのと同じ SAPISIDHASH。値はこの関数の外に出さない
    const jar = Object.fromEntries(document.cookie.split("; ").map((s) => [s.slice(0, s.indexOf("=")), s.slice(s.indexOf("=") + 1)]));
    const ts = Math.floor(Date.now() / 1000), parts = [];
    for (const [name, cookie] of [["SAPISIDHASH", "SAPISID"], ["SAPISID1PHASH", "__Secure-1PAPISID"], ["SAPISID3PHASH", "__Secure-3PAPISID"]]) {
      if (!jar[cookie]) continue;
      const d = await crypto.subtle.digest("SHA-1", new TextEncoder().encode(`${ts} ${jar[cookie]} ${location.origin}`));
      parts.push(`${name} ${ts}_${[...new Uint8Array(d)].map((x) => x.toString(16).padStart(2, "0")).join("")}`);
    }
    if (!parts.length) throw new Error("SAPISID の Cookie がない（docs.google.com にログインしていない）");
    return parts.join(" ");
  }

  const parse = (t) => JSON.parse(t.replace(/^\)\]\}'\s*/, ""));

  async function genai(doc, method, body) { // キーは、編集画面が genai に付ける公開のキー（HTML の espresso_api_key）
    const r = await fetch(`${GENAI}${method}?key=${doc.key}`, {
      method: "POST", credentials: "include", body: JSON.stringify(body),
      headers: { "Content-Type": "application/json+protobuf", "X-Goog-AuthUser": "0", Authorization: await authorization() },
    });
    const t = await r.text();
    if (!r.ok) throw new Error(`genai ${method}: HTTP ${r.status} ${t.slice(0, 300)}`);
    return parse(t);
  }

  async function editPage(vidsId) { // 編集画面の HTML の info_params（token・ouid）と、文書のモデルの塊
    const t = await (await fetch(`/videos/d/${vidsId}/edit`, { credentials: "include" })).text();
    const info = t.match(/"info_params":(\{[^}]*\})/), chunks = [...t.matchAll(/var modelChunk = (\{.*?\}); var modelChunkParseEnd/gs)].map((m) => JSON.parse(m[1]));
    if (!info || !chunks.length) throw new Error(`Vids ${vidsId} の編集画面を読めない（ログインの画面か、画面の作りが変わった）`);
    return { info: JSON.parse(info[1]), key: t.match(/"espresso_api_key":"([\w-]+)"/)?.[1], chunks };
  }

  async function openDoc(vidsId) { // 編集画面の HTML から、token・ouid・リビジョン。sid は自分で作る（16 桁の 16 進）
    const { info, key, chunks } = await editPage(vidsId);
    if (!key) throw new Error("編集画面に genai のキー（espresso_api_key）がない");
    const rev = Math.max(...chunks.map((c) => c.revision));
    const sid = [...crypto.getRandomValues(new Uint8Array(8))].map((x) => x.toString(16).padStart(2, "0")).join("");
    return { id: vidsId, token: info.token, ouid: info.ouid, key, rev, sid, reqId: 0, ph: 0, waited: [], model: chunks.flatMap((c) => c.chunk) };
  }

  async function docs(doc, path, form, extra = {}) {
    const q = new URLSearchParams({ id: doc.id, ...extra, token: doc.token, ouid: doc.ouid });
    const r = await fetch(`/videos/u/0/d/${doc.id}/${path}?${q}`, {
      method: "POST", credentials: "include", body: new URLSearchParams(form),
      headers: { "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8", "X-Same-Domain": "1" },
    });
    const t = await r.text();
    if (!r.ok) throw new Error(`${path}: HTTP ${r.status} ${t.slice(0, 300)}`);
    return parse(t);
  }

  // 保存は、ときどき 550 で断られる（[["er",…,550,…],["di",<40〜63>]]。断られた保存は何も書かない）。短い間に保存を重ねたあと（同じ Vids にも、同じアカウントの
  // ほかの Vids にも）に続き、5〜10 分保存しないと通る（2026-10-22）。di の意味は分からない。同じ sid・reqId のまま、di より 5 秒長く待ち、版を読み直して送り直す（3 回まで）
  async function save(doc, commands, blobIdMap = {}) {
    const reqId = doc.reqId++;
    for (let tries = 0; ; tries++) {
      try {
        const res = await docs(doc, "save", {
          rev: String(doc.rev), bundles: JSON.stringify([{ commands, sid: doc.sid, reqId }]),
          ...(Object.keys(blobIdMap).length ? { blobIdMap: JSON.stringify(blobIdMap) } : {}),
        }, { sid: doc.sid, vc: "1", c: "1", w: "1", flr: "0", smb: "[9, ]" });
        doc.rev = res.revisionRanges.at(-1).at(-1);
        return res;
      } catch (e) {
        if (tries === 3 || !String(e).includes("HTTP 550")) throw e;
        const di = Number(String(e).match(/"di",(\d+)/)?.[1] ?? 60);
        doc.waited.push(di + 5);
        await new Promise((r) => setTimeout(r, (di + 5) * 1000));
        doc.rev = Math.max(doc.rev, ...(await editPage(doc.id)).chunks.map((c) => c.revision));
      }
    }
  }

  const placeholder = (doc) => `PLACEHOLDER_${doc.sid}_${doc.ph++}`;

  async function insertMedia(doc, type, items) { // items: {key: si}。戻り値 {key: {ni: Drive の media ID, sb: バイト数}}
    const req = Object.fromEntries(Object.entries(items).map(([k, si]) => [k, { si, mi: "0", bs: "0", mt: "", cs: {}, me: type }]));
    const res = await docs(doc, "insertmedia", { insertable_media_type: type, insert_media_requests: JSON.stringify(req) });
    for (const [k, v] of Object.entries(res)) if (v.ms !== "OK") throw new Error(`insertmedia ${type} ${k}: ${v.ms}`);
    return res;
  }

  function findString(x, pred) {
    if (typeof x === "string") return pred(x) ? x : null;
    if (Array.isArray(x)) for (const y of x) { const r = findString(y, pred); if (r) return r; }
    return null;
  }

  function findList(x, pred) {
    if (!Array.isArray(x)) return null;
    if (pred(x)) return x;
    for (const y of x) { const r = findList(y, pred); if (r) return r; }
    return null;
  }

  const ctx = (sel, seq, extra) => [sel, null, [9, null, null, null, `goog_${Date.now() % 1e9}`, null, String(seq), null, ...extra]];
  const flix = (id) => [null, null, null, [[[null, null, null, null, null, null, null, [null, null, [[id, "application/vnd.google-apps.flix", null, null, 1]]]]]]];

  // 下書き（シーンの組み立て）を作る。台本は自分で渡すので、台本の生成（[0][0]=144）は呼ばない
  function draftBody(vidsId, slidesId, scenes, preset) {
    const head = ctx(33, 1, [flix(vidsId), null, null, [5, 0], null, "en", null, null, null, null, null, 1, null, null, null, null, null,
      [[[[slidesId, "application/vnd.google-apps.punch", null, null, null, null, null, null, null, null, null, [null, [scenes.map((s) => s.pageId)]]]]]],
      null, null, null, null, null, null, null, null, Intl.DateTimeFormat().resolvedOptions().timeZone, null, null, null, null, null, 0, null, null, null, null, [1]]);
    const scene = (s) => [null, [null, null, null, null, null, null, null, null, null, null, null, null, null,
      [s.pageId, null, [null, null, s.script, [[[null, null, s.script], [null, null, "THIRD_PERSON"]]]]]]];
    const n28 = Array(28).fill(null);
    return [[...head, [...n28, [null, [null, null, null, [[[null, null, null, null, null, null, null, null, [null, scenes.map(scene)]]]]]]],
      [null, null, null, [[null, null, 120000, 5700000, 4294967296, 2, null, null, [preset]], ["1WWzyK6Af7VxPVBAzmDfI8DgS0G4W9-GPyvFXxrL42KU", 1], null, 2, 2]], null, 1], [1, null, 1]];
  }

  function ttsBody(script, voice) {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    return [...ctx(254, 3, [null, null, null, [16, 0], null, "en", ...Array(5).fill(null), 1, ...Array(14).fill(null), tz, ...Array(5).fill(null), 0]),
      [null, null, script], [...Array(25).fill(null), [voice]], null, 1];
  }

  const DOC_LEVEL = (c) => [1, 45, 13].includes(c[0]) || (c[0] === 18 && c[1]?.[0] === "n") || (c[0] === 12 && c[1] === "flix-master");
  const props = (p) => { const o = new Map(); for (let i = 0; i + 1 < p.length; i += 2) o.set(p[i], p[i + 1]); return o; };
  const flat = (m) => [...m].flat();

  // Slides のページをすべて Vids のシーンにし、ページごとの台本を Conversational voice で読ませる。
  // scenes: [{pageId, script}]（Slides のページの objectId と、そのページのノート）。voice: genai の声の名前（Elio は Achird）
  async function createFromSlides({ vidsId, slidesId, scenes, voice = "Achird", label = "Elio", preset, music = true }) {
    const doc = await openDoc(vidsId);
    const draft = await genai(doc, "streamGenerate", draftBody(vidsId, slidesId, scenes, preset || "docs-preset-voice-achird"));
    const modelStr = findString(draft, (s) => s.startsWith('[["[[4,'));
    if (!modelStr) throw new Error("下書きの応答にシーンのコマンドがない");
    const [cmdStr, , assets] = JSON.parse(modelStr)[0];
    const groups = JSON.parse(cmdStr).map((g) => g[1].filter((c) => !DOC_LEVEL(c)));
    const sceneIds = groups.map((g) => g.find((c) => c[0] === 12)?.[1]);
    if (sceneIds.includes(undefined)) throw new Error("下書きの応答に、シーンのないまとまりがある（下書きの形が変わった）");
    if (sceneIds.length !== scenes.length) throw new Error(`下書きのシーンが ${sceneIds.length}、ページが ${scenes.length}（音声を別のシーンに置かないよう止める）`);
    const size = Object.fromEntries(assets.filter((a) => Array.isArray(a[2])).map((a) => [a[0], a[2][2]]));

    // 画像: 元の Slides の blob を、この Vids に写す
    const blobs = new Set();
    for (const g of groups) for (const c of g) if (c[0] === 3) { const v = props(c[4] || []).get(49); if (v) blobs.add(v); }
    const copied = blobs.size ? await docs(doc, "copyimages", { photo_info: JSON.stringify(Object.fromEntries([...blobs].map((b) => [b, { it: "EXISTING_IMAGE_EMBEDDED", uc: "DEFAULT", pdi: slidesId, pdt: "punch" }]))) }) : {};
    const blobIdMap = {}, ph = {};
    for (const b of blobs) {
      if (!copied[b]) throw new Error("copyimages: Slides の画像を写せなかった");
      ph[b] = placeholder(doc); blobIdMap[ph[b]] = copied[b];
    }
    for (const g of groups) for (const c of g) if (c[0] === 3 && Array.isArray(c[4])) {
      const p = props(c[4]);
      if (!p.has(49)) continue;
      p.set(49, ph[p.get(49)]); p.delete(39);
      if (size[c[1]]) { p.set(8, size[c[1]][0]); p.set(9, size[c[1]][1]); }
      c[4] = flat(p);
    }

    // 音声: シーンごとに Conversational voice で読ませ、取り込んで置く
    const audio = [], durations = [];
    for (const [i, s] of scenes.entries()) {
      if (!s.script) { durations.push(null); continue; }
      const v = await voiceover(doc, blobIdMap, sceneIds[i], s.script, voice, label, `${sceneIds[i]}_vo`);
      audio.push(...v.commands); durations.push(v.ms);
    }

    // BGM: 下書きが選んだ曲（Shutterstock）
    const bgm = assets.find((a) => a[0] === "background-audio");
    if (music && bgm) {
      const [src, , [sec, nanos], , title] = bgm[3];
      const got = (await insertMedia(doc, "LMS_AUDIO", { [src]: { si: src, ki: 1 } }))[src];
      const p = placeholder(doc); blobIdMap[p] = got.ni;
      audio.push([58, `${sceneIds[0]}_bgm`, [118, 20, 158, 2, 173, 0, 175, 1800, 176, sec * 1000 + Math.round(nanos / 1e6), 177, 2,
        181, `${title} (Provided by Shutterstock)`, 184, sceneIds[0], 190, 2, 200, 1, 204, -6, 58, p]]);
    }

    // 元からあるシーン（空の Vids の 5 秒の空シーン "p"、--rebuild の古いシーン）を消す。[13, 今の並びの位置, 0, null, id] は画面の Delete と同じ
    // 同じ保存に入れると 550 になるので、組んだあとの保存で消す。音声の付いたシーンは消せない（550）ので、先に音声を [59] で消す
    const { scenes: old, media } = state(doc.model);
    await save(doc, [[20], [4, groups.flat()], [4, audio]], blobIdMap); // [20] は画面の最初の保存にあった。文字のコマンドと一緒に送ると 550
    const oldMedia = Object.keys(media).filter((m) => old.includes(media[m]));
    if (oldMedia.length) await save(doc, [[4, oldMedia.map((m) => [59, m])]]);
    const now = state((await editPage(doc.id)).chunks.flatMap((c) => c.chunk)).scenes; // 新しいシーンの入った並び
    for (const id of old.filter((x) => now.includes(x)).sort((a, b) => now.indexOf(b) - now.indexOf(a))) // 後ろから消すと、前の位置は変わらない
      await save(doc, [[13, now.indexOf(id), 0, null, id]]);
    return { vidsId, scenes: sceneIds.length, voiced: durations.filter((d) => d).length, durationsMs: durations, music: !!(music && bgm), revision: doc.rev, waited: doc.waited };
  }

  // 文書のモデル（コマンドの並び）から: シーンの ID（並びの順）、シーンの台本の文字、シーンの音声の要素
  function state(model) {
    const scenes = [], text = {}, voice = {}, media = {}; // media: 要素の ID → 付いているシーン（音声・BGM）
    for (const c of model) {
      if (c[0] === 12 && c[3] === 0) scenes.push(c[1]);
      else if (c[0] === 13 && scenes.includes(c[4])) scenes.splice(scenes.indexOf(c[4]), 1); // シーンを消す [13, 位置, 0, null, ID]
      else if (c[0] === 15) { const t = text[c[1]] ?? ""; text[c[1]] = t.slice(0, c[3]) + c[4] + t.slice(c[3]); } // 文字を入れる [15, 枠, null, 位置, 文字]
      else if (c[0] === 16) { const t = text[c[1]] ?? ""; text[c[1]] = t.slice(0, c[3]) + t.slice(c[4]); }        // 消す [16, 枠, null, 始め, 終わり]
      else if (c[0] === 58) { const p = props(c[2]); media[c[1]] = p.get(184); if (p.get(177) === 3) voice[p.get(184)] = { id: c[1], md5: p.get(194), label: p.get(181) }; }
      else if (c[0] === 59) { delete media[c[1]]; for (const k of Object.keys(voice)) if (voice[k].id === c[1]) delete voice[k]; }
    }
    const script = (id) => (text[`${id}:notes_text`] ?? "").replace(/\n$/, "");
    return { scenes, script, voice, media };
  }

  // 1 シーンの音声を Conversational voice で作り、取り込む。戻り値は、置くコマンドと長さ（ミリ秒）
  async function voiceover(doc, blobIdMap, sceneId, script, voice, label, id) {
    const tts = await genai(doc, "generate", ttsBody(script, voice));
    const ref = findList(tts, (x) => x.length >= 4 && x[1] === "bard_storage" && x[3] === "lookup_temp_data");
    if (!ref) throw new Error(`シーン ${sceneId}: 音声の応答に一時ファイルがない`);
    const key = `bard_storagelookup_temp_data${ref[0]}`;
    const got = (await insertMedia(doc, "CONTRIB_SERVICE_AUDIO", { [key]: { si: { co: "bard_storage", sc: "lookup_temp_data", uk: ref[0] }, ki: 0 } }))[key];
    const ms = Math.round((Number(got.sb) - 44) / 48); // 24 kHz・16 bit・モノラルの WAV（2026-10-21 の実測で長さと一致）
    const p = placeholder(doc); blobIdMap[p] = got.ni;
    return { ms, commands: [[58, id, [118, 100, 158, 2, 173, 0, 176, ms, 177, 3, 181, `${script.replace(/\[[^\]]*\]/g, "").trim().slice(0, 20)} - ${label}`,
      184, sceneId, 194, md5b64(script), 200, 1, 202, 1, 58, p]], [18, [sceneId], [], [16, ms + 1]]] };
  }

  // 台本か声の違うシーンの、台本の文字と音声を差し替える。声は音声の名札（181 の「… - <声>」）で見る（途中で止まった声の替えも、回し直せば直る）。
  // 画面で台本を直して Update voiceover を押したときと同じ保存（文字は [16]・[15] を 1 回、音声は [4, [[59, 古い音声], [58, 新しい音声], [18, シーンの長さ]]] を 1 回）。
  // シーンの数が違えば何もしない
  async function updateVoiceovers({ vidsId, scripts, voice = "Achird", label = "Elio" }) {
    const doc = await openDoc(vidsId);
    const { scenes, script, voice: vo } = state(doc.model);
    if (scenes.length !== scripts.length) return { sceneCount: scenes.length, updated: [] };
    const updated = [];
    for (const [i, id] of scenes.entries()) {
      const s = scripts[i], cur = script(id);
      if (cur === s && (s ? vo[id]?.md5 === md5b64(s) && vo[id].label?.endsWith(` - ${label}`) : !vo[id])) continue;
      if (cur !== s) await save(doc, [...(cur ? [[16, `${id}:notes_text`, null, 0, cur.length]] : []), ...(s ? [[15, `${id}:notes_text`, null, 0, s]] : [])]);
      const blobIdMap = {}, cmds = vo[id] ? [[59, vo[id].id]] : [];
      if (s) cmds.push(...(await voiceover(doc, blobIdMap, id, s, voice, label, `${id}_vo_${doc.sid}`)).commands);
      else if (cmds.length) cmds.push([18, [id], [], [16, 5000]]); // 音声を外したシーンは、空の Vids の空シーンと同じ 5 秒にする（古い音声の長さのまま無音にしない）
      if (cmds.length) await save(doc, [[4, cmds]], blobIdMap);
      updated.push(i + 1);
    }
    return { sceneCount: scenes.length, updated, revision: doc.rev, waited: doc.waited };
  }

  // 読み直して確かめる: シーンの数、シーンごとに台本の文字が scripts と合うか、音声（177=3）の台本の MD5（194）が合うか（音声がなければ null）、
  // 音声の名札の声が label か（音声がなければ null）
  async function inspect({ vidsId, scripts, label }) {
    const doc = await openDoc(vidsId);
    const { scenes, script, voice } = state(doc.model);
    return { scenes: scenes.length, revision: doc.rev, textMatch: scenes.map((id, i) => script(id) === (scripts[i] ?? "")),
      voiceMatch: scenes.map((id, i) => (id in voice ? voice[id].md5 === md5b64(scripts[i] ?? "") : null)),
      labelMatch: scenes.map((id) => (id in voice ? !!voice[id].label?.endsWith(` - ${label}`) : null)) };
  }

  window.VidsClient = { createFromSlides, updateVoiceovers, inspect, _test: { md5b64, draftBody, ttsBody, state } };
  return "VidsClient loaded";
})();
