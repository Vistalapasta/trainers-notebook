// Aba Breeding (regras da página "Day Care" da wiki). Usa os dados de pokemon.js: e = egg groups, x = sexo
// ("MF", "M", "F" ou "-" sem sexo), b = o que nasce do ovo (primeiro estágio da família, sem os bebês que o
// Day Care Man não tira do ovo), ep = 1 quando os egg groups vieram só da PokéAPI (a wiki não confirma). ovos.json (opcional, das páginas "Green Egg"… da wiki): cor -> {h: horas, p: [pokémon]}.
const GRUPO_SEM_OVO = "Undiscovered";
const DITTO = "Ditto";
const CORES_OVO = { Verde: 6, Laranja: 18, Rosa: 30, Roxo: 42 };
const INCUBADORAS = [["Default Incubator", 1], ["Great Incubator", 2], ["Super Incubator", 2.5]];
// Balls que não passam para o filhote: ele vem na Poké Ball
const BALLS_ESPECIAIS = ["Cherish Ball", "Heal Ball", "Heavy Ball", "Moon Ball", "Net Ball", "Beast Ball", "Old Ball", "Wing Ball", "Feather Ball", "Master Ball"];
const BALLS_COMUNS = ["Poké Ball", "Great Ball", "Super Ball", "Ultra Ball"];
const OVOS_PACHIRISU = 20;
const XP_POR_LEVEL_TAXA = { abaixo50: 3, acima50: 4 };  // dólares por XP no Day Care

let ovos = undefined;  // undefined = não carregado; null = sem o arquivo
let ovosChocados = 0;

async function carregarOvos() {
  if (ovos !== undefined) return;
  try { const r = await fetch("/static/ovos.json"); ovos = r.ok ? await r.json() : null; } catch { ovos = null; }
}
const corDoOvo = nome => ovos && Object.keys(ovos).find(c => ovos[c].p.includes(nome));
const ehDitto = nome => nome === DITTO;
// Egg group só dos jogos oficiais (a wiki não confirma): o app diz que cruza, mas o jogo talvez não deixe
const incerto = p => p.ep && !p.e.includes(GRUPO_SEM_OVO);
const ehEspecial = ball => BALLS_ESPECIAIS.some(b => chave(b) === chave(ball || ""));
const nomeBall = ball => [...BALLS_COMUNS, ...BALLS_ESPECIAIS].find(b => chave(b) === chave(ball || "")) || (ball || "").trim();
const sexoTexto = { M: "♂", F: "♀", "-": "sem sexo" };
const horas = h => { const m = Math.round(h * 60); return `${Math.floor(m / 60)}h${m % 60 ? String(m % 60).padStart(2, "0") : ""}`; };

// Estado de um dos pais, lido da tela
function lerPai(i) {
  const caixa = $(`#pai-${i}`);
  const texto = caixa.querySelector(".pai-nome").value;
  const nome = acharPokemon(texto);
  const p = nome && pokemons[nome];
  return {
    texto, nome, p,
    sexo: p ? (ehDitto(nome) ? "-" : p.x === "MF" ? caixa.querySelector(".pai-sexo").value : p.x) : "",
    ball: caixa.querySelector(".pai-ball").value.trim(),
    everstone: caixa.querySelector(".pai-everstone").checked,
    nature: caixa.querySelector(".pai-nature").value,
  };
}

// Regras para sair um ovo. Devolve a lista de verificações [ok, texto] e quem é a mãe (de quem vem a família)
function verificarCasal(a, b) {
  const regras = [];
  const dittos = [a, b].filter(x => ehDitto(x.nome)).length;
  const semOvo = [a, b].filter(x => !ehDitto(x.nome) && x.p.e.includes(GRUPO_SEM_OVO));
  regras.push([!semOvo.length, semOvo.length
    ? `${semOvo.map(x => x.nome).join(" e ")} não dá${semOvo.length > 1 ? "o" : ""} ovo (grupo Undiscovered: lendários, bebês e exclusivos de quest, evento ou sistema)`
    : "Os dois podem dar ovo"]);
  if (semOvo.length) return { regras };
  if (dittos === 2) {
    regras.push([false, "Dois Ditto não cruzam entre si"]);
    return { regras };
  }
  let mae = null;
  if (dittos === 1) {
    const outro = ehDitto(a.nome) ? b : a;
    regras.push([true, `Com Ditto, qualquer pokémon que dá ovo cruza (inclusive sem sexo ou de um sexo só); nasce da família de ${outro.nome}`]);
    mae = outro;
  } else {
    const comuns = a.p.e.filter(g => b.p.e.includes(g) && g !== GRUPO_SEM_OVO);
    regras.push([comuns.length > 0, comuns.length ? `Egg group em comum: ${comuns.join(", ")}` : `Sem egg group em comum (${a.nome}: ${a.p.e.join(", ")}; ${b.nome}: ${b.p.e.join(", ")})`]);
    const opostos = (a.sexo === "M" && b.sexo === "F") || (a.sexo === "F" && b.sexo === "M");
    const semSexo = [a, b].filter(x => x.sexo === "-");
    regras.push([opostos, semSexo.length ? `${semSexo.map(x => x.nome).join(" e ")} não ${semSexo.length > 1 ? "têm" : "tem"} sexo: só cruza${semSexo.length > 1 ? "m" : ""} com Ditto`
      : opostos ? "Sexos diferentes" : `Os dois são ${sexoTexto[a.sexo]}: precisam ter sexos diferentes`]);
    mae = a.sexo === "F" ? a : b.sexo === "F" ? b : null;
  }
  return { regras, mae };
}

// Pokébola do filhote (seção "Escolha de Pokeball no Breeding" da wiki). Ball especial nunca passa: vira Poké Ball,
// exceto mãe em ball especial + pai da mesma espécie, que passa a ball do pai.
function ballDoFilhote(a, b, mae) {
  const passa = x => !x.ball ? `a ball de ${x.nome} (informe acima)` : ehEspecial(x.ball) ? `Poké Ball (${nomeBall(x.ball)} não passa)` : nomeBall(x.ball);
  if (ehDitto(a.nome) || ehDitto(b.nome)) return `${passa(mae)}: com Ditto, vem a ball do outro pokémon`;
  const pai = mae === a ? b : a;
  const mesma = chave(a.nome) === chave(b.nome);
  if (!mesma) return `${passa(mae)}: espécies diferentes, vem a ball da mãe`;
  if (ehEspecial(mae.ball) && !ehEspecial(pai.ball)) return `${passa(pai)}: mãe em ${nomeBall(mae.ball)} com pai da mesma espécie, vem a ball do pai`;
  return `50% ${passa(mae)} (mãe) e 50% ${passa(pai)} (pai): mesma espécie`;
}

function natureDoFilhote(a, b) {
  const com = [a, b].filter(x => x.everstone);
  const sem = com.filter(x => !x.nature);
  if (!com.length) return "Aleatória (nenhum dos pais com Everstone)";
  if (sem.length) return `Escolha a nature de ${sem.map(x => x.nome).join(" e ")} para ver o resultado`;
  if (com.length === 1) return `<b>${com[0].nature}</b> (de ${esc(com[0].nome)}, que segura a Everstone; a Everstone é consumida)`;
  return a.nature === b.nature ? `<b>${a.nature}</b> (os dois têm a mesma; as duas Everstones são consumidas)`
    : `50% <b>${a.nature}</b> e 50% <b>${b.nature}</b> (os dois seguram Everstone; as duas são consumidas)`;
}

function desenharOvo(nome) {
  const cor = corDoOvo(nome);
  if (ovos === null) return `<div class="dica">Cor do ovo: ainda sem dados. Exporte as páginas "Green Egg", "Orange Egg", "Pink Egg" e "Purple Egg" da wiki.</div>`;
  if (!cor) return `<div class="dica">Cor do ovo: a wiki não lista ${esc(nome)} em nenhum ovo (as páginas dos ovos estão incompletas, principalmente a 6ª e a 7ª geração). Veja no jogo ao chocar.</div>`;
  const h = ovos[cor].h;
  return `<div>Ovo <b>${cor}</b>: ${INCUBADORAS.map(([n, v]) => `${n.replace(" Incubator", "")} ${horas(h / v)}`).join(" · ")}</div>`;
}

function desenharCasal() {
  const alvo = $("#resultado-casal");
  const a = lerPai(1), b = lerPai(2);
  for (const [i, x] of [[1, a], [2, b]]) atualizarPai(i, x);
  if (!a.nome || !b.nome) {
    alvo.innerHTML = `<div class="dica">${[a, b].some(x => x.texto.trim() && !x.nome) ? "Pokémon não encontrado (use o nome em inglês, como no jogo)." : "Escolha os dois pokémon do casal."}</div>`;
    return;
  }
  const { regras, mae } = verificarCasal(a, b);
  const ok = regras.every(r => r[0]);
  const nasce = ok && mae ? mae.p.b : null;
  const semConfirmar = [a, b].filter(x => incerto(x.p)).map(x => x.nome);
  const aviso = semConfirmar.length ? `<div class="aviso-breeding">⚠ A wiki não informa o egg group de ${esc([...new Set(semConfirmar)].join(" e "))}:
    o resultado usa os dados dos jogos oficiais, e no otPokemon ${semConfirmar.length > 1 ? "eles" : "ele"} talvez não possa${semConfirmar.length > 1 ? "m" : ""} cruzar
    (como os exclusivos de quest e evento). Confira no jogo antes de deixar no Day Care.</div>` : "";
  alvo.innerHTML = `${aviso}
    <div class="veredito ${!ok ? "s-caro" : aviso ? "aviso-fora" : "s-ótimo"}">${!ok ? "Não dão ovo" : aviso ? "Talvez possam dar ovo (sem confirmação da wiki)" : "Podem dar ovo"}</div>
    <ul class="regras">${regras.map(([v, t]) => `<li class="${v ? "sobe" : "desce"}">${v ? "✓" : "✗"} ${esc(t)}</li>`).join("")}</ul>
    ${ok && !mae ? `<div class="dica">Escolha o sexo de cada um para saber quem é a mãe.</div>` : ""}
    ${nasce ? `<div class="nasce">${retratoMini(nasce)}<div>Nasce <button class="link" data-ficha="${esc(nasce)}">${esc(nasce)}</button>
        <span class="dica">(família ${ehDitto(a.nome) || ehDitto(b.nome) ? "do pokémon que não é o Ditto" : "da mãe"}; sexo ${pokemons[nasce]?.x === "MF" ? "aleatório" : sexoTexto[pokemons[nasce]?.x] || "?"})</span></div></div>
      ${desenharOvo(nasce)}
      <div>Nature: ${natureDoFilhote(a, b)}</div>
      <div>Pokébola: ${esc(ballDoFilhote(a, b, mae))}</div>` : ""}`;
  desenharParceiros(a.nome ? a : null);
}

// Ajusta o seletor de sexo de cada pai à espécie (só aparece quando ela pode ser dos dois sexos)
function atualizarPai(i, x) {
  const caixa = $(`#pai-${i}`);
  const sel = caixa.querySelector(".pai-sexo");
  sel.hidden = !(x.p && x.p.x === "MF" && !ehDitto(x.nome));
  caixa.querySelector(".pai-info").innerHTML = x.p
    ? `${retratoMini(x.nome)}<span>${x.p.t.map(t => `<span class="tipo">${t}</span>`).join("")}</span>
       <span class="dica">${ehDitto(x.nome) ? "cruza com qualquer um que dá ovo" : `${x.p.e.join(", ")}${x.p.x !== "MF" ? ` · ${sexoTexto[x.p.x]}` : ""}`}</span>` : "";
  caixa.querySelector(".pai-nature").disabled = !caixa.querySelector(".pai-everstone").checked;
}

// Com quem o pokémon pode cruzar: mesmo egg group, sexo compatível, e sempre o Ditto
function desenharParceiros(x) {
  const alvo = $("#resultado-parceiros");
  if (!x) { alvo.innerHTML = `<div class="dica">Escolha o primeiro pokémon do casal para ver com quem ele pode cruzar.</div>`; return; }
  const titulo = `<h3>Com quem ${esc(x.nome)} cruza</h3>${incerto(x.p) ? `<div class="aviso-breeding">⚠ A wiki não informa o egg group de ${esc(x.nome)}: a lista usa os dados dos jogos oficiais e talvez ele não possa cruzar no otPokemon.</div>` : ""}`;
  if (ehDitto(x.nome)) { alvo.innerHTML = `${titulo}<div class="dica">Ditto cruza com qualquer pokémon que dá ovo (menos outro Ditto).</div>`; return; }
  if (x.p.e.includes(GRUPO_SEM_OVO)) { alvo.innerHTML = `${titulo}<div class="dica">Não dá ovo (grupo Undiscovered).</div>`; return; }
  const ditto = `<button data-parceiro="${DITTO}">${retratoMini(DITTO)}Ditto</button>`;
  if (x.p.x === "-") { alvo.innerHTML = `${titulo}<div class="dica">Sem sexo: só cruza com Ditto.</div><div class="aprendem">${ditto}</div>`; return; }
  // Precisa existir o sexo oposto: quem é só ♂ procura quem pode ser ♀, e vice-versa
  const precisa = x.p.x === "M" ? "F" : x.p.x === "F" ? "M" : null;
  const serve = p => p.x !== "-" && (!precisa || p.x === "MF" || p.x === precisa) && !(x.p.x === p.x && p.x !== "MF");
  const grupos = x.p.e.filter(g => g !== GRUPO_SEM_OVO).map(g => [g, Object.keys(pokemons).filter(n => n !== DITTO && pokemons[n].e.includes(g) && !pokemons[n].e.includes(GRUPO_SEM_OVO) && serve(pokemons[n]))]);
  alvo.innerHTML = `${titulo}
    <div class="dica">Clique para colocar como o segundo do casal.</div>
    <div class="aprendem">${ditto}</div>
    ${grupos.map(([g, lista]) => `<details class="grupo-ovo" ${lista.length <= 40 ? "open" : ""}><summary><b>${g}</b> <span class="dica">(${lista.length})</span></summary>
      <div class="aprendem">${lista.map(n => `<button data-parceiro="${esc(n)}" ${incerto(pokemons[n]) ? `title="A wiki não informa o egg group: talvez não possa cruzar"` : ""}>${retratoMini(n)}${esc(n)}${incerto(pokemons[n]) ? ` <span class="aviso-fora">?</span>` : ""}</button>`).join("")}</div></details>`).join("")}
    ${grupos.some(([, l]) => l.some(n => incerto(pokemons[n]))) ? `<div class="dica">? = a wiki não informa o egg group; talvez não possa cruzar.</div>` : ""}`;
}

// Custo do Day Care: dólares por XP (3 abaixo do level 50, 4 a partir dele), em HD
function desenharCusto() {
  const xp = Number($("#dc-xp").value) || 0, level = Number($("#dc-level").value) || 0;
  const taxa = level && level < 50 ? XP_POR_LEVEL_TAXA.abaixo50 : XP_POR_LEVEL_TAXA.acima50;
  $("#dc-custo").innerHTML = xp ? `${fmt(xp * taxa)} dólares = <b>${fmt(xp * taxa / 100)} HD</b> <span class="dica">(${taxa} dólares por XP)</span>` : "";
}

function desenharContador() {
  const falta = OVOS_PACHIRISU - ovosChocados;
  $("#ovos-chocados").textContent = ovosChocados;
  $("#ovos-pachirisu").innerHTML = falta > 0 ? `Faltam <b>${falta}</b> para o Special Pachirisu egg (chance de Shiny Pachirisu).`
    : `Chegou nos ${OVOS_PACHIRISU}: o Day Care Man dá o Special Pachirisu egg.`;
  $("#barra-ovos").style.width = `${Math.min(100, ovosChocados / OVOS_PACHIRISU * 100)}%`;
}
async function mudarContador(delta) {
  ovosChocados = Math.max(0, ovosChocados + delta);
  desenharContador();
  try { await api("/api/contadores/ovos_chocados", { method: "PUT", body: JSON.stringify({ valor: ovosChocados }) }); }
  catch (e) { alert(e.message); }
}

let breedingIniciado = false;
async function abrirBreeding() {
  await carregarPokemons();
  await carregarOvos();
  if (!breedingIniciado) {
    breedingIniciado = true;
    const natures = Object.values(NATURES).flatMap(Object.values).sort();
    for (const sel of document.querySelectorAll(".pai-nature")) sel.innerHTML = `<option value="">nature…</option>` + natures.map(n => `<option>${n}</option>`).join("");
    $("#lista-balls").innerHTML = [...BALLS_COMUNS, ...BALLS_ESPECIAIS].map(b => `<option value="${b}">`).join("");
    $("#tabela-ovos").innerHTML = `<thead><tr><th>Ovo</th>${INCUBADORAS.map(([n, v]) => `<th>${n.replace(" Incubator", "")} <span class="dica">${v}×</span></th>`).join("")}</tr></thead>
      <tbody>${Object.entries(CORES_OVO).map(([c, h]) => `<tr><td>${c}</td>${INCUBADORAS.map(([, v]) => `<td>${horas(h / v)}</td>`).join("")}</tr>`).join("")}</tbody>`;
    try { ovosChocados = (await api("/api/contadores/ovos_chocados")).valor; } catch { }
  }
  desenharContador();
  desenharCasal();
}

$("#casal").addEventListener("input", desenharCasal);
$("#casal").addEventListener("change", desenharCasal);
$("#casal").addEventListener("click", e => {
  const f = e.target.closest("[data-ficha]");
  if (f) { history.replaceState(null, "", "#busca"); mostrarAba("busca"); abrirPokemon(f.dataset.ficha); }
});
$("#resultado-parceiros").addEventListener("click", e => {
  const b = e.target.closest("[data-parceiro]");
  if (!b) return;
  $("#pai-2 .pai-nome").value = b.dataset.parceiro;
  desenharCasal();
  $("#casal").scrollIntoView({ behavior: "smooth", block: "start" });
});
$("#dc-xp").addEventListener("input", desenharCusto);
$("#dc-level").addEventListener("input", desenharCusto);
$("#ovo-mais").addEventListener("click", () => mudarContador(1));
$("#ovo-menos").addEventListener("click", () => mudarContador(-1));
