class Utils {
    static uuid(len, radix) {
        var chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'.split('');
        var uuid = [], i;
        radix = radix || chars.length;
     
        if (len) {
            for (i = 0; i < len; i++) uuid[i] = chars[0 | Math.random()*radix];
        } else {
            var r;
            uuid[8] = uuid[13] = uuid[18] = uuid[23] = '-';
            uuid[14] = '4';
            for (i = 0; i < 36; i++) {
                if (!uuid[i]) {
                    r = 0 | Math.random()*16;
                    uuid[i] = chars[(i == 19) ? (r & 0x3) | 0x8 : r];
                }
            }
        }
        return uuid.join('').toLocaleLowerCase();
    }
    static isDOM(o) {
        return (
            typeof HTMLElement === "object" ? o instanceof HTMLElement : //DOM2
            o && typeof o === "object" && o !== null && o.nodeType === 1 && typeof o.nodeName==="string"
        );
    }
}
class Socket {
    constructor(baseurl) {
        this._ws = null;
        this._wsReconnectTask = null;
        this._clientId = Utils.uuid();
        this._baseurl = baseurl;
        this._url = this._baseurl + "?id=" + this._clientId
        this._keepaliveTask = null;
        this._echoCallbacks = {}
        this._wsConnect()
        window.addEventListener("beforeunload", () => {
            this.send("disconnect")
            this._ws?.close()
        })
        setInterval(() => this._keepalive(), 5000);
        this._keepalive();
    }
    async _keepalive() {
        console.log(await this.send("keepalive", {
            "timestamp": new Date()
        }))
    }
    async _sendByXHR(event, data) {
        var xhr = new XMLHttpRequest();
        var echo_id = Utils.uuid();
        xhr.addEventListener("readystatechange", (event) => {
            if (event.target.readyState == XMLHttpRequest.DONE) {
                this._dispatchData(JSON.parse(xhr.response)); 
            }
        })
        xhr.open("POST", this._url);
        return this._setEchoCallback(echo_id, () => {
            xhr.send(JSON.stringify({
                "event": event,
                "data": data,
                echo_id
            }));
            setTimeout(() => {
                xhr.abort();
            }, 10000)
        });
    }
    _dispatchData(responses) {
        responses.forEach(response => {
            const { echo_id, event, data } = response;
            console.log(echo_id, event)
            if (echo_id == null) { // global dispatch event

            } else if (echo_id in this._echoCallbacks) {
                var { resolve, reject, timer } = this._echoCallbacks[echo_id];
                delete this._echoCallbacks[echo_id];
                clearTimeout(timer);
                resolve(data);
            }
        });
    }
    _wsConnect() {
        clearTimeout(this._wsReconnectTask)
        this._ws?.close()
        this._ws = new WebSocket(
            this._url
        )
        this._ws.addEventListener("close", () => {
            console.warn("The websocket has disconnected. After 5s to reconnect.")
            setTimeout(() => {
                this._wsConnect()
            }, 5000)
        })
        this._ws.addEventListener("message", (event) => {
            var raw_data = JSON.parse(event.data);
            this._dispatchData(raw_data)
        })
    }
    _sendByWs(event, data) {
        if (this._ws?.readyState != WebSocket.OPEN) return;
        var echo_id = Utils.uuid();
        return this._setEchoCallback(echo_id, () => {
            this._ws.send(JSON.stringify(
                {
                    "event": event,
                    "data": data,
                    echo_id
                }
            ))
        });
    }
    _setEchoCallback(id, executor) {
        return new Promise((resolve, reject) => {
            this._echoCallbacks[id] = { resolve, reject, timer: setTimeout(() => {
                reject("Timeout Error.")
            }, 10000)};
            executor();
        })
    }
    async send(event, data) {
        var handler = this._ws?.readyState == WebSocket.OPEN ? this._sendByWs : this._sendByXHR
        return handler.bind(this)(event, data);
    }
    
}
class I18NManager {
    constructor() {
        this._i18n = {}
        this._lang = "zh_CN"
    }
    addLangage(lang, key, value) {
        if (!(lang in this._i18n)) {
            this._i18n[lang] = {}
        }
        this._i18n[lang][key] = value;
    }
    addLanguageTable(lang, table) {
        table.entries().forEach(([key, value]) => {
            this.addLangage(lang, key, value)
        })
    }
    t(key, params) {
        if (!(this._lang in this._i18n)) {
            return key;
        }
        var value = this._i18n[this._lang][key];
        if (value == null) {
            return key;
        }
        params.entries().forEach(([key, value]) => {
            value = value.replace(`%${key}%`, value);
        })
        return value;
    }
    setLang(lang) {
        this._lang = lang;
        window.dispatchEvent(new CustomEvent("langChange", { detail: lang }))
    }
}
class ElementManager {
    constructor() {
        this._elements = []
        window.addEventListener("langChange", (event) => {
            this._elements.forEach(element => element._render_i18n())
        })
    }
    add(element) {
        this._elements.push(element);
    }
}
class Element {
    constructor(object) {
        if (typeof object == "string") {
            this._base = document.createElement(object);
        } else if (Utils.isDOM(object)) {
            this._base = object;
        } 
        this._i18n_key = null;
        this._i18n_params = {};
        this._children = []
        $ElementManager.add(this);
    }
    get origin() {
        return this._base;
    }
    html(html) {
        this._base.innerHTML = html;
        return this;
    }
    text(text) {
        this._base.innerText = text;
        return this;
    }
    i18n(key) {
        this._i18n_key = key;
        this._render_i18n();
        return this;
    }
    t18n(params) {
        this._i18n_params = params || {};
        this._render_i18n();
        return this;
    }
    _render_i18n() {
        if (this._i18n_key == null) {
            return;
        }
        this.text($i18n.t(this._i18n_key))
    }
    append(element) {
        if (Utils.isDOM(element)) {
            element = new Element(element);
        }
        this._children.push(element);
        this._base.appendChild(element.origin);
    }
    classes(...classes) {
        this._base.classList.add(...classes);
        return this;
    }
    removeClasses(...classes) {
        this._base.classList.remove(...classes);
        return this;
    }
    style(key, value) {
        this._base.style[key] = value;
        return this;
    }
    on(event, handler) {
        this._base.addEventListener(event, handler);
        return this;
    }
    get children() {
        return this._children;
    }
    get length() {
        return this._children.length;
    }
    removeChild(object) {
        // first number
        // second dom
        // last element
        if (typeof object == "number") {
            this._children.splice(object, 1);
        } else if (Utils.isDOM(object)) {
            this._children.splice(this._children.indexOf(new Element(object)), 1);
        } else {
            this._children.splice(this._children.indexOf(object), 1);
        }
    }
    get firstChild() {
        return this._children[0];
    }
    get lastChild() {
        return this._children[this._children.length - 1];
    }
}
class Style {
    constructor() {
        this._styles = {}
        this._style_dom = document.createElement("style");
        document.getElementsByTagName("head").item(0).appendChild(this._style_dom);
    }
    _parseToString(object) {
        // if object is array, we foreach and parse again
        // if obejct is table, we join ";" in it
        // if object is string, we return it
        if (Array.isArray(object)) {
            return object.map(this._parseToString).join(";");
        } else if (typeof object == "object") {
            return Object.entries(object).map(([key, value]) => `${key}:${this._parseToString(value)}`).join(";");
        } else {
            return object.toString();
        }
    }
    add(name, style) {
        this._styles[name] = this._parseToString(style);
        this.render();
    }
    render() {
        this._style_dom.innerHTML = Object.entries(this._styles).map(([name, style]) => `${name}{${style}}`).join("");
    }
}
function createElement(object) {
    return new Element(object);
}
const $ElementManager = new ElementManager();
const $style = new Style();
const $i18n = new I18NManager();
const $socket = new Socket(window.location.origin + "/api");

window.addEventListener("DOMContentLoaded", () => {
    console.log("hello world")
    $style.add("body", {
        "background-color": "black"
    })
    Array.from(document.getElementsByClassName("preloader")).forEach(e => {
        const element = new Element(e);
        requestAnimationFrame(() => {
            element.classes("hidden");
            setTimeout(() => {
                element.remove();
            }, 5000)
        })
    })
})