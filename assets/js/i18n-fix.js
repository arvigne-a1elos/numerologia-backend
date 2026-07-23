(function () {
  'use strict';

  // Keys used in the HTML via data-i18n attributes
  const KEYS = [
    'nav_home','nav_map','nav_prod','nav_urna','nav_elec','nav_energy',
    'hero_title','hero_sub','hero_btn1','hero_btn2','hero_btn3',
    'calc_title','label_name','label_date','label_email','btn_calc',
    'btn_express','btn_completo','prod_title','prod_sub','th_prod','th_price',
    'th_energy','th_action','urna_title','urna_desc','urna_5names','elec_title',
    'elec_desc','elec_mask','elec_sigla','elec_existente','elec_email','energy_title',
    'energy_desc','footer_text'
  ];

  // Defensive: TRAD might be defined in the inline script. If not, create empty.
  window.TRAD = window.TRAD || {};

  const i18n = {};
  for (const lang in TRAD) {
    if (!TRAD.hasOwnProperty(lang)) continue;
    i18n[lang] = {};
    for (const k of KEYS) {
      i18n[lang][k] = (TRAD[lang] && TRAD[lang][k]) || (TRAD.pt && TRAD.pt[k]) || k;
    }
  }
  i18n.pt = i18n.pt || (TRAD.pt || {});

  function getCurrentLang() {
    return localStorage.getItem('l') || 'pt';
  }

  function t(key) {
    const l = getCurrentLang();
    return (i18n[l] && i18n[l][key]) || (i18n.pt && i18n.pt[key]) || key;
  }

  function applyLang() {
    const l = getCurrentLang();
    document.querySelectorAll('[data-i18n]').forEach(function (el) {
      const key = el.dataset.i18n;
      if (!key) return;
      el.textContent = t(key);
    });
    document.querySelectorAll('.lang-btn').forEach(function (b) {
      b.classList.toggle('active', b.dataset.lang === l);
    });
    document.documentElement.dir = (l === 'ar') ? 'rtl' : 'ltr';
  }

  function setLang(code) {
    localStorage.setItem('l', code);
    applyLang();
    if (typeof renderProdTable === 'function') try { renderProdTable(); } catch(e){}
    if (typeof renderEnergyGrid === 'function') try { renderEnergyGrid(); } catch(e){}
  }

  // Minimal event refactor: bind the most important handlers after DOMContentLoaded
  document.addEventListener('DOMContentLoaded', function () {
    try { applyLang(); } catch (e) { console.error('applyLang error', e); }
    if (typeof renderProdTable === 'function') try { renderProdTable(); } catch(e){}
    if (typeof renderEnergyGrid === 'function') try { renderEnergyGrid(); } catch(e){}

    document.querySelectorAll('.lang-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        const code = this.dataset.lang;
        if (!code) return;
        setLang(code);
      });
    });

    const mainForm = document.getElementById('mainForm');
    if (mainForm) {
      mainForm.addEventListener('submit', function (e) {
        e.preventDefault();
        if (typeof calculate === 'function') calculate();
      });
    }

    // Bind express/completo buttons if present
    document.querySelectorAll('#calcResult .btn-sm').forEach(function (btn, idx) {
      if (idx === 0) btn.addEventListener('click', function (e) { if (typeof payExpress === 'function') payExpress(); });
      if (idx === 1) btn.addEventListener('click', function (e) { if (typeof payCompleto === 'function') payCompleto(); });
    });

    // Bind tab buttons
    document.querySelectorAll('.tab-btn').forEach(function(b) {
      b.addEventListener('click', function(){
        // The original setCargo expects (c,b) signature; try to infer from text
        const txt = this.textContent || '';
        if (txt.toLowerCase().includes('vereador')) setCargo && setCargo('vereador', this);
        else if (txt.toLowerCase().includes('estadual')) setCargo && setCargo('dep_estadual', this);
        else if (txt.toLowerCase().includes('federal')) setCargo && setCargo('dep_federal', this);
        else if (txt.toLowerCase().includes('senador')) setCargo && setCargo('senador', this);
      });
    });
  });

  // expose helpers if needed
  window.setLang = setLang;
  window.t = t;
})();