/* Formulário de cotação — dinâmica, cálculo ao vivo e formsets. */
(function () {
  "use strict";

  const BRL = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
  const num = (v) => {
    if (v === null || v === undefined) return 0;
    const n = parseFloat(String(v).replace(",", "."));
    return isNaN(n) ? 0 : n;
  };
  const money = (n) => BRL.format(n || 0);
  // percentuais informados como número inteiro (5 = 5%)
  const pct = (v) => num(v) / 100;

  // ----------------------------------------------------------------- tipo
  const tipoInput = document.getElementById("id_tipo");
  const cards = document.querySelectorAll("#tipo-cards .opt");
  const secSrv = document.getElementById("sec-servicos");
  const secMer = document.getElementById("sec-mercadorias");

  function aplicarTipo(val) {
    cards.forEach((c) => c.classList.toggle("sel", c.dataset.val === val));
    const temS = val === "Serviços" || val === "Serviços e Mercadoria";
    const temM = val === "Mercadoria" || val === "Serviços e Mercadoria";
    secSrv.classList.toggle("hidden", !temS);
    secMer.classList.toggle("hidden", !temM);
    recalcTudo();
  }
  cards.forEach((c) =>
    c.addEventListener("click", () => {
      tipoInput.value = c.dataset.val;
      aplicarTipo(c.dataset.val);
    })
  );
  if (tipoInput.value) aplicarTipo(tipoInput.value);

  // --------------------------------------------------------------- filial
  const filialSel = document.getElementById("id_filial");
  const filialInfo = document.getElementById("filial-info");
  if (filialSel) {
    filialSel.addEventListener("change", async () => {
      const pk = filialSel.value;
      if (!pk) {
        filialInfo.classList.add("hidden");
        return;
      }
      try {
        const r = await fetch(`/api/filial/${pk}/`);
        const d = await r.json();
        filialInfo.innerHTML =
          `<strong>${d.planta}</strong> — ${d.municipio}/${d.uf} · CEP ${d.cep}<br>` +
          `CNPJ ${d.cnpj}<br>${d.endereco}`;
        filialInfo.classList.remove("hidden");
      } catch (e) {
        filialInfo.classList.add("hidden");
      }
    });
    if (filialSel.value) filialSel.dispatchEvent(new Event("change"));
  }

  // -------------------------------------------------- regra do regime (CSRF/IRRF)
  // Simples Nacional não tem retenção de CSRF e IRRF em serviços.
  const regimeSel = document.getElementById("id_regime");
  const isSimples = () => regimeSel && regimeSel.value === "Simples Nacional";

  function aplicarRegimeNoCard(card) {
    const block = isSimples();
    ["perc_csrf", "perc_irrf"].forEach((sfx) => {
      const el = card.querySelector(`[name$="-${sfx}"]`);
      if (!el) return;
      if (block) {
        el.value = "0";
        el.readOnly = true;
        el.classList.add("locked");
        el.title = "Sem retenção de CSRF/IRRF para Simples Nacional";
      } else {
        el.readOnly = false;
        el.classList.remove("locked");
        el.title = "";
      }
    });
  }

  function aplicarRegime() {
    document.querySelectorAll("#srv-items .srv-item").forEach(aplicarRegimeNoCard);
    recalcTudo();
  }
  if (regimeSel) regimeSel.addEventListener("change", aplicarRegime);

  // --------------------------------------------------------- cálculo serviço
  function calcServico(card) {
    const valor = num(card.querySelector('[name$="-valor_servico"]')?.value);
    const iss = pct(card.querySelector('[name$="-perc_iss"]')?.value);
    const inss = pct(card.querySelector('[name$="-perc_inss"]')?.value);
    const csrf = pct(card.querySelector('[name$="-perc_csrf"]')?.value);
    const irrf = pct(card.querySelector('[name$="-perc_irrf"]')?.value);
    const retido = valor * iss + valor * inss + valor * csrf + valor * irrf;
    const liquido = valor - retido;
    card.querySelector(".out-retido").value = money(retido);
    card.querySelector(".out-liquido").value = money(liquido);
    return { retido, liquido };
  }

  async function lookupAtividade(card) {
    const cod = card.querySelector('[name$="-codigo_servico"]')?.value;
    const csrf = card.querySelector('[name$="-perc_csrf"]')?.value || "";
    if (!cod) return;
    try {
      const r = await fetch(`/api/atividade/?codigo=${encodeURIComponent(cod)}&csrf=${csrf}`);
      const d = await r.json();
      const desc = card.querySelector('[name$="-descricao"]');
      const sap = card.querySelector('[name$="-codigo_sap"]');
      if (desc) desc.value = d.descricao || "";
      if (sap) sap.value = d.codigo_sap || "";
    } catch (e) {}
  }

  // ------------------------------------------------------ cálculo mercadoria
  const CAT_IPI_BASE = ["Uso ou Consumo", "Ativo Fixo"];
  function calcMercadoria(card) {
    const g = (sfx) => num(card.querySelector(`[name$="-${sfx}"]`)?.value);
    const gp = (sfx) => pct(card.querySelector(`[name$="-${sfx}"]`)?.value);
    const cat = card.querySelector('[name$="-categoria"]')?.value || "";
    const bruto = g("quantidade") * g("valor_unitario");
    const ipi = Math.round(bruto * gp("perc_ipi") * 100) / 100;
    const p = gp("perc_reducao_base");
    let base;
    if (CAT_IPI_BASE.includes(cat)) base = bruto + ipi - (bruto + ipi) * p;
    else base = bruto - bruto * p;
    base = Math.round(base * 100) / 100;
    const vicms = Math.round(base * gp("perc_icms") * 100) / 100;
    const st = g("icms_st");
    const total = Math.round((base + ipi + st) * 100) / 100;
    card.querySelector(".out-ipi").value = money(ipi);
    card.querySelector(".out-base").value = money(base);
    card.querySelector(".out-vicms").value = money(vicms);
    card.querySelector(".out-total").value = money(total);
    return { ipi, vicms, total };
  }

  // ---------------------------------------------------------------- totais
  function isVisible(sec) {
    return !sec.classList.contains("hidden");
  }
  function naoExcluido(card) {
    const del = card.querySelector('[name$="-DELETE"]');
    return !(del && del.checked);
  }
  function recalcTudo() {
    let tServ = 0, tRet = 0, tMat = 0, tIpi = 0, tIcms = 0;
    if (isVisible(secSrv)) {
      secSrv.querySelectorAll(".srv-item").forEach((c) => {
        if (!naoExcluido(c)) return;
        const r = calcServico(c);
        tServ += r.liquido;
        tRet += r.retido;
      });
    }
    if (isVisible(secMer)) {
      secMer.querySelectorAll(".mer-item").forEach((c) => {
        if (!naoExcluido(c)) return;
        const r = calcMercadoria(c);
        tMat += r.total;
        tIpi += r.ipi;
        tIcms += r.vicms;
      });
    }
    document.getElementById("t-servico").textContent = money(tServ);
    document.getElementById("t-retido").textContent = money(tRet);
    document.getElementById("t-material").textContent = money(tMat);
    document.getElementById("t-ipi").textContent = money(tIpi);
    document.getElementById("t-icms").textContent = money(tIcms);
    document.getElementById("t-liquido").textContent = money(tServ + tMat);
  }

  // --------------------------------------------------------- eventos card
  function bindCard(card, tipo) {
    card.addEventListener("input", recalcTudo);
    card.addEventListener("change", recalcTudo);
    const rm = card.querySelector(".rm");
    if (rm) rm.addEventListener("click", () => removerCard(card));
    if (tipo === "srv") {
      const cod = card.querySelector('[name$="-codigo_servico"]');
      if (cod)
        cod.addEventListener("change", async () => {
          await lookupAtividade(card);
          recalcTudo();
        });
      const csrf = card.querySelector('[name$="-perc_csrf"]');
      if (csrf) csrf.addEventListener("change", () => lookupAtividade(card));
    }
  }

  function removerCard(card) {
    const del = card.querySelector('[name$="-DELETE"]');
    if (del) {
      del.checked = true; // mantém no POST como excluído (item existente)
      card.style.display = "none";
    } else {
      card.remove();
    }
    recalcTudo();
  }

  // ----------------------------------------------------- adicionar itens
  function addItem(tipo) {
    const prefix = tipo; // 'srv' ou 'mer'
    const totalInput = document.getElementById(`id_${prefix}-TOTAL_FORMS`);
    const idx = parseInt(totalInput.value, 10);
    const tpl = document.getElementById(`${prefix}-empty`);
    const html = tpl.innerHTML.replace(/__prefix__/g, idx);
    const wrapper = document.createElement("div");
    wrapper.innerHTML = html.trim();
    const card = wrapper.firstElementChild;
    document.getElementById(`${prefix}-items`).appendChild(card);
    totalInput.value = idx + 1;
    bindCard(card, prefix);
    if (prefix === "srv") aplicarRegimeNoCard(card);
    recalcTudo();
  }
  document.getElementById("add-srv")?.addEventListener("click", () => addItem("srv"));
  document.getElementById("add-mer")?.addEventListener("click", () => addItem("mer"));

  // ------------------------------------------------------- aceite dos termos
  const aceiteChk = document.getElementById("id_aceite");
  const btnEnviar = document.getElementById("btn-enviar");
  const aceiteHint = document.getElementById("aceite-hint");
  function aplicarAceite() {
    if (!aceiteChk || !btnEnviar) return;
    btnEnviar.disabled = !aceiteChk.checked;
    if (aceiteHint)
      aceiteHint.textContent = aceiteChk.checked
        ? "Confira os dados antes de enviar. Você não poderá editar depois do envio."
        : "Aceite os termos (abaixo) para habilitar o envio.";
  }
  if (aceiteChk) aceiteChk.addEventListener("change", aplicarAceite);

  // ------------------------------------------------------------ init
  document.querySelectorAll("#srv-items .srv-item").forEach((c) => {
    bindCard(c, "srv");
    lookupAtividade(c);
  });
  document.querySelectorAll("#mer-items .mer-item").forEach((c) => bindCard(c, "mer"));
  aplicarRegime();
  aplicarAceite();
  recalcTudo();
})();
