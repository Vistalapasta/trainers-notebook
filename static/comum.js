// Funções usadas pela página principal e pelo modo mini
const $ = s => document.querySelector(s);
const fmt = v => v == null ? "—" : v.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
const pct = v => v == null ? "—" : (v > 0 ? "+" : "") + (v * 100).toFixed(1) + "%";

async function api(url, opts = {}) {
  const r = await fetch(url, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).erro || "Erro " + r.status);
  return r.status === 204 ? null : r.json();
}

function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

// Preço de referência de um item do market para as outras abas (TMs, times): a média de mercado de 30 dias;
// sem ela, o mercado do último registro. null se o item não tem preço.
function precoReferencia(i) {
  if (!i) return null;
  if (i.media30 != null) return { valor: i.media30, fonte: "média 30d" };
  if (i.mercado_atual != null) return { valor: i.mercado_atual, fonte: "último mercado" };
  return null;
}

// Selo do sinal já com a diferença para a média (ex.: "ótimo -18.0%")
function selo(i) {
  const diff = i.diff30 != null && i.sinal !== "poucos dados" ? " " + pct(i.diff30) : "";
  return `<span class="badge s-${i.sinal.split(" ")[0]}" title="Mercado atual vs média de mercado de 30 dias">${i.sinal}${diff}</span>`;
}

// Alertas: pergunta ao servidor a cada 3 s. Cada alerta novo vira notificação do
// Windows uma vez só, mesmo com a página principal e o modo mini abertos juntos.
function lerNotificado() { try { return Number(localStorage.getItem("alertaNotificado") || 0); } catch { return 0; } }
function gravarNotificado(id) { try { localStorage.setItem("alertaNotificado", String(id)); } catch {} }

const ICONE_ALERTA = { alvo: "🎯", otimo: "🟢", cronometro: "⏱" };
const TITULO_ALERTA = { alvo: "🎯 Preço-alvo atingido", otimo: "🟢 Ótimo para comprar", cronometro: "⏱ Cronômetro terminou" };

// Versão desktop (desktop.py): a janela não tem as notificações do navegador; elas saem pelo Windows
const naDesktop = () => !!window.pywebview?.api;

function notificar(alerta) {
  if (location.pathname === "/mini") return;  // a pedido do usuário, só o app principal notifica
  if (alerta.id <= lerNotificado()) return;
  if (naDesktop()) {
    gravarNotificado(alerta.id);
    window.pywebview.api.notificar(TITULO_ALERTA[alerta.tipo] || "Trainer's Notebook", alerta.mensagem);
    return;
  }
  if (!("Notification" in window) || Notification.permission !== "granted") return;
  gravarNotificado(alerta.id);
  new Notification(TITULO_ALERTA[alerta.tipo] || "Trainer's Notebook", { body: alerta.mensagem, tag: "alerta-" + alerta.id });
}

// aoAtualizar(naoLidos, houveNovos) é chamado a cada consulta
function vigiarAlertas(aoAtualizar) {
  let ultimo = null;
  async function verificar() {
    try {
      const r = await api(`/api/alertas?depois=${ultimo ?? 0}`);
      const novos = r.alertas;  // mais recentes primeiro
      if (ultimo === null) {
        // Na primeira consulta, o que já existia não vira notificação
        if (novos.length) gravarNotificado(Math.max(lerNotificado(), novos[0].id));
      } else {
        [...novos].reverse().forEach(notificar);
      }
      if (novos.length) ultimo = novos[0].id;
      else ultimo ??= 0;
      aoAtualizar(r.nao_lidos, novos.length > 0);
    } catch {}
  }
  verificar();
  setInterval(verificar, 3000);
}

function pedirPermissaoNotificacao() {
  if ("Notification" in window && Notification.permission === "default") return Notification.requestPermission();
  return Promise.resolve(window.Notification?.permission);
}
