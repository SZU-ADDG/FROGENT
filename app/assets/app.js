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

function renderMessages() {
    el.messages.replaceChildren();
    const messages = state.chats[state.activeChatId]?.messages || [];
    if (!messages.length) el.messages.append(welcome());
    for (const message of messages) el.messages.append(messageNode(message));
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
