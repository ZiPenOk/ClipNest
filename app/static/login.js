const setupRequired = document.body.dataset.setupRequired === "true";
const form = document.querySelector("#auth-form");
const usernameInput = document.querySelector("#auth-username");
const passwordInput = document.querySelector("#auth-password");
const confirmInput = document.querySelector("#auth-confirm-password");
const submitButton = document.querySelector("#auth-submit");
const errorEl = document.querySelector("#auth-error");

function setError(message) {
  errorEl.textContent = message || "";
  errorEl.hidden = !message;
}

function normalizeError(error) {
  const text = String(error || "").trim();
  if (!text) return "操作失败，请稍后重试";
  if (text.includes("Admin account already exists")) return "管理员已经初始化，请直接登录";
  if (text.includes("Admin account has not been initialized")) return "还没有初始化管理员账号";
  if (text.includes("Invalid username or password")) return "用户名或密码不正确";
  if (text.includes("Username must be at least")) return "用户名至少需要 3 个字符";
  if (text.includes("Password must be at least")) return "密码至少需要 8 个字符";
  if (text.includes("Passwords do not match")) return "两次输入的密码不一致";
  return text;
}

async function submitAuth(event) {
  event.preventDefault();
  setError("");

  const username = usernameInput.value.trim();
  const password = passwordInput.value;
  const confirmPassword = confirmInput.value;

  if (!username) {
    setError("请输入用户名");
    usernameInput.focus();
    return;
  }
  if (!password) {
    setError("请输入密码");
    passwordInput.focus();
    return;
  }
  if (setupRequired && password !== confirmPassword) {
    setError("两次输入的密码不一致");
    confirmInput.focus();
    return;
  }

  submitButton.disabled = true;
  submitButton.textContent = setupRequired ? "正在初始化" : "正在登录";
  try {
    const response = await fetch(setupRequired ? "/api/setup" : "/api/session", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(setupRequired
        ? { username, password, confirm_password: confirmPassword }
        : { username, password }),
    });
    if (!response.ok) {
      let message = await response.text();
      try {
        const parsed = JSON.parse(message);
        message = parsed.detail || message;
      } catch (_) {}
      throw new Error(message);
    }
    window.location.href = "/";
  } catch (error) {
    setError(normalizeError(error.message));
    submitButton.disabled = false;
    submitButton.textContent = setupRequired ? "初始化并进入" : "登录";
  }
}

form.addEventListener("submit", submitAuth);
