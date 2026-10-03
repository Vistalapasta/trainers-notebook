// Aba Times: até 6 pokémon por time, cada um com held item, nature, TMs e golpes do Move Tutor, e o custo total pelo
// preço de referência do market (precoReferencia: média de mercado de 30 dias) e em Battle Points (Move Tutor). Usa os dados da aba Busca (pokemon.js) e os itens da aba
// Preços (itens). Os times ficam no banco (tabela times); cada mudança salva na hora.
const MAXIMO_MEMBROS = 6;
const CATEGORIA_HELD = "Held Items";

let times = [], timeAtual = null, coberturaAberta = false;


// Custo de um membro: held item + TMs. Cada peça: {nome, item, preco} (preco null = sem preço no market)
function pecasDoMembro(m) {
  const pecas = [];
  if (m.h) { const i = itemPorNome(m.h); pecas.push({ tipo: "held", nome: i ? i.nome : m.h, item: i, preco: precoReferencia(i) }); }
  for (const c of m.tms) { const i = itemDoTM(c); pecas.push({ tipo: "tm", cod: c, nome: `${c} - ${tms[c]?.[0] ?? ""}`, item: i, preco: precoReferencia(i) }); }
  return pecas;
}
const soma = pecas => pecas.reduce((s, p) => s + (p.preco ? p.preco.valor : 0), 0);

// Move Tutor: cada pokémon aprende o seu (não é compartilhado como o TM), então o custo em BP soma membro a membro
const custoTutor = (p, golpe) => (p?.u || []).find(x => x[0] === golpe)?.[1] ?? 0;
const bpDoMembro = m => { const p = pokemons[acharPokemon(m.p)]; return (m.u || []).reduce((s, g) => s + custoTutor(p, g), 0); };
const bpDoTime = t => t.membros.reduce((s, m) => s + bpDoMembro(m), 0);

// TMs são compartilhados: comprado uma vez, serve para o time todo. Held items contam um por pokémon.
function custoDoTime(t) {
  const pecas = t.membros.flatMap(pecasDoMembro);
  const held = pecas.filter(p => p.tipo === "held");
  const vistos = new Set();
  const tmsUnicos = pecas.filter(p => p.tipo === "tm" && !vistos.has(p.cod) && vistos.add(p.cod));
  return { held, tms: tmsUnicos, total: soma(held) + soma(tmsUnicos), semPreco: [...new Set([...held, ...tmsUnicos].filter(p => !p.preco).map(p => p.nome))] };
}

// Cobertura de tipos do time (resumo discreto, recolhido). Ataque: golpes de dano do moveset e os TMs e golpes do
// Move Tutor escolhidos. Defesa: tipos de ataque a que 2+ membros são fracos, e quantos resistem.
function coberturaDoTime(t) {
  const membros = t.membros.map(m => [m, pokemons[acharPokemon(m.p)]]).filter(([, p]) => p);
  if (!membros.length) return null;
  const tiposGolpes = new Set();
  for (const [m, p] of membros) {
    const golpes = [...(p.g || []).map(g => [g[1], g[2]]), ...m.tms.map(c => tms[c]?.slice(1, 3) || []), ...(m.u || []).map(g => golpesInfo[g] || [])];
    for (const [cat, tipo] of golpes) if (cat && cat !== "Status" && tabelaTipos[tipo]) tiposGolpes.add(tipo);
  }
  const todos = Object.keys(tabelaTipos);
  const sem = todos.filter(d => ![...tiposGolpes].some(a => tabelaTipos[a][d] >= 2));
  const defesas = membros.map(([, p]) => defesaPorTipo(p.t));
  const fraquezas = todos.map(a => ({ tipo: a, fracos: defesas.filter(d => d[a] > 1).length, resistem: defesas.filter(d => d[a] < 1).length }))
    .filter(x => x.fracos >= 2).sort((a, b) => b.fracos - b.resistem - (a.fracos - a.resistem));
  const tanques = membros.filter(([, p]) => perfil(p).tanque).length;
  return { tanques, atacantes: membros.length - tanques, sem, fraquezas };
}

function desenharCobertura(t) {
  const c = coberturaDoTime(t);
  if (!c) return "";
  const resumo = [`${c.tanques} tanque${c.tanques === 1 ? "" : "s"}, ${c.atacantes} atacante${c.atacantes === 1 ? "" : "s"}`,
    c.fraquezas.length ? `${c.fraquezas.length} fraqueza${c.fraquezas.length === 1 ? "" : "s"} em comum` : "sem fraquezas em comum",
    c.sem.length ? `sem golpe forte contra ${c.sem.length} tipo${c.sem.length === 1 ? "" : "s"}` : "golpe forte contra todos os tipos"];
  return `<details class="cobertura" ${coberturaAberta ? "open" : ""}>
    <summary><b>Cobertura de tipos</b> ${resumo.join(" · ")}</summary>
    <div>Fraquezas em comum: ${c.fraquezas.length ? c.fraquezas.map(x => `<span class="tipo" title="resistir inclui imunidade">${x.tipo}: ${x.fracos} fracos${x.resistem ? `, ${x.resistem} resiste${x.resistem === 1 ? "" : "m"}` : ""}</span>`).join("") : "nenhuma (2+ membros fracos ao mesmo tipo)"}</div>
    <div>Sem golpe forte contra: ${c.sem.length ? c.sem.map(x => `<span class="tipo">${x}</span>`).join("") : "nenhum"}</div>
    <div class="dica">Golpes de dano do moveset e os TMs e Move Tutor escolhidos; perfil tanque/atacante como na aba Busca.</div>
  </details>`;
}

async function carregarTimes() {
  await carregarPokemons();
  times = await api("/api/times");
  if (!times.find(t => t.id === timeAtual)) timeAtual = times[0]?.id ?? null;
  desenharTimes();
}

async function salvarTime(t) {
  t.membros = t.membros.slice(0, MAXIMO_MEMBROS);
  try { await api(`/api/times/${t.id}`, { method: "PUT", body: JSON.stringify({ nome: t.nome, membros: t.membros }) }); }
  catch (e) { alert(e.message); }
}

function desenharTimes() {
  $("#times").innerHTML = times.length ? times.map(t => {
    const { total } = custoDoTime(t);
    return `<button class="time-item ${t.id === timeAtual ? "sel" : ""}" data-time="${t.id}">
      <span class="retratos">${t.membros.map(m => { const n = acharPokemon(m.p), r = n && imagensDe(n, ehShiny(m.p)).r;
        return r ? `<img class="retrato-mini" src="/static/pmd/retrato/${r.f}" alt="${esc(m.p)}" title="${esc(m.p)}">` : ""; }).join("")}</span>
      <b>${esc(t.nome)}</b><span class="dica">${t.membros.length}/${MAXIMO_MEMBROS} · ${fmt(total)} HD${bpDoTime(t) ? ` · ${fmt(bpDoTime(t))} BP` : ""}</span></button>`;
  }).join("") : `<div class="dica">Nenhum time ainda. Clique em "+ Novo time".</div>`;
  desenharEditor();
}

function desenharEditor() {
  const alvo = $("#editor-time");
  const t = times.find(x => x.id === timeAtual);
  if (!t) { alvo.innerHTML = `<div class="vazio">Crie ou selecione um time.</div>`; return; }
  const custo = custoDoTime(t);
  const semPreco = custo.semPreco;
  const vagas = Array.from({ length: MAXIMO_MEMBROS }, (_, i) => t.membros[i] ? cartaoMembro(t.membros[i], i) : vagaVazia(i, i === t.membros.length));
  alvo.innerHTML = `
    <div class="cab-time">
      <input id="nome-time" value="${esc(t.nome)}" maxlength="60" title="Nome do time">
      <div class="card total-time" title="Held items (um por pokémon) + TMs (cada um uma vez: o TM serve para o time todo)"><span>Custo total</span><b>${fmt(custo.total)} HD</b></div>
      ${bpDoTime(t) ? `<div class="card total-time" title="Golpes do Move Tutor (cada pokémon paga o seu)"><span>Move Tutor</span><b>${fmt(bpDoTime(t))} BP</b></div>` : ""}
      <button class="sec" id="btn-duplicar-time" title="Cria uma cópia deste time para testar variações">Duplicar</button>
      <button class="del" id="btn-remover-time">Remover time</button>
    </div>
    <div class="dica">Held items: ${fmt(soma(custo.held))} HD (${custo.held.length}) · TMs: ${fmt(soma(custo.tms))} HD (${custo.tms.length}, cada TM conta uma vez para o time todo)</div>
    ${semPreco.length ? `<div class="dica aviso-preco">Fora da conta, sem preço no market: ${semPreco.map(esc).join(", ")}. Cadastre e registre na aba Mercado.</div>` : ""}
    <div class="vagas">${vagas.join("")}</div>
    ${desenharCobertura(t)}
    <div class="dica">Preço de cada item = média de mercado de 30 dias da aba Mercado (sem média, o último mercado registrado).</div>`;
}

function vagaVazia(i, proxima) {
  return `<div class="vaga vazia">${proxima
    ? `<input class="add-pokemon" list="lista-pokemon" placeholder="+ Pokémon ${i + 1}…" autocomplete="off">`
    : `<span class="dica">Vaga ${i + 1}</span>`}</div>`;
}

function cartaoMembro(m, i) {
  const nome = acharPokemon(m.p);
  const p = nome && pokemons[nome];
  const img = nome ? imagensDe(nome, ehShiny(m.p)) : {};
  const pecas = pecasDoMembro(m);
  const held = pecas.find(x => x.tipo === "held");
  const preco = x => x.preco ? `<span class="preco" title="${x.preco.fonte}">${fmt(x.preco.valor)} HD</span>` : `<span class="sem-preco">sem preço</span>`;
  const faltam = p ? (p.m || []).filter(c => !m.tms.includes(c)) : [];
  return `<div class="vaga" data-membro="${i}">
    <div class="cab-membro">
      ${img.r ? `<img class="retrato-membro" src="/static/pmd/retrato/${img.r.f}" alt="">` : ""}
      <div><b>${esc(m.p)}</b><div>${p ? p.t.map(t => `<span class="tipo">${t}</span>`).join("") : `<span class="dica">não encontrado</span>`}</div></div>
      ${nome ? `<button class="sec" data-acao="ficha" title="Abrir a ficha na aba Busca (perfil, tipagem, TMs e natures)">Ficha</button>` : ""}
      <button class="del" data-acao="tirar" title="Tirar do time">✕</button>
    </div>
    <label>Held item
      <span class="linha-held"><input data-acao="held" list="lista-itens-market" value="${esc(m.h)}" placeholder="nenhum" autocomplete="off">
      ${held ? preco(held) : ""}
      ${held && !held.item ? `<button type="button" class="sec" data-acao="cadastrar" title="Cadastrar na aba Mercado, categoria ${CATEGORIA_HELD}">Cadastrar</button>` : ""}</span>
    </label>
    ${p ? seletorNature(p, m.n) : ""}
    <div class="tms-membro">
      ${pecas.filter(x => x.tipo === "tm").map(x => `<span class="move">${iconeCat(tms[x.cod]?.[1])}<span class="cod">${x.cod}</span> ${esc(tms[x.cod]?.[0] ?? "")} ${preco(x)}
        <button class="del" data-acao="tirar-tm" data-tm="${x.cod}" title="Tirar TM">✕</button></span>`).join("")}
      ${faltam.length ? `<select data-acao="add-tm"><option value="">+ TM…</option>${faltam.map(c => `<option value="${c}">${c} - ${esc(tms[c][0])}${precoTM(c) ? ` (${precoTM(c)})` : ""}</option>`).join("")}</select>`
        : p && !p.m ? `<span class="dica">A wiki não lista TMs deste pokémon.</span>` : ""}
    </div>
    ${p?.u ? `<div class="tms-membro">
      ${(m.u || []).map(g => `<span class="move">${iconeCat(golpesInfo[g]?.[0])}${esc(g)} <span class="cod">${fmt(custoTutor(p, g))} BP</span>
        <button class="del" data-acao="tirar-tutor" data-golpe="${esc(g)}" title="Tirar golpe do Move Tutor">✕</button></span>`).join("")}
      ${p.u.some(([g]) => !(m.u || []).includes(g)) ? `<select data-acao="add-tutor"><option value="">+ Move Tutor…</option>${p.u.filter(([g]) => !(m.u || []).includes(g))
        .map(([g, bp]) => `<option value="${esc(g)}">${esc(g)} (${fmt(bp)} BP)</option>`).join("")}</select>` : ""}
    </div>` : ""}
  </div>`;
}

// Nature livre: as três sugestões da aba Busca primeiro (a recomendada para a função do pokémon marcada) e depois
// todas as outras. Sem escolha, o cartão mostra qual é a recomendada.
function seletorNature(p, escolhida) {
  const { opcoes, recomendada, perfil: pf } = sugerirNatures(p);
  const rec = opcoes[recomendada];
  const efeito = (sobe, desce) => sobe === desce ? "neutra" : `+${STATS[sobe][0]} −${STATS[desce][0]}`;
  const todas = Object.fromEntries(Object.entries(NATURES).flatMap(([sobe, l]) => Object.entries(l).map(([desce, n]) => [n, efeito(sobe, desce)])));
  const sugeridas = new Set(opcoes.map(o => o.nature));
  const outras = Object.keys(todas).filter(n => !sugeridas.has(n)).sort();
  const opt = (n, texto) => `<option value="${n}" ${n === escolhida ? "selected" : ""}>${texto}</option>`;
  const atual = todas[escolhida] ?? "";
  return `<label>Nature
    <span class="linha-held"><select data-acao="nature" title="${esc(rec.porque)}">
      <option value="">não escolhida</option>
      <optgroup label="Sugeridas (${pf.tanque ? "tanque" : "atacante"})">${opcoes.map((o, i) =>
        opt(o.nature, `${o.nature} · ${o.foco} (${efeito(o.sobe, o.desce)})${i === recomendada ? " ★ recomendada" : ""}`)).join("")}</optgroup>
      <optgroup label="Todas">${outras.map(n => opt(n, `${n} (${todas[n]})`)).join("")}</optgroup>
    </select></span>
    <span class="dica">${escolhida
      ? (escolhida === rec.nature ? `${atual} · a recomendada` : `${atual} · recomendada para ${pf.tanque ? "tanque" : "atacante"}: ${rec.nature}`)
      : `Recomendada para ${pf.tanque ? "tanque" : "atacante"}: <b>${rec.nature}</b> (${efeito(rec.sobe, rec.desce)})`}</span>
  </label>`;
}

// Sugestões para o held item: os held items do jogo (helditems.json) e os itens cadastrados na categoria Held Items
function preencherItensMarket() {
  const nomes = new Map(Object.entries(heldItems).map(([n, h]) => [n.toLowerCase(), [n, h.c]]));
  for (const i of itens) if (i.categoria === CATEGORIA_HELD && !nomes.has(i.nome.toLowerCase())) nomes.set(i.nome.toLowerCase(), [i.nome, i.categoria]);
  $("#lista-itens-market").innerHTML = [...nomes.values()].sort((a, b) => a[0].localeCompare(b[0]))
    .map(([n, c]) => `<option value="${esc(n)}">${esc(c)}</option>`).join("");
}

async function abrirTimes() {
  await carregarPokemons();
  preencherItensMarket();
  await carregarTimes();
}

const timeSelecionado = () => times.find(x => x.id === timeAtual);
async function mudar(fn) {
  const t = timeSelecionado();
  fn(t);
  desenharTimes();
  await salvarTime(t);
}

$("#btn-novo-time").addEventListener("click", async () => {
  const t = await api("/api/times", { method: "POST", body: JSON.stringify({ nome: `Time ${times.length + 1}` }) });
  times.push(t);
  timeAtual = t.id;
  desenharTimes();
  $("#nome-time").select();
});
$("#times").addEventListener("click", e => {
  const b = e.target.closest("[data-time]");
  if (b) { timeAtual = Number(b.dataset.time); desenharTimes(); }
});

const editor = $("#editor-time");
editor.addEventListener("change", async e => {
  const el = e.target;
  if (el.id === "nome-time") {
    if (!el.value.trim()) { el.value = timeSelecionado().nome; return; }
    return mudar(t => { t.nome = el.value.trim(); });
  }
  if (el.classList.contains("add-pokemon")) {
    const nome = acharPokemon(el.value);
    if (!nome) { el.setCustomValidity("Pokémon não encontrado"); el.reportValidity(); return; }
    // O "change" pode chegar duas vezes antes de a tela ser redesenhada: cada campo adiciona um pokémon só
    if (el.dataset.usado) return;
    el.dataset.usado = 1;
    return mudar(t => { t.membros.push({ p: (ehShiny(el.value) ? "Shiny " : "") + nome, h: "", n: "", tms: [], u: [] }); });
  }
  const i = Number(el.closest("[data-membro]")?.dataset.membro);
  if (el.dataset.acao === "held") {
    const item = itemPorNome(el.value);
    return mudar(t => { t.membros[i].h = item ? item.nome : acharHeld(el.value) || el.value.trim(); });
  }
  if (el.dataset.acao === "nature") return mudar(t => { t.membros[i].n = el.value; });
  if (el.dataset.acao === "add-tutor" && el.value) return mudar(t => { t.membros[i].u = [...(t.membros[i].u || []), el.value]; });
  if (el.dataset.acao === "add-tm" && el.value) return mudar(t => { t.membros[i].tms.push(el.value); });
});
editor.addEventListener("toggle", e => { if (e.target.classList.contains("cobertura")) coberturaAberta = e.target.open; }, true);
editor.addEventListener("input", e => { if (e.target.classList.contains("add-pokemon")) e.target.setCustomValidity(""); });
editor.addEventListener("click", async e => {
  if (e.target.closest("#btn-remover-time")) {
    const t = timeSelecionado();
    if (!confirm(`Remover o time "${t.nome}"?`)) return;
    await api(`/api/times/${t.id}`, { method: "DELETE" });
    times = times.filter(x => x !== t);
    timeAtual = times[0]?.id ?? null;
    return desenharTimes();
  }
  if (e.target.closest("#btn-duplicar-time")) {
    const orig = timeSelecionado();
    const t = await api("/api/times", { method: "POST", body: JSON.stringify({ nome: `${orig.nome} (cópia)` }) });
    t.membros = structuredClone(orig.membros);
    times.push(t);
    timeAtual = t.id;
    desenharTimes();
    await salvarTime(t);
    return $("#nome-time").select();
  }
  const b = e.target.closest("button[data-acao]");
  if (!b) return;
  const i = Number(b.closest("[data-membro]").dataset.membro);
  if (b.dataset.acao === "tirar") return mudar(t => { t.membros.splice(i, 1); });
  if (b.dataset.acao === "tirar-tutor") return mudar(t => { t.membros[i].u = t.membros[i].u.filter(g => g !== b.dataset.golpe); });
  if (b.dataset.acao === "ficha") {
    history.replaceState(null, "", "#busca");
    mostrarAba("busca");
    return abrirPokemon(timeSelecionado().membros[i].p);
  }
  if (b.dataset.acao === "tirar-tm") return mudar(t => { t.membros[i].tms = t.membros[i].tms.filter(c => c !== b.dataset.tm); });
  if (b.dataset.acao === "cadastrar") {
    const nome = timeSelecionado().membros[i].h;
    try { await api("/api/itens", { method: "POST", body: JSON.stringify({ nome, categoria: CATEGORIA_HELD }) }); }
    catch (err) { return alert(err.message); }
    await carregarItens();
    preencherItensMarket();
    // O servidor padroniza a grafia; o time passa a usar o nome cadastrado
    return mudar(t => { t.membros[i].h = itemPorNome(nome)?.nome ?? nome; });
  }
});
