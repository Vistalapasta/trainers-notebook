// Aba Mercado > Farm: sessões de caça registradas depois de jogar (local, data, duração, drops e gastos) e quanto
// cada uma rendeu por hora. Preço de cada item: o preço fixo de NPC, se houver (tabela precos_npc, por nome),
// senão o preço de referência do market (precoReferencia: média de mercado de 30 dias). Os valores usam os preços
// de hoje, para comparar os farms com o mesmo preço. Usa os itens da aba Preços (itens) e itemPorNome (pokemon.js).
let farms = [], farmAtual = null, precosNpc = {};

function precoFarm(nome) {
  if (!nome) return null;
  const npc = Object.entries(precosNpc).find(([n]) => n.toLowerCase() === nome.trim().toLowerCase());
  if (npc) return { valor: npc[1], fonte: "NPC" };
  return precoReferencia(itemPorNome(nome));
}
const npcDe = nome => Object.entries(precosNpc).find(([n]) => n.toLowerCase() === (nome || "").trim().toLowerCase())?.[1] ?? null;

// Bruto (drops), gastos, lucro e lucro por hora; itens sem preço ficam fora e são listados
function contaFarm(f) {
  const somar = linhas => linhas.reduce((s, l) => s + (precoFarm(l.i)?.valor ?? 0) * l.q, 0);
  const bruto = somar(f.drops), gastos = somar(f.gastos), lucro = bruto - gastos;
  const semPreco = [...new Set([...f.drops, ...f.gastos].filter(l => l.i && l.q && !precoFarm(l.i)).map(l => l.i))];
  return { bruto, gastos, lucro, porHora: lucro / (f.minutos / 60), semPreco };
}

// Ranking por local: lucro somado ÷ horas somadas (sessão longa pesa mais que sessão curta)
function rankingLocais() {
  const locais = {};
  for (const f of farms) {
    const r = (locais[f.local || "Sem nome"] ??= { local: f.local || "Sem nome", sessoes: 0, minutos: 0, lucro: 0 });
    r.sessoes++; r.minutos += f.minutos; r.lucro += contaFarm(f).lucro;
  }
  return Object.values(locais).map(r => ({ ...r, porHora: r.lucro / (r.minutos / 60) })).sort((a, b) => b.porHora - a.porHora);
}

const duracaoFarm = min => { const h = Math.floor(min / 60), m = min % 60; return h && m ? `${h}h${String(m).padStart(2, "0")}` : h ? `${h}h` : `${m}min`; };
const dataBR = d => d.split("-").reverse().join("/");

async function abrirFarm() {
  if (!itens.length) await carregarItens();
  [farms, precosNpc] = await Promise.all([api("/api/farms"), api("/api/precos-npc")]);
  if (!farms.find(f => f.id === farmAtual)) farmAtual = farms[0]?.id ?? null;
  desenharFarms();
}

function preencherListasFarm() {
  const nomes = new Map();
  for (const n of [...itens.map(i => i.nome), ...Object.keys(precosNpc), ...farms.flatMap(f => [...f.drops, ...f.gastos].map(l => l.i))])
    if (n && !nomes.has(n.toLowerCase())) nomes.set(n.toLowerCase(), n);
  $("#lista-farm-itens").innerHTML = [...nomes.values()].sort((a, b) => a.localeCompare(b, "pt-BR")).map(n => `<option value="${esc(n)}">`).join("");
  $("#lista-farm-locais").innerHTML = [...new Set(farms.map(f => f.local).filter(Boolean))].map(n => `<option value="${esc(n)}">`).join("");
}

function desenharFarms() {
  desenharListaFarm();
  desenharEditorFarm();
}

// Lista e ranking sem mexer no editor (para não perder o campo em que o usuário está)
function desenharListaFarm() {
  preencherListasFarm();
  const ranking = rankingLocais();
  $("#ranking-farm").innerHTML = ranking.length ? `
    <table><thead><tr><th>Nome</th><th class="num">Sessões</th><th class="num">Tempo</th><th class="num" title="Lucro somado ÷ horas somadas">Lucro/hora</th></tr></thead>
    <tbody>${ranking.map((r, i) => `<tr><td>${i === 0 && ranking.length > 1 ? "🏆 " : ""}${esc(r.local)}</td><td class="num">${r.sessoes}</td>
      <td class="num">${duracaoFarm(r.minutos)}</td><td class="num ${r.porHora < 0 ? "negativo" : ""}"><b>${fmt(r.porHora)}</b> HD</td></tr>`).join("")}</tbody></table>` : "";
  $("#lista-farms").innerHTML = farms.length ? farms.map(f => {
    const c = contaFarm(f);
    return `<button class="time-item ${f.id === farmAtual ? "sel" : ""}" data-farm="${f.id}">
      <b>${esc(f.local || "Sem nome")}</b><span class="dica">${fmt(c.porHora)} HD/h</span>
      <span class="dica">${dataBR(f.data)} · ${duracaoFarm(f.minutos)}</span><span class="dica">${fmt(c.lucro)} HD</span></button>`;
  }).join("") : `<div class="dica">Nenhuma sessão ainda. Depois de caçar, clique em "+ Nova sessão" e anote o que dropou.</div>`;
}

const farmSelecionado = () => farms.find(f => f.id === farmAtual);

function linhaFarm(lado, l, i) {
  const p = precoFarm(l.i), npc = npcDe(l.i);
  return `<tr data-lado="${lado}" data-i="${i}">
    <td><input data-campo="i" list="lista-farm-itens" value="${esc(l.i)}" placeholder="Item…" autocomplete="off"></td>
    <td><input data-campo="q" type="number" min="0" step="any" value="${l.q}" class="qtd"></td>
    <td class="num preco-farm">${precoTexto(p)}</td>
    <td class="num subtotal">${p ? fmt(p.valor * l.q) : "—"}</td>
    <td><input data-campo="npc" type="number" min="0" step="any" value="${npc ?? ""}" placeholder="market" class="npc"
      title="Preço fixo de NPC (HD por unidade): vale no lugar do market para este item em todas as sessões. Vazio = market."></td>
    <td><button class="del" data-tirar title="Tirar">✕</button></td></tr>`;
}
const precoTexto = p => p ? `${fmt(p.valor)} <span class="dica">${p.fonte}</span>` : `<span class="sem-preco">sem preço</span>`;

function tabelaFarm(lado, linhas, titulo) {
  return `<h3>${titulo}</h3>
    <table class="tabela-farm"><thead><tr><th>Item</th><th>Qtd</th><th class="num">Preço (HD)</th><th class="num">Total (HD)</th>
      <th title="Preço fixo de NPC: vale no lugar do market">NPC (HD)</th><th></th></tr></thead>
    <tbody>${linhas.map((l, i) => linhaFarm(lado, l, i)).join("")}
      <tr class="nova"><td><input data-nova="${lado}" list="lista-farm-itens" placeholder="+ ${lado === "drops" ? "Drop" : "Gasto"}…" autocomplete="off"></td><td colspan="5"></td></tr>
    </tbody></table>`;
}

function desenharEditorFarm() {
  const alvo = $("#editor-farm"), f = farmSelecionado();
  if (!f) { alvo.innerHTML = `<div class="vazio">Crie ou selecione uma sessão.</div>`; return; }
  alvo.innerHTML = `
    <div class="cab-time">
      <label>Nome <input id="farm-local" list="lista-farm-locais" value="${esc(f.local)}" placeholder="ex.: Gyarados na ilha, Pesca de Magikarp" autocomplete="off"></label>
      <label>Data <input id="farm-data" type="date" value="${f.data}"></label>
      <label>Duração <span class="duracao"><input id="farm-h" type="number" min="0" max="24" value="${Math.floor(f.minutos / 60)}"> h
        <input id="farm-m" type="number" min="0" max="59" value="${f.minutos % 60}"> min</span></label>
      <div class="card total-time"><span>Lucro/hora</span><b id="farm-por-hora"></b></div>
      <button class="del" id="btn-remover-farm">Remover sessão</button>
    </div>
    <div class="dica" id="farm-resumo"></div>
    <div class="dica aviso-preco" id="farm-sem-preco"></div>
    ${tabelaFarm("drops", f.drops, "Drops")}
    ${tabelaFarm("gastos", f.gastos, "Gastos (potions, pokébolas, revives…)")}
    <label style="margin-top:12px">Obs <input id="farm-obs" value="${esc(f.obs)}" placeholder="opcional (pokémon usado, bônus, evento…)" autocomplete="off"></label>
    <div class="dica" style="margin-top:8px">Preço de cada item: o preço de NPC, se você preencher; senão a média de mercado de 30 dias da aba Mercado
      (sem média, o último mercado). Usa os preços de hoje, para comparar as sessões com o mesmo preço.</div>`;
  atualizarTotaisFarm();
}

function atualizarTotaisFarm() {
  const f = farmSelecionado(), c = contaFarm(f);
  $("#farm-por-hora").textContent = `${fmt(c.porHora)} HD`;
  $("#farm-por-hora").classList.toggle("negativo", c.porHora < 0);
  $("#farm-resumo").textContent = `Drops: ${fmt(c.bruto)} HD · Gastos: ${fmt(c.gastos)} HD · Lucro: ${fmt(c.lucro)} HD em ${duracaoFarm(f.minutos)}`;
  $("#farm-sem-preco").textContent = c.semPreco.length ? `Fora da conta, sem preço: ${c.semPreco.join(", ")}. Registre no market ou preencha o preço de NPC.` : "";
}

// Salva um pouco depois da última mudança (os campos de quantidade mudam a cada tecla)
let salvarFarmTimer = null;
function salvarFarmDepois() {
  clearTimeout(salvarFarmTimer);
  const f = farmSelecionado();
  salvarFarmTimer = setTimeout(async () => {
    try { await api(`/api/farms/${f.id}`, { method: "PUT", body: JSON.stringify(f) }); }
    catch (e) { alert(e.message); }
  }, 400);
}

const editorFarm = $("#editor-farm");
editorFarm.addEventListener("input", e => {
  const el = e.target, f = farmSelecionado();
  const tr = el.closest("tr[data-lado]");
  if (tr && el.dataset.campo !== "npc") {
    const l = f[tr.dataset.lado][Number(tr.dataset.i)];
    if (el.dataset.campo === "q") l.q = Number(el.value) || 0;
    else l.i = el.value.trim();
    const p = precoFarm(l.i);
    tr.querySelector(".preco-farm").innerHTML = precoTexto(p);
    tr.querySelector(".subtotal").textContent = p ? fmt(p.valor * l.q) : "—";
    if (el.dataset.campo === "i") tr.querySelector(".npc").value = npcDe(l.i) ?? "";
  } else if (el.id === "farm-h" || el.id === "farm-m") {
    const min = (Number($("#farm-h").value) || 0) * 60 + (Number($("#farm-m").value) || 0);
    if (min < 1 || min > 24 * 60) return;
    f.minutos = min;
  } else if (el.id === "farm-local") f.local = el.value.trim();
  else if (el.id === "farm-data") { if (!el.value) return; f.data = el.value; }
  else if (el.id === "farm-obs") f.obs = el.value;
  else return;
  atualizarTotaisFarm();
  salvarFarmDepois();
});
editorFarm.addEventListener("change", async e => {
  const el = e.target, f = farmSelecionado();
  if (el.dataset.nova) {  // linha nova: vira item e o foco vai para a quantidade
    const nome = el.value.trim();
    if (!nome) return;
    const item = itemPorNome(nome);
    f[el.dataset.nova].push({ i: item ? item.nome : nome, q: 1 });
    salvarFarmDepois();
    desenharFarms();
    const linhas = editorFarm.querySelectorAll(`tr[data-lado="${el.dataset.nova}"] input[data-campo="q"]`);
    linhas[linhas.length - 1]?.select();
    return;
  }
  if (el.dataset.campo === "npc") {
    const nome = f[el.closest("tr").dataset.lado][Number(el.closest("tr").dataset.i)].i;
    if (!nome) return;
    const preco = el.value === "" ? null : Number(el.value);
    try { await api("/api/precos-npc", { method: "PUT", body: JSON.stringify({ nome, preco: preco > 0 ? preco : null }) }); }
    catch (err) { return alert(err.message); }
    precosNpc = await api("/api/precos-npc");
    return desenharFarms();  // o preço vale para todas as linhas e sessões com esse item
  }
  // Nome do item ou local escolhido: padroniza a grafia e atualiza lista e ranking
  if (el.dataset.campo === "i") {
    const tr = el.closest("tr"), l = f[tr.dataset.lado][Number(tr.dataset.i)], item = itemPorNome(l.i);
    if (item) { l.i = item.nome; el.value = item.nome; }
    salvarFarmDepois();
  }
  desenharListaFarm();
});
editorFarm.addEventListener("click", async e => {
  const f = farmSelecionado();
  if (e.target.closest("#btn-remover-farm")) {
    if (!confirm(`Remover a sessão de ${dataBR(f.data)}${f.local ? ` "${f.local}"` : ""}?`)) return;
    await api(`/api/farms/${f.id}`, { method: "DELETE" });
    farms = farms.filter(x => x !== f);
    farmAtual = farms[0]?.id ?? null;
    return desenharFarms();
  }
  if (e.target.closest("[data-tirar]")) {
    const tr = e.target.closest("tr");
    f[tr.dataset.lado].splice(Number(tr.dataset.i), 1);
    salvarFarmDepois();
    desenharFarms();
  }
});

$("#lista-farms").addEventListener("click", e => {
  const b = e.target.closest("[data-farm]");
  if (b) { farmAtual = Number(b.dataset.farm); desenharFarms(); }
});
$("#btn-nova-farm").addEventListener("click", async () => {
  // A sessão nova começa no mesmo local da última (o mais comum é repetir o farm)
  const f = await api("/api/farms", { method: "POST", body: JSON.stringify({ local: farms[0]?.local ?? "" }) });
  farms.unshift(f);
  farmAtual = f.id;
  desenharFarms();
  $("#farm-local").select();
});
