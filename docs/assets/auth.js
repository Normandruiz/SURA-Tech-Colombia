/* ============================================================
   SURA Tech Colombia · Password gate (client-side)
   Hash SHA-256 de la pass real. Cualquiera con devtools puede
   bypassearlo - es proteccion contra acceso casual, no seguro
   contra ataque dirigido.
   ============================================================ */

(function () {
  const HASH_OK = "8e621e71fbf2d29f948113f31de79c663e3c638b69360892c9b9f865753f79cf"; // Beyond@2026
  const STORAGE_KEY = "sura_tech_auth_ok";
  const STORAGE_TTL_MS = 1000 * 60 * 60 * 12; // 12 horas

  // Si ya esta autenticado, no mostrar nada
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v) {
      const stamp = parseInt(v, 10);
      if (!isNaN(stamp) && Date.now() - stamp < STORAGE_TTL_MS) {
        return;
      }
    }
  } catch (e) {}

  // Inyectar overlay con CSS inline (no depende de styles.css)
  const overlay = document.createElement("div");
  overlay.id = "sura-auth-overlay";
  overlay.innerHTML = `
    <style>
      #sura-auth-overlay {
        position: fixed; inset: 0; z-index: 999999;
        background: linear-gradient(135deg, #0033A0 0%, #002171 100%);
        display: flex; align-items: center; justify-content: center;
        font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      }
      #sura-auth-box {
        background: #FFFFFF;
        border-radius: 16px;
        padding: 48px 48px 36px;
        max-width: 420px;
        width: calc(100% - 32px);
        box-shadow: 0 20px 60px rgba(0,33,113,0.4);
      }
      #sura-auth-box h1 {
        margin: 0 0 6px;
        font-size: 24px;
        color: #0033A0;
        letter-spacing: -0.01em;
      }
      #sura-auth-box .sub {
        margin: 0 0 28px;
        font-size: 14px;
        color: #768692;
      }
      #sura-auth-box label {
        display: block;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #0033A0;
        font-weight: 600;
        margin-bottom: 8px;
      }
      #sura-auth-box input {
        width: 100%;
        box-sizing: border-box;
        padding: 14px 16px;
        font-size: 15px;
        border: 2px solid #F0F0F0;
        border-radius: 10px;
        font-family: inherit;
        color: #53565A;
        outline: none;
        transition: border-color .15s ease;
      }
      #sura-auth-box input:focus { border-color: #0033A0; }
      #sura-auth-box button {
        width: 100%;
        margin-top: 20px;
        padding: 14px;
        background: #0033A0;
        color: #FFFFFF;
        border: 0;
        border-radius: 10px;
        font-family: inherit;
        font-size: 15px;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        cursor: pointer;
        transition: background .15s ease;
      }
      #sura-auth-box button:hover { background: #002171; }
      #sura-auth-box button:disabled { opacity: 0.6; cursor: not-allowed; }
      #sura-auth-box .err {
        color: #DC2626;
        font-size: 13px;
        margin-top: 12px;
        min-height: 18px;
      }
      #sura-auth-box .footer {
        margin-top: 24px;
        padding-top: 18px;
        border-top: 1px solid #F0F0F0;
        font-size: 12px;
        color: #768692;
        text-align: center;
      }
    </style>
    <div id="sura-auth-box">
      <h1>SURA Tech Colombia</h1>
      <p class="sub">Informe estratégico · Acceso restringido</p>
      <label for="sura-auth-pass">Contraseña</label>
      <input id="sura-auth-pass" type="password" autocomplete="off" autofocus>
      <button id="sura-auth-btn" type="button">Acceder</button>
      <div class="err" id="sura-auth-err"></div>
      <div class="footer">Beyond Media Agency</div>
    </div>
  `;
  document.documentElement.appendChild(overlay);
  // Bloquear scroll mientras esta el overlay
  document.documentElement.style.overflow = "hidden";

  async function sha256Hex(text) {
    const buf = new TextEncoder().encode(text);
    const hash = await crypto.subtle.digest("SHA-256", buf);
    return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, "0")).join("");
  }

  const input = document.getElementById("sura-auth-pass");
  const btn   = document.getElementById("sura-auth-btn");
  const err   = document.getElementById("sura-auth-err");

  async function tryAuth() {
    const pass = input.value || "";
    if (!pass) { err.textContent = "Ingresá la contraseña."; return; }
    btn.disabled = true; err.textContent = "";
    try {
      const hex = await sha256Hex(pass);
      if (hex === HASH_OK) {
        try { localStorage.setItem(STORAGE_KEY, String(Date.now())); } catch (e) {}
        overlay.style.transition = "opacity .25s ease";
        overlay.style.opacity = "0";
        setTimeout(() => {
          overlay.remove();
          document.documentElement.style.overflow = "";
        }, 280);
      } else {
        err.textContent = "Contraseña incorrecta.";
        btn.disabled = false;
        input.focus();
        input.select();
      }
    } catch (e) {
      err.textContent = "Error: " + e.message;
      btn.disabled = false;
    }
  }

  btn.addEventListener("click", tryAuth);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") tryAuth(); });
})();
