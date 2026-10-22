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

  async function genai(doc, method, body) { // キーは、編集画面が genai に付ける公開のキー（HTML の espresso_api_key）。body がなければ、長くかかる生成の進み（v1/operations/…）を GET で見る
    const get = body === undefined;
    const r = await fetch(get ? `${GENAI.replace(/genai\/$/, "")}${method}?%24alt=protojson&key=${doc.key}` : `${GENAI}${method}?key=${doc.key}`, {
      method: get ? "GET" : "POST", credentials: "include", ...(get ? {} : { body: JSON.stringify(body) }), // GET に Content-Type を付けると通らない（2026-10-22。画面も付けない）
      headers: { ...(get ? {} : { "Content-Type": "application/json+protobuf" }), "X-Goog-AuthUser": "0", Authorization: await authorization() },
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
        doc.rev = Math.max(doc.rev, ...(await editPage(doc.id).catch(() => ({ chunks: [] }))).chunks.map((c) => c.revision)); // 読み直せなくても送り直す（版は前のまま）
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

  // AI avatar の動画（口の動きを合わせた 1280 × 720 の MP4）を、ttsBody の音声（bard_storage の一時ファイル）と avatar の ID から作る。
  // 画面の Avatar のパネルで Generate を押したときと同じ（[1, null, [[null, "1", 1187]]] の意味は分からない。画面が送ったまま）
  function avatarBody(vidsId, audioKey, actorId) {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const audio = [null, null, null, [[[...Array(29).fill(null), [[...Array(19).fill(null), ["bard_storage", "lookup_temp_data", audioKey]], null, ["audio/mpeg"]]]]]];
    return [[...ctx(124, 0, [flix(vidsId), null, null, [27, 0], null, "en", ...Array(5).fill(null), 1, ...Array(14).fill(null), tz, ...Array(5).fill(null), 0, null, null, null, null, [1]]),
      audio, [...Array(13).fill(null), [actorId, null, 1]], [1, null, [[null, "1", 1187]]], 1], [0, null, 0]];
  }

  // avatar を置く要素。画面で Mask video の楕円を選び、縦横を同じに切り抜いたときと同じ形（種類 8 は楕円。基準の大きさは 120000 EMU 四方で、
  // 変換の倍率 tf[0]・tf[3] を掛けた大きさになる。79・84 は横の拡大と左へのずらし（16:9 の動画の真ん中を正方形に切る）。87・88 は動画の縦・横）
  // look: 作り直す avatar の前の要素の {type, props}。画面で直した形・切り抜き・枠・影を引き継ぎ、動画・長さ・台本の印（58・176・194）だけを替える
  const avatarElement = (id, sceneId, tf, media, ms, md5, look = null) => [
    [3, id, look?.type ?? 8, tf, look ? flat(new Map([...props(look.props), [58, media], [176, ms], [194, md5]]))
      : [22, 381, 177, 3, 19, [null, 3], 58, media, 188, 1, 200, 1, 15, [null, 4], 16, 1, 183, 16 / 9, 202, 2, 194, md5, 57, 3, 176, ms,
        180, 1, 87, 540, 88, 960, 79, 16 / 9, 80, 1, 84, -7 / 18, 85, 0, 90, 0], sceneId],
    [35, id, 0, [0, 20, 1, 2, 10, 0, 3, 0, 5, [null, 1, []], 6, 1, 7, ms], sceneId], [18, [sceneId], [], [16, ms]]];
  const avatarOf = (id) => id.match(/_av_(actor\d+)_/)?.[1]; // avatar の要素の ID に、avatar の ID を入れておく（update が、どの avatar かを見る）

  const DOC_LEVEL = (c) => [1, 45, 13].includes(c[0]) || (c[0] === 18 && c[1]?.[0] === "n") || (c[0] === 12 && c[1] === "flix-master");
  const props = (p) => { const o = new Map(); for (let i = 0; i + 1 < p.length; i += 2) o.set(p[i], p[i + 1]); return o; };
  const flat = (m) => [...m].flat();

  // Slides のページをすべて Vids のシーンにし、ページごとの台本を Conversational voice で読ませる。
  // scenes: [{pageId, script, place}]（Slides のページの objectId と、そのページのノートと、avatar を置く変換 [倍率, 0, 0, 倍率, x, y]）。
  // voice: genai の声の名前（Elio は Achird）。avatar: {id, voice} を渡すと、place のあるシーンは音声の代わりに AI avatar が読む（place が null のシーンは音声だけ）
  async function createFromSlides({ vidsId, slidesId, scenes, voice = "Achird", label = "Elio", preset, music = true, avatar = null }) {
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

    // 音声: avatar のないシーンを Conversational voice で読ませ、取り込んで置く。avatar のシーンは、シーンを保存したあとで作る（下）
    const audio = [], durations = scenes.map(() => null);
    const isAvatar = (i) => !!(avatar && scenes[i].place);
    const jobs = scenes.map((s, i) => i).filter((i) => scenes[i].script);
    for (const i of jobs.filter((i) => !isAvatar(i))) {
      const v = await voiceover(doc, blobIdMap, sceneIds[i], scenes[i].script, voice, label, `${sceneIds[i]}_vo`);
      audio.push(...v.commands); durations[i] = v.ms;
    }

    // BGM: 下書きが選んだ曲（Shutterstock）
    const bgm = assets.find((a) => a[0] === "background-audio");
    if (music && bgm) {
      const [src, , [sec, nanos], , title] = bgm[3];
      const got = (await insertMedia(doc, "LMS_AUDIO", { [src]: { si: src, ki: 1 } }))[src];
      const p = placeholder(doc); blobIdMap[p] = got.ni;
      audio.push([58, `${sceneIds[0]}_bgm`, [118, 20, 158, 2, 173, 0, 175, 1800, 176, sec * 1000 + Math.round((nanos ?? 0) / 1e6), 177, 2,
        181, `${title} (Provided by Shutterstock)`, 184, sceneIds[0], 190, 2, 200, 1, 204, -6, 58, p]]);
    }

    // 元からあるシーン（空の Vids の 5 秒の空シーン "p"）を消す。[13, 今の並びの位置, 0, null, id] は画面の Delete と同じ
    // 同じ保存に入れると 550 になるので、組んだあとの保存で消す。音声の付いたシーンは消せない（550）ので、先に音声を [59] で消す（avatar も先に消す）
    const st = state(doc.model), old = st.scenes;
    await save(doc, [[20], [4, groups.flat()], [4, audio]], blobIdMap); // [20] は画面の最初の保存にあった。文字のコマンドと一緒に送ると 550
    const oldMedia = Object.keys(st.media).filter((m) => old.includes(st.media[m]));
    const drop = [...oldMedia.map((m) => [59, m]), ...old.flatMap((id) => unplace(st, id))];
    if (drop.length) await save(doc, [[4, drop]]);
    const now = state((await editPage(doc.id)).chunks.flatMap((c) => c.chunk)).scenes; // 新しいシーンの入った並び
    for (const id of old.filter((x) => now.includes(x)).sort((a, b) => now.indexOf(b) - now.indexOf(a))) // 後ろから消すと、前の位置は変わらない
      await save(doc, [[13, now.indexOf(id), 0, null, id]]);

    // avatar: シーンを保存できてから作る（保存が断られても avatar の回数を使わない）。1 つ 1 分ほどかかるので 3 つずつ並べ、
    // 最初の 1 つの応答で、残りの回数が足りるかを見る。置くのはシーンごとに 1 回ずつ保存する
    const quota = {}, avJobs = jobs.filter(isAvatar);
    const made = await pool(avJobs, 3, async (i) => {
      const map = {};
      return { map, ...(await makeAvatar(doc, map, sceneIds[i], scenes[i].script, avatar, scenes[i].place)) };
    }, (r) => checkQuota(r, avJobs.length - 1, quota));
    for (const [k, i] of avJobs.entries()) {
      if (!made[k]) continue;
      lowest(quota, made[k].quota);
      await save(doc, [[4, made[k].commands]], made[k].map);
      durations[i] = made[k].ms;
    }
    if (made.stopped) throw made.stopped;
    return { vidsId, scenes: sceneIds.length, voiced: durations.filter((d) => d).length, avatars: avJobs.length, durationsMs: durations,
      music: !!(music && bgm), quota, revision: doc.rev, waited: doc.waited };
  }

  // 文書のモデル（コマンドの並び）から: シーンの ID（並びの順）、シーンの台本の文字、シーンの音声の要素、シーンの avatar の要素、シーンの時間の並び
  function state(model) {
    const scenes = [], text = {}, voice = {}, media = {}; // media: 要素の ID → 付いているシーン（音声・BGM）
    const avatar = {}, timing = {}; // avatar: シーン → {id, md5, actor, tf}。timing: シーン → 時間の並びの要素の ID（[35] で入り [36, 位置, シーン] で抜ける）
    for (const c of model) {
      if (c[0] === 12 && c[3] === 0) scenes.push(c[1]);
      else if (c[0] === 13 && scenes.includes(c[4])) scenes.splice(scenes.indexOf(c[4]), 1); // シーンを消す [13, 位置, 0, null, ID]
      else if (c[0] === 15) { const t = text[c[1]] ?? ""; text[c[1]] = t.slice(0, c[3]) + c[4] + t.slice(c[3]); } // 文字を入れる [15, 枠, null, 位置, 文字]
      else if (c[0] === 16) { const t = text[c[1]] ?? ""; text[c[1]] = t.slice(0, c[3]) + t.slice(c[4]); }        // 消す [16, 枠, null, 始め, 終わり]
      else if (c[0] === 58) { const p = props(c[2]); media[c[1]] = p.get(184); if (p.get(177) === 3) voice[p.get(184)] = { id: c[1], md5: p.get(194), label: p.get(181) }; }
      else if (c[0] === 59) { delete media[c[1]]; for (const k of Object.keys(voice)) if (voice[k].id === c[1]) delete voice[k]; }
      else if (c[0] === 3 && Array.isArray(c[4]) && props(c[4]).get(202) === 2) // [3, ID, 種類, 変換, 属性, シーン]
        avatar[c[5]] = { id: c[1], md5: props(c[4]).get(194), actor: avatarOf(c[1]), tf: c[3], type: c[2], props: c[4] };
      else if (c[0] === 6) { for (const a of Object.values(avatar)) if (a.id === c[1]) a.tf = c[2]; }           // 動かす [6, ID, 変換]
      else if (c[0] === 5) { for (const a of Object.values(avatar)) if (c[1].includes(a.id)) {                  // 属性を替える [5, [ID], [外す鍵], [鍵, 値, …]]
        const m = props(a.props); for (const k of c[2] ?? []) m.delete(k); for (const [k, v] of props(c[3] ?? [])) m.set(k, v);
        a.props = flat(m); a.md5 = m.get(194); } }
      else if (c[0] === 19) { for (const a of Object.values(avatar)) if (c[1].includes(a.id)) a.type = c[2]; }  // 形を替える [19, [ID], 種類]（Mask video）
      else if (c[0] === 0) { for (const k of Object.keys(avatar)) if (c[1].includes(avatar[k].id)) delete avatar[k]; } // 要素を消す [0, [ID]]
      else if (c[0] === 35) (timing[c[4]] ??= []).splice(c[2], 0, c[1]);
      else if (c[0] === 36) timing[c[2]]?.splice(c[1], 1);
    }
    const script = (id) => (text[`${id}:notes_text`] ?? "").replace(/\n$/, "");
    return { scenes, script, voice, media, avatar, timing };
  }

  // シーンの avatar を消すコマンド（画面で選んで Delete を押したときと同じ: 時間の並びから抜き、要素を消す）
  const unplace = (st, sceneId) => {
    const a = st.avatar[sceneId];
    if (!a) return [];
    const at = (st.timing[sceneId] ?? []).indexOf(a.id);
    return [...(at >= 0 ? [[36, at, sceneId]] : []), [0, [a.id]]];
  };

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

  // 1 シーンの AI avatar を作り、取り込む。avatar: {id: "actor50", voice: "achird"}（声は avatar ごとに決まっている）。tf: 置く位置と大きさ（avatarElement）。
  // 戻り値は、置くコマンドと長さ（ミリ秒）と、生成の応答にある avatar の回数（{limit, left}）
  async function makeAvatar(doc, blobIdMap, sceneId, script, avatar, tf, look = null) {
    const tts = await genai(doc, "generate", ttsBody(script, avatar.voice));
    const audio = findList(tts, (x) => x.length >= 4 && x[1] === "bard_storage" && x[3] === "lookup_temp_data");
    if (!audio) throw new Error(`シーン ${sceneId}: 音声の応答に一時ファイルがない`);
    const started = await genai(doc, "streamGenerate", avatarBody(doc.id, audio[0], avatar.id));
    const op = findString(started, (s) => s.startsWith("agency_session_id/"));
    if (!op) throw new Error(`シーン ${sceneId}: avatar の応答に生成の ID がない（${JSON.stringify(started).slice(0, 300)}）`);
    const q = findList(started, (x) => x.length === 8 && /^\d+$/.test(x[0] ?? "") && x[1] === null && /^\d+$/.test(x[2] ?? ""));
    let video, misses = 0;
    for (let i = 0; !video; i++) { // 3 秒の台本で約 1 分かかった（2026-10-22）。15 分で諦める
      if (i === 180) throw new Error(`シーン ${sceneId}: avatar の生成が 15 分で終わらない`);
      await new Promise((r) => setTimeout(r, 5000));
      let st;
      try { st = await genai(doc, `operations/${op}`); misses = 0; } catch (e) { if (++misses === 12) throw e; continue; } // 1 回の失敗では止めない（1 分続いたら止める）
      video = findList(st, (x) => x.length >= 8 && x[1] === "bard_storage" && x[3] === "lookup_temp_data" && /video\.mp4/.test(x[4] ?? ""));
      if (!video && st[2] === 1) throw new Error(`シーン ${sceneId}: avatar の生成が動画なしで終わった（${JSON.stringify(st).slice(0, 300)}）`);
    }
    const [sec, nanos] = video[7];
    const ms = Number(sec) * 1000 + Math.round((nanos ?? 0) / 1e6); // 秒ちょうどなら nanos がないことがある
    const key = `bard_storagelookup_temp_data${video[0]}`;
    const got = (await insertMedia(doc, "CONTRIB_SERVICE_VIDEO", { [key]: { si: { co: "bard_storage", sc: "lookup_temp_data", uk: video[0] }, ki: 0 } }))[key];
    const p = placeholder(doc); blobIdMap[p] = got.ni;
    return { ms, quota: q && { limit: Number(q[0]), left: Number(q[2]) },
      commands: avatarElement(`${sceneId}_av_${avatar.id}_${doc.sid}`, sceneId, tf, p, ms, md5b64(script), look) };
  }

  // avatar の回数。生成の応答に、その月の上限と残り（例: 50 回のうち 46）がある。残りのいちばん少ないものを控える
  const lowest = (acc, q) => { if (q && !(acc.left <= q.left)) Object.assign(acc, q); };
  // 足りなければ止める理由（作った 1 つは、呼んだ側が置いてから止める）
  function checkQuota(first, rest, acc) {
    lowest(acc, first.quota);
    if (rest && acc.left !== undefined && acc.left < rest)
      return `avatar の残りが今月 ${acc.left} 回（上限 ${acc.limit}）で、あと ${rest} シーンに足りない（1 シーンだけ作って置いた）`;
  }

  // fn を items に、同時に n 個まで。最初の 1 個は 1 人で回し、その結果を first(結果) で見てから残りに進む（avatar の回数が足りるか）。
  // first が理由を返したら、残りは回さず out.stopped に理由（Error）を入れて返す。途中で 1 つ失敗したら、ほかの手は新しく始めず、
  // できたものを out に残して out.stopped にそのエラーを入れて返す。呼んだ側は、できたものを置いてから out.stopped を投げる（avatar の回数を捨てない）
  async function pool(items, n, fn, first = () => {}) {
    const out = [];
    if (!items.length) return out;
    out[0] = await fn(items[0]);
    const why = first(out[0]);
    if (why) { out.stopped = new Error(why); return out; }
    let next = 1;
    await Promise.all(Array.from({ length: n }, async () => {
      while (!out.stopped && next < items.length) { const k = next++; try { out[k] = await fn(items[k]); } catch (e) { out.stopped ??= e; } }
    }));
    return out;
  }

  // 台本か声の違うシーンの、台本の文字と音声を差し替える。声は音声の名札（181 の「… - <声>」）で見る（途中で止まった声の替えも、回し直せば直る）。
  // 画面で台本を直して Update voiceover を押したときと同じ保存（文字は [16]・[15] を 1 回、音声は [4, [[59, 古い音声], [58, 新しい音声], [18, シーンの長さ]]] を 1 回）。
  // avatar: {id, voice} なら、台本のあるシーンを AI avatar にする（avatar と台本が合っていれば作り直さない）。置く場所は places[i]（[倍率, 0, 0, 倍率, x, y]、
  // null はそのシーンだけ音声）。places がなければ、今の avatar の場所のまま（今が音声だけのシーンは音声のまま）。シーンの数が違えば何もしない
  async function updateScenes({ vidsId, scripts, voice = "Achird", label = "Elio", avatar = null, places = null }) {
    const doc = await openDoc(vidsId);
    const st = state(doc.model), { scenes, script, voice: vo, avatar: av } = st;
    if (scenes.length !== scripts.length) return { sceneCount: scenes.length, updated: [] };
    const plan = scenes.map((id, i) => {
      const s = scripts[i], a = av[id], v = vo[id], tf = places ? places[i] : a?.tf;
      return { id, i, s, a, v, tf, want: !!(avatar && s && (places ? tf : a || !v)) };
    });
    const homeless = plan.filter((p) => p.want && !p.tf).map((p) => p.i + 1); // 保存を始める前に止める（途中まで書いて止まらない）
    if (homeless.length) throw new Error(`シーン ${homeless} に avatar を置く場所がない（vids.py layout の --layout を渡す）`);
    // 控えは avatar なのに Vids に avatar が 1 つもない（音声だけから替える update が途中で止まった）。--layout なしでは音声のまま通ってしまうので止める
    if (avatar && !places && !Object.keys(av).length) throw new Error("この Vids には avatar がまだない。同じ --layout を渡して回し直す");
    const jobs = [], moved = [];
    for (const { id, i, s, a, v, tf, want } of plan) {
      const cur = script(id);
      const good = cur === s && (s ? (want ? a?.md5 === md5b64(s) && a.actor === avatar.id && !v : v?.md5 === md5b64(s) && v.label?.endsWith(` - ${label}`) && !a) : !v && !a);
      if (good) {
        if (want && JSON.stringify(tf) !== JSON.stringify(a.tf)) { await save(doc, [[6, a.id, tf]]); moved.push(i + 1); } // 動かすだけなら作り直さない
        continue;
      }
      if (cur !== s) await save(doc, [...(cur ? [[16, `${id}:notes_text`, null, 0, cur.length]] : []), ...(s ? [[15, `${id}:notes_text`, null, 0, s]] : [])]);
      jobs.push({ i, id, s, want, tf, look: a && { type: a.type, props: a.props }, drop: [...(v ? [[59, v.id]] : []), ...unplace(st, id)] });
    }
    // 作るのは並べて（avatar は 3 つずつ）、保存は 1 つずつ。avatar の作業を先に回す（最初の 1 つの応答で、残りの回数が足りるかを見る）
    jobs.sort((x, y) => y.want - x.want);
    const quota = {};
    const made = await pool(jobs, avatar ? 3 : 1, async (j) => {
      const blobIdMap = {};
      const r = !j.s ? null : j.want ? await makeAvatar(doc, blobIdMap, j.id, j.s, avatar, j.tf, j.look) : await voiceover(doc, blobIdMap, j.id, j.s, voice, label, `${j.id}_vo_${doc.sid}`);
      return { blobIdMap, ...r };
    }, (r) => checkQuota(r, jobs.slice(1).filter((j) => j.want).length, quota));
    for (const [k, j] of jobs.entries()) {
      if (!made[k]) continue;
      lowest(quota, made[k].quota);
      const cmds = [...j.drop, ...(made[k].commands ?? (j.drop.length ? [[18, [j.id], [], [16, 5000]]] : []))]; // 音声を外したシーンは、空の Vids の空シーンと同じ 5 秒にする（古い音声の長さのまま無音にしない）
      if (cmds.length) await save(doc, [[4, cmds]], made[k].blobIdMap);
    }
    if (made.stopped) throw made.stopped;
    return { sceneCount: scenes.length, updated: jobs.map((j) => j.i + 1).sort((x, y) => x - y), moved, quota, revision: doc.rev, waited: doc.waited };
  }

  // 読み直して確かめる: シーンの数、シーンごとに台本の文字が scripts と合うか、読む要素（avatar か音声）の台本の MD5（194）が合うか（どちらもなければ null）、
  // 読むのが誰か（avatar の ID か、音声の名札の声。どちらもなければ null）、avatar と音声の両方があるシーン
  async function inspect({ vidsId, scripts }) {
    const doc = await openDoc(vidsId);
    const { scenes, script, voice, avatar } = state(doc.model);
    const reader = (id) => avatar[id] ?? voice[id];
    return { scenes: scenes.length, revision: doc.rev, textMatch: scenes.map((id, i) => script(id) === (scripts[i] ?? "")),
      voiceMatch: scenes.map((id, i) => (reader(id) ? reader(id).md5 === md5b64(scripts[i] ?? "") : null)),
      who: scenes.map((id) => avatar[id]?.actor ?? voice[id]?.label?.split(" - ").at(-1) ?? null),
      both: scenes.flatMap((id, i) => (avatar[id] && voice[id] ? [i + 1] : [])) };
  }

  window.VidsClient = { createFromSlides, updateScenes, inspect, _test: { md5b64, draftBody, ttsBody, avatarBody, avatarElement, state, unplace, pool } };
  return "VidsClient loaded";
})();
