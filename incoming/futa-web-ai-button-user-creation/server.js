const http = require("http");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { URL } = require("url");

const ROOT = __dirname;
const DATA_DIR = path.join(ROOT, "data");
const USERS_FILE = path.join(DATA_DIR, "users.json");
const PATIENTS_FILE = path.join(DATA_DIR, "patients.json");
const PORT = Number(process.env.PORT || 3000);
const SESSION_SECRET = process.env.SESSION_SECRET || "development-only-change-this-secret";
const sessions = new Map();

const contentTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".jpg": "image/jpeg",
  ".json": "application/json; charset=utf-8"
};

function readJson(file, fallback) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
    return fallback;
  }
}

function writeJson(file, value) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, "utf8");
}

function hashPassword(password, salt = crypto.randomBytes(16).toString("hex")) {
  const hash = crypto.pbkdf2Sync(password, salt, 120000, 32, "sha256").toString("hex");
  return `${salt}:${hash}`;
}

function verifyPassword(password, stored) {
  const [salt, expected] = String(stored).split(":");
  if (!salt || !expected) return false;
  const actual = crypto.pbkdf2Sync(password, salt, 120000, 32, "sha256").toString("hex");
  return crypto.timingSafeEqual(Buffer.from(actual), Buffer.from(expected));
}

function ensureAdmin() {
  const users = readJson(USERS_FILE, []);
  if (users.some((user) => user.staffId === "admin")) return users;
  users.push({
    id: crypto.randomUUID(),
    staffId: "admin",
    fullName: "System Administrator",
    role: "admin",
    passwordHash: hashPassword(process.env.ADMIN_PASSWORD || "admin123"),
    createdAt: new Date().toISOString()
  });
  writeJson(USERS_FILE, users);
  return users;
}

function sendJson(response, status, body) {
  response.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store"
  });
  response.end(JSON.stringify(body));
}

function sendError(response, status, message) {
  sendJson(response, status, { message });
}

function parseCookies(request) {
  return Object.fromEntries(
    (request.headers.cookie || "")
      .split(";")
      .map((item) => item.trim().split("="))
      .filter(([key, value]) => key && value)
      .map(([key, value]) => [key, decodeURIComponent(value)])
  );
}

function currentUser(request) {
  const sessionId = parseCookies(request).session;
  const session = sessionId && sessions.get(sessionId);
  if (!session || session.expiresAt < Date.now()) return null;
  return session.user;
}

function requireUser(request, response) {
  const user = currentUser(request);
  if (!user) {
    sendError(response, 401, "You must sign in first.");
    return null;
  }
  return user;
}

function requireAdmin(request, response) {
  const user = requireUser(request, response);
  if (!user) return null;
  if (user.role !== "admin") {
    sendError(response, 403, "Only an administrator can perform this action.");
    return null;
  }
  return user;
}

function readBody(request) {
  return new Promise((resolve, reject) => {
    let body = "";
    request.on("data", (chunk) => {
      body += chunk;
      if (body.length > 1024 * 1024) {
        reject(new Error("Request body is too large."));
        request.destroy();
      }
    });
    request.on("end", () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch {
        reject(new Error("Request body must be valid JSON."));
      }
    });
    request.on("error", reject);
  });
}

function publicUser(user) {
  return { id: user.id, staffId: user.staffId, fullName: user.fullName, role: user.role };
}

function validateCredentials(staffId, password) {
  return (
    typeof staffId === "string" &&
    /^[A-Za-z0-9._-]{3,64}$/.test(staffId.trim()) &&
    typeof password === "string" &&
    password.length >= 8 &&
    password.length <= 200
  );
}

function aiAnswer(question) {
  const text = question.toLowerCase();
  if (text.includes("bleed") || text.includes("cut")) {
    return "Apply firm, direct pressure with clean cloth or gauze. Seek urgent medical help if bleeding is heavy or does not stop.";
  }
  if (text.includes("burn")) {
    return "Cool the burn under clean, cool running water for at least 20 minutes. Do not use ice, butter, or creams.";
  }
  if (text.includes("chok")) {
    return "If the person cannot speak, cough, or breathe, call emergency services and use age-appropriate choking first aid.";
  }
  if (text.includes("faint") || text.includes("unconscious")) {
    return "Lay the person flat, check breathing, and call emergency services if they do not recover quickly or are not breathing normally.";
  }
  return "I can provide general first-aid information, but I cannot diagnose illness. For severe, sudden, or worrying symptoms, contact a qualified clinician or emergency services.";
}

async function handleApi(request, response, url) {
  if (request.method === "POST" && url.pathname === "/api/login") {
    const body = await readBody(request);
    const user = ensureAdmin().find(
      (candidate) =>
        candidate.staffId.toLowerCase() === String(body.staffId || "").trim().toLowerCase() &&
        verifyPassword(String(body.password || ""), candidate.passwordHash)
    );
    if (!user) return sendError(response, 401, "Invalid staff ID or password.");
    const sessionId = crypto.randomBytes(32).toString("hex");
    sessions.set(sessionId, { user: publicUser(user), expiresAt: Date.now() + 8 * 60 * 60 * 1000 });
    response.writeHead(200, {
      "Content-Type": "application/json; charset=utf-8",
      "Set-Cookie": `session=${sessionId}; HttpOnly; SameSite=Lax; Path=/; Max-Age=28800`
    });
    return response.end(JSON.stringify({ message: "Login successful.", user: publicUser(user) }));
  }

  if (request.method === "POST" && url.pathname === "/api/logout") {
    const sessionId = parseCookies(request).session;
    if (sessionId) sessions.delete(sessionId);
    response.writeHead(204, { "Set-Cookie": "session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0" });
    return response.end();
  }

  if (request.method === "GET" && url.pathname === "/api/session") {
    const user = currentUser(request);
    return user ? sendJson(response, 200, { user }) : sendError(response, 401, "Not signed in.");
  }

  if (request.method === "POST" && url.pathname === "/api/register") {
    const body = await readBody(request);
    if (!validateCredentials(body.staffId, body.password)) {
      return sendError(response, 400, "Staff ID or password is invalid.");
    }
    const users = ensureAdmin();
    if (users.some((user) => user.staffId.toLowerCase() === body.staffId.trim().toLowerCase())) {
      return sendError(response, 409, "That staff ID is already in use.");
    }
    users.push({
      id: crypto.randomUUID(),
      staffId: body.staffId.trim(),
      fullName: body.staffId.trim(),
      role: "staff",
      passwordHash: hashPassword(body.password),
      createdAt: new Date().toISOString()
    });
    writeJson(USERS_FILE, users);
    return sendJson(response, 201, { message: "Account created successfully." });
  }

  if (request.method === "POST" && url.pathname === "/api/admin/users") {
    if (!requireAdmin(request, response)) return;
    const body = await readBody(request);
    if (!validateCredentials(body.staffId, body.password) || !body.fullName || body.role !== "student") {
      return sendError(response, 400, "Student ID, name, password, and student role are required.");
    }
    const users = ensureAdmin();
    if (users.some((user) => user.staffId.toLowerCase() === body.staffId.trim().toLowerCase())) {
      return sendError(response, 409, "That student ID is already in use.");
    }
    users.push({
      id: crypto.randomUUID(),
      staffId: body.staffId.trim(),
      fullName: body.fullName.trim(),
      role: "student",
      passwordHash: hashPassword(body.password),
      createdAt: new Date().toISOString()
    });
    writeJson(USERS_FILE, users);
    return sendJson(response, 201, { message: "Student account created successfully." });
  }

  if (request.method === "POST" && url.pathname === "/api/ai/ask") {
    if (!requireUser(request, response)) return;
    const body = await readBody(request);
    if (typeof body.question !== "string" || !body.question.trim() || body.question.length > 500) {
      return sendError(response, 400, "Ask a question between 1 and 500 characters.");
    }
    return sendJson(response, 200, { answer: aiAnswer(body.question.trim()) });
  }

  if (url.pathname === "/api/patients") {
    if (!requireUser(request, response)) return;
    let patients = readJson(PATIENTS_FILE, []);
    if (request.method === "GET") {
      const search = (url.searchParams.get("search") || "").toLowerCase();
      if (search) {
        patients = patients.filter((patient) =>
          [patient.hospitalNumber, patient.fullName, patient.sex, patient.phone, patient.diagnosis]
            .some((value) => String(value || "").toLowerCase().includes(search))
        );
      }
      return sendJson(response, 200, patients);
    }
    if (request.method === "POST" || request.method === "PUT") {
      const body = await readBody(request);
      if (!body.fullName || !body.sex || !body.phone) {
        return sendError(response, 400, "Full name, sex, and phone are required.");
      }
      const id = request.method === "PUT" ? url.pathname.split("/").pop() : crypto.randomUUID();
      const patient = { ...body, id, hospitalNumber: body.hospitalNumber || `HF-${Date.now()}` };
      if (request.method === "PUT") {
        const index = patients.findIndex((item) => item.id === id);
        if (index < 0) return sendError(response, 404, "Patient record not found.");
        patients[index] = { ...patients[index], ...patient };
      } else {
        patients.push(patient);
      }
      writeJson(PATIENTS_FILE, patients);
      return sendJson(response, request.method === "POST" ? 201 : 200, { message: "Patient record saved.", ...patient });
    }
  }

  const patientMatch = url.pathname.match(/^\/api\/patients\/([^/]+)$/);
  if (patientMatch && (request.method === "GET" || request.method === "PUT")) {
    if (!requireUser(request, response)) return;
    const patients = readJson(PATIENTS_FILE, []);
    const patientIndex = patients.findIndex((item) => item.id === patientMatch[1]);
    if (patientIndex < 0) return sendError(response, 404, "Patient record not found.");
    if (request.method === "GET") return sendJson(response, 200, patients[patientIndex]);
    const body = await readBody(request);
    if (!body.fullName || !body.sex || !body.phone) {
      return sendError(response, 400, "Full name, sex, and phone are required.");
    }
    patients[patientIndex] = { ...patients[patientIndex], ...body, id: patientMatch[1] };
    writeJson(PATIENTS_FILE, patients);
    return sendJson(response, 200, { message: "Patient record saved.", ...patients[patientIndex] });
  }
  if (patientMatch && request.method === "DELETE") {
    if (!requireUser(request, response)) return;
    const patients = readJson(PATIENTS_FILE, []);
    const remaining = patients.filter((item) => item.id !== patientMatch[1]);
    if (remaining.length === patients.length) return sendError(response, 404, "Patient record not found.");
    writeJson(PATIENTS_FILE, remaining);
    return sendJson(response, 200, { message: "Patient record deleted." });
  }

  return sendError(response, 404, "API endpoint not found.");
}

function serveStatic(request, response, url) {
  let requestedPath = decodeURIComponent(url.pathname);
  if (requestedPath === "/") requestedPath = "/index.html";
  const filePath = path.normalize(path.join(ROOT, requestedPath));
  if (!filePath.startsWith(ROOT + path.sep)) return sendError(response, 403, "Forbidden.");
  fs.readFile(filePath, (error, content) => {
    if (error) return sendError(response, error.code === "ENOENT" ? 404 : 500, "File not found.");
    response.writeHead(200, { "Content-Type": contentTypes[path.extname(filePath).toLowerCase()] || "application/octet-stream" });
    response.end(content);
  });
}

ensureAdmin();
http.createServer(async (request, response) => {
  const url = new URL(request.url, `http://${request.headers.host || "localhost"}`);
  try {
    if (url.pathname.startsWith("/api/")) await handleApi(request, response, url);
    else serveStatic(request, response, url);
  } catch (error) {
    console.error(error);
    if (!response.headersSent) sendError(response, 500, "The server could not process the request.");
  }
}).listen(PORT, () => {
  console.log(`FUTA Hospital Management System running at http://localhost:${PORT}`);
});
