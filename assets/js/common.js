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
    static isEmpty(obj) {
        if (Array.isArray(obj)) {
            return obj.length === 0;
        } else if (typeof obj === 'string') {
            return obj.trim().length === 0;
        } else if (obj!== null && typeof obj === 'object') {
            return Object.keys(obj).length === 0;
        } else {
            return!obj;
        }
    }
}
class I18NManager {
    constructor() {
        this._i18n = {}
        this._lang = "zh_CN"
        globalThis.$i18n = this;
    }
    addLangage(lang, key, value) {
        if (!(lang in this._i18n)) {
            this._i18n[lang] = {}
        }
        this._i18n[lang][key] = value;
    }
    addLanguageTable(lang, table) {
        Object.entries(table).forEach(([key, value]) => {
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
        Object.entries(params || {}).forEach(([key, v]) => {
            if (v instanceof Element) {
                var e = document.createElement("div");
                e.appendChild(v.origin);
                v = e.innerHTML;
            }
            value = value.replaceAll(`%${key}%`, v);
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
        globalThis.$ElementManager = this;
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
        } else {
            console.log(object)
        }
        this._i18n_key = null;
        this._i18n_params = {};
        this._children = []
        this._styles = {}
        globalThis.$ElementManager.add(this);
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
    i18n(key, params = {}) {
        this._i18n_key = key;
        this._i18n_params = params;
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
        this.html($i18n.t(this._i18n_key, this._i18n_params))
    }
    append(...elements) {
        elements.forEach(element => {
            if (Utils.isDOM(element)) {
                element = new Element(element);
            }
            this._children.push(element);
            this._base.appendChild(element.origin);
        })
        return this
    }
    classes(...classes) {
        this._base.classList.add(...classes);
        return this;
    }
    removeClasses(...classes) {
        this._base.classList.remove(...classes);
        return this;
    }
    removeAllClasses() {
        this._base.classList = [];
        return this
    }
    hasClasses(...classes) {
        console.log(classes, this._base.classList.contains(...classes), this._base.classList)
        return this._base.classList.contains(...classes);
    }
    toggle(...classes) {
        this._base.classList.toggle(...classes);
        return this;
    }
    style(key, value) {
        this._base.style[key] = value;
        return this;
    }
    styleProperty(key, value) {
        this._base.style.setProperty(key, value);
        return this;
    }
    value(value) {
        this._base.value = value;
        return this;
    }
    get val() {
        return this._base.value;
    }
    addEventListener(event, handler) {
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
        this._base.removeChild(object.origin);
        return this
    }
    get firstChild() {
        return this._children[0];
    }
    get lastChild() {
        return this._children[this._children.length - 1];
    }
    remove() {
        this._children.forEach(child => child.remove());
        this._base.remove();
    }
    clear() {
        this._children.forEach(child => child.remove());
        this.html("")
        this.removeClasses(
            ...this._base.classList.values()
        )
    }
    appendBefore(element) {
        this._children.unshift(element);
        this._base.insertBefore(element.origin, this._base.firstChild);
        return this
    }
    attributes(attributes) {
        Object.entries(attributes).forEach(([key, value]) => {
            this._base.setAttribute(key, value);
        })
        return this;
    }
    click() {
        return this.origin.click()
    }
    create(object, handler = null) {
        var obj = new Element(object);
        if (handler != null) {
            handler(obj);
        }
        this.append(obj);
        return this
    }
    focus() {
        return this.origin.focus()
    }
}
class Configuration {
    constructor(storage) {
        this.storage = storage ?? localStorage
    }
    get(key, _def) {
        var item = this.storage.getItem(key) != null ? JSON.parse(this.storage.getItem(key)) : {
            value: _def
        };
        return item.value;
    }
    set(key, value) {
        this.storage.setItem(key, JSON.stringify({
            "value": value,
            "timestamp": new Date()
        }));
    }
}
class Style {
    constructor($configuration) {
        globalThis.$style = this;
        this._styles = {}
        this._medias = {}
        this._style_dom = document.createElement("style");
        this._style_sheet = this._style_dom.sheet;
        this._themes = {}
        this._current_theme = null;
        this.applyTheme($configuration.get("theme", window.matchMedia("(prefers-color-scheme: dark)") ? "dark" : "light"))
        document.getElementsByTagName("head").item(0).appendChild(this._style_dom);
        this.render_task = null;
    }
    _parseToString(object) {
        if (Array.isArray(object)) {
            return object.map(this._parseToString).join(";");
        } else if (typeof object == "object") {
            return Object.entries(object).map(([key, value]) => typeof value === "object" ? `${key}{${this._parseToString(value)}}` : `${key}:${this._parseToString(value)};`).join("");
        } else {
            return object.toString();
        }
    }
    add(name, style) {
        if (!name.startsWith("@")) {

            this._styles[name] = (this._styles[name] || '') + ";" + this._parseToString(style);
        } else {
            if (!(name in this._medias)) this._medias[name] = []
            if (this._medias[name].indexOf(style) == -1) this._medias[name].push(this._parseToString(style));
            this._styles[name] = this._medias[name].join(";");
        }
        if (this.render_task != null) return;
        this.render_task = requestAnimationFrame(() => {
            this.render();
            this.render_task = null;
        })
    }
    addAll(styles) {
        Object.entries(styles).forEach(([name, style]) => this.add(name, style));
    }
    render() {
        const theme = {};
        Object.entries(this._themes[this._current_theme] || {}).forEach(([key, value]) => {
            theme[`--${key}`] = value;
        })
        this._styles[":root"] = this._parseToString(theme); 
        const styleRules = Object.entries(this._styles).map(([name, style]) => style == null ? "" : `${name}{${style}}`.replaceAll(/\n|\t|\r/g, "").replaceAll(/\s\s/g, " "));
        requestAnimationFrame(() => {
            this._clear_render();
            styleRules.forEach(styleRule => {
                this._sheet_render(styleRule);
            });   
        })
    }
    _clear_render() {
        this._style_sheet = this._style_dom.sheet;
        if (this._style_sheet) {
            this._clear_render = () => {
                while (this._style_sheet.cssRules.length > 0) {
                    this._style_sheet.deleteRule(0);
                }
            }
        } else {
            this._clear_render = () => {
                while (this._style_dom.childNodes.length > 0) {
                    this._style_dom.removeChild(this._style_dom.childNodes[0]);
                }
            }
        }
        this._clear_render()
    }
    _sheet_render(styleRule) {
        this._style_sheet = this._style_dom.sheet;
        if (this._style_sheet) {
            try {
                var handler = (styleRule) => {
                    this._style_sheet.insertRule(styleRule, this._style_sheet.cssRules.length);
                }
                handler(styleRule)
                this._sheet_render = handler;
                return;
            } catch (e) {
                console.log(e)
            }
        }
        this._sheet_render = (styleRule) => this._style_dom.appendChild(document.createTextNode(styleRule));
        this._sheet_render()
    }
    applyTheme(name) {
        this._current_theme = name || Object.keys(this._themes)[0];
        this.render();
    }
    setTheme(name, style) {
        this._themes[name] = style;
    }
}
class SVGContainers {
    static _parse(element) {
        return new Element(document.createRange().createContextualFragment(element).childNodes[0]);
    }
    static get menu() {
        return SVGContainers._parse('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path d="M4 6h16v2H4zm0 5h16v2H4zm0 5h16v2H4z"></path></svg>')
    }
    static get moon() {
        return SVGContainers._parse('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path d="M12 11.807A9.002 9.002 0 0 1 10.049 2a9.942 9.942 0 0 0-5.12 2.735c-3.905 3.905-3.905 10.237 0 14.142 3.906 3.906 10.237 3.905 14.143 0a9.946 9.946 0 0 0 2.735-5.119A9.003 9.003 0 0 1 12 11.807z"></path></svg>')
    }
    static get sun() {
        return SVGContainers._parse('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path d="M6.995 12c0 2.761 2.246 5.007 5.007 5.007s5.007-2.246 5.007-5.007-2.246-5.007-5.007-5.007S6.995 9.239 6.995 12zM11 19h2v3h-2zm0-17h2v3h-2zm-9 9h3v2H2zm17 0h3v2h-3zM5.637 19.778l-1.414-1.414 2.121-2.121 1.414 1.414zM16.242 6.344l2.122-2.122 1.414 1.414-2.122 2.122zM6.344 7.759 4.223 5.637l1.415-1.414 2.12 2.122zm13.434 10.605-1.414 1.414-2.122-2.122 1.414-1.414z"></path></svg>')
    }
    static get user() {
        return SVGContainers._parse('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path d="M12 2A10.13 10.13 0 0 0 2 12a10 10 0 0 0 4 7.92V20h.1a9.7 9.7 0 0 0 11.8 0h.1v-.08A10 10 0 0 0 22 12 10.13 10.13 0 0 0 12 2zM8.07 18.93A3 3 0 0 1 11 16.57h2a3 3 0 0 1 2.93 2.36 7.75 7.75 0 0 1-7.86 0zm9.54-1.29A5 5 0 0 0 13 14.57h-2a5 5 0 0 0-4.61 3.07A8 8 0 0 1 4 12a8.1 8.1 0 0 1 8-8 8.1 8.1 0 0 1 8 8 8 8 0 0 1-2.39 5.64z"></path><path d="M12 6a3.91 3.91 0 0 0-4 4 3.91 3.91 0 0 0 4 4 3.91 3.91 0 0 0 4-4 3.91 3.91 0 0 0-4-4zm0 6a1.91 1.91 0 0 1-2-2 1.91 1.91 0 0 1 2-2 1.91 1.91 0 0 1 2 2 1.91 1.91 0 0 1-2 2z"></path></svg>')
    }
    static get close() {
        return SVGContainers._parse('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path d="m16.192 6.344-4.243 4.242-4.242-4.242-1.414 1.414L10.535 12l-4.242 4.242 1.414 1.414 4.242-4.242 4.243 4.242 1.414-1.414L13.364 12l4.242-4.242z"></path></svg>')
    }
    static get exit() {
        return SVGContainers._parse('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path d="M19.002 3h-14c-1.103 0-2 .897-2 2v4h2V5h14v14h-14v-4h-2v4c0 1.103.897 2 2 2h14c1.103 0 2-.897 2-2V5c0-1.103-.898-2-2-2z"></path><path d="m11 16 5-4-5-4v3.001H3v2h8z"></path></svg>')
    }
    static get arrow_down() {
        return SVGContainers._parse('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path d="M16.293 9.293 12 13.586 7.707 9.293l-1.414 1.414L12 16.414l5.707-5.707z"></path></svg>')
    }
}
class Progressbar extends Element {
    constructor() {
        super("div")
        $style.addAll({
            ".progressbar": {
                "width": "100%",
                "height": "2px",
                "background": "var(--background)",
                "position": "absolute",
                "top": "0",
                "left": "0",
                "z-index": "9999"
            },
            ".progressbar > div": {
                "width": "0",
                "height": "100%",
                "background": "var(--main-color)",
                "transition": "width 0.5s ease-in-out"
            }
        })
        this.classes("progressbar")
        this._child = createElement("div")
        this._child.style("--progress", 0)
        this.append(this._child)
        this.set(0)
        this._clear = null
    }
    set(progress) {
        if (this._clear != null) {
            clearTimeout(this._clear)
            this._clear = null
        }
        requestAnimationFrame(() => {
            this._child.style("width", progress + "%")
        })
    }
    clear() {
        if (this._clear) {
            clearTimeout(this._clear)
            this._clear = null
        }
        this._clear = setTimeout(() => {
            this.set(0)
            requestAnimationFrame(() => {
                this._child.style("width", 0)
            })
        }, 1000)
    }
}
class Modal extends Element {
    constructor() {
        super("div")
        globalThis.$modal = this
        $style.addAll({
            ".modal": {
                "position": "fixed",
                "top": "0",
                "left": "0",
                "width": "100vw",
                "height": "100vh",
                "background": "rgba(0, 0, 0, 0.4)",
                "z-index": "9999",
                "display": "flex",
                "align-items": "center",
                "justify-content": "center",
                "transition": "opacity 300ms cubic-bezier(0.4, 0, 0.2, 1)",
                "overflow": "auto"
            },
            ".modal.opacity-0": {
                "opacity": "0"
            },
            ".modal.hidden": {
                "display": "none"
            },
        })
        this.classes("modal")
        this.task = null
        this.addEventListener("click", (event) => {
            if (event.target == this.origin) {
                this.hide()
            }
        })
        window.addEventListener("DOMContentLoaded", () => {
            document.body.prepend(this.origin)
        })
        this.classes("hidden", "opacity-0")
    }
    show() {
        this.removeClasses("hidden")
        requestAnimationFrame(() => {
            this.removeClasses("opacity-0")
        })
        return this;
    }
    hide() {
        this.classes("opacity-0")
        if (this.task != null) return;
        this.task = setTimeout(() => {
            this.classes("hidden")
            while (this.firstChild != null) {
                this.removeChild(this.firstChild)
            }
            this.task = null
        }, 300)
        return this;
    }
}
function createElement(object) {
    return new Element(object);
}
class RouteEvent {
    constructor(instance, before_route, current_route, params = {}) {
        this.instance = instance;
        this.current_route = current_route
        this.before_route = before_route
        this.params = params
    }
}
class Router {
    constructor(route_prefix = "/") {
        this._route_prefix = route_prefix.replace(/\/+$/, "")
        this._before_handlers = []
        this._after_handlers = []
        this._current_path = this._get_current_path()
        this._routes = []
    }
    init() {
        window.addEventListener("popstate", () => {
            this._popstate_handler()
        })
        this._popstate_handler()
        window.addEventListener("click", (e) => {
            if (e.target.tagName == "A") {
                const href = e.target.getAttribute("href")
                const url = new URL(href, window.location.origin);
                if (url.origin != window.location.origin) return;
                e.preventDefault()
                if (url.pathname.startsWith(this._route_prefix)) {
                    this._popstate_handler(url.pathname)
                }
            }
        })
    }
    page(path) {
        this._popstate_handler(path)
    }
    _get_current_path() {
        return window.location.pathname
    }
    async _popstate_handler(path) {
        const new_path = (path ?? this._get_current_path()).replace(this._route_prefix, "") || "/"
        const old_path = this._current_path
        if (old_path == new_path) return;
        window.history.pushState(null, '', this._route_prefix + new_path)
        this._current_path = new_path
        this._before_handlers.forEach(handler => {
            try {
                handler(new RouteEvent(this, old_path, new_path))
            } catch (e) {
                console.log(e)
            }
        })
        try {
            // get route
            var routes = this._routes.filter(x => x.path.test(new_path))
            if (routes) {
                routes.forEach(route => {
                    var params = route.path.exec(new_path).slice(1).reduce((acc, cur, i) => {
                        acc[route.params[i]] = cur
                        return acc
                    }, {})
                    var handler = route ? route.handler : null
                    if (handler) {
                        try {
                            handler(new RouteEvent(this, old_path, new_path, params))
                        } catch (e) {
                            console.log(e)
                        }
                    }
                })
                
            }
        } catch (e) {
            console.log(e)
        }
        this._after_handlers.forEach(handler => {
            try {
                handler(new RouteEvent(this, old_path, new_path))
            } catch (e) {
                console.log(e)
            }
        })
    }
    on(path, handler) {
        // path {xxx}
        // replace to like python (?P<xxx>*.+)
        var params = (path.match(/\{((\w+)|(\:(url)\:))\}/g) || []).map(x => x.replaceAll("{", "").replaceAll("}", "").replaceAll(":", ""))
        var regexp_path = path.replace(/\{\:(url)\:\}/g, "(.*)").replace(/\{(\w+)\}/g, "([^/]*)")
        var config = {
            raw_path: path,
            path: new RegExp(`^${regexp_path}$`),
            params: params,
            handler
        }
        this._routes.push(config)
        // sort path length
        this._routes.sort((a, b) => b.path.length - a.path.length)
        return this
    }
    before_handler(handler) {
        if (handler == null) this;
        this._before_handlers.push(handler)
        return this
    }
    after_handler(handler) {
        if (handler == null) this;
        this._after_handlers.push(handler)
        return this
    }
}
class ServiceData {
    causedBy = null
    httpCode = null
}
class ServiceError extends Error {
    $isServiceError = false;
    constructor(code, message, data) {
        super(message, { cause: data?.causedBy })
        this.message = message
        this.code = code
        if (typeof data === 'object' && data) {
            if (typeof data.httpCode === 'number') {
                this.httpCode = data.httpCode
            }
            this.data = data;
        }
    }
    static fromJSON(json) {
        try {
            const error = new ServiceError(json.code, json.message, json.data)
            error.httpCode = json.httpCode;
            return error
        } catch (e) {
            if ('message' in json) {
                const err = new Error(json.message);
                if (typeof json.stack === 'string') {
                    err.stack = json.stack;
                }
                Object.assign(err, json);
                return new ServiceError('COMMON_UNKNOWN', '未知错误', {
                    causedBy: err,
                });
            }
            else {
                return new ServiceError('COMMON_UNKNOWN', '未知错误', {
                    error: json,
                });
            }
        }
    }
    static fromError(error) {
        return new ServiceError('COMMON_UNKNOWN', '未知错误', {
            causedBy: error,
        });
    }
    static isServiceError(error) {
        return typeof error === 'object' && error !== null && error.$isServiceError === true;
    }
}
class InputElement extends Element {
    constructor() {
        super("div")
        $style.addAll({
            ".simple-input": `
                display: inline-flex;
                flex-direction: column;
                position: relative;
                min-width: 0px;
                vertical-align: top;
                width: 100%;
            `,
            ".simple-input label": `
                color: var(--text-dark-color);
                font-size: 14px;
                font-family: inherit;
                font-weight: 400;
                line-height: 1.4375em;
                display: block;
                transform-origin: left top;
                text-overflow: ellipsis;
                max-width: calc(100% - 24px);
                position: absolute;
                left: -4px;
                top: 0px;
                transform: translate(14px, 9px) scale(1);
                z-index: 1;
                pointer-events: none;
                padding: 0px 4px;
                white-space: nowrap;
                overflow: hidden;
                background: var(--background);
                transition: color 200ms cubic-bezier(0, 0, 0.2, 1), transform 200ms cubic-bezier(0, 0, 0.2, 1), max-width 200ms cubic-bezier(0, 0, 0.2, 1); 
            `,
            ".simple-input .input": `
                font-size: 14px;
                font-family: inherit;
                font-weight: 400;
                line-height: 1.4375em;
                color: rgb(0, 0, 0);
                box-sizing: border-box;
                cursor: text;
                display: inline-flex;
                -webkit-box-align: center;
                align-items: center;
                width: 100%;
                position: relative;
                border-radius: 4px;
            `,
            ".simple-input .input input": `
                font: inherit;
                letter-spacing: inherit;
                color: currentcolor;
                border: 0px;
                box-sizing: content-box;
                background: none;
                height: 1.4375em;
                margin: 0px;
                -webkit-tap-highlight-color: transparent;
                display: block;
                min-width: 0px;
                width: 100%;
                animation-name: mui-auto-fill-cancel;
                animation-duration: 10ms;
                padding: 8.5px 14px;
            `,
            ".simple-input .input:hover fieldset": {
                "border-color": "var(--main-color)",
            },
            ".simple-input .input fieldset": {
                "border-color": "var(--input-border-color)",
                "text-align": "left",
                "position": "absolute",
                "bottom": "0px",
                "right": "0px",
                "top": "-5px",
                "left": "0px",
                "pointer-events": "none",
                "min-width": "0%",
                "margin": "0px",
                "padding": "0px 8px",
                "border-radius": "inherit",
                "border-style": "solid",
                "border-width": "1px",
                "overflow": "hidden",
                "border-color": "rgba(0, 0, 0, 0.23)"
            },
            ".simple-input .input legend": `
                float: unset;
                width: auto;
                display: block;
                height: 11px;
                font-size: 0.75em;
                visibility: hidden;
                max-width: 0.01px;
                overflow: hidden;
                padding: 0px;
                transition: max-width 50ms cubic-bezier(0, 0, 0.2, 1);
                white-space: nowrap;
                background: var(--background)
            `,
            ".simple-input .input legend > span": `
                padding-left: 5px;
                padding-right: 5px;
                display: inline-block;
                opacity: 0;
                visibility: visible;
            `,
            ".simple-input.focus label": {
                "color": "var(--main-color)"
            },
            ".simple-input.focus .input fieldset": {
                "border-color": "var(--main-color)",
                "border-width": "2px",
            },
            ".simple-input.active label": {
                "transform": "translate(14px, -9px) scale(0.75);"
            }
        })
        this.$input = createElement("input")
        this.classes("simple-input")
        this.$label = createElement("label")
        this.$label_span = createElement("span")
        this.$error_label = createElement("p")
        this.append(this.$label, createElement("div").classes("input").append(this.$input.addEventListener("focus", () => {
            this.classes("focus")
        }).addEventListener("blur", () => {
            this.removeClasses("focus")
            if (Utils.isEmpty(this.$input.val)) {
                this.removeClasses("active")
            }
        }).addEventListener("click", () => {
            this.classes("active")
        }), createElement("fieldset").append(
            createElement("legend").append(this.$label_span))
        )).addEventListener("input", () => {
            this.classes("focus")
            if (Utils.isEmpty(this.$input.val)) {
                this.removeClasses("active")
            } else {
                this.classes("active")
            }
        })
    }
    label(value) {
        this.$label_span.text(value)
        this.$label.text(value)
        return this
    }
    label_i18n(key, params = {}) {
        this.$label_span.i18n(key, params)
        this.$label.i18n(key, params)
        return this
    }
    label_t18n(params) {
        this.$label_span.t18n(params)
        this.$label.t18n(params)
        return this
    }
    get input() {
        return this.$input
    }
    focus() {
        return this.$input.focus()
    }
    click() {
        return this.$input.click()
    }
    value(value) {
        this.$input.value(value)
        if (Utils.isEmpty(this.$input.val)) {
            this.removeClasses("active")
        } else {
            this.classes("active")
        }
        return this
    }
}
function parseJWT(token) {
    try {
        header, payload, signature = token.split(".")
        return {
            header: btoa(header),
            payload: btoa(payload),
            signature: signature
        }
    } catch (e) {
        return null
    }
}
function ref(object, params) {
    var handler = params.handler || function () { };
    var timeout = params.timeout || 0
    var task = null;
    return new Proxy(object, {
        set(target, key, value) {
            target[key] = value
            if (timeout > 0) {
                if (task) {
                    clearTimeout(task)
                }
                task = setTimeout(() => {
                    handler({
                        key,
                        value,
                        object
                    })
                    task = null
                }, timeout)
            } else {
                handler({
                    key,
                    value,
                    object
                })
            }
            return true
        }
    })
}
function calcElementHeight(element) {
    var origin = element.origin;
    var rect = origin.getBoundingClientRect()
    return rect.height
}
function calcElementWidth(element) {
    var origin = element.origin;
    var rect = origin.getBoundingClientRect()
    return rect.width
}
class Lock {
    _lock = false;
    _waitList = [];
    async acquire() {
        if (this._lock) {
            await new Promise((resolve) => {
                this._waitList.push(resolve);
            });
        }
        this._lock = true;
    }
    release() {
        this._lock = false;
        if (this._waitList.length > 0) {
            let resolve = this._waitList.shift();
            resolve && resolve();
        }
    }
}
const process_pid = Math.floor(Math.random() * 0xFFFFFF)
class ObjectID {
    static _pid = process_pid;
    static _inc = Math.floor(Math.random() * 0xFFFFFF);
    static _inc_lock = new Lock();
    static _type_marker = 7;
    static _MAX_COUNTER_VALUE = 0xFFFFFF;
    static __random = ObjectID._randomBytes();
    __id;
    constructor(oid) {
        if (oid instanceof ArrayBuffer) {
            if (oid.byteLength != 12)
                ObjectID.raise(oid);
            this.__id = oid;
        }
        else if (oid instanceof ObjectID || typeof oid === "string") {
            this._validate(oid);
        }
        else {
            ObjectID.raise(oid);
        }
    }
    static _random() {
        if (ObjectID._pid != process_pid) {
            ObjectID._pid = process_pid;
            ObjectID.__random = ObjectID._randomBytes();
        }
        return ObjectID.__random; // 4 bytes current time, 5 bytes random, 3 bytes inc.
    }
    static async create() {
        await ObjectID._inc_lock.acquire();
        var inc = ObjectID._inc;
        ObjectID._inc = (inc + 1) % ObjectID._MAX_COUNTER_VALUE;
        var res_id = [ObjectID.PACKINT_RANDOM((new Date()).getTime() / 1000, ObjectID._random()), ObjectID.PACKINT(inc).slice(1, 4)];
        ObjectID._inc_lock.release();
        var res = new ArrayBuffer(res_id[0].byteLength + res_id[1].byteLength);
        var offset = 0;
        for (let r of res_id) {
            const view = new Uint8Array(r);
            for (let i = 0; i < view.length; i++) {
                res[i + offset] = view[i];
            }
            offset += view.length;
        }
        return new ObjectID(res);
    }
    _validate(oid) {
        if (oid instanceof ObjectID) {
            this.__id = oid.__id;
        }
        else if (typeof oid == "string" && oid.length == 24) {
            this.__id = Buffer.from(oid, "hex").buffer;
        }
        else {
            ObjectID.raise(oid);
        }
    }
    static raise(oid) {
        throw new Error(oid + " is not a valid ObjectId, it must be a 12-byte input or a 24-character hex string");
    }
    static _randomBytes() {
        var buf = new Uint8Array(5);
        for (let i = 0; i < 5; i++) {
            buf[i] = Math.floor(Math.random() * 256);
        }
        return buf.buffer;
    }
    static PACKINT(int) {
        const buf = new ArrayBuffer(4);
        const view = new DataView(buf);
        view.setInt32(0, int, false);
        return buf;
    }
    static UNPACKINT(buf) {
        return new DataView(buf).getInt32(0);
    }
    static PACKINT_RANDOM(int, random) {
        const int_buf = new ArrayBuffer(4);
        const intView = new DataView(int_buf);
        intView.setInt32(0, int, false);

        const res = new ArrayBuffer(int_buf.byteLength + random.byteLength);
        const resView = new DataView(res);

        // 复制整数部分数据
        for (let i = 0; i < int_buf.byteLength; i++) {
            resView.setUint8(i, intView.getUint8(i));
        }

        // 复制随机字节部分数据
        const randomUint8 = new Uint8Array(random);
        for (let i = 0; i < random.byteLength; i++) {
            resView.setUint8(int_buf.byteLength + i, randomUint8[i]);
        }

        return res;
    }
    toString() {
        if (this.__id == undefined) {
            return "";
        }
        var res = "";
        for (let i = 0; i < this.__id.byteLength; i++) {
            res += ("0" + this.__id[i].toString(16)).slice(-2);
        }
        return res;
    }
    get generationTime() {
        if (this.__id == undefined) {
            return new Date(0);
        }
        return new Date(ObjectID.UNPACKINT(this.__id.slice(0, 4)) * 1000);
    }
    static fromDate(date) {
        var res_id = [ObjectID.PACKINT_RANDOM(date.getTime() / 1000, ObjectID._randomBytes()), ObjectID.PACKINT(0).slice(1, 4)];
        var res = new ArrayBuffer(res_id[0].byteLength + res_id[1].byteLength);
        var offset = 0;
        for (let r of res_id) {
            const view = new Uint8Array(r);
            for (let i = 0; i < view.length; i++) {
                res.writeUInt8(view[i], i + offset);
            }
            offset += view.length;
        }
        return new ObjectID(res);
        //return new ObjectID(ObjectID.PACKINT_RANDOM(date.getTime() / 1000, ObjectID._randomBytes()));
    }
}
export {
    Element,
    SVGContainers,
    Progressbar,
    createElement,
    Configuration,
    Router,
    ElementManager,
    I18NManager,
    Style,
    ServiceData,
    ServiceError,
    Modal,
    InputElement,
    Utils,
    ref,
    calcElementHeight,
    calcElementWidth,
    ObjectID
}