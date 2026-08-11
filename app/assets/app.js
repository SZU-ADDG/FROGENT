"use strict";

const state = {
    userId: null,
    username: null,
    chats: {},
    activeChatId: null,
    pendingFiles: [],
    sending: false,
};

const el = Object.fromEntries(
    [
        "login-view", "register-view", "chat-view", "login-form", "login-username",
        "login-password", "login-status", "show-register", "register-form",
        "register-username", "register-email", "register-password", "register-confirm",
        "register-status", "show-login", "sidebar", "close-sidebar", "open-sidebar",
        "new-chat", "chat-history", "account-name", "logout", "messages", "chat-status",
        "attachment-status", "file-input", "attach", "message-input", "send",
    ].map((id) => [id, document.getElementById(id)])
);

function showView(name) {
    el["login-view"].hidden = name !== "login";
    el["register-view"].hidden = name !== "register";
    el["chat-view"].hidden = name !== "chat";
}

function status(target, message = "", error = false) {
    target.textContent = message;
    target.style.color = error ? "#a33b32" : "";
}

async function requestJson(path, options = {}) {
    const response = await fetch(path, options);
    let payload;
    try {
        payload = await response.json();
    } catch {
        throw new Error(`Invalid server response (${response.status})`);
    }
    if (!response.ok || payload.success === false) {
        throw new Error(payload.message || `Request failed (${response.status})`);
    }
    return payload;
}

function newChat() {
    const suffix = globalThis.crypto?.randomUUID?.()
        || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
    const id = `${state.userId}-${suffix}`;
    const now = new Date().toISOString();
    state.chats[id] = {
        id,
        title: "New conversation",
        messages: [],
        createdAt: now,
        updatedAt: now,
        files: [],
        molecules: [],
    };
    selectChat(id);
}

function selectChat(chatId) {
    if (!state.chats[chatId]) return;
    state.activeChatId = chatId;
    renderHistory();
    renderMessages();
    el.sidebar.classList.remove("open");
}

function sortedChats() {
    return Object.values(state.chats).sort(
        (left, right) => new Date(right.updatedAt) - new Date(left.updatedAt)
    );
}

function renderHistory() {
    el["chat-history"].replaceChildren();
    for (const chat of sortedChats()) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "history-item";
        button.classList.toggle("active", chat.id === state.activeChatId);
        const title = document.createElement("strong");
        title.textContent = chat.title || "Conversation";
        const updated = document.createElement("span");
        updated.textContent = readableDate(chat.updatedAt || chat.createdAt);
        button.append(title, updated);
        button.addEventListener("click", () => selectChat(chat.id));
        el["chat-history"].append(button);
    }
}

function readableDate(value) {
    const date = new Date(value);
    return Number.isNaN(date.valueOf()) ? "" : date.toLocaleString();
}

function welcome() {
    const container = document.createElement("div");
    container.className = "welcome";
    const title = document.createElement("h2");
    title.textContent = "What should FROGENT investigate or design?";
    const text = document.createElement("p");
    text.textContent = "Use literature retrieval, qualitative scientific judgment, molecular tools, docking, or a combined research workflow.";
    container.append(title, text);
    return container;
}

function messageText(message) {
    if (typeof message.content === "string") return message.content;
    if (Array.isArray(message.content)) {
        return message.content
            .filter((item) => item && typeof item.text === "string")
            .map((item) => item.text)
            .join("\n");
    }
    if (message.content && typeof message.content.text === "string") {
        return message.content.text;
    }
    return "";
}

function messageNode(message) {
    const item = document.createElement("article");
    item.className = `message ${message.isUser ? "user" : "agent"}`;
    const avatar = document.createElement("img");
    avatar.src = message.isUser ? "/assets/user.png" : "/assets/logo.png";
    avatar.alt = "";
    const body = document.createElement("div");
    body.className = "message-content";
    body.textContent = messageText(message);
    const names = Array.isArray(message.fileNames)
        ? message.fileNames.filter(Boolean)
        : (message.fileNames ? [message.fileNames] : []);
    if (names.length) {
        const meta = document.createElement("span");
        meta.className = "message-meta";
        meta.textContent = `Attachments: ${names.join(", ")}`;
        body.append(meta);
    }
    item.append(avatar, body);
    return item;
}

function structureAtoms(molecule) {
    const data = typeof molecule.data === "string" ? molecule.data : "";
    const format = String(molecule.format || "").toLowerCase();
    const atoms = [];
    if (format === "pdb") {
        for (const line of data.split(/\r?\n/)) {
            if (!line.startsWith("ATOM  ") && !line.startsWith("HETATM")) continue;
            const x = Number(line.slice(30, 38));
            const y = Number(line.slice(38, 46));
            const z = Number(line.slice(46, 54));
            const atomName = line.slice(12, 16).trim().replace(/^\d+/, "");
            const element = line.slice(76, 78).trim() || atomName.slice(0, 1);
            if ([x, y, z].every(Number.isFinite)) atoms.push({x, y, z, element});
        }
    } else if (format === "sdf" || format === "mol") {
        const lines = data.split(/\r?\n/);
        const count = Number.parseInt((lines[3] || "").slice(0, 3), 10);
        for (const line of lines.slice(4, 4 + (Number.isFinite(count) ? count : 0))) {
            const x = Number(line.slice(0, 10));
            const y = Number(line.slice(10, 20));
            const z = Number(line.slice(20, 30));
            const element = line.slice(31, 34).trim();
            if ([x, y, z].every(Number.isFinite)) atoms.push({x, y, z, element});
        }
    } else if (format === "mol2") {
        const lines = data.split(/\r?\n/);
        let inAtoms = false;
        for (const line of lines) {
            if (line.startsWith("@<TRIPOS>ATOM")) { inAtoms = true; continue; }
            if (inAtoms && line.startsWith("@<TRIPOS>")) break;
            if (!inAtoms || !line.trim()) continue;
            const fields = line.trim().split(/\s+/);
            const [x, y, z] = fields.slice(2, 5).map(Number);
            const element = (fields[5] || fields[1] || "C").split(".")[0];
            if ([x, y, z].every(Number.isFinite)) atoms.push({x, y, z, element});
        }
    }
    return atoms.slice(0, 5000);
}

function atomColor(element) {
    return ({C: "#59636d", N: "#315fd5", O: "#d74b43", S: "#d5a928",
        P: "#dd7b2d", F: "#58a56b", CL: "#58a56b", BR: "#8d5134",
        I: "#7156a5", H: "#d9dfe5"})[String(element || "C").toUpperCase()] || "#8a98a6";
}

function structureBonds(atoms) {
    const radii = {H: 0.31, C: 0.76, N: 0.71, O: 0.66, F: 0.57, P: 1.07,
        S: 1.05, CL: 1.02, BR: 1.20, I: 1.39};
    const cellSize = 2.4;
    const cells = new Map();
    const bonds = [];
    const key = (x, y, z) => `${x},${y},${z}`;
    atoms.forEach((atom, index) => {
        const cell = [atom.x, atom.y, atom.z].map((value) => Math.floor(value / cellSize));
        for (let dx = -1; dx <= 1; dx += 1) for (let dy = -1; dy <= 1; dy += 1) {
            for (let dz = -1; dz <= 1; dz += 1) {
                for (const other of cells.get(key(cell[0] + dx, cell[1] + dy, cell[2] + dz)) || []) {
                    const candidate = atoms[other];
                    const distance = Math.hypot(atom.x - candidate.x, atom.y - candidate.y, atom.z - candidate.z);
                    const left = radii[String(atom.element || "C").toUpperCase()] || 0.77;
                    const right = radii[String(candidate.element || "C").toUpperCase()] || 0.77;
                    if (distance > 0.25 && distance <= Math.min(2.35, (left + right) * 1.28)) {
                        bonds.push([other, index]);
                    }
                }
            }
        }
        const cellKey = key(...cell);
        if (!cells.has(cellKey)) cells.set(cellKey, []);
        cells.get(cellKey).push(index);
    });
    return bonds.slice(0, 20000);
}

function structureViewer(molecule) {
    const wrapper = document.createElement("div");
    wrapper.className = "structure-viewer";
    const atoms = structureAtoms(molecule);
    if (!atoms.length) {
        const note = document.createElement("p");
        note.textContent = "Preview unavailable for this structure format; download remains available.";
        wrapper.append(note);
        return wrapper;
    }
    const canvas = document.createElement("canvas");
    canvas.width = 720;
    canvas.height = 360;
    canvas.setAttribute("aria-label", `Interactive 3D preview of ${molecule.filename || "structure"}`);
    const hint = document.createElement("span");
    const bonds = structureBonds(atoms);
    hint.textContent = `${atoms.length} atoms · ${bonds.length} inferred bonds · drag to rotate`;
    let rotationX = -0.35;
    let rotationY = 0.55;
    let dragging = false;
    let previousX = 0;
    let previousY = 0;
    const center = atoms.reduce((sum, atom) => ({
        x: sum.x + atom.x / atoms.length,
        y: sum.y + atom.y / atoms.length,
        z: sum.z + atom.z / atoms.length,
    }), {x: 0, y: 0, z: 0});
    const radius = Math.max(1, ...atoms.map((atom) => Math.hypot(
        atom.x - center.x, atom.y - center.y, atom.z - center.z
    )));
    const draw = () => {
        const context = canvas.getContext("2d");
        context.clearRect(0, 0, canvas.width, canvas.height);
        context.fillStyle = "#f7faf8";
        context.fillRect(0, 0, canvas.width, canvas.height);
        const cosX = Math.cos(rotationX), sinX = Math.sin(rotationX);
        const cosY = Math.cos(rotationY), sinY = Math.sin(rotationY);
        const projected = atoms.map((atom, index) => {
            const x0 = atom.x - center.x, y0 = atom.y - center.y, z0 = atom.z - center.z;
            const x1 = x0 * cosY + z0 * sinY;
            const z1 = -x0 * sinY + z0 * cosY;
            const y1 = y0 * cosX - z1 * sinX;
            const z2 = y0 * sinX + z1 * cosX;
            const scale = 142 / radius;
            return {...atom, index, px: canvas.width / 2 + x1 * scale,
                py: canvas.height / 2 + y1 * scale, depth: z2};
        });
        context.strokeStyle = "rgba(94, 110, 102, 0.48)";
        context.lineWidth = 2;
        for (const [left, right] of bonds) {
            context.beginPath();
            context.moveTo(projected[left].px, projected[left].py);
            context.lineTo(projected[right].px, projected[right].py);
            context.stroke();
        }
        for (const atom of [...projected].sort((left, right) => left.depth - right.depth)) {
            const size = Math.max(4, 7 + (atom.depth / radius) * 1.5);
            context.beginPath();
            context.arc(atom.px, atom.py, size, 0, Math.PI * 2);
            context.fillStyle = atomColor(atom.element);
            context.fill();
        }
    };
    canvas.addEventListener("pointerdown", (event) => {
        dragging = true; previousX = event.clientX; previousY = event.clientY;
        canvas.setPointerCapture(event.pointerId);
    });
    canvas.addEventListener("pointermove", (event) => {
        if (!dragging) return;
        rotationY += (event.clientX - previousX) * 0.012;
        rotationX += (event.clientY - previousY) * 0.012;
        previousX = event.clientX; previousY = event.clientY; draw();
    });
    canvas.addEventListener("pointerup", () => { dragging = false; });
    canvas.addEventListener("pointercancel", () => { dragging = false; });
    draw();
    wrapper.append(canvas, hint);
    return wrapper;
}

function renderMessages() {
    el.messages.replaceChildren();
    const chat = state.chats[state.activeChatId] || {};
    const messages = chat.messages || [];
    if (!messages.length) el.messages.append(welcome());
    for (const message of messages) el.messages.append(messageNode(message));
    const molecules = Array.isArray(chat.molecules) ? chat.molecules : [];
    if (molecules.length) {
        const panel = document.createElement("section");
        panel.className = "molecule-downloads";
        const heading = document.createElement("h3");
        heading.textContent = "Molecular structures";
        panel.append(heading);
        for (const molecule of molecules) {
            const card = document.createElement("article");
            card.className = "molecule-card";
            card.append(structureViewer(molecule));
            const link = document.createElement("a");
            link.className = "molecule-download";
            link.href = molecule.download_url;
            link.download = molecule.filename || "structure";
            link.textContent = `Download ${molecule.filename || "structure"}`;
            card.append(link);
            panel.append(card);
        }
        el.messages.append(panel);
    }
    if (state.activeChatId && messages.length) {
        const exports = document.createElement("section");
        exports.className = "report-exports";
        const label = document.createElement("strong");
        label.textContent = "Download report";
        exports.append(label);
        for (const [format, name] of [["md", "Markdown"], ["pdf", "PDF"], ["docx", "Word"]]) {
            const link = document.createElement("a");
            link.href = `/api/chats/${encodeURIComponent(state.activeChatId)}/report.${format}`;
            link.textContent = name;
            link.download = `frogent-report.${format}`;
            exports.append(link);
        }
        el.messages.append(exports);
    }
    el.messages.scrollTop = el.messages.scrollHeight;
}

function normalizeChats(chats) {
    const result = {};
    if (!chats || typeof chats !== "object") return result;
    for (const [id, chat] of Object.entries(chats)) {
        if (!chat || typeof chat !== "object") continue;
        result[id] = {
            id,
            title: typeof chat.title === "string" ? chat.title : "Conversation",
            messages: Array.isArray(chat.messages) ? chat.messages : [],
            createdAt: chat.createdAt || new Date().toISOString(),
            updatedAt: chat.updatedAt || chat.createdAt || new Date().toISOString(),
            files: Array.isArray(chat.files) ? chat.files : [],
            molecules: Array.isArray(chat.molecules) ? chat.molecules : [],
        };
    }
    return result;
}

async function login(event) {
    event.preventDefault();
    status(el["login-status"], "Signing in…");
    try {
        const payload = await requestJson("/api/login", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                username: el["login-username"].value.trim(),
                password: el["login-password"].value,
            }),
        });
        state.userId = payload.user_id;
        state.username = el["login-username"].value.trim();
        state.chats = normalizeChats(payload.chat_sessions);
        el["account-name"].textContent = state.username;
        showView("chat");
        const first = sortedChats()[0];
        if (first) selectChat(first.id);
        else newChat();
        status(el["login-status"]);
    } catch (error) {
        status(el["login-status"], error.message, true);
    }
}

async function register(event) {
    event.preventDefault();
    if (el["register-password"].value !== el["register-confirm"].value) {
        status(el["register-status"], "Passwords do not match.", true);
        return;
    }
    status(el["register-status"], "Creating account…");
    try {
        await requestJson("/api/register", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                username: el["register-username"].value.trim(),
                email: el["register-email"].value.trim(),
                password: el["register-password"].value,
            }),
        });
        el["register-form"].reset();
        showView("login");
        status(el["login-status"], "Account created. You can sign in.");
    } catch (error) {
        status(el["register-status"], error.message, true);
    }
}

async function logout() {
    try {
        await requestJson("/api/logout", {method: "POST"});
    } catch {
        // Clear the local authenticated surface even when the server is unavailable.
    }
    state.userId = null;
    state.username = null;
    state.chats = {};
    state.activeChatId = null;
    state.pendingFiles = [];
    el["login-form"].reset();
    renderAttachments();
    showView("login");
}

async function uploadFiles() {
    const files = [...el["file-input"].files];
    if (!files.length) return;
    const body = new FormData();
    for (const file of files) body.append("file", file);
    status(el["chat-status"], "Uploading files…");
    el.attach.disabled = true;
    try {
        const payload = await requestJson("/api/upload", {method: "POST", body});
        state.pendingFiles.push(...payload.files);
        renderAttachments();
        status(el["chat-status"]);
    } catch (error) {
        status(el["chat-status"], error.message, true);
    } finally {
        el.attach.disabled = false;
        el["file-input"].value = "";
    }
}

function renderAttachments() {
    el["attachment-status"].textContent = state.pendingFiles.length
        ? `Ready: ${state.pendingFiles.map((item) => item.filename).join(", ")}`
        : "";
}

async function sendMessage() {
    if (state.sending || !state.activeChatId) return;
    const message = el["message-input"].value.trim();
    if (!message && !state.pendingFiles.length) return;
    const chat = state.chats[state.activeChatId];
    const files = [...state.pendingFiles];
    const fileNames = files.map((item) => item.filename);
    chat.messages.push({content: message, isUser: true, fileNames});
    if (chat.messages.length === 1) {
        chat.title = message ? `${message.slice(0, 42)}${message.length > 42 ? "…" : ""}` : "File analysis";
    }
    chat.updatedAt = new Date().toISOString();
    state.pendingFiles = [];
    el["message-input"].value = "";
    renderAttachments();
    renderHistory();
    renderMessages();
    setSending(true, "FROGENT is working…");
    try {
        const answer = await streamAnswer(message, files);
        chat.messages.push({content: answer, isUser: false, name: "agent"});
        chat.updatedAt = new Date().toISOString();
        renderHistory();
        renderMessages();
        status(el["chat-status"]);
    } catch (error) {
        chat.messages.push({content: `Agent error: ${error.message}`, isUser: false, name: "error"});
        renderMessages();
        status(el["chat-status"], error.message, true);
    } finally {
        setSending(false);
    }
}

function setSending(value, message = "") {
    state.sending = value;
    el.send.disabled = value;
    el.attach.disabled = value;
    el["message-input"].disabled = value;
    status(el["chat-status"], message);
    if (!value) el["message-input"].focus();
}

async function streamAnswer(message, files) {
    const response = await fetch("/api/chat", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({message, files, chat_id: state.activeChatId}),
    });
    if (!response.ok || !response.body) {
        let detail = `Chat request failed (${response.status})`;
        try {
            const payload = await response.json();
            detail = payload.message || detail;
        } catch {
            // Retain the status-based error.
        }
        throw new Error(detail);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let answer = "";
    let done = false;
    while (!done) {
        const part = await reader.read();
        buffer += decoder.decode(part.value || new Uint8Array(), {stream: !part.done});
        buffer = buffer.replace(/\r\n/g, "\n");
        let boundary;
        while ((boundary = buffer.indexOf("\n\n")) >= 0) {
            const frame = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + 2);
            const result = consumeFrame(frame, answer);
            answer = result.answer;
            done = done || result.done;
            if (result.error) throw new Error(result.error);
            if (answer) {
                status(el["chat-status"], "Receiving Agent answer…");
            }
        }
        if (part.done) break;
    }
    if (!answer.trim()) throw new Error("Agent returned no answer.");
    return answer;
}

function consumeFrame(frame, currentAnswer) {
    const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n");
    if (!data) return {answer: currentAnswer, done: false};
    if (data === "[DONE]") return {answer: currentAnswer, done: true};
    try {
        const event = JSON.parse(data);
        if (typeof event.error === "string" && event.error) {
            return {answer: currentAnswer, done: false, error: event.error};
        }
        return {
            answer: typeof event.content === "string" ? event.content : currentAnswer,
            done: false,
        };
    } catch {
        return {answer: currentAnswer, done: false};
    }
}

function resizeInput() {
    el["message-input"].style.height = "auto";
    el["message-input"].style.height = `${Math.min(el["message-input"].scrollHeight, 180)}px`;
}

el["login-form"].addEventListener("submit", login);
el["register-form"].addEventListener("submit", register);
el["show-register"].addEventListener("click", () => showView("register"));
el["show-login"].addEventListener("click", () => showView("login"));
el.logout.addEventListener("click", logout);
el["new-chat"].addEventListener("click", newChat);
el["open-sidebar"].addEventListener("click", () => el.sidebar.classList.add("open"));
el["close-sidebar"].addEventListener("click", () => el.sidebar.classList.remove("open"));
el.attach.addEventListener("click", () => el["file-input"].click());
el["file-input"].addEventListener("change", uploadFiles);
el.send.addEventListener("click", sendMessage);
el["message-input"].addEventListener("input", resizeInput);
el["message-input"].addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
});

showView("login");
el["login-username"].focus();
