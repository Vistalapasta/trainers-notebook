// Aba Busca (pokémon, TMs/golpes e held items). Pokémon: perfil (tanque ou atacante), tipagem, TMs, Move Tutor e sugestão de nature.
// pokemon.json: t = tipos, s = stats do jogo [HP, Atk, Def, SpA, SpD, Spe], w = 1 quando os stats vieram da wiki
// (senão são os oficiais × 0,03), g = moveset [golpe, categoria, tipo, efeito], m = TMs/HMs (códigos),
// u = Move Tutor [golpe, custo em Battle Points]. tms.json: código -> [golpe, categoria, tipo, efeito].
// golpes.json: golpe -> [categoria, tipo, efeito].
// pmd/pmd.json (ferramentas/baixar_sprites.py): imagens do PMDCollab, CC BY-NC 4.0. pokemon[nome] = {r: retrato,
// a: sprite Idle {f, w, h, d: durações em 1/60 s}, s: shiny {r, a}}; cada um com c = ids dos artistas.
// artistas[id] = [nome, contato]. Crédito obrigatório: aparece na ficha e na lista de créditos da aba.

// Natures do otPokemon (mesma tabela da wiki): NATURES[stat que sobe][stat que desce]. Na diagonal ficam as neutras.
const STATS = { atk: ["Attack", 1], def: ["Defense", 2], spa: ["Sp. Atk", 3], spd: ["Sp. Def", 4], spe: ["Speed", 5] };
const NATURES = {
  atk: { atk: "Hardy", def: "Lonely", spe: "Brave", spa: "Adamant", spd: "Naughty" },
  def: { atk: "Bold", def: "Docile", spe: "Relaxed", spa: "Impish", spd: "Lax" },
  spe: { atk: "Timid", def: "Hasty", spe: "Serious", spa: "Jolly", spd: "Naive" },
  spa: { atk: "Modest", def: "Mild", spe: "Quiet", spa: "Bashful", spd: "Rash" },
  spd: { atk: "Calm", def: "Gentle", spe: "Sassy", spa: "Careful", spd: "Quirky" },
};

// Ignora maiúsculas, espaços e pontuação ("Mr mime", "Kings Shield") e o prefixo "Shiny"
const chave = t => t.toLowerCase().replace(/^\s*shiny\s+/, "").replace(/[^a-z0-9♀♂]/g, "");
const conjunto = nomes => new Set(nomes.map(chave));
// Golpes que recuperam HP (curam uma parte do HP máximo, então rendem mais em quem tem muito HP)
const CURA = conjunto([
  "Recover", "Roost", "Rest", "Life Dew", "Synthesis", "Moonlight", "Morning Sun", "Soft-Boiled", "Milk Drink",
  "Slack Off", "Wish", "Heal Order", "Aqua Ring", "Ingrain", "Shore Up", "Strength Sap", "Leech Seed", "Heal Pulse",
  "Floral Healing", "Pain Split", "Jungle Healing", "Lunar Blessing",
]);
// Golpes de proteção e de aumento de defesa
const PROTECAO = conjunto([
  "Protect", "Detect", "King's Shield", "Spiky Shield", "Baneful Bunker", "Crafty Shield", "Substitute", "Reflect",
  "Light Screen", "Aurora Veil", "Harden", "Withdraw", "Iron Defense", "Barrier", "Acid Armor", "Amnesia",
  "Cotton Guard", "Defense Curl", "Cosmic Power", "Stockpile", "Curse", "Bulk Up", "Calm Mind",
]);
const cura = g => CURA.has(chave(g[0]));
// Golpes de dano que sobem defesa de efeito colateral (ex.: Skull Bash) não contam
const defensivo = g => cura(g) || PROTECAO.has(chave(g[0])) || (g[1] === "Status" && /\+\d+ (Sp\.? )?Defense/.test(g[3]));

// Golpes de TM e Move Tutor são opções que o jogador escolhe, então contam menos que o moveset:
// 0,25 cada no estilo de ataque e, juntos, no máximo +0,5 no perfil de tanque
const PESO_APRENDIVEL = 0.25, MAXIMO_APRENDIVEL_DEFESA = 0.5;

let pokemons = null, tabelaTipos = null, tms = null, golpesInfo = null, pmd = null, heldItems = null;

async function carregarPokemons() {
  if (pokemons) return;
  [pokemons, tabelaTipos, tms, golpesInfo, pmd, heldItems] = await Promise.all(
    ["/static/pokemon.json", "/static/tipos.json", "/static/tms.json", "/static/golpes.json", "/static/pmd/pmd.json", "/static/helditems.json"]
      .map(async u => (await fetch(u)).json()));
  $("#lista-held").innerHTML = Object.entries(heldItems).map(([n, h]) => `<option value="${esc(n)}">${esc(h.c)}</option>`).join("");
  $("#lista-pokemon").innerHTML = Object.keys(pokemons).map(n => `<option value="${esc(n)}">`).join("");
  const doTutor = [...new Set(Object.values(pokemons).flatMap(p => (p.u || []).map(u => u[0])))].filter(g => !codigoDoGolpe(g)).sort();
  $("#lista-tms").innerHTML = Object.entries(tms).map(([c, [g]]) => `<option value="${c} - ${esc(g)}">`).join("")
    + doTutor.map(g => `<option value="${esc(g)}">`).join("");
}

const codigoDoGolpe = golpe => Object.keys(tms).find(c => chave(tms[c][0]) === chave(golpe));

// Golpes de TM e Move Tutor no mesmo formato do moveset, com a origem
function aprendiveis(p) {
  const r = (p.m || []).map(c => [...tms[c], c]);
  for (const [golpe, custo] of p.u || []) r.push([golpe, ...(golpesInfo[golpe] || ["", "", ""]), `Move Tutor (${custo} BP)`]);
  return r;
}

// Multiplicador de dano que cada tipo de ataque causa no pokémon (tabela de Elementos da wiki)
function defesaPorTipo(tipos) {
  const r = {};
  for (const ataque in tabelaTipos) r[ataque] = tipos.reduce((m, t) => m * tabelaTipos[ataque][t], 1);
  return r;
}

// Tipagem forte × fraca. Defesa: dano que recebe de cada tipo de ataque.
// Ataque: contra quem os golpes do próprio tipo são fortes/fracos, e a cobertura dos golpes de dano do moveset.
function tipagem(p) {
  const def = defesaPorTipo(p.t);
  const recebe = m => Object.keys(def).filter(t => def[t] === m);
  const contra = (tiposAtaque, m) => Object.keys(tabelaTipos).filter(d => tiposAtaque.some(a => tabelaTipos[a][d] === m));
  const golpes = [...new Set((p.g || []).filter(g => g[1] !== "Status" && tabelaTipos[g[2]]).map(g => g[2]))];
  const cobertos = new Set(contra(golpes, 2));
  return {
    defesa: [["Fraco 4×", recebe(4), "fraco"], ["Fraco 2×", recebe(2), "fraco"], ["Resiste ½", recebe(0.5), "resiste"],
             ["Resiste ¼", recebe(0.25), "resiste"], ["Imune", recebe(0), "resiste"]],
    ataque: p.t.map(t => ({ tipo: t, forte: contra([t], 2), fraco: contra([t], 0.5), nulo: contra([t], 0) })),
    cobertura: p.g ? { forte: [...cobertos], sem: Object.keys(tabelaTipos).filter(d => !cobertos.has(d)) } : null,
  };
}

// Físico ou especial: golpes de dano do moveset (peso 1) e de TM/Move Tutor (peso 0,25).
// Diferença de 2 ou mais decide; senão, Attack e Sp. Atk com até 10% de diferença = misto.
function estiloDeAtaque(p) {
  const [, atk, , spa] = p.s;
  const conta = (lista, cat) => lista.filter(g => g[1] === cat).length;
  const extras = aprendiveis(p);
  const mf = conta(p.g || [], "Físico"), me = conta(p.g || [], "Especial");
  const af = conta(extras, "Físico"), ae = conta(extras, "Especial");
  const fis = mf + af * PESO_APRENDIVEL, esp = me + ae * PESO_APRENDIVEL;
  const golpes = (p.g ? `moveset ${mf} físicos/${me} especiais` : "") + (extras.length ? `${p.g ? "; " : ""}TMs e tutor ${af}/${ae}` : "");
  if (fis >= esp + 2) return { ataque: "atk", porque: golpes };
  if (esp >= fis + 2) return { ataque: "spa", porque: golpes };
  // Misto: o ataque principal é o que os golpes favorecem (quando pendem para um lado) ou o maior stat
  const principal = fis !== esp ? (fis > esp ? "atk" : "spa") : atk >= spa ? "atk" : "spa";
  if (Math.abs(atk - spa) <= Math.max(atk, spa) * 0.1) return { ataque: principal, misto: true, porque: "Attack e Sp. Atk parecidos" + (golpes ? `, ${golpes}` : "") };
  return { ataque: atk > spa ? "atk" : "spa", porque: `${STATS[atk > spa ? "atk" : "spa"][0]} bem maior que o outro ataque` };
}

// Pontua a tendência a tanque por stats, golpes, tipagem e cura com HP alto.
// Tanque com 3 pontos ou mais; sem moveset (wiki sem dados), com 2 ou mais.
function perfil(p) {
  const [hp, atk, def, spa, spd, spe] = p.s;
  const motivos = [];
  // Stats: HP conta em dobro (nature nenhuma aumenta HP, e é ele que segura o dano)
  const razao = ((2 * hp + def + spd) / 4) / ((Math.max(atk, spa) + spe) / 2);
  const pStats = razao >= 2 ? 3 : razao >= 1.3 ? 2 : razao >= 1.1 ? 1 : razao <= 0.8 ? -1 : 0;
  motivos.push({ pontos: pStats, texto: `Stats: HP (peso 2) e defesas ${razao >= 1 ? (razao * 100 - 100).toFixed(0) + "% acima" : (100 - razao * 100).toFixed(0) + "% abaixo"} de ataque e velocidade` });

  // Golpes: cada golpe de cura/proteção/defesa do moveset vale 1; os de TM/Move Tutor somam no máximo 0,5. Máximo 2.
  const doMoveset = (p.g || []).filter(defensivo).map(g => g[0]);
  const jaTem = conjunto(doMoveset);
  const extras = [...new Set(aprendiveis(p).filter(g => defensivo(g) && !jaTem.has(chave(g[0]))).map(g => g[0]))];
  const danosos = (p.g || []).filter(g => g[1] !== "Status").length;
  if (p.g || extras.length) {
    const soma = Math.min(2, doMoveset.length + (extras.length ? MAXIMO_APRENDIVEL_DEFESA : 0));
    const pGolpes = soma > 0 ? soma : danosos >= 6 ? -1 : 0;
    const partes = [doMoveset.length ? `moveset: ${doMoveset.join(", ")}` : "", extras.length ? `TM/tutor: ${extras.join(", ")}` : ""].filter(Boolean);
    motivos.push({ pontos: pGolpes, texto: partes.length ? `Golpes de cura/proteção/defesa (${partes.join("; ")})` : `Golpes: ${danosos} de dano e nenhum defensivo` });
  } else {
    motivos.push({ pontos: 0, texto: "Golpes: moveset não encontrado na wiki" });
  }

  const mult = Object.values(defesaPorTipo(p.t));
  const fraco = mult.filter(m => m > 1).length, resiste = mult.filter(m => m < 1).length;
  motivos.push({ pontos: resiste - fraco >= 4 ? 1 : fraco > resiste ? -1 : 0, texto: `Tipagem: resiste ou é imune a ${resiste} tipos, fraco a ${fraco}` });

  // Cura com HP alto: quem tem golpe de cura e o HP como maior stat recupera muito a cada cura
  const curas = [...new Set([...(p.g || []), ...aprendiveis(p)].filter(cura).map(g => g[0]))];
  const hpMaior = hp >= Math.max(atk, def, spa, spd, spe);
  if (curas.length) motivos.push({ pontos: hpMaior ? 1 : 0, texto: `Cura (${curas.join(", ")}): ${hpMaior ? `HP ${hp.toFixed(2)} é o maior stat, cada cura recupera muito` : `HP ${hp.toFixed(2)} não é o maior stat`}` });

  const pontos = motivos.reduce((s, m) => s + m.pontos, 0);
  const minimo = p.g ? 3 : 2;
  return { tanque: pontos >= minimo, pontos, minimo, motivos };
}

// Aumentar o que o pokémon faz melhor e diminuir o ataque que ele não usa.
// Atacante misto não tem ataque sobrando: perde a defesa mais baixa. Tanque misto perde o ataque mais baixo.
function sugerirNatures(p) {
  const [, atk, def, spa, spd] = p.s;
  const estilo = estiloDeAtaque(p), pf = perfil(p);
  const defesa = def >= spd ? "def" : "spd";
  const outroAtaque = estilo.ataque === "atk" ? "spa" : "atk";
  const caiAtacante = estilo.misto ? (def >= spd ? "spd" : "def") : outroAtaque;
  const caiTanque = estilo.misto ? (atk >= spa ? "spa" : "atk") : outroAtaque;
  const porque = cai => !estilo.misto ? `não usa ${STATS[cai][0]}`
    : cai === outroAtaque ? `${STATS[cai][0]} é o ataque mais fraco` : "usa os dois ataques, então perde a defesa mais baixa";
  const opcoes = [
    { foco: "Dano", sobe: estilo.ataque, desce: caiAtacante, porque: `ataque ${estilo.ataque === "atk" ? "físico" : "especial"} (${estilo.porque}); ${porque(caiAtacante)}` },
    { foco: "Velocidade", sobe: "spe", desce: caiAtacante, porque: `ataca mais rápido; ${porque(caiAtacante)}` },
    { foco: "Tanque", sobe: defesa, desce: caiTanque, porque: `${STATS[defesa][0]} é a defesa mais alta; ${porque(caiTanque)}` },
  ];
  const lista = opcoes.map(o => ({ ...o, nature: NATURES[o.sobe][o.desce] }));
  return { opcoes: lista, recomendada: pf.tanque ? 2 : 0, perfil: pf };
}

function acharPokemon(texto) {
  const t = chave(texto);
  return t && Object.keys(pokemons).find(n => chave(n) === t);
}

// Preço do TM no market, se ele estiver cadastrado na aba Preços (nome com "TM05", "TM 5"...)
function itemDoTM(c) {
  if (typeof itens === "undefined") return null;
  const [, tipo, num] = c.match(/^(TM|HM)(\d+)$/);
  return itens.find(i => {
    const m = i.nome.match(/\b(tm|hm)\s*0*(\d+)\b/i);
    return m && m[1].toUpperCase() === tipo && Number(m[2]) === Number(num);
  }) || null;
}
const precoTM = c => { const r = precoReferencia(itemDoTM(c)); return r ? `${fmt(r.valor)} HD` : ""; };

function desenharTipagem(tp) {
  const chips = (tipos, cls) => tipos.length ? tipos.map(t => `<span class="tipo ${cls}">${t}</span>`).join("") : `<span class="dica">nenhum</span>`;
  const linha = (rotulo, conteudo) => `<tr><th>${rotulo}</th><td>${conteudo}</td></tr>`;
  return `
    <h3>Tipagem</h3>
    <div class="tipagem">
      <table><caption>Defesa (dano que recebe)</caption>
        ${tp.defesa.filter(([, tipos]) => tipos.length).map(([r, tipos, cls]) => linha(r, chips(tipos, cls))).join("")}
      </table>
      <table><caption>Ataque com golpes do próprio tipo</caption>
        ${tp.ataque.map(a => linha(a.tipo, `<div>Forte contra ${chips(a.forte, "resiste")}</div><div>Fraco contra ${chips(a.fraco, "fraco")}</div>` +
          (a.nulo.length ? `<div>Sem efeito em ${chips(a.nulo, "fraco")}</div>` : ""))).join("")}
        ${tp.cobertura ? linha("Moveset", `<div>Super efetivo contra ${chips(tp.cobertura.forte, "resiste")}</div><div>Sem golpe forte contra ${chips(tp.cobertura.sem, "")}</div>`) : ""}
      </table>
    </div>`;
}

// Bolinha com a categoria do golpe: F físico, E especial, S status
const CAT = { "Físico": "F", "Especial": "E", "Status": "S" };
const iconeCat = cat => CAT[cat] ? `<i class="cat-${CAT[cat]}">${CAT[cat]}</i>` : "";
const dicaGolpe = (cat, tipo, efeito) => esc([cat, tipo, efeito].filter(Boolean).join(" · "));

// ---------- Imagens do PMDCollab ----------

const ehShiny = texto => /^\s*shiny\s/i.test(texto);
// Imagens do pokémon; no shiny, cada imagem que faltar fica a normal
function imagensDe(nome, shiny) {
  const x = pmd.pokemon[nome] || {}, s = shiny && x.s || {};
  return { r: s.r || x.r, a: s.a || x.a, shiny: shiny && !!(s.r || s.a) };
}
const retratoMini = nome => { const r = pmd.pokemon[nome]?.r; return r ? `<img class="retrato-mini" src="/static/pmd/retrato/${r.f}" alt="" loading="lazy">` : ""; };

const artista = id => {
  const [nome, contato] = pmd.artistas[id] || [id, ""];
  return contato ? `<a href="${esc(contato)}" target="_blank" rel="noopener">${esc(nome)}</a>` : esc(nome);
};
const PMD = `<a href="https://sprites.pmdcollab.org/" target="_blank" rel="noopener">PMDCollab</a>`;
const LICENCA = `<a href="https://creativecommons.org/licenses/by-nc/4.0/deed.pt-br" target="_blank" rel="noopener">CC BY-NC 4.0</a>`;

function creditoFicha(img) {
  const partes = [img.r && `Retrato: ${img.r.c.map(artista).join(", ")}`, img.a && `Sprite: ${img.a.c.map(artista).join(", ")}`].filter(Boolean);
  return partes.length ? `<div class="credito">${partes.join(" · ")} — ${PMD}, ${LICENCA}</div>` : "";
}

// Sprite animado: a imagem tem os quadros lado a lado; cada quadro dura d[i]/60 s. Para quando sai da tela.
const ZOOM = 2;
function animarSprites(raiz) {
  for (const el of raiz.querySelectorAll(".sprite[data-d]")) {
    const d = JSON.parse(el.dataset.d), w = Number(el.dataset.w) * ZOOM;
    let i = 0;
    const passo = () => {
      if (!el.isConnected) return;
      el.style.backgroundPositionX = `${-i * w}px`;
      setTimeout(passo, d[i] * 1000 / 60);
      i = (i + 1) % d.length;
    };
    passo();
  }
}
const spriteHTML = a => a ? `<div class="sprite" data-w="${a.w}" data-d="${JSON.stringify(a.d)}"
  style="width:${a.w * ZOOM}px;height:${a.h * ZOOM}px;background-image:url('/static/pmd/sprite/${a.f}');background-size:${a.w * a.d.length * ZOOM}px ${a.h * ZOOM}px"></div>` : "";

// Painel "Créditos" do topo: fontes dos dados e lista completa de artistas (licença CC BY-NC 4.0 pede crédito a todos)
async function desenharCreditos() {
  const alvo = $("#painel-creditos");
  if (alvo.innerHTML) return;
  await carregarPokemons();
  const usados = Object.keys(pmd.artistas).sort((a, b) => pmd.artistas[a][0].localeCompare(pmd.artistas[b][0], "pt", { sensitivity: "base" }));
  alvo.innerHTML = `
    <h3>Créditos</h3>
    <p class="dica">Programa de fã, não oficial (veja "Sobre", no botão ⓘ).</p>
    <p>Dados dos pokémon, golpes, TMs, held items, breeding e quests: <a href="https://wiki.otponline.com/" target="_blank" rel="noopener">wiki do otPokemon</a>
      e <a href="https://pokeapi.co/" target="_blank" rel="noopener">PokéAPI</a>. Os vídeos das quests são dos criadores no YouTube, com os links publicados na wiki.</p>
    <p>Fonte: Atkinson Hyperlegible (Braille Institute), licença SIL Open Font License. Gráficos: Chart.js (MIT).
      Leitura dos prints: RapidOCR e modelos do PaddleOCR (Apache 2.0), no seu computador.</p>
    <p>Retratos e sprites do <a href="https://sprites.pmdcollab.org/" target="_blank" rel="noopener">PMD Sprite Repository</a>
      (<a href="https://github.com/PMDCollab/SpriteCollab" target="_blank" rel="noopener">PMDCollab/SpriteCollab</a>), licença ${LICENCA}:
      uso não comercial e com crédito aos artistas. Modificação: dos sprites só é mostrada a animação parada, virada para a frente.
      Pokémon e os nomes dos pokémon são marcas de The Pokémon Company, Nintendo, Game Freak e Creatures; CHUNSOFT é a desenvolvedora de Pokémon Mystery Dungeon.</p>
    <p>Créditos completos do PMDCollab, por artista e imagem:
      <a href="/static/pmd/spritebot_credits.txt" target="_blank" rel="noopener">spritebot_credits.txt</a>.</p>
    <p>Artistas das imagens usadas aqui (${usados.length}):</p>
    <div class="artistas">${usados.map(id => `<span>${artista(id)}</span>`).join("")}</div>`;
}

// Aceita o código ("tm5", "TM05"), o texto da lista ("TM05 - Waterfall") ou o golpe ("waterfall", "heal bell")
function acharGolpe(texto) {
  const t = texto.trim().toLowerCase();
  const cod = t.match(/^(tm|hm)\s*0*(\d+)/);
  if (cod) {
    const c = Object.keys(tms).find(c => c.slice(0, 2).toLowerCase() === cod[1] && Number(c.slice(2)) === Number(cod[2]));
    return c ? tms[c][0] : null;
  }
  return Object.keys(golpesInfo).find(g => chave(g) === chave(t)) || null;
}

function desenharGolpe() {
  const alvo = $("#resultado-tm");
  const texto = $("#busca-tm").value;
  if (!texto.trim()) return;
  const golpe = acharGolpe(texto);
  if (!golpe) { alvo.innerHTML = `<div class="dica">Golpe não encontrado. Digite o número do TM (TM05) ou o nome do golpe em inglês.</div>`; return; }
  const [cat, tipo, efeito] = golpesInfo[golpe];
  const c = codigoDoGolpe(golpe);
  const porTM = c ? Object.keys(pokemons).filter(n => (pokemons[n].m || []).includes(c)) : [];
  const porTutor = Object.keys(pokemons).map(n => [n, (pokemons[n].u || []).find(u => u[0] === golpe)]).filter(([, u]) => u);
  const noMoveset = Object.keys(pokemons).filter(n => (pokemons[n].g || []).some(g => g[0] === golpe));
  const item = c && itemDoTM(c);
  const botoes = lista => `<div class="aprendem">${lista.map(([n, extra]) => `<button data-pokemon="${esc(n)}">${retratoMini(n)}${esc(n)}${extra ? ` <span class="dica">${extra}</span>` : ""}</button>`).join("")}</div>`;
  const grupo = (titulo, lista) => lista.length ? `<div class="dica" style="margin-top:12px">${titulo}</div>${botoes(lista)}` : "";
  alvo.innerHTML = `
    <div><b>${c ? `${c} · ` : ""}${esc(golpe)}</b> <span class="move" style="margin-left:6px">${iconeCat(cat)}${cat}</span><span class="tipo">${tipo}</span>${efeito ? ` <span class="dica">${esc(efeito)}</span>` : ""}</div>
    ${c ? `<div class="dica" style="margin-top:6px">${item ? (precoReferencia(item) ? `No market: ${precoReferencia(item).fonte} ${fmt(precoReferencia(item).valor)} HD · menor agora ${fmt(item.atual)} HD ${selo(item)}` : "No market: sem registro") + ` <span class="dica">(item "${esc(item.nome)}")</span>` : `Preço: cadastre "${c} - ${esc(golpe)}" na aba Mercado para acompanhar.`}</div>` : ""}
    ${grupo(`Aprendem pelo ${c}: ${porTM.length} pokémon`, porTM.map(n => [n]))}
    ${grupo(`Aprendem no Move Tutor: ${porTutor.length} pokémon (custo em Battle Points)`, porTutor.map(([n, u]) => [n, `${u[1]} BP`]))}
    ${grupo(`Já vem no moveset: ${noMoveset.length} pokémon`, noMoveset.map(n => [n]))}
    ${porTM.length + porTutor.length + noMoveset.length ? '<div class="dica" style="margin-top:8px">Clique num pokémon para abrir a ficha.</div>' : ""}`;
}

// ---------- Held items (helditems.json: nome -> {c: categoria, e: efeito, p: pokémon que usam}) ----------

// Item cadastrado na aba Preços com esse nome (para o preço)
const itemPorNome = nome => nome && typeof itens !== "undefined" && itens.find(i => i.nome.toLowerCase() === nome.trim().toLowerCase()) || null;
const acharHeld = texto => Object.keys(heldItems).find(n => chave(n) === chave(texto)) || null;

function desenharHeld() {
  const alvo = $("#resultado-held");
  const texto = $("#busca-held").value;
  if (!texto.trim()) return;
  const nome = acharHeld(texto);
  if (!nome) { alvo.innerHTML = `<div class="dica">Held item não encontrado. Use o nome em inglês, como no jogo.</div>`; return; }
  const h = heldItems[nome], item = itemPorNome(nome), ref = precoReferencia(item);
  alvo.innerHTML = `
    <div><b>${esc(nome)}</b> <span class="tipo">${esc(h.c)}</span></div>
    ${h.e ? `<div style="margin-top:6px">${esc(h.e)}</div>` : ""}
    <div class="dica" style="margin-top:6px">${item ? (ref ? `No market: ${ref.fonte} ${fmt(ref.valor)} HD · menor agora ${fmt(item.atual)} HD ${selo(item)}` : "No market: sem registro")
      : `Preço: cadastre "${esc(nome)}" na aba Mercado para acompanhar.`}</div>
    ${h.p.length ? `<div class="dica" style="margin-top:12px">Usado por:</div><div class="aprendem">${h.p.map(n => acharPokemon(n) || n)
      .map(n => `<button data-pokemon="${esc(n)}">${retratoMini(n)}${esc(n)}</button>`).join("")}</div>` : ""}`;
}

// Clicar num golpe da ficha abre a busca; clicar num pokémon da busca abre a ficha dele
function abrirGolpe(texto) {
  $("#busca-tm").value = texto;
  desenharGolpe();
  $("#tms").scrollIntoView({ behavior: "smooth", block: "start" });
}
function abrirPokemon(nome) {
  $("#busca-pokemon").value = nome;
  desenharNature();
  $("#natures").scrollIntoView({ behavior: "smooth", block: "start" });
}

function desenharNature() {
  const alvo = $("#resultado-nature");
  const texto = $("#busca-pokemon").value;
  if (!texto.trim()) return;
  const nome = acharPokemon(texto);
  if (!nome) { alvo.innerHTML = `<div class="dica">Pokémon não encontrado na lista do jogo (gerações 1 a 7, 8ª geração de eventos e formas regionais). Use o nome em inglês, como no jogo.</div>`; return; }
  const p = pokemons[nome];
  const { opcoes, recomendada, perfil: pf } = sugerirNatures(p);
  const principal = opcoes[recomendada];
  const card = (rotulo, i, k) =>
    `<div class="card ${k === principal.sobe ? "sobe" : k === principal.desce ? "desce" : ""}"><span>${rotulo}</span><b>${p.s[i].toFixed(2)}</b></div>`;
  const sinal = n => n > 0 ? `+${n}` : String(n);
  const img = imagensDe(nome, ehShiny(texto));
  alvo.innerHTML = `
    <div class="cabeca">
      ${img.r ? `<img class="retrato" src="/static/pmd/retrato/${img.r.f}" alt="">` : ""}${spriteHTML(img.a)}
      <div>
        <div><b>${img.shiny ? "Shiny " : ""}${esc(nome)}</b>${p.t.map(t => `<span class="tipo">${t}</span>`).join("")}
          <span class="badge ${pf.tanque ? "s-bom" : "s-normal"}" style="margin-left:8px">${pf.tanque ? "Tanque" : "Atacante"} · ${sinal(pf.pontos)} pts</span></div>
        ${creditoFicha(img)}
      </div>
    </div>
    <div class="stats-base">${card("HP", 0)}${Object.entries(STATS).map(([k, [r, i]]) => card(r, i, k)).join("")}</div>
    ${p.w ? "" : `<div class="dica">A wiki não tem stats nem moveset deste pokémon (página vazia ou ficha de lendário): stats estimados (oficial × 0,03).</div>`}
    <ul class="motivos">${pf.motivos.map(m => `<li><b class="${m.pontos > 0 ? "sobe" : m.pontos < 0 ? "desce" : ""}">${sinal(m.pontos)}</b> ${esc(m.texto)}</li>`).join("")}
      <li class="dica">${pf.minimo} pontos ou mais = tanque, e a nature recomendada passa a ser a de Tanque.</li></ul>
    ${p.g ? `<div class="moves">${p.g.map(g => `<span class="move" title="${dicaGolpe(g[1], g[2], g[3])}">${iconeCat(g[1])}${esc(g[0])}</span>`).join("")}</div>` : ""}
    ${desenharTipagem(tipagem(p))}
    ${p.m ? `<h3>TMs que aprende (${p.m.length})</h3>
      <div class="lista-tms">${p.m.map(c => `<button class="move" data-golpe="${c}" title="${dicaGolpe(tms[c][1], tms[c][2], tms[c][3])}">${iconeCat(tms[c][1])}<span class="cod">${c}</span> ${esc(tms[c][0])}${precoTM(c) ? ` <span class="preco">${precoTM(c)}</span>` : ""}</button>`).join("")}</div>` : ""}
    ${p.u ? `<h3>Move Tutor (${p.u.length})</h3>
      <div class="lista-tms">${p.u.map(([g, custo]) => { const [cat, tipo, efeito] = golpesInfo[g] || []; return `<button class="move" data-golpe="${esc(g)}" title="${dicaGolpe(cat, tipo, efeito)}">${iconeCat(cat)}${esc(g)} <span class="cod">${custo} BP</span></button>`; }).join("")}</div>` : ""}
    <h3>Nature</h3>
    <table>
      <thead><tr><th>Foco</th><th>Nature</th><th>Sobe 10%</th><th>Desce 10%</th><th>Por quê</th></tr></thead>
      <tbody>${opcoes.map((o, i) => `<tr class="${i === recomendada ? "principal" : ""}">
        <td>${o.foco}${i === recomendada ? ' <span class="dica">(recomendada)</span>' : ""}</td>
        <td class="nat">${o.nature}</td><td class="sobe">+${STATS[o.sobe][0]}</td><td class="desce">−${STATS[o.desce][0]}</td>
        <td class="porque">${esc(o.porque)}</td></tr>`).join("")}</tbody>
    </table>`;
  animarSprites(alvo);
}

$("#busca-pokemon").addEventListener("input", async () => { await carregarPokemons(); desenharNature(); });
$("#busca-tm").addEventListener("input", async () => { await carregarPokemons(); desenharGolpe(); });
$("#resultado-nature").addEventListener("click", e => { const b = e.target.closest("[data-golpe]"); if (b) abrirGolpe(b.dataset.golpe); });
$("#busca-held").addEventListener("input", async () => { await carregarPokemons(); desenharHeld(); });
$("#resultado-held").addEventListener("click", e => { const b = e.target.closest("[data-pokemon]"); if (b) abrirPokemon(b.dataset.pokemon); });
$("#resultado-tm").addEventListener("click", e => { const b = e.target.closest("[data-pokemon]"); if (b) abrirPokemon(b.dataset.pokemon); });
