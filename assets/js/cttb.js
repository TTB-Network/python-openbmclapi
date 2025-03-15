export var app = null;
var style = null
var i18n = null;

export class CTElement {
    constructor(
        tag = 'div',
    ) {
        if (typeof tag == 'string') {
            this.$base = document.createElement(tag);
        } else if (CTElement.isDOM(tag)) {
            this.$base = tag;
        } else throw new Error('Tag must be a string');
        this._children = [];
        this._i18n = {
            key: null,
            params: null
        }
        this._attr_i18n = {};
        
        // add into app
        if (app.elements.map(e => e.$base).includes(this.$base)) return;
        app.elements.push(this);
    }
    append(...children) {
        for (let child of children) {
            if (CTElement.isDOM(child)) {
                child = new CTElement(child);
            }
            if (!(child instanceof CTElement)) {
                throw new Error('Child must be a CTElement');
            }
            this.$base.appendChild(child.$base);
            this._children.push(child);
        }
        return this;
    }
    prepend(...children) {
        for (let child of children) {
            if (CTElement.isDOM(child)) {
                child = new CTElement(child);
            }
            if (!(child instanceof CTElement)) {
                throw new Error('Child must be a CTElement');
            }
            this.$base.prepend(child.$base);
            this._children.unshift(child);
        }
        return this;
    }
    removeChild(child) {
        if (CTElement.isDOM(child)) {
            child = new CTElement(child);
        }
        if (!(child instanceof CTElement)) {
            throw new Error('Child must be a CTElement');
        }
        if (Array.from(this.$base.children).find(c => c == child.$base) != undefined) this.$base.removeChild(child.$base);
        this._children = this._children.filter(c => c.$base != child.$base);
        return this;
    }
    findChild(child) {
        if (CTElement.isDOM(child)) {
            child = new CTElement(child);
        }
        if (!(child instanceof CTElement)) {
            throw new Error('Child must be a CTElement');
        }
        return this._children.find(c => c.$base == child.$base);
    }
    clear() {
        this._children = [];
        while (this.$base.firstChild != null) {
            this.$base.removeChild(this.$base.firstChild);
        }
        return this;
    }
    focus() {
        this.$base.focus();
        return this;
    }
    click() {
        this.$base.click();
        return this;
    }
    classes(...classes) {
        this.$base.classList.add(...classes);
        return this;
    }
    hasClasses(...classes) {
        return this.$base.classList.contains(...classes);
    }
    ctoggle(...classes) {
        this.$base.classList.toggle(...classes);
        return this;
    }
    style(key, value) {
        this.$base.style.setProperty(key, value);
        return this;
    }
    styles(styles) {
        for (let key in styles) {
            this.$base.style.setProperty(key, styles[key]);
        }
        return this;
    }
    removeClasses(...classes) {
        this.$base.classList.remove(...classes);
        return this;
    }
    text(text) {
        this.$base.innerText = text;
        return this;
    }
    html(html) {
        this.$base.innerHTML = html;
        return this;
    }
    listener(name, callback, options = {}) {
        this.$base.addEventListener(name, callback, options);
        return this;
    }
    remove() {
        this.$base.remove();
        delete this; // remove reference
    }
    i18n(key, params) {
        this._i18n = {
            key, 
            params
        }
        this._render_i18n();
        return this;
    }
    t18n(params) {
        this._i18n.params = params;
        this._render_i18n();
        return this;
    }
    _render_i18n() {
        if (this._i18n.key) {
            this.$base.innerHTML = i18n.t(this._i18n.key, this._i18n.params);
        }
    }
    attr(name, value) {
        this.$base.setAttribute(name, value);
        return this;
    }
    attr_i18n(name, key, params) {
        this._attr_i18n[name] = {
            key,
            params
        }
        this._render_attr_i18n();
        return this;
    }
    _render_attr_i18n() {
        for (let name in this._attr_i18n) {
            this.$base.setAttribute(name, i18n.t(this._attr_i18n[name].key, this._attr_i18n[name].params));
        }
    }
    get children() {
        return this._children;
    }
    get base() {
        return this.$base;
    }
    get inputValue() {
        return this.$base.value;
    }
    static isDOM(o) {
        return (
            typeof HTMLElement === "object" ? o instanceof HTMLElement : //DOM2
            o && typeof o === "object" && o !== null && o.nodeType === 1 && typeof o.nodeName==="string"
        );
    }
    static create(tag) {
        return new CTElement(tag);
    }
    get boundingClientRect() {
        return this.$base.getBoundingClientRect()
    }
    getattr(name) {
        return this.$base.getAttribute(name);
    }
}
class CTStyle {
    constructor() {
        this.theme = localStorage.getItem('theme') || 'auto';
        this.styles = {};
        this.medias = {}
        this.themes = {};
        this.root = {}

        this._raf = null;

        this.$style = document.createElement('style');

        document.head.appendChild(this.$style);

        this.loadDefaultTheme();
    }
    loadDefaultTheme() {
        this.addThemes("dark", {
            "background": "rgb(24, 24, 24)",
            "dark-color": "rgba(0, 0, 0, 0.8)",
            "color": "rgba(255, 255, 255, 0.8)"
        })
        this.addThemes("light", {
            "background": "rgb(248, 248, 247)",
            "dark-color": "rgba(255, 255, 255, 0.8)",
            "color": "rgba(0, 0, 0, 0.8)"
        })
    }
    isDark() {
        if (this.theme != 'auto') {
            return this.theme == 'dark';
        }
        return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    setTheme(theme) {
        if (['auto', 'dark', 'light'].indexOf(theme) == -1) {
            throw new Error('Invalid theme');
        }
        this.theme = theme;
        localStorage.setItem('theme', theme);
        this.render();
    }
    addGlobal(key, value) {
        this.root[key] = value;
        this.render();
    }
    addGlobals(values) {
        for (let key in values) {
            this.addGlobal(key, values[key]);
        }
    }
    addStyle(key, value) {
        if (!key.startsWith("@")) {
            this.styles[key] = (this.styles[key] || '') + ";" + this._parseToString(value);
        } else {
            if (!(key in this.medias)) this.medias[key] = []
            if (this.medias[key].indexOf(value) == -1) this.medias[key].push(this._parseToString(value));
            this.styles[key] = this.medias[key].join(";");
        }
        this.render();
    }
    addStyles(values) {
        for (let key in values) {
            this.addStyle(key, values[key]);
        }
    }
    addThemes(theme, values) {
        for (let key in values) {
            this.addTheme(theme, key, values[key]);
        }
        this.render();
    }
    addTheme(theme, key, value) {
        if (!(theme in this.themes)) this.themes[theme] = {};
        if (!(key in this.themes[theme])) this.themes[theme][key] = [];
        this.themes[theme][key].push(value);
        this.render();
    }
    render() {
        if (this._raf != null) return;
        this._raf = raf(() => {
            this._render();
        })
    }
    _render() {
        this._raf = null;
        // first remove all styles

        var styles = {};
        // first theme
        var theme = this.themes[this.isDark() ? 'dark' : 'light'] || {};
        var theme_values = {};
        for (let key in theme) {
            theme_values[`--${key}`] = this._parseToString(theme[key]);
        }
        for (let key in this.root) {
            theme_values[`--${key}`] = this._parseToString(this.root[key]);
        }
        styles[':root'] = this._parseToString(theme_values);
        for (let key in this.styles) {
            styles[key] = this.styles[key];
        }
        // then add styles
        const styleRules = Object.entries(styles).map(([name, style]) => style == null ? "" : `${name}{${style}}`.replaceAll(/\n|\t|\r/g, "").replaceAll(/\s\s/g, " "));
        requestAnimationFrame(() => {
            this._clear_render()
            styleRules.forEach(styleRule => {
                this._sheet_render(styleRule);
            })
        })
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
    _clear_render() {
        this._style_sheet = this.$style.sheet;
        if (this._style_sheet) {
            this._clear_render = () => {
                while (this._style_sheet.cssRules.length > 0) {
                    this._style_sheet.deleteRule(0);
                }
            }
        } else {
            this._clear_render = () => {
                while (this.$style.childNodes.length > 0) {
                    this.$style.removeChild(this.$style.childNodes[0]);
                }
            }
        }
        this._clear_render()
    }
    _sheet_render(styleRule) {
        this._style_sheet = this.$style.sheet;
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
        this._sheet_render = (styleRule) => this.$style.appendChild(document.createTextNode(styleRule));
        this._sheet_render()
    }
}
class CTApplication {
    constructor() {
        app = this;
        // find preloader
        this.router = new CTRouterManager("/")
        this.elements = [];
        this.i18n = new CTI18N();
        this.logger = console;
        this.style = style;

        this.$document_body = document.body;
        this._body = new CTElement(this.$document_body);

        this.init();
    }
    init() {
        window.addEventListener('DOMContentLoaded', () => {
            // handle router
            
            let preloader = this.findElement('.preloader');
            if (preloader != null) {
                let style = document.head.querySelector('style');
                preloader.classes("hidden");
                preloader.listener("transitionend", () => {
                    preloader.remove();
                    style?.remove();
                }, { once: true });
            }
            this.router.init();
        }, { once: true });
    }
    findElement(selector) {
        let element = document.querySelector(selector);
        if (element == null) return null;
        return new CTElement(element);
    }
    createElement(tag) {
        return new CTElement(tag);
    }

    route(path) {
        this.router.page(path);
    }
    addRoute(path, func) {
        this.router.on(path, func);
    }

    get body() {
        return this._body;
    }
}
class CTRouteEvent {
    constructor(manager, instance, beforeRoute, currentRoute, params = {}) {
        this.manager = manager
        this.instance = instance;
        this.currentRoute = currentRoute
        this.beforeRoute = beforeRoute
        this.params = params
    }
}
class CTRouter {
    constructor(
        route_prefix = "/",
    ) {
        this._route_prefix = route_prefix.replace(/\/+$/, "")
        this._routes = []
        this._beforeHandlers = []
        this._afterHandlers = []
        this._currentPath = null
    }
    get _getCurrentPath() {
        return window.location.pathname.replace(this._route_prefix, "") || "/"
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
    beforeHandler(handler) {
        if (handler == null) this;
        this._beforeHandlers.push(handler)
        return this
    }
    afterHandler(handler) {
        if (handler == null) this;
        this._afterHandlers.push(handler)
        return this
    }

}
class CTRouterManager {
    constructor(
        route_prefix = "/",
    ) {
        this._routes = [
            new CTRouter(route_prefix)
        ]
    }
    init() {
        window.addEventListener("popstate", () => {
            this._popstateHandler()
        })
        window.addEventListener("click", (e) => {
            if (e.target.tagName == "A") {
                const href = e.target.getAttribute("href")
                const url = new URL(href, window.location.origin);
                if (url.origin != window.location.origin) return;
                e.preventDefault()
                if (url.pathname.startsWith(this._route_prefix)) {
                    this._popstateHandler(url.pathname)
                }
            }
        })
        this._popstateHandler()
    }
    get _getCurrentPath() {
        return window.location.pathname
    }
    _popstateHandler(path) {
        path = path || this._getCurrentPath
        const matchRoutes = []
        for (const router of this._routes) {
            if (path.startsWith(router._route_prefix)) {
                matchRoutes.push(router)
            }
        }
        if (!matchRoutes.length) matchRoutes.push(this._routes[0])
        const handlers = {
            before: [],
            route: [],
            after: []
        };
        var router = null;
        for (const r of matchRoutes) {
            let new_path = path.replace(r._route_prefix, "") || "/"
            var match_routes = r._routes.filter(x => x.path.test(new_path))
            if (match_routes.length) {
                router = r
                break
            }
        }
        router = router || matchRoutes[0]
        const old_path = router._currentPath
        const new_path = path.replace(router._route_prefix, "") || "/"
        if (new_path == router._currentPath) return;
        router._currentPath = new_path
        window.history.pushState(null, '', router._route_prefix + new_path)
        for (const handler of router._beforeHandlers) {
            handlers.before.push(handler)
        }

        // route
        for (const route of router._routes.filter(x => x.path.test(new_path))) {
            handlers.route.push(route)
        }
        // after
        for (const handler of router._afterHandlers) {
            handlers.after.push(handler)
        }
        this._run(handlers, {
            manager: this,
            router,
            old_path: old_path,
            new_path: new_path,
        })
    }
    _run(handlers = {
        before: [],
        route: [],
        after: []
    }, options = {
        manager: this,
        router: null,
        old_path: null,
        new_path: null,
    }) {
        var preHandle = (
            preHandlers
        ) => {
            preHandlers.forEach(handler => {
                try {
                    handler(new CTRouteEvent(
                        options.manager,
                        options.router,
                        options.old_path,
                        options.new_path,
                    ))
                } catch (e) {
                    console.error(e)
                }
            })
        }
        preHandle(handlers.before)
        try {
            handlers.route.forEach(route => {
                var params = route.path.exec(options.new_path).slice(1).reduce((acc, cur, i) => {
                    acc[route.params[i]] = cur
                    return acc
                }, {})
                var handler = route ? route.handler : null
                if (handler) {
                    try {
                        handler(new CTRouteEvent(
                            options.manager,
                            options.router,
                            options.old_path,
                            options.new_path,
                            params
                        ))
                    } catch (e) {
                        console.log(e)
                    }
                }
            })
        } catch (e) {
            console.error(e)

        }
        preHandle(handlers.after)
        return true
    }
    on(path, handler) {
        this._routes[0].on(path, handler)
        return this
    }
    beforeHandler(handler) {
        this._routes[0].beforeHandler(handler)
        return this
    }
    afterHandler(handler) {
        this._routes[0].afterHandler(handler)
        return this
    }
    page(path) {
        this._popstateHandler(
            this._routes[0]._route_prefix + path
        )
        return this
    }
}
class CTI18NChangeEvent extends Event {
    constructor() {
        super("cti18nchange");
    }
}
class CTI18N {
    constructor() {
        i18n = this;
        this.defaultLang = "zh-cn"
        this.currentLang = this.defaultLang;
        this.languages = {}
    }
    setLang(lang) {
        this.currentLang = lang;
        // trigger event;
        window.dispatchEvent(new CTI18NChangeEvent());
    }
    addLanguage(lang, key, value) {
        if (!(lang in this.languages)) this.languages[lang] = {};
        this.languages[lang][key] = value;
    }
    addLanguages(lang, obj) {
        for (let key in obj) {
            this.addLanguage(lang, key, obj[key]);
        }
    }
    t(key, params) {
        let lang = this.currentLang;
        if (!(lang in this.languages) || !(key in this.languages[lang])) return key;
        let value = this.languages[lang][key];
        if (params != null) {
            for (let key in params) {
                value = value.replace("{" + key + "}", params[key]);
            }
        }
        return value || key;
    }
}
export function raf(callback) {
    return requestAnimationFrame(callback);
}
export function createApp() {
    if (app == null) {
        style = new CTStyle();
        app = new CTApplication();
        app.init();
        globalThis.app = app;
    }
    return app;
}
export function createRouter(
    prefix = "/"
) {
    return new CTRouter(prefix);
}
var observeOptions = {
    debouned: 0,
    handler: null
}
export function observe(obj, options = observeOptions) {
    let merged = Object.assign({}, observeOptions, options);
    var pending = [];
    var task = null;
    return new Proxy(proxy, {
        set(target, key, value) {
            if (merged.handler == null) return;
            target[key] = value;
            if (merged.debouned == 0) {
                handler({
                    object: target,
                    key: key,
                    value: value
                })
            } else {
                if (task != null) clearTimeout(task)
                pending.push({
                    key: key,
                    value: value
                })
                task = setTimeout(() => {
                    clearTimeout(task)
                    let changes = pending.copyWithin(0, pending.length);
                    pending = [];
                    handler({
                        object: target,
                        changes
                    })  
                })
            }
        }
    })
}