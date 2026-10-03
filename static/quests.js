// Aba Jogo > Quests: as quests da página "Quests" da wiki (quests.json, gerado por ferramentas/gerar_quests.py) com
// level, premium e prêmio, e a marcação das feitas (tabela quests_feitas, pelo título da página na wiki).
// O level e o premium do jogador e os filtros ficam no navegador (só servem para filtrar).
const WIKI = "https://wiki.otponline.com/";
let quests = null, questsFeitas = {};
let filtroQuests = { busca: "", grupo: "", mostrar: "afazer", nivel: "", premium: true };
try { Object.assign(filtroQuests, JSON.parse(localStorage.getItem("filtroQuests") || "{}")); } catch {}

async function abrirQuests() {
  if (!quests) quests = await (await fetch("/static/quests.json")).json();
  questsFeitas = await api("/api/quests-feitas");
  for (const [k, v] of Object.entries(filtroQuests)) {
    const el = $(`#quests-filtros [name="${k}"]`);
    if (el) el.type === "checkbox" ? el.checked = v : el.value = v;
  }
  desenharQuests();
}

// Dá para fazer agora: level do jogador alcança (ou sem level informado) e, se é premium, o jogador tem premium
const alcanca = q => (!filtroQuests.nivel || q.l == null || q.l <= Number(filtroQuests.nivel)) && (!q.p || filtroQuests.premium);

function desenharQuests() {
  const f = filtroQuests, busca = f.busca.trim().toLowerCase();
  const lista = quests.filter(q => (!f.grupo || q.g === f.grupo)
      && (f.mostrar === "todas" || (f.mostrar === "feitas") === !!questsFeitas[q.w])
      && (!busca || q.n.toLowerCase().includes(busca) || q.r.toLowerCase().includes(busca)))
    .sort((a, b) => alcanca(b) - alcanca(a) || (a.l ?? 0) - (b.l ?? 0) || a.n.localeCompare(b.n, "pt-BR"));
  const feitas = quests.filter(q => questsFeitas[q.w]).length;
  const prontas = quests.filter(q => !questsFeitas[q.w] && alcanca(q)).length;
  $("#quests-resumo").innerHTML = `<b>${feitas}</b> de ${quests.length} feitas` +
    (f.nivel || !f.premium ? ` · <b>${prontas}</b> a fazer que você já pode` : "");
  $("#quests-lista").innerHTML = lista.length ? `
    <table><thead><tr><th></th><th>Quest</th><th class="num">Level</th><th title="Precisa de premium">Premium</th><th>Prêmio</th><th></th></tr></thead>
    <tbody>${lista.map(q => `<tr class="${questsFeitas[q.w] ? "feita" : alcanca(q) ? "" : "longe"}">
      <td><input type="checkbox" data-quest="${esc(q.w)}" ${questsFeitas[q.w] ? "checked" : ""} title="Marcar como feita"></td>
      <td><a href="${WIKI}${encodeURIComponent(q.w.replace(/ /g, "_"))}" target="_blank" rel="noopener" title="Abrir na wiki (requisitos e passo a passo)">${esc(q.n)}</a>
        ${q.g !== "Quest" ? `<span class="cat">${q.g}</span>` : ""}
        ${questsFeitas[q.w] ? `<br><span class="cat">feita em ${new Date(questsFeitas[q.w].replace(" ", "T")).toLocaleDateString("pt-BR")}</span>` : ""}</td>
      <td class="num">${q.l ?? "—"}</td>
      <td>${q.p ? "★ sim" : ""}</td>
      <td class="premio">${esc(q.r) || '<span class="dica">não informado</span>'}</td>
      <td>${q.v ? `<a href="${esc(q.v)}" target="_blank" rel="noopener" title="Vídeo da quest">▶ vídeo</a>` : ""}</td></tr>`).join("")}</tbody></table>`
    : `<div class="vazio">${f.mostrar === "feitas" ? "Nenhuma quest feita ainda." : "Nenhuma quest com esses filtros."}</div>`;
}

$("#quests-filtros").addEventListener("input", e => {
  const el = e.target;
  if (!el.name) return;
  filtroQuests[el.name] = el.type === "checkbox" ? el.checked : el.value;
  try { localStorage.setItem("filtroQuests", JSON.stringify(filtroQuests)); } catch {}
  desenharQuests();
});
$("#quests-lista").addEventListener("change", async e => {
  const quest = e.target.dataset.quest;
  if (!quest) return;
  try { await api("/api/quests-feitas", { method: "PUT", body: JSON.stringify({ quest, feita: e.target.checked }) }); }
  catch (err) { return alert(err.message); }
  questsFeitas = await api("/api/quests-feitas");
  desenharQuests();
});
